import json
import logging
import asyncio
import time
from typing import Any, NamedTuple

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part, TaskState, TextPart
from a2a.utils.message import new_agent_text_message
from a2a.utils.errors import ServerError, UnsupportedOperationError

# Make sure you have a shared config for the artifact name
from common.config import DEFAULT_SDR_ARTIFACT_NAME, DEFAULT_UI_CLIENT_URL

from google.adk import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.adk.artifacts import InMemoryArtifactService
from google.adk.events import Event, EventActions
from google.genai import types as genai_types

# ADK Authentication related imports
from google.adk.auth import AuthConfig, AuthCredential, AuthScheme
from google.adk.tools.openapi_tool.openapi_spec_parser.tool_auth_handler import (
    ToolContextCredentialStore,
)


# Import the SDR agent
from .sdr.agent import root_agent


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # Enable DEBUG logging for ADK events

# --- Authentication Helpers (Copy-pasted from original adk_agent_executor.py) ---
class ADKAuthDetails(NamedTuple):
    """Contains a collection of properties related to handling ADK authentication."""
    state: str
    uri: str
    future: asyncio.Future
    auth_config: AuthConfig
    auth_request_function_call_id: str

class StoredCredential(NamedTuple):
    """Contains OAuth2 credentials."""
    key: str
    credential: AuthCredential

# 1 minute timeout to keep the demo moving.
auth_receive_timeout_seconds = 60

def convert_genai_parts_to_a2a(parts: list[genai_types.Part]) -> list[Part]:
    """Convert a list of Google Gen AI Part types into a list of A2A Part types."""
    # Simplified for example; ensure full conversion logic if needed for files etc.
    a2a_parts = []
    for part in parts:
        if part.text:
            a2a_parts.append(Part(root=TextPart(text=part.text)))
        # Add logic for file_data, inline_data if your SDR agent handles them
    return a2a_parts

def get_auth_request_function_call(event: Event) -> genai_types.FunctionCall | None:
    """Get the special auth request function call from the event."""
    if not (event.content and event.content.parts):
        return None
    for part in event.content.parts:
        if (
            part
            and part.function_call
            and part.function_call.name == 'adk_request_credential'
            and event.long_running_tool_ids # Check if it's a long-running tool request
            and part.function_call.id in event.long_running_tool_ids
        ):
            return part.function_call
    return None

def get_auth_config(
    auth_request_function_call: genai_types.FunctionCall,
) -> AuthConfig:
    """Extracts the AuthConfig object from the arguments of the auth request function call."""
    if not auth_request_function_call.args or not (
        auth_config := auth_request_function_call.args.get('authConfig')
    ):
        raise ValueError(
            f'Cannot get auth config from function call: {auth_request_function_call}'
        )
    return AuthConfig.model_validate(auth_config)
# --- End of Authentication Helpers ---


class SDRAgentExecutor(AgentExecutor):
    """Executes the SDR ADK agent logic in response to A2A requests."""

    _awaiting_auth: dict[str, asyncio.Future]
    _credentials: dict[str, StoredCredential]

    def __init__(self):
        self._adk_agent = root_agent
        self._adk_runner = Runner(
            app_name="sdr_adk_runner",
            agent=self._adk_agent,
            session_service=InMemorySessionService(),
            artifact_service=InMemoryArtifactService(),
        )
        self._awaiting_auth = {} # Initialize auth state
        self._credentials = {} # Initialize credential storage
        logger.info("SDRAgentExecutor initialized with ADK Runner, artifact service, and auth handlers.")

    # --- Authentication Handling Methods (Copy-pasted and adapted) ---
    async def on_auth_callback(self, state: str, uri: str):
        """Called by the main Starlette app when an OAuth callback is received."""
        logger.debug(f"on_auth_callback received for state: {state}, uri: {uri}")
        if state in self._awaiting_auth:
            self._awaiting_auth[state].set_result(uri)
        else:
            logger.warning(f"No pending authentication request found for state: {state}")

    def _prepare_auth_request(
        self, auth_request_function_call: genai_types.FunctionCall, agent_card_url: str # Needs agent_card_url to build redirect_uri
    ) -> ADKAuthDetails:
        """Prepares the authentication request details."""
        if not (auth_request_function_call_id := auth_request_function_call.id):
            raise ValueError(
                f'Cannot get function call id from function call: {auth_request_function_call}'
            )
        auth_config = get_auth_config(auth_request_function_call)
        if not (auth_config and auth_request_function_call_id):
            raise ValueError(
                f'Cannot get auth config from function call: {auth_request_function_call}'
            )
        oauth2_config = auth_config.exchanged_auth_credential.oauth2
        base_auth_uri = oauth2_config.auth_uri
        if not base_auth_uri:
            raise ValueError(
                f'Cannot get auth uri from auth config: {auth_config}'
            )
        
        # Ensure agent_card_url ends with a slash if it's the base for routes
        if not agent_card_url.endswith('/'):
            agent_card_url += '/'
        redirect_uri = f'{agent_card_url}authenticate' # Use the SDR agent's own /authenticate endpoint
        
        oauth2_config.redirect_uri = redirect_uri
        state_token = oauth2_config.state
        future = asyncio.get_running_loop().create_future()
        self._awaiting_auth[state_token] = future
        
        # Google Calendar tool might append query params, just ensure redirect_uri is set
        auth_request_uri = base_auth_uri + f'&redirect_uri={redirect_uri}'

        logger.debug(f"Prepared auth request URI: {auth_request_uri}")
        return ADKAuthDetails(
            state=state_token,
            uri=auth_request_uri,
            future=future,
            auth_config=auth_config,
            auth_request_function_call_id=auth_request_function_call_id,
        )

    async def _complete_auth_processing(
        self,
        context: RequestContext,
        auth_details: ADKAuthDetails,
        task_updater: TaskUpdater,
        initial_message_content: genai_types.Content # Need original message to resume
    ) -> None:
        logger.debug('Waiting for auth event from callback')
        try:
            auth_uri = await asyncio.wait_for(
                auth_details.future, timeout=auth_receive_timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.debug('Timed out waiting for auth, marking task as failed')
            task_updater.update_status(
                TaskState.failed,
                message=new_agent_text_message(
                    'Timed out waiting for authorization.',
                    context_id=context.context_id,
                ),
            )
            return
        logger.debug('Auth received, continuing with ADK runner')
        await task_updater.update_status(
            TaskState.working,
            message=new_agent_text_message(
                'Auth received, continuing...', context_id=context.context_id
            ),
        )
        del self._awaiting_auth[auth_details.state]

        # Update the auth config with the response URI
        oauth2_config = (
            auth_details.auth_config.exchanged_auth_credential.oauth2
        )
        oauth2_config.auth_response_uri = auth_uri

        # Create a FunctionResponse for adk_request_credential
        auth_content = genai_types.Content(
            parts=[
                genai_types.Part(
                    function_response=genai_types.FunctionResponse(
                        id=auth_details.auth_request_function_call_id,
                        name='adk_request_credential', # Must match the requested function name
                        response=auth_details.auth_config.model_dump(), # The full authConfig
                    ),
                )
            ]
        )
        
        # Resume the ADK runner with the auth response
        # The key is to provide the *original message* along with the auth response.
        # This is where the ADK Runner knows to continue the interrupted flow.
        logger.info(f"Resuming ADK runner with auth response for session: {context.context_id}")
        async for event in self._adk_runner.run_async(
            user_id="a2a_user", # Or actual user ID
            session_id=context.context_id,
            new_message=initial_message_content, # The original user message that triggered the auth
            tool_response=auth_content # The authentication response
        ):
            # Process events from the resumed run
            await self._process_adk_event(event, context, task_updater)


        # Extract and store the stored credential after a successful run
        # This ensures future sessions for this user can preload auth
        if context.call_context and context.call_context.user.is_authenticated:
            await self._store_user_auth(
                context,
                auth_details.auth_config.auth_scheme,
                auth_details.auth_config.raw_auth_credential,
            )

    async def _ensure_auth(self, session: Session) -> Session:
        """Ensures that previously stored credentials are loaded into the session."""
        user_id = session.user_id # Use the session's user_id for credential lookup
        if (
            stored_cred := self._credentials.get(user_id)
        ) and not session.state.get(stored_cred.key):
            event_action = EventActions(
                state_delta={
                    stored_cred.key: stored_cred.credential,
                }
            )
            event = Event(
                invocation_id='preload_auth',
                author='system',
                actions=event_action,
                timestamp=time.time(),
            )
            logger.debug('Preloading authorization state for session: %s', session.id)
            await self._adk_runner.session_service.append_event(session, event)
        return session

    async def _store_user_auth(
        self,
        context: RequestContext,
        auth_scheme: AuthScheme,
        raw_credential: AuthCredential,
    ) -> None:
        """Stores the user's OAuth2 credential for future sessions."""
        user_id = 'a2a_user' # Default for A2A if user not authenticated by your backend
        if context.call_context and context.call_context.user.is_authenticated:
            user_id = context.call_context.user.user_name

        session = await self._adk_runner.session_service.get_session(
            app_name=self._adk_runner.app_name,
            user_id=user_id,
            session_id=context.context_id,
        )
        if not session:
            logger.warning(f"Cannot store auth: session not found for user {user_id}, session {context.context_id}")
            return

        # ToolContextCredentialStore doesn't require the tool context to
        # get the credential key, so we can just pass None.
        tool_credential_store = ToolContextCredentialStore(None)
        credential_key = tool_credential_store.get_credential_key(
            auth_scheme,
            raw_credential,
        )
        stored_credential = session.state.get(credential_key) # Get from current session state
        if stored_credential: # Only store if it was actually in the session state
            self._credentials[user_id] = (
                StoredCredential(
                    key=credential_key, credential=stored_credential
                )
            )
            logger.info(f"Stored credential for user: {user_id}")
        else:
            logger.warning(f"No credential found in session state for key {credential_key} to store.")

    # --- Core Execution Logic (Modified to handle auth) ---
    async def _process_adk_event(
        self, event: Event, context: RequestContext, task_updater: TaskUpdater
    ):
        """Helper to process individual ADK events."""
        if auth_request_function_call := get_auth_request_function_call(event):
            # Auth is required! Pause execution and instruct user.
            # Need the agent_card_url from context or configuration
            # For simplicity, pass it down from the execute method.
            agent_card_url = DEFAULT_UI_CLIENT_URL # Assuming this is your base URL for redirects

            auth_details = self._prepare_auth_request(
                auth_request_function_call, agent_card_url # Pass the URL
            )
            logger.info(
                f'Task {context.task_id}: Authorization required. Visit {auth_details.uri}'
            )
            await task_updater.update_status(
                TaskState.auth_required,
                message=new_agent_text_message(
                    f'Authorization is required to continue. Please visit this link to authorize: {auth_details.uri}'
                ),
                # You might want to include the auth_details.uri in artifact for UI
                # artifacts=[Part(root=DataPart(data={"auth_uri": auth_details.uri}))]
            )
            # DO NOT BREAK here in a simple loop, the outer execute method will
            # be responsible for handling the waiting and resumption.
            # We return the auth_details to indicate auth was requested and provide
            # the necessary details for resumption.
            return auth_details # Return auth details

        if event.is_final_response():
            parts = convert_genai_parts_to_a2a(event.content.parts)
            logger.debug(f'Task {context.task_id}: Final response: {parts}')
            # This is where the final result from the calendar tool (or other tools)
            # would be handled by the SDR agent's logic.
            # For now, just pass it through as an artifact.
            # Your SDR agent's instruction should guide it to produce specific outputs.
            await task_updater.add_artifact(parts, name="sdr_final_output")
            await task_updater.complete()
            return False # Indicate completion

        if event.content and not event.get_function_calls():
            # This is a streaming text response from the LLM, but not a tool call
            parts = convert_genai_parts_to_a2a(event.content.parts)
            logger.debug(f'Task {context.task_id}: Intermediate text response: {parts}')
            await task_updater.update_status(
                TaskState.working,
                message=task_updater.new_agent_message(parts),
            )
            return False

        # If it's a function call *that's not an auth request*, or other event types,
        # we typically just let the ADK Runner process it and wait for the next event.
        logger.debug(f'Task {context.task_id}: Skipping event type: {event.event_type} or non-text content.')
        return False


    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task_updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        logger.info(f"DEBUG: Context message parts: {[str(part) for part in context.message.parts]}")

        if not context.current_task:
            task_updater.submit(message=context.message)

        task_updater.start_work(
            message=task_updater.new_agent_message(
                parts=[
                    Part(root=DataPart(data={"status": "Processing SDR request for business lead..."}))
                ]
            )
        )

        business_data: dict | None = None
        ui_client_url = DEFAULT_UI_CLIENT_URL # Fallback to default

        if context.message and context.message.parts:
            for part_union in context.message.parts:
                part = part_union.root
                if isinstance(part, DataPart):
                    # Try to extract business lead data and ui_client_url
                    business_data_candidate = part.data.get("business_data") or part.data.get("lead") or part.data.get("business")
                    if business_data_candidate:
                         # Basic check if it looks like business data
                        if "name" in business_data_candidate and ("phone" in business_data_candidate or "email" in business_data_candidate):
                            business_data = business_data_candidate
                        else: # If not nested, assume the part.data is the business data
                            if "name" in part.data and ("phone" in part.data or "email" in part.data):
                                business_data = part.data

                    if "ui_client_url" in part.data:
                        ui_client_url = part.data["ui_client_url"]

        if business_data is None:
            logger.error(f"Task {context.task_id}: Missing business lead data in input")
            await task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[
                        Part(
                            root=DataPart(
                                data={"error": "Invalid input: Missing business lead data"}
                            )
                        )
                    ]
                )
            )
            return

        business_name = business_data.get("name", "Unknown Business")
        user_message_text = f"Process SDR outreach for business lead: {business_name}. Here is the full lead data: {json.dumps(business_data)}. The UI client URL is: {ui_client_url}"

        # Create both text and structured data
        initial_adk_content = genai_types.Content(
            parts=[
                genai_types.Part(text=user_message_text),
                genai_types.Part(text=json.dumps({
                    "business_data": business_data,
                    "ui_client_url": ui_client_url,
                    "operation": "sdr_outreach"
                }))
            ]
        )

        session_id_for_adk = context.context_id
        logger.info(f"Task {context.task_id}: Using ADK session_id: '{session_id_for_adk}' for business: '{business_name}'")

        session: Session | None = None
        try:
            session = await self._adk_runner.session_service.get_session(
                app_name=self._adk_runner.app_name,
                user_id="a2a_user", # Consider using a real user ID from context.call_context.user
                session_id=session_id_for_adk,
            )
            if not session:
                logger.info(f"Task {context.task_id}: Creating new ADK session for business: {business_name}")
                session = await self._adk_runner.session_service.create_session(
                    app_name=self._adk_runner.app_name,
                    user_id="a2a_user",
                    session_id=session_id_for_adk,
                    state={"business_data": business_data},  # Store business data in session state
                )
            if session:
                session = await self._ensure_auth(session) # Load any pre-existing auth
                logger.info(f"Task {context.task_id}: Successfully obtained/created ADK session for business: {business_name}")
        except Exception as e:
            logger.exception(f"Task {context.task_id}: Exception during session handling: {e}")
            await task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[
                        Part(
                            root=DataPart(
                                data={"error": f"Internal error during session setup: {e}"}
                            )
                        )
                    ]
                )
            )
            return

        if not session:
            error_message = f"Failed to establish ADK session for business '{business_name}'"
            logger.error(f"Task {context.task_id}: {error_message}")
            await task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[
                        Part(
                            root=DataPart(
                                data={"error": f"Internal error: {error_message}"}
                            )
                        )
                    ]
                )
            )
            return

        # --- Main execution loop ---
        try:
            logger.info(f"Task {context.task_id}: Starting ADK run_async for business: {business_name}")
            
            # Use a variable to track auth details if needed
            auth_details = None

            async for event in self._adk_runner.run_async(
                user_id="a2a_user",
                session_id=session_id_for_adk,
                new_message=initial_adk_content,
            ):
                auth_result = await self._process_adk_event(event, context, task_updater)
                if auth_result:
                    auth_details = auth_result
                    logger.info(f"Auth requested, suspending ADK run for task {context.task_id}")
                    # Break out of the current run_async loop to wait for auth callback
                    break
            
            if auth_details:
                # If auth was requested, _complete_auth_processing will resume the runner
                # and continue processing.
                logger.info(f"Task {context.task_id}: Now waiting for auth callback to resume processing...")
                await self._complete_auth_processing(
                    context, auth_details, task_updater, initial_adk_content
                )
            
            # After the loop finishes (either naturally or after auth resumption),
            # the task_updater.complete() or .failed() should have been called
            # by _process_adk_event or _complete_auth_processing.
            logger.info(f"Task {context.task_id}: ADK execute finished for {business_name}.")

        except Exception as e:
            logger.exception(f"Task {context.task_id}: Error running SDR ADK agent for business {business_name}: {e}")
            await task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[Part(root=DataPart(data={"error": f"ADK Agent error: {e}"}))]
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        logger.warning(f"Cancellation not implemented for SDR task: {context.task_id}")
        task_updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await task_updater.failed(
            message=task_updater.new_agent_message(
                parts=[Part(root=DataPart(data={"error": "Task cancelled"}))]
            )
        )
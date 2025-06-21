import json
import logging
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part, TaskState

# Make sure you have a shared config for the artifact name
from common.config import DEFAULT_SDR_ARTIFACT_NAME, DEFAULT_UI_CLIENT_URL
from google.adk import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types as genai_types

from .sdr.agent import sdr_agent

logger = logging.getLogger(__name__)

class SDRAgentExecutor(AgentExecutor):
    """Executes the SDR ADK agent logic in response to A2A requests."""

    def __init__(self):
        self._adk_agent = sdr_agent
        # IMPORTANT: Add artifact_service to the Runner initialization
        self._adk_runner = Runner(
            app_name="sdr_adk_runner",
            agent=self._adk_agent,
            session_service=InMemorySessionService(),
            artifact_service=InMemoryArtifactService(),
        )
        logger.info("SDRAgentExecutor initialized with ADK Runner and artifact service.")

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

        # Extract business lead data from context.message
        business_data: dict | None = None
        ui_client_url = DEFAULT_UI_CLIENT_URL

        if context.message and context.message.parts:
            for part_union in context.message.parts:
                part = part_union.root
                if isinstance(part, DataPart):
                    # Try to extract business lead data
                    if "business_data" in part.data:
                        business_data = part.data["business_data"]
                    elif "lead" in part.data:
                        business_data = part.data["lead"]
                    elif "business" in part.data:
                        business_data = part.data["business"]
                    else:
                        # If the entire data part looks like business data
                        if "name" in part.data and ("phone" in part.data or "email" in part.data):
                            business_data = part.data
                    
                    if "ui_client_url" in part.data:
                        ui_client_url = part.data["ui_client_url"]

        if business_data is None:
            logger.error(f"Task {context.task_id}: Missing business lead data in input")
            task_updater.failed(
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

        
        # Create a clear user message for the agent
        business_name = business_data.get("name", "Unknown Business")
        user_message = f"Process SDR outreach for business lead: {business_name}"
        
        # Create both text and structured data
        adk_content = genai_types.Content(
            parts=[
                genai_types.Part(text=user_message),
                genai_types.Part(text=json.dumps({
                    "business_data": business_data, 
                    "ui_client_url": ui_client_url,
                    "operation": "sdr_outreach"
                }))
            ]
        )

        # Session handling code
        session_id_for_adk = context.context_id
        logger.info(f"Task {context.task_id}: Using ADK session_id: '{session_id_for_adk}' for business: '{business_name}'")

        session: Session | None = None
        if session_id_for_adk:
            try:
                session = await self._adk_runner.session_service.get_session(
                    app_name=self._adk_runner.app_name,
                    user_id="a2a_user",
                    session_id=session_id_for_adk,
                )
            except Exception as e:
                logger.exception(f"Task {context.task_id}: Exception during get_session: {e}")
                session = None

            if not session:
                logger.info(f"Task {context.task_id}: Creating new ADK session for business: {business_name}")
                try:
                    session = await self._adk_runner.session_service.create_session(
                        app_name=self._adk_runner.app_name,
                        user_id="a2a_user",
                        session_id=session_id_for_adk,
                        state={
                            "business_data": business_data,
                            "call_result": '',
                            "refined_requirements": '',
                            "website_preview_link": '',
                            "offer_file_path": '',
                            "crafted_email": '',
                        },  # Store business data in session state
                    )
                    if session:
                        logger.info(f"Task {context.task_id}: Successfully created ADK session for business: {business_name}")
                except Exception as e:
                    logger.exception(f"Task {context.task_id}: Exception during create_session: {e}")
                    session = None

        if not session:
            error_message = f"Failed to establish ADK session for business '{business_name}'"
            logger.error(f"Task {context.task_id}: {error_message}")
            task_updater.failed(
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

        # Initialize optional state variables to avoid missing context errors in subsequent agents
        # e.g., offer_file_path and website_preview_link used by the email agent templates
        try:
            if "offer_file_path" not in session.state:
                session.state["offer_file_path"] = ""
            if "website_preview_link" not in session.state:
                session.state["website_preview_link"] = ""
        except Exception:
            logger.warning(f"Task {context.task_id}: Unable to set default state keys for offer_file_path or website_preview_link")

        # Execute the ADK Agent
        try:
            logger.info(f"Task {context.task_id}: Calling ADK run_async for business: {business_name}")
            final_result = {"status": "completed", "business_name": business_name, "sdr_result": {}}
            
            # Collect all results from the agent pipeline
            all_events = []
            phone_call_result = None
            
            async for event in self._adk_runner.run_async(
                user_id="a2a_user",
                session_id=session_id_for_adk,
                new_message=adk_content,
            ):
                # Collect and log the raw event
                all_events.append(event)
                logger.info(f"Task {context.task_id}: ADK Event: {event}")
                # Stream intermediate agent messages back to the client
                # so that human-in-the-loop prompts (e.g., website creation) are surfaced
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        # Text parts: relay to client as working status updates
                        if hasattr(part, "text") and part.text:
                            try:
                                from a2a.types import TextPart
                                msg = task_updater.new_agent_message(
                                    parts=[Part(root=TextPart(text=part.text))]
                                )
                                task_updater.update_status(TaskState.working, message=msg)
                            except ImportError:
                                # Fallback: send as data part
                                msg = task_updater.new_agent_message(
                                    parts=[Part(root=DataPart(data={"text": part.text}))]
                                )
                                task_updater.update_status(TaskState.working, message=msg)
                        # Function call events: relay tool invocation details
                        if hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call
                            # Send the tool name and args for transparency
                            msg = task_updater.new_agent_message(
                                parts=[Part(root=DataPart(data={
                                    "tool_call": fc.name,
                                    "args": fc.args
                                }))]
                            )
                            task_updater.update_status(TaskState.working, message=msg)
                
                # Capture function call results (like phone_call)
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        # Look for function calls
                        if hasattr(part, 'function_call') and part.function_call:
                            function_name = part.function_call.name
                            logger.info(f"Task {context.task_id}: Function call detected: {function_name}")
                            
                            # Capture phone call results
                            if function_name == "phone_call":
                                phone_call_result = part.function_call.args
                                logger.info(f"Task {context.task_id}: Phone call result captured")
                                
                            # Look for final SDR results
                            elif function_name == "final_sdr_results":
                                sdr_result = part.function_call.args.get("sdr_result", {})
                                final_result["sdr_result"] = sdr_result
                                logger.info(f"Task {context.task_id}: SDR process completed for {business_name}")
                        
                        # Also capture text responses
                        elif hasattr(part, "text") and part.text:
                            final_result["message"] = part.text
                
                # For final responses, ensure we have all the data
                if event.is_final_response():
                    logger.info(f"Task {context.task_id}: Final response received")

            # Add phone call result to final result if we captured it
            if phone_call_result:
                final_result["phone_call_result"] = phone_call_result
                logger.info(f"Task {context.task_id}: Added phone call result to final output")

            # Log the complete final result
            logger.info(f"Task {context.task_id}: Complete final result: {json.dumps(final_result, indent=2)}")

            task_updater.add_artifact(
                parts=[Part(root=DataPart(data=final_result))],
                name="sdr_results",
            )
            task_updater.complete()

        except Exception as e:
            logger.exception(f"Task {context.task_id}: Error running SDR ADK agent for business {business_name}: {e}")
            task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[Part(root=DataPart(data={"error": f"ADK Agent error: {e}"}))]
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        logger.warning(f"Cancellation not implemented for SDR task: {context.task_id}")
        task_updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        task_updater.failed(
            message=task_updater.new_agent_message(
                parts=[Part(root=DataPart(data={"error": "Task cancelled"}))]
            )
        )
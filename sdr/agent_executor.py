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
from google.genai import types as genai_types

from .sdr.agent import sdr_agent

logger = logging.getLogger(__name__)


class SDRAgentExecutor(AgentExecutor):
    """Executes the SDR ADK agent logic in response to A2A requests."""

    def __init__(self):
        self._adk_agent = sdr_agent
        self._adk_runner = Runner(
            app_name="sdr_adk_runner",
            agent=self._adk_agent,
            session_service=InMemorySessionService(),
        )
        logger.info("SDRAgentExecutor initialized with ADK Runner.")

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

        # Prepare input for ADK Agent with clear structure
        agent_input_dict = {
            "business_data": business_data,
            "ui_client_url": ui_client_url,
            "operation": "sdr_outreach"
        }
        
        # Create a clear user message for the agent
        business_name = business_data.get("name", "Unknown Business")
        user_message = f"Process SDR outreach for business lead: {business_name}"
        
        # Create both text and structured data
        adk_content = genai_types.Content(
            parts=[
                genai_types.Part(text=user_message),
                genai_types.Part(text=json.dumps(agent_input_dict))
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
                        state={"business_data": business_data},  # Store business data in session state
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

        # Execute the ADK Agent
        try:
            logger.info(f"Task {context.task_id}: Calling ADK run_async for business: {business_name}")
            final_result = {"status": "completed", "business_name": business_name, "sdr_result": {}}
            
            async for event in self._adk_runner.run_async(
                user_id="a2a_user",
                session_id=session_id_for_adk,
                new_message=adk_content,
            ):
                if event.is_final_response():
                    if event.content and event.content.parts:
                        # Look for function calls with SDR results
                        for part in event.content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                if part.function_call.name == "final_sdr_results":
                                    sdr_result = part.function_call.args.get("sdr_result", {})
                                    final_result["sdr_result"] = sdr_result
                                    logger.info(f"Task {context.task_id}: SDR process completed for {business_name}")
                            elif hasattr(part, "text") and part.text:
                                final_result["message"] = part.text

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
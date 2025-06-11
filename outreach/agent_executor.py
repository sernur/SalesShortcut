import json
import logging
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part, TaskState

# Make sure you have a shared config for the artifact name
from common.config import DEFAULT_OUTREACH_ARTIFACT_NAME, DEFAULT_UI_CLIENT_URL
from google.adk import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types as genai_types

from .outreach.agent import outreach_agent

logger = logging.getLogger(__name__)


class OutreachAgentExecutor(AgentExecutor):
    """Executes the Outreach ADK agent logic in response to A2A requests."""

    def __init__(self):
        self._adk_agent = outreach_agent
        self._adk_runner = Runner(
            app_name="outreach_adk_runner",
            agent=self._adk_agent,
            session_service=InMemorySessionService(),
        )
        logger.info("OutreachAgentExecutor initialized with ADK Runner.")

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task_updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        
        logger.info(f"DEBUG: Context message parts: {[str(part) for part in context.message.parts]}")

        if not context.current_task:
            task_updater.submit(message=context.message)

        task_updater.start_work(
            message=task_updater.new_agent_message(
                parts=[
                    Part(root=DataPart(data={"status": "Processing outreach request..."}))
                ]
            )
        )

        # Extract outreach parameters from context.message
        outreach_target: str | None = None
        outreach_type: str | None = None
        outreach_message: str | None = None
        ui_client_url = DEFAULT_UI_CLIENT_URL

        if context.message and context.message.parts:
            for part_union in context.message.parts:
                part = part_union.root
                if isinstance(part, DataPart):
                    # Try multiple keys for outreach parameters
                    if "target" in part.data:
                        outreach_target = part.data["target"]
                    elif "phone" in part.data:
                        outreach_target = part.data["phone"]
                    elif "email" in part.data:
                        outreach_target = part.data["email"]
                    
                    if "type" in part.data:
                        outreach_type = part.data["type"]
                    elif "action" in part.data:
                        outreach_type = part.data["action"]
                    
                    if "message" in part.data:
                        outreach_message = part.data["message"]
                    elif "script" in part.data:
                        outreach_message = part.data["script"]
                    elif "content" in part.data:
                        outreach_message = part.data["content"]
                    
                    if "ui_client_url" in part.data:
                        ui_client_url = part.data["ui_client_url"]

        if outreach_target is None:
            logger.error(f"Task {context.task_id}: Missing outreach target (phone/email) in input")
            task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[
                        Part(
                            root=DataPart(
                                data={"error": "Invalid input: Missing outreach target"}
                            )
                        )
                    ]
                )
            )
            return

        # Default values if not provided
        if outreach_type is None:
            outreach_type = "email" if "@" in outreach_target else "phone"
        if outreach_message is None:
            outreach_message = "Professional outreach message"

        # Prepare input for ADK Agent with clear structure
        agent_input_dict = {
            "target": outreach_target,
            "type": outreach_type,
            "message": outreach_message,
            "ui_client_url": ui_client_url,
            "operation": "conduct_outreach"
        }
        
        # Create a clear user message for the agent
        user_message = f"Conduct {outreach_type} outreach to {outreach_target}"
        
        # Create both text and structured data
        adk_content = genai_types.Content(
            parts=[
                genai_types.Part(text=user_message),
                genai_types.Part(text=json.dumps(agent_input_dict))
            ]
        )

        # [Rest of the session handling code remains the same...]
        session_id_for_adk = context.context_id
        logger.info(f"Task {context.task_id}: Using ADK session_id: '{session_id_for_adk}' for outreach: '{outreach_target}'")

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
                logger.info(f"Task {context.task_id}: Creating new ADK session for outreach: {outreach_target}")
                try:
                    session = await self._adk_runner.session_service.create_session(
                        app_name=self._adk_runner.app_name,
                        user_id="a2a_user",
                        session_id=session_id_for_adk,
                        state={"target": outreach_target, "type": outreach_type},
                    )
                    if session:
                        logger.info(f"Task {context.task_id}: Successfully created ADK session for outreach: {outreach_target}")
                except Exception as e:
                    logger.exception(f"Task {context.task_id}: Exception during create_session: {e}")
                    session = None

        if not session:
            error_message = f"Failed to establish ADK session for outreach '{outreach_target}'"
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
            logger.info(f"Task {context.task_id}: Calling ADK run_async for outreach: {outreach_target}")
            final_result = {"status": "completed", "target": outreach_target, "type": outreach_type, "results": []}
            
            async for event in self._adk_runner.run_async(
                user_id="a2a_user",
                session_id=session_id_for_adk,
                new_message=adk_content,
            ):
                if event.is_final_response():
                    if event.content and event.content.parts:
                        # Look for function calls with outreach data
                        for part in event.content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                if part.function_call.name in ["phone_call_tool", "message_email_tool"]:
                                    outreach_results = part.function_call.args
                                    final_result["results"].append(outreach_results)
                                    logger.info(f"Task {context.task_id}: Completed {part.function_call.name} for {outreach_target}")
                            elif hasattr(part, "text") and part.text:
                                final_result["message"] = part.text

            task_updater.add_artifact(
                parts=[Part(root=DataPart(data=final_result))],
                name="outreach_results",
            )
            task_updater.complete()

        except Exception as e:
            logger.exception(f"Task {context.task_id}: Error running Outreach ADK agent for target {outreach_target}: {e}")
            task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[Part(root=DataPart(data={"error": f"ADK Agent error: {e}"}))]
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        logger.warning(f"Cancellation not implemented for Outreach task: {context.task_id}")
        task_updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        task_updater.failed(
            message=task_updater.new_agent_message(
                parts=[Part(root=DataPart(data={"error": "Task cancelled"}))]
            )
        )
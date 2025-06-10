import json
import logging
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part, TaskState

# Make sure you have a shared config for the artifact name
from common.config import DEFAULT_LEAD_FINDER_ARTIFACT_NAME
from google.adk import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types as genai_types

from .lead_finder.agent import lead_finder_agent

logger = logging.getLogger(__name__)


class LeadFinderAgentExecutor(AgentExecutor):
    """Executes the Lead Finder ADK agent logic in response to A2A requests."""

    def __init__(self):
        self._adk_agent = lead_finder_agent
        self._adk_runner = Runner(
            app_name="lead_finder_adk_runner",
            agent=self._adk_agent,
            session_service=InMemorySessionService(),
        )
        logger.info("LeadFinderAgentExecutor initialized with ADK Runner.")

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task_updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        if not context.current_task:
            task_updater.submit(message=context.message)

        task_updater.start_work(
            message=task_updater.new_agent_message(
                parts=[
                    Part(root=DataPart(data={"status": "Processing city search..."}))
                ]
            )
        )

        city: str | None = None
        if context.message and context.message.parts:
            for part_union in context.message.parts:
                part = part_union.root
                if isinstance(part, DataPart) and "city" in part.data:
                    city = part.data.get("city")
                    break

        if not city:
            logger.error(f"Task {context.task_id}: Missing 'city' in input data")
            task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[Part(root=DataPart(data={"error": "Invalid input: Missing city"}))]
                )
            )
            return

        agent_input_data = {"city": city}
        agent_input_json = json.dumps(agent_input_data)
        adk_content = genai_types.Content(
            parts=[genai_types.Part(text=agent_input_json)]
        )

        # Session management (as you had it)
        session: Session | None = await self._adk_runner.session_service.get_session(
            app_name=self._adk_runner.app_name,
            user_id="a2a_user",
            session_id=context.context_id,
        )
        if session is None:
            logger.info(f"Task {context.task_id}: Creating new ADK session for '{context.context_id}'.")
            session = await self._adk_runner.session_service.create_session(
                app_name=self._adk_runner.app_name,
                user_id="a2a_user",
                session_id=context.context_id,
                state={}
            )

        if not session:
            error_message = f"Failed to establish ADK session for '{context.context_id}'."
            logger.error(f"Task {context.task_id}: {error_message}")
            task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[Part(root=DataPart(data={"error": f"Internal error: {error_message}"}))]
                )
            )
            return

        final_businesses: list = []
        
        try:
            logger.info(f"Running LeadFinderAgent for city: '{city}'")
            async for event in self._adk_runner.run_async(
                user_id="a2a_user",
                session_id=context.context_id,
                new_message=adk_content,
            ):
                # --- THIS IS THE KEY CHANGE ---
                # We are now looking for the 'function_call' produced by our `post_results_callback`.
                if event.content and event.content.parts:
                    first_part = event.content.parts[0]
                    if (
                        hasattr(first_part, "function_call")
                        and first_part.function_call
                        and first_part.function_call.name == "final_lead_results" # The name we defined in the callback
                    ):
                        # The callback has given us the final, clean data
                        args = first_part.function_call.args
                        if isinstance(args, dict):
                            final_businesses = args.get("businesses", [])
                            logger.info(f"Executor received {len(final_businesses)} businesses from the agent callback.")
                            # Since this is the definitive final result, we can break.
                            break

            # The rest of the logic is the same as before.
            # It adds the artifact (which can be an empty list) and completes the task.
            task_updater.add_artifact(
                parts=[Part(root=DataPart(data={"businesses": final_businesses}))],
                name=DEFAULT_LEAD_FINDER_ARTIFACT_NAME,
            )
            task_updater.complete()
            logger.info(f"Task {context.task_id} completed successfully.")

        except Exception as e:
            logger.error(
                f"Error running LeadFinder ADK agent for task {context.task_id}: {e}",
                exc_info=True,
            )
            task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[Part(root=DataPart(data={"error": f"ADK Agent error: {e}"}))]
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        logger.warning(
            f"Cancellation not implemented for LeadFinder ADK agent task: {context.task_id}"
        )
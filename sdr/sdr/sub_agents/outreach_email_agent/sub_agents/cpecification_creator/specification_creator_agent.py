"""
Specification Creator Agent - Custom agent that implements iterative refinement logic.
"""

import logging
from typing import AsyncGenerator
from typing_extensions import override

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.llm_agent import LlmAgent
from google.adk.events import Event
from google.genai import types

from .requirements_refiner_agent import requirements_refiner_agent
from .quality_checker_agent import quality_checker_agent
from .spec_creator_agent import spec_creator_agent

logger = logging.getLogger(__name__)


class SpecificationCreatorAgent(BaseAgent):
    """
    A custom agent that implements iterative refinement logic for creating commercial specifications.
    Uses RequirementsRefinerAgent, QualityCheckerAgent, and SpecCreatorAgent in a loop until quality is acceptable.
    """

    requirements_refiner_agent: LlmAgent
    quality_checker_agent: LlmAgent
    spec_creator_agent: LlmAgent
    max_iterations: int

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        name: str,
        requirements_refiner_agent: LlmAgent,
        quality_checker_agent: LlmAgent,
        spec_creator_agent: LlmAgent,
        max_iterations: int = 3
    ):
        """
        Initializes the SpecificationCreatorAgent.
        Args:
            name: The name of the agent.
            requirements_refiner_agent: Agent for refining requirements.
            quality_checker_agent: Agent for checking quality.
            spec_creator_agent: Agent for creating specifications.
            max_iterations: Maximum number of refinement iterations.
        """
        sub_agents_list = [requirements_refiner_agent, quality_checker_agent, spec_creator_agent]

        super().__init__(
            name=name,
            requirements_refiner_agent=requirements_refiner_agent,
            quality_checker_agent=quality_checker_agent,
            spec_creator_agent=spec_creator_agent,
            max_iterations=max_iterations,
            sub_agents=sub_agents_list,
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Implements the iterative specification creation logic.
        """
        logger.info(f"[{self.name}] Starting specification creation workflow.")

        iteration = 0
        quality_approved = False

        while iteration < self.max_iterations and not quality_approved:
            iteration += 1
            logger.info(f"[{self.name}] Starting iteration {iteration}/{self.max_iterations}")

            # Step 1: Refine requirements
            logger.info(f"[{self.name}] Step 1: Refining requirements...")
            async for event in self.requirements_refiner_agent.run_async(ctx):
                logger.info(f"[{self.name}] RequirementsRefinerAgent event: {event.model_dump_json(indent=2, exclude_none=True)}")
                yield event

            # Step 2: Create specification
            logger.info(f"[{self.name}] Step 2: Creating specification...")
            async for event in self.spec_creator_agent.run_async(ctx):
                logger.info(f"[{self.name}] SpecCreatorAgent event: {event.model_dump_json(indent=2, exclude_none=True)}")
                yield event

            # Step 3: Check quality
            logger.info(f"[{self.name}] Step 3: Checking quality...")
            async for event in self.quality_checker_agent.run_async(ctx):
                logger.info(f"[{self.name}] QualityCheckerAgent event: {event.model_dump_json(indent=2, exclude_none=True)}")
                yield event

            # Check if quality is approved
            quality_result = ctx.session.state.get("quality_check_result", "")
            if "approved" in quality_result.lower() or "acceptable" in quality_result.lower():
                quality_approved = True
                logger.info(f"[{self.name}] Quality approved after {iteration} iterations.")
            else:
                logger.info(f"[{self.name}] Quality not approved, continuing to next iteration...")

        if not quality_approved:
            logger.warning(f"[{self.name}] Maximum iterations reached without quality approval.")
            yield Event(
                content=types.Content(
                    parts=[
                        types.Part(
                            text=f"Specification creation completed after {self.max_iterations} iterations. Final quality check may not be fully approved."
                        )
                    ]
                ),
                author=self.name,
            )
        else:
            yield Event(
                content=types.Content(
                    parts=[
                        types.Part(
                            text=f"Specification creation completed successfully after {iteration} iterations with quality approval."
                        )
                    ]
                ),
                author=self.name,
            )

        logger.info(f"[{self.name}] Specification creation workflow finished.")


# Create the agent instance
specification_creator_agent = SpecificationCreatorAgent(
    name="SpecificationCreatorAgent",
    requirements_refiner_agent=requirements_refiner_agent,
    quality_checker_agent=quality_checker_agent,
    spec_creator_agent=spec_creator_agent,
    max_iterations=3
)
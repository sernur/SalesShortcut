"""
Specification Creator Agent for creating detailed commercial specifications.
"""

from google.adk.agents.llm_agent import LlmAgent
from .....config import MODEL_THINK
from .....prompts import SPEC_CREATOR_PROMPT

spec_creator_agent = LlmAgent(
    name="SpecCreatorAgent",
    description="Agent that creates detailed commercial specifications and offer documents",
    model=MODEL_THINK,
    instruction=SPEC_CREATOR_PROMPT,
    output_key="commercial_specification"
)
"""
Requirements Refiner Agent for analyzing and refining commercial requirements.
"""

from google.adk.agents.llm_agent import LlmAgent
from .....config import MODEL_THINK
from .....prompts import REQUIREMENTS_REFINER_PROMPT

requirements_refiner_agent = LlmAgent(
    name="RequirementsRefinerAgent",
    description="Agent that analyzes customer needs and refines business requirements for commercial offers",
    model=MODEL_THINK,
    instruction=REQUIREMENTS_REFINER_PROMPT,
    output_key="refined_requirements"
)
"""
Quality Checker Agent for validating commercial offer quality.
"""

from google.adk.agents.llm_agent import LlmAgent
from ....config import MODEL
from ....prompts import QUALITY_CHECKER_PROMPT

quality_checker_agent = LlmAgent(
    name="QualityCheckerAgent",
    description="Agent that validates and ensures quality of commercial specifications and offers",
    model=MODEL,
    instruction=QUALITY_CHECKER_PROMPT,
    output_key="quality_check_result"
)
from google.adk.agents.llm_agent import LlmAgent
from .website_creator_prompts import PROMPT_PREPARE_PROMPT

prepare_request = LlmAgent(
    name="PrepareApproval",
    instruction=PROMPT_PREPARE_PROMPT
)
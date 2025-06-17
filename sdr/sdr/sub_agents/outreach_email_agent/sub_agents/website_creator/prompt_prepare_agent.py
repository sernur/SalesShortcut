from google.adk.agents.llm_agent import LlmAgent
from .website_creator_prompts import PROMPT_PREPARE_PROMPT
from sdr.sdr.config import MODEL

prepare_prompt = LlmAgent(
    name="PrepareApproval",
    model=MODEL,
    instruction=PROMPT_PREPARE_PROMPT,
    output_key="website_creation_prompt",
)
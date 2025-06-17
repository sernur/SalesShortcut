from google.adk.agents.llm_agent import LlmAgent
from sdr.sdr.config import MODEL

process_decision = LlmAgent(
    name="ProcessDecision",
    model=MODEL,
    instruction="Check state key 'website_preview_link'. If not empty, proceed."
)
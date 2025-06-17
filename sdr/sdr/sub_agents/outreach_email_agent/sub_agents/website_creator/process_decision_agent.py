from google.adk.agents.llm_agent import LlmAgent

process_decision = LlmAgent(
    name="ProcessDecision",
    instruction="Check state key 'website_preview_link'. If not empty, proceed."
)
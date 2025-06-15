
from google.adk.agents.llm_agent import LlmAgent
from ..config import MODEL_THINK
from ..prompts import CONVERSATION_CLASSIFIER_PROMPT

conversation_classifier_agent = LlmAgent(
    name="ConversationClassifierAgent",
    description="Agent that analyzes conversation results and classifies them into categories",
    model=MODEL_THINK,
    instruction=CONVERSATION_CLASSIFIER_PROMPT,
    output_key="call_category"
)

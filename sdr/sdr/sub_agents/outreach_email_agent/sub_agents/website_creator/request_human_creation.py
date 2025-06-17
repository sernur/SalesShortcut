from google.adk.agents.llm_agent import LlmAgent
from .tools.human_creation_tool import request_human_input_tool
from sdr.sdr.config import MODEL


request_URL = LlmAgent(
    name="RequestHumanApproval",
    model=MODEL,
    instruction="Use the external_approval_tool with amount from state['approval_amount'] and reason from state['approval_reason'].",
    tools=[request_human_input_tool],
    output_key="website_preview_link"
)

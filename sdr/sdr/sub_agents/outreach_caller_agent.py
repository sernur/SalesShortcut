"""
Outreach Caller Agent for making phone calls to convince business owners.
"""

from google.adk.agents.llm_agent import LlmAgent
from ..config import MODEL
from ..tools.phone_call import phone_call_function_tool
from ..callbacks import phone_number_validation_callback
from ..prompts import OUTREACH_CALLER_PROMPT


outreach_caller_agent = LlmAgent(
    name="OutreachCallerAgent",
    description="Agent that makes phone calls to convince business owners to accept email proposals",
    model=MODEL,
    instruction=OUTREACH_CALLER_PROMPT,
    before_tool_callback=phone_number_validation_callback,
    tools=[phone_call_function_tool],
    output_key="call_result"
)
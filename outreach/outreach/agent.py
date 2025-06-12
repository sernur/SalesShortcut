"""
Main agent definition for the Outreach Agent.
"""

import os
from google.adk.agents.llm_agent import LlmAgent
from .config import MODEL, GOOGLE_API_KEY
from .prompts import ROOT_AGENT_PROMPT
from .tools.phone_call import phone_call_function_tool, phone_number_validation_callback
from .tools.message_email import message_email_function_tool
from .callbacks import post_results_callback

# Set Google API key as environment variable if not already set
if GOOGLE_API_KEY and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Create the root agent (OutreachAgent)
outreach_agent = LlmAgent(
    name="OutreachAgent",
    description="Specialized agent for conducting outreach activities including phone calls and email messaging",
    model=MODEL,
    instruction=ROOT_AGENT_PROMPT,
    tools=[phone_call_function_tool, message_email_function_tool],
    before_tool_callback=phone_number_validation_callback,
    after_agent_callback=post_results_callback,
    output_key="outreach_results",
)

root_agent = outreach_agent
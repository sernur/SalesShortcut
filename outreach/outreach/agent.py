"""
Main agent definition for the Outreach Agent.
"""

import os
from google.adk.agents.llm_agent import LlmAgent
from .config import MODEL, GOOGLE_API_KEY
from .prompts import ROOT_AGENT_PROMPT
from .tools.message_email import message_email_function_tool
from .callbacks import post_results_callback

# Create the root agent (OutreachAgent)
outreach_agent = LlmAgent(
    name="OutreachAgent",
    description="Specialized agent for conducting outreach activities including phone calls and email messaging",
    model=MODEL,
    instruction=ROOT_AGENT_PROMPT,
    tools=[message_email_function_tool],
    after_agent_callback=post_results_callback,
    output_key="outreach_results",
)

root_agent = outreach_agent
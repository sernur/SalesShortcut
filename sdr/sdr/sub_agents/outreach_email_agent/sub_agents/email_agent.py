"""
Email Agent for crafting and sending outreach emails.
"""

from google.adk.agents.llm_agent import LlmAgent
from ...config import MODEL
from ...prompts import EMAIL_AGENT_PROMPT

email_agent = LlmAgent(
    name="EmailAgent",
    description="Agent that crafts and sends personalized business outreach emails with commercial offers",
    model=MODEL,
    instruction=EMAIL_AGENT_PROMPT,
    tools=[],  # GmailToolset will be implemented later
    output_key="email_sent_result"
)
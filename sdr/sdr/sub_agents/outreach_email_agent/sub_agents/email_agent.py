"""
Email Agent for crafting and sending outreach emails.
"""
import os # Import os to access environment variables

from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.google_api_tool import GmailToolset # <-- Import GmailToolset

from ....config import MODEL, GOOGLE_CLOUD_CLIENT_ID, GOOGLE_CLOUD_CLIENT_SECRET
from ....prompts import EMAIL_AGENT_PROMPT


# based on the client_id and client_secret.
gmail_toolset = GmailToolset(
    client_id=GOOGLE_CLOUD_CLIENT_ID,
    client_secret=GOOGLE_CLOUD_CLIENT_SECRET
)

email_agent = LlmAgent(
    name="EmailAgent",
    description="Agent that crafts and sends personalized business outreach emails with commercial offers",
    model=MODEL,
    instruction=EMAIL_AGENT_PROMPT,
    tools=[gmail_toolset],  # <-- Add the GmailToolset here
    output_key="email_sent_result"
)
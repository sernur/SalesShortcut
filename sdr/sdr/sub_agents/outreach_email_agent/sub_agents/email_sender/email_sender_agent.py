"""
Email Agent for crafting and sending outreach emails.
"""
import os # Import os to access environment variables

from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.google_api_tool import GmailToolset # <-- Import GmailToolset

from sdr.sdr.config import MODEL, GOOGLE_CLOUD_CLIENT_ID, GOOGLE_CLOUD_CLIENT_SECRET
from ...outreach_email_prompt import EMAIL_SENDER_AGENT_PROMPT
from ...tools.create_rfc88_message import create_rfc822_message


# based on the client_id and client_secret.
gmail_toolset = GmailToolset(
    client_id=GOOGLE_CLOUD_CLIENT_ID,
    client_secret=GOOGLE_CLOUD_CLIENT_SECRET
)

gmail_toolset.configure_auth(
    client_id=GOOGLE_CLOUD_CLIENT_ID,
    client_secret=GOOGLE_CLOUD_CLIENT_SECRET
)

email_agent = LlmAgent(
    name="EmailAgent",
    description="Agent that crafts and sends personalized business outreach emails with commercial offers",
    model=MODEL,
    instruction=EMAIL_SENDER_AGENT_PROMPT,
    tools=[create_rfc822_message, gmail_toolset],
    output_key="email_sent_result"
)
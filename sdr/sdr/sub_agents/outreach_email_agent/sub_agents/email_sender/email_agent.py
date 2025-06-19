"""
Email Agent for crafting and sending outreach emails.
"""

from google.adk.agents import SequentialAgent
from .email_crafter_agent import email_crafter_agent
# from .email_sender_agent import email_sender_agent

email_agent = SequentialAgent(
    name="EmailAgent",
    description="Agent that crafts and sends personalized business outreach emails with commercial offers",
    sub_agents=[
        email_crafter_agent,
        # email_sender_agent
    ],
)
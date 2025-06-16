"""
Websiter Creator Agent for creating demo prototype websites.
"""

from google.adk.agents.llm_agent import LlmAgent
from ...config import MODEL
from ...prompts import WEBSITER_CREATOR_PROMPT

websiter_creator_agent = LlmAgent(
    name="WebsiterCreatorAgent",
    description="Agent that creates demo prototype websites and returns the link",
    model=MODEL,
    instruction=WEBSITER_CREATOR_PROMPT,
    tools=[],  # Website creation tool will be implemented later
    output_key="demo_website_link"
)
"""
Engagement Saver Agent for saving email engagement data to BigQuery.
"""

from google.adk.agents.llm_agent import LlmAgent
from sdr.sdr.config import MODEL
from ....prompts import ENGAGEMENT_SAVER_PROMPT

engagement_saver_agent = LlmAgent(
    name="EngagementSaverAgent",
    description="Agent that saves email engagement and outreach data to BigQuery for analytics",
    model=MODEL,
    instruction=ENGAGEMENT_SAVER_PROMPT,
    tools=[],  # BigQuery engagement tool will be implemented later
    output_key="engagement_saved_result"
)
"""
MergerAgent implementation.
"""

from google.adk.agents.llm_agent import Agent
from lead_finder.config import MODEL
from lead_finder.prompts import MERGER_AGENT_PROMPT
from lead_finder.tools.bigquery_utils import bigquery_upload

merger_agent = Agent(
    model=MODEL,
    name="MergerAgent",
    description="Agent for processing and merging business data",
    instruction=MERGER_AGENT_PROMPT,
    tools=[bigquery_upload],
)

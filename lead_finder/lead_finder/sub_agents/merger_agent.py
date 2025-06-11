"""
MergerAgent implementation.
"""

from google.adk.agents.llm_agent import Agent
from ..config import MODEL
from ..prompts import MERGER_AGENT_PROMPT
from ..tools.bigquery_utils import bigquery_upload_tool

merger_agent = Agent(
    model=MODEL,
    name="MergerAgent",
    description="Agent for processing and merging business data",
    instruction=MERGER_AGENT_PROMPT,
    tools=[bigquery_upload_tool],
)

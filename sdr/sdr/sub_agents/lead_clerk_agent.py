"""
Lead Clerk Agent for processing conversation results and storing data.
"""

from google.adk.agents.llm_agent import LlmAgent
from ..config import MODEL
from ..prompts import LEAD_CLERK_PROMPT
from ..tools.bigquery_utils import sdr_bigquery_upload_tool

lead_clerk_agent = LlmAgent(
    name="LeadClerkAgent",
    description="Agent that analyzes conversation results and decides whether to store lead data",
    model=MODEL,
    instruction=LEAD_CLERK_PROMPT,
    tools=[sdr_bigquery_upload_tool],
    output_key="clerk_result"
)
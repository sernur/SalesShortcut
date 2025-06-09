"""
ClusterSearchAgent implementation.
"""

from google.adk.agents.llm_agent import Agent
from lead_finder.config import MODEL
from lead_finder.prompts import CLUSTER_SEARCH_AGENT_PROMPT
from lead_finder.tools.cluster_search import cluster_search

cluster_search_agent = Agent(
    model=MODEL,
    name="ClusterSearchAgent",
    description="Agent specialized in finding business information using custom cluster search",
    instruction=CLUSTER_SEARCH_AGENT_PROMPT,
    tools=[cluster_search],
)


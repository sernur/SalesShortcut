"""
PotentialLeadFinderAgent implementation.
"""

from google.adk.agents.llm_agent import Agent
from lead_finder.config import MODEL
from lead_finder.prompts import POTENTIAL_LEAD_FINDER_PROMPT
from lead_finder.sub_agents.google_maps_agent import google_maps_agent
from lead_finder.sub_agents.cluster_search_agent import cluster_search_agent

potential_lead_finder_agent = Agent(
    model=MODEL,
    name="PotentialLeadFinderAgent",
    description="Parallel agent for finding potential business leads",
    instruction=POTENTIAL_LEAD_FINDER_PROMPT,
    sub_agents=[google_maps_agent, cluster_search_agent],
    agent_type="parallel",  # This agent runs sub-agents in parallel
)

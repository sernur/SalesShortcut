"""
Main agent definition for the Lead Finder Agent.
"""

from google.adk.agents.llm_agent import Agent
from lead_finder.config import MODEL
from lead_finder.prompts import ROOT_AGENT_PROMPT
from lead_finder.sub_agents.potential_lead_finder_agent import potential_lead_finder_agent
from lead_finder.sub_agents.merger_agent import merger_agent

# Create the root agent (LeadFinderAgent)
lead_finder_agent = Agent(
    model=MODEL,
    name="LeadFinderAgent",
    description="Sequential agent for finding business leads in a specified city",
    instruction=ROOT_AGENT_PROMPT,
    sub_agents=[potential_lead_finder_agent, merger_agent],
    agent_type="sequential",  # This agent runs sub-agents sequentially
)

root_agent = lead_finder_agent
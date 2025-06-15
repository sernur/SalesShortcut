"""
Main agent definition for the SDR Agent.
"""

from google.adk.agents.sequential_agent import SequentialAgent
from .config import MODEL
from .sub_agents.research_lead_agent import research_lead_agent
from .sub_agents.proposal_generator_agent import proposal_generator_agent
from .sub_agents.outreach_caller_agent import outreach_caller_agent
from .sub_agents.lead_clerk_agent import lead_clerk_agent
from .callbacks import post_results_callback

# Create the root agent (SDRAgent)
sdr_agent = SequentialAgent(
    name="SDRAgent",
    description="Sequential agent for SDR outreach to business leads with research, proposal generation, phone calls, and lead management",
    sub_agents=[
        research_lead_agent,
        proposal_generator_agent,
        outreach_caller_agent,
        lead_clerk_agent
    ],
    after_agent_callback=post_results_callback,
)

root_agent = sdr_agent
"""
GoogleMapsAgent implementation.
"""

from google.adk.agents.llm_agent import Agent
from ..config import MODEL
from ..prompts import GOOGLE_MAPS_AGENT_PROMPT
from ..tools.maps_search import google_maps_search

google_maps_agent = Agent(
    model=MODEL,
    name="GoogleMapsAgent",
    description="Agent specialized in finding business information using Google Maps",
    instruction=GOOGLE_MAPS_AGENT_PROMPT,
    tools=[google_maps_search],
)

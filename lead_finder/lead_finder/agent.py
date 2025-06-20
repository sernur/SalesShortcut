"""
Main agent definition for the Lead Finder Agent.
"""

import logging
from typing import Dict, Any, List, Optional
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.agents.sequential_agent import SequentialAgent
from .config import MODEL
from .prompts import ROOT_AGENT_PROMPT
from .sub_agents.potential_lead_finder_agent import potential_lead_finder_agent
from .sub_agents.merger_agent import merger_agent
from .callbacks import post_results_callback
from .tools.bigquery_utils import (
    bigquery_upload, 
    bigquery_query_leads,
    bigquery_no_website_upload,
    bigquery_query_no_website_leads
)

# Create the root agent (LeadFinderAgent)
lead_finder_agent = SequentialAgent(
    name="LeadFinderAgent",
    description="Sequential agent for finding business leads in a specified city",
    sub_agents=[potential_lead_finder_agent, merger_agent],
    after_agent_callback=post_results_callback,
)

root_agent = lead_finder_agent

async def _search_and_save_leads(self, city: str, business_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for leads in a city and save them to BigQuery.
    
    Args:
        city: The city to search in
        business_type: Optional business type to filter by
        
    Returns:
        Dictionary with search results and statistics
    """
    try:
        # Search for businesses without websites
        search_result = google_maps_search(
            city=city,
            business_type=business_type,
            min_rating=0.0,  # Don't filter by rating initially
            max_results=100,  # Get up to 100 results
            exclude_websites=True  # Only get businesses without websites
        )
        
        if search_result["status"] != "success":
            return search_result
        
        # Upload to the no-website specific table
        upload_result = await bigquery_no_website_upload(
            data=search_result["results"],
            city=city,
            search_type="no_website_search"
        )
        
        # Combine results
        return {
            "status": "success",
            "search_results": search_result,
            "upload_results": upload_result,
            "total_results": len(search_result["results"]),
            "total_uploaded": upload_result["stats"].get("new_inserted", 0)
        }
        
    except Exception as e:
        logger.error(f"Error in _search_and_save_leads: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
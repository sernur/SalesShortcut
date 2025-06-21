"""
Callbacks for the Lead Manager Agent.
"""
import json
import logging
import os
import re
from typing import Optional, Dict, Any
from datetime import datetime

import httpx
import common.config as config

from google.adk.agents.callback_context import CallbackContext
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

def send_meeting_update_to_ui(meeting_data: Dict[str, Any], lead_data: Dict[str, Any]):
    """
    Sends a meeting arrangement update to the UI client's /agent_callback endpoint.
    """
    ui_client_url = os.environ.get(
        "UI_CLIENT_SERVICE_URL", config.DEFAULT_UI_CLIENT_URL
    ).rstrip("/")
    callback_endpoint = f"{ui_client_url}/agent_callback"

    payload = {
        "agent_type": "lead_manager",
        "business_id": lead_data.get("id", f"lead_{lead_data.get('email', 'unknown')}"),
        "status": "meeting_arranged",
        "message": f"Meeting arranged with {lead_data.get('name', 'Unknown')} - {meeting_data.get('title', 'Unknown Meeting')}",
        "timestamp": datetime.now().isoformat(),
        "data": {
            # Lead information
            "lead_name": lead_data.get("name", "Unknown"),
            "lead_email": lead_data.get("email", ""),
            "lead_company": lead_data.get("company", ""),
            "lead_phone": lead_data.get("phone", ""),
            
            # Meeting information  
            "meeting_id": meeting_data.get("meeting_id", ""),
            "meeting_title": meeting_data.get("title", ""),
            "meeting_start": meeting_data.get("start_time", ""),
            "meeting_end": meeting_data.get("end_time", ""),
            "meeting_duration": meeting_data.get("duration", 60),
            "meeting_link": meeting_data.get("meet_link", ""),
            "calendar_link": meeting_data.get("calendar_link", ""),
            
            # Metadata
            "agent_action": "meeting_arranged",
            "processing_timestamp": datetime.now().isoformat()
        }
    }

    logger.info(f"Sending POST to UI endpoint: {callback_endpoint} for meeting: {meeting_data.get('title', 'Unknown')}")
    try:
        with httpx.Client() as client:
            response = client.post(callback_endpoint, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Successfully posted meeting update to UI. Status: {response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Error sending POST request to UI client at {e.request.url if hasattr(e, 'request') else 'unknown'}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while posting to the UI client: {e}")

async def post_lead_manager_callback(callback_context: CallbackContext) -> Optional[genai_types.Content]:
    """
    Callback function for Lead Manager Agent completion.
    This version includes robust parsing for all potential JSON strings from the context.
    """
    agent_name = callback_context.agent_name
    logger.info(f"[Callback] Exiting agent: {agent_name}. Processing final result.")

    context_state = callback_context.state.to_dict()
    logger.info(f"[Callback] Current callback_context.state: {context_state}")

    # ====================================================================
    # --- FIX: Robustly parse all potential JSON strings from the state ---
    # ====================================================================
    
    # Helper function to safely parse a string that might be markdown-wrapped JSON
    def safe_json_parse(value: any, key_name: str) -> any:
        if not isinstance(value, str):
            return value # It's already an object, return as-is
        
        cleaned_str = value
        match = re.search(r"```json\s*([\s\S]*?)\s*```", cleaned_str)
        if match:
            cleaned_str = match.group(1)
        
        try:
            return json.loads(cleaned_str)
        except json.JSONDecodeError:
            logger.warning(f"[Callback] Could not parse '{key_name}' as JSON. Using raw string value.")
            return value # Return the original string if parsing fails

    notification_data = safe_json_parse(context_state.get('notification_result'), 'notification_result')
    meeting_data = safe_json_parse(context_state.get('meeting_result'), 'meeting_result')
    hot_lead_data = safe_json_parse(context_state.get('hot_lead_email'), 'hot_lead_email')

    # ====================================================================
    # --- Logic now uses the cleaned and parsed data objects ---
    # ====================================================================

    if notification_data and notification_data != "no_action_needed":
        logger.info("[Callback] Meeting arrangement results found in state.")
        
        # The data is already parsed, now we just use it.
        # This block can be simplified or enhanced to send specific UI updates.
        if isinstance(meeting_data, dict) and isinstance(hot_lead_data, dict):
            lead_data_details = hot_lead_data.get("lead_data", {})
            logger.info(f"Processing results for lead: {lead_data_details.get('name', 'N/A')}")
            # Example of sending a structured update
            # send_meeting_update_to_ui(meeting_data, lead_data_details)
        else:
            logger.info("Proceeding with general notification.")

    elif context_state.get('hot_lead_email') == "no_action_needed":
        logger.info("[Callback] No hot lead meeting requests found - no action needed.")
    else:
        logger.warning("[Callback] No meeting arrangement results found in state.")

    try:
        # Save the parsed Python objects, not the raw strings
        await callback_context.save_artifact("lead_manager_results", {
            "notification_result": notification_data,
            "meeting_result": meeting_data,
            "hot_lead_email": hot_lead_data,
            "timestamp": datetime.now().isoformat()
        })
        logger.info("[Callback] Saved artifact for lead manager completion.")
    except Exception as e:
        logger.error(f"[Callback] Error saving final artifact: {e}")

    logger.info("[Callback] Lead Manager callback finished.")
    return None

"""
Callbacks for the SDR Agent.
"""
import json
import asyncio
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import re

import httpx

import common.config as config

from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from google.genai import types as genai_types


logger = logging.getLogger(__name__)

def send_update_to_ui(business_data: dict):
    """
    Sends a single business update to the UI client's /agent_callback endpoint.
    This function will now ensure a 'city' field is present in the 'data' payload.
    """
    ui_client_url = os.environ.get(
        "UI_CLIENT_SERVICE_URL", config.DEFAULT_UI_CLIENT_URL
    ).rstrip("/")
    callback_endpoint = f"{ui_client_url}/agent_callback"

    # Create a copy of the business_data to modify it for UI client's validation
    data_for_ui = business_data.copy()

    # Ensure 'city' is a top-level field for UI client's AgentUpdate validation
    if 'city' not in data_for_ui and 'address' in data_for_ui:
        extracted_city = extract_city_from_address(data_for_ui['address'])
        if extracted_city:
            data_for_ui['city'] = extracted_city
        else:
            logger.warning(f"Could not extract city from address: {data_for_ui.get('address')}. Business may not be created in UI.")
            # Optionally, you might want to return here or set a default city
            # if 'city' is strictly required for every business.

    payload = {
        "agent_type": "lead_finder",
        "business_id": data_for_ui.get("id"), # Use id from the potentially modified data_for_ui
        "status": "found",
        "message": f"Successfully discovered business: {data_for_ui.get('name')}",
        "timestamp": datetime.now().isoformat(),
        "data": data_for_ui # Send the modified data with the top-level 'city'
    }

    logger.info(f"Sending POST to UI endpoint: {callback_endpoint} for business: {data_for_ui.get('name')}")
    try:
        with httpx.Client() as client:
            response = client.post(callback_endpoint, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Successfully posted update for {data_for_ui.get('name')} to UI. Status: {response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Error sending POST request to UI client at {e.request.url}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while posting to the UI client: {e}")



async def post_results_callback(callback_context: CallbackContext) -> Optional[genai_types.Content]:
    agent_name = callback_context.agent_name
    logger.info(f"[Callback] Exiting agent: {agent_name}. Processing final result.")

    final_businesses: List[Dict[str, Any]] = []

    # Access the state directly
    context_state = callback_context.state.to_dict()
    print(f"[Callback] Current callback_context.state: {context_state}")

    # Check if 'final_sdr_results' key exists in the state
    if 'final_sdr_results' in context_state:
        merged_leads_text = context_state['final_sdr_results']
        
        # Use regex to find the JSON block in the text
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", merged_leads_text)
        if json_match:
            try:
                json_str = json_match.group(1)
                parsed_data = json.loads(json_str)
                if isinstance(parsed_data, list):
                    final_businesses = parsed_data
                    logger.info(f"[Callback] Successfully extracted {len(final_businesses)} businesses from callback_context.state.")
                else:
                    logger.warning(f"[Callback] Extracted JSON from state is not a list: {parsed_data}")
            except json.JSONDecodeError as e:
                logger.error(f"[Callback] Failed to parse JSON from callback_context.state: {e}")
        else:
            logger.warning(f"[Callback] No JSON block found in 'final_sdr_results' state data.")
    else:
        logger.warning("[Callback] 'final_sdr_results' not found in callback_context.state.")
        return None


    if not final_businesses:
        logger.warning("[Callback] No businesses found for UI update. Check MergerAgent's output_key and state propagation.")
        # For deeper debugging if needed, log the full state
        logger.warning(f"Full callback_context.state.to_dict(): {context_state}")
        return None


    for biz in final_businesses:
        if "id" not in biz:
            # Generate a stable ID based on unique business attributes
            biz_id_components = [str(biz.get("name", "")), str(biz.get("address", "")), str(biz.get("phone", ""))]
            # Filter out empty strings/None values before joining for hashing
            clean_components = [c for c in biz_id_components if c and c != 'None']
            biz["id"] = "generated_" + str(hash(tuple(clean_components))) if clean_components else str(datetime.now().timestamp())
        send_update_to_ui(biz)

    try:
        # Saving artifacts
        # This part is still subject to the "Artifact service is not initialized" error
        # but it should not block UI updates now.
        await callback_context.save_artifact("final_lead_results", {
            "businesses": final_businesses,
            "count": len(final_businesses)
        })
        logger.info(f"[Callback] Saved artifact with {len(final_businesses)} businesses for task completion.")
    except Exception as e:
        logger.error(f"[Callback] Error saving final artifact: {e}")

    logger.info("[Callback] UI updates sent. Callback finished.")
    return None



def validate_us_phone_number(phone_number: str) -> Dict[str, Any]:
    """
    Validate that the phone number is a valid US number for ElevenLabs.
    
    Args:
        phone_number: Phone number to validate
        
    Returns:
        Dict with validation result and normalized number
    """
    import re
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone_number)
    
    # Check for valid US number patterns
    if len(digits_only) == 10:
        # Add +1 prefix for 10-digit numbers
        normalized = f"+1{digits_only}"
    elif len(digits_only) == 11 and digits_only.startswith('1'):
        # Already has country code
        normalized = f"+{digits_only}"
    else:
        return {
            "valid": False,
            "error": f"Invalid US phone number format: {phone_number}. Expected 10 or 11 digits.",
            "normalized": None
        }
    
    # Basic US number validation (not toll-free, not premium)
    area_code = digits_only[-10:-7]
    if area_code.startswith('0') or area_code.startswith('1'):
        return {
            "valid": False,
            "error": f"Invalid area code: {area_code}. Area codes cannot start with 0 or 1.",
            "normalized": None
        }
    
    return {
        "valid": True,
        "error": None,
        "normalized": normalized
    }


# CORRECTED: Removed the extra 'def' keyword
async def phone_number_validation_callback(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext
) -> Optional[Dict]:
    """
    Before-tool callback to validate phone number format and modify args if needed.
    """
    
    tool_name = tool.name # Get the name of the tool being called
    
    # Only apply this callback to the phone call tool (or its test version)
    if tool_name not in ["phone_call_tool", "phone_call_tool_test"]:
        return None # Do nothing if it's not the relevant tool

    # The phone number is expected in the 'destination' argument for the phone_call_tool
    # or 'phone_number' if using an older signature or a different tool.
    destination = args.get("destination") or args.get("phone_number", "")
    
    if not destination:
        # If no destination is provided, let the tool handle the error or raise one here.
        # For a callback, returning None means proceed with original args.
        # If you want to block the tool from running, return a dict with "result".
        logger.warning("No destination phone number found in tool arguments.")
        return None # Or raise ValueError("Missing destination phone number") if you want to explicitly block

    validation_result = validate_us_phone_number(destination)
    
    if not validation_result["valid"]:
        logger.error(f"Phone number validation failed: {validation_result['error']}")
        # When returning a dictionary, the tool call is skipped and this result is used.
        return {"result": f"Phone number validation failed: {validation_result['error']}"}
    
    # If valid, update the args with the normalized version
    normalized_number = validation_result["normalized"]
    if normalized_number != destination: # Only modify if a change occurred
        logger.info(f"Phone number normalized: {destination} -> {normalized_number}")
        args["destination"] = normalized_number
        # If your tool also uses 'phone_number', you might want to update or remove it too
        if "phone_number" in args:
            args["phone_number"] = normalized_number
            
    # Return None to indicate that the tool execution should proceed with the (potentially modified) args.
    return None


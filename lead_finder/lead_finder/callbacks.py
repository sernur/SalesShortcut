# In lead_finder/callbacks.py

import json
import asyncio
import os
import logging
from typing import Optional
from datetime import datetime

import httpx

import common.config as config

from google.adk.agents.callback_context import CallbackContext
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

def send_update_to_ui(business_data: dict):
    """
    Sends a single business update to the UI client's /agent_callback endpoint.
    """
    ui_client_url = os.environ.get(
        "UI_CLIENT_SERVICE_URL", config.DEFAULT_UI_CLIENT_URL
    ).rstrip("/")
    callback_endpoint = f"{ui_client_url}/agent_callback"

    # The payload must match the `AgentUpdate` Pydantic model in the UI client
    payload = {
        "agent_type": "lead_finder",
        "business_id": business_data.get("id"), # merger agent assigns an ID
        "status": "found", # The status for a newly found lead
        "message": f"Successfully discovered business: {business_data.get('name')}",
        "timestamp": datetime.now().isoformat(),
        "data": business_data # You can send the full business data here if needed
    }

    logger.info(f"Sending POST to UI endpoint: {callback_endpoint} for business: {business_data.get('name')}")
    try:
        # We are in a sync callback, so we use a sync httpx call
        with httpx.Client() as client:
            response = client.post(callback_endpoint, json=payload, timeout=10.0)
            response.raise_for_status() # Raise an exception for 4xx or 5xx status codes
            logger.info(f"Successfully posted update for {business_data.get('name')} to UI. Status: {response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Error sending POST request to UI client at {e.request.url}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while posting to the UI client: {e}")



def post_results_callback(callback_context: CallbackContext) -> Optional[genai_types.Content]:
    """
    This callback runs after the root lead_finder_agent completes.
    It intercepts the final output, packages it, sends direct HTTP callbacks
    to the UI for each business, and returns the final result for the A2A task.
    """
    agent_name = callback_context.agent_name
    logger.info(f"[Callback] Exiting agent: {agent_name}. Processing final result.")
    
    print(f"DEBUG: Available attributes in callback_context are: {dir(callback_context)}")
    
    invocation_result = callback_context.invocation_result
    final_businesses = []

    if (
        invocation_result
        and invocation_result.parts
        and hasattr(invocation_result.parts[0], "function_response")
    ):
        function_response = invocation_result.parts[0].function_response
        # Correctly check for the tool/function name from your merger agent
        if function_response.name == "save_merged_leads":
            response_data = function_response.response
            if isinstance(response_data, dict):
                final_businesses = response_data.get("businesses", [])
                logger.info(f"[Callback] Extracted {len(final_businesses)} businesses from agent's final tool call.")

    if not final_businesses:
        logger.warning("[Callback] Agent did not produce a final list of businesses. No direct UI callbacks will be sent.")
    else:
        send_update_to_ui(final_businesses)

    # --- A2A Task Result Logic ---
    # We still return the final content for the A2A task, as this is best practice.
    # It provides a primary, reliable way to get the full results list.
    final_output_content = genai_types.Content(
        parts=[
            genai_types.Part(
                function_call=genai_types.FunctionCall(
                    name="final_lead_results",
                    args={"businesses": final_businesses},
                )
            )
        ],
        role="model",
    )

    logger.info("[Callback] Returning new Content object for the A2A task artifact.")
    return final_output_content

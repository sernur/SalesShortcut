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
    agent_name = callback_context.agent_name
    logger.info(f"[Callback] Exiting agent: {agent_name}. Processing final result.")

    invocation_result = callback_context.user_content          # still correct
    final_businesses: list[dict] = []

    if invocation_result and invocation_result.parts:
        part0 = invocation_result.parts[0]

        # Safely get the function_response (may be None)
        fn_resp = getattr(part0, "function_response", None)
        if fn_resp and fn_resp.name == "save_merged_leads":
            data = fn_resp.response or {}
            final_businesses = data.get("businesses", [])
        else:
            logger.warning(
                "[Callback] No tool call in final content – "
                "agent likely exited without merging leads. "
                "Raw content: %s", invocation_result
            )

    # ---------- notify UI ----------
    for biz in final_businesses:
        send_update_to_ui(biz)

    # ---------- return artifact for the A2A task ----------
    return genai_types.Content(
        role="model",
        parts=[
            genai_types.Part(
                function_call=genai_types.FunctionCall(
                    name="final_lead_results",
                    args={"businesses": final_businesses},
                )
            )
        ],
    )


async def post_results_callback_test(callback_context: CallbackContext) -> Optional[genai_types.Content]:
    """
    Fixed callback - NO MORE invocation_result error
    """
    agent_name = callback_context.agent_name
    logger.info(f"[Callback TEST] Exiting agent: {agent_name}. Processing final result.")
    
    # Create mock data for testing since we can't extract real data yet
    final_businesses = [
        {
            "id": "test_1",
            "name": "Test Business 1 Mary",
            "address": "123 Test St, Mary",
            "city": "Mary",  # <--- ADD THIS
            "phone": "+1-555-0123",
            "website": None,
            "category": "Test Category",
            "established": "2020"
        },
        {
            "id": "test_2",
            "name": "Test Business 2 Mary",
            "address": "456 Test Ave, Mary",
            "city": "Mary", # <--- AND ADD THIS
            "phone": "+1-555-0456",
            "website": None,
            "category": "Test Category 2",
            "established": "2021"
        }
    ]
    
    logger.info(f"[Callback] Creating mock data: {len(final_businesses)} businesses")
    
    for business in final_businesses:
        # This part is fine.
        send_update_to_ui(business)
    
    # Save as artifact
    try:
        await callback_context.save_artifact("final_lead_results", {
            "businesses": final_businesses,
            "count": len(final_businesses)
        })
        logger.info(f"[Callback] Saved artifact with {len(final_businesses)} businesses")
    except Exception as e:
        logger.error(f"[Callback] Error saving artifact: {e}")
    
    # Return the final content for the A2A task
    final_output_content = genai_types.Content(
        parts=[
            genai_types.Part(
                function_call=genai_types.FunctionCall(
                    name="final_lead_results",
                    args={"businesses": final_businesses, "count": len(final_businesses)},
                )
            )
        ],
        role="model",
    )

    logger.info("[Callback] UI updates sent. Callback finished.")
    return None 
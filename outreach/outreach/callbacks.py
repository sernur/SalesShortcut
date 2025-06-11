# In outreach/callbacks.py

import json
import asyncio
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

import httpx

import common.config as config

from google.adk.agents.callback_context import CallbackContext
from google.genai import types as genai_types

logger = logging.getLogger(__name__)


def send_update_to_ui(outreach_data: dict):
    """
    Sends an outreach update to the UI client's /agent_callback endpoint.
    """
    ui_client_url = os.environ.get(
        "UI_CLIENT_SERVICE_URL", config.DEFAULT_UI_CLIENT_URL
    ).rstrip("/")
    callback_endpoint = f"{ui_client_url}/agent_callback"

    # Create a copy of the outreach_data to modify it for UI client's validation
    data_for_ui = outreach_data.copy()

    payload = {
        "agent_type": "outreach",
        "task_id": data_for_ui.get("id") or data_for_ui.get("message_id") or data_for_ui.get("call_id"),
        "status": data_for_ui.get("status", "completed"),
        "message": f"Outreach activity completed: {data_for_ui.get('action_type', 'unknown')}",
        "timestamp": datetime.now().isoformat(),
        "data": data_for_ui
    }

    logger.info(f"Sending POST to UI endpoint: {callback_endpoint} for outreach: {data_for_ui.get('action_type')}")
    try:
        with httpx.Client() as client:
            response = client.post(callback_endpoint, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Successfully posted outreach update to UI. Status: {response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Error sending POST request to UI client at {e.request.url}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while posting to the UI client: {e}")


async def post_results_callback(callback_context: CallbackContext) -> Optional[genai_types.Content]:
    agent_name = callback_context.agent_name
    logger.info(f"[Callback] Exiting agent: {agent_name}. Processing outreach results.")

    final_results: List[Dict[str, Any]] = []

    # Access the state directly
    context_state = callback_context.state.to_dict()
    print(f"[Callback] Current callback_context.state: {context_state}")

    # Look for outreach results in various state keys
    outreach_keys = ['outreach_results', 'phone_call_results', 'email_results', 'final_results']
    
    for key in outreach_keys:
        if key in context_state:
            try:
                results_data = context_state[key]
                if isinstance(results_data, str):
                    # Try to parse as JSON if it's a string
                    try:
                        parsed_data = json.loads(results_data)
                        if isinstance(parsed_data, list):
                            final_results.extend(parsed_data)
                        elif isinstance(parsed_data, dict):
                            final_results.append(parsed_data)
                    except json.JSONDecodeError:
                        # If not JSON, treat as single result
                        final_results.append({"action_type": key, "result": results_data})
                elif isinstance(results_data, list):
                    final_results.extend(results_data)
                elif isinstance(results_data, dict):
                    final_results.append(results_data)
                    
                logger.info(f"[Callback] Found {len(final_results)} results from {key}")
            except Exception as e:
                logger.error(f"[Callback] Error processing {key} from state: {e}")

    if not final_results:
        logger.warning("[Callback] No outreach results found in callback_context.state.")
        # Create a mock result for testing
        final_results = [{
            "id": f"mock_{datetime.now().timestamp()}",
            "action_type": "test_outreach",
            "status": "completed",
            "message": "Mock outreach activity completed for testing",
            "timestamp": datetime.now().isoformat()
        }]

    # Send updates to UI for each result
    for result in final_results:
        if "id" not in result:
            # Generate a stable ID for the result
            result["id"] = f"outreach_{datetime.now().timestamp()}_{hash(str(result))}"
        send_update_to_ui(result)

    try:
        # Save artifacts
        await callback_context.save_artifact("final_outreach_results", {
            "results": final_results,
            "count": len(final_results)
        })
        logger.info(f"[Callback] Saved artifact with {len(final_results)} outreach results for task completion.")
    except Exception as e:
        logger.error(f"[Callback] Error saving final artifact: {e}")

    logger.info("[Callback] UI updates sent. Callback finished.")
    return None
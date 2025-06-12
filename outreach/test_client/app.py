#!/usr/bin/env python3
"""
A2A-enabled FastAPI web client for testing the Outreach Agent.
Supports both phone calls and email messaging via A2A communication.
This version strictly uses A2A for communication with the ADK Agent.
"""
import os
import sys
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import httpx

# --- START OF CHANGE ---
# Get the absolute path of the current file's directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Navigate up two levels to reach the project root
# current_dir is '.../outreach/test_client'
# parent_dir is '.../outreach'
# project_root is '.../' (the directory containing 'common', 'outreach', etc.)
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))

# Add the project root to sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root) # Insert at the beginning for higher priority
# --- END OF CHANGE ---

# Now you can import common.config directly
import common.config as config # This should now work

# The rest of your code
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BUSINESS_LOGIC_LOGGER = "BusinessLogic" # This line seems out of place for this file,
                                          # typically defined in common.config or the main entry
                                          # of a business logic component.

# A2A SDK Imports - these are now mandatory
try:
    from a2a.client import A2AClient, A2AClientHTTPError, A2AClientJSONError
    from a2a.types import DataPart as A2ADataPart
    from a2a.types import JSONRPCErrorResponse
    from a2a.types import SendMessageSuccessResponse
    from a2a.types import Message as A2AMessage
    from a2a.types import MessageSendConfiguration, MessageSendParams
    from a2a.types import Role as A2ARole
    from a2a.types import SendMessageRequest, SendMessageResponse
    from a2a.types import Task as A2ATask
    A2A_AVAILABLE = True
except ImportError:
    logger.warning("A2A dependencies not found, falling back to simple HTTP client")
    A2A_AVAILABLE = False
    # Exit if A2A is not available as it's a hard dependency now
    import sys
    sys.exit(1)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Base URL of the Outreach Agent API (defaults to ADK main default port)
AGENT_URL = os.environ.get("OUTREACH_AGENT_URL", "http://localhost:8083")

async def check_a2a_availability(url: str) -> bool:
    """
    Check if the outreach agent is alive and responds in an A2A-compatible way.
    This can be by checking for a specific A2A agent card or a known A2A endpoint.
    For simplicity, we'll assume a successful connection to the base URL implies
    A2A compatibility if the A2A SDK is available. In a real scenario, you'd
    check for the agent card or a specific A2A endpoint.
    """
    if not A2A_AVAILABLE:
        logger.error("A2A_AVAILABLE is not available. Cannot check agent availability.")
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Attempt to connect to the agent's base URL.
            # A robust check would involve fetching the agent card via A2AClient.get_agent_card()
            # but for this example, a simple HTTP GET to the base URL is a good start.
            response = await client.get(f"{url}/")
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to connect to Outreach Agent at {url}: {e}")
        return False

async def call_outreach_agent_a2a(task_type: str, task_data: dict[str, Any], session_id: str) -> dict[str, Any]:
    """
    Calls the Outreach agent via A2A to conduct outreach activities.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    outreach_url = os.environ.get(
        "DEFAULT_OUTREACH_URL", config.DEFAULT_OUTREACH_URL
    ).rstrip("/")

    business_logger.info(f"Calling Outreach at {outreach_url} for {task_type}")

    outcome = {
        "success": False,
        "result": None,
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient() as http_client:
            a2a_client = A2AClient(httpx_client=http_client, url=outreach_url)

            # Prepare A2A message
            a2a_task_id = f"outreach-client-{session_id}"
            
            # Convert to outreach agent expected format
            if task_type == "phone_call":
                outreach_data = {
                    "target": task_data["phone_number"],
                    "type": "phone",
                    "message": task_data["script"],
                    "operation": "conduct_outreach"
                }
            elif task_type == "email":
                outreach_data = {
                    "target": task_data["to_email"],
                    "type": "email",
                    "message": f"Subject: {task_data['subject']}\n\n{task_data['message_body']}",
                    "operation": "conduct_outreach"
                }
            else:
                outreach_data = task_data

            sdk_message = A2AMessage(
                taskId=a2a_task_id,
                contextId=session_id,
                messageId=str(uuid.uuid4()),
                role=A2ARole.user,
                parts=[A2ADataPart(data=outreach_data)],
                metadata={"operation": "outreach", "task_type": task_type, "outreach_data": outreach_data},
            )
            
            sdk_send_params = MessageSendParams(
                message=sdk_message,
                configuration=MessageSendConfiguration(
                    acceptedOutputModes=["data", "application/json"]
                ),
            )
            
            sdk_request = SendMessageRequest(
                id=str(uuid.uuid4()), params=sdk_send_params
            )

            # Send request to Outreach
            response: SendMessageResponse = await a2a_client.send_message(sdk_request)
            root_response_part = response.root
            
            if isinstance(root_response_part, JSONRPCErrorResponse):
                actual_error = root_response_part.error
                business_logger.error(
                    f"A2A Error from Outreach: {actual_error.code} - {actual_error.message}"
                )
                outcome["error"] = f"A2A Error: {actual_error.code} - {actual_error.message}"
                
            elif isinstance(root_response_part, SendMessageSuccessResponse):
                task_result: A2ATask = root_response_part.result
                business_logger.info(
                    f"Outreach task {task_result.id} completed with state: {task_result.status.state}"
                )

                # Extract outreach results from artifacts
                if task_result.artifacts:
                    outreach_results_artifact = next(
                        (
                            a
                            for a in task_result.artifacts
                            if a.name == config.DEFAULT_OUTREACH_ARTIFACT_NAME
                        ),
                        None,
                    )

                    if outreach_results_artifact and outreach_results_artifact.parts:
                        art_part_root = outreach_results_artifact.parts[0].root
                        if isinstance(art_part_root, A2ADataPart):
                            result_data = art_part_root.data
                            business_logger.info(f"Extracted Outreach Results: {result_data}")
                            outcome["success"] = True
                            outcome["result"] = result_data
                        else:
                            business_logger.warning(f"Unexpected artifact part type: {type(art_part_root)}")
                            outcome["error"] = "Invalid artifact format"
                    else:
                        business_logger.info("Outreach results artifact not found or empty")
                        outcome["success"] = True
                        outcome["result"] = {"message": "Outreach completed but no detailed results available"}
                else:
                    business_logger.info("No artifacts found in Outreach response")
                    outcome["success"] = True
                    outcome["result"] = {"message": "Outreach completed but no artifacts returned"}
            else:
                business_logger.error(f"Invalid A2A response type: {type(root_response_part)}")
                outcome["error"] = "Invalid response type"
                
    except Exception as e:
        if A2A_AVAILABLE and 'A2AClientHTTPError' in str(type(e)):
            business_logger.error(f"HTTP Error calling Outreach: {e}")
            outcome["error"] = f"Connection Error: {e}"
        elif A2A_AVAILABLE and 'A2AClientJSONError' in str(type(e)):
            business_logger.error(f"JSON Error from Outreach: {e}")
            outcome["error"] = f"JSON Response Error: {e}"
        else:
            business_logger.error(f"Unexpected error calling Outreach: {e}", exc_info=True)
            outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    """
    Render the main page with empty forms.
    """
    return templates.TemplateResponse("index.html", {
        "request": request,
        "phone": "",
        "prompt": "",
        "email": "",
        "subject": "",
        "message": "",
        "phone_result": None,
        "email_result": None,
    })

@app.post("/call", response_class=HTMLResponse)
async def call(request: Request, phone: str = Form(...), prompt: str = Form(...)):
    """
    Handle phone call form submission strictly via A2A communication.
    """
    session_id = str(uuid.uuid4())

    # Prepare phone call data
    phone_data = {
        "phone_number": phone,
        "script": prompt,
    }

    logging.info(f"Calling Outreach Agent for phone call to {phone} with prompt: {prompt}")
    # Call agent using A2A only
    result = await call_outreach_agent_a2a("phone_call", phone_data, session_id)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "phone": phone,
        "prompt": prompt,
        "email": "",
        "subject": "",
        "message": "",
        "phone_result": result,
        "email_result": None,
    })

@app.post("/email", response_class=HTMLResponse)
async def send_email(
    request: Request,
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...)
):
    """
    Handle email form submission strictly via A2A communication.
    """
    session_id = str(uuid.uuid4())

    # Prepare email data
    email_data = {
        "to_email": email,
        "subject": subject,
        "message_body": message,
        "email_type": "outreach", # Specify email type if agent supports it
        "task_type": "email" # Ensure agent knows the task type
    }

    # Call agent using A2A only
    result = await call_outreach_agent_a2a("email", email_data, session_id)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "phone": "",
        "prompt": "",
        "email": email,
        "subject": subject,
        "message": message,
        "phone_result": None,
        "email_result": result,
    })

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check if outreach agent supports A2A
    outreach_agent_a2a_mode = await check_a2a_availability(AGENT_URL)

    return JSONResponse({
        "status": "healthy",
        "service": "outreach_test_client",
        "a2a_sdk_available": A2A_AVAILABLE,
        "outreach_agent_a2a_mode": outreach_agent_a2a_mode,
        "agent_url": AGENT_URL,
        "timestamp": datetime.now().isoformat(),
    })
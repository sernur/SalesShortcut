#!/usr/bin/env python3
"""
A2A-enabled FastAPI web client for testing the Outreach Agent.
Supports both phone calls and email messaging via A2A communication.
"""
import os
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import httpx

# A2A SDK Imports with fallback
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
    A2A_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Base URL of the Outreach Agent API (defaults to ADK main default port)
AGENT_URL = os.environ.get("OUTREACH_AGENT_URL", "http://localhost:8083")

async def call_outreach_agent_a2a(task_type: str, task_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    """
    Calls the Outreach Agent via A2A communication.
    """
    logger.info(f"Calling Outreach Agent via A2A for {task_type}")
    
    outcome = {
        "success": False,
        "result": None,
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient() as http_client:
            a2a_client = A2AClient(httpx_client=http_client, url=AGENT_URL)
            
            # Prepare A2A message
            a2a_task_id = f"outreach-{task_type}-{session_id}"
            
            sdk_message = A2AMessage(
                taskId=a2a_task_id,
                contextId=session_id,
                messageId=str(uuid.uuid4()),
                role=A2ARole.user,
                parts=[A2ADataPart(data=task_data)],
                metadata={"operation": task_type, "timestamp": datetime.now().isoformat()},
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
            
            # Send request to Outreach Agent
            response: SendMessageResponse = await a2a_client.send_message(sdk_request)
            root_response_part = response.root
            
            if isinstance(root_response_part, JSONRPCErrorResponse):
                actual_error = root_response_part.error
                logger.error(f"A2A Error from Outreach Agent: {actual_error.code} - {actual_error.message}")
                outcome["error"] = f"A2A Error: {actual_error.code} - {actual_error.message}"
                
            elif isinstance(root_response_part, SendMessageSuccessResponse):
                task_result: A2ATask = root_response_part.result
                logger.info(f"Outreach task {task_result.id} completed with state: {task_result.status.state}")
                
                # Extract result data from artifacts
                if task_result.artifacts:
                    result_artifact = task_result.artifacts[0] if task_result.artifacts else None
                    if result_artifact and result_artifact.parts:
                        art_part_root = result_artifact.parts[0].root
                        if isinstance(art_part_root, A2ADataPart):
                            outcome["success"] = True
                            outcome["result"] = art_part_root.data
                        else:
                            logger.warning(f"Unexpected artifact part type: {type(art_part_root)}")
                            outcome["error"] = "Invalid artifact format"
                    else:
                        logger.info("No result artifact found")
                        outcome["success"] = True
                        outcome["result"] = {"status": "completed", "message": "Task completed without specific result"}
                else:
                    logger.info("No artifacts found in response")
                    outcome["success"] = True
                    outcome["result"] = {"status": "completed", "message": "Task completed"}
            else:
                logger.error(f"Invalid A2A response type: {type(root_response_part)}")
                outcome["error"] = "Invalid response type"
                
    except Exception as e:
        logger.error(f"Error calling Outreach Agent via A2A: {e}", exc_info=True)
        outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_outreach_agent_simple(endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls the Outreach Agent via simple HTTP when A2A is not available.
    """
    logger.info(f"Calling Outreach Agent via simple HTTP at {endpoint}")
    
    outcome = {
        "success": False,
        "result": None,
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{AGENT_URL}{endpoint}", data=data)
            response.raise_for_status()
            result = response.json()
            outcome["success"] = True
            outcome["result"] = result
    except Exception as e:
        logger.error(f"Error calling Outreach Agent via HTTP: {e}")
        outcome["error"] = str(e)
    
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
    Handle phone call form submission via A2A communication.
    """
    session_id = str(uuid.uuid4())
    
    # Prepare phone call data
    phone_data = {
        "phone_number": phone,
        "script": prompt,
        "task_type": "phone_call"
    }
    
    # Try A2A first, fallback to simple HTTP
    if A2A_AVAILABLE:
        result = await call_outreach_agent_a2a("phone_call", phone_data, session_id)
    else:
        result = await call_outreach_agent_simple("/mock_phone_call", {
            "phone_number": phone, 
            "script": prompt
        })
    
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
    Handle email form submission via A2A communication.
    """
    session_id = str(uuid.uuid4())
    
    # Prepare email data
    email_data = {
        "to_email": email,
        "subject": subject,
        "message_body": message,
        "email_type": "outreach",
        "task_type": "email"
    }
    
    # Try A2A first, fallback to simple HTTP
    if A2A_AVAILABLE:
        result = await call_outreach_agent_a2a("email", email_data, session_id)
    else:
        # For simple HTTP, we'll create a mock endpoint that doesn't exist yet
        result = await call_outreach_agent_simple("/mock_email", {
            "to_email": email,
            "subject": subject,
            "message_body": message,
            "email_type": "outreach"
        })
    
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
    return {
        "status": "healthy",
        "service": "outreach_test_client",
        "a2a_available": A2A_AVAILABLE,
        "agent_url": AGENT_URL,
        "timestamp": datetime.now().isoformat(),
    }
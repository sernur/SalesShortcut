"""
FastAPI application for the SalesShortcut UI Client.

Provides a web interface to manage sales agent workflows including lead finding,
SDR engagement, lead management, and calendar scheduling. Features real-time
updates via WebSocket and A2A integration with sales agents.
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from enum import Enum

# Common project imports
import common.config as config
import httpx
from pydantic import BaseModel, Field, ValidationError

from fastapi import Depends, FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

UI_CLIENT_LOGGER = "UIClient"
BUSINESS_LOGIC_LOGGER = "BusinessLogic"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(UI_CLIENT_LOGGER)

# A2A SDK Imports (optional - fallback to simple HTTP if not available)
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

# Ensure imports work
try:
    import common.config
except ImportError as e:
    logger.error(f"Failed to import necessary application modules: {e}")
    logger.error("Ensure you run uvicorn from the project root directory.")
    logger.error("Example: uvicorn ui_client.main:app --reload --port 8000")
    sys.exit(1)

module_dir = Path(__file__).parent
templates_dir = module_dir / "templates"
static_dir = module_dir / "static"

# Business Status Enums
class BusinessStatus(str, Enum):
    FOUND = "found"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    NOT_INTERESTED = "not_interested"
    NO_RESPONSE = "no_response"
    CONVERTING = "converting"
    MEETING_SCHEDULED = "meeting_scheduled"

class AgentType(str, Enum):
    LEAD_FINDER = "lead_finder"
    SDR = "sdr"
    LEAD_MANAGER = "lead_manager"

# Data Models
class Business(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    description: Optional[str] = None
    city: str
    status: BusinessStatus = BusinessStatus.FOUND
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    notes: List[str] = Field(default_factory=list)

class AgentUpdate(BaseModel):
    agent_type: AgentType
    business_id: str
    status: BusinessStatus
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Optional[dict[str, Any]] = None

class LeadFinderRequest(BaseModel):
    city: str = Field(..., min_length=1, max_length=100, description="Target city for lead finding")

class HumanInputRequest(BaseModel):
    request_id: str
    prompt: str
    type: str
    timestamp: str

class HumanInputResponse(BaseModel):
    request_id: str
    response: str

# Global application state
app_state = {
    "is_running": False,
    "current_city": None,
    "businesses": {},  # dict[str, Business]
    "agent_updates": [],  # List[AgentUpdate]
    "websocket_connections": set(),  # Set[WebSocket]
    "session_id": None,
    "human_input_requests": {},  # dict[str, HumanInputRequest]
}

class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_update(self, data: dict[str, Any]):
        """Send update to all connected clients."""
        if not self.active_connections:
            return
        
        message = json.dumps(data, default=str)
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {e}")
                disconnected.add(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.info("UI Client starting up...")
    # Initialize any startup tasks here
    yield
    logger.info("UI Client shutting down...")

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=str(templates_dir))
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

def format_currency(value: Optional[float]) -> str:
    """Formats an optional float value as currency."""
    if value is None:
        return "N/A"
    return f"${value:,.2f}"

def format_datetime(dt: datetime) -> str:
    """Formats datetime for display."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# Add custom filters to templates
templates.env.filters["format_currency"] = format_currency
templates.env.filters["format_datetime"] = format_datetime

async def call_lead_finder_agent_a2a(city: str, session_id: str) -> dict[str, Any]:
    """
    Calls the Lead Finder agent via A2A to find businesses in the specified city.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    lead_finder_url = os.environ.get(
        "LEAD_FINDER_SERVICE_URL", config.DEFAULT_LEAD_FINDER_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling Lead Finder at {lead_finder_url} for city: {city}")
    
    outcome = {
        "success": False,
        "businesses": [],
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient() as http_client:
            a2a_client = A2AClient(httpx_client=http_client, url=lead_finder_url)
            
            # Prepare A2A message
            a2a_task_id = f"lead-search-{session_id}"
            
            search_data = {
                "city": city,
            }
            
            sdk_message = A2AMessage(
                taskId=a2a_task_id,
                contextId=session_id,
                messageId=str(uuid.uuid4()),
                role=A2ARole.user,
                parts=[A2ADataPart(data=search_data)],
                metadata={"operation": "find_leads", "city": city},
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
            
            # Send request to Lead Finder
            response: SendMessageResponse = await a2a_client.send_message(sdk_request)
            root_response_part = response.root
            
            if isinstance(root_response_part, JSONRPCErrorResponse):
                actual_error = root_response_part.error
                business_logger.error(
                    f"A2A Error from Lead Finder: {actual_error.code} - {actual_error.message}"
                )
                outcome["error"] = f"A2A Error: {actual_error.code} - {actual_error.message}"
                
            elif isinstance(root_response_part, SendMessageSuccessResponse):
                task_result: A2ATask = root_response_part.result
                business_logger.info(
                    f"Lead Finder task {task_result.id} completed with state: {task_result.status.state}"
                )
                
                # Extract business data from artifacts
                if task_result.artifacts:
                    lead_results_artifact = next(
                        (
                            a
                            for a in task_result.artifacts
                            if a.name == config.DEFAULT_LEAD_FINDER_ARTIFACT_NAME
                        ),
                        None,
                    )
                    
                    if lead_results_artifact and lead_results_artifact.parts:
                        art_part_root = lead_results_artifact.parts[0].root
                        if isinstance(art_part_root, A2ADataPart):
                            result_data = art_part_root.data
                            business_logger.info(f"Extracted Lead Results: {result_data}")
                            
                            if isinstance(result_data, dict) and "businesses" in result_data:
                                outcome["success"] = True
                                outcome["businesses"] = result_data["businesses"]
                            else:
                                business_logger.warning("Unexpected lead results format")
                                outcome["error"] = "Invalid lead results format"
                        else:
                            business_logger.warning(f"Unexpected artifact part type: {type(art_part_root)}")
                    else:
                        business_logger.info("Lead results artifact not found or empty - checking for empty results")
                        # Don't set this as an error immediately, let the success flow handle empty results
                        outcome["success"] = True
                        outcome["businesses"] = []
                else:
                    business_logger.info("No artifacts found in Lead Finder response - treating as empty results")
                    outcome["success"] = True
                    outcome["businesses"] = []
            else:
                business_logger.error(f"Invalid A2A response type: {type(root_response_part)}")
                outcome["error"] = "Invalid response type"
                
    except Exception as e:
        if A2A_AVAILABLE and 'A2AClientHTTPError' in str(type(e)):
            business_logger.error(f"HTTP Error calling Lead Finder: {e}")
            outcome["error"] = f"Connection Error: {e}"
        elif A2A_AVAILABLE and 'A2AClientJSONError' in str(type(e)):
            business_logger.error(f"JSON Error from Lead Finder: {e}")
            outcome["error"] = f"JSON Response Error: {e}"
        else:
            business_logger.error(f"Unexpected error calling Lead Finder: {e}", exc_info=True)
            outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_lead_finder_agent_simple(city: str, session_id: str) -> dict[str, Any]:
    """
    Calls the Lead Finder service via simple HTTP POST when A2A is not available.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    lead_finder_url = os.environ.get(
        "LEAD_FINDER_SERVICE_URL", config.DEFAULT_LEAD_FINDER_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling Lead Finder (simple HTTP) at {lead_finder_url} for city: {city}")
    
    outcome = {
        "success": False,
        "businesses": [],
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Try different endpoints that might exist
            endpoints_to_try = [
                f"{lead_finder_url}/find_leads",
                f"{lead_finder_url}/search",
                f"{lead_finder_url}/",
            ]
            
            search_data = {
                "city": city,
                "max_results": 50,
                "session_id": session_id,
            }
            
            for endpoint in endpoints_to_try:
                try:
                    business_logger.info(f"Trying endpoint: {endpoint}")
                    response = await client.post(endpoint, json=search_data)
                    
                    if response.status_code == 200:
                        result_data = response.json()
                        business_logger.info(f"Got response from {endpoint}: {result_data}")
                        
                        # Handle different response formats
                        if isinstance(result_data, dict):
                            if "businesses" in result_data:
                                outcome["success"] = True
                                outcome["businesses"] = result_data["businesses"]
                                break
                            elif "results" in result_data:
                                outcome["success"] = True
                                outcome["businesses"] = result_data["results"]
                                break
                            elif "data" in result_data:
                                outcome["success"] = True
                                outcome["businesses"] = result_data["data"]
                                break
                        elif isinstance(result_data, list):
                            outcome["success"] = True
                            outcome["businesses"] = result_data
                            break
                    
                    business_logger.warning(f"Endpoint {endpoint} returned status {response.status_code}")
                    
                except Exception as e:
                    business_logger.warning(f"Endpoint {endpoint} failed: {e}")
                    continue
            
            if not outcome["success"]:
                outcome["error"] = "All Lead Finder endpoints failed or returned no data"
                
    except Exception as e:
        business_logger.error(f"Unexpected error calling Lead Finder: {e}", exc_info=True)
        outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_lead_finder_agent(city: str, session_id: str) -> dict[str, Any]:
    """
    Calls the Lead Finder agent - uses A2A if available, otherwise falls back to simple HTTP.
    """
    if A2A_AVAILABLE:
        return await call_lead_finder_agent_a2a(city, session_id)
    else:
        return await call_lead_finder_agent_simple(city, session_id)

async def call_sdr_agent_a2a(business_data: dict[str, Any], session_id: str) -> dict[str, Any]:
    """
    Calls the SDR agent via A2A to process a business lead.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    sdr_url = os.environ.get(
        "SDR_SERVICE_URL", config.DEFAULT_SDR_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling SDR agent at {sdr_url} for business: {business_data.get('name', 'Unknown')}")
    
    outcome = {
        "success": False,
        "message": None,
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient() as http_client:
            a2a_client = A2AClient(httpx_client=http_client, url=sdr_url)
            
            # Prepare A2A message
            a2a_task_id = f"sdr-engagement-{session_id}-{business_data.get('id', 'unknown')}"
            
            sdk_message = A2AMessage(
                taskId=a2a_task_id,
                contextId=session_id,
                messageId=str(uuid.uuid4()),
                role=A2ARole.user,
                parts=[A2ADataPart(data=business_data)],
                metadata={"operation": "engage_lead", "business_id": business_data.get("id")},
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
            
            # Send request to SDR agent
            response: SendMessageResponse = await a2a_client.send_message(sdk_request)
            root_response_part = response.root
            
            if isinstance(root_response_part, JSONRPCErrorResponse):
                actual_error = root_response_part.error
                business_logger.error(
                    f"A2A Error from SDR agent: {actual_error.code} - {actual_error.message}"
                )
                outcome["error"] = f"A2A Error: {actual_error.code} - {actual_error.message}"
                
            elif isinstance(root_response_part, SendMessageSuccessResponse):
                task_result: A2ATask = root_response_part.result
                business_logger.info(
                    f"SDR agent task {task_result.id} completed with state: {task_result.status.state}"
                )
                
                outcome["success"] = True
                outcome["message"] = f"SDR agent has started processing {business_data.get('name', 'the business')}"
                
            else:
                business_logger.error(f"Invalid A2A response type: {type(root_response_part)}")
                outcome["error"] = "Invalid response type"
                
    except Exception as e:
        if A2A_AVAILABLE and 'A2AClientHTTPError' in str(type(e)):
            business_logger.error(f"HTTP Error calling SDR agent: {e}")
            outcome["error"] = f"Connection Error: {e}"
        elif A2A_AVAILABLE and 'A2AClientJSONError' in str(type(e)):
            business_logger.error(f"JSON Error from SDR agent: {e}")
            outcome["error"] = f"JSON Response Error: {e}"
        else:
            business_logger.error(f"Unexpected error calling SDR agent: {e}", exc_info=True)
            outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_sdr_agent_simple(business_data: dict[str, Any], session_id: str) -> dict[str, Any]:
    """
    Calls the SDR agent via simple HTTP POST when A2A is not available.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    sdr_url = os.environ.get(
        "SDR_SERVICE_URL", config.DEFAULT_SDR_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling SDR agent (simple HTTP) at {sdr_url} for business: {business_data.get('name', 'Unknown')}")
    
    outcome = {
        "success": False,
        "message": None,
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Try different endpoints that might exist
            endpoints_to_try = [
                # f"{sdr_url}/engage_lead",
                # f"{sdr_url}/process",
                f"{sdr_url}/",
            ]
            
            sdr_data = {
                "business": business_data,
                "session_id": session_id,
            }
            
            for endpoint in endpoints_to_try:
                try:
                    business_logger.info(f"Trying SDR endpoint: {endpoint}")
                    response = await client.post(endpoint, json=sdr_data)
                    
                    if response.status_code == 200:
                        result_data = response.json()
                        business_logger.info(f"Got response from SDR at {endpoint}: {result_data}")
                        
                        outcome["success"] = True
                        outcome["message"] = f"SDR agent has started processing {business_data.get('name', 'the business')}"
                        break
                    
                    business_logger.warning(f"SDR endpoint {endpoint} returned status {response.status_code}")
                    
                except Exception as e:
                    business_logger.warning(f"SDR endpoint {endpoint} failed: {e}")
                    continue
            
            if not outcome["success"]:
                outcome["error"] = "All SDR agent endpoints failed"
                
    except Exception as e:
        business_logger.error(f"Unexpected error calling SDR agent: {e}", exc_info=True)
        outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_sdr_agent(business_data: dict[str, Any], session_id: str) -> dict[str, Any]:
    """
    Calls the SDR agent - uses A2A if available, otherwise falls back to simple HTTP.
    """
    if A2A_AVAILABLE:
        return await call_sdr_agent_a2a(business_data, session_id)
    else:
        return await call_sdr_agent_simple(business_data, session_id)

async def call_lead_manager_agent_a2a(query: str, session_id: str) -> dict[str, Any]:
    """
    Calls the Lead Manager agent via A2A to process lead management tasks.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    lead_manager_url = os.environ.get(
        "LEAD_MANAGER_SERVICE_URL", config.DEFAULT_LEAD_MANAGER_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling Lead Manager at {lead_manager_url} for query: {query}")
    
    outcome = {
        "success": False,
        "message": None,
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient() as http_client:
            a2a_client = A2AClient(httpx_client=http_client, url=lead_manager_url)
            
            # Prepare A2A message
            a2a_task_id = f"lead-management-{session_id}"
            
            lead_data = {
                "query": query,
                "ui_client_url": config.DEFAULT_UI_CLIENT_URL
            }
            
            sdk_message = A2AMessage(
                taskId=a2a_task_id,
                contextId=session_id,
                messageId=str(uuid.uuid4()),
                role=A2ARole.user,
                parts=[A2ADataPart(data=lead_data)],
                metadata={"operation": "process_lead_management", "query": query},
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
            
            # Send request to Lead Manager
            response: SendMessageResponse = await a2a_client.send_message(sdk_request)
            root_response_part = response.root
            
            if isinstance(root_response_part, JSONRPCErrorResponse):
                actual_error = root_response_part.error
                business_logger.error(
                    f"A2A Error from Lead Manager: {actual_error.code} - {actual_error.message}"
                )
                outcome["error"] = f"A2A Error: {actual_error.code} - {actual_error.message}"
                
            elif isinstance(root_response_part, SendMessageSuccessResponse):
                task_result: A2ATask = root_response_part.result
                business_logger.info(
                    f"Lead Manager task {task_result.id} completed with state: {task_result.status.state}"
                )
                
                # Extract result from artifacts
                if task_result.artifacts:
                    lead_management_artifact = next(
                        (
                            a
                            for a in task_result.artifacts
                            if a.name == config.DEFAULT_LEAD_MANAGER_ARTIFACT_NAME
                        ),
                        None,
                    )
                    
                    if lead_management_artifact and lead_management_artifact.parts:
                        art_part_root = lead_management_artifact.parts[0].root
                        if isinstance(art_part_root, A2ADataPart):
                            result_data = art_part_root.data
                            business_logger.info(f"Lead Manager Result: {result_data}")
                            outcome["success"] = True
                            outcome["message"] = result_data.get("message", "Lead management task completed")
                
                if not outcome["success"]:
                    outcome["success"] = True
                    outcome["message"] = "Lead management task completed successfully"
                
            else:
                business_logger.error(f"Invalid A2A response type: {type(root_response_part)}")
                outcome["error"] = "Invalid response type"
                
    except Exception as e:
        business_logger.error(f"Unexpected error calling Lead Manager: {e}", exc_info=True)
        outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_lead_manager_agent_simple(query: str, session_id: str) -> dict[str, Any]:
    """
    Calls the Lead Manager service via simple HTTP POST when A2A is not available.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    lead_manager_url = os.environ.get(
        "LEAD_MANAGER_SERVICE_URL", config.DEFAULT_LEAD_MANAGER_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling Lead Manager (simple) at {lead_manager_url} for query: {query}")
    
    outcome = {
        "success": False,
        "message": None,
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient() as http_client:
            payload = {
                "query": query,
                "ui_client_url": config.DEFAULT_UI_CLIENT_URL
            }
            
            response = await http_client.post(
                f"{lead_manager_url}/search",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                business_logger.info(f"Lead Manager (simple) responded: {result}")
                outcome["success"] = True
                outcome["message"] = result.get("message", "Lead management completed successfully")
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                business_logger.error(f"Lead Manager (simple) error: {error_msg}")
                outcome["error"] = error_msg
                
    except Exception as e:
        business_logger.error(f"Unexpected error calling Lead Manager (simple): {e}", exc_info=True)
        outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_lead_manager_agent(query: str, session_id: str) -> dict[str, Any]:
    """
    Calls the Lead Manager agent - uses A2A if available, otherwise falls back to simple HTTP.
    """
    if A2A_AVAILABLE:
        return await call_lead_manager_agent_a2a(query, session_id)
    else:
        return await call_lead_manager_agent_simple(query, session_id)

async def run_lead_finding_process(city: str, session_id: str):
    """Run the complete lead finding process."""
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    try:
        business_logger.info(f"Starting lead finding process for {city}")
        
        # Call Lead Finder agent
        result = await call_lead_finder_agent(city, session_id)
        
        if result["success"]:
            found_businesses = result.get("businesses", [])
            business_logger.info(f"Lead Finder returned {len(found_businesses)} businesses")

            # Send completion update regardless of whether businesses were found
            await manager.send_update({
                "type": "lead_finding_completed",
                "city": city,
                "business_count": len(found_businesses),
                "timestamp": datetime.now().isoformat(),
            })
            
            # Check if the returned list is empty
            if not found_businesses:
                business_logger.info(f"No businesses found for city: {city}. Notifying UI.")
                await manager.send_update({
                    "type": "lead_finding_empty",
                    "city": city,
                    "message": "No businesses found for this city. Try another city.",
                    "timestamp": datetime.now().isoformat(),
                })
            
        else:
            business_logger.error(f"Lead finding failed: {result['error']}")
            await manager.send_update({
                "type": "lead_finding_failed",
                "error": result["error"],
                "timestamp": datetime.now().isoformat(),
            })
    
    except Exception as e:
        business_logger.error(f"Error in lead finding process: {e}", exc_info=True)
        await manager.send_update({
            "type": "lead_finding_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })
    
    finally:
        # The process is no longer running, regardless of outcome
        app_state["is_running"] = False
        # Also send an update to the UI so it can re-enable buttons etc.
        await manager.send_update({
            "type": "process_finished",
            "timestamp": datetime.now().isoformat(),
        })

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current state to newly connected client
        await websocket.send_text(json.dumps({
            "type": "initial_state",
            "businesses": [business.dict() for business in app_state["businesses"].values()],
            "current_city": app_state["current_city"],
            "is_running": app_state["is_running"],
        }))
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Agent callback endpoint
# In ui_client/main.py
# In ui_client/main.py

# In ui_client/main.py

# In ui_client/main.py

@app.post("/agent_callback")
async def agent_callback(update: AgentUpdate):
    """
    Endpoint for agents to send updates about business processing.
    This version handles creating new businesses and correctly serializes
    Pydantic models before sending them over WebSockets.
    """
    logger.info(f"Received agent callback: {update.agent_type} for business {update.business_id}")

    # Check if business exists
    if update.business_id in app_state["businesses"]:
        # Business exists, so update it
        business = app_state["businesses"][update.business_id]
        business.status = update.status
        business.updated_at = datetime.now()
        business.notes.append(f"{update.agent_type}: {update.message}")
        logger.info(f"Updated business {business.name} status to {update.status}")
    else:
        # Business does NOT exist, so create it from the callback data
        logger.info(f"Business ID {update.business_id} not found. Creating new business entry.")
        if update.data and "name" in update.data and "city" in update.data:
            try:
                new_business = Business(
                    id=update.business_id,
                    name=update.data.get("name"),
                    phone=update.data.get("phone"),
                    email=update.data.get("email"),
                    description=update.data.get("description"),
                    city=update.data.get("city"),
                    status=update.status,
                    notes=[f"{update.agent_type}: {update.message}"]
                )
                app_state["businesses"][update.business_id] = new_business
            except Exception as e:
                logger.error(f"Failed to create business from callback data: {e}")
                return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid business data for creation"})
        else:
            logger.warning(f"Cannot create business {update.business_id}: 'data' field in callback is missing or incomplete.")
            return JSONResponse(status_code=400, content={"status": "error", "message": "Cannot create business from incomplete data"})

    # Get the final business object to send in the update.
    final_business_obj = app_state["businesses"].get(update.business_id)
    if final_business_obj:
        # Store agent update in our list
        app_state["agent_updates"].append(update)

        # Build the JSON-safe payload using .model_dump()
        update_payload = {
            "type": "business_updated",
            "agent": update.agent_type.value,
            "business": final_business_obj.model_dump(),
            "update": update.model_dump(),
            "timestamp": datetime.now().isoformat(),
        }

        # Send the payload over the WebSocket
        await manager.send_update(update_payload)

    return JSONResponse(status_code=200, content={"status": "success", "message": "Business processed"})


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    """Serves the main page - either input form or dashboard."""
    if app_state["is_running"] or app_state["businesses"]:
        # Show dashboard if we have data or process is running
        return templates.TemplateResponse(
            name="dashboard.html",
            context={
                "request": request,  # Correct: 'request' is now inside the context
                "businesses": list(app_state["businesses"].values()),
                "current_city": app_state["current_city"],
                "is_running": app_state["is_running"],
                "agent_updates": app_state["agent_updates"][-20:],  # Last 20 updates
            }
        )
    else:
        # Show input form
        return templates.TemplateResponse(
            name="index.html",
            context={
                "request": request  # Correct: 'request' is now inside the context
            }
        )
        
        
@app.post("/start_lead_finding")
async def start_lead_finding(city: str = Form(...)):
    """Start the lead finding process for a given city."""
    if app_state["is_running"]:
        return JSONResponse(
            status_code=400,
            content={"error": "Lead finding process is already running"}
        )
    
    try:
        # Validate input
        request_data = LeadFinderRequest(city=city.strip())
        
        app_state["is_running"] = True
        app_state["current_city"] = request_data.city
        app_state["session_id"] = str(uuid.uuid4())
        app_state["businesses"] = {}  # Reset businesses for new search
        app_state["agent_updates"] = []  # Reset updates
        
        logger.info(f"Starting lead finding process for city: {request_data.city}")
        
        # Send initial update
        await manager.send_update({
            "type": "process_started",
            "city": request_data.city,
            "timestamp": datetime.now().isoformat(),
        })
        
        # Call Lead Finder agent asynchronously
        asyncio.create_task(run_lead_finding_process(request_data.city, app_state["session_id"]))
        
        return RedirectResponse("/", status_code=303)
        
    except ValidationError as e:
        logger.error(f"Invalid city input: {e}")
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid input: {e}"}
        )
    except Exception as e:
        logger.error(f"Error starting lead finding: {e}", exc_info=True)
        app_state["is_running"] = False
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to start process: {e}"}
        )


@app.get("/api/businesses")
async def get_businesses():
    """API endpoint to get all businesses."""
    return {
        "businesses": [business.dict() for business in app_state["businesses"].values()],
        "total": len(app_state["businesses"])
    }

@app.get("/api/status")
async def get_status():
    """API endpoint to get current application status."""
    return {
        "is_running": app_state["is_running"],
        "current_city": app_state["current_city"],
        "business_count": len(app_state["businesses"]),
        "session_id": app_state["session_id"],
    }

@app.post("/send_to_sdr")
async def send_business_to_sdr(business_id: str = Form(...)):
    """Send a business to the SDR agent for processing."""
    try:
        # Check if business exists
        if business_id not in app_state["businesses"]:
            return JSONResponse(
                status_code=404,
                content={"error": "Business not found"}
            )
        
        business = app_state["businesses"][business_id]
        
        # Convert business to dict for sending to SDR
        business_data = business.model_dump()
        
        # Get current session ID
        session_id = app_state["session_id"] or str(uuid.uuid4())
        
        logger.info(f"Sending business {business.name} to SDR agent")
        
        # Call SDR agent
        result = await call_sdr_agent(business_data, session_id)
        
        if result["success"]:
            # Send success update via WebSocket
            await manager.send_update({
                "type": "sdr_engaged",
                "business_id": business_id,
                "business_name": business.name,
                "message": result["message"],
                "timestamp": datetime.now().isoformat(),
            })
            
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": result["message"]}
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"error": result["error"]}
            )
            
    except Exception as e:
        logger.error(f"Error sending business to SDR: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to send to SDR: {e}"}
        )

@app.post("/reset")
async def reset_state():
    """Reset the application state."""
    app_state["is_running"] = False
    app_state["current_city"] = None
    app_state["businesses"] = {}
    app_state["agent_updates"] = []
    app_state["session_id"] = None
    
    await manager.send_update({
        "type": "state_reset",
        "timestamp": datetime.now().isoformat(),
    })
    
    return RedirectResponse("/", status_code=303)

@app.post("/trigger_lead_manager")
async def trigger_lead_manager():
    """Trigger the Lead Manager agent manually."""
    logger.info("Manual trigger for Lead Manager agent requested")
    
    try:
        # Get or create session ID
        session_id = app_state.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            app_state["session_id"] = session_id
        
        # Send initial update
        await manager.send_update({
            "type": "agent_status",
            "agent": "lead_manager",
            "status": "active",
            "message": "Lead Manager agent triggered manually",
            "timestamp": datetime.now().isoformat(),
        })
        
        # Call Lead Manager agent
        result = await call_lead_manager_agent("check_lead_emails", session_id)
        
        if result["success"]:
            logger.info(f"Lead Manager agent triggered successfully: {result['message']}")
            
            # Send success update
            await manager.send_update({
                "type": "agent_status", 
                "agent": "lead_manager",
                "status": "idle",
                "message": result["message"] or "Lead management completed successfully",
                "timestamp": datetime.now().isoformat(),
            })
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": result["message"] or "Lead Manager agent triggered successfully",
                    "timestamp": datetime.now().isoformat()
                }
            )
        else:
            logger.error(f"Lead Manager agent failed: {result['error']}")
            
            # Send error update
            await manager.send_update({
                "type": "agent_status",
                "agent": "lead_manager", 
                "status": "error",
                "message": f"Error: {result['error']}",
                "timestamp": datetime.now().isoformat(),
            })
            
            return JSONResponse(
                status_code=500,
                content={"error": result["error"]}
            )
            
    except Exception as e:
        logger.error(f"Error triggering Lead Manager agent: {e}", exc_info=True)
        
        # Send error update
        await manager.send_update({
            "type": "agent_status",
            "agent": "lead_manager",
            "status": "error", 
            "message": f"Error triggering agent: {e}",
            "timestamp": datetime.now().isoformat(),
        })
        
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to trigger Lead Manager: {e}"}
        )

@app.post("/api/human-input")
async def receive_human_input_request(request: HumanInputRequest):
    """Receive a human input request from agents."""
    logger.info(f"Received human input request: {request.request_id} - {request.type}")
    
    # Store the request
    app_state["human_input_requests"][request.request_id] = request
    
    # Send notification to all connected WebSocket clients
    await manager.send_update({
        "type": "human_input_request",
        "request_id": request.request_id,
        "prompt": request.prompt,
        "input_type": request.type,
        "timestamp": request.timestamp,
    })
    
    return {
        "status": "received",
        "request_id": request.request_id,
        "message": "Human input request received. Please check the UI for the modal dialog.",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/human-input")
async def get_pending_human_input_requests():
    """Get all pending human input requests."""
    return {
        "requests": [req.dict() for req in app_state["human_input_requests"].values()],
        "count": len(app_state["human_input_requests"])
    }

@app.post("/api/human-input/{request_id}")
async def submit_human_input_response(request_id: str, response: HumanInputResponse):
    """Submit a response to a human input request."""
    if request_id not in app_state["human_input_requests"]:
        return JSONResponse(
            status_code=404,
            content={"error": "Request not found"}
        )
    
    # Get the request first (but don't remove it yet)
    original_request = app_state["human_input_requests"].get(request_id)
    
    logger.info(f"Human input response submitted for {request_id}: {response.response}")
    
    # Try to notify the human creation tool via HTTP callback to SDR agent
    success = False
    agent_url = os.environ.get("SDR_SERVICE_URL", config.DEFAULT_SDR_URL).rstrip("/")
    callback_url = f"{agent_url}/api/human-input/{request_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            agent_resp = await client.post(
                callback_url,
                json={"url": response.response},
                headers={"Content-Type": "application/json"}
            )
            if agent_resp.status_code == 200:
                logger.info(f"Successfully notified human creation tool on agent for request {request_id}")
                success = True
            else:
                logger.warning(f"Agent returned status {agent_resp.status_code} for request {request_id}: {agent_resp.text}")
    except httpx.ConnectError:
        logger.warning(f"Connection to SDR agent failed for request {request_id}")
    except Exception as e:
        logger.error(f"Error notifying SDR agent for request {request_id}: {e}")
    
    # Only remove the request from UI state AFTER successful processing
    if success:
        app_state["human_input_requests"].pop(request_id, None)
    
    # Send WebSocket notification that response was submitted
    await manager.send_update({
        "type": "human_input_response_submitted",
        "request_id": request_id,
        "response": response.response,
        "timestamp": datetime.now().isoformat()
    })
    
    return {
        "status": "success",
        "request_id": request_id,
        "message": "Response submitted successfully",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    return {
        "status": "healthy",
        "service": "ui_client",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(manager.active_connections),
        "current_city": app_state["current_city"],
        "is_running": app_state["is_running"],
        "business_count": len(app_state["businesses"]),
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info("--- Starting FastAPI server for UI Client ---")
    logger.info("Ensure dependent A2A services are running:")
    logger.info(f"  Lead Finder: python -m lead_finder --port {config.DEFAULT_LEAD_FINDER_PORT}")
    logger.info(f"  SDR: python -m sdr --port {config.DEFAULT_SDR_PORT}")
    logger.info(f"  Lead Manager: python -m lead_manager --port {config.DEFAULT_LEAD_MANAGER_PORT}")
    logger.info(f"--- Access UI at http://0.0.0.0:{config.DEFAULT_UI_CLIENT_PORT} ---")
    
    uvicorn.run(
        "ui_client.main:app",
        host="0.0.0.0",
        port=config.DEFAULT_UI_CLIENT_PORT,
        reload=True
    )
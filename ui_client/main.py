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
    CALENDAR_ASSISTANT = "calendar_assistant"

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

# Global application state
app_state = {
    "is_running": False,
    "current_city": None,
    "businesses": {},  # dict[str, Business]
    "agent_updates": [],  # List[AgentUpdate]
    "websocket_connections": set(),  # Set[WebSocket]
    "session_id": None,
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
        
        message = json.dumps(data)
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
                        business_logger.warning("Lead results artifact not found or empty")
                        outcome["error"] = "No lead results returned"
                else:
                    business_logger.warning("No artifacts found in Lead Finder response")
                    outcome["error"] = "No artifacts in response"
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

            # --- This is the key change ---
            # Check if the returned list is empty
            if not found_businesses:
                business_logger.info(f"No businesses found for city: {city}. Notifying UI.")
                await manager.send_update({
                    "type": "lead_finding_empty",
                    "city": city,
                    "message": "Nothing found, try another city.",
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

async def run_lead_finding_process(city: str, session_id: str):
    """Run the complete lead finding process."""
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    try:
        business_logger.info(f"Starting lead finding process for {city}")
        
        # Call Lead Finder agent
        result = await call_lead_finder_agent(city, session_id)
        
        if result["success"]:
            business_logger.info(f"Lead Finder returned {len(result['businesses'])} businesses")
            # await process_lead_finder_results(result["businesses"], city)
            
            # Send completion update
            await manager.send_update({
                "type": "lead_finding_completed",
                "city": city,
                "business_count": len(result["businesses"]),
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
        app_state["is_running"] = False

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
    logger.info(f"  Calendar Assistant: python -m calendar_assistant --port {config.DEFAULT_CALENDAR_ASSISTANT_PORT}")
    logger.info(f"--- Access UI at http://0.0.0.0:{config.DEFAULT_UI_CLIENT_PORT} ---")
    
    uvicorn.run(
        "ui_client.main:app",
        host="0.0.0.0",
        port=config.DEFAULT_UI_CLIENT_PORT,
        reload=True
    )
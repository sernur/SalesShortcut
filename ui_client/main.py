from fastapi import FastAPI, WebSocket, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json
import asyncio
import os
from typing import List

app = FastAPI()

# Get the directory of this file to find templates
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(current_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/search")
async def run_search(search_query: str = Form(...)):
    print(f"Search triggered with query: {search_query}")
    
    # Send immediate feedback to UI
    user_message = {
        "sender": "ui_client",
        "content": f"Search initiated for: {search_query}",
        "type": "system_message"
    }
    await manager.send_message(json.dumps(user_message))
    
    # Trigger lead_manager agent
    try:
        import requests
        
        # Prepare payload for lead_manager agent
        payload = {
            "query": search_query,
            "ui_client_url": "http://localhost:8000"
        }
        
        # Try simple lead_manager API first, then fall back to A2A
        try:
            # Try simple API first
            response = requests.post(
                "http://localhost:8001/search",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                success_message = {
                    "sender": "ui_client",
                    "content": f"✅ Lead Manager: {result.get('message', 'Search processed successfully')}",
                    "type": "system_message"
                }
                await manager.send_message(json.dumps(success_message))
            else:
                error_message = {
                    "sender": "ui_client",
                    "content": f"❌ Lead Manager error: HTTP {response.status_code}",
                    "type": "error_message"
                }
                await manager.send_message(json.dumps(error_message))
                
        except requests.exceptions.ConnectionError:
            conn_error_message = {
                "sender": "ui_client",
                "content": "❌ Could not connect to Lead Manager service",
                "type": "error_message"
            }
            await manager.send_message(json.dumps(conn_error_message))
        except requests.exceptions.Timeout:
            timeout_message = {
                "sender": "ui_client", 
                "content": "❌ Lead Manager service timeout",
                "type": "error_message"
            }
            await manager.send_message(json.dumps(timeout_message))
        except requests.exceptions.RequestException as e:
            # Fall back to A2A format if simple API fails
            try:
                a2a_payload = {
                    "message": {
                        "parts": [
                            {
                                "root": {
                                    "data": payload
                                }
                            }
                        ]
                    }
                }
                
                response = requests.post(
                    "http://localhost:8001/tasks",
                    json=a2a_payload,
                    timeout=10
                )
                
                if response.status_code == 200:
                    a2a_success_message = {
                        "sender": "ui_client",
                        "content": "✅ Lead Manager (A2A): Task submitted successfully",
                        "type": "system_message"
                    }
                    await manager.send_message(json.dumps(a2a_success_message))
                else:
                    a2a_error_message = {
                        "sender": "ui_client",
                        "content": f"❌ Lead Manager (A2A): HTTP {response.status_code}",
                        "type": "error_message"
                    }
                    await manager.send_message(json.dumps(a2a_error_message))
                    
            except Exception as fallback_error:
                fallback_error_message = {
                    "sender": "ui_client",
                    "content": f"❌ Both simple and A2A APIs failed: {str(fallback_error)}",
                    "type": "error_message"
                }
                await manager.send_message(json.dumps(fallback_error_message))
            
    except Exception as e:
        print(f"Error triggering lead_manager: {e}")
        unexpected_error_message = {
            "sender": "ui_client",
            "content": f"❌ Unexpected error: {str(e)}",
            "type": "error_message"
        }
        await manager.send_message(json.dumps(unexpected_error_message))
    
    return {"status": "Search initiated", "query": search_query}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)

@app.post("/webhook/lead_manager")
async def lead_manager_webhook(message: dict):
    """Endpoint for lead_manager to send messages via HTTP"""
    # Format message with sender info
    formatted_message = {
        "sender": message.get("agent", "unknown"),
        "content": message.get("message", ""),
        "type": "agent_message"
    }
    await manager.send_message(json.dumps(formatted_message))
    return {"status": "Message sent"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
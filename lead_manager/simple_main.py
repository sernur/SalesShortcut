#!/usr/bin/env python3
"""Simple Lead Manager service without ADK dependencies"""

import asyncio
import requests
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import click

app = FastAPI()

class SearchRequest(BaseModel):
    query: str
    ui_client_url: str = "http://localhost:8000"

@app.get("/")
def read_root():
    return {"message": "Lead Manager service - simple version", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "lead_manager"}

@app.post("/search")
async def process_search(request: SearchRequest):
    """Process search request and send WebSocket message to UI client"""
    try:
        # Simulate processing
        await asyncio.sleep(1)
        
        # Send WebSocket message to UI client
        websocket_message = f"Hello I am Lead Manager - Processing: {request.query}"
        
        payload = {
            "message": websocket_message,
            "agent": "lead_manager_simple",
            "query": request.query
        }
        
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{request.ui_client_url}/webhook/lead_manager",
                json=payload,
                timeout=5
            )
        
        if response.status_code == 200:
            return {"status": "success", "message": "WebSocket message sent successfully"}
        else:
            return {"status": "error", "message": f"Failed to send WebSocket message: {response.status_code}"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing search: {str(e)}")

@click.command()
@click.option("--host", default="localhost", help="Host to bind the server to.")
@click.option("--port", default=8001, help="Port to bind the server to.")
def main(host: str, port: int):
    """Run the simple Lead Manager service."""
    print(f"Starting simple Lead Manager service on http://{host}:{port}/")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()
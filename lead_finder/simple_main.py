"""
Simple HTTP fallback server for Lead Finder service when ADK/A2A dependencies are not available.
"""
import logging

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

logger = logging.getLogger(__name__)
app = FastAPI()

class SearchRequest(BaseModel):
    city: str
    max_results: int = 50
    session_id: str | None = None

@app.post("/find_leads")
@app.post("/search")
@app.post("/")
async def find_leads(request: SearchRequest):
    """
    Simple fallback endpoint: returns an empty list of businesses.
    """
    logger.info(f"[Simple] Received find_leads request for city: {request.city}")
    return {"businesses": []}

def run_simple(host: str, port: int):
    """
    Starts the simple HTTP server.
    """
    logger.warning("Starting simple Lead Finder HTTP server (fallback mode)...")
    uvicorn.run(app, host=host, port=port)
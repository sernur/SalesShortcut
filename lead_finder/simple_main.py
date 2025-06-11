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
    Simple fallback endpoint: returns sample businesses for testing.
    """
    logger.info(f"[Simple] Received find_leads request for city: {request.city}")
    
    # Create sample businesses based on the requested city
    sample_businesses = [
        {
            "id": f"{request.city.lower()}_business_1",
            "name": f"Local Restaurant {request.city}",
            "phone": "+1-555-0123",
            "email": None,
            "description": f"Family-owned restaurant serving local cuisine in {request.city}",
            "city": request.city,
            "address": f"123 Main St, {request.city}",
            "website": None,
            "category": "Restaurant",
            "established": "2018"
        },
        {
            "id": f"{request.city.lower()}_business_2",
            "name": f"{request.city} Auto Repair",
            "phone": "+1-555-0456",
            "email": f"info@{request.city.lower()}auto.com",
            "description": f"Professional auto repair services in {request.city}",
            "city": request.city,
            "address": f"456 Oak Ave, {request.city}",
            "website": None,
            "category": "Automotive",
            "established": "2015"
        },
        {
            "id": f"{request.city.lower()}_business_3",
            "name": f"{request.city} Fitness Center",
            "phone": "+1-555-0789",
            "email": None,
            "description": f"Community fitness center with modern equipment in {request.city}",
            "city": request.city,
            "address": f"789 Elm St, {request.city}",
            "website": None,
            "category": "Fitness",
            "established": "2020"
        }
    ]
    
    logger.info(f"[Simple] Returning {len(sample_businesses)} sample businesses for {request.city}")
    return {"businesses": sample_businesses}

def run_simple(host: str, port: int):
    """
    Starts the simple HTTP server.
    """
    logger.warning("Starting simple Lead Finder HTTP server (fallback mode)...")
    uvicorn.run(app, host=host, port=port)
#!/usr/bin/env python3
"""Simple HTTP service for Outreach agent when ADK dependencies are not available"""

import uvicorn
from fastapi import FastAPI, Form
import logging

logger = logging.getLogger(__name__)

def run_simple(host: str, port: int):
    """Run a simple HTTP service for development/testing purposes."""
    
    app = FastAPI()
    
    @app.get("/")
    def read_root():
        return {
            "message": "Outreach service - Simple mode (ADK not available)",
            "service": "outreach",
            "mode": "simple"
        }
    
    @app.get("/health")
    def health_check():
        return {"status": "healthy", "service": "outreach", "mode": "simple"}
    
    @app.post("/mock_phone_call")
    def mock_phone_call(phone_number: str = Form(...), script: str = Form(...)):
        return {
            "status": "completed",
            "phone_number": phone_number,
            "duration": "2 minutes",
            "outcome": "Mock call completed successfully"
        }
    
    @app.post("/mock_email")
    def mock_email(to_email: str = Form(...), subject: str = Form(...), message_body: str = Form(...)):
        return {
            "status": "sent",
            "to_email": to_email,
            "subject": subject,
            "message_body": message_body,
            "message_id": f"mock_{hash(to_email)}",
            "delivery_status": "delivered"
        }
    
    logger.info(f"Starting Outreach simple service on http://{host}:{port}/")
    uvicorn.run(app, host=host, port=port)
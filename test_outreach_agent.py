#!/usr/bin/env python3
"""
Test script for the Outreach agent via A2A API.
"""
import asyncio
import json
import httpx
from typing import Dict, Any

OUTREACH_AGENT_URL = "http://127.0.0.1:8083"

async def test_phone_call_outreach():
    """Test phone call outreach functionality."""
    payload = {
        "message": {
            "parts": [
                {
                    "root": {
                        "data": {
                            "destination": "+1-555-123-4567",
                            "prompt": "You are calling on behalf of SalesShortcut and offering lead generation automation services because of their outdated manual processes. You found out that they are a small business with 5-10 employees, they struggle with lead qualification, and they currently use spreadsheets for tracking. Your main goal is to categorize this call into three categories: agreed_for_getting_email_proposal, not_interested, call_later. Return the JSON."
                        }
                    }
                }
            ]
        }
    }
    
    print("Testing phone call outreach...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(f"{OUTREACH_AGENT_URL}/tasks", json=payload)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error: {e}")
            return None

async def test_email_outreach():
    """Test email outreach functionality."""
    payload = {
        "message": {
            "parts": [
                {
                    "root": {
                        "data": {
                            "target": "john@company.com",
                            "type": "email",
                            "message": "Subject: Introduction from SalesShortcut\n\nHi John,\n\nI hope this email finds you well. I'm reaching out because I believe SalesShortcut could help streamline your sales process...",
                            "objective": "initial outreach to potential client"
                        }
                    }
                }
            ]
        }
    }
    
    print("\nTesting email outreach...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(f"{OUTREACH_AGENT_URL}/tasks", json=payload)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error: {e}")
            return None

async def test_invalid_phone_number():
    """Test phone number validation."""
    payload = {
        "message": {
            "parts": [
                {
                    "root": {
                        "data": {
                            "destination": "123",  # Invalid phone number
                            "prompt": "Test prompt for validation"
                        }
                    }
                }
            ]
        }
    }
    
    print("\nTesting invalid phone number validation...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(f"{OUTREACH_AGENT_URL}/tasks", json=payload)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error: {e}")
            return None

async def check_agent_health():
    """Check if the agent is running."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{OUTREACH_AGENT_URL}/health")
            print(f"Agent health: {response.status_code}")
            if response.status_code == 200:
                print(f"Health response: {response.json()}")
                return True
        except Exception as e:
            print(f"Agent not running: {e}")
            return False
    return False

async def main():
    """Run all tests."""
    print("=== Outreach Agent Test Suite ===\n")
    
    # Check if agent is running
    if not await check_agent_health():
        print("❌ Outreach agent is not running!")
        print("Start it with: python -m outreach")
        return
    
    print("✅ Outreach agent is running\n")
    
    # Run tests
    await test_phone_call_outreach()
    await test_email_outreach()
    await test_invalid_phone_number()
    
    print("\n=== Test Suite Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
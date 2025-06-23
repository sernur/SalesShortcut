import sys
import asyncio
from typing import Any, Dict

# Add the main project to Python path
sys.path.append('/Users/xskills/Development/Python/Hackathons/SalesShortcut')

from sdr.sdr.tools.phone_call import phone_call
from google.adk.tools import ToolContext

# Mock data for testing
business_data = {
    "business_name": "Test Business",
    "phone": "+14353173849",  # Replace with your test phone number
    "email": "test@example.com",
    "location": "Test City, UT"
}

proposal = """
# Test Proposal
This is a test proposal for website development services.
We offer comprehensive web solutions including:
- Modern responsive design
- SEO optimization
- E-commerce functionality
"""

async def test_phone_call():
    print("Testing phone_call function...")
    result = await phone_call(business_data, proposal)
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(test_phone_call())
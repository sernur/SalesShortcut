"""
Google Maps search tool implementation.
"""

from typing import Dict, Any
from google.adk.tools import FunctionTool
import requests
import json
from ..config import GOOGLE_MAPS_API_KEY

def google_maps_search(city: str) -> dict[str, Any]:
    """
    Implementation of Google Maps search for businesses in a specified city.
    
    Args:
        city: The name of the city to search in

    Returns:
        A dictionary containing search results
    """
    if not GOOGLE_MAPS_API_KEY:
        # Mock results for development or when API key is not available
        mock_results = [
            {
                "name": f"Business 1 in {city}",
                "address": f"123 Main St, {city}, State, 12345",
                "phone": "555-123-4567",
                "website": "https://www.business1.com",
                "category": "Restaurant",
                "rating": 4.5
            },
            {
                "name": f"Business 2 in {city}",
                "address": f"456 Oak Ave, {city}, State, 12345",
                "phone": "555-987-6543",
                "website": "https://www.business2.com",
                "category": "Retail",
                "rating": 4.2
            }
        ]
        return {"status": "success", "results": mock_results}
    
    # In a real implementation, use the Google Maps API
    # This is a simplified example - real implementation would need proper error handling and pagination
    try:
        endpoint = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": f"businesses in {city}",
            "key": GOOGLE_MAPS_API_KEY
        }
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for place in data.get("results", []):
            business = {
                "name": place.get("name", ""),
                "address": place.get("formatted_address", ""),
                "category": place.get("types", [""])[0] if place.get("types") else "",
                "rating": place.get("rating", 0),
                # Would need additional Place Details request for phone and website
                "phone": "",
                "website": ""
            }
            results.append(business)
        
        return {"status": "success", "results": results}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}

google_maps_search_tool = FunctionTool(func=google_maps_search)
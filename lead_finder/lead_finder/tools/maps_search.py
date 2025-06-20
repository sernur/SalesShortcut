"""
Google Maps search tool implementation.
"""

import logging
from typing import Dict, Any, List, Optional
from google.adk.tools import FunctionTool
import googlemaps
from ..config import GOOGLE_MAPS_API_KEY
from datetime import datetime

logger = logging.getLogger(__name__)

class GoogleMapsClient:
    """Google Maps API client wrapper for business searches."""
    
    def __init__(self):
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Google Maps client."""
        if not GOOGLE_MAPS_API_KEY:
            logger.warning("Google Maps API key not found. Using mock data.")
            raise ValueError("Google Maps API key is required for Google Maps client initialization.")
            return
        
        try:
            self.client = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
            logger.info("Successfully initialized Google Maps client")
        except Exception as e:
            logger.error(f"Failed to initialize Google Maps client: {e}")
            self.client = None
    
    def _get_place_details(self, place_id: str) -> Dict[str, Any]:
        """Get detailed information for a place."""
        if not self.client or not place_id:
            return {}
        
        try:
            result = self.client.place(place_id=place_id)
            return result.get('result', {})
        except Exception as e:
            logger.error(f"Error getting place details for {place_id}: {e}")
            return {}
    
    def _get_primary_category(self, types: List[str]) -> str:
        """Get the primary business category from place types."""
        if not types:
            return ""
        
        # Prioritize business-related types
        business_types = [
            "restaurant", "cafe", "bar", "store", "shop", "retail",
            "service", "business", "establishment"
        ]
        
        for type_ in types:
            if any(bt in type_.lower() for bt in business_types):
                return type_
        
        return types[0] if types else ""
    
    def _get_open_status(self, hours: Dict[str, Any]) -> bool:
        """Get the current open status of a business."""
        return hours.get('open_now', False) if hours else False
    
    def _get_mock_results(self, city: str, business_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate mock results for testing."""
        mock_businesses = [
            {
                "place_id": f"mock_{city.lower()}_1",
                "name": f"Mock Business 1 - {city}",
                "address": f"123 Main St, {city}",
                "phone": "555-0123",
                "website": "",  # No website
                "rating": 4.5,
                "total_ratings": 100,
                "category": business_type or "General Business",
                "price_level": 2,
                "is_open": True,
                "location": {"lat": 40.7128, "lng": -74.0060}
            },
            {
                "place_id": f"mock_{city.lower()}_2",
                "name": f"Mock Business 2 - {city}",
                "address": f"456 Oak Ave, {city}",
                "phone": "555-0456",
                "website": "",  # No website
                "rating": 4.0,
                "total_ratings": 75,
                "category": business_type or "General Business",
                "price_level": 1,
                "is_open": True,
                "location": {"lat": 40.7589, "lng": -73.9851}
            }
        ]
        return mock_businesses
    
    def search_businesses(
        self, 
        city: str, 
        business_type: Optional[str] = None,
        radius: int = 25000,  # 25km radius
        min_rating: float = 0.0,
        max_results: int = 100,
        exclude_websites: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for businesses in a specified city.
        
        Args:
            city: The name of the city to search in
            business_type: Optional business type filter
            radius: Search radius in meters (default: 25km)
            min_rating: Minimum rating filter (default: 0.0)
            max_results: Maximum number of results (default: 100)
            exclude_websites: If True, only return businesses without websites
            
        Returns:
            List of business information dictionaries
        """
        if not self.client:
            logger.info("Using mock data for business search")
            return self._get_mock_results(city, business_type)
        
        try:
            # First, get the city's location
            geocode_result = self.client.geocode(city)
            if not geocode_result:
                logger.error(f"Could not find location for city: {city}")
                return self._get_mock_results(city, business_type)
            
            location = geocode_result[0]['geometry']['location']
            logger.info(f"Found location for {city}: {location}")
            
            # Build search query
            if business_type:
                query = f"{business_type} businesses in {city}"
            else:
                query = f"businesses in {city}"
            
            logger.info(f"Searching for: {query}")
            
            # Perform nearby search
            places_result = self.client.places_nearby(
                location=location,
                radius=radius,
                type=business_type if business_type else None
            )
            
            businesses = []
            results = places_result.get('results', [])
            logger.info(f"Found {len(results)} initial results")
            
            for place in results:
                # Get detailed information
                place_details = self._get_place_details(place.get('place_id', ''))
                
                # Skip if no details found
                if not place_details:
                    continue
                
                # Filter by rating if specified
                rating = place_details.get('rating', place.get('rating', 0))
                if rating < min_rating:
                    continue
                
                # Skip businesses with websites if exclude_websites is True
                if exclude_websites and place_details.get('website'):
                    logger.debug(f"Skipping business with website: {place_details.get('name')}")
                    continue
                
                # Extract business information
                business = {
                    "place_id": place.get('place_id', ''),
                    "name": place_details.get('name', place.get('name', '')),
                    "address": place_details.get('formatted_address', place.get('formatted_address', '')),
                    "phone": place_details.get('formatted_phone_number', ''),
                    "website": place_details.get('website', ''),
                    "rating": rating,
                    "total_ratings": place_details.get('user_ratings_total', 0),
                    "category": self._get_primary_category(place_details.get('types', place.get('types', []))),
                    "price_level": place_details.get('price_level', 0),
                    "is_open": self._get_open_status(place_details.get('opening_hours', {})),
                    "location": {
                        "lat": place.get('geometry', {}).get('location', {}).get('lat'),
                        "lng": place.get('geometry', {}).get('location', {}).get('lng')
                    }
                }
                
                # Only add businesses with valid information
                if business["name"] and business["address"]:
                    businesses.append(business)
                    logger.debug(f"Added business: {business['name']}")
                
                # Stop if we've reached max_results
                if len(businesses) >= max_results:
                    logger.info(f"Reached max results limit ({max_results})")
                    break
            
            logger.info(f"Found {len(businesses)} valid businesses in {city}")
            return businesses
            
        except Exception as e:
            logger.error(f"Error searching businesses in {city}: {e}")
            return self._get_mock_results(city, business_type)

# Global client instance
_maps_client = GoogleMapsClient()

def google_maps_search(
    city: str, 
    business_type: Optional[str] = None,
    min_rating: float = 0.0,  # Changed to 0.0 to get all businesses
    max_results: int = 100,  # Increased to 100
    exclude_websites: bool = True  # Add parameter to filter websites
) -> Dict[str, Any]:
    """
    Enhanced Google Maps search for businesses in a specified city.
    
    Args:
        city: The name of the city to search in
        business_type: Optional business type filter
        min_rating: Minimum rating filter (default: 0.0)
        max_results: Maximum number of results (default: 100)
        exclude_websites: If True, only return businesses without websites (default: True)

    Returns:
        A dictionary containing search results and metadata
    """
    try:
        client = GoogleMapsClient()
        
        # Search for businesses
        businesses = client.search_businesses(
            city=city,
            business_type=business_type,
            min_rating=min_rating,
            max_results=max_results,
            exclude_websites=exclude_websites
        )
        
        # Filter out businesses with websites if requested
        if exclude_websites:
            businesses = [b for b in businesses if not b.get('website')]
        
        return {
            "status": "success",
            "total_results": len(businesses),
            "results": businesses,
            "search_metadata": {
                "city": city,
                "business_type": business_type,
                "min_rating": min_rating,
                "max_results": max_results,
                "api_available": client.client is not None,
                "exclude_websites": exclude_websites
            }
        }
        
    except Exception as e:
        logger.error(f"Error in google_maps_search: {e}")
        return {
            "status": "error",
            "message": str(e),
            "total_results": 0,
            "results": [],
            "search_metadata": {
                "city": city,
                "business_type": business_type,
                "min_rating": min_rating,
                "max_results": max_results,
                "api_available": False,
                "exclude_websites": exclude_websites
            }
        }

# Enhanced function tool with support for multiple search types
def google_maps_nearby_search(city: str, business_type: str = "restaurant") -> Dict[str, Any]:
    """Search for specific business types nearby."""
    return google_maps_search(city, business_type=business_type)

def google_maps_high_rated_search(city: str, min_rating: float = 4.0) -> Dict[str, Any]:
    """Search for highly-rated businesses."""
    return google_maps_search(city, min_rating=min_rating)

# Create function tools
google_maps_search_tool = FunctionTool(func=google_maps_search)
google_maps_nearby_search_tool = FunctionTool(func=google_maps_nearby_search)
google_maps_high_rated_search_tool = FunctionTool(func=google_maps_high_rated_search)
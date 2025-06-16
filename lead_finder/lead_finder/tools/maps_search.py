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
            return
        
        try:
            self.client = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
            logger.info("Google Maps client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Maps client: {e}")
            self.client = None

    def _get_place_details(self, place_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific place."""
        if not self.client:
            return {}
        
        try:
            # Request specific fields for business information
            fields = [
                'name', 'formatted_address', 'formatted_phone_number',
                'website', 'rating', 'user_ratings_total', 'type',
                'opening_hours', 'price_level', 'geometry'
            ]
            
            details = self.client.place(place_id=place_id, fields=fields)
            return details.get('result', {})
        except Exception as e:
            logger.error(f"Error getting place details for {place_id}: {e}")
            return {}

    def search_businesses(
        self, 
        city: str, 
        business_type: Optional[str] = None,
        radius: int = 10000,
        min_rating: float = 3.0,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for businesses in a specified city with filtering options.
        
        Args:
            city: The name of the city to search in
            business_type: Optional business type filter (e.g., 'restaurant', 'retail')
            radius: Search radius in meters (default: 10km)
            min_rating: Minimum rating filter (default: 3.0)
            max_results: Maximum number of results to return (default: 20)
            
        Returns:
            List of business information dictionaries
        """
        if not self.client:
            return self._get_mock_results(city, business_type)
        
        try:
            # Build search query
            if business_type:
                query = f"{business_type} businesses in {city}"
            else:
                query = f"businesses in {city}"
            
            logger.info(f"Searching for: {query}")
            
            # Perform text search
            places_result = self.client.places(
                query=query,
                location=None,  # Let Google determine the location from city name
                radius=radius
            )
            
            businesses = []
            for place in places_result.get('results', [])[:max_results]:
                # Get detailed information
                place_details = self._get_place_details(place.get('place_id', ''))
                
                # Filter by rating if specified
                rating = place_details.get('rating', place.get('rating', 0))
                if rating < min_rating:
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
                    "category": self._get_primary_category(place_details.get('type', place.get('types', []))),
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
            
            logger.info(f"Found {len(businesses)} businesses in {city}")
            return businesses
            
        except Exception as e:
            logger.error(f"Error searching businesses in {city}: {e}")
            return self._get_mock_results(city, business_type)

    def _get_primary_category(self, types: List[str]) -> str:
        """Extract the primary business category from Google Places types."""
        if not types:
            return "Business"
        
        # Priority mapping for business-relevant types
        priority_types = {
            'restaurant': 'Restaurant',
            'food': 'Food & Beverage',
            'store': 'Retail Store',
            'shopping_mall': 'Shopping Mall',
            'clothing_store': 'Clothing Store',
            'electronics_store': 'Electronics Store',
            'furniture_store': 'Furniture Store',
            'hardware_store': 'Hardware Store',
            'supermarket': 'Supermarket',
            'pharmacy': 'Pharmacy',
            'bank': 'Bank',
            'real_estate_agency': 'Real Estate',
            'lawyer': 'Legal Services',
            'doctor': 'Healthcare',
            'dentist': 'Healthcare',
            'veterinary_care': 'Veterinary',
            'beauty_salon': 'Beauty & Wellness',
            'gym': 'Fitness',
            'car_dealer': 'Automotive',
            'car_repair': 'Automotive Services',
            'gas_station': 'Gas Station',
            'lodging': 'Hospitality',
            'travel_agency': 'Travel Services'
        }
        
        # Find the first matching priority type
        for place_type in types:
            if place_type in priority_types:
                return priority_types[place_type]
        
        # Return the first type if no priority match
        return types[0].replace('_', ' ').title() if types else 'Business'

    def _get_open_status(self, opening_hours: Dict[str, Any]) -> Optional[bool]:
        """Extract current open status from opening hours info."""
        return opening_hours.get('open_now') if opening_hours else None

    def _get_mock_results(self, city: str, business_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fallback mock results when API is not available."""
        logger.info(f"Using mock data for {city} (API not available)")
        
        category = business_type.title() if business_type else "Business"
        
        return [
            {
                "place_id": f"mock_id_1_{city}",
                "name": f"Premium {category} in {city}",
                "address": f"123 Main St, {city}, State, 12345",
                "phone": "555-123-4567",
                "website": "https://www.example1.com",
                "category": category,
                "rating": 4.5,
                "total_ratings": 150,
                "price_level": 2,
                "is_open": True,
                "location": {"lat": 40.7128, "lng": -74.0060}
            },
            {
                "place_id": f"mock_id_2_{city}",
                "name": f"Quality {category} Services in {city}",
                "address": f"456 Oak Ave, {city}, State, 12345",
                "phone": "555-987-6543",
                "website": "https://www.example2.com",
                "category": category,
                "rating": 4.2,
                "total_ratings": 89,
                "price_level": 1,
                "is_open": False,
                "location": {"lat": 40.7589, "lng": -73.9851}
            }
        ]

# Global client instance
_maps_client = GoogleMapsClient()

def google_maps_search(
    city: str, 
    business_type: Optional[str] = None,
    min_rating: float = 3.0,
    max_results: int = 20
) -> Dict[str, Any]:
    """
    Enhanced Google Maps search for businesses in a specified city.
    
    Args:
        city: The name of the city to search in
        business_type: Optional business type filter
        min_rating: Minimum rating filter (default: 3.0)
        max_results: Maximum number of results (default: 20)

    Returns:
        A dictionary containing search results and metadata
    """
    try:
        logger.info(f"Starting business search for city: {city}, type: {business_type}")
        
        businesses = _maps_client.search_businesses(
            city=city,
            business_type=business_type,
            min_rating=min_rating,
            max_results=max_results
        )
        
        return {
            "status": "success",
            "city": city,
            "business_type": business_type,
            "total_results": len(businesses),
            "min_rating_filter": min_rating,
            "results": businesses,
            "search_metadata": {
                "api_available": _maps_client.client is not None,
                "search_radius_km": 10,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error in google_maps_search: {e}")
        return {
            "status": "error",
            "message": str(e),
            "city": city,
            "business_type": business_type,
            "results": []
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
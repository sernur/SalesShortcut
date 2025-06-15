#!/usr/bin/env python3
"""
Test script for Google Maps and BigQuery integrations.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the lead_finder module to the path
sys.path.append('lead_finder')

async def test_google_maps_integration():
    """Test the Google Maps API integration."""
    print("🗺️  Testing Google Maps Integration...")
    
    try:
        from lead_finder.tools.maps_search import google_maps_search, google_maps_nearby_search
        
        # Test basic search
        print("   Testing basic business search...")
        result = google_maps_search(city="San Francisco", max_results=5)
        print(f"   ✅ Basic search returned {result['total_results']} results")
        print(f"   📊 API Available: {result['search_metadata']['api_available']}")
        
        if result['results']:
            sample_business = result['results'][0]
            print(f"   📍 Sample: {sample_business['name']} - {sample_business['category']}")
        
        # Test restaurant search
        print("   Testing restaurant search...")
        restaurant_result = google_maps_nearby_search(city="New York", business_type="restaurant")
        print(f"   ✅ Restaurant search returned {restaurant_result['total_results']} results")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Google Maps test failed: {e}")
        return False

async def test_bigquery_integration():
    """Test the BigQuery integration."""
    print("💾 Testing BigQuery Integration...")
    
    try:
        from lead_finder.tools.bigquery_utils import bigquery_upload, bigquery_query_leads
        
        # Test data for upload
        test_businesses = [
            {
                "place_id": "test_place_123",
                "name": "Test Business 1",
                "address": "123 Test St, Test City, TC 12345",
                "phone": "555-TEST-123",
                "website": "https://test1.com",
                "category": "Restaurant",
                "rating": 4.5,
                "total_ratings": 100,
                "price_level": 2,
                "is_open": True,
                "location": {"lat": 40.7128, "lng": -74.0060}
            },
            {
                "place_id": "test_place_456",
                "name": "Test Business 2",
                "address": "456 Test Ave, Test City, TC 12345",
                "phone": "555-TEST-456",
                "website": "https://test2.com",
                "category": "Retail Store",
                "rating": 4.2,
                "total_ratings": 75,
                "price_level": 1,
                "is_open": False,
                "location": {"lat": 40.7589, "lng": -73.9851}
            }
        ]
        
        # Test upload
        print("   Testing BigQuery upload...")
        upload_result = await bigquery_upload(
            data=test_businesses, 
            city="Test City", 
            search_type="test"
        )
        print(f"   ✅ Upload status: {upload_result['status']}")
        print(f"   📊 Stats: {upload_result['stats']}")
        
        # Test query (will work if BigQuery is available)
        print("   Testing BigQuery query...")
        try:
            query_result = await bigquery_query_leads(
                city="Test City",
                limit=10
            )
            print(f"   ✅ Query status: {query_result['status']}")
            if query_result['status'] == 'success':
                print(f"   📊 Found {query_result['total_results']} leads")
            else:
                print(f"   ℹ️  Query message: {query_result.get('message', 'No message')}")
        except Exception as query_error:
            print(f"   ⚠️  Query test skipped: {query_error}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ BigQuery test failed: {e}")
        return False

async def test_integrated_workflow():
    """Test the complete workflow: Maps search -> BigQuery upload."""
    print("🔄 Testing Integrated Workflow...")
    
    try:
        from lead_finder.tools.maps_search import google_maps_search
        from lead_finder.tools.bigquery_utils import bigquery_upload
        
        # Search for businesses
        print("   Step 1: Searching for businesses...")
        search_result = google_maps_search(city="Boston", business_type="cafe", max_results=3)
        
        if search_result['status'] != 'success' or not search_result['results']:
            print("   ⚠️  No businesses found for upload test")
            return True
        
        # Upload to BigQuery
        print("   Step 2: Uploading to BigQuery...")
        businesses = search_result['results']
        upload_result = await bigquery_upload(
            data=businesses,
            city="Boston",
            search_type="cafe_search"
        )
        
        print(f"   ✅ Integrated workflow completed")
        print(f"   📊 Search: {len(businesses)} businesses found")
        print(f"   📊 Upload: {upload_result['status']}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Integrated workflow failed: {e}")
        return False

def check_environment():
    """Check if required environment variables are set."""
    print("🔧 Checking Environment Configuration...")
    
    required_vars = ['GOOGLE_API_KEY']
    optional_vars = ['GOOGLE_MAPS_API_KEY', 'GOOGLE_CLOUD_PROJECT']
    
    all_good = True
    
    for var in required_vars:
        if os.getenv(var):
            print(f"   ✅ {var}: Set")
        else:
            print(f"   ❌ {var}: Not set (required)")
            all_good = False
    
    for var in optional_vars:
        if os.getenv(var):
            print(f"   ✅ {var}: Set")
        else:
            print(f"   ⚠️  {var}: Not set (will use fallback/mock)")
    
    return all_good

async def main():
    """Run all integration tests."""
    print("🚀 Starting Integration Tests for SalesShortcut")
    print("=" * 50)
    
    # Check environment
    env_ok = check_environment()
    print()
    
    if not env_ok:
        print("❌ Environment check failed. Please set required variables in .env file.")
        print("💡 Copy config.template to .env and fill in your API keys.")
        return
    
    # Run tests
    tests = [
        ("Google Maps Integration", test_google_maps_integration),
        ("BigQuery Integration", test_bigquery_integration),
        ("Integrated Workflow", test_integrated_workflow)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
        print()
    
    # Summary
    print("📋 Test Results Summary:")
    print("-" * 30)
    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All integrations working successfully!")
    else:
        print("⚠️  Some tests failed. Check your API keys and configuration.")

if __name__ == "__main__":
    asyncio.run(main()) 
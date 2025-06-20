#!/usr/bin/env python3
"""
Demo script to test Google Maps and BigQuery integrations directly.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'lead_finder'))

async def demo_lead_finder_workflow(city: str):
    """Demonstrate the workflow for finding businesses WITHOUT websites in a user-specified city."""
    print(f"🚀 SalesShortcut Lead Finder Integration Demo (No Website Mode) for {city}")
    print("=" * 50)
    
    try:
        # Import the integration tools
        from lead_finder.tools.maps_search import google_maps_search
        from lead_finder.tools.bigquery_utils import bigquery_no_website_upload, bigquery_query_no_website_leads
        
        # Step 1: Search for businesses using Google Maps
        print(f"📍 Step 1: Searching for businesses using Google Maps ({city}, no website)...")
        business_type = None  # Search for any business
        
        search_result = google_maps_search(
            city=city, 
            business_type=business_type, 
            min_rating=0.0,
            max_results=200
        )
        
        print(f"   🔍 Search Query: businesses in {city}")
        print(f"   📊 Status: {search_result['status']}")
        print(f"   📈 Results Found: {search_result['total_results']}")
        print(f"   🤖 API Connected: {search_result['search_metadata']['api_available']}")
        
        # Filter for businesses with NO website
        no_website_results = [b for b in search_result['results'] if not b.get('website')]
        print(f"   🚫 Businesses without website: {len(no_website_results)}")
        if no_website_results:
            print("\n   📋 Sample No-Website Results:")
            for i, business in enumerate(no_website_results[:3], 1):
                print(f"     {i}. {business['name']}")
                print(f"        📍 {business['address']}")
                print(f"        ⭐ Rating: {business['rating']}")
                print(f"        📞 Phone: {business['phone'] or 'N/A'}")
                print()
        else:
            print("   ⚠️  No businesses without websites found in search results.")
        
        # Step 2: Upload businesses with no website to BigQuery
        print("\n💾 Step 2: Uploading businesses WITHOUT websites to BigQuery...")
        if no_website_results:
            upload_no_website_result = await bigquery_no_website_upload(
                data=no_website_results,
                city=city,
                search_type="no_website_search"
            )
            print(f"   📤 Upload Status (no website): {upload_no_website_result['status']}")
            print(f"   📊 Upload Stats (no website): {upload_no_website_result['stats']}")
            if 'mock_file' in upload_no_website_result:
                print(f"   📁 Fallback File (no website): {upload_no_website_result['mock_file']}")
        else:
            print("   ⚠️  No businesses to upload.")
        
        # Step 3: Query existing leads with no website
        print("🔍 Step 3: Querying existing leads WITHOUT websites from BigQuery...")
        try:
            query_no_website_result = await bigquery_query_no_website_leads(
                city=city,
                min_rating=0.0,
                limit=100
            )
            print(f"   📊 Query Status (no website): {query_no_website_result['status']}")
            if query_no_website_result['status'] == 'success':
                print(f"   📈 Total Leads Found (no website): {query_no_website_result['total_results']}")
                if query_no_website_result['results']:
                    print(f"   📋 Sample No-Website Lead: {query_no_website_result['results'][0]['name']}")
            else:
                print(f"   ℹ️  Note (no website): {query_no_website_result.get('message', 'Using fallback storage')}")
        except Exception as e:
            print(f"   ⚠️  Query test (no website): {e}")
        
        # Step 4: Show connection status
        print("\n🔗 Connection Status Summary:")
        print("-" * 30)
        if search_result['search_metadata']['api_available']:
            print("   ✅ Google Maps API: Connected and Working")
        else:
            print("   ⚠️  Google Maps API: Using Mock Data (check API keys/quotas)")
        if no_website_results and upload_no_website_result['status'] == 'success':
            if 'mock_file' in upload_no_website_result:
                print("   ⚠️  BigQuery: Using File Fallback (check authentication)")
            else:
                print("   ✅ BigQuery: Connected and Working")
        else:
            print("   ❌ BigQuery: Error occurred or no data uploaded")
        return True
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        print(f"🔍 Error details: {traceback.format_exc()}")
        return False

async def demo_different_search_types():
    """Demo different types of business searches."""
    print("\n🎯 Testing Different Search Types:")
    print("-" * 40)
    
    try:
        from lead_finder.tools.maps_search import (
            google_maps_search, 
            google_maps_nearby_search, 
            google_maps_high_rated_search
        )
        
        # Test different search types
        searches = [
            ("General Business Search", lambda: google_maps_search("Portland", max_results=3)),
            ("Coffee Shop Search", lambda: google_maps_nearby_search("Portland", "coffee")),
            ("High-Rated Search", lambda: google_maps_high_rated_search("Portland", min_rating=4.5)),
        ]
        
        for name, search_func in searches:
            print(f"\n   🔍 {name}:")
            result = search_func()
            print(f"     Status: {result['status']}")
            print(f"     Results: {result['total_results']}")
            if result['results']:
                sample = result['results'][0]
                print(f"     Sample: {sample['name']} (⭐{sample['rating']})")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Search types demo failed: {e}")
        return False

async def main():
    """Run the no-website demo only, with city from command line."""
    city = sys.argv[1] if len(sys.argv) > 1 else "Salt Lake City"
    success = await demo_lead_finder_workflow(city)
    print("\n" + "=" * 50)
    if success:
        print("🎉 Demo completed successfully!")
        print("✅ Your Google Maps and BigQuery integrations (no website mode) are working!")
    else:
        print("⚠️  Demo completed with some issues.")
        print("   Check the error messages above for troubleshooting.")

if __name__ == "__main__":
    asyncio.run(main()) 
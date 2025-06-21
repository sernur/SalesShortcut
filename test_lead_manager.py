#!/usr/bin/env python3
"""
Test script for Lead Manager Agent.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'lead_manager'))

async def test_email_checker_tool():
    """Test the email checking functionality."""
    print("📧 Testing Email Checker Tool...")
    
    try:
        from lead_manager.lead_manager.tools.check_email import check_unread_emails
        
        print("   Checking unread emails...")
        result = await check_unread_emails()
        
        print(f"   ✅ Email check status: {result['success']}")
        print(f"   📊 Found {result['count']} unread emails")
        
        if result['emails']:
            sample_email = result['emails'][0]
            print(f"   📨 Sample: {sample_email['sender_email']} - {sample_email['subject']}")
        
        return result['success']
        
    except Exception as e:
        print(f"   ❌ Email checker test failed: {e}")
        import traceback
        print(f"   🔍 Detailed error: {traceback.format_exc()}")
        return False

async def test_bigquery_hot_leads():
    """Test the BigQuery hot leads checking."""
    print("💾 Testing BigQuery Hot Leads Check...")
    
    try:
        from lead_manager.lead_manager.tools.bigquery_utils import check_hot_lead
        
        # Test with a sample email
        test_email = "test@example.com"
        print(f"   Checking if {test_email} is a hot lead...")
        
        result = await check_hot_lead(test_email)
        
        print(f"   ✅ Hot lead check status: {result['success']}")
        print(f"   📊 Is hot lead: {result['is_hot_lead']}")
        
        if result['is_hot_lead']:
            print(f"   🔥 Hot lead data found: {result['lead_data']}")
        else:
            print(f"   📋 {test_email} is not in hot leads database")
        
        return result['success']
        
    except Exception as e:
        print(f"   ❌ BigQuery test failed: {e}")
        import traceback
        print(f"   🔍 Detailed error: {traceback.format_exc()}")
        return False

async def test_calendar_availability():
    """Test the calendar availability checking."""
    print("📅 Testing Calendar Availability...")
    
    try:
        from lead_manager.lead_manager.tools.calendar_utils import check_calendar_availability
        
        print("   Checking calendar availability...")
        result = await check_calendar_availability(days_ahead=3)
        
        print(f"   ✅ Calendar check status: {result['success']}")
        
        if result['success']:
            print(f"   📊 Available slots: {result['total_available_slots']}")
            print(f"   🌍 Timezone: {result['timezone']}")
            
            if result['available_slots']:
                sample_slot = result['available_slots'][0]
                print(f"   🕐 Next available: {sample_slot['date']} at {sample_slot['time']}")
        
        return result['success']
        
    except Exception as e:
        print(f"   ❌ Calendar test failed: {e}")
        import traceback
        print(f"   🔍 Detailed error: {traceback.format_exc()}")
        return False

async def test_lead_manager_agent():
    """Test the complete Lead Manager Agent."""
    print("🤖 Testing Lead Manager Agent...")
    
    try:
        from google.adk import Runner
        from google.adk.sessions import InMemorySessionService
        from google.adk.artifacts import InMemoryArtifactService
        from google.adk.memory import InMemoryMemoryService
        from google.genai import types as genai_types
        
        from lead_manager.lead_manager.agent import root_agent
        
        # Create runner
        runner = Runner(
            app_name="test_lead_manager",
            agent=root_agent,
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
            artifact_service=InMemoryArtifactService(),
        )
        
        # Prepare test input
        test_input = {
            "operation": "check_lead_emails",
            "ui_client_url": "http://localhost:8000"
        }
        
        content = genai_types.Content(
            parts=[genai_types.Part(text=json.dumps(test_input))]
        )
        
        print("   Running Lead Manager Agent...")
        
        # Run the agent
        session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session_id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        print(f"   📝 Agent: {part.text}")
        
        print("   ✅ Lead Manager Agent test completed")
        return True
        
    except Exception as e:
        print(f"   ❌ Lead Manager Agent test failed: {e}")
        import traceback
        print(f"   🔍 Detailed error: {traceback.format_exc()}")
        return False

def check_environment():
    """Check if required environment variables are set."""
    print("🔧 Checking Environment Configuration...")
    
    required_vars = [
        'SERVICE_ACCOUNT_FILE',
        'SALES_EMAIL',
        'GOOGLE_CLOUD_PROJECT'
    ]
    
    optional_vars = [
        'DATASET_ID',
        'TABLE_ID',
        'MEETING_TABLE_ID'
    ]
    
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
            print(f"   ⚠️  {var}: Not set (will use default)")
    
    # Check service account file exists
    service_account_file = os.getenv('SERVICE_ACCOUNT_FILE')
    if service_account_file and Path(service_account_file).exists():
        print(f"   ✅ Service account file: Found")
    else:
        print(f"   ❌ Service account file: Not found at {service_account_file}")
        all_good = False
    
    return all_good

def check_file_structure():
    """Check if the required files exist."""
    print("📁 Checking File Structure...")
    
    required_files = [
        'lead_manager/lead_manager/agent.py',
        'lead_manager/lead_manager/tools/check_email.py',
        'lead_manager/lead_manager/tools/bigquery_utils.py',
        'lead_manager/lead_manager/tools/calendar_utils.py',
        'lead_manager/lead_manager/sub_agents/email_checker_agent.py',
        'lead_manager/lead_manager/sub_agents/email_analyzer.py',
        'lead_manager/lead_manager/config.py'
    ]
    
    all_good = True
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"   ✅ {file_path}: Found")
        else:
            print(f"   ❌ {file_path}: Missing")
            all_good = False
    
    return all_good

def generate_curl_test():
    """Generate curl command to test the agent."""
    print("🌐 Generated curl test command:")
    print()
    
    curl_command = '''curl -X POST http://localhost:8080/api/tasks \\
  -H "Content-Type: application/json" \\
  -d '{
    "agent_type": "lead_manager",
    "data": {
      "operation": "check_lead_emails",
      "ui_client_url": "http://localhost:8000"
    }
  }'
'''
    
    print(curl_command)
    print()
    print("🔧 Make sure the A2A server is running on port 8080")
    print("🔧 Make sure the UI client is running on port 8000")

async def main():
    """Run all tests for Lead Manager."""
    print("🚀 Starting Lead Manager Tests")
    print("=" * 50)
    
    # Check file structure first
    file_ok = check_file_structure()
    print()
    
    if not file_ok:
        print("❌ File structure check failed. Some required files are missing.")
        return
    
    # Check environment
    env_ok = check_environment()
    print()
    
    if not env_ok:
        print("❌ Environment check failed. Please set required variables in .env file.")
        print("💡 Required: SERVICE_ACCOUNT_FILE, SALES_EMAIL, GOOGLE_CLOUD_PROJECT")
        return
    
    # Run component tests
    tests = [
        ("Email Checker Tool", test_email_checker_tool),
        ("BigQuery Hot Leads", test_bigquery_hot_leads),
        ("Calendar Availability", test_calendar_availability),
        ("Lead Manager Agent", test_lead_manager_agent)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            import traceback
            print(f"🔍 Detailed error: {traceback.format_exc()}")
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
        print("🎉 All Lead Manager components working successfully!")
    elif passed > 0:
        print("⚠️  Some tests passed, some failed. Check the details above.")
    else:
        print("❌ All tests failed. Check your configuration and credentials.")
    
    print()
    generate_curl_test()

if __name__ == "__main__":
    asyncio.run(main())
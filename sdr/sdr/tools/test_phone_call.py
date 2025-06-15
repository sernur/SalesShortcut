#!/usr/bin/env python3
"""
Standalone test script for ElevenLabs phone calling functionality.
Run this script to test real phone calls without the full agent workflow.
"""

import os
import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from ..config import ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, ELEVENLABS_PHONE_NUMBER_ID
from ..prompts import CALLER_PROMPT

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION - EDIT THESE VALUES FOR YOUR TEST
# ============================================================================

TEST_PHONE_NUMBER = "+4353173849"  

# Custom system prompt for the test call
TEST_SYSTEM_PROMPT = CALLER_PROMPT.format(
    business_data= """{
      "created_at": "2025-06-15T10:37:13.223516",
      "email": null,
      "city": "Logan",
      "notes": [
        "AgentType.LEAD_FINDER: Successfully discovered business: The Sportsman in Logan"
      ],
      "id": "generated_-5254716622828483295",
      "description": null,
      "phone": "435-317-3849",
      "status": "found",
      "updated_at": "2025-06-15T10:37:13.223519",
      "name": "The Sportsman in Logan"
    }""",
    proposal = "Subject: Proposal for a Powerful Website Redesign for The Sportsman in Logan\n\nDear [Name of Decision-Maker at The Sportsman in Logan, if known, otherwise: Owner/Manager],\n\nWe understand that The Sportsman in Logan has been a trusted provider of quality sporting goods and services in Cache Valley since 1947. Your commitment to excellent customer service, high-quality products, and expert advice has built a strong reputation. We recognize the value of your long-standing history and family-owned business.\n\nOur research indicates that while you have a website ([https://www.thesportsmanltd.com/](https://www.thesportsmanltd.com/)), there's a significant opportunity to enhance your online presence to better serve your loyal customers and reach new ones.\n\n**Here's what we've found, and how we can help:**\n\n**Current Situation:**\n\n*   **Strong Local Reputation:** The Sportsman is known for outstanding customer service, knowledgeable staff, and a great selection of sporting goods, including clothing, shoes, skis, bikes, and camping supplies. You also offer unique products, rentals, and services like ski and snowboard tuning.\n*   **Online Presence Gap:** Your current website could be significantly improved to enhance your brand and reach more customers. It appears you are on Shopify.\n*   **Competition:** You face competition from larger retailers and online stores. Customers are looking for an easy way to buy online, and access to information 24/7.\n\n**How a New Website Can Help:**\n\nWe propose a redesigned website to address these challenges and unlock new opportunities:\n\n*   **Increase Visibility:** We'll implement SEO best practices to improve your search engine ranking, attracting more local customers searching for sporting goods and services.\n*   **Enhance Customer Experience:** Your customers can easily browse products, access rental information, and learn about your services 24/7, leading to greater satisfaction.\n*   **Drive Online Sales:** An e-commerce platform will allow you to sell your products online, expanding your reach and revenue potential, solving your customer's desire to buy products easily.\n*   **Showcase Expertise:** Highlight your staff's expertise and knowledge, especially your ski and snowboard tuning services, fostering customer trust and loyalty.\n*   **Build Brand Loyalty:** Share your story, history, and values to connect with your customers on a deeper level.\n\n**Our Services and Solutions:**\n\nWe offer comprehensive website development services, including:\n\n*   **Modern, User-Friendly Design:** A website tailored to your brand, showcasing your products and services in an engaging way.\n*   **E-commerce Functionality:** Enabling online sales and easy management of your product catalog.\n*   **SEO Optimization:** Ensuring your website ranks high in search results, driving organic traffic.\n*   **Mobile Responsiveness:** Ensuring your website looks and functions flawlessly on all devices.\n*   **Ongoing Support and Maintenance:** Providing continuous support to keep your website up-to-date.\n\n**Benefits You Can Expect:**\n\n*   **Increased Revenue:** Through online sales and increased store traffic.\n*   **Improved Customer Engagement:** With a user-friendly website and online communication tools.\n*   **Enhanced Brand Image:** Reflecting your company's quality and expertise.\n*   **Competitive Advantage:** Differentiating yourself from competitors with a professional online presence.\n*   **Address customer pain points:** Provide customers with the ability to buy products online, anytime.\n\n**Next Steps:**\n\nWe are confident that a new website will be a valuable investment for The Sportsman. We'd like to offer you a free website audit to see how you can improve your online visibility. We'd love to schedule a brief call to discuss your specific needs, goals, and how we can help you achieve them. Are you available for a call on [Suggest a specific date and time, e.g., Thursday at 2:00 PM]?  We can then discuss:\n*   Your specific product catalog.\n*   Your rental and service offerings in detail.\n*   Your target audience and brand.\n\nSincerely,\n[Your Name/Company Name]\n[Your Contact Information]",
)

# First message the agent will say
FIRST_MESSAGE = "Hello! This is Lexi from Web Solutions Inc. I hope I'm not catching you at a bad time. I'm calling to let you know about our website development services for small businesses. Do you have just a quick moment to chat?"

# ============================================================================
# CONFIGURATION FROM ENVIRONMENT (these should be set in your environment)
# ============================================================================



# ============================================================================
# VALIDATION AND UTILITY FUNCTIONS
# ============================================================================

def validate_us_phone_number(phone_number: str) -> Dict[str, Any]:
    """Validate that the phone number is a valid US number for ElevenLabs."""
    import re
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone_number)
    
    # Check for valid US number patterns
    if len(digits_only) == 10:
        # Add +1 prefix for 10-digit numbers
        normalized = f"+1{digits_only}"
    elif len(digits_only) == 11 and digits_only.startswith('1'):
        # Already has country code
        normalized = f"+{digits_only}"
    else:
        return {
            "valid": False,
            "error": f"Invalid US phone number format: {phone_number}. Expected 10 or 11 digits.",
            "normalized": None
        }
    
    # Basic US number validation (not toll-free, not premium)
    area_code = digits_only[-10:-7]
    if area_code.startswith('0') or area_code.startswith('1'):
        return {
            "valid": False,
            "error": f"Invalid area code: {area_code}. Area codes cannot start with 0 or 1.",
            "normalized": None
        }
    
    return {
        "valid": True,
        "error": None,
        "normalized": normalized
    }

def _init_elevenlabs_client():
    """Initialize and return the ElevenLabs client and conversational AI subclient."""
    try:
        from elevenlabs import ElevenLabs
        
        api_key = ELEVENLABS_API_KEY
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY not found in environment variables.")
            
        client = ElevenLabs(api_key=api_key)
        convai = client.conversational_ai
        return client, convai
    except ImportError:
        logger.error("ElevenLabs library not available. Please install: pip install elevenlabs")
        return None, None
    except Exception as e:
        logger.error(f"Failed to initialize ElevenLabs client: {e}")
        return None, None

# ============================================================================
# MAIN CALLING FUNCTION
# ============================================================================

async def make_test_call(
    to_number: str,
    system_prompt: str,
    first_message: str,
    poll_interval: float = 1.0
) -> dict[str, Any]:
    """
    Place a test outbound call via ElevenLabs and return the conversation transcript.
    
    Args:
        to_number: E.164-formatted destination phone number
        system_prompt: System prompt guiding agent behavior
        first_message: First message the agent will say
        poll_interval: Seconds between status checks

    Returns:
        A dictionary containing call status, transcript, and debug information
    """
    result = {
        "status": "initializing",
        "transcript": [],
        "debug_info": [],
        "error": None,
        "conversation_id": None
    }
    
    def add_debug(msg):
        result["debug_info"].append(msg)
        logger.info(msg)
    
    # Validate environment variables
    if not ELEVENLABS_API_KEY:
        error_msg = "ELEVENLABS_API_KEY environment variable is not set"
        add_debug(f"ERROR: {error_msg}")
        result["status"] = "error"
        result["error"] = error_msg
        return result
    
    if not ELEVENLABS_AGENT_ID:
        error_msg = "ELEVENLABS_AGENT_ID environment variable is not set"
        add_debug(f"ERROR: {error_msg}")
        result["status"] = "error"
        result["error"] = error_msg
        return result
        
    if not ELEVENLABS_PHONE_NUMBER_ID:
        error_msg = "ELEVENLABS_PHONE_NUMBER_ID environment variable is not set"
        add_debug(f"ERROR: {error_msg}")
        result["status"] = "error"
        result["error"] = error_msg
        return result

    # Initialize ElevenLabs client
    client, convai = _init_elevenlabs_client()
    if not client or not convai:
        error_msg = "Failed to initialize ElevenLabs client"
        add_debug(f"ERROR: {error_msg}")
        result["status"] = "error"
        result["error"] = error_msg
        return result
    
    add_debug(f"Initiating ElevenLabs call to: {to_number}")
    add_debug(f"Using Agent ID: {ELEVENLABS_AGENT_ID}")
    add_debug(f"Using Phone Number ID: {ELEVENLABS_PHONE_NUMBER_ID}")

    try:
        # Initiate the call with prompt overrides
        response = convai.twilio_outbound_call(
            agent_id=ELEVENLABS_AGENT_ID,
            agent_phone_number_id=ELEVENLABS_PHONE_NUMBER_ID,
            to_number=to_number,
            conversation_initiation_client_data={
                "conversation_config_override": {
                    "agent": {
                        "prompt": {"prompt": system_prompt},
                        "first_message": first_message
                    }
                }
            }
        )
        
        # Extract conversation ID
        conv_id = None
        for attr in ['conversation_id', 'id', 'callSid']:
            if hasattr(response, attr):
                conv_id = getattr(response, attr)
                add_debug(f"Found ID in '{attr}': {conv_id}")
                break
                
        if not conv_id:
            for attr_name in dir(response):
                if attr_name.startswith('_'):
                    continue
                try:
                    attr_value = getattr(response, attr_name)
                    if isinstance(attr_value, str) and len(attr_value) > 8:
                        add_debug(f"Using {attr_name} as conversation ID: {attr_value}")
                        conv_id = attr_value
                        break
                except:
                    pass
                    
        if not conv_id:
            raise RuntimeError("Could not find a conversation ID in the response")

        add_debug(f"Call initiated successfully. Conversation ID: {conv_id}")
        result["status"] = "initiated"
        result["conversation_id"] = conv_id

        # Poll until the conversation is complete
        add_debug("Polling for conversation completion...")
        poll_count = 0
        max_polls = 300  # 5 minutes max
        
        while poll_count < max_polls:
            try:
                details = convai.get_conversation(conv_id)
                
                status = None
                if hasattr(details, 'status'):
                    status = details.status
                    add_debug(f"Polling status: {status} (poll #{poll_count + 1})")
                    result["status"] = status
                    if status in ("done", "failed", "completed_successfully", "ended"):
                        add_debug(f"Conversation {status}.")
                        break
                else:
                    add_debug("Could not determine conversation status. Breaking poll loop.")
                    result["status"] = "unknown"
                    break
                    
            except Exception as e:
                add_debug(f"Error polling conversation: {str(e)}")
                result["status"] = "error_polling"
                result["error"] = str(e)
                break

            await asyncio.sleep(poll_interval)
            poll_count += 1

        if poll_count >= max_polls:
            add_debug("Maximum polling time reached")
            result["status"] = "timeout"

        # Extract transcript
        add_debug("Attempting to extract transcript...")
        transcript_turns = []
        
        if hasattr(details, 'transcript') and details.transcript is not None:
            transcript_turns = details.transcript
        elif hasattr(details, 'turns') and details.turns is not None:
            transcript_turns = details.turns
        else:
            for attr in dir(details):
                if attr.startswith('_'):
                    continue
                try:
                    value = getattr(details, attr)
                    if isinstance(value, list) and len(value) > 0:
                        transcript_turns = value
                        break
                except:
                    pass

        # Process transcript turns
        formatted_transcript = []
        for turn in transcript_turns:
            role = "unknown"
            if hasattr(turn, 'role'):
                role = turn.role
            
            message = "unknown"
            if hasattr(turn, 'message'):
                msg = turn.message
                if isinstance(msg, str):
                    message = msg
                elif hasattr(msg, 'text'):
                    message = msg.text
            elif hasattr(turn, 'text'):
                message = turn.text
                
            formatted_transcript.append({"role": role, "message": message})
            
        result["transcript"] = formatted_transcript
        add_debug(f"Extracted {len(formatted_transcript)} transcript turns")
        return result

    except Exception as e:
        add_debug(f"Error initiating call: {str(e)}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

# ============================================================================
# MAIN TEST FUNCTION
# ============================================================================

async def run_phone_call_test():
    """Run the complete phone call test."""
    
    print("=" * 80)
    print("📞 ELEVENLABS PHONE CALL TEST")
    print("=" * 80)
    
    # Validate phone number
    print(f"\n🔍 Validating phone number: {TEST_PHONE_NUMBER}")
    validation = validate_us_phone_number(TEST_PHONE_NUMBER)
    
    if not validation["valid"]:
        print(f"❌ Phone number validation failed: {validation['error']}")
        print("\n💡 Please edit TEST_PHONE_NUMBER in this script with a valid US phone number")
        return
        
    normalized_number = validation["normalized"]
    print(f"✅ Phone number valid. Normalized: {normalized_number}")
    
    # Check environment variables
    print(f"\n🔧 Checking environment variables...")
    env_vars = {
        "ELEVENLABS_API_KEY": "✅ Set" if ELEVENLABS_API_KEY else "❌ Missing",
        "ELEVENLABS_AGENT_ID": "✅ Set" if ELEVENLABS_AGENT_ID else "❌ Missing", 
        "ELEVENLABS_PHONE_NUMBER_ID": "✅ Set" if ELEVENLABS_PHONE_NUMBER_ID else "❌ Missing"
    }
    
    for var, status in env_vars.items():
        print(f"   {var}: {status}")
    
    missing_vars = [var for var, status in env_vars.items() if "❌" in status]
    if missing_vars:
        print(f"\n❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these environment variables before running the test.")
        return
    
    # Confirm before making the call
    print(f"\n⚠️  ABOUT TO MAKE A REAL PHONE CALL!")
    print(f"   📞 Calling: {normalized_number}")
    print(f"   🤖 Agent will say: \"{FIRST_MESSAGE[:60]}...\"")
    print(f"\n💰 Note: This will use ElevenLabs credits and may incur charges.")
    
    confirm = input("\n❓ Do you want to proceed with the call? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("❌ Call cancelled by user.")
        return
    
    # Make the call
    print(f"\n🚀 Initiating call to {normalized_number}...")
    print("⏳ This may take a few minutes depending on call duration...")
    
    start_time = time.time()
    result = await make_test_call(
        to_number=normalized_number,
        system_prompt=TEST_SYSTEM_PROMPT,
        first_message=FIRST_MESSAGE,
        poll_interval=2.0
    )
    end_time = time.time()
    
    # Display results
    print(f"\n📊 CALL COMPLETED (took {end_time - start_time:.1f} seconds)")
    print("=" * 60)
    print(f"Status: {result['status']}")
    print(f"Conversation ID: {result.get('conversation_id', 'N/A')}")
    
    if result.get('error'):
        print(f"Error: {result['error']}")
    
    # Display transcript
    transcript = result.get('transcript', [])
    if transcript:
        print(f"\n📝 CONVERSATION TRANSCRIPT ({len(transcript)} turns):")
        print("-" * 50)
        for i, turn in enumerate(transcript, 1):
            role_icon = "🤖" if turn["role"] == "agent" else "👤"
            print(f"{i}. {role_icon} {turn['role'].upper()}: {turn['message']}")
    else:
        print("\n❌ No transcript available")
    
    # Display debug info
    debug_info = result.get('debug_info', [])
    if debug_info:
        print(f"\n🔧 DEBUG INFORMATION:")
        print("-" * 30)
        for info in debug_info:
            print(f"   {info}")
    
    # Save results to file
    output_file = Path.cwd() / f"phone_call_test_result_{int(time.time())}.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "test_phone_number": normalized_number,
                "result": result
            }, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Results saved to: {output_file}")
    except Exception as e:
        print(f"\n❌ Failed to save results: {e}")
    
    print("\n✅ Test completed!")

# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Check if running in the correct environment
    if not TEST_PHONE_NUMBER or TEST_PHONE_NUMBER == "+1234567890":
        print("❌ Please edit TEST_PHONE_NUMBER in this script before running!")
        print("   Set it to your own phone number for testing.")
        exit(1)
    
    # Run the test
    asyncio.run(run_phone_call_test())
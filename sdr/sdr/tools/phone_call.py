"""
Phone call tool for outreach activities using ElevenLabs Conversational AI.
"""
import os
import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from google.adk.tools import FunctionTool, ToolContext
from ..config import ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, ELEVENLABS_PHONE_NUMBER_ID

logger = logging.getLogger(__name__)


def validate_us_phone_number(phone_number: str) -> Dict[str, Any]:
    """
    Validate that the phone number is a valid US number for ElevenLabs.
    
    Args:
        phone_number: Phone number to validate
        
    Returns:
        Dict with validation result and normalized number
    """
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


async def phone_number_validation_callback(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Before-tool callback to validate phone number format.
    
    Args:
        tool_input: The input parameters for the phone_call_tool
        
    Returns:
        Modified tool input with validated/normalized phone number
    """
    # Handle both old and new parameter names for backward compatibility
    destination = tool_input.get("destination") or tool_input.get("phone_number", "")
    
    if not destination:
        raise ValueError("Missing destination phone number")
    
    validation_result = validate_us_phone_number(destination)
    
    if not validation_result["valid"]:
        logger.error(f"Phone number validation failed: {validation_result['error']}")
        raise ValueError(f"Phone number validation failed: {validation_result['error']}")
    
    # Update the destination with the normalized version
    tool_input["destination"] = validation_result["normalized"]
    # Remove old parameter name if it exists
    if "phone_number" in tool_input:
        del tool_input["phone_number"]
    
    logger.info(f"Phone number normalized: {destination} -> {validation_result['normalized']}")
    
    return tool_input


def _write_call_log(filepath: Path, call_data: Dict[str, Any]) -> None:
    """Helper function to write call log data to file."""
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "call_data": call_data
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


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
        logger.warning("ElevenLabs library not available. Phone calls will be mocked.")
        return None, None
    except Exception as e:
        logger.error(f"Failed to initialize ElevenLabs client: {e}")
        return None, None


async def _make_real_call(
    convai,
    agent_id: str,
    phone_number_id: str,
    to_number: str,
    system_prompt: str,
    first_message: str,
    poll_interval: float = 1.0
) -> dict[str, Any]:
    """
    Place an actual outbound call via ElevenLabs and return the conversation transcript.
    
    Args:
        convai: The conversational AI client
        agent_id: The ID of the ElevenLabs agent
        phone_number_id: The ID of the phone number to use for the call
        to_number: E.164-formatted destination phone number
        system_prompt: System prompt guiding agent behavior
        first_message: Agent's opening message
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
    
    add_debug(f"Initiating ElevenLabs call to: {to_number}")
    add_debug(f"Using Agent ID: {agent_id}")
    add_debug(f"Using Phone Number ID: {phone_number_id}")

    try:
        # Initiate the call with prompt overrides
        response = convai.twilio_outbound_call(
            agent_id=agent_id,
            agent_phone_number_id=phone_number_id,
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
        while True:
            try:
                details = convai.get_conversation(conv_id)
                
                status = None
                if hasattr(details, 'status'):
                    status = details.status
                    add_debug(f"Polling status: {status}")
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
        return result

    except Exception as e:
        add_debug(f"Error initiating call: {str(e)}")
        result["status"] = "error"
        result["error"] = str(e)
        return result


# Extract key information with flexible key handling
    if business_data:
        debug_info["business_data"] = business_data
        business_name = business_data.get('name', 'Unknown Business')
        
        # Handle both 'phone' and 'phone_number' keys
        business_phone = (
            business_data.get('phone') or 
            business_data.get('phone_number') or 
            'No phone available'
        )
        
        business_email = business_data.get('email', 'No email available')
        business_city = business_data.get('city', 'Unknown City')
        
        debug_info["extracted_phone"] = business_phone
        
        print(f"\n🎯 EXTRACTED BUSINESS INFORMATION:")
        print(f"   📝 Name: {business_name}")
        print(f"   📞 Phone: {business_phone}")
        print(f"   📧 Email: {business_email}")
        print(f"   🏙️ City: {business_city}")
        print(f"   🔍 Keys in business_data: {list(business_data.keys())}")
        
        # Check if phone number is usable for calling
        if business_phone and business_phone != 'No phone available':
            print(f"\n✅ PHONE NUMBER READY FOR CALLING: {business_phone}")
        else:
            print(f"\n❌ NO VALID PHONE NUMBER FOUND")
    else:
        print(f"\n❌ CRITICAL: No business_data found!")
        business_name = 'Unknown Business'
        business_phone = 'No phone available'
        business_email = 'No email available'
    
    # Write comprehensive debug file
    root_path = Path.cwd()
    debug_file = root_path / "phone_call_debug_detailed.json"
    
    try:
        with open(debug_file, 'w', encoding='utf-8') as f:
            json.dump(debug_info, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Debug info written to: {debug_file}")
    except Exception as e:
        print(f"❌ Failed to write debug file: {e}")
    
    # Create mock conversation result
    print(f"\n🎭 CREATING MOCK CONVERSATION RESULT")
    print("-" * 50)
    
    # Mock conversation with the extracted data
    mock_transcript = [
        {
            "role": "agent", 
            "message": f"Hello, my name is Lexi from SalesShortcuts and I am calling {business_name} to discuss building a website for your business."
        },
        {
            "role": "user", 
            "message": "Hi, thanks for calling. How would it help my business?"
        },
        {
            "role": "agent", 
            "message": "We can help you build a professional website that attracts more customers and increases your online presence. Based on our research, we see that your business could really benefit from having an online store and better visibility in search results."
        },
        {
            "role": "user", 
            "message": "That sounds interesting, can you send me more details via email?"
        },
        {
            "role": "agent", 
            "message": f"Absolutely! I'll send you a detailed proposal to {business_email} with all the information about how we can help {business_name} grow online."
        },
        {
            "role": "user", 
            "message": "Great, I will look forward to it. Thanks for calling!"
        },
        {
            "role": "agent", 
            "message": "Thank you for your time! You'll receive the email within the next hour. Have a great day!"
        }
    ]
    
    # Print the mock conversation to console
    print("\n📞 MOCK CONVERSATION TRANSCRIPT:")
    print("=" * 60)
    for i, turn in enumerate(mock_transcript, 1):
        role_icon = "🤖" if turn["role"] == "agent" else "👤"
        print(f"{i}. {role_icon} {turn['role'].upper()}: {turn['message']}")
    print("=" * 60)
    
    # Create final result
    result = {
        "id": f"test_phone_call_{int(time.time())}",
        "action_type": "phone_call",
        "status": "test_completed" if business_data else "error_no_business_data",
        "business_data": business_data,
        "business_name": business_name,
        "destination": business_phone,
        "transcript": mock_transcript,
        "summary": f"[TEST] Call to {business_name} ({business_phone}) completed successfully. Customer interested in website proposal.",
        "debug_info": debug_info,
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"\n🎯 FINAL RESULT SUMMARY:")
    print(f"   Status: {result['status']}")
    print(f"   Business: {business_name}")
    print(f"   Phone: {business_phone}")
    print(f"   Transcript Length: {len(mock_transcript)} turns")
    
    print("\n" + "="*80)
    print("✅ PHONE CALL FUNCTION DEBUG COMPLETE")
    print("="*80 + "\n")
    
    return result

# High level tool definition for phone call
phone_call_tool = FunctionTool(func=phone_call)
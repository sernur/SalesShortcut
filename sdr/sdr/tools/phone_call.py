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
) -> Dict[str, Any]:
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


async def phone_call_tool(
    destination: str,
    prompt: str
) -> Dict[str, Any]:
    """
    Phone call tool for outreach activities using ElevenLabs Conversational AI.
    
    Args:
        destination: The phone number to call (E.164 format recommended)
        prompt: The complete prompt/instruction for the call agent
        
    Returns:
        A dictionary containing call results and categorization
    """
    
    # Internal configuration
    max_duration_minutes = 5
    call_categories = ["agreed_for_getting_email_proposal", "not_interested", "call_later"]
    
    # Create call log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"phone_call_log_{timestamp}.json"
    filepath = Path(filename)
    
    call_data = {
        "destination": destination,
        "prompt": prompt,
        "max_duration_minutes": max_duration_minutes,
        "status": "initiated",
        "timestamp": datetime.now().isoformat(),
        "call_type": "real_call",
        "target_categories": call_categories
    }
    
    try:
        # Initialize ElevenLabs client
        client, convai = _init_elevenlabs_client()
        
        if not convai:
            # Fallback to mock if ElevenLabs not available
            logger.warning("ElevenLabs not available, using mock call")
            call_data["call_type"] = "mock_call"
            await asyncio.sleep(1)
            
            # Generate mock result with categorization
            import random
            mock_category = random.choice(call_categories)
            
            call_result = {
                "status": "completed",
                "duration_seconds": random.randint(120, 300),
                "category": mock_category,
                "transcript": [
                    {"role": "agent", "message": prompt[:100] + "..."},
                    {"role": "user", "message": "Hi, thanks for calling."},
                    {"role": "agent", "message": "I'd like to discuss our solution that could help your business..."}
                ],
                "summary": f"[MOCK] Call completed to {destination}. Prospect categorized as: {mock_category}",
                "call_type": "mock_call"
            }
            
            # Add category-specific details
            if mock_category == "agreed_for_getting_email_proposal":
                call_result["next_action"] = "Send email proposal"
                call_result["prospect_email"] = f"contact@{destination.replace('+1', '').replace('-', '')}.com"
            elif mock_category == "not_interested":
                call_result["next_action"] = "Mark as not interested"
                call_result["reason"] = "Not a good fit for current needs"
            else:  # call_later
                call_result["next_action"] = "Schedule follow-up call"
                call_result["callback_date"] = "2024-12-20"
        else:
            # Make real call using ElevenLabs
            agent_id = ELEVENLABS_AGENT_ID
            phone_number_id = ELEVENLABS_PHONE_NUMBER_ID
            
            if not agent_id or not phone_number_id:
                raise ValueError("ElevenLabs agent_id and phone_number_id must be configured")
            
            # Enhanced system prompt with categorization instructions
            system_prompt = f"""
            {prompt}
            
            IMPORTANT CATEGORIZATION INSTRUCTIONS:
            Your main goal is to categorize this call into one of these three categories based on the prospect's response:
            
            1. "agreed_for_getting_email_proposal" - Prospect is interested and wants to receive an email proposal
            2. "not_interested" - Prospect is not interested in the offering
            3. "call_later" - Prospect asks to be called back later or wants to think about it
            
            Keep the call focused and within {max_duration_minutes} minutes. 
            At the end of the call, clearly determine which category the prospect falls into based on their responses.
            """
            
            # Extract first message from prompt
            first_message = prompt.split('\n')[0] if '\n' in prompt else prompt[:100] + "..."
            
            # Make the actual call
            call_result = await _make_real_call(
                convai=convai,
                agent_id=agent_id,
                phone_number_id=phone_number_id,
                to_number=destination,
                instruction=system_prompt,
                first_message=first_message,
                poll_interval=1.0
            )

            # Process the real call result and categorize
            if call_result["status"] in ["done", "completed_successfully"]:
                call_result["status"] = "completed"
                
                # Analyze transcript for categorization
                category = "call_later"  # default
                if call_result.get("transcript"):
                    transcript_text = " ".join([turn["message"] for turn in call_result["transcript"]]).lower()
                    
                    # Simple keyword-based categorization
                    if any(word in transcript_text for word in ["yes", "send", "email", "proposal", "interested"]):
                        category = "agreed_for_getting_email_proposal"
                        call_result["next_action"] = "Send email proposal"
                    elif any(word in transcript_text for word in ["no", "not interested", "not a fit", "busy"]):
                        category = "not_interested"
                        call_result["next_action"] = "Mark as not interested"
                    else:
                        category = "call_later"
                        call_result["next_action"] = "Schedule follow-up call"
                
                call_result["category"] = category
                call_result["summary"] = f"Call completed to {destination}. Prospect categorized as: {category}"
                
            elif call_result["status"] == "failed":
                call_result["category"] = "call_later"
                call_result["summary"] = f"Call failed to {destination}. Will retry later."
                call_result["next_action"] = "Retry call or try alternative contact method"
        
        call_data.update(call_result)
        
        # Write call log
        await asyncio.to_thread(_write_call_log, filepath, call_data)
        
        return call_data
        
    except Exception as e:
        logger.exception(f"Error during phone call to {destination}")
        error_result = {
            "status": "failed",
            "category": "call_later",
            "error": f"Error during phone call: {str(e)}",
            "summary": f"Call to {destination} failed due to technical error",
            "next_action": "Retry call or try alternative contact method",
            "call_type": "error"
        }
        call_data.update(error_result)
        
        try:
            await asyncio.to_thread(_write_call_log, filepath, call_data)
        except:
            pass
            
        return call_data


async def phone_call_tool_test(
    destination: str,
    prompt: str,
    tool_context: ToolContext
) -> Dict[str, Any]:
    """
    Test version of the phone call tool for outreach activities.
    
    Args:
        destination: The phone number to call (E.164 format recommended)
        prompt: The complete prompt/instruction for the call agent
        
    Returns:
        A dictionary containing test call results
    """
    # Log all tool_context in json
    tool_context_json = tool_context.to_dict()
    logger.info(f"Tool context for `phone_call_tool_test`: {json.dumps(tool_context_json, indent=2)}")
    logger.info(f"Starting phone call tool test to {destination} with prompt: {prompt}")
    # Sleep for 3 seconds to simulate processing time
    await asyncio.sleep(3)
    
    # Mock conversation result
    result = {
        "id": f"test_phone_call_{int(time.time())}",
        "action_type": "phone_call",
        "status": "test_completed",
        "destination": destination,
        "prompt": prompt,
        "transcript": [
            {"role": "agent", "message": "Hello, my name is Lexi from SalesShortcuts and I am calling to discuss the potential building website for your business."},
            {"role": "user", "message": "Hi, thanks for calling. How it would help my business?"},
            {"role": "agent", "message": "We can help you build a professional website that attracts more customers and increases your online presence."},
            {"role": "user", "message": "That sounds interesting, can you send me more details via email?"},
            {"role": "agent", "message": "Sure, I will send you an email with all the details right away."}
            {"role": "user", "message": "Great, I will look forward to it. Bye!"}
        ],
        "summary": f"[TEST] Call to {destination} completed successfully.",
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info(f"Phone call tool test completed: {result}")
    return result


phone_call_function_tool = FunctionTool(func=phone_call_tool_test)
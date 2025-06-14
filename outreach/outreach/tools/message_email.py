"""
Email messaging tool for outreach activities.
"""
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from google.adk.tools import FunctionTool
from ..config import SMTP_SERVER, SMTP_PORT, EMAIL_USERNAME, EMAIL_PASSWORD, FROM_EMAIL


def _write_email_log(filepath: Path, email_data: Dict[str, Any]) -> None:
    """Helper function to write email log data to file."""
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "email_data": email_data
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


async def message_email_tool(
    to_email: str,
    subject: str,
    message_body: str,
    email_type: str = "outreach",
    cc_emails: Optional[List[str]] = None,
    personalization_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Email messaging tool for outreach activities.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line
        message_body: The email message content
        email_type: Type of email (e.g., "outreach", "follow_up", "meeting_invite")
        cc_emails: Optional list of CC email addresses
        personalization_data: Optional data for personalizing the email
        
    Returns:
        A dictionary containing email send results and status
    """
    
    # Create email log file
    timestamp = datetime.now().isoformat()
    filename = f"email_log_{timestamp}.json"
    filepath = Path(filename)
    
    email_data = {
        "to_email": to_email,
        "subject": subject,
        "message_body": message_body,
        "email_type": email_type,
        "cc_emails": cc_emails or [],
        "personalization_data": personalization_data or {},
        "from_email": FROM_EMAIL,
        "status": "initiated",
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # For now, simulate email sending with mock data
        # In production, this would integrate with SMTP server or email service
        
        await asyncio.sleep(0.5)  # Simulate email processing time
        
        # Apply personalization if provided
        personalized_body = message_body
        if personalization_data:
            for key, value in personalization_data.items():
                personalized_body = personalized_body.replace(f"{{{key}}}", str(value))
        
        # Mock email result based on type
        if email_type == "outreach":
            email_result = {
                "status": "sent",
                "message_id": f"outreach_{timestamp}_{hash(to_email)}",
                "delivery_status": "delivered",
                "personalized_body": personalized_body,
                "tracking": {
                    "sent_at": datetime.now().isoformat(),
                    "expected_delivery": "within_5_minutes"
                },
                "next_action": "Monitor for response within 48 hours"
            }
        elif email_type == "follow_up":
            email_result = {
                "status": "sent",
                "message_id": f"followup_{timestamp}_{hash(to_email)}",
                "delivery_status": "delivered",
                "personalized_body": personalized_body,
                "tracking": {
                    "sent_at": datetime.now().isoformat(),
                    "is_follow_up": True
                },
                "next_action": "Wait for response or schedule next follow-up"
            }
        elif email_type == "meeting_invite":
            email_result = {
                "status": "sent",
                "message_id": f"meeting_{timestamp}_{hash(to_email)}",
                "delivery_status": "delivered",
                "personalized_body": personalized_body,
                "tracking": {
                    "sent_at": datetime.now().isoformat(),
                    "calendar_invite_included": True
                },
                "next_action": "Await meeting confirmation"
            }
        else:
            email_result = {
                "status": "sent",
                "message_id": f"email_{timestamp}_{hash(to_email)}",
                "delivery_status": "delivered",
                "personalized_body": personalized_body,
                "tracking": {
                    "sent_at": datetime.now().isoformat()
                },
                "next_action": "Monitor for response"
            }
        
        email_data.update(email_result)
        
        await asyncio.to_thread(_write_email_log, filepath, email_data)
        
        return email_data
        
    except Exception as e:
        error_result = {
            "status": "failed",
            "error": f"Error sending email: {str(e)}",
            "next_action": "Retry email send or try alternative contact method"
        }
        email_data.update(error_result)
        
        try:
            await asyncio.to_thread(_write_email_log, filepath, email_data)
        except:
            pass  # Don't fail if we can't write the log
            
        return email_data


async def message_email_tool_test(
    to_email: str,
    subject: str,
    message_body: str,
    email_type: str = "outreach",
    cc_emails: Optional[List[str]] = None,
    personalization_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Test version of the email messaging tool for outreach activities.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line
        message_body: The email message content
        email_type: Type of email (e.g., "outreach", "follow_up", "meeting_invite")
        cc_emails: Optional list of CC email addresses
        personalization_data: Optional data for personalizing the email
        
    Returns:
        A dictionary containing test email send results and status
    """
    import time
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Sleep 3 seconds to simulate processing time
    await asyncio.sleep(3)
    
    result = {
        "id": f"test_email_{int(time.time())}",
        "action_type": "email",
        "status": "test_success",
        "message": "Test email sent successfully",
        "to_email": to_email,
        "subject": subject,
        "message_body": message_body,
        "email_type": email_type,
        "cc_emails": cc_emails or [],
        "personalization_data": personalization_data or {},
        "next_action": "Verify test email in inbox",
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info(f"Email tool test completed: {result}")
    return result


message_email_function_tool = FunctionTool(func=message_email_tool_test)
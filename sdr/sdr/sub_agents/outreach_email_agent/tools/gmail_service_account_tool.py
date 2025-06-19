"""
Gmail Service Account Tool - No manual authentication required.
Uses service account with domain-wide delegation to send emails.
Based on working example with attachment support.
"""

import os
import base64
import mimetypes
from typing import Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from sdr.sdr.config import SERVICE_ACCOUNT_FILE, SALES_EMAIL, GMAIL_SCOPES


def create_service_account_credentials():
    """
    Creates service account credentials with domain-wide delegation.
    Handles both local development (JSON file) and cloud deployment scenarios.
    
    Returns:
        google.oauth2.service_account.Credentials: Delegated credentials for the sales email
    """
    try:
        print(f"🔑 Setting up service account authentication for {SALES_EMAIL}...")
        
        # Try to use environment variable for cloud deployment first
        credentials = None
        
        # Check if GOOGLE_APPLICATION_CREDENTIALS is set (cloud deployment)
        if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            print("📁 Using GOOGLE_APPLICATION_CREDENTIALS environment variable...")
            credentials = service_account.Credentials.from_service_account_file(
                os.getenv('GOOGLE_APPLICATION_CREDENTIALS'), scopes=GMAIL_SCOPES
            )
        # Check if service account file exists locally
        elif os.path.exists(SERVICE_ACCOUNT_FILE):
            print(f"📁 Using local service account file: {SERVICE_ACCOUNT_FILE}")
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=GMAIL_SCOPES
            )
        else:
            # Try default cloud credentials (for Cloud Run with service account attached)
            try:
                print("☁️ Attempting to use default Cloud credentials...")
                from google.auth import default
                credentials, _ = default(scopes=GMAIL_SCOPES)
            except Exception as default_error:
                raise FileNotFoundError(
                    f"No service account credentials found. Tried:\n"
                    f"1. GOOGLE_APPLICATION_CREDENTIALS env var\n"
                    f"2. Local file: {SERVICE_ACCOUNT_FILE}\n"
                    f"3. Default cloud credentials\n"
                    f"Default credentials error: {default_error}"
                )
        
        # Create delegated credentials for the sales email
        if hasattr(credentials, 'with_subject'):
            delegated_credentials = credentials.with_subject(SALES_EMAIL)
        else:
            # For some credential types, we might not need delegation
            delegated_credentials = credentials
        
        print(f"✅ Service account authentication successful for {SALES_EMAIL}")
        return delegated_credentials
        
    except Exception as e:
        print(f"❌ Service account setup failed: {e}")
        raise


def send_email_with_attachment(to_email: str, subject: str, body: str, attachment_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Send email from sales account with optional attachment using service account.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body text
        attachment_path: Optional path to attachment file
        
    Returns:
        Dict containing send result with status and message/error info
    """
    try:
        print(f"📧 Preparing to send email to {to_email}")
        print(f"   From: {SALES_EMAIL}")
        print(f"   Subject: {subject}")
        if attachment_path:
            print(f"   Attachment: {attachment_path}")
        
        # Check if attachment exists
        if attachment_path and not os.path.exists(attachment_path):
            print(f"⚠️  Warning: Attachment file not found at {attachment_path}")
            print("   Sending email without attachment...")
            attachment_path = None
        
        # Create credentials
        credentials = create_service_account_credentials()
        
        # Create Gmail service
        service = build('gmail', 'v1', credentials=credentials)
        
        # Create message with or without attachment
        if attachment_path and os.path.exists(attachment_path):
            print("📎 Adding attachment...")
            message = MIMEMultipart()
            message.attach(MIMEText(body, 'plain'))
            
            # Add attachment
            content_type, encoding = mimetypes.guess_type(attachment_path)
            if content_type is None or encoding is not None:
                content_type = 'application/octet-stream'  # Default type
            
            main_type, sub_type = content_type.split('/', 1)
            
            with open(attachment_path, 'rb') as f:
                file_data = f.read()
            
            attachment_part = MIMEBase(main_type, sub_type)
            attachment_part.set_payload(file_data)
            encoders.encode_base64(attachment_part)
            
            filename = os.path.basename(attachment_path)
            attachment_part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )
            message.attach(attachment_part)
            print(f"✅ Attachment added: {filename}")
        else:
            # Simple text message if no attachment
            message = MIMEText(body, 'plain')
        
        # Set email headers
        message['to'] = to_email
        message['from'] = SALES_EMAIL
        message['subject'] = subject
        
        # Send email
        print("📤 Sending email...")
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        result = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        message_id = result.get('id')
        thread_id = result.get('threadId')
        
        print("✅ EMAIL SENT SUCCESSFULLY!")
        print(f"   Message ID: {message_id}")
        print(f"   Thread ID: {thread_id}")
        if attachment_path and os.path.exists(attachment_path):
            print(f"   📎 Attachment: {os.path.basename(attachment_path)} included")
        print(f"   📬 Check {to_email} inbox!")
        
        return {
            "status": "success",
            "message_id": message_id,
            "thread_id": thread_id,
            "message": f"Email sent successfully from {SALES_EMAIL} to {to_email}",
            "attachment_included": attachment_path is not None and os.path.exists(attachment_path)
        }
        
    except HttpError as error:
        error_details = str(error)
        print(f"❌ Gmail API error: {error_details}")
        return {
            "status": "failed",
            "error": f"Gmail API error: {error_details}",
            "message": f"Failed to send email from {SALES_EMAIL} to {to_email}"
        }
        
    except Exception as e:
        print(f"❌ Email sending failed: {e}")
        return {
            "status": "failed", 
            "error": str(e),
            "message": f"Failed to send email from {SALES_EMAIL} to {to_email}"
        }


# Tool function for LLM Agent usage
def gmail_send_tool(to_email: str, subject: str, body: str, attachment_path: Optional[str] = None) -> str:
    """
    Tool function for sending emails via Gmail API using service account.
    Designed to be used as a tool by LLM agents.
    
    Args:
        to_email: Recipient email address
        subject: Email subject  
        body: Email body text
        attachment_path: Optional path to attachment file
        
    Returns:
        String result of the email sending operation
    """
    result = send_email_with_attachment(to_email, subject, body, attachment_path)
    
    if result["status"] == "success":
        attachment_info = f" with attachment" if result.get("attachment_included") else ""
        return f"✅ Email sent successfully to {to_email}{attachment_info}! Message ID: {result.get('message_id', 'N/A')}"
    else:
        return f"❌ Failed to send email to {to_email}. Error: {result.get('error', 'Unknown error')}"


def send_crafted_email(crafted_email: Dict[str, str], attachment_path: Optional[str] = None) -> str:
    """
    Tool function to send email from crafted_email data structure.
    
    Args:
        crafted_email: Dict with 'to', 'subject', 'body' keys
        attachment_path: Optional path to attachment file
        
    Returns:
        String result of the email sending operation
    """
    try:
        to_email = crafted_email.get('to', '')
        subject = crafted_email.get('subject', '')
        body = crafted_email.get('body', '')
        
        if not all([to_email, subject, body]):
            return "❌ Invalid crafted_email data: missing to, subject, or body fields"
        
        return gmail_send_tool(to_email, subject, body, attachment_path)
        
    except Exception as e:
        return f"❌ Error processing crafted email: {str(e)}"
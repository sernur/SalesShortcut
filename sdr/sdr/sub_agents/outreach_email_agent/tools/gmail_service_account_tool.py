"""
Gmail Service Account Tool - No manual authentication required.
Uses service account with domain-wide delegation to send emails.
Based on working example with attachment support.
"""

import os
import base64
import mimetypes
import logging
from typing import Optional, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.adk.tools import FunctionTool

from sdr.sdr.config import SERVICE_ACCOUNT_FILE, SALES_EMAIL, GMAIL_SCOPES

# Setup logger for this module
logger = logging.getLogger(__name__)


def create_service_account_credentials():
    """
    Creates service account credentials with domain-wide delegation.
    Handles both local development (JSON file) and cloud deployment scenarios.
    
    Returns:
        google.oauth2.service_account.Credentials: Delegated credentials for the sales email
    """
    try:
        print(f"🔑 Setting up service account authentication for {SALES_EMAIL}...")
        logger.info(f"Setting up service account authentication for {SALES_EMAIL}")
        
        # Try to use environment variable for cloud deployment first
        credentials = None
        
        # Check if SERVICE_ACCOUNT_FILE is set (cloud deployment)
        if os.getenv('SERVICE_ACCOUNT_FILE'):
            print("📁 Using SERVICE_ACCOUNT_FILE environment variable...")
            logger.info(f"Using SERVICE_ACCOUNT_FILE: {os.getenv('SERVICE_ACCOUNT_FILE')}")
            credentials = service_account.Credentials.from_service_account_file(
                os.getenv('SERVICE_ACCOUNT_FILE'), scopes=GMAIL_SCOPES
            )
        # Check if service account file exists locally
        elif os.path.exists(SERVICE_ACCOUNT_FILE):
            print(f"📁 Using local service account file: {SERVICE_ACCOUNT_FILE}")
            logger.info(f"Using local service account file: {SERVICE_ACCOUNT_FILE}")
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=GMAIL_SCOPES
            )
        else:
            # Try default cloud credentials (for Cloud Run with service account attached)
            try:
                print("☁️ Attempting to use default Cloud credentials...")
                logger.info("Attempting to use default Cloud credentials")
                from google.auth import default
                credentials, _ = default(scopes=GMAIL_SCOPES)
            except Exception as default_error:
                logger.error(f"Default credentials failed: {default_error}")
                raise FileNotFoundError(
                    f"No service account credentials found. Tried:\n"
                    f"1. SERVICE_ACCOUNT_FILE env var\n"
                    f"2. Local file: {SERVICE_ACCOUNT_FILE}\n"
                    f"3. Default cloud credentials\n"
                    f"Default credentials error: {default_error}"
                )
        
        # Create delegated credentials for the sales email
        if hasattr(credentials, 'with_subject'):
            delegated_credentials = credentials.with_subject(SALES_EMAIL)
            logger.info(f"Created delegated credentials for {SALES_EMAIL}")
        else:
            # For some credential types, we might not need delegation
            delegated_credentials = credentials
            logger.info("Using non-delegated credentials")
        
        print(f"✅ Service account authentication successful for {SALES_EMAIL}")
        logger.info(f"Service account authentication successful for {SALES_EMAIL}")
        return delegated_credentials
        
    except Exception as e:
        print(f"❌ Service account setup failed: {e}")
        logger.error(f"Service account setup failed: {e}", exc_info=True)
        raise


def send_email_with_attachment(to_email: str, subject: str, body: str, attachment_path: Optional[str] = None) -> dict[str, Any]:
    """
    Send email from sales account with optional attachment using service account.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body text
        attachment_path: Optional path to attachment file
        
    Returns:
        dict containing send result with status and message/error info
    """
    try:
        print(f"📧 Preparing to send email to {to_email}")
        print(f"   From: {SALES_EMAIL}")
        print(f"   Subject: {subject}")
        logger.info(f"Preparing to send email from {SALES_EMAIL} to {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Body length: {len(body)} characters")
        
        if attachment_path:
            print(f"   Attachment: {attachment_path}")
            logger.info(f"Attachment path: {attachment_path}")
        
        # Check if attachment exists
        if attachment_path and not os.path.exists(attachment_path):
            print(f"⚠️  Warning: Attachment file not found at {attachment_path}")
            print("   Sending email without attachment...")
            logger.warning(f"Attachment file not found at {attachment_path}")
            attachment_path = None
        
        # Create credentials
        logger.info("Creating service account credentials...")
        credentials = create_service_account_credentials()
        
        # Create Gmail service
        logger.info("Building Gmail service...")
        service = build('gmail', 'v1', credentials=credentials)
        logger.info("Gmail service created successfully")
        
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
        logger.info("Encoding email message...")
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        logger.info(f"Raw message length: {len(raw_message)} characters")
        
        logger.info("Calling Gmail API to send email...")
        result = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        message_id = result.get('id')
        thread_id = result.get('threadId')
        
        print("✅ EMAIL SENT SUCCESSFULLY!")
        print(f"   Message ID: {message_id}")
        print(f"   Thread ID: {thread_id}")
        logger.info(f"Email sent successfully! Message ID: {message_id}, Thread ID: {thread_id}")
        
        if attachment_path and os.path.exists(attachment_path):
            print(f"   📎 Attachment: {os.path.basename(attachment_path)} included")
            logger.info(f"Attachment included: {os.path.basename(attachment_path)}")
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
        logger.error(f"Gmail API error: {error_details}", exc_info=True)
        return {
            "status": "failed",
            "error": f"Gmail API error: {error_details}",
            "message": f"Failed to send email from {SALES_EMAIL} to {to_email}"
        }
        
    except Exception as e:
        print(f"❌ Email sending failed: {e}")
        logger.error(f"Email sending failed: {e}", exc_info=True)
        return {
            "status": "failed", 
            "error": str(e),
            "message": f"Failed to send email from {SALES_EMAIL} to {to_email}"
        }


send_email = FunctionTool(func=send_email_with_attachment)
"""
Gmail Pub/Sub Pull Listener Service
==================================

This service continuously pulls messages from your Pub/Sub subscription
and processes Gmail notifications.
"""

import json
import time
import os
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from google.cloud import pubsub_v1
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ID = os.getenv("PROJECT_ID")
SUBSCRIPTION_NAME = os.getenv("SUBSCRIPTION_NAME", "gmail-notifications-pull")
SALES_EMAIL = os.getenv("SALES_EMAIL")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", ".secrets/sales-automation-service.json")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GmailPubSubListener:
    def __init__(self):
        self.project_id = PROJECT_ID
        self.subscription_name = SUBSCRIPTION_NAME
        self.sales_email = SALES_EMAIL
        
        # Initialize Pub/Sub subscriber
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscription_path = self.subscriber.subscription_path(
            PROJECT_ID, SUBSCRIPTION_NAME
        )
        
        # Initialize Gmail service
        self.gmail_service = self._init_gmail_service()
        
        logger.info(f"🚀 Gmail Listener initialized")
        logger.info(f"   📧 Email: {self.sales_email}")
        logger.info(f"   📡 Subscription: {self.subscription_path}")
    
    def _init_gmail_service(self):
        """Initialize Gmail API service with delegation"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, 
                scopes=['https://www.googleapis.com/auth/gmail.readonly']
            )
            delegated_creds = credentials.with_subject(self.sales_email)
            service = build('gmail', 'v1', credentials=delegated_creds)
            
            # Test access
            profile = service.users().getProfile(userId='me').execute()
            logger.info(f"✅ Gmail API access confirmed for {profile.get('emailAddress')}")
            
            return service
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gmail service: {e}")
            return None
    
    def process_gmail_notification(self, notification_data):
        """Process a Gmail notification from Pub/Sub"""
        try:
            # Parse notification
            if isinstance(notification_data, bytes):
                notification_data = notification_data.decode('utf-8')
            
            notification = json.loads(notification_data)
            email_address = notification.get('emailAddress')
            history_id = notification.get('historyId')
            
            logger.info(f"📨 Processing notification:")
            logger.info(f"   📧 Email: {email_address}")
            logger.info(f"   📊 History ID: {history_id}")
            
            if not self.gmail_service:
                logger.error("❌ Gmail service not available")
                return False
            
            # Get recent messages using history
            try:
                # List recent messages from history
                history = self.gmail_service.users().history().list(
                    userId='me',
                    startHistoryId=history_id,
                    maxResults=10
                ).execute()
                
                changes = history.get('history', [])
                logger.info(f"📋 Found {len(changes)} history changes")
                
                for change in changes:
                    # Process messages added
                    messages_added = change.get('messagesAdded', [])
                    for msg_added in messages_added:
                        message_id = msg_added['message']['id']
                        self.process_new_message(message_id)
                        
            except Exception as e:
                logger.warning(f"⚠️ History API failed, trying recent messages: {e}")
                # Fallback: Get recent unread messages
                self.check_recent_messages()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing notification: {e}")
            return False
    
    def process_new_message(self, message_id):
        """Process a specific new message"""
        try:
            # Get full message
            message = self.gmail_service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extract headers
            headers = message['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
            
            logger.info(f"📬 New message received:")
            logger.info(f"   📨 From: {sender}")
            logger.info(f"   📋 Subject: {subject}")
            logger.info(f"   📅 Date: {date}")
            logger.info(f"   🆔 Message ID: {message_id}")
            
            # HERE: Add your ADK Agent A2A trigger
            self.trigger_adk_agent(message_id, sender, subject, message)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing message {message_id}: {e}")
            return False
    
    def check_recent_messages(self):
        """Fallback: Check for recent unread messages"""
        try:
            logger.info("🔍 Checking recent unread messages...")
            
            messages = self.gmail_service.users().messages().list(
                userId='me',
                q='is:unread',
                maxResults=5
            ).execute()
            
            message_list = messages.get('messages', [])
            logger.info(f"📧 Found {len(message_list)} unread messages")
            
            for msg in message_list:
                self.process_new_message(msg['id'])
                
        except Exception as e:
            logger.error(f"❌ Error checking recent messages: {e}")
    
    def trigger_adk_agent(self, message_id, sender, subject, full_message):
        """Trigger your ADK Agent via A2A"""
        logger.info(f"🤖 Triggering ADK Agent for message {message_id}")
        
        # TODO: Replace this with your actual ADK Agent A2A call
        # Example data you might send:
        agent_payload = {
            "event_type": "new_email",
            "email_data": {
                "message_id": message_id,
                "sender": sender,
                "subject": subject,
                "timestamp": datetime.now().isoformat(),
                "sales_email": self.sales_email
            }
        }
        
        # Example A2A call (replace with your actual implementation):
        try:
            # import requests
            # response = requests.post(
            #     "YOUR_ADK_AGENT_ENDPOINT",
            #     json=agent_payload,
            #     headers={"Authorization": "Bearer YOUR_TOKEN"}
            # )
            # logger.info(f"✅ ADK Agent triggered: {response.status_code}")
            
            logger.info(f"📤 Would trigger ADK Agent with: {agent_payload}")
            
        except Exception as e:
            logger.error(f"❌ Failed to trigger ADK Agent: {e}")
    
    def message_callback(self, message):
        """Callback for processing Pub/Sub messages"""
        try:
            logger.info(f"📥 Received Pub/Sub message: {message.message_id}")
            
            # Process the Gmail notification
            success = self.process_gmail_notification(message.data)
            
            if success:
                message.ack()
                logger.info(f"✅ Message {message.message_id} processed and acknowledged")
            else:
                message.nack()
                logger.error(f"❌ Message {message.message_id} processing failed, nacked")
                
        except Exception as e:
            logger.error(f"❌ Error in message callback: {e}")
            message.nack()
    
    def start_listening(self):
        """Start the pull subscription listener"""
        logger.info(f"🎧 Starting Gmail Pub/Sub listener...")
        logger.info(f"📡 Listening on: {self.subscription_path}")
        
        # Configure flow control
        flow_control = pubsub_v1.types.FlowControl(max_messages=10)
        
        try:
            # Start pulling messages
            streaming_pull_future = self.subscriber.pull(
                request={
                    "subscription": self.subscription_path,
                    "max_messages": 10,
                },
                callback=self.message_callback,
                flow_control=flow_control,
            )
            
            logger.info(f"🚀 Listening for messages on {self.subscription_path}")
            logger.info(f"💡 Send an email to {self.sales_email} to test!")
            
            # Keep the main thread running
            with self.subscriber:
                try:
                    # Run indefinitely
                    streaming_pull_future.result()
                except KeyboardInterrupt:
                    streaming_pull_future.cancel()
                    logger.info("🛑 Listener stopped by user")
                except Exception as e:
                    streaming_pull_future.cancel()
                    logger.error(f"❌ Listener error: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Failed to start listener: {e}")
    
    def test_connection(self):
        """Test the connection to Pub/Sub and Gmail"""
        logger.info("🧪 Testing connections...")
        
        # Test Pub/Sub subscription
        try:
            # Check if subscription exists
            subscription = self.subscriber.get_subscription(
                request={"subscription": self.subscription_path}
            )
            logger.info(f"✅ Pub/Sub subscription exists: {subscription.name}")
        except Exception as e:
            logger.error(f"❌ Pub/Sub subscription test failed: {e}")
            return False
        
        # Test Gmail API
        if self.gmail_service:
            try:
                profile = self.gmail_service.users().getProfile(userId='me').execute()
                logger.info(f"✅ Gmail API working for {profile.get('emailAddress')}")
            except Exception as e:
                logger.error(f"❌ Gmail API test failed: {e}")
                return False
        else:
            logger.error("❌ Gmail service not initialized")
            return False
        
        return True

def main():
    """Main function to run the listener"""
    logger.info("🚀 Starting Gmail Pub/Sub Listener Service")
    
    # Create and test listener
    listener = GmailPubSubListener()
    
    # Test connections first
    if not listener.test_connection():
        logger.error("❌ Connection tests failed, exiting")
        return
    
    # Start listening
    try:
        listener.start_listening()
    except KeyboardInterrupt:
        logger.info("🛑 Service stopped by user")
    except Exception as e:
        logger.error(f"❌ Service error: {e}")

if __name__ == "__main__":
    main()
"""
BigQuery utility tools for SDR results.
"""
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
import os
import uuid

from typing import Dict, Any, List
from google.adk.tools import FunctionTool
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from ..config import PROJECT, DATASET_ID, TABLE_ID

logger = logging.getLogger(__name__)

def _write_json_file(filepath: Path, data: Dict[str, Any]) -> None:
    """Helper function to write JSON data to file."""
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


async def sdr_bigquery_upload(
    business_data: Dict[str, Any],
    proposal: str,
    call_category: Dict[str, Any],
) -> dict[str, Any]:
    """
    BigQuery upload tool for SDR results.
    
    Args:
        business_data: The original business lead data
        proposal: The generated proposal that was sent to the business owner to discuss on the phone call
        call_category: The resulted call category from the conversation classifier agent
        
    Returns:
        A dictionary containing upload status
    """
    
    # Create output file in current directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sdr_bigquery_upload_{timestamp}.json"
    filepath = Path(filename)
    
    # Prepare SDR record for upload
    sdr_record = {
        "timestamp": datetime.now().isoformat(),
        "business_data": business_data,
        "proposal": proposal,
        "call_category": call_category,
    }
    
    try:
        await asyncio.to_thread(_write_json_file, filepath, sdr_record)
        
        return {
            "status": "success",
            "message": f"SDR results uploaded successfully to {filename}",
            "record": sdr_record,
            "file_path": str(filepath)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error writing SDR data to file: {str(e)}"
        }


sdr_bigquery_upload_tool = FunctionTool(func=sdr_bigquery_upload)


# --- NEW: Email Engagement Table ---
ENGAGEMENT_TABLE_ID = "email_engagement"

async def bigquery_email_engagement_upload(
    recipient_email: str,
    subject: str,
    status: str,
    campaign_id: str = "default_campaign",
    notes: str = ""
) -> Dict[str, Any]:
    """
    Upload email engagement data to BigQuery.

    Args:
        recipient_email: The email address of the recipient.
        subject: The subject of the email.
        status: The engagement status (e.g., 'SENT', 'OPENED', 'CLICKED', 'REPLIED').
        campaign_id: The campaign this email belongs to.
        notes: Any additional notes.

    Returns:
        A dictionary containing upload status.
    """
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    dataset_id = os.getenv("DATASET_ID", "sdr_data")
    
    if not project:
        return {"status": "error", "message": "GOOGLE_CLOUD_PROJECT not configured"}

    try:
        client = bigquery.Client(project=project)
        table_ref = client.dataset(dataset_id).table(ENGAGEMENT_TABLE_ID)

        # Ensure table exists with the correct schema
        try:
            client.get_table(table_ref)
        except NotFound:
            schema = [
                bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("recipient_email", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("subject", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("campaign_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("notes", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            ]
            table = bigquery.Table(table_ref, schema=schema)
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp"
            )
            client.create_table(table)
            logger.info(f"Created BigQuery table: {ENGAGEMENT_TABLE_ID}")

        # Prepare data for insertion
        now = datetime.utcnow()
        row_to_insert = {
            "event_id": str(uuid.uuid4()),
            "recipient_email": recipient_email,
            "subject": subject,
            "status": status,
            "campaign_id": campaign_id,
            "notes": notes,
            "timestamp": now.isoformat() + 'Z',
        }
        
        errors = client.insert_rows_json(table_ref, [row_to_insert])
        if errors:
            logger.error(f"BigQuery insertion errors for engagement: {errors}")
            return {"status": "error", "message": f"Failed to insert engagement data: {errors}"}

        logger.info(f"Successfully uploaded email engagement data for {recipient_email}")
        return {"status": "success", "message": "Email engagement data uploaded successfully."}

    except Exception as e:
        logger.error(f"Error in bigquery_email_engagement_upload: {e}")
        return {"status": "error", "message": str(e)}

# --- NEW: Function Tool for Email Engagement ---
bigquery_email_engagement_tool = FunctionTool(func=bigquery_email_engagement_upload)


# --- NEW: Accepted Offers Table ---
ACCEPTED_OFFERS_TABLE_ID = "accepted_offers"

async def bigquery_accepted_offer_upload(
    business_name: str,
    business_id: str,
    contact_email: str,
    offer_details: str,
    notes: str = ""
) -> Dict[str, Any]:
    """
    Upload accepted offer data to BigQuery.

    Args:
        business_name: The name of the business.
        business_id: The unique ID of the business (e.g., place_id).
        contact_email: The primary contact email.
        offer_details: A description of the accepted offer.
        notes: Any additional notes about the acceptance.

    Returns:
        A dictionary containing upload status.
    """
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    dataset_id = os.getenv("DATASET_ID", "sdr_data")
    
    if not project:
        return {"status": "error", "message": "GOOGLE_CLOUD_PROJECT not configured"}

    try:
        client = bigquery.Client(project=project)
        table_ref = client.dataset(dataset_id).table(ACCEPTED_OFFERS_TABLE_ID)

        try:
            client.get_table(table_ref)
        except NotFound:
            schema = [
                bigquery.SchemaField("acceptance_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("business_name", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("business_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("contact_email", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("offer_details", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("notes", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            ]
            table = bigquery.Table(table_ref, schema=schema)
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp"
            )
            client.create_table(table)
            logger.info(f"Created BigQuery table: {ACCEPTED_OFFERS_TABLE_ID}")

        now = datetime.utcnow()
        row_to_insert = {
            "acceptance_id": str(uuid.uuid4()),
            "business_name": business_name,
            "business_id": business_id,
            "contact_email": contact_email,
            "offer_details": offer_details,
            "notes": notes,
            "timestamp": now.isoformat() + 'Z',
        }
        
        errors = client.insert_rows_json(table_ref, [row_to_insert])
        if errors:
            logger.error(f"BigQuery insertion errors for accepted offer: {errors}")
            return {"status": "error", "message": f"Failed to insert accepted offer data: {errors}"}

        logger.info(f"Successfully uploaded accepted offer for {business_name}")
        return {"status": "success", "message": "Accepted offer data uploaded successfully."}

    except Exception as e:
        logger.error(f"Error in bigquery_accepted_offer_upload: {e}")
        return {"status": "error", "message": str(e)}

# --- NEW: Function Tool for Accepted Offers ---
bigquery_accepted_offer_tool = FunctionTool(func=bigquery_accepted_offer_upload)
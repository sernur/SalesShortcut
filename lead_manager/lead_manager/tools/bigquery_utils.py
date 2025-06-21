"""
BigQuery utility tools for Lead Manager.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from google.adk.tools import FunctionTool
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from ..config import PROJECT, DATASET_ID, TABLE_ID, MEETING_TABLE_ID

logger = logging.getLogger(__name__)


# TODO(sergazy): Implement these
def _write_json_file(filepath: Path, data: Dict[str, Any]) -> None:
    """Helper function to write JSON data to file."""
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    
    # Custom JSON encoder to handle datetime objects
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return super().default(obj)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False, cls=DateTimeEncoder)

async def check_hot_lead(email_address: str) -> Optional[Dict[str, Any]]:
    """
    Checks if an email address belongs to a hot lead by querying the SDR results table.
    A hot lead is defined as a lead with a status of 'SUCCESS' or 'NEEDS_FOLLOW_UP'.
    
    Args:
        email_address: The email address to check.
        
    Returns:
        A dictionary containing the lead data if found, otherwise None.
    """
    try:
        logger.info(f"🔍 Checking if {email_address} is a hot lead...")
        
        client = bigquery.Client(project=PROJECT)
        
        # Correctly query the sdr_results table from the sdr_data dataset
        sdr_dataset_id = "sdr_data"
        sdr_table_id = "sdr_results"
        
        query = f"""
            SELECT *
            FROM `{PROJECT}.{sdr_dataset_id}.{sdr_table_id}`
            WHERE LOWER(contact_email) = LOWER(@email_address)
              AND call_category IN ('SUCCESS', 'NEEDS_FOLLOW_UP')
            ORDER BY timestamp DESC
            LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("email_address", "STRING", email_address),
            ]
        )
        
        query_job = client.query(query, job_config=job_config)
        results = list(query_job)
        
        if not results:
            logger.info(f"❌ {email_address} is not a hot lead.")
            return None
        
        lead_data = dict(results[0])
        logger.info(f"✅ Found hot lead: {email_address}")
        return lead_data
        
    except Exception as e:
        logger.error(f"❌ Error checking hot lead status for {email_address}: {e}")
        return None

async def save_meeting_arrangement(
    lead_data: Dict[str, Any],
    meeting_data: Dict[str, Any],
    email_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Save meeting arrangement data to BigQuery.
    
    Args:
        lead_data: Hot lead information
        meeting_data: Meeting details and results
        email_data: Original email that triggered the meeting
        
    Returns:
        Dictionary containing upload status
    """
    try:
        logger.info("💾 Saving meeting arrangement to BigQuery...")
        
        # Create output file for backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"lead_manager_meeting_{timestamp}.json"
        filepath = Path(filename)
        
        # Prepare meeting record
        meeting_record = {
            "timestamp": datetime.now().isoformat(),
            "lead_email": lead_data.get("email", ""),
            "lead_name": lead_data.get("name", ""),
            "lead_company": lead_data.get("company", ""),
            "lead_phone": lead_data.get("phone", ""),
            "meeting_id": meeting_data.get("meeting_id", ""),
            "meeting_title": meeting_data.get("title", ""),
            "meeting_date": meeting_data.get("start_time", ""),
            "meeting_link": meeting_data.get("meet_link", ""),
            "meeting_duration": meeting_data.get("duration", 60),
            "original_email_subject": email_data.get("subject", ""),
            "original_email_date": email_data.get("date", ""),
            "original_message_id": email_data.get("message_id", ""),
            "status": "arranged",
            "agent_type": "lead_manager"
        }
        
        # Write backup file
        backup_data = {
            "meeting_record": meeting_record,
            "full_lead_data": lead_data,
            "full_meeting_data": meeting_data,
            "full_email_data": email_data
        }
        await asyncio.to_thread(_write_json_file, filepath, backup_data)
        
        # Initialize BigQuery client
        client = bigquery.Client(project=PROJECT)
        
        # Get table reference and ensure it exists
        table_ref = client.dataset(DATASET_ID).table(MEETING_TABLE_ID)

        # Define target schema
        target_schema = [
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("lead_email", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("lead_name", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("lead_company", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("lead_phone", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("meeting_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("meeting_title", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("meeting_date", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("meeting_link", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("meeting_duration", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("original_email_subject", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("original_email_date", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("original_message_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("status", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("agent_type", "STRING", mode="NULLABLE"),
        ]

        try:
            table = client.get_table(table_ref)
            logger.info(f"Found existing table {MEETING_TABLE_ID}")
            
            # Check for missing fields
            current_field_names = {field.name for field in table.schema}
            target_field_names = {field.name for field in target_schema}
            missing_fields = target_field_names - current_field_names
            
            if missing_fields:
                logger.info(f"Adding missing fields to table: {missing_fields}")
                new_schema = list(table.schema)
                for field in target_schema:
                    if field.name in missing_fields:
                        new_schema.append(field)
                table.schema = new_schema
                table = client.update_table(table, ["schema"])
                logger.info("Schema updated successfully")
                
        except NotFound:
            logger.info(f"Table {MEETING_TABLE_ID} not found. Creating table...")
            table = bigquery.Table(table_ref, schema=target_schema)
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp"
            )
            client.create_table(table)
            logger.info(f"✅ Table {MEETING_TABLE_ID} created.")

        # Insert row
        rows_to_insert = [meeting_record]
        errors = client.insert_rows_json(table, rows_to_insert)
        
        if errors:
            logger.error(f"❌ BigQuery insert errors: {errors}")
            return {
                "success": False,
                "errors": errors,
                "backup_file": str(filepath),
                "message": f"Failed to upload to BigQuery but backup saved to {filepath}"
            }
        
        logger.info("✅ Meeting arrangement saved to BigQuery successfully")
        return {
            "success": True,
            "meeting_id": meeting_record["meeting_id"],
            "backup_file": str(filepath),
            "message": "Meeting arrangement saved successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Error saving meeting arrangement: {e}")
        
        # Try to save backup file even if BigQuery fails
        try:
            backup_data = {
                "error": str(e),
                "meeting_record": meeting_record if 'meeting_record' in locals() else {},
                "lead_data": lead_data,
                "meeting_data": meeting_data,
                "email_data": email_data
            }
            _write_json_file(filepath, backup_data)
            backup_message = f"Backup saved to {filepath}"
        except:
            backup_message = "Could not save backup file"
        
        return {
            "success": False,
            "error": str(e),
            "backup_file": str(filepath) if 'filepath' in locals() else None,
            "message": f"Error saving meeting arrangement: {str(e)}. {backup_message}"
        }

# Create the tools
check_hot_lead_tool = FunctionTool(func=check_hot_lead)

save_meeting_tool = FunctionTool(func=save_meeting_arrangement)
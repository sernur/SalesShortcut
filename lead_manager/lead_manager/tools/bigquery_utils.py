"""
BigQuery utility tools for Lead Manager.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from google.adk.tools import FunctionTool
from google.cloud import bigquery
from ..config import PROJECT, DATASET_ID, TABLE_ID, MEETING_TABLE_ID

logger = logging.getLogger(__name__)


# TODO(sergazy): Implement these
def _write_json_file(filepath: Path, data: Dict[str, Any]) -> None:
    """Helper function to write JSON data to file."""
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

async def check_hot_lead(email_address: str) -> bool:
    """
    Check if an email address is in the hot leads database.
    
    Args:
        email_address: Email address to check
        
    Returns:
        bool indicating if the email is a hot lead or not, along with lead data if found.
    """
    
    # Sleep for 2 sec
    await asyncio.sleep(2)
    if email_address.lower() == "meinnps@gmail.com":
        logger.info(f"✅ {email_address} is a hot lead (mocked for testing)")
        return True
    else:
        return False
    # try:
    #     logger.info(f"🔍 Checking if {email_address} is a hot lead...")
        
    #     # Initialize BigQuery client
    #     client = bigquery.Client(project=PROJECT)
        
    #     # Query to check if email exists in hot leads table
    #     query = f"""
    #     SELECT 
    #         *
    #     FROM `{PROJECT}.{DATASET_ID}.{TABLE_ID}`
    #     WHERE LOWER(email) = LOWER(@email_address)
    #     LIMIT 1
    #     """
        
    #     # Configure query parameters
    #     job_config = bigquery.QueryJobConfig(
    #         query_parameters=[
    #             bigquery.ScalarQueryParameter("email_address", "STRING", email_address),
    #         ]
    #     )
        
    #     # Execute query
    #     query_job = client.query(query, job_config=job_config)
    #     results = list(query_job)
        
    #     if not results:
    #         logger.info(f"❌ {email_address} is not a hot lead")
    #         return {
    #             "success": True,
    #             "is_hot_lead": False,
    #             "email": email_address,
    #             "lead_data": None,
    #             "message": f"{email_address} is not found in hot leads database"
    #         }
        
    #     # Convert BigQuery row to dictionary
    #     lead_data = dict(results[0])
        
    #     # Convert any datetime objects to strings for JSON serialization
    #     for key, value in lead_data.items():
    #         if isinstance(value, datetime):
    #             lead_data[key] = value.isoformat()
        
    #     logger.info(f"✅ {email_address} is a hot lead!")
    #     return {
    #         "success": True,
    #         "is_hot_lead": True,
    #         "email": email_address,
    #         "lead_data": lead_data,
    #         "message": f"{email_address} found in hot leads database"
    #     }
        
    # except Exception as e:
    #     logger.error(f"❌ Error checking hot lead: {e}")
    #     return {
    #         "success": False,
    #         "is_hot_lead": False,
    #         "email": email_address,
    #         "lead_data": None,
    #         "error": str(e),
    #         "message": f"Error checking hot lead status: {str(e)}"
    #     }

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
        _write_json_file(filepath, backup_data)
        
        # Initialize BigQuery client
        client = bigquery.Client(project=PROJECT)
        
        # Get table reference
        table_id = f"{PROJECT}.{DATASET_ID}.{MEETING_TABLE_ID}"
        table = client.get_table(table_id)
        
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
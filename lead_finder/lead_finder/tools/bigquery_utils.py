"""
BigQuery utility tools.
"""

from typing import Dict, Any, List
from google.adk.tools import ToolContext
from google.cloud import bigquery
from ..config import PROJECT, DATASET_ID, TABLE_ID

def bigquery_upload(data: List[dict[str, Any]], tool_context: ToolContext) -> dict[str, Any]:
    """
    BigQuery upload tool.
    
    Args:
        data: The business data to upload
        tool_context: The tool context from ADK
        
    Returns:
        A dictionary containing upload status
    """
    if not PROJECT:
        # Mock response for development or when project is not available
        num_records = len(data)
        return {
            "status": "success", 
            "message": f"[MOCK] Successfully uploaded {num_records} business records to BigQuery",
            "records_processed": num_records
        }
    
    try:
        # Create a BigQuery client
        client = bigquery.Client(project=PROJECT)
        
        # Get the table reference
        table_ref = client.dataset(DATASET_ID).table(TABLE_ID)
        
        # Load the data into BigQuery
        job_config = bigquery.LoadJobConfig()
        job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
        job_config.autodetect = True
        
        # Convert data to newline-delimited JSON
        job = client.load_table_from_json(
            data,
            table_ref,
            job_config=job_config
        )
        
        # Wait for the job to complete
        job.result()
        
        # Return the result
        return {
            "status": "success",
            "message": f"Successfully uploaded {len(data)} business records to BigQuery table {DATASET_ID}.{TABLE_ID}",
            "records_processed": len(data)
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error uploading data to BigQuery: {str(e)}"
        }


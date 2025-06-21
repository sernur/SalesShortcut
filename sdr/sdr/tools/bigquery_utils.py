"""
BigQuery utility tools for SDR results.
"""
import json
import asyncio
from datetime import datetime
from pathlib import Path

from typing import Dict, Any, List
from google.adk.tools import FunctionTool
from google.cloud import bigquery
from ..config import PROJECT, DATASET_ID, TABLE_ID

import logging
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

    logger.info("⚒️ [TOOL] Starting BigQuery upload process...")
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
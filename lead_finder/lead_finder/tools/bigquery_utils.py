"""
BigQuery utility tools.
"""
import json
import asyncio
from datetime import datetime
from pathlib import Path

from typing import Dict, Any, List
from google.adk.tools import FunctionTool
from google.cloud import bigquery
from ..config import PROJECT, DATASET_ID, TABLE_ID


# Temporary mock function to simulate BigQuery upload
def _write_json_file(filepath: Path, data: List[Dict[str, Any]]) -> None:
    """Helper function to write JSON data to file."""
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "record_count": len(data),
        "data": data
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


async def bigquery_upload(data: List[dict[str, Any]]) -> dict[str, Any]:
    """
    BigQuery upload tool.
    
    Args:
        data: The business data to upload
        
    Returns:
        A dictionary containing upload status
    """
    
    num_records = len(data)
    
    # Create output file in current directory
    timestamp = datetime.now().isoformat()
    filename = f"bigquery_upload_{timestamp}.json"
    filepath = Path(filename)
    
    try:
        await asyncio.to_thread(_write_json_file, filepath, data)
        
        return data
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error writing mock data to file: {str(e)}"
        }
            
bigquery_upload_tool = FunctionTool(func=bigquery_upload)

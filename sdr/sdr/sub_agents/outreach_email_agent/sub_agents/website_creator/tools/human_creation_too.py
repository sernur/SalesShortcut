"This module provides a tool for human creation of websites based on a given prompt."

from google.adk.tools import FunctionTool, ToolContext

import logging
logger = logging.getLogger(__name__)


async def human_creation(website_creation_prompt: str, tool_context: ToolContext) -> str:
    """
    Sends a prompt to a human for creating a website.
    
    Args:
        website_creation_prompt (str): The prompt for creating the website.
        
    Returns:
        str: An URL for the created website.
    """
    # Logic of pausing the execution and waiting for the human to creat the website
    
    # Sending the prompt to the UI via REST API
    
    # Waiting for the UI return the URL of the created website
    
    # Proceeding with the URL of the created website


request_human_input_tool = FunctionTool(func=human_creation)
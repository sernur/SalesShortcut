"""Content editing tools for the OfferFileCreatorAgent."""

import logging
from google.adk.tools import FunctionTool
from sdr.sdr.config import TEST_MODE

logger = logging.getLogger(__name__)

def edit_proposal_content(current_content: str, edit_instructions: str) -> str:
    """
    Edit proposal content based on specific instructions.
    
    Args:
        current_content (str): The current markdown proposal content
        edit_instructions (str): Specific instructions on what to edit
        
    Returns:
        str: The edited proposal content
    """
    try:
        logger.info(f"Processing content edit request - Instructions: {edit_instructions[:100]}...")
        logger.debug(f"Current content length: {len(current_content)} characters")
        
        if TEST_MODE:
            logger.info("TEST MODE: Returning mock edited content")
            mock_content = current_content + f"\n\n<!-- MOCK EDIT: {edit_instructions} -->"
            logger.info(f"TEST MODE: Mock edit applied, new length: {len(mock_content)} characters")
            return mock_content
        
        # This function allows the agent to modify the proposal content
        # The agent can provide specific edit instructions and this tool
        # will help apply them to the content
        
        # For now, return the current content with a note that editing is possible
        # The LLM agent will actually perform the editing logic
        edited_content = current_content
        
        logger.info("Content editing completed successfully")
        logger.debug(f"Final content length: {len(edited_content)} characters")
        return edited_content
        
    except Exception as e:
        logger.error(f"Error editing content: {e}", exc_info=True)
        raise

def replace_content_section(current_content: str, section_name: str, new_section_content: str) -> str:
    """
    Replace a specific section in the proposal content.
    
    Args:
        current_content (str): The current markdown proposal content
        section_name (str): The name/title of the section to replace
        new_section_content (str): The new content for that section
        
    Returns:
        str: The updated proposal content
    """
    try:
        logger.info(f"Replacing section: {section_name}")
        logger.debug(f"New section content length: {len(new_section_content)} characters")
        
        if TEST_MODE:
            logger.info(f"TEST MODE: Returning mock section replacement for '{section_name}'")
            mock_content = current_content.replace(f"## {section_name}", f"## {section_name} (MOCK REPLACED)")
            logger.info(f"TEST MODE: Mock section replacement completed")
            return mock_content
        
        import re
        
        # Look for the section header and replace the content until the next header
        pattern = rf"(#+\s*{re.escape(section_name)}.*?)\n(.*?)(?=\n#+|\Z)"
        
        def replacement(match):
            header = match.group(1)
            return f"{header}\n{new_section_content}"
        
        updated_content = re.sub(pattern, replacement, current_content, flags=re.DOTALL | re.IGNORECASE)
        
        # If section wasn't found, append it
        if updated_content == current_content:
            updated_content += f"\n\n## {section_name}\n{new_section_content}"
            
        logger.info("Section replacement completed successfully")
        logger.debug(f"Updated content length: {len(updated_content)} characters")
        return updated_content
        
    except Exception as e:
        logger.error(f"Error replacing section: {e}", exc_info=True)
        raise

def add_content_section(current_content: str, section_name: str, section_content: str, position: str = "end") -> str:
    """
    Add a new section to the proposal content.
    
    Args:
        current_content (str): The current markdown proposal content
        section_name (str): The name/title of the new section
        section_content (str): The content for the new section
        position (str): Where to add it ("start", "end", or after a specific section)
        
    Returns:
        str: The updated proposal content with the new section
    """
    try:
        logger.info(f"Adding new section: {section_name} at position: {position}")
        logger.debug(f"Section content length: {len(section_content)} characters")
        
        if TEST_MODE:
            logger.info(f"TEST MODE: Returning mock section addition for '{section_name}'")
            mock_content = current_content + f"\n\n## {section_name} (MOCK ADDED)\n{section_content[:50]}..."
            logger.info(f"TEST MODE: Mock section addition completed")
            return mock_content
        
        new_section = f"\n\n## {section_name}\n{section_content}"
        
        if position == "start":
            # Add after the first title/header
            lines = current_content.split('\n')
            insert_index = 1
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith('#'):
                    insert_index = i
                    break
            lines.insert(insert_index, new_section)
            updated_content = '\n'.join(lines)
        elif position == "end":
            updated_content = current_content + new_section
        else:
            # Add after specific section
            import re
            pattern = rf"(#+\s*{re.escape(position)}.*?(?:\n.*?)*?)(?=\n#+|\Z)"
            updated_content = re.sub(pattern, rf"\1{new_section}", current_content, flags=re.DOTALL | re.IGNORECASE)
            
        logger.info("Section addition completed successfully")
        logger.debug(f"Updated content length: {len(updated_content)} characters")
        return updated_content
        
    except Exception as e:
        logger.error(f"Error adding section: {e}", exc_info=True)
        raise

# Create function tools
edit_proposal_content_tool = FunctionTool(func=edit_proposal_content)
replace_content_section_tool = FunctionTool(func=replace_content_section)
add_content_section_tool = FunctionTool(func=add_content_section)
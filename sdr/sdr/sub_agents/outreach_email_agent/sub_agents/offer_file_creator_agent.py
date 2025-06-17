"""LllmAgnet that creates an offer file for the OutreachEmailAgent."""
from google.adk.agents.llm_agent import LlmAgent
from sdr.sdr.config import MODEL
from ..outreach_email_prompt import OFFER_FILE_CREATOR_PROMPT
from ..tools.offer_file_tools import create_offer_file


offer_file_creator_agent = LlmAgent(
    name="OfferFileCreatorAgent",
    description="Agent that creates a commercial offer file based on refined requirements and quality checks",
    model=MODEL,
    instruction=OFFER_FILE_CREATOR_PROMPT,
    tools=[create_offer_file],
    output_key="offer_file_path"
)
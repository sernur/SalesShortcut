# an LlmAgent
from google.adk.agents.llm_agent import LlmAgent
from sdr.sdr.config import MODEL
from ...outreach_email_prompt import EMAIL_CRAFTER_PROMPT
from typing import Optional
from pydantic import BaseModel, Field

class CraftedEmail(BaseModel):
    to: str = Field(description="The recipient email address.")
    subject: str = Field(description="The subject line of the email.")
    body: str = Field(description="The body content of the email.")
    attachment: Optional[str] = Field(
        None, 
        description="Optional attachment file path for the email."
    )


email_crafter_agent = LlmAgent(
    name="EmailCrafterAgent",
    description="Agent that crafts personalized outreach emails based on provided data.",
    model=MODEL,
    output_schema=CraftedEmail,
    instruction=EMAIL_CRAFTER_PROMPT,
    output_key="crafted_email"
)

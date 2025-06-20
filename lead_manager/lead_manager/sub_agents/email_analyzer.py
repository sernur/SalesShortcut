"""
Email Analyzer Agent for analyzing emails and identifying hot leads with meeting requests.
"""

import json
import logging
import re
from typing import AsyncGenerator, Dict, Any
from typing_extensions import override

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from ..tools.bigquery_utils import check_hot_lead

logger = logging.getLogger(__name__)

class EmailAnalyzer(BaseAgent):
    """
    A custom agent that analyzes emails to identify hot leads with meeting requests.
    Loops through emails and uses BigQuery to check if senders are hot leads.
    """

    calendar_organizer_agent: BaseAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, calendar_organizer_agent: BaseAgent):
        """
        Initializes the EmailAnalyzer.
        Args:
            name: The name of the agent.
            calendar_organizer_agent: The agent responsible for organizing calendar meetings.
        """
        # Define the sub_agents list for the framework
        sub_agents_list = [calendar_organizer_agent]

        super().__init__(
            name=name,
            calendar_organizer_agent=calendar_organizer_agent,
            sub_agents=sub_agents_list
        )

    async def _is_meeting_request_llm(self, email_data: Dict[str, Any], ctx: InvocationContext) -> dict:
        """
        Use LLM to analyze email content to determine if it's a meeting request.
        
        Args:
            email_data: Email data dictionary
            ctx: Invocation context for LLM access
            
        Returns:
            A dictionary with the calendar request data
        """
        from google.genai import GenerativeModel
        from ..config import MODEL
        from ..prompts import EMAIL_ANALYZER_PROMPT
        
        try:
            # Create the LLM prompt for meeting request analysis
            analysis_prompt = EMAIL_ANALYZER_PROMPT.format(**email_data)

            # Initialize the model
            analysis_prompt = EMAIL_ANALYZER_PROMPT.format(email_data=email_data)

            # Initialize the model and generate the response
            model = GenerativeModel(MODEL)
            response = await model.generate_content_async(analysis_prompt)

            # --- PARSING AND VALIDATION LOGIC ---
            response_text = response.text.strip()
            
            # 1. Clean the string to remove markdown fences (e.g., ```json)
            if "```" in response_text:
                match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text)
                if match:
                    response_text = match.group(1)
            
            # 2. Parse the cleaned string into a dictionary
            parsed_data = json.loads(response_text)
            
            return parsed_data
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in LLM response for {email_data.get('sender_email')}: {e}")
            return {"status": "no_meeting_request", "error": str(e)}
            
        except Exception as e:
            logger.error(f"Error in LLM meeting analysis for {email_data.get('sender_email')}: {e}")
            # Fallback to simple keyword check if LLM fails
            simple_keywords = ['meeting', 'schedule', 'call', 'discuss', 'available', 'appointment']
            email_text = f"{email_data.get('subject', '')} {email_data.get('body', '')}".lower()
            
            has_keyword = any(keyword in email_text for keyword in simple_keywords)
            logger.info(f"Fallback keyword analysis for {email_data.get('sender_email')}: {has_keyword}")
            return has_keyword

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Analyzes unread emails to identify hot leads with meeting requests.
        """
        logger.info(f"[{self.name}] Starting email analysis workflow.")

        # Get unread emails from session state
        unread_emails_data = ctx.session.state.get("unread_emails")

        if not unread_emails_data:
            logger.error(f"[{self.name}] No unread emails data found in session state.")
            yield Event(
                content=types.Content(
                    parts=[
                        types.Part(
                            text="Email analysis failed: No unread emails data found in session state."
                        )
                    ]
                ),
                author=self.name,
            )
            return

        # Parse unread emails data
        if isinstance(unread_emails_data, str):
            import json
            try:
                unread_emails_data = json.loads(unread_emails_data)
            except json.JSONDecodeError:
                logger.error(f"[{self.name}] Failed to parse unread emails data JSON.")
                yield Event(
                    content=types.Content(
                        parts=[
                            types.Part(
                                text="Email analysis failed: Invalid unread emails data format."
                            )
                        ]
                    ),
                    author=self.name,
                )
                return

        emails = unread_emails_data.get("emails", [])
        
        if not emails:
            logger.info(f"[{self.name}] No emails to analyze.")
            # Set state to indicate no action needed
            ctx.session.state["hot_lead_email"] = "no_action_needed"
            yield Event(
                content=types.Content(
                    parts=[
                        types.Part(
                            text="No emails to analyze. No action needed."
                        )
                    ]
                ),
                author=self.name,
            )
            return

        logger.info(f"[{self.name}] Analyzing {len(emails)} emails for hot leads...")

        
        for i, email_data in enumerate(emails):
            sender_email = email_data.get("sender_email", "")
            subject = email_data.get("subject", "")
            
            logger.info(f"[{self.name}] Analyzing email {i+1}/{len(emails)}: {sender_email} - {subject}")
            
            # Check if sender is a hot lead using BigQuery tool
            try:
                # Call the check_hot_lead tool function directly
                hot_lead_result = await check_hot_lead(sender_email)
                
                ctx.session.state["hot_lead_email"] = "no_action_needed"
                if hot_lead_result:
                    logger.info(f"[{self.name}] Hot lead identified: {sender_email}")
                    
                    # Check if this email contains a meeting request using LLM
                    calendar_request_data = await self._is_meeting_request_llm(email_data, ctx)

                    # If calendar_request_data['status'] == no_meeting_request skip
                    if isinstance(calendar_request_data, dict) and calendar_request_data.get("status") == "meeting_request":
                        logger.info(f"[{self.name}] Meeting request found from hot lead: {sender_email}")
                        
                        logger.info(f"[{self.name}] Triggering CalendarOrganizerAgent for hot lead meeting request...")
                        
                        ctx.session.state["calendar_request"] = calendar_request_data
                        async for event in self.calendar_organizer_agent.run_async(ctx):
                            logger.info(f"[{self.name}] Event from CalendarOrganizerAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
                            yield event
                            
                        # Stop the loop and trigger calendar organizer
                        break
                    else:
                        logger.info(f"[{self.name}]! ! ! Hot lead But {sender_email} email does not contain meeting request.")
                        ## TODO: Handle conversation with hot lead without meeting request
                else:
                    logger.info(f"[{self.name}] {sender_email} IS NOT a hot lead.")
                    
            except Exception as e:
                logger.error(f"[{self.name}] Error checking hot lead status for {sender_email}: {e}")
                continue
            # No hot lead meeting requests found
        logger.info(f"[{self.name}] No hot lead meeting requests found in {len(emails)} emails.")
        
        ctx.session.state["hot_lead_email"] = "no_action_needed"
        yield Event(
            content=types.Content(
                parts=[
                    types.Part(
                        text=f"Analyzed {len(emails)} emails. No hot lead meeting requests found."
                    )
                ]
            ),
            author=self.name,
        )

        logger.info(f"[{self.name}] Email analysis workflow finished.")
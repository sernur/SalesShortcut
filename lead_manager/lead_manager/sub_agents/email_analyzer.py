"""
Email Analyzer Agent for analyzing emails and identifying hot leads with meeting requests.
"""

import logging
from typing import AsyncGenerator, Dict, Any
from typing_extensions import override

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from ..tools.bigquery_utils import check_hot_lead_tool

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

    async def _is_meeting_request_llm(self, email_data: Dict[str, Any], ctx: InvocationContext) -> bool:
        """
        Use LLM to analyze email content to determine if it's a meeting request.
        
        Args:
            email_data: Email data dictionary
            ctx: Invocation context for LLM access
            
        Returns:
            True if the email appears to be a meeting request
        """
        from google.genai import GenerativeModel
        from ..config import MODEL
        
        try:
            # Create the LLM prompt for meeting request analysis
            analysis_prompt = f"""
You are an expert email analyzer. Analyze the following email to determine if it contains a meeting request or scheduling inquiry.

Email Details:
From: {email_data.get('sender', 'Unknown')}
Subject: {email_data.get('subject', 'No Subject')}
Body: {email_data.get('body', 'No body content')}

Instructions:
1. Analyze the email content for meeting requests, scheduling inquiries, or appointment requests
2. Look for explicit requests like "Can we schedule a meeting?", "Are you available for a call?", etc.
3. Look for implied requests like "I'd like to discuss", "Let's talk about", "When would be a good time", etc.
4. Consider time-related references and availability questions
5. Consider demo requests, consultation requests, or "let's connect" type messages
6. Ignore automated emails, newsletters, or purely informational messages

Respond with ONLY "YES" if this email contains a meeting/scheduling request, or "NO" if it does not.

Response:"""
            
            # Initialize the model
            model = GenerativeModel(MODEL)
            
            # Generate response
            response = model.generate_content(analysis_prompt)
            
            # Parse the response
            response_text = response.text.strip().upper()
            
            is_meeting_request = response_text == "YES"
            
            logger.info(f"LLM analysis for {email_data.get('sender_email')}: {response_text} -> {is_meeting_request}")
            
            return is_meeting_request
            
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

        # Loop through emails to find hot leads with meeting requests
        hot_lead_email_found = None
        
        for i, email_data in enumerate(emails):
            sender_email = email_data.get("sender_email", "")
            subject = email_data.get("subject", "")
            
            logger.info(f"[{self.name}] Analyzing email {i+1}/{len(emails)}: {sender_email} - {subject}")
            
            # Check if sender is a hot lead using BigQuery tool
            try:
                # Call the check_hot_lead tool function directly
                hot_lead_result = await check_hot_lead_tool.func(sender_email)
                
                if hot_lead_result.get("is_hot_lead", False):
                    logger.info(f"[{self.name}] Hot lead identified: {sender_email}")
                    
                    # Check if this email contains a meeting request using LLM
                    if await self._is_meeting_request_llm(email_data, ctx):
                        logger.info(f"[{self.name}] Meeting request found from hot lead: {sender_email}")
                        
                        # Store the hot lead email and lead data for processing
                        hot_lead_email_found = {
                            "email_data": email_data,
                            "lead_data": hot_lead_result.get("lead_data", {}),
                            "sender_email": sender_email
                        }
                        
                        # Store in session state
                        ctx.session.state["hot_lead_email"] = hot_lead_email_found
                        
                        yield Event(
                            content=types.Content(
                                parts=[
                                    types.Part(
                                        text=f"Hot lead meeting request identified from {sender_email}. Proceeding to calendar organization."
                                    )
                                ]
                            ),
                            author=self.name,
                        )
                        
                        # Stop the loop and trigger calendar organizer
                        break
                    else:
                        logger.info(f"[{self.name}] Hot lead {sender_email} email does not contain meeting request.")
                else:
                    logger.info(f"[{self.name}] {sender_email} is not a hot lead.")
                    
            except Exception as e:
                logger.error(f"[{self.name}] Error checking hot lead status for {sender_email}: {e}")
                continue

        # If we found a hot lead email with meeting request, trigger calendar organizer
        if hot_lead_email_found:
            logger.info(f"[{self.name}] Triggering CalendarOrganizerAgent for hot lead meeting request...")
            async for event in self.calendar_organizer_agent.run_async(ctx):
                logger.info(f"[{self.name}] Event from CalendarOrganizerAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
                yield event
        else:
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
"""
Email Analyzer Agent for analyzing emails and identifying hot leads with meeting requests.
Fixed version with robust JSON parsing, updated imports, and complete Event objects.
"""
import json
import logging
import re
from typing import AsyncGenerator, Dict, Any
from typing_extensions import override

# --- FIX 1, PART A: Move imports to the top of the file ---
import google.generativeai as genai
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from ..tools.bigquery_utils import check_hot_lead
from ..config import MODEL # Assuming MODEL and PROMPT are in your config
from ..prompts import EMAIL_ANALYZER_PROMPT

logger = logging.getLogger(__name__)

def parse_llm_json_output(raw_data: str) -> dict:
    """
    Extracts and parses a JSON object from a raw string,
    which might include markdown code fences.
    """
    if not isinstance(raw_data, str):
        if isinstance(raw_data, dict): return raw_data
        raise TypeError(f"Expected a string to parse, but got {type(raw_data)}")

    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw_data)
    if match:
        json_str = match.group(1)
    else:
        json_str = raw_data

    try:
        return json.loads(json_str.strip())
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON: {e}")
        raise ValueError("Could not parse the extracted JSON string.") from e


class EmailAnalyzer(BaseAgent):
    """
    A custom agent that analyzes emails to identify hot leads with meeting requests.
    """
    calendar_organizer_agent: BaseAgent
    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, calendar_organizer_agent: BaseAgent):
        sub_agents_list = [calendar_organizer_agent]
        super().__init__(
            name=name,
            calendar_organizer_agent=calendar_organizer_agent,
            sub_agents=sub_agents_list
        )

    async def _is_meeting_request_llm(self, email_data: Dict[str, Any], ctx: InvocationContext) -> dict:
        """
        Use LLM to analyze email content to determine if it's a meeting request.
        """
        sender_email = email_data.get('sender_email_address', email_data.get('sender_email', 'unknown'))
        
        try:
            analysis_prompt = EMAIL_ANALYZER_PROMPT.format(email_data=email_data)
            
            combined_schema = {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["meeting_request", "no_meeting_request"]},
                        "title": {"type": "string"}, "description": {"type": "string"},
                        "start_datetime": {"type": "string"}, "end_datetime": {"type": "string"},
                        "attendees": {"type": "array", "items": {"type": "string"}}
                    }, "required": ["status"], "additionalProperties": False
            }
            
            # --- FIX 1, PART B: Use the imported 'genai' module ---
            model = genai.GenerativeModel(MODEL)
            response = await model.generate_content_async(
                analysis_prompt,
                generation_config={"response_schema": combined_schema, "response_mime_type": "application/json"}
            )
            
            raw_response = response.candidates[0].content.parts[0].text
            return json.loads(raw_response)
        
        except Exception as e:
            # This block now correctly handles real runtime errors, not ImportErrors
            logger.error(f"[{self.name}] Error in LLM meeting analysis for {sender_email}: {e}")
            simple_keywords = ['meeting', 'schedule', 'call', 'discuss', 'available', 'appointment']
            email_text = f"{email_data.get('subject_line', '')} {email_data.get('body_content', '')}".lower()
            
            if any(keyword in email_text for keyword in simple_keywords):
                return {"status": "meeting_request", "fallback": True, "title": f"Meeting with {sender_email}"}
            else:
                return {"status": "no_meeting_request", "fallback": True}

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        logger.info(f"[{self.name}] Starting email analysis workflow.")
        unread_emails_data = ctx.session.state.get("unread_emails")

        if not unread_emails_data:
            # --- FIX 2: Add author to all Event yields ---
            yield Event(content=types.Content(parts=[types.Part(text="No unread emails data found.")], author=self.name))
            return

        try:
            unread_emails_dict = parse_llm_json_output(unread_emails_data)
        except (ValueError, TypeError) as e:
            logger.error(f"[{self.name}] Failed to parse unread emails data: {e}")
            ctx.session.state["meeting_result"] = "parsing_failed"
            # --- FIX 2: Add author to all Event yields ---
            yield Event(
                content=types.Content(parts=[types.Part(text=f"Email analysis failed: {e}")]),
                author=self.name,
            )
            return

        emails_list = unread_emails_dict.get("unread_emails", [])
        if not emails_list:
            ctx.session.state["meeting_result"] = "no_action_needed"
            # --- FIX 2: Add author to all Event yields ---
            yield Event(content=types.Content(parts=[types.Part(text="No unread emails found to analyze.")], author=self.name))
            return

        logger.info(f"[{self.name}] Analyzing {len(emails_list)} emails for hot leads...")
        hot_leads_found = 0
        meeting_requests_found = 0

        for email_data in emails_list:
            sender_email = email_data.get("sender_email_address", "")
            if not sender_email: continue

            try:
                # The logic inside this try/except is now correct
                if await check_hot_lead(sender_email):
                    hot_leads_found += 1
                    logger.info(f"[{self.name}] Hot lead identified: {sender_email}")
                    
                    calendar_request_data = await self._is_meeting_request_llm(email_data, ctx)
                    if calendar_request_data.get("status") == "meeting_request":
                        meeting_requests_found += 1
                        logger.info(f"[{self.name}] Meeting request found from hot lead: {sender_email}")
                        
                        ctx.session.state["calendar_request"] = calendar_request_data
                        ctx.session.state["hot_lead_email"] = email_data
                        ctx.session.state["meeting_result"] = "meeting_request_found"
                        
                        async for event in self.calendar_organizer_agent.run_async(ctx):
                            yield event
                        return
            except Exception as e:
                # This will catch errors during check_hot_lead or _is_meeting_request_llm
                logger.error(f"[{self.name}] Error processing email for {sender_email}: {e}", exc_info=True)
                continue

        summary_message = f"Analyzed {len(emails_list)} emails. Found {hot_leads_found} hot leads and {meeting_requests_found} meeting requests. No further action needed at this time."
        ctx.session.state["meeting_result"] = "no_meeting_requests"
        
        # --- FIX 2: Add author to all Event yields ---
        yield Event(
            content=types.Content(parts=[types.Part(text=summary_message)]),
            author=self.name,
        )
        logger.info(f"[{self.name}] Email analysis workflow finished.")
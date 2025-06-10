import json
import logging
import requests
from typing import AsyncGenerator
from pydantic import BaseModel, Field

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

class SearchInput(BaseModel):
    query: str = Field(..., description="Search query string")
    ui_client_url: str = Field(default="http://localhost:8000", description="UI Client URL for callbacks")

class LeadManagerAgent(BaseAgent):
    def __init__(self, agent_name: str = "LeadManager", **kwargs):
        super().__init__(
            name=agent_name,
            description="Simple Lead Manager Agent that sends WebSocket messages to UI client",
            **kwargs,
        )
        logger.info(f"[{self.name}] Initialized Lead Manager Agent")

    def _parse_input(self, ctx: InvocationContext) -> SearchInput | None:
        """Parse and validate input from the context."""
        invocation_id_short = ctx.invocation_id[:8]
        logger.debug(f"[{self.name} ({invocation_id_short})] Parsing input...")
        
        if (
            not ctx.user_content
            or not ctx.user_content.parts
            or not hasattr(ctx.user_content.parts[0], "text")
        ):
            logger.error(f"[{self.name} ({invocation_id_short})] No input text found")
            return None

        input_text = ctx.user_content.parts[0].text
        try:
            input_data = json.loads(input_text)
            validated_input = SearchInput(**input_data)
            logger.info(f"[{self.name} ({invocation_id_short})] Successfully parsed input: {validated_input.query}")
            return validated_input
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name} ({invocation_id_short})] JSON decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"[{self.name} ({invocation_id_short})] Input validation error: {e}")
            return None

    async def send_websocket_message(self, ui_client_url: str, message: str, invocation_id: str):
        """Send message to UI client via webhook endpoint."""
        try:
            payload = {
                "message": message,
                "agent": "lead_manager",
                "invocation_id": invocation_id
            }
            
            response = requests.post(
                f"{ui_client_url}/webhook/lead_manager",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"[{self.name}] Successfully sent WebSocket message: {message}")
                return True
            else:
                logger.error(f"[{self.name}] Failed to send message: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.name}] Error sending WebSocket message: {e}")
            return False

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        invocation_id_short = ctx.invocation_id[:8]
        logger.info(f"[{self.name} ({invocation_id_short})] >>> Lead Manager Agent START <<<")

        # Parse input
        search_input = self._parse_input(ctx)
        if search_input is None:
            yield Event(
                author=self.name,
                content=genai_types.Content(
                    parts=[genai_types.Part(text="Error: Invalid input format")]
                ),
            )
            return

        # Send initial processing message
        yield Event(
            author=self.name,
            content=genai_types.Content(
                parts=[genai_types.Part(text=f"Processing search query: {search_input.query}")]
            ),
        )

        # Send WebSocket message to UI client
        websocket_message = f"Hello I am Lead Manager - Processing: {search_input.query}"
        success = await self.send_websocket_message(
            search_input.ui_client_url, 
            websocket_message, 
            ctx.invocation_id
        )

        if success:
            yield Event(
                author=self.name,
                content=genai_types.Content(
                    parts=[genai_types.Part(text="Successfully sent WebSocket message to UI client")]
                ),
            )
        else:
            yield Event(
                author=self.name,
                content=genai_types.Content(
                    parts=[genai_types.Part(text="Failed to send WebSocket message to UI client")]
                ),
            )

        logger.info(f"[{self.name} ({invocation_id_short})] >>> Lead Manager Agent END <<<")

# Create the root agent instance
root_agent = LeadManagerAgent()
logger.info("Lead Manager root_agent instance created")
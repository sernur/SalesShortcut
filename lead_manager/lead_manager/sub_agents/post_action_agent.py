"""
Post Action Agent for handling post-meeting arrangement tasks.
"""

from google.adk.agents.llm_agent import LlmAgent

from ..config import MODEL
from ..prompts import POST_ACTION_PROMPT
from ..tools.ui_notification import notify_meeting_tool
from ..tools.check_email import mark_email_read_tool
from ..tools.bigquery_utils import save_meeting_tool

post_action_agent = LlmAgent(
    model=MODEL,
    name="PostActionAgent",
    description="Agent that handles post-meeting arrangement tasks like UI notifications and email marking",
    instruction=POST_ACTION_PROMPT,
    tools=[notify_meeting_tool, mark_email_read_tool, save_meeting_tool],
    output_key="notification_result"
)
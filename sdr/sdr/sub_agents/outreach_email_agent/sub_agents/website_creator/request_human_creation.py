from google.adk.agents.llm_agent import LlmAgent
from .tools.human_creation_tool import request_human_input_tool
from sdr.sdr.config import MODEL

def _skip_human_creation_if_exists(tool, args, tool_context):
    # Skip invoking human_creation if a preview link is already present
    existing = tool_context.state.get("website_preview_link", "")
    if existing:
        return existing
    return None


request_URL = LlmAgent(
    name="RequestHumanApproval",
    model=MODEL,
    # Prompt model to call human_creation for website prototype
    instruction=(
        "Read the prompt from state['website_creation_prompt'] and invoke the human_creation tool "
        "to request a demo website prototype. Do not output any other text; return only the function call."
    ),
    tools=[request_human_input_tool],
    before_tool_callback=_skip_human_creation_if_exists,
    output_key="website_preview_link"
)

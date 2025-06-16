#!/usr/bin/env python3
"""SDR Agent Service"""
import logging
import click
import common.config as defaults

# Attempt to import A2A/ADK dependencies
try:
    import uvicorn
    from a2a.server.apps import A2AStarletteApplication
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.tasks import InMemoryTaskStore
    from a2a.types import AgentCapabilities, AgentCard, AgentSkill
    from .sdr.agent import sdr_agent
    from .agent_executor import SDRAgentExecutor
    ADK_AVAILABLE = True
except ImportError as e:
    ADK_AVAILABLE = False
    missing_dep = e

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



@click.command()
@click.option(
    "--host",
    default=defaults.DEFAULT_SDR_URL.split(":")[1].replace("//", ""),
    help="Host to bind the server to.",
)
@click.option(
    "--port",
    default=int(defaults.DEFAULT_SDR_URL.split(":")[2]),
    help="Port to bind the server to.",
)

def main(host: str, port: int):
    """Runs the SDR ADK agent as an A2A server."""
    # Fallback to simple HTTP if ADK/A2A deps missing
    if not ADK_AVAILABLE:
        logger.warning(f"!!!! SDR ADK or A2A SDK dependencies not found ({missing_dep}).")
        return

    logger.info(f"Configuring SDR A2A server...")

    try:
        agent_card = AgentCard(
            name=sdr_agent.name,
            description=sdr_agent.description,
            url=f"http://{host}:{port}",
            version="1.0.0",
            capabilities=AgentCapabilities(
                streaming=False,
                pushNotifications=False,
            ),
            defaultInputModes=['text', 'json', 'data'],
            defaultOutputModes=['text'],
            skills=[
                AgentSkill(
                    id='research_leads',
                    name='Search the internet for Leads',
                    description='Using Google Search, gather information about potential lead from the internet.',
                    examples=[
                        "Find information about business named 'Acme Corp' in San Francisco",
                        "Find information about a restaurant named 'Joe's Diner' in New York City",
                    ],
                    tags=['research', 'business'],
                ),
                AgentSkill(
                    id='proposal_generation',
                    name='Generate Proposal for Lead',
                    description='Generate a proposal for the lead based on the gathered information.',
                    examples=[
                        "Generate a proposal for 'Acme Corp' based on the gathered information",
                        "Create a proposal for 'Joe\'s Diner' to offer our services",
                    ],
                    tags=['proposal', 'business'],
                ),
                AgentSkill(
                    id='outreach_phone_caller',
                    name='Outreach Phone Caller',
                    description='Make a phone call to the lead to discuss the proposal.',
                    examples=[
                        "Call 'Acme Corp' to discuss the proposal",
                        "Make a phone call to 'Joe\'s Diner' to offer our services",
                    ],
                    tags=['outreach', 'phone'],
                ),
                AgentSkill(
                    id='lead_engagement_saver',
                    name='Lead Engagement Saver',
                    description='Save the lead engagement information for future reference.',
                    examples=[
                        "Save the engagement information for 'Acme Corp'",
                        "Store the lead details for 'Joe\'s Diner'",
                    ],
                    tags=['engagement', 'lead'],
                ),
                AgentSkill(
                    id='conversation_classifier',
                    name='Conversation Classifier',
                    description='Classify the conversation to determine the next steps.',
                    examples=[
                        "Classify the conversation with 'Acme Corp' to determine if they are interested",
                        "Analyze the conversation with 'Joe\'s Diner' to see if they want to proceed",
                    ],
                    tags=['classification', 'conversation'],
                ),
                AgentSkill(
                    id='sdr_router',
                    name='SDR Router',
                    description='Route the lead to the appropriate agent based on the conversation classification.',
                    examples=[
                        "Route the lead from 'Acme Corp' to the appropriate agent",
                        "Direct the lead from 'Joe\'s Diner' to the right team",
                    ],
                    tags=['routing', 'lead'],
                )
                
            ]
        )
    except AttributeError as e:
        logger.error(
            f"Error accessing attributes from sdr_agent: {e}. Is sdr/agent.py correct?"
        )
        raise
    try:
        agent_executor = SDRAgentExecutor()

        task_store = InMemoryTaskStore()

        request_handler = DefaultRequestHandler(agent_executor, task_store)

        app_builder = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )

        logger.info(f"Starting SDR A2A server on {host}:{port}")
        # Start the Server
        import uvicorn
        logger.info(f"Starting SDR A2A server on http://{host}:{port}/")
        uvicorn.run(app_builder.build(), host=host, port=port)
    except Exception as e:
        logger.error(f"Failed to start SDR A2A server: {e}")
        raise

if __name__ == '__main__':
    main()
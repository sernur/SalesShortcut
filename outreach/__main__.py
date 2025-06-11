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
    from .outreach.agent import outreach_agent
    from .agent_executor import OutreachAgentExecutor
    ADK_AVAILABLE = True
except ImportError as e:
    ADK_AVAILABLE = False
    missing_dep = e

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--host",
    default=defaults.DEFAULT_OUTREACH_URL.split(":")[1].replace("//", ""),
    help="Host to bind the server to.",
)
@click.option(
    "--port",
    default=int(defaults.DEFAULT_OUTREACH_URL.split(":")[2]),
    help="Port to bind the server to.",
)
def main(host: str, port: int):
    """Runs the OUTREACH ADK agent as an A2A server."""
    # Fallback to simple HTTP if ADK/A2A deps missing
    if not ADK_AVAILABLE:
        from .simple_main import run_simple
        logger.warning(f"ADK or A2A SDK dependencies not found ({missing_dep}), falling back to simple HTTP service.")
        run_simple(host, port)
        return
    logger.info(f"Configuring OUTREACH A2A server...")
    
    try:
        agent_card = AgentCard(
            name=outreach_agent.name,
            description=outreach_agent.description,
            url=f"http://{host}:{port}",
            version="1.0.0",
            capabilities=AgentCapabilities(
                streaming=False,
                pushNotifications=False,
            ),
            defaultInputModes=['text'],
            defaultOutputModes=['text'],
            skills=[
                AgentSkill(
                    id='phone_outreach',
                    name='Phone Call Outreach',
                    description='Make phone calls to leads with specific scripts and objectives to gather information or qualify prospects.',
                    examples=[
                        "Call +1-555-123-4567 to qualify the lead for our software solution",
                        "Make a phone call to +1-555-987-6543 to schedule a meeting with the prospect",
                        "Call the lead to gather information about their current challenges on +1-555-456-7890",
                    ],
                    tags=["phone", "call", "outreach", "qualification"],
                ),
                AgentSkill(
                    id='email_outreach',
                    name='Email Outreach',
                    description='Send personalized emails to prospects for initial outreach, follow-ups, or meeting invitations.',
                    examples=[
                        "Send an introductory email to john@company.com about our services",
                        "Follow up with the prospect via email about yesterday's conversation at john@company.com",
                        "Send a meeting invitation email to the qualified lead at john@company.com  ",
                    ],
                    tags=["email", "outreach", "follow-up", "meeting"],
                )
            ],
        )
    except AttributeError as e:
        logger.error(
            f"Error accessing attributes from outreach_agent: {e}. Is outreach/agent.py correct?"
        )
        raise

    try:
        agent_executor = OutreachAgentExecutor()
        
        task_store = InMemoryTaskStore()
        
        request_handler = DefaultRequestHandler(agent_executor, task_store)
        
        app_builder = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )
        
        logger.info(f"Starting OUTREACH A2A server on {host}:{port}")
        # Start the Server
        import uvicorn
    
        logger.info(f"Starting Outreach A2A server on http://{host}:{port}/")
        uvicorn.run(app_builder.build(), host=host, port=port)
            
    except Exception as e:
        logger.error(f"Failed to start OUTREACH A2A server: {e}")
        raise


if __name__ == '__main__':
    main()
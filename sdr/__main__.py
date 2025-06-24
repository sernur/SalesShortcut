#!/usr/bin/env python3
"""SDR Agent Service"""
import logging
import click
import common.config as defaults

# Attempt to import A2A/ADK dependencies
try:
    import uvicorn
    from starlette.routing import Route # <--- Import Route
    from starlette.responses import PlainTextResponse, JSONResponse # <--- Import PlainTextResponse and JSONResponse
    from starlette.requests import Request # <--- Import Request
    from a2a.server.apps import A2AStarletteApplication
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.tasks import InMemoryTaskStore
    from a2a.types import AgentCapabilities, AgentCard, AgentSkill
    from .sdr.agent import root_agent 
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
    if not ADK_AVAILABLE:
        logger.warning(f"!!!! SDR ADK or A2A SDK dependencies not found ({missing_dep}).")
        return

    logger.info(f"Configuring SDR A2A server...")

    try:
        # Pass the full URL to the AgentCard as the base for redirects
        full_agent_url = f"http://{host}:{port}"

        agent_card = AgentCard(
            name=root_agent.name,
            description=root_agent.description,
            url=full_agent_url, # <--- Ensure this is the correct base URL
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
                ),
                AgentSkill( # <--- Add Calendar Skill
                    id='check_availability', # This ID should match what CalendarToolset can do
                    name='Check Calendar Availability',
                    description="Checks a user's availability for a time using their Google Calendar",
                    tags=['calendar'],
                    examples=['Am I free from 10am to 11am tomorrow?'],
                ),
                # If you have other calendar functions expose them too
                # AgentSkill(id='create_event', name='Create Calendar Event', description='Creates an event on the user\'s Google Calendar.', tags=['calendar']),
            ]
        )
    except AttributeError as e:
        logger.error(
            f"Error accessing attributes from root_agent: {e}. Is sdr/agent.py correct?"
        )
        raise

    try:
        agent_executor = SDRAgentExecutor() # Your modified executor

        task_store = InMemoryTaskStore()
        request_handler = DefaultRequestHandler(agent_executor, task_store)

        # Initialize A2AStarletteApplication without the 'routes' argument
        # as it's not supported by its constructor.
        a2a_app_builder = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )

        # Build the underlying Starlette application instance
        app = a2a_app_builder.build() # This returns the Starlette app

        # Now, add your custom route directly to the Starlette app's routes list
        app.routes.append(
            Route(
                path='/authenticate',
                methods=['GET'],
                endpoint=lambda request: agent_executor.on_auth_callback(
                    str(request.query_params.get('state')),
                    str(request.url)
                ),
            )
        )
        # Human input callback endpoint for UI to notify agent of human response
        from sdr.sdr.sub_agents.outreach_email_agent.sub_agents.website_creator.tools.human_creation_tool import submit_human_response

        async def human_input_callback(request: Request):
            request_id = request.path_params.get('request_id')
            try:
                data = await request.json()
            except Exception:
                return JSONResponse({'status': 'failed', 'message': 'Invalid JSON'}, status_code=400)
            # Accept 'url' or 'response' fields from the human input payload
            url = data.get('url') or data.get('response')
            if not request_id or not url:
                return JSONResponse({'status': 'failed', 'message': 'Missing request_id or url'}, status_code=400)
            success = submit_human_response(request_id, url)
            if success:
                return JSONResponse({'status': 'success', 'request_id': request_id})
            return JSONResponse({'status': 'failed', 'message': 'Invalid request ID or request not pending'}, status_code=404)

        app.routes.append(
            Route(
                path='/api/human-input/{request_id}',
                methods=['POST'],
                endpoint=human_input_callback
            )
        )

        # Health check endpoint
        async def health_check(request: Request):
            """Simple health check endpoint"""
            return JSONResponse({
                'status': 'healthy',
                'message': 'SDR service is running',
                'endpoints': [
                    '/test/ui-callback',
                    '/test/human-creation',
                    '/api/human-input/{request_id}',
                    '/authenticate'
                ]
            })
        
        app.routes.append(
            Route(
                path='/health',
                methods=['GET'],
                endpoint=health_check
            )
        )

        # Test endpoints for SDR <-> UI communication testing
        from sdr.sdr.callbacks import send_sdr_update_to_ui
        from sdr.sdr.sub_agents.outreach_email_agent.sub_agents.website_creator.tools.human_creation_tool import send_ui_notification
        
        async def test_ui_callback(request: Request):
            """Test endpoint to trigger send_sdr_update_to_ui functionality"""
            try:
                # Sample business data for testing
                test_business_data = {
                    "id": "test-123",
                    "name": "Test Business Corp",
                    "address": "123 Main St, San Francisco, CA, 94105",
                    "phone": "+1234567890",
                    "email": "test@testbusiness.com"
                }
                
                # Sample email result for testing
                test_email_result = {
                    "status": "success",
                    "message": "Test email sent",
                    "crafted_email": {
                        "to": "test@testbusiness.com",
                        "subject": "Test Subject - SDR Communication Test",
                        "body": "This is a test email body to verify SDR-UI communication is working properly."
                    }
                }
                
                # Call the actual function
                success = send_sdr_update_to_ui(test_business_data, test_email_result)
                
                return JSONResponse({
                    'status': 'success' if success else 'failed',
                    'message': 'UI callback test completed',
                    'test_data': {
                        'business_data': test_business_data,
                        'email_result': test_email_result
                    },
                    'ui_callback_success': success
                })
            except Exception as e:
                logger.error(f"Test UI callback error: {e}")
                return JSONResponse({
                    'status': 'error',
                    'message': f'Test failed: {str(e)}'
                }, status_code=500)

        async def test_human_creation(request: Request):
            """Test endpoint to trigger human_creation functionality"""
            try:
                # Get test prompt from query params or use default
                prompt = request.query_params.get('prompt', 'Create a test website for communication testing between SDR and UI')
                
                # Test the send_ui_notification function (without full human_creation flow)
                test_request_id = f"test-{hash(prompt) % 100000}"
                
                # Send notification to UI
                success = await send_ui_notification(test_request_id, prompt)
                
                return JSONResponse({
                    'status': 'success' if success else 'failed',  
                    'message': 'Human creation test completed',
                    'test_data': {
                        'request_id': test_request_id,
                        'prompt': prompt
                    },
                    'ui_notification_success': success,
                    'note': 'This tests the UI notification part of human_creation. Full workflow requires actual human interaction.'
                })
            except Exception as e:
                logger.error(f"Test human creation error: {e}")
                return JSONResponse({
                    'status': 'error',
                    'message': f'Test failed: {str(e)}'
                }, status_code=500)
        
        # Add test endpoints
        app.routes.append(
            Route(
                path='/test/ui-callback',
                methods=['GET'],
                endpoint=test_ui_callback
            )
        )
        
        app.routes.append(
            Route(
                path='/test/human-creation',
                methods=['GET'], 
                endpoint=test_human_creation
            )
        )

        logger.info(f"Starting RiskGuard A2A server on http://{host}:{port}/")
        uvicorn.run(app, host=host, port=port) # Run the modified Starlette app
    except Exception as e:
        logger.error(f"Failed to start SDR A2A server: {e}")
        raise

if __name__ == "__main__":
    main()
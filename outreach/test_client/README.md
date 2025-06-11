# Outreach Agent A2A Test Client

A modern FastAPI web interface for testing the Outreach Agent with both phone calls and email messaging via A2A (Agent-to-Agent) communication.

## Features

- 📞 **Phone Call Outreach**: Test phone call functionality with custom scripts
- 📧 **Email Outreach**: Send emails with personalized subject lines and messages  
- 🚀 **A2A Communication**: Full Agent-to-Agent communication support with fallback to simple HTTP
- 🎨 **Modern UI**: Clean, responsive web interface with side-by-side forms
- ✅ **Real-time Results**: Immediate feedback with success/error indicators

## Requirements

Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

- `OUTREACH_AGENT_URL`: Base URL of the Outreach Agent service (default: `http://localhost:8083`)

## Architecture

The test client supports two communication modes:

1. **A2A Mode** (preferred): Uses Google Cloud ADK A2A SDK for agent communication
2. **Simple HTTP Mode** (fallback): Direct HTTP calls when A2A dependencies are not available

## Running

### Start the Outreach Agent (required dependency)

First, ensure the Outreach Agent is running:
```bash
# From the project root
python -m outreach --port 8083
```

### Start the Test Client

Start the test client on port 8501:
```bash
# From the outreach/test_client directory
uvicorn app:app --reload --port 8501
```

Open http://localhost:8501 in your browser to access the interface.

## Usage

### Phone Call Testing
1. Enter a phone number (e.g., `+1-555-123-4567`)
2. Write your call script or prompt
3. Click "📞 Make Phone Call"
4. View the results including call status and response

### Email Testing  
1. Enter a recipient email address
2. Write your subject line
3. Compose your email message
4. Click "📧 Send Email"
5. View the results including delivery status and tracking info

## API Endpoints

- `GET /`: Main interface with forms
- `POST /call`: Phone call submission endpoint
- `POST /email`: Email submission endpoint  
- `GET /health`: Health check endpoint

## Development

The client automatically detects A2A availability and falls back gracefully to simple HTTP if needed. This ensures compatibility across different environments while providing the full A2A experience when available.
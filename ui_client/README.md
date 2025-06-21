## 🧪 Testing UI Notifications with curl

Ensure the UI client is running (e.g. `uvicorn ui_client.main:app --reload --port 8000`) before testing.
Below are sample `curl` commands to test each type of card notification by sending a POST request to the UI client's `/agent_callback` endpoint.

1. Lead Finder (Business Card)
```bash
curl -X POST http://localhost:8000/agent_callback \
  -H 'Content-Type: application/json' \
  -d @- << 'EOF'
{
  "agent_type": "lead_finder",
  "business_id": "biz-789",
  "status": "found",
  "message": "Found business: Example Co",
  "timestamp": "2025-06-21T11:50:00",
  "data": {
    "name": "Example Co",
    "city": "Metropolis",
    "phone": "+1-555-5678",
    "email": "hello@example.com",
    "description": "A description of Example Co"
  }
}
EOF
```

2. SDR Agent (Email Outreach Card)
```bash
curl -X POST http://localhost:8000/agent_callback \
  -H 'Content-Type: application/json' \
  -d @- << 'EOF'
{
  "agent_type": "sdr",
  "business_id": "biz-123",
  "status": "contacted",
  "message": "Sent outreach email to Acme Corp",
  "timestamp": "2025-06-21T12:05:00",
  "data": {
    "name": "Acme Corp",
    "city": "Gotham",
    "phone": "+1-555-1234",
    "email": "contact@acme.com",
    "email_subject": "Outreach: Intro to SalesShortcut",
    "body_preview": "Hello, I’m reaching out regarding..."
  }
}
EOF
``
3. Lead Manager (Hot Lead Email)
```bash
curl -X POST http://localhost:8000/agent_callback \
  -H 'Content-Type: application/json' \
  -d @- << 'EOF'
{
  "agent_type": "lead_manager",
  "business_id": "hot_lead_test1",
  "status": "converting",
  "message": "Hot lead email from test@example.com",
  "timestamp": "2025-06-21T12:00:00",
  "data": {
    "sender_email": "test@example.com",
    "sender_name": "Test User",
    "subject": "Test Subject",
    "body_preview": "This is a preview of the email body...",
    "received_date": "2025-06-21T12:00:00",
    "message_id": "msg-123",
    "type": "hot_lead_email"
  }
}
EOF
```

4. Calendar Assistant (Meeting Request Notification)
```bash
curl -X POST http://localhost:8000/agent_callback \
  -H 'Content-Type: application/json' \
  -d @- << 'EOF'
{
  "agent_type": "calendar",
  "business_id": "biz-1000",
  "status": "meeting_scheduled",
  "message": "Incoming meeting request for TestCo",
  "timestamp": "2025-06-21T13:05:00",
  "data": {
    "status": "meeting_request",
    "title": "Intro Call with TestCo",
    "description": "Looking forward to discussing your product feature roadmap...",
    "start_datetime": "2025-06-22T10:00:00-06:00",
    "end_datetime": "2025-06-22T10:45:00-06:00",
    "attendees": ["info@testco.com", "sales@zemzen.org"]
  }
}
EOF
```
# SalesShortcut UI Client

A modern, real-time web dashboard for managing AI-powered sales lead generation and qualification workflows. This application provides a centralized interface to monitor and control multiple sales agents working together to find, qualify, and schedule meetings with potential customers.

## 🚀 Features

- **Real-time Dashboard**: Live updates via WebSocket for instant visibility into sales agent activities
- **Multi-Agent Workflow**: Orchestrates Lead Finder, SDR, Lead Manager, and Calendar Assistant agents
- **City-based Lead Generation**: Target specific cities for focused lead discovery
- **Status Tracking**: Track leads through the entire sales funnel from discovery to meeting scheduling
- **Activity Logging**: Comprehensive logging of all agent activities and lead interactions
- **Responsive Design**: Modern, mobile-friendly interface with intuitive navigation
- **A2A Integration**: Seamless communication with sales agents using A2A (Agent-to-Agent) protocol

## 📋 Table of Contents

- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## 🏗️ Architecture

The UI Client serves as the central orchestration point for the SalesShortcut platform:
```txt
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Input    │───▶│   UI Client      │───▶│  Lead Finder    │
│   (City Name)   │    │   (Dashboard)    │    │     Agent       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
│                         │
▼                         ▼
┌──────────────────┐    ┌─────────────────┐
│   WebSocket      │    │      SDR        │
│   Updates        │    │     Agent       │
└──────────────────┘    └─────────────────┘
│                         │
▼                         ▼
┌──────────────────┐    ┌─────────────────┐
│   Real-time      │    │  Lead Manager   │
│   Dashboard      │    │     Agent       │
└──────────────────┘    └─────────────────┘
│
▼
┌─────────────────┐
│ Calendar Agent  │
│   (Meetings)    │
└─────────────────┘
 ```
### Agent Flow

1. **Lead Finder Agent**: Discovers potential businesses in target cities
2. **SDR Agent**: Engages with prospects and qualifies their interest
3. **Lead Manager Agent**: Converts qualified leads into sales opportunities
4. **Calendar Assistant**: Schedules meetings with hot prospects

### Data Models

- **Business**: Core entity representing a potential customer
- **Agent Update**: Status updates from agents about business interactions
- **WebSocket Events**: Real-time communication for dashboard updates

## 🛠️ Installation

### Prerequisites

- Python 3.9+
- Node.js 16+ (for frontend assets, if needed)
- Google API Key (for Gemini LLM inference)
- Running sales agent services

### Local Development Setup

1. **Clone the repository**:
```bash
   git clone <repository-url>
   cd salesshortcut
```

2. Install Python dependencies:
```bash
   pip install -r requirements.txt
```
3. Set environment variables:
```bash
export GOOGLE_API_KEY="your-google-api-key"

# Optional: Override default service URLs
export LEAD_FINDER_SERVICE_URL="http://localhost:8081"
export SDR_SERVICE_URL="http://localhost:8084"
export LEAD_MANAGER_SERVICE_URL="http://localhost:8001"
export CALENDAR_ASSISTANT_SERVICE_URL="http://localhost:8080"
```
4. Start the application:
```bash
# Using the module
python -m ui_client

# Or with custom configuration
python -m ui_client --port 8000 --reload --log-level DEBUG
```

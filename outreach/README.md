# Outreach Agent

The Outreach Agent is a specialized ADK agent for conducting sales outreach activities including phone calls and email messaging. It's designed as an internal agent that provides outreach services to other agents in the SalesShortcut ecosystem.

## Features

### =' Core Capabilities
- **Phone Call Outreach**: Make real phone calls using ElevenLabs Conversational AI
- **Email Messaging**: Send personalized emails with dynamic content
- **Phone Number Validation**: Automatic US phone number validation and normalization
- **Transcript Analysis**: Extract and analyze conversation transcripts
- **A2A Integration**: Full Agent-to-Agent communication support
- **UI Callbacks**: Real-time updates to the SalesShortcut dashboard

### 📞 Phone Call Features
- **Real Calls**: Uses ElevenLabs Conversational AI for actual phone conversations
- **Mock Fallback**: Automatic fallback to realistic mock calls for testing
- **Simplified Interface**: Only requires `destination` and `prompt` parameters
- **Automatic Categorization**: Categorizes calls into 3 predefined outcomes
- **Conversation Polling**: Real-time monitoring of call status and completion
- **Transcript Extraction**: Full conversation capture with role identification
- **Smart Analysis**: Analyzes transcript to determine call outcome category

**Call Categories:**
- `agreed_for_getting_email_proposal`: Prospect is interested and wants email proposal
- `not_interested`: Prospect is not interested in the offering
- `call_later`: Prospect wants to be called back later or needs time to think

### =� Email Features
- **Personalization**: Dynamic email content with variable substitution
- **Multiple Types**: Support for outreach, follow-up, and meeting invitation emails
- **Delivery Tracking**: Email send status and delivery confirmation
- **Template Support**: Flexible email formatting and content management

## Configuration

### Environment Variables

Create a `.env` file in the outreach directory with:

```env
# Model Configuration
MODEL=gemini-2.0-flash-lite
TEMPERATURE=0.2
TOP_P=0.95
TOP_K=40

# ElevenLabs Configuration (for real phone calls)
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_AGENT_ID=your_agent_id
ELEVENLABS_PHONE_NUMBER_ID=your_phone_number_id

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
FROM_EMAIL=your_email@gmail.com

# Legacy Twilio (optional fallback)
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_PHONE_NUMBER=your_twilio_number
```

### ElevenLabs Setup

1. **Create Account**: Sign up at [ElevenLabs](https://elevenlabs.io/)
2. **Get API Key**: Generate API key from your dashboard
3. **Create Agent**: Set up a conversational AI agent
4. **Configure Phone**: Add a phone number for outbound calls
5. **Update Config**: Add credentials to your `.env` file

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install ElevenLabs for real phone calls
pip install elevenlabs>=1.0.0
```

## Usage

### Starting the Agent

```bash
# Start the outreach agent server
python -m outreach

# Or with custom host/port
python -m outreach --host 0.0.0.0 --port 8083
```

### Agent-to-Agent Communication

The Outreach Agent accepts A2A requests with the following format:

#### Phone Call Request
```json
{
  "message": {
    "parts": [{
      "root": {
        "data": {
          "destination": "+1-555-123-4567",
          "prompt": "You are calling on behalf of SalesShortcut and offering lead generation automation services because of their outdated manual processes. You found out that they are a small business with 5-10 employees, they struggle with lead qualification, and they currently use spreadsheets for tracking. Your main goal is to categorize this call into three categories: agreed_for_getting_email_proposal, not_interested, call_later."
        }
      }
    }]
  }
}
```

#### Email Request
```json
{
  "message": {
    "parts": [{
      "root": {
        "data": {
          "target": "john@company.com",
          "type": "email",
          "message": "Subject: Introduction from SalesShortcut\n\nHi John,\n\nI hope this email finds you well...",
          "objective": "initial outreach to potential client"
        }
      }
    }]
  }
}
```

### Tool Parameters

#### Phone Call Tool
- `destination`: Phone number to call (automatically normalized to E.164 format)
- `prompt`: Complete instruction/script for the call agent including context and categorization goals

**Internal Configuration (Encapsulated):**
- `max_duration_minutes`: 5 minutes (hardcoded)
- `call_categories`: `["agreed_for_getting_email_proposal", "not_interested", "call_later"]`
- Automatic categorization based on conversation analysis

#### Email Tool
- `to_email`: Recipient email address
- `subject`: Email subject line
- `message_body`: Email content
- `email_type`: Type of email ("outreach", "follow_up", "meeting_invite")
- `personalization_data`: Optional data for email personalization

## Testing

### Option 1: Direct A2A Testing (Recommended)

Use the provided test script:

```bash
# Run comprehensive test suite
python test_outreach_agent.py
```

The test script includes:
- Phone call outreach testing
- Email outreach testing
- Phone number validation testing
- Agent health checks

### Option 2: Manual curl Testing

```bash
# Test phone call
curl -X POST http://127.0.0.1:8083/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "parts": [{
        "root": {
          "data": {
            "destination": "+1-435-317-3839",
            "prompt": "You are calling on behalf of SalesShortcut offering automation services. Your goal is to categorize this call into: agreed_for_getting_email_proposal, not_interested, call_later."
          }
        }
      }]
    }
  }'

# Test email
curl -X POST http://127.0.0.1:8083/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "parts": [{
        "root": {
          "data": {
            "target": "test@example.com",
            "type": "email",
            "message": "Test email content",
            "objective": "initial outreach"
          }
        }
      }]
    }
  }'
```

### Option 3: Integration Testing

Test via other agents that use the Outreach Agent:

```bash
# Start UI client and lead manager, then trigger outreach through the dashboard
python -m ui_client
python -m lead_manager
```

## Phone Number Validation

The agent automatically validates and normalizes US phone numbers:

### Accepted Formats
- `5551234567` � `+15551234567`
- `1-555-123-4567` � `+15551234567`
- `(555) 123-4567` � `+15551234567`
- `+1 555 123 4567` � `+15551234567`

### Validation Rules
- Must be 10 or 11 digits (with optional country code)
- Area code cannot start with 0 or 1
- Automatically adds +1 country code for 10-digit numbers
- Rejects invalid formats with clear error messages

## Output and Logging

### Call Logs
Phone calls generate detailed logs in `phone_call_log_TIMESTAMP.json`:

```json
{
  "timestamp": "2024-12-11T10:30:00Z",
  "call_data": {
    "destination": "+15551234567",
    "prompt": "You are calling on behalf of SalesShortcut...",
    "status": "completed",
    "category": "agreed_for_getting_email_proposal",
    "duration_seconds": 180,
    "transcript": [
      {"role": "agent", "message": "Hello, this is John..."},
      {"role": "user", "message": "Yes, I'm interested. Please send me a proposal."}
    ],
    "summary": "Call completed to +15551234567. Prospect categorized as: agreed_for_getting_email_proposal",
    "next_action": "Send email proposal"
  }
}
```

### Email Logs
Emails generate logs in `email_log_TIMESTAMP.json`:

```json
{
  "timestamp": "2024-12-11T10:30:00Z",
  "email_data": {
    "to_email": "john@company.com",
    "subject": "Introduction from SalesShortcut",
    "status": "sent",
    "message_id": "email_123456",
    "next_action": "Monitor for response"
  }
}
```

## Architecture

### Agent Structure
```
outreach/
   __main__.py              # A2A server entry point
   agent_executor.py        # A2A request handler
   simple_main.py          # Fallback HTTP service
   outreach/
       agent.py            # Root LlmAgent definition
       callbacks.py        # UI callback integration
       config.py           # Configuration management
       prompts.py          # Agent prompts
       tools/
           phone_call.py   # ElevenLabs phone integration
           message_email.py # Email messaging tool
```

### Integration Flow
1. **A2A Request** � Agent Executor
2. **Parameter Extraction** � Phone/Email data
3. **Validation** � Phone number format check
4. **Tool Execution** � ElevenLabs/SMTP integration
5. **Result Processing** � Transcript analysis
6. **UI Callback** � Dashboard update
7. **Response** � A2A result with artifacts

## Troubleshooting

### Common Issues

1. **ElevenLabs Not Available**
   - Agent automatically falls back to mock calls
   - Check API key and agent configuration
   - Verify ElevenLabs library installation

2. **Phone Number Validation Errors**
   - Ensure phone numbers are US format
   - Check for valid area codes (no 0/1 prefix)
   - Use E.164 format when possible

3. **Email Sending Issues**
   - Verify SMTP configuration
   - Check email credentials and app passwords
   - Ensure firewall allows SMTP connections

4. **A2A Connection Issues**
   - Verify agent is running on correct port (8083)
   - Check network connectivity
   - Review agent logs for errors

### Debug Mode
Enable detailed logging by setting:

```env
LOG_LEVEL=DEBUG
```

## Development

### Adding New Tools
1. Create tool function in `outreach/tools/`
2. Add tool to agent definition in `agent.py`
3. Update agent skills in `__main__.py`
4. Add tests to test suite

### Extending Validation
Modify `phone_number_validation_callback` in `tools/phone_call.py` to add:
- International number support
- Additional validation rules
- Custom normalization logic

## API Reference

### Agent Skills

#### Phone Outreach Skill
- **ID**: `phone_outreach`
- **Description**: Make phone calls to leads with specific scripts and objectives
- **Tags**: `["phone", "call", "outreach", "qualification"]`

#### Email Outreach Skill
- **ID**: `email_outreach`  
- **Description**: Send personalized emails for outreach, follow-ups, or meetings
- **Tags**: `["email", "outreach", "follow-up", "meeting"]`

### Health Endpoint
```
GET /health
```
Returns agent status and configuration information.

---

## License

This agent is part of the SalesShortcut ecosystem. See main project license for details.
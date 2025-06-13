#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting local services..."

# Ensure we are in the project root directory (where the script is located)
cd "$(dirname "$0")"

# Check if GOOGLE_API_KEY is set
if [ -z "$GOOGLE_API_KEY" ]; then
  echo "ERROR: Please set GOOGLE_API_KEY environment variable for Gemini LLM inference."
  exit 1
fi

echo "Using GOOGLE_API_KEY for Gemini LLM inference..."

# Start Calendar Assistant (Default Port: 8080)
echo "Starting Calendar Assistant service in the background..."
GOOGLE_API_KEY="$GOOGLE_API_KEY" python -m calendar_assistant &
CALENDAR_PID=$!
echo "Calendar Assistant started with PID: $CALENDAR_PID"

# Start Lead Finder (Default Port: 8081)
echo "Starting Lead Finder service in the background..."
GOOGLE_API_KEY="$GOOGLE_API_KEY" python -m lead_finder &
LEAD_FINDER_PID=$!
echo "Lead Finder started with PID: $LEAD_FINDER_PID"

# Start Lead Manager (Port: 8082)
echo "Starting Lead Manager service in the background..."
GOOGLE_API_KEY="$GOOGLE_API_KEY" python -m lead_manager --port 8082 &
LEAD_MANAGER_PID=$!
echo "Lead Manager started with PID: $LEAD_MANAGER_PID"

# Start Outreach (Default Port: 8083)
echo "Starting Outreach service in the background..."
GOOGLE_API_KEY="$GOOGLE_API_KEY" python -m outreach &
OUTREACH_PID=$!
echo "Outreach started with PID: $OUTREACH_PID"

# Start SDR (Default Port: 8084)
echo "Starting SDR service in the background..."
GOOGLE_API_KEY="$GOOGLE_API_KEY" python -m sdr &
SDR_PID=$!
echo "SDR started with PID: $SDR_PID"

# Start UI Client (Default Port: 8000)
echo "Starting UI Client service in the background..."
GOOGLE_API_KEY="$GOOGLE_API_KEY" python -m ui_client &
UI_CLIENT_PID=$!
echo "UI Client started with PID: $UI_CLIENT_PID"

# Start Outreach Test Client (Port: 8501)
echo "Starting Outreach Test Client in the background..."
cd outreach/test_client && pip install -r requirements.txt > /dev/null 2>&1 && FORCE_SIMPLE_MODE=true uvicorn app:app --host 127.0.0.1 --port 8501 &
OUTREACH_TEST_CLIENT_PID=$!
echo "Outreach Test Client started with PID: $OUTREACH_TEST_CLIENT_PID"
cd - > /dev/null

echo "--------------------------------------------------"
echo "Local services started:"
echo "  Calendar Assistant: http://127.0.0.1:8080 (PID: $CALENDAR_PID)"
echo "  Lead Finder:        http://127.0.0.1:8081 (PID: $LEAD_FINDER_PID)"
echo "  Lead Manager:       http://127.0.0.1:8082 (PID: $LEAD_MANAGER_PID)"
echo "  Outreach:           http://127.0.0.1:8083 (PID: $OUTREACH_PID)"
echo "  SDR:                http://127.0.0.1:8084 (PID: $SDR_PID)"
echo "  UI Client:          http://127.0.0.1:8000 (PID: $UI_CLIENT_PID)"
echo "  Outreach Test Client: http://127.0.0.1:8501 (PID: $OUTREACH_TEST_CLIENT_PID)"
echo "--------------------------------------------------"
echo "Use 'kill $CALENDAR_PID $LEAD_FINDER_PID $LEAD_MANAGER_PID $OUTREACH_PID $SDR_PID $UI_CLIENT_PID $OUTREACH_TEST_CLIENT_PID' or Ctrl+C to stop all services."

# Optional: Wait for all background processes to finish (uncomment if needed)
# wait
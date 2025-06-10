# Makefile for SalesShortcut A2A Project
# 
# Usage:
#   make deploy_local    - Deploy locally with environment variables
#   make deploy_cloud    - Deploy to cloud with environment variables  
#   make test_local      - Run local test (UI Client + Lead Manager only)
#   make clean           - Kill all running services
#   make setup           - Install dependencies
#   make help            - Show this help

# Default values for API keys (override in .env file or export before running)
GOOGLE_API_KEY ?= $(shell echo $$GOOGLE_API_KEY)
OPENAI_API_KEY ?= $(shell echo $$OPENAI_API_KEY)
ANTHROPIC_API_KEY ?= $(shell echo $$ANTHROPIC_API_KEY)

# Check if .env file exists and source it
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

.PHONY: help deploy_local deploy_cloud test_local clean setup check_env

help:
	@echo "SalesShortcut A2A Project - Available Commands:"
	@echo ""
	@echo "  make deploy_local    - Deploy all services locally"
	@echo "  make deploy_cloud    - Deploy all services to cloud"
	@echo "  make test_local      - Run test deployment (UI Client + Lead Manager)"
	@echo "  make clean           - Kill all running services"
	@echo "  make setup           - Install Python dependencies"
	@echo "  make check_env       - Check environment variables"
	@echo "  make help            - Show this help"
	@echo ""
	@echo "Environment Variables:"
	@echo "  GOOGLE_API_KEY       - Required for Gemini LLM inference"
	@echo "  OPENAI_API_KEY       - Optional for OpenAI models"
	@echo "  ANTHROPIC_API_KEY    - Optional for Claude models"
	@echo ""
	@echo "Create a .env file to set API keys automatically:"
	@echo "  echo 'GOOGLE_API_KEY=your_key_here' > .env"

check_env:
	@echo "Checking environment variables..."
	@if [ -z "$(GOOGLE_API_KEY)" ]; then \
		echo "❌ GOOGLE_API_KEY is not set"; \
		echo "   Export it: export GOOGLE_API_KEY=your_key_here"; \
		echo "   Or create .env file: echo 'GOOGLE_API_KEY=your_key_here' > .env"; \
		exit 1; \
	else \
		echo "✅ GOOGLE_API_KEY is set"; \
	fi
	@if [ -n "$(OPENAI_API_KEY)" ]; then echo "✅ OPENAI_API_KEY is set"; else echo "⚠️  OPENAI_API_KEY is not set (optional)"; fi
	@if [ -n "$(ANTHROPIC_API_KEY)" ]; then echo "✅ ANTHROPIC_API_KEY is set"; else echo "⚠️  ANTHROPIC_API_KEY is not set (optional)"; fi

deploy_local: clean check_env
	@echo "🚀 Deploying all services locally..."
	@chmod +x ./deploy_local.sh
	@GOOGLE_API_KEY="$(GOOGLE_API_KEY)" \
	 OPENAI_API_KEY="$(OPENAI_API_KEY)" \
	 ANTHROPIC_API_KEY="$(ANTHROPIC_API_KEY)" \
	 ./deploy_local.sh

deploy_cloud: check_env
	@echo "☁️  Deploying all services to cloud..."
	@chmod +x ./deploy_cloud_run.sh
	@GOOGLE_API_KEY="$(GOOGLE_API_KEY)" \
	 OPENAI_API_KEY="$(OPENAI_API_KEY)" \
	 ANTHROPIC_API_KEY="$(ANTHROPIC_API_KEY)" \
	 ./deploy_cloud_run.sh

test_local: clean check_env
	@echo "🧪 Running local test deployment (UI Client + Lead Manager)..."
	@chmod +x ./test_local.sh
	@GOOGLE_API_KEY="$(GOOGLE_API_KEY)" \
	 OPENAI_API_KEY="$(OPENAI_API_KEY)" \
	 ANTHROPIC_API_KEY="$(ANTHROPIC_API_KEY)" \
	 ./test_local.sh

clean:
	@echo "🧹 Stopping all services..."
	@pkill -f "python -m ui_client" || true
	@pkill -f "python -m lead_manager" || true
	@pkill -f "python -m lead_finder" || true
	@pkill -f "python -m calendar_assistant" || true
	@pkill -f "python -m outreach" || true
	@pkill -f "python -m sdr" || true
	@echo "✅ All services stopped"

setup:
	@echo "📦 Installing dependencies..."
	@if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
	@if [ -f ui_client/requirements.txt ]; then pip install -r ui_client/requirements.txt; fi
	@if [ -f lead_manager/requirements.txt ]; then pip install -r lead_manager/requirements.txt; fi
	@if [ -f lead_finder/requirements.txt ]; then pip install -r lead_finder/requirements.txt; fi
	@if [ -f calendar_assistant/requirements.txt ]; then pip install -r calendar_assistant/requirements.txt; fi
	@if [ -f outreach/requirements.txt ]; then pip install -r outreach/requirements.txt; fi
	@if [ -f sdr/requirements.txt ]; then pip install -r sdr/requirements.txt; fi
	@echo "✅ Dependencies installed"

# Create example .env file
.env.example:
	@echo "# SalesShortcut A2A Project Environment Variables" > .env.example
	@echo "# Copy this file to .env and fill in your API keys" >> .env.example
	@echo "" >> .env.example
	@echo "# Required for Gemini LLM inference" >> .env.example
	@echo "GOOGLE_API_KEY=your_google_api_key_here" >> .env.example
	@echo "" >> .env.example
	@echo "# Optional API keys" >> .env.example
	@echo "OPENAI_API_KEY=your_openai_api_key_here" >> .env.example
	@echo "ANTHROPIC_API_KEY=your_anthropic_api_key_here" >> .env.example
	@echo "✅ Created .env.example file"

init: .env.example
	@echo "🎉 Project initialized!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Copy .env.example to .env: cp .env.example .env"
	@echo "2. Edit .env and add your API keys"
	@echo "3. Run: make setup"
	@echo "4. Run: make test_local"
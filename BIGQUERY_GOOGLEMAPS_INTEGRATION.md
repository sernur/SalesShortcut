# BigQuery and Google Maps Integration

This document outlines the integration work for BigQuery and Google Maps APIs in the SalesShortcut multi-agent system.

## 🎯 Project Overview

**SalesShortcut** is a multi-agent sales automation system. Your task is to complete the BigQuery and Google Maps API integrations in the **Lead Finder Agent** and extend functionality to other agents.

## 🏗️ Current Architecture

- **Lead Finder Agent** (Port 8081) - Discovers potential business leads
- **Lead Manager Agent** (Port 8082) - Manages and qualifies leads  
- **Outreach Agent** (Port 8083) - Handles phone calls and email outreach
- **SDR Agent** (Port 8084) - Sales Development Representative workflows
- **Calendar Assistant** (Port 8080) - Manages scheduling and appointments
- **UI Client** (Port 8000) - Web dashboard for monitoring and control

## 📋 Your Specific Tasks

### ✅ Completed
- [x] Created new branch: `feature/bigquery-googlemaps-integration`
- [x] Set up virtual environment with all dependencies
- [x] Installed BigQuery and Google Maps client libraries
- [x] Created configuration template with all required API keys

### 🔄 In Progress
- [ ] Complete Google Maps API Integration (Lead Finder Agent)
- [ ] Complete BigQuery Integration (Lead Finder Agent)
- [ ] Extend BigQuery integration to other agents
- [ ] Add comprehensive testing and error handling

### 📍 Current Status: **SETUP COMPLETE - READY TO START DEVELOPMENT**

## 🛠️ Setup Instructions

1. **Virtual Environment**: Already created and activated
   ```bash
   source venv/bin/activate
   ```

2. **Environment Configuration**:
   ```bash
   cp config.template .env
   # Edit .env with your actual API keys
   ```

3. **Required API Keys**:
   - `GOOGLE_API_KEY` - For Gemini LLM
   - `GOOGLE_MAPS_API_KEY` - For Places API
   - `GOOGLE_CLOUD_PROJECT` - Your GCP Project ID

## 📂 Key Files to Work On

### Lead Finder Agent
- `lead_finder/lead_finder/tools/maps_search.py` - Google Maps integration
- `lead_finder/lead_finder/tools/bigquery_utils.py` - BigQuery integration
- `lead_finder/lead_finder/config.py` - Configuration management

### Other Agents (Future)
- `lead_manager/` - Lead management with BigQuery
- `outreach/` - Outreach analytics storage
- `sdr/` - Territory management and analytics

## 🎯 Next Steps

### Phase 1: Google Maps API Integration
1. Uncomment and fix the real API implementation in `maps_search.py`
2. Implement proper Places API calls with error handling
3. Add support for different search types and filters
4. Test with real API calls

### Phase 2: BigQuery Integration  
1. Replace JSON file writing with real BigQuery operations
2. Set up proper authentication and table schemas
3. Implement data validation and deduplication
4. Add querying capabilities for existing leads

### Phase 3: Integration & Testing
1. Test agent-to-agent communication
2. Add comprehensive error handling
3. Create proper logging and monitoring
4. Extend to other agents as needed

## 🚀 Development Workflow

1. Work on one component at a time
2. Test locally before committing
3. Use meaningful commit messages
4. Keep the virtual environment activated
5. Update this document as you progress

## 🔧 Dependencies Installed

- `google-cloud-bigquery` - BigQuery client library
- `googlemaps` - Google Maps API client
- `google-adk` - Google Agent Development Kit
- `a2a-sdk` - Agent-to-Agent communication
- All other project dependencies

## 📚 Useful Resources

- [Google Maps Places API Documentation](https://developers.google.com/maps/documentation/places/web-service)
- [BigQuery Python Client Documentation](https://cloud.google.com/bigquery/docs/reference/libraries)
- [Google ADK Documentation](https://developers.google.com/agent-development-kit)

---

**Ready to start development!** 🚀

Next command: Focus on Google Maps API integration in `lead_finder/lead_finder/tools/maps_search.py` 
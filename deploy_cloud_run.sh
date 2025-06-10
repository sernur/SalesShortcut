#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
export PROJECT_ID="${PROJECT_ID:-your-gcp-project-id}" # Uses env var $PROJECT_ID if set, otherwise the default
export REGION="${REGION:-us-central1}"                 # Uses env var $REGION if set, otherwise the default
export REPOSITORY_NAME="sales-shortcut"

# Derived Artifact Registry path prefix
export AR_PREFIX="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}"

# Service Names
export CALENDAR_ASSISTANT_SERVICE_NAME="calendar-assistant-service"
export LEAD_FINDER_SERVICE_NAME="lead-finder-service"
export LEAD_MANAGER_SERVICE_NAME="lead-manager-service"
export OUTREACH_SERVICE_NAME="outreach-service"
export SDR_SERVICE_NAME="sdr-service"
export UI_CLIENT_SERVICE_NAME="ui-client-service"

# Cloud Build Config file names
export CALENDAR_ASSISTANT_BUILDFILE="cloudbuild-calendar_assistant.yaml"
export LEAD_FINDER_BUILDFILE="cloudbuild-lead_finder.yaml"
export LEAD_MANAGER_BUILDFILE="cloudbuild-lead_manager.yaml"
export OUTREACH_BUILDFILE="cloudbuild-outreach.yaml"
export SDR_BUILDFILE="cloudbuild-sdr.yaml"
export UI_CLIENT_BUILDFILE="cloudbuild-ui_client.yaml"

# Image tags (used for deployment after build)
export CALENDAR_ASSISTANT_IMAGE_TAG="${AR_PREFIX}/calendar-assistant:latest"
export LEAD_FINDER_IMAGE_TAG="${AR_PREFIX}/lead-finder:latest"
export LEAD_MANAGER_IMAGE_TAG="${AR_PREFIX}/lead-manager:latest"
export OUTREACH_IMAGE_TAG="${AR_PREFIX}/outreach:latest"
export SDR_IMAGE_TAG="${AR_PREFIX}/sdr:latest"
export UI_CLIENT_IMAGE_TAG="${AR_PREFIX}/ui-client:latest"

# Check if PROJECT_ID is set
if [ "$PROJECT_ID" == "your-gcp-project-id" ]; then
  echo "ERROR: Please set your PROJECT_ID in the script before running."
  exit 1
fi

# Check if GOOGLE_API_KEY is set
if [ -z "$GOOGLE_API_KEY" ]; then
  echo "ERROR: Please set GOOGLE_API_KEY environment variable for Gemini LLM inference."
  echo "Example: export GOOGLE_API_KEY='your-api-key' && ./deploy_cloud_run.sh"
  exit 1
fi

# --- Pre-flight Checks ---
echo "Using Project ID: $PROJECT_ID"
echo "Using Region: $REGION"
echo "Using Repository: $REPOSITORY_NAME"
echo "Artifact Registry Prefix: $AR_PREFIX"
echo "---"

# --- Setup Artifact Registry (if it doesn't exist) ---
echo "Creating Artifact Registry repository (if needed)..."
gcloud artifacts repositories create $REPOSITORY_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository for sales shortcut services" \
    --project=$PROJECT_ID || echo "Repository '$REPOSITORY_NAME' likely already exists in region '$REGION'."
echo "---"

# --- 1. Deploy Calendar Assistant ---
echo "Deploying Calendar Assistant..."

# Step 1.1: Build and Push Image using Cloud Build Config
echo "Building Calendar Assistant image using $CALENDAR_ASSISTANT_BUILDFILE..."
gcloud builds submit . --config=$CALENDAR_ASSISTANT_BUILDFILE \
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPOSITORY_NAME \
    --project=$PROJECT_ID --quiet

# Step 1.2: Deploy to Cloud Run using the built image tag
echo "Deploying Calendar Assistant service ($CALENDAR_ASSISTANT_SERVICE_NAME)..."
gcloud run deploy $CALENDAR_ASSISTANT_SERVICE_NAME \
    --image=$CALENDAR_ASSISTANT_IMAGE_TAG \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY" \
    --project=$PROJECT_ID

# Step 1.3: Get Service URL
export CALENDAR_ASSISTANT_SERVICE_URL=$(gcloud run services describe $CALENDAR_ASSISTANT_SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)
echo "Calendar Assistant URL: $CALENDAR_ASSISTANT_SERVICE_URL"
echo "---"

# --- 2. Deploy Lead Finder ---
echo "Deploying Lead Finder..."

# Step 2.1: Build and Push Image using Cloud Build Config
echo "Building Lead Finder image using $LEAD_FINDER_BUILDFILE..."
gcloud builds submit . --config=$LEAD_FINDER_BUILDFILE \
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPOSITORY_NAME \
    --project=$PROJECT_ID --quiet

# Step 2.2: Deploy to Cloud Run
echo "Deploying Lead Finder service ($LEAD_FINDER_SERVICE_NAME)..."
gcloud run deploy $LEAD_FINDER_SERVICE_NAME \
    --image=$LEAD_FINDER_IMAGE_TAG \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY" \
    --project=$PROJECT_ID

# Step 2.3: Get Service URL
export LEAD_FINDER_SERVICE_URL=$(gcloud run services describe $LEAD_FINDER_SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)
echo "Lead Finder URL: $LEAD_FINDER_SERVICE_URL"
echo "---"

# --- 3. Deploy Lead Manager ---
echo "Deploying Lead Manager..."

# Step 3.1: Build and Push Image using Cloud Build Config
echo "Building Lead Manager image using $LEAD_MANAGER_BUILDFILE..."
gcloud builds submit . --config=$LEAD_MANAGER_BUILDFILE \
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPOSITORY_NAME \
    --project=$PROJECT_ID --quiet

# Step 3.2: Deploy to Cloud Run (passing Lead Finder URL)
echo "Deploying Lead Manager service ($LEAD_MANAGER_SERVICE_NAME)..."
gcloud run deploy $LEAD_MANAGER_SERVICE_NAME \
    --image=$LEAD_MANAGER_IMAGE_TAG \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,LEAD_FINDER_SERVICE_URL=$LEAD_FINDER_SERVICE_URL" \
    --project=$PROJECT_ID

# Step 3.3: Get Service URL
export LEAD_MANAGER_SERVICE_URL=$(gcloud run services describe $LEAD_MANAGER_SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)
echo "Lead Manager URL: $LEAD_MANAGER_SERVICE_URL"
echo "---"

# --- 4. Deploy Outreach ---
echo "Deploying Outreach..."

# Step 4.1: Build and Push Image using Cloud Build Config
echo "Building Outreach image using $OUTREACH_BUILDFILE..."
gcloud builds submit . --config=$OUTREACH_BUILDFILE \
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPOSITORY_NAME \
    --project=$PROJECT_ID --quiet

# Step 4.2: Deploy to Cloud Run (passing Lead Manager URL)
echo "Deploying Outreach service ($OUTREACH_SERVICE_NAME)..."
gcloud run deploy $OUTREACH_SERVICE_NAME \
    --image=$OUTREACH_IMAGE_TAG \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,LEAD_MANAGER_SERVICE_URL=$LEAD_MANAGER_SERVICE_URL" \
    --project=$PROJECT_ID

# Step 4.3: Get Service URL
export OUTREACH_SERVICE_URL=$(gcloud run services describe $OUTREACH_SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)
echo "Outreach URL: $OUTREACH_SERVICE_URL"
echo "---"

# --- 5. Deploy SDR ---
echo "Deploying SDR..."

# Step 5.1: Build and Push Image using Cloud Build Config
echo "Building SDR image using $SDR_BUILDFILE..."
gcloud builds submit . --config=$SDR_BUILDFILE \
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPOSITORY_NAME \
    --project=$PROJECT_ID --quiet

# Step 5.2: Deploy to Cloud Run (passing Outreach URL)
echo "Deploying SDR service ($SDR_SERVICE_NAME)..."
gcloud run deploy $SDR_SERVICE_NAME \
    --image=$SDR_IMAGE_TAG \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,OUTREACH_SERVICE_URL=$OUTREACH_SERVICE_URL" \
    --project=$PROJECT_ID

# Step 5.3: Get Service URL
export SDR_SERVICE_URL=$(gcloud run services describe $SDR_SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)
echo "SDR URL: $SDR_SERVICE_URL"
echo "---"

# --- 6. Deploy UI Client ---
echo "Deploying UI Client..."

# Step 6.1: Build and Push Image using Cloud Build Config
echo "Building UI Client image using $UI_CLIENT_BUILDFILE..."
gcloud builds submit . --config=$UI_CLIENT_BUILDFILE \
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPOSITORY_NAME \
    --project=$PROJECT_ID --quiet

# Step 6.2: Deploy to Cloud Run (passing all service URLs)
echo "Deploying UI Client service ($UI_CLIENT_SERVICE_NAME)..."
gcloud run deploy $UI_CLIENT_SERVICE_NAME \
    --image=$UI_CLIENT_IMAGE_TAG \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,CALENDAR_ASSISTANT_SERVICE_URL=$CALENDAR_ASSISTANT_SERVICE_URL,LEAD_FINDER_SERVICE_URL=$LEAD_FINDER_SERVICE_URL,LEAD_MANAGER_SERVICE_URL=$LEAD_MANAGER_SERVICE_URL,OUTREACH_SERVICE_URL=$OUTREACH_SERVICE_URL,SDR_SERVICE_URL=$SDR_SERVICE_URL" \
    --project=$PROJECT_ID

# Step 6.3: Get Service URL
export UI_CLIENT_SERVICE_URL=$(gcloud run services describe $UI_CLIENT_SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)
echo "UI Client URL: $UI_CLIENT_SERVICE_URL"
echo "---"

echo "Deployment Complete!"
echo "Access the UI Client at: $UI_CLIENT_SERVICE_URL"
echo "Remember to consider security (--allow-unauthenticated) for production environments."
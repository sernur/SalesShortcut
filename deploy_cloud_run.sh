#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
export PROJECT_ID="${PROJECT_ID:-salesshortcut}" # Uses env var $PROJECT_ID if set, otherwise the default
export REGION="${REGION:-us-central1}"                 # Uses env var $REGION if set, otherwise the default
export REPOSITORY_NAME="sales-shortcut"

# Derived Artifact Registry path prefix
export AR_PREFIX="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}"

# Service Names
export LEAD_FINDER_SERVICE_NAME="lead-finder-service"
export LEAD_MANAGER_SERVICE_NAME="lead-manager-service"
export SDR_SERVICE_NAME="sdr-service"
export GMAIL_LISTENER_SERVICE_NAME="gmail-listener-service"
export UI_CLIENT_SERVICE_NAME="ui-client-service"

# Cloud Build Config file names
export LEAD_FINDER_BUILDFILE="cloudbuild-lead_finder.yaml"
export LEAD_MANAGER_BUILDFILE="cloudbuild-lead_manager.yaml"
export SDR_BUILDFILE="cloudbuild-sdr.yaml"
export GMAIL_LISTENER_BUILDFILE="cloudbuild-gmail_listener.yaml"
export UI_CLIENT_BUILDFILE="cloudbuild-ui_client.yaml"

# Image tags (used for deployment after build)
export LEAD_FINDER_IMAGE_TAG="${AR_PREFIX}/lead-finder:latest"
export LEAD_MANAGER_IMAGE_TAG="${AR_PREFIX}/lead-manager:latest"
export SDR_IMAGE_TAG="${AR_PREFIX}/sdr:latest"
export GMAIL_LISTENER_IMAGE_TAG="${AR_PREFIX}/gmail-listener:latest"
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

# Set Google Maps API key from local env if available
export GOOGLE_MAPS_API_KEY="${GOOGLE_MAPS_API_KEY:-AIzaSyBdsjrHYHzFgbcG0ASBn2Mji1CnhRAz3h8}"

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
# Separator after setup
echo "---"
# Parse services to deploy (optional: supply names as args: lead-finder, lead-manager, sdr, gmail-listener, ui-client)
if [ $# -gt 0 ]; then
  DEPLOY_SERVICES="$@"
else
  DEPLOY_SERVICES="lead-finder lead-manager sdr gmail-listener ui-client"
fi

# --- 1. Deploy Lead Finder ---
if echo "$DEPLOY_SERVICES" | grep -qw "lead-finder"; then
  echo "Deploying Lead Finder..."

# Step 1.1: Build and Push Image using Cloud Build Config
echo "Building Lead Finder image using $LEAD_FINDER_BUILDFILE..."
gcloud builds submit . --config=$LEAD_FINDER_BUILDFILE \
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPOSITORY_NAME \
    --project=$PROJECT_ID --quiet

# Step 1.2: Deploy to Cloud Run
echo "Getting latest image digest for Lead Finder..."
LEAD_FINDER_DIGEST=$(gcloud artifacts docker images list $AR_PREFIX/lead-finder --format="value(DIGEST)" --limit=1 --project=$PROJECT_ID)
echo "Using image digest: $LEAD_FINDER_DIGEST"
echo "Deploying Lead Finder service ($LEAD_FINDER_SERVICE_NAME)..."
gcloud run deploy $LEAD_FINDER_SERVICE_NAME \
    --image=$AR_PREFIX/lead-finder@$LEAD_FINDER_DIGEST \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,GOOGLE_MAPS_API_KEY=$GOOGLE_MAPS_API_KEY" \
    --project=$PROJECT_ID

# Step 1.3: Get Service URL
export LEAD_FINDER_SERVICE_URL=$(gcloud run services describe $LEAD_FINDER_SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)
  echo "Lead Finder URL: $LEAD_FINDER_SERVICE_URL"
  echo "---"
fi

# --- 2. Deploy Lead Manager ---
if echo "$DEPLOY_SERVICES" | grep -qw "lead-manager"; then
  echo "Deploying Lead Manager..."

# Step 2.1: Build and Push Image using Cloud Build Config
echo "Building Lead Manager image using $LEAD_MANAGER_BUILDFILE..."
gcloud builds submit . --config=$LEAD_MANAGER_BUILDFILE \
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPOSITORY_NAME \
    --project=$PROJECT_ID --quiet

# Step 2.2: Deploy to Cloud Run (passing Lead Finder URL)
echo "Getting latest image digest for Lead Manager..."
LEAD_MANAGER_DIGEST=$(gcloud artifacts docker images list $AR_PREFIX/lead-manager --format="value(DIGEST)" --limit=1 --project=$PROJECT_ID)
echo "Using image digest: $LEAD_MANAGER_DIGEST"
echo "Deploying Lead Manager service ($LEAD_MANAGER_SERVICE_NAME)..."
gcloud run deploy $LEAD_MANAGER_SERVICE_NAME \
    --image=$AR_PREFIX/lead-manager@$LEAD_MANAGER_DIGEST \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,GOOGLE_MAPS_API_KEY=$GOOGLE_MAPS_API_KEY,LEAD_FINDER_SERVICE_URL=$LEAD_FINDER_SERVICE_URL" \
    --project=$PROJECT_ID

# Step 2.3: Get Service URL
export LEAD_MANAGER_SERVICE_URL=$(gcloud run services describe $LEAD_MANAGER_SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)
  echo "Lead Manager URL: $LEAD_MANAGER_SERVICE_URL"
  echo "---"
fi

# --- 3. Deploy SDR ---
if echo "$DEPLOY_SERVICES" | grep -qw "sdr"; then
  echo "Deploying SDR..."

# Step 3.1: Build and Push Image using Cloud Build Config
echo "Building SDR image using $SDR_BUILDFILE..."
gcloud builds submit . --config=$SDR_BUILDFILE \
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPOSITORY_NAME \
    --project=$PROJECT_ID --quiet

# Step 3.2: Deploy to Cloud Run (passing Lead Manager URL)
echo "Getting latest image digest for SDR..."
SDR_DIGEST=$(gcloud artifacts docker images list $AR_PREFIX/sdr --format="value(DIGEST)" --limit=1 --project=$PROJECT_ID)
echo "Using image digest: $SDR_DIGEST"
echo "Deploying SDR service ($SDR_SERVICE_NAME)..."
gcloud run deploy $SDR_SERVICE_NAME \
    --image=$AR_PREFIX/sdr@$SDR_DIGEST \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,GOOGLE_MAPS_API_KEY=$GOOGLE_MAPS_API_KEY,LEAD_MANAGER_SERVICE_URL=$LEAD_MANAGER_SERVICE_URL" \
    --project=$PROJECT_ID

# Step 3.3: Get Service URL
export SDR_SERVICE_URL=$(gcloud run services describe $SDR_SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)
  echo "SDR URL: $SDR_SERVICE_URL"
  echo "---"
fi

# --- 4. Deploy Gmail Listener ---
if echo "$DEPLOY_SERVICES" | grep -qw "gmail-listener"; then
  echo "Deploying Gmail Listener..."

# Step 4.1: Build and Push Image using Cloud Build Config
echo "Building Gmail Listener image using $GMAIL_LISTENER_BUILDFILE..."
gcloud builds submit . --config=$GMAIL_LISTENER_BUILDFILE \
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPOSITORY_NAME \
    --project=$PROJECT_ID --quiet

# Step 4.2: Deploy to Cloud Run (passing Lead Manager URL)
echo "Getting latest image digest for Gmail Listener..."
GMAIL_LISTENER_DIGEST=$(gcloud artifacts docker images list $AR_PREFIX/gmail-listener --format="value(DIGEST)" --limit=1 --project=$PROJECT_ID)
echo "Using image digest: $GMAIL_LISTENER_DIGEST"
echo "Deploying Gmail Listener service ($GMAIL_LISTENER_SERVICE_NAME)..."
gcloud run deploy $GMAIL_LISTENER_SERVICE_NAME \
    --image=$AR_PREFIX/gmail-listener@$GMAIL_LISTENER_DIGEST \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,GOOGLE_MAPS_API_KEY=$GOOGLE_MAPS_API_KEY,LEAD_MANAGER_SERVICE_URL=$LEAD_MANAGER_SERVICE_URL" \
    --project=$PROJECT_ID

# Step 4.3: Get Service URL
export GMAIL_LISTENER_SERVICE_URL=$(gcloud run services describe $GMAIL_LISTENER_SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)
  echo "Gmail Listener URL: $GMAIL_LISTENER_SERVICE_URL"
  echo "---"
fi

# --- 5. Deploy UI Client ---
if echo "$DEPLOY_SERVICES" | grep -qw "ui-client"; then
  echo "Deploying UI Client..."

# Step 5.1: Build and Push Image using Cloud Build Config
echo "Building UI Client image using $UI_CLIENT_BUILDFILE..."
gcloud builds submit . --config=$UI_CLIENT_BUILDFILE \
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPOSITORY_NAME \
    --project=$PROJECT_ID --quiet

# Step 5.2: Deploy to Cloud Run (passing all service URLs)
echo "Getting latest image digest for UI Client..."
UI_CLIENT_DIGEST=$(gcloud artifacts docker images list $AR_PREFIX/ui_client --format="value(DIGEST)" --limit=1 --project=$PROJECT_ID)
echo "Using image digest: $UI_CLIENT_DIGEST"
echo "Deploying UI Client service ($UI_CLIENT_SERVICE_NAME)..."
gcloud run deploy $UI_CLIENT_SERVICE_NAME \
    --image=$AR_PREFIX/ui_client@$UI_CLIENT_DIGEST \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,GOOGLE_MAPS_API_KEY=$GOOGLE_MAPS_API_KEY,LEAD_FINDER_SERVICE_URL=$LEAD_FINDER_SERVICE_URL,LEAD_MANAGER_SERVICE_URL=$LEAD_MANAGER_SERVICE_URL,SDR_SERVICE_URL=$SDR_SERVICE_URL,GMAIL_LISTENER_SERVICE_URL=$GMAIL_LISTENER_SERVICE_URL" \
    --project=$PROJECT_ID

# Step 5.3: Get Service URL
export UI_CLIENT_SERVICE_URL=$(gcloud run services describe $UI_CLIENT_SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' --project=$PROJECT_ID)
  echo "UI Client URL: $UI_CLIENT_SERVICE_URL"
  echo "---"
fi

# Grant public access to deployed services
echo "Granting public (unauthenticated) access to deployed services..."
for S in $DEPLOY_SERVICES; do
  case "$S" in
    lead-finder) NAME=$LEAD_FINDER_SERVICE_NAME;;
    lead-manager) NAME=$LEAD_MANAGER_SERVICE_NAME;;
    sdr) NAME=$SDR_SERVICE_NAME;;
    gmail-listener) NAME=$GMAIL_LISTENER_SERVICE_NAME;;
    ui-client) NAME=$UI_CLIENT_SERVICE_NAME;;
    *) continue;;
  esac
  echo " - $NAME"
  gcloud run services add-iam-policy-binding "$NAME" \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --platform managed \
    --region "$REGION" \
    --project "$PROJECT_ID" || echo "Warning: failed to bind $NAME"
done

echo "Deployment Complete!"
echo "Access the UI Client at: $UI_CLIENT_SERVICE_URL"
echo "Remember to consider security (--allow-unauthenticated) for production environments."
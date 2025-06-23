#!/bin/bash

# Cloud Run Deployment Script
# Deploys the dev-assist application to Google Cloud Run

set -e

# Configuration from environment or defaults
GCP_PROJECT_ID=${GCP_PROJECT_ID:-""}
GCP_REGION=${GCP_REGION:-"asia-southeast1"}
ENVIRONMENT=${ENVIRONMENT:-"development"}
IMAGE_TAG=${IMAGE_TAG:-"latest"}

echo "🚀 Deploying dev-assist application to Cloud Run"
echo "   Project: $GCP_PROJECT_ID"
echo "   Region: $GCP_REGION"
echo "   Environment: $ENVIRONMENT"
echo "   Image Tag: $IMAGE_TAG"

# Check if project ID is set
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "❌ GCP_PROJECT_ID environment variable is required"
    exit 1
fi

# Set gcloud defaults
gcloud config set project $GCP_PROJECT_ID
gcloud config set run/region $GCP_REGION

# Enable required APIs (skip if running in CI/CD)
if [ "${CI:-false}" = "true" ] || [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
    echo "📡 Skipping API enablement in CI/CD environment..."
    echo "ℹ️  APIs should be pre-enabled via setup script"
else
    echo "📡 Enabling required APIs..."
    gcloud services enable run.googleapis.com --quiet
    gcloud services enable cloudbuild.googleapis.com --quiet
    gcloud services enable secretmanager.googleapis.com --quiet
    gcloud services enable sqladmin.googleapis.com --quiet
fi

# Create service accounts if they don't exist
echo "👤 Setting up service accounts..."

# API service account
if ! gcloud iam service-accounts describe dev-assist-api@$GCP_PROJECT_ID.iam.gserviceaccount.com >/dev/null 2>&1; then
    gcloud iam service-accounts create dev-assist-api \
        --display-name="Dev Assist API Service" \
        --description="Service account for Dev Assist API Cloud Run service"
    echo "✅ Created API service account"
else
    echo "ℹ️  API service account already exists"
fi

# Frontend service account
if ! gcloud iam service-accounts describe dev-assist-frontend@$GCP_PROJECT_ID.iam.gserviceaccount.com >/dev/null 2>&1; then
    gcloud iam service-accounts create dev-assist-frontend \
        --display-name="Dev Assist Frontend Service" \
        --description="Service account for Dev Assist Frontend Cloud Run service"
    echo "✅ Created frontend service account"
else
    echo "ℹ️  Frontend service account already exists"
fi

# Grant Secret Manager access to API service account (skip if running in CI/CD)
if [ "${CI:-false}" = "true" ] || [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
    echo "🔐 Skipping IAM permission granting in CI/CD environment..."
    echo "ℹ️  Permissions should be pre-configured via setup script"
else
    echo "🔐 Granting Secret Manager permissions..."
    gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
        --member="serviceAccount:dev-assist-api@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet
fi

# Update service YAML files with project ID
echo "📝 Updating service configurations..."
sed -i "s/PROJECT_ID/$GCP_PROJECT_ID/g" service.yaml
sed -i "s/PROJECT_ID/$GCP_PROJECT_ID/g" frontend-service.yaml
sed -i "s/REGION/$GCP_REGION/g" service.yaml

# Deploy API service
echo "🚀 Deploying API service..."
gcloud run services replace service.yaml \
    --region=$GCP_REGION \
    --quiet

# Update API service to use latest image
gcloud run services update dev-assist-api \
    --image=asia-southeast1-docker.pkg.dev/$GCP_PROJECT_ID/dev-assist/api:$IMAGE_TAG \
    --region=$GCP_REGION \
    --quiet

# Deploy Frontend service
echo "🚀 Deploying Frontend service..."
gcloud run services replace frontend-service.yaml \
    --region=$GCP_REGION \
    --quiet

# Update Frontend service to use latest image
gcloud run services update dev-assist-frontend \
    --image=asia-southeast1-docker.pkg.dev/$GCP_PROJECT_ID/dev-assist/frontend:$IMAGE_TAG \
    --region=$GCP_REGION \
    --quiet

# Configure traffic and IAM
echo "🌐 Configuring public access..."

# Allow unauthenticated access to frontend
gcloud run services add-iam-policy-binding dev-assist-frontend \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --region=$GCP_REGION \
    --quiet

# Allow unauthenticated access to API (you may want to restrict this in production)
gcloud run services add-iam-policy-binding dev-assist-api \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --region=$GCP_REGION \
    --quiet

# Get service URLs
API_URL=$(gcloud run services describe dev-assist-api \
    --region=$GCP_REGION \
    --format="value(status.url)")

FRONTEND_URL=$(gcloud run services describe dev-assist-frontend \
    --region=$GCP_REGION \
    --format="value(status.url)")

echo ""
echo "✅ Cloud Run deployment completed!"
echo ""
echo "📋 Service URLs:"
echo "   🔗 Frontend: $FRONTEND_URL"
echo "   🔗 API: $API_URL"
echo "   🔗 API Docs: $API_URL/docs"
echo "   🔗 API Health: $API_URL/api/v1/healthz"
echo ""
echo "📊 Deployment Information:"
echo "   📦 API Image: asia-southeast1-docker.pkg.dev/$GCP_PROJECT_ID/dev-assist/api:$IMAGE_TAG"
echo "   📦 Frontend Image: asia-southeast1-docker.pkg.dev/$GCP_PROJECT_ID/dev-assist/frontend:$IMAGE_TAG"
echo "   🌍 Region: $GCP_REGION"
echo "   🏷️  Environment: $ENVIRONMENT"
echo ""
echo "🔧 Management Commands:"
echo "   📊 View logs: gcloud run services logs read dev-assist-api --region=$GCP_REGION"
echo "   📈 View metrics: gcloud run services list --region=$GCP_REGION"
echo "   🔄 Update service: gcloud run services update SERVICE_NAME --image=NEW_IMAGE --region=$GCP_REGION"
echo ""
echo "⚠️  Note: Services are configured to scale to zero for cost optimization"
echo "   First request after idle period may experience cold start delay (~2-3 seconds)"
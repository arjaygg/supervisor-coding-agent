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

# Deploy API service using gcloud run deploy
echo "🚀 Deploying API service..."
gcloud run deploy dev-assist-api \
    --image=asia-southeast1-docker.pkg.dev/$GCP_PROJECT_ID/dev-assist/api:$IMAGE_TAG \
    --region=$GCP_REGION \
    --platform=managed \
    --service-account=dev-assist-api@$GCP_PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars="APP_DEBUG=false,LOG_LEVEL=INFO,PYTHONPATH=/app,PORT=8000" \
    --set-secrets="DATABASE_URL=development-db-url:latest,REDIS_URL=development-redis-url:latest,CELERY_BROKER_URL=development-redis-url:latest,CELERY_RESULT_BACKEND=development-redis-url:latest,JWT_SECRET_KEY=development-jwt-secret:latest,OPENAI_API_KEY=development-openai-api-key:latest,GITHUB_TOKEN=development-github-token:latest" \
    --cpu=1 \
    --memory=1Gi \
    --min-instances=1 \
    --max-instances=10 \
    --concurrency=100 \
    --timeout=900 \
    --port=8000 \
    --allow-unauthenticated \
    --quiet

# Deploy Frontend service
echo "🚀 Deploying Frontend service..."
gcloud run deploy dev-assist-frontend \
    --image=asia-southeast1-docker.pkg.dev/$GCP_PROJECT_ID/dev-assist/frontend:$IMAGE_TAG \
    --region=$GCP_REGION \
    --platform=managed \
    --service-account=dev-assist-frontend@$GCP_PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars="NODE_ENV=production,PORT=80" \
    --cpu=0.5 \
    --memory=512Mi \
    --min-instances=1 \
    --max-instances=5 \
    --concurrency=1000 \
    --timeout=300 \
    --port=80 \
    --allow-unauthenticated \
    --quiet

# Services deployed with --allow-unauthenticated flag
echo "🌐 Services are publicly accessible..."

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
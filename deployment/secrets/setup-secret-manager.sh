#!/bin/bash

# Cloud Secret Manager Setup Script
# This script creates and manages secrets for the dev-assist application

set -e

# Configuration from environment or defaults
GCP_PROJECT_ID=${GCP_PROJECT_ID:-""}
ENVIRONMENT=${ENVIRONMENT:-"development"}

echo "🔐 Setting up Cloud Secret Manager for dev-assist application"
echo "   Project: $GCP_PROJECT_ID"
echo "   Environment: $ENVIRONMENT"

# Check if project ID is set
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "❌ GCP_PROJECT_ID environment variable is required"
    exit 1
fi

# Enable Secret Manager API if not already enabled
echo "📡 Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project=$GCP_PROJECT_ID

# Create secrets with environment prefix
echo "🔑 Creating application secrets..."

# Database secrets
echo "Creating database secrets..."
if ! gcloud secrets describe "${ENVIRONMENT}-db-url" --project=$GCP_PROJECT_ID >/dev/null 2>&1; then
    echo "postgresql://supervisor:supervisor_pass@postgres:5432/supervisor_agent" | \
    gcloud secrets create "${ENVIRONMENT}-db-url" \
        --data-file=- \
        --project=$GCP_PROJECT_ID \
        --labels=environment=$ENVIRONMENT,component=database
    echo "✅ Created ${ENVIRONMENT}-db-url"
else
    echo "ℹ️  Secret ${ENVIRONMENT}-db-url already exists"
fi

# Redis secrets
echo "Creating redis secrets..."
if ! gcloud secrets describe "${ENVIRONMENT}-redis-url" --project=$GCP_PROJECT_ID >/dev/null 2>&1; then
    echo "redis://redis:6379/0" | \
    gcloud secrets create "${ENVIRONMENT}-redis-url" \
        --data-file=- \
        --project=$GCP_PROJECT_ID \
        --labels=environment=$ENVIRONMENT,component=cache
    echo "✅ Created ${ENVIRONMENT}-redis-url"
else
    echo "ℹ️  Secret ${ENVIRONMENT}-redis-url already exists"
fi

# JWT Secret Key
echo "Creating JWT secret..."
if ! gcloud secrets describe "${ENVIRONMENT}-jwt-secret" --project=$GCP_PROJECT_ID >/dev/null 2>&1; then
    # Generate a secure random JWT secret
    openssl rand -base64 32 | \
    gcloud secrets create "${ENVIRONMENT}-jwt-secret" \
        --data-file=- \
        --project=$GCP_PROJECT_ID \
        --labels=environment=$ENVIRONMENT,component=auth
    echo "✅ Created ${ENVIRONMENT}-jwt-secret"
else
    echo "ℹ️  Secret ${ENVIRONMENT}-jwt-secret already exists"
fi

# API Keys (placeholder - replace with actual values)
echo "Creating API keys..."
if ! gcloud secrets describe "${ENVIRONMENT}-openai-api-key" --project=$GCP_PROJECT_ID >/dev/null 2>&1; then
    echo "PLACEHOLDER_OPENAI_KEY" | \
    gcloud secrets create "${ENVIRONMENT}-openai-api-key" \
        --data-file=- \
        --project=$GCP_PROJECT_ID \
        --labels=environment=$ENVIRONMENT,component=ai
    echo "✅ Created ${ENVIRONMENT}-openai-api-key (placeholder)"
    echo "⚠️  Remember to update with actual OpenAI API key"
else
    echo "ℹ️  Secret ${ENVIRONMENT}-openai-api-key already exists"
fi

# GitHub Token for repository access
echo "Creating GitHub token..."
if ! gcloud secrets describe "${ENVIRONMENT}-github-token" --project=$GCP_PROJECT_ID >/dev/null 2>&1; then
    echo "PLACEHOLDER_GITHUB_TOKEN" | \
    gcloud secrets create "${ENVIRONMENT}-github-token" \
        --data-file=- \
        --project=$GCP_PROJECT_ID \
        --labels=environment=$ENVIRONMENT,component=integration
    echo "✅ Created ${ENVIRONMENT}-github-token (placeholder)"
    echo "⚠️  Remember to update with actual GitHub token"
else
    echo "ℹ️  Secret ${ENVIRONMENT}-github-token already exists"
fi

# SSL Email for Let's Encrypt
echo "Creating SSL email..."
if ! gcloud secrets describe "${ENVIRONMENT}-letsencrypt-email" --project=$GCP_PROJECT_ID >/dev/null 2>&1; then
    echo "admin@dev-assist.example.com" | \
    gcloud secrets create "${ENVIRONMENT}-letsencrypt-email" \
        --data-file=- \
        --project=$GCP_PROJECT_ID \
        --labels=environment=$ENVIRONMENT,component=ssl
    echo "✅ Created ${ENVIRONMENT}-letsencrypt-email"
else
    echo "ℹ️  Secret ${ENVIRONMENT}-letsencrypt-email already exists"
fi

echo ""
echo "📋 Secret Manager setup completed!"
echo ""
echo "📝 Created secrets:"
gcloud secrets list --filter="labels.environment=$ENVIRONMENT" --project=$GCP_PROJECT_ID --format="table(name,labels.component:label=COMPONENT,createTime.date():label=CREATED)"

echo ""
echo "🔧 Next steps:"
echo "1. Update secrets with actual values using:"
echo "   echo 'your-actual-secret' | gcloud secrets versions add SECRET_NAME --data-file=-"
echo ""
echo "2. Grant Cloud Run service access to secrets:"
echo "   gcloud secrets add-iam-policy-binding SECRET_NAME \\"
echo "     --member='serviceAccount:your-service@project.iam.gserviceaccount.com' \\"
echo "     --role='roles/secretmanager.secretAccessor'"
echo ""
echo "3. Update your containers to use Secret Manager instead of environment variables"
#!/bin/bash

# Grant GitHub Actions Service Account Cloud Run Permissions
# This script grants the GitHub Actions service account the necessary permissions to deploy to Cloud Run

set -e

# Configuration from environment or defaults
GCP_PROJECT_ID=${GCP_PROJECT_ID:-"gen-lang-client-0274960249"}
GITHUB_SERVICE_ACCOUNT=${GITHUB_SERVICE_ACCOUNT:-"github-actions@${GCP_PROJECT_ID}.iam.gserviceaccount.com"}

echo "🔐 Granting GitHub Actions service account Cloud Run permissions"
echo "   Project: $GCP_PROJECT_ID"
echo "   Service Account: $GITHUB_SERVICE_ACCOUNT"

# Check if project ID is set
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "❌ GCP_PROJECT_ID environment variable is required"
    exit 1
fi

# Set gcloud defaults
gcloud config set project $GCP_PROJECT_ID

# Grant Cloud Run Developer role
echo "🚀 Granting Cloud Run Developer role..."
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:$GITHUB_SERVICE_ACCOUNT" \
    --role="roles/run.developer" \
    --quiet

# Grant Cloud Run Service Agent role (for service management)
echo "🔧 Granting Cloud Run Service Agent role..."
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:$GITHUB_SERVICE_ACCOUNT" \
    --role="roles/run.serviceAgent" \
    --quiet

# Grant Service Account User role (to act as service accounts)
echo "👤 Granting Service Account User role..."
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:$GITHUB_SERVICE_ACCOUNT" \
    --role="roles/iam.serviceAccountUser" \
    --quiet

# Grant Cloud Build Service Account role (for container deployments)
echo "🔨 Granting Cloud Build Service Account role..."
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:$GITHUB_SERVICE_ACCOUNT" \
    --role="roles/cloudbuild.builds.builder" \
    --quiet

echo ""
echo "✅ GitHub Actions service account permissions granted!"
echo ""
echo "📋 Granted Roles:"
echo "   🚀 roles/run.developer - Deploy and manage Cloud Run services"
echo "   🔧 roles/run.serviceAgent - Manage Cloud Run service configuration"
echo "   👤 roles/iam.serviceAccountUser - Act as Cloud Run service accounts"
echo "   🔨 roles/cloudbuild.builds.builder - Build and deploy containers"
echo ""
echo "🧪 Test deployment with:"
echo "   Comment on PR: /deploy dev"
echo ""
echo "📊 Verify permissions:"
echo "   gcloud projects get-iam-policy $GCP_PROJECT_ID --flatten='bindings[].members' --format='table(bindings.role)' --filter='bindings.members:$GITHUB_SERVICE_ACCOUNT'"
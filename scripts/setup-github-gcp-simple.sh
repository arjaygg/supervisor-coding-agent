#!/bin/bash

# Simple GitHub Actions → Google Cloud Integration Setup
# Handles edge cases and provides more reliable setup

set -euo pipefail

# Configuration
PROJECT_ID="${1:-}"
REPO_OWNER="${2:-arjaygg}"
REPO_NAME="${3:-supervisor-coding-agent}"

if [[ -z "$PROJECT_ID" ]]; then
    echo "Usage: $0 <project-id> [repo-owner] [repo-name]"
    echo "Example: $0 gen-lang-client-0274960249"
    exit 1
fi

echo "🚀 Setting up GitHub Actions → Google Cloud Integration"
echo "Project: $PROJECT_ID"
echo "Repository: $REPO_OWNER/$REPO_NAME"
echo ""

read -p "Continue with setup? (Y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "Setup cancelled"
    exit 0
fi

# Default to yes if user just pressed enter
if [[ -z $REPLY ]]; then
    REPLY="Y"
fi

# Set project
gcloud config set project "$PROJECT_ID"

# Enable APIs
echo "📡 Enabling APIs..."
echo "Enabling compute.googleapis.com..."
gcloud services enable compute.googleapis.com
echo "Enabling secretmanager.googleapis.com..."
gcloud services enable secretmanager.googleapis.com
echo "Enabling iam.googleapis.com..."
gcloud services enable iam.googleapis.com
echo "Enabling cloudresourcemanager.googleapis.com..."
gcloud services enable cloudresourcemanager.googleapis.com
echo "Enabling storage.googleapis.com..."
gcloud services enable storage.googleapis.com
echo "✅ All APIs enabled"

# Create service account
echo "👤 Creating service account..."
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions CI/CD" \
  --description="Service account for GitHub Actions workflows" || echo "Service account may already exist"

SA_EMAIL="github-actions@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant permissions
echo "🔐 Granting permissions..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/compute.instanceAdmin.v1" || true

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/compute.securityAdmin" || true

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.admin" || true

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin" || true

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountTokenCreator" || true

# Create workload identity pool
echo "🔗 Creating workload identity pool..."
echo "Checking if pool 'github-pool' already exists..."
if gcloud iam workload-identity-pools describe "github-pool" --location="global" --project="$PROJECT_ID" &>/dev/null; then
    echo "✅ Pool 'github-pool' already exists"
else
    echo "Creating new workload identity pool 'github-pool'..."
    gcloud iam workload-identity-pools create "github-pool" \
        --location="global" \
        --display-name="GitHub Actions Pool" \
        --description="Pool for GitHub Actions workflows" \
        --project="$PROJECT_ID"
    echo "✅ Pool created successfully"
fi

# Wait a moment for pool to be ready
echo "Waiting 5 seconds for pool to be ready..."
sleep 5

# Create workload identity provider with simpler mapping
echo "🔗 Creating workload identity provider..."
echo "Checking if provider 'github-provider' already exists..."
if gcloud iam workload-identity-pools providers describe "github-provider" \
    --location="global" \
    --workload-identity-pool="github-pool" \
    --project="$PROJECT_ID" &>/dev/null; then
    echo "✅ Provider 'github-provider' already exists"
else
    echo "Creating new workload identity provider 'github-provider'..."
    echo "Repository being configured: ${REPO_OWNER}/${REPO_NAME}"
    gcloud iam workload-identity-pools providers create-oidc "github-provider" \
        --location="global" \
        --workload-identity-pool="github-pool" \
        --display-name="GitHub Provider" \
        --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
        --attribute-condition="assertion.repository=='${REPO_OWNER}/${REPO_NAME}'" \
        --issuer-uri="https://token.actions.githubusercontent.com" \
        --project="$PROJECT_ID"
    echo "✅ Provider created successfully"
fi

# Allow GitHub to impersonate service account
echo "🔐 Setting up impersonation..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${REPO_OWNER}/${REPO_NAME}"

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="$PRINCIPAL" \
  --project="$PROJECT_ID"

# Get provider name
PROVIDER_NAME=$(gcloud iam workload-identity-pools providers describe "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --format="value(name)" \
  --project="$PROJECT_ID")

echo ""
echo "🎉 Setup Complete!"
echo "================="
echo ""
echo "📋 Add these secrets to your GitHub repository:"
echo "Repository → Settings → Secrets and variables → Actions"
echo ""
echo "Secret Name: GCP_PROJECT_ID"
echo "Secret Value: $PROJECT_ID"
echo ""
echo "Secret Name: GCP_SERVICE_ACCOUNT_EMAIL"
echo "Secret Value: $SA_EMAIL"
echo ""
echo "Secret Name: GCP_WORKLOAD_IDENTITY_PROVIDER"
echo "Secret Value: $PROVIDER_NAME"
echo ""
echo "🧪 Test the connection by running the 'Test GCP Connection' workflow in GitHub Actions!"
echo ""
echo "✅ One-time setup complete. All future workflows will authenticate automatically."
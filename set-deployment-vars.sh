#!/bin/bash

# Set deployment environment variables
# Copy your values from GitHub Secrets here

echo "Setting up deployment environment variables..."

# Required: Your GCP Project ID
export GCP_PROJECT_ID="your-project-id-here"

# Optional: Domain configuration for SSL
export DOMAIN_NAME=""  # Leave empty for localhost testing
export LETSENCRYPT_EMAIL="admin@example.com"

# Optional: VM configuration  
export GCP_ZONE="us-central1-a"
export VM_NAME="dev-assist-vm"

echo "Environment variables set:"
echo "  GCP_PROJECT_ID: ${GCP_PROJECT_ID}"
echo "  DOMAIN_NAME: ${DOMAIN_NAME:-localhost (testing mode)}"
echo "  LETSENCRYPT_EMAIL: ${LETSENCRYPT_EMAIL}"
echo "  GCP_ZONE: ${GCP_ZONE}"
echo "  VM_NAME: ${VM_NAME}"
echo ""
echo "To deploy the nginx migration, run:"
echo "  source ./set-deployment-vars.sh"
echo "  ./deployment/gcp/deploy-nginx-migration.sh"
#!/bin/bash

# Cloud Run Setup Wrapper Script
# Simple wrapper to run the Cloud Run setup from project root

set -e

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Cloud Run Setup for Dev-Assist Application${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "deployment/cloud-run/setup-cloud-run.sh" ]; then
    echo -e "${YELLOW}⚠️  Please run this script from the project root directory${NC}"
    echo "Current directory: $(pwd)"
    echo "Expected to find: deployment/cloud-run/setup-cloud-run.sh"
    exit 1
fi

# Check for required environment variable
if [ -z "$GCP_PROJECT_ID" ]; then
    echo -e "${YELLOW}📝 GCP_PROJECT_ID not set. Please provide your Google Cloud Project ID:${NC}"
    read -p "Enter GCP Project ID: " GCP_PROJECT_ID
    export GCP_PROJECT_ID
    echo ""
fi

echo -e "${GREEN}🎯 Using Project ID: $GCP_PROJECT_ID${NC}"
echo ""

# Optional: Set other environment variables
echo -e "${BLUE}⚙️  Configuration Options (press Enter for defaults):${NC}"

# Region
read -p "GCP Region [asia-southeast1]: " GCP_REGION
GCP_REGION=${GCP_REGION:-"asia-southeast1"}
export GCP_REGION

# Environment
read -p "Environment [development]: " ENVIRONMENT
ENVIRONMENT=${ENVIRONMENT:-"development"}
export ENVIRONMENT

echo ""
echo -e "${GREEN}📋 Configuration Summary:${NC}"
echo -e "   📦 Project: $GCP_PROJECT_ID"
echo -e "   🌍 Region: $GCP_REGION"
echo -e "   🏷️  Environment: $ENVIRONMENT"
echo ""

read -p "Continue with setup? (y/N): " CONFIRM
if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}🚀 Starting Cloud Run setup...${NC}"
echo ""

# Run the actual setup script
exec ./deployment/cloud-run/setup-cloud-run.sh
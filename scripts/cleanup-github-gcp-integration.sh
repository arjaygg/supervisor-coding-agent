#!/bin/bash

# Cleanup GitHub Actions → Google Cloud Integration
# Use this script to clean up a failed setup and start fresh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_ID="${1:-}"
SERVICE_ACCOUNT_NAME="${2:-github-actions}"
POOL_NAME="github-pool"
PROVIDER_NAME="github-provider"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Show usage
show_usage() {
    cat << EOF
GitHub Actions → Google Cloud Integration Cleanup

This script cleans up a failed or partial setup so you can start fresh.

Usage: $0 <project-id> [service-account-name]

Arguments:
  project-id              Google Cloud project ID (required)
  service-account-name    Service account name (default: github-actions)

Examples:
  $0 my-gcp-project
  $0 my-gcp-project my-service-account

EOF
}

# Validate inputs
if [[ -z "$PROJECT_ID" ]]; then
    log_error "Project ID is required"
    show_usage
    exit 1
fi

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v gcloud &> /dev/null; then
        log_error "Google Cloud CLI (gcloud) is not installed"
        exit 1
    fi

    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        log_error "You are not authenticated with Google Cloud"
        exit 1
    fi

    gcloud config set project "$PROJECT_ID" &> /dev/null
    log_success "Prerequisites check passed"
}

# Cleanup workload identity provider
cleanup_provider() {
    log_info "Cleaning up Workload Identity Provider..."
    
    if gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
        --location="global" \
        --workload-identity-pool="$POOL_NAME" \
        --project="$PROJECT_ID" &> /dev/null; then
        
        log_info "Deleting Workload Identity Provider '$PROVIDER_NAME'..."
        gcloud iam workload-identity-pools providers delete "$PROVIDER_NAME" \
            --location="global" \
            --workload-identity-pool="$POOL_NAME" \
            --project="$PROJECT_ID" \
            --quiet
        log_success "Workload Identity Provider deleted"
    else
        log_info "Workload Identity Provider '$PROVIDER_NAME' not found (already clean)"
    fi
}

# Cleanup workload identity pool
cleanup_pool() {
    log_info "Cleaning up Workload Identity Pool..."
    
    if gcloud iam workload-identity-pools describe "$POOL_NAME" \
        --location="global" \
        --project="$PROJECT_ID" &> /dev/null; then
        
        log_info "Deleting Workload Identity Pool '$POOL_NAME'..."
        gcloud iam workload-identity-pools delete "$POOL_NAME" \
            --location="global" \
            --project="$PROJECT_ID" \
            --quiet
        log_success "Workload Identity Pool deleted"
    else
        log_info "Workload Identity Pool '$POOL_NAME' not found (already clean)"
    fi
}

# Cleanup service account
cleanup_service_account() {
    local sa_email="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
    log_info "Cleaning up service account..."
    
    if gcloud iam service-accounts describe "$sa_email" --project="$PROJECT_ID" &> /dev/null; then
        log_info "Deleting service account '$SERVICE_ACCOUNT_NAME'..."
        gcloud iam service-accounts delete "$sa_email" \
            --project="$PROJECT_ID" \
            --quiet
        log_success "Service account deleted"
    else
        log_info "Service account '$SERVICE_ACCOUNT_NAME' not found (already clean)"
    fi
}

# Main cleanup
main() {
    echo -e "${BLUE}🧹 GitHub Actions → Google Cloud Integration Cleanup${NC}"
    echo "This will remove all components created by the setup script."
    echo ""
    echo "Project ID: $PROJECT_ID"
    echo "Service Account: $SERVICE_ACCOUNT_NAME"
    echo ""
    
    read -p "Continue with cleanup? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cleanup cancelled"
        exit 0
    fi

    check_prerequisites
    cleanup_provider
    cleanup_pool
    cleanup_service_account
    
    log_success "Cleanup completed! You can now run the setup script again."
}

# Run main function
main
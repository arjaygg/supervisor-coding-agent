#!/bin/bash

# GitHub Actions → Google Cloud Integration Setup Script
# One-time setup to connect your GitHub repository to Google Cloud
# Uses Workload Identity Federation (secure, keyless authentication)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
PROJECT_ID=""
REPO_OWNER=""
REPO_NAME=""
SERVICE_ACCOUNT_NAME="github-actions"
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

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Show usage
show_usage() {
    cat << EOF
GitHub Actions → Google Cloud Integration Setup

This script sets up secure authentication between your GitHub repository 
and Google Cloud using Workload Identity Federation (no keys required).

Usage: $0 [options]

Options:
  --project-id PROJECT_ID     Google Cloud project ID (required)
  --repo-owner OWNER          GitHub repository owner/username (required)
  --repo-name NAME            GitHub repository name (required)
  --service-account NAME      Service account name (default: github-actions)
  --help, -h                  Show this help message

Examples:
  $0 --project-id my-gcp-project --repo-owner myusername --repo-name dev-assist
  $0 --project-id my-project --repo-owner myorg --repo-name dev-assist --service-account ci-cd

Environment Variables (alternative to flags):
  GCP_PROJECT_ID              Google Cloud project ID
  GITHUB_REPOSITORY_OWNER     GitHub repository owner
  GITHUB_REPOSITORY_NAME      GitHub repository name

EOF
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --project-id)
                PROJECT_ID="$2"
                shift 2
                ;;
            --repo-owner)
                REPO_OWNER="$2"
                shift 2
                ;;
            --repo-name)
                REPO_NAME="$2"
                shift 2
                ;;
            --service-account)
                SERVICE_ACCOUNT_NAME="$2"
                shift 2
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Try to get values from environment if not provided
    PROJECT_ID="${PROJECT_ID:-${GCP_PROJECT_ID:-}}"
    REPO_OWNER="${REPO_OWNER:-${GITHUB_REPOSITORY_OWNER:-}}"
    REPO_NAME="${REPO_NAME:-${GITHUB_REPOSITORY_NAME:-}}"

    # Auto-detect from git if in a repository
    if [[ -z "$REPO_OWNER" || -z "$REPO_NAME" ]] && [[ -d ".git" ]]; then
        local git_remote
        if git_remote=$(git remote get-url origin 2>/dev/null); then
            # Extract owner/repo from git remote URL
            if [[ "$git_remote" =~ github\.com[:/]([^/]+)/([^/.]+) ]]; then
                REPO_OWNER="${REPO_OWNER:-${BASH_REMATCH[1]}}"
                REPO_NAME="${REPO_NAME:-${BASH_REMATCH[2]}}"
                log_info "Auto-detected from git: $REPO_OWNER/$REPO_NAME"
            fi
        fi
    fi

    # Validate required parameters
    if [[ -z "$PROJECT_ID" ]]; then
        log_error "Project ID is required. Use --project-id or set GCP_PROJECT_ID"
        show_usage
        exit 1
    fi

    if [[ -z "$REPO_OWNER" ]]; then
        log_error "Repository owner is required. Use --repo-owner or set GITHUB_REPOSITORY_OWNER"
        show_usage
        exit 1
    fi

    if [[ -z "$REPO_NAME" ]]; then
        log_error "Repository name is required. Use --repo-name or set GITHUB_REPOSITORY_NAME"
        show_usage
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."

    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        log_error "Google Cloud CLI (gcloud) is not installed."
        log_info "Install it from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi

    # Check if user is authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        log_error "You are not authenticated with Google Cloud."
        log_info "Run: gcloud auth login"
        exit 1
    fi

    # Check if project exists and user has access
    if ! gcloud projects describe "$PROJECT_ID" &> /dev/null; then
        log_error "Cannot access project '$PROJECT_ID' or project does not exist."
        log_info "Make sure you have access to the project and it exists."
        exit 1
    fi

    # Set the project
    gcloud config set project "$PROJECT_ID" &> /dev/null

    log_success "Prerequisites check passed"
}

# Enable required APIs
enable_apis() {
    log_step "Enabling required Google Cloud APIs..."

    local apis=(
        "compute.googleapis.com"
        "secretmanager.googleapis.com"
        "iam.googleapis.com"
        "cloudresourcemanager.googleapis.com"
        "storage.googleapis.com"
        "containerregistry.googleapis.com"
        "artifactregistry.googleapis.com"
    )

    for api in "${apis[@]}"; do
        log_info "Enabling $api..."
        if gcloud services enable "$api" --project="$PROJECT_ID" 2>/dev/null; then
            log_success "Enabled $api"
        else
            log_warning "Failed to enable $api (may already be enabled)"
        fi
    done

    log_success "APIs enabled successfully"
}

# Create service account
create_service_account() {
    log_step "Creating service account..."

    local sa_email="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

    # Check if service account already exists
    if gcloud iam service-accounts describe "$sa_email" --project="$PROJECT_ID" &> /dev/null; then
        log_warning "Service account '$SERVICE_ACCOUNT_NAME' already exists"
    else
        log_info "Creating service account '$SERVICE_ACCOUNT_NAME'..."
        gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
            --display-name="GitHub Actions CI/CD" \
            --description="Service account for GitHub Actions workflows" \
            --project="$PROJECT_ID"

        log_success "Service account created: $sa_email"
    fi

    echo "$sa_email"
}

# Grant required permissions
grant_permissions() {
    local sa_email="$1"
    log_step "Granting permissions to service account..."

    local roles=(
        "roles/compute.instanceAdmin.v1"    # VM management
        "roles/compute.securityAdmin"       # Firewall rules
        "roles/secretmanager.admin"         # Secret management
        "roles/storage.admin"               # Container registry (GCR)
        "roles/artifactregistry.writer"     # Artifact Registry
        "roles/iam.serviceAccountTokenCreator"  # Token creation
    )

    for role in "${roles[@]}"; do
        log_info "Granting $role..."
        if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:${sa_email}" \
            --role="$role" \
            --quiet 2>/dev/null; then
            log_success "Granted $role"
        else
            log_warning "Failed to grant $role (may already exist)"
        fi
    done

    log_success "Permissions granted successfully"
}

# Create Workload Identity Pool
create_workload_identity_pool() {
    log_step "Creating Workload Identity Pool..."

    # Check if pool already exists
    if gcloud iam workload-identity-pools describe "$POOL_NAME" \
        --location="global" \
        --project="$PROJECT_ID" &> /dev/null; then
        log_warning "Workload Identity Pool '$POOL_NAME' already exists"
    else
        log_info "Creating Workload Identity Pool '$POOL_NAME'..."
        gcloud iam workload-identity-pools create "$POOL_NAME" \
            --location="global" \
            --display-name="GitHub Actions Pool" \
            --description="Pool for GitHub Actions workflows" \
            --project="$PROJECT_ID"

        log_success "Workload Identity Pool created"
    fi
}

# Create Workload Identity Provider
create_workload_identity_provider() {
    log_step "Creating Workload Identity Provider..."

    # Check if provider already exists
    if gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
        --location="global" \
        --workload-identity-pool="$POOL_NAME" \
        --project="$PROJECT_ID" &> /dev/null; then
        log_warning "Workload Identity Provider '$PROVIDER_NAME' already exists"
    else
        log_info "Creating Workload Identity Provider '$PROVIDER_NAME'..."
        gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_NAME" \
            --location="global" \
            --workload-identity-pool="$POOL_NAME" \
            --display-name="GitHub Provider" \
            --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
            --attribute-condition="assertion.repository=='${REPO_OWNER}/${REPO_NAME}'" \
            --issuer-uri="https://token.actions.githubusercontent.com" \
            --project="$PROJECT_ID"

        log_success "Workload Identity Provider created"
    fi
}

# Bind service account to workload identity
bind_service_account() {
    local sa_email="$1"
    log_step "Binding service account to Workload Identity..."

    local member="principalSet://iam.googleapis.com/projects/$(gcloud config get-value project --quiet)/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${REPO_OWNER}/${REPO_NAME}"

    log_info "Allowing GitHub repository '$REPO_OWNER/$REPO_NAME' to impersonate service account..."
    
    if gcloud iam service-accounts add-iam-policy-binding "$sa_email" \
        --role="roles/iam.workloadIdentityUser" \
        --member="$member" \
        --project="$PROJECT_ID" \
        --quiet 2>/dev/null; then
        log_success "Service account binding completed"
    else
        log_warning "Service account binding may already exist"
    fi
}

# Get configuration values
get_configuration_values() {
    log_step "Retrieving configuration values..."

    # Get service account email
    local sa_email="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

    # Get workload identity provider name
    local provider_name
    provider_name=$(gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
        --location="global" \
        --workload-identity-pool="$POOL_NAME" \
        --format="value(name)" \
        --project="$PROJECT_ID")

    echo "$sa_email|$provider_name"
}

# Display setup results
display_results() {
    local sa_email="$1"
    local provider_name="$2"

    echo ""
    echo "🎉 Setup Complete!"
    echo "==================="
    echo ""
    log_success "GitHub Actions → Google Cloud integration configured successfully!"
    echo ""
    
    echo -e "${CYAN}📋 GitHub Repository Secrets${NC}"
    echo "Add these secrets to your GitHub repository:"
    echo "Repository → Settings → Secrets and variables → Actions"
    echo ""
    echo -e "${YELLOW}Secret Name:${NC} GCP_PROJECT_ID"
    echo -e "${YELLOW}Secret Value:${NC} $PROJECT_ID"
    echo ""
    echo -e "${YELLOW}Secret Name:${NC} GCP_SERVICE_ACCOUNT_EMAIL"
    echo -e "${YELLOW}Secret Value:${NC} $sa_email"
    echo ""
    echo -e "${YELLOW}Secret Name:${NC} GCP_WORKLOAD_IDENTITY_PROVIDER"
    echo -e "${YELLOW}Secret Value:${NC} $provider_name"
    echo ""

    echo -e "${CYAN}📝 Optional Repository Variables${NC}"
    echo "Add these variables for convenience:"
    echo ""
    echo -e "${YELLOW}Variable Name:${NC} GCP_ZONE"
    echo -e "${YELLOW}Variable Value:${NC} us-central1-a"
    echo ""
    echo -e "${YELLOW}Variable Name:${NC} VM_NAME"
    echo -e "${YELLOW}Variable Value:${NC} dev-assist-vm"
    echo ""

    echo -e "${CYAN}🧪 Next Steps${NC}"
    echo "1. Add the secrets above to your GitHub repository"
    echo "2. Commit and push the GitHub Actions workflows"
    echo "3. Test the connection by creating a PR"
    echo "4. Deploy your first environment!"
    echo ""

    echo -e "${CYAN}🔗 Useful Links${NC}"
    echo "• GitHub repository: https://github.com/$REPO_OWNER/$REPO_NAME"
    echo "• Google Cloud project: https://console.cloud.google.com/home/dashboard?project=$PROJECT_ID"
    echo "• GitHub Actions: https://github.com/$REPO_OWNER/$REPO_NAME/actions"
    echo ""

    log_success "You're all set! This was a one-time setup."
}

# Test connection (optional)
test_connection() {
    log_step "Testing connection (optional)..."
    
    log_info "You can test the connection by running this command in your repository:"
    echo ""
    echo "gh workflow run 'Test GCP Connection'"
    echo ""
    log_info "Or create a test PR to trigger the ephemeral environment workflow."
}

# Main execution
main() {
    echo -e "${BLUE}🚀 GitHub Actions → Google Cloud Integration Setup${NC}"
    echo "This script will configure secure authentication between GitHub and Google Cloud"
    echo ""

    parse_arguments "$@"
    
    echo "Configuration:"
    echo "• Project ID: $PROJECT_ID"
    echo "• Repository: $REPO_OWNER/$REPO_NAME"
    echo "• Service Account: $SERVICE_ACCOUNT_NAME"
    echo ""

    read -p "Continue with setup? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Setup cancelled"
        exit 0
    fi

    check_prerequisites

    enable_apis

    local sa_email
    sa_email=$(create_service_account)

    grant_permissions "$sa_email"

    create_workload_identity_pool

    create_workload_identity_provider

    bind_service_account "$sa_email"

    local config_values
    config_values=$(get_configuration_values)
    local provider_name
    provider_name=$(echo "$config_values" | cut -d'|' -f2)

    display_results "$sa_email" "$provider_name"

    test_connection
}

# Run main function
main "$@"
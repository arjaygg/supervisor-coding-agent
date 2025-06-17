#!/bin/bash

# Dev-Assist Secrets Management Script
# Manages secrets across different environments (local, Google Secret Manager)

set -euo pipefail

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-}"
SECRETS_PROVIDER="${SECRETS_PROVIDER:-environment}"
SECRETS_FILE="${SECRETS_FILE:-.env.secrets}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if running from correct directory
    if [[ ! -f "supervisor_agent/__init__.py" ]]; then
        log_error "This script must be run from the dev-assist root directory"
        exit 1
    fi
    
    # Check for Google Cloud SDK if using GSM
    if [[ "$SECRETS_PROVIDER" == "google_secret_manager" ]]; then
        if ! command -v gcloud &> /dev/null; then
            log_error "Google Cloud CLI required for Google Secret Manager"
            exit 1
        fi
        
        if [[ -z "$PROJECT_ID" ]]; then
            log_error "GCP_PROJECT_ID environment variable required for Google Secret Manager"
            exit 1
        fi
        
        # Check authentication
        if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
            log_error "Please authenticate with Google Cloud: gcloud auth login"
            exit 1
        fi
        
        # Enable Secret Manager API
        gcloud services enable secretmanager.googleapis.com --project="$PROJECT_ID" || log_warning "Failed to enable Secret Manager API"
    fi
    
    log_success "Prerequisites check passed"
}

# List all secrets
list_secrets() {
    log_info "Listing secrets..."
    
    case "$SECRETS_PROVIDER" in
        "environment")
            log_info "Environment variables with secret-like names:"
            env | grep -E "(SECRET|PASSWORD|TOKEN|KEY|CRED)" | cut -d= -f1 | sort
            ;;
        "file")
            if [[ -d ".secrets" ]]; then
                log_info "Secrets in .secrets directory:"
                ls -la .secrets/
            else
                log_info "No .secrets directory found"
            fi
            ;;
        "google_secret_manager")
            if [[ -n "$PROJECT_ID" ]]; then
                log_info "Secrets in Google Secret Manager (project: $PROJECT_ID):"
                gcloud secrets list --project="$PROJECT_ID" --format="table(name,createTime)" 2>/dev/null || log_error "Failed to list secrets"
            fi
            ;;
        *)
            log_error "Unknown secrets provider: $SECRETS_PROVIDER"
            exit 1
            ;;
    esac
}

# Get a secret value
get_secret() {
    local secret_name="$1"
    local show_value="${2:-false}"
    
    log_info "Getting secret: $secret_name"
    
    local value=""
    
    case "$SECRETS_PROVIDER" in
        "environment")
            value=$(env | grep "^${secret_name}=" | cut -d= -f2- || echo "")
            if [[ -z "$value" ]]; then
                # Try common prefixes
                for prefix in "SECRET_" "CRED_"; do
                    value=$(env | grep "^${prefix}${secret_name}=" | cut -d= -f2- || echo "")
                    if [[ -n "$value" ]]; then
                        break
                    fi
                done
            fi
            ;;
        "file")
            if [[ -f ".secrets/$secret_name" ]]; then
                value=$(cat ".secrets/$secret_name")
            fi
            ;;
        "google_secret_manager")
            if [[ -n "$PROJECT_ID" ]]; then
                value=$(gcloud secrets versions access latest --secret="$secret_name" --project="$PROJECT_ID" 2>/dev/null || echo "")
            fi
            ;;
    esac
    
    if [[ -n "$value" ]]; then
        log_success "Secret found"
        if [[ "$show_value" == "true" ]]; then
            echo "Value: $value"
        else
            echo "Value: [HIDDEN] (use --show to display)"
        fi
    else
        log_error "Secret not found"
        exit 1
    fi
}

# Set a secret value
set_secret() {
    local secret_name="$1"
    local secret_value="$2"
    
    log_info "Setting secret: $secret_name"
    
    case "$SECRETS_PROVIDER" in
        "environment")
            log_warning "Cannot set environment variables programmatically"
            log_info "Add this to your .env file:"
            echo "$secret_name=$secret_value"
            ;;
        "file")
            mkdir -p .secrets
            echo "$secret_value" > ".secrets/$secret_name"
            chmod 600 ".secrets/$secret_name"
            log_success "Secret saved to .secrets/$secret_name"
            ;;
        "google_secret_manager")
            if [[ -n "$PROJECT_ID" ]]; then
                # Create secret if it doesn't exist
                if ! gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &>/dev/null; then
                    gcloud secrets create "$secret_name" --project="$PROJECT_ID"
                    log_info "Created new secret: $secret_name"
                fi
                
                # Add new version
                echo "$secret_value" | gcloud secrets versions add "$secret_name" --data-file=- --project="$PROJECT_ID"
                log_success "Secret version added to Google Secret Manager"
            fi
            ;;
    esac
}

# Delete a secret
delete_secret() {
    local secret_name="$1"
    
    log_warning "Deleting secret: $secret_name"
    read -p "Are you sure? (yes/no): " confirm
    
    if [[ "$confirm" != "yes" ]]; then
        log_info "Deletion cancelled"
        return
    fi
    
    case "$SECRETS_PROVIDER" in
        "environment")
            log_warning "Cannot delete environment variables programmatically"
            log_info "Remove $secret_name from your .env file manually"
            ;;
        "file")
            if [[ -f ".secrets/$secret_name" ]]; then
                rm ".secrets/$secret_name"
                log_success "Secret file deleted"
            else
                log_error "Secret file not found"
            fi
            ;;
        "google_secret_manager")
            if [[ -n "$PROJECT_ID" ]]; then
                gcloud secrets delete "$secret_name" --project="$PROJECT_ID" --quiet
                log_success "Secret deleted from Google Secret Manager"
            fi
            ;;
    esac
}

# Initialize secrets for Dev-Assist
init_secrets() {
    log_info "Initializing secrets for Dev-Assist..."
    
    # Required secrets with prompts
    local secrets=(
        "CLAUDE_API_KEYS:Claude API keys (comma-separated)"
        "SECRET_KEY:Application secret key"
        "DATABASE_PASSWORD:Database password"
        "REDIS_PASSWORD:Redis password (optional)"
        "SLACK_BOT_TOKEN:Slack bot token (optional)"
        "EMAIL_PASSWORD:Email password (optional)"
    )
    
    for secret_def in "${secrets[@]}"; do
        local secret_name=$(echo "$secret_def" | cut -d: -f1)
        local secret_prompt=$(echo "$secret_def" | cut -d: -f2)
        
        # Check if secret already exists
        if get_secret "$secret_name" &>/dev/null; then
            log_info "Secret $secret_name already exists, skipping"
            continue
        fi
        
        # Prompt for value
        echo ""
        read -p "$secret_prompt: " -s secret_value
        echo ""
        
        if [[ -n "$secret_value" ]]; then
            set_secret "$secret_name" "$secret_value"
        else
            log_info "Skipping empty secret: $secret_name"
        fi
    done
    
    # Generate random secret key if not provided
    if ! get_secret "SECRET_KEY" &>/dev/null; then
        log_info "Generating random secret key..."
        local random_key=$(openssl rand -hex 32)
        set_secret "SECRET_KEY" "$random_key"
    fi
    
    log_success "Secrets initialization completed"
}

# Migrate secrets between providers
migrate_secrets() {
    local source_provider="$1"
    local target_provider="$2"
    
    log_info "Migrating secrets from $source_provider to $target_provider"
    
    # This would require implementing cross-provider secret reading
    log_warning "Secret migration not yet implemented"
    log_info "Please manually copy secrets between providers"
}

# Generate environment file from secrets
generate_env_file() {
    local output_file="${1:-$SECRETS_FILE}"
    
    log_info "Generating environment file: $output_file"
    
    # Template for environment file
    cat > "$output_file" << 'EOF'
# Dev-Assist Environment Configuration
# Generated from secrets manager

# Application
SECRET_KEY=${SECRET_KEY}
APP_DEBUG=false
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://supervisor:${DATABASE_PASSWORD}@postgres:5432/supervisor_agent

# Redis
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# Celery
CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/0

# Claude Configuration
CLAUDE_API_KEYS=${CLAUDE_API_KEYS}
CLAUDE_QUOTA_LIMIT_PER_AGENT=1000
CLAUDE_QUOTA_RESET_HOURS=24

# Notification Configuration
SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
SLACK_CHANNEL=#alerts
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_USERNAME=${EMAIL_USERNAME}
EMAIL_PASSWORD=${EMAIL_PASSWORD}

# Security
SECRETS_PROVIDER=${SECRETS_PROVIDER}
SECRETS_AUDIT_LOGGING=true
EOF
    
    # Replace placeholders with actual values
    local temp_file=$(mktemp)
    cp "$output_file" "$temp_file"
    
    # Get all secrets referenced in the template
    local secret_names=(
        "SECRET_KEY"
        "DATABASE_PASSWORD"
        "REDIS_PASSWORD"
        "CLAUDE_API_KEYS"
        "SLACK_BOT_TOKEN"
        "EMAIL_USERNAME"
        "EMAIL_PASSWORD"
    )
    
    for secret_name in "${secret_names[@]}"; do
        local value=""
        if value=$(get_secret "$secret_name" true 2>/dev/null | grep "Value:" | cut -d' ' -f2-); then
            sed -i "s/\${$secret_name}/$value/g" "$temp_file"
        else
            # Remove lines with missing secrets
            sed -i "/\${$secret_name}/d" "$temp_file"
        fi
    done
    
    mv "$temp_file" "$output_file"
    chmod 600 "$output_file"
    
    log_success "Environment file generated: $output_file"
}

# Health check for secrets
health_check() {
    log_info "Running secrets health check..."
    
    local errors=0
    
    # Check required secrets
    local required_secrets=(
        "CLAUDE_API_KEYS"
        "SECRET_KEY"
    )
    
    for secret_name in "${required_secrets[@]}"; do
        if get_secret "$secret_name" &>/dev/null; then
            log_success "Required secret found: $secret_name"
        else
            log_error "Required secret missing: $secret_name"
            ((errors++))
        fi
    done
    
    # Check provider-specific health
    case "$SECRETS_PROVIDER" in
        "google_secret_manager")
            if [[ -n "$PROJECT_ID" ]]; then
                if gcloud secrets list --project="$PROJECT_ID" --limit=1 &>/dev/null; then
                    log_success "Google Secret Manager connection OK"
                else
                    log_error "Google Secret Manager connection failed"
                    ((errors++))
                fi
            fi
            ;;
        "file")
            if [[ -d ".secrets" ]]; then
                log_success "Local secrets directory exists"
            else
                log_warning "Local secrets directory not found"
            fi
            ;;
    esac
    
    if [[ $errors -eq 0 ]]; then
        log_success "Secrets health check passed"
        return 0
    else
        log_error "Secrets health check failed with $errors errors"
        return 1
    fi
}

# Show usage
show_usage() {
    cat << EOF
Usage: $0 <command> [options]

Commands:
  list                     List all secrets
  get <name> [--show]      Get a secret value
  set <name> <value>       Set a secret value
  delete <name>            Delete a secret
  init                     Initialize secrets for Dev-Assist
  migrate <from> <to>      Migrate secrets between providers
  generate-env [file]      Generate environment file from secrets
  health                   Check secrets health

Environment Variables:
  SECRETS_PROVIDER         Secret provider (environment|file|google_secret_manager)
  GCP_PROJECT_ID          Google Cloud project ID (for GSM)
  SECRETS_FILE            Output file for generate-env (default: .env.secrets)

Examples:
  $0 list
  $0 get CLAUDE_API_KEYS --show
  $0 set DATABASE_PASSWORD mysecretpassword
  $0 init
  
  # Using Google Secret Manager
  export SECRETS_PROVIDER=google_secret_manager
  export GCP_PROJECT_ID=my-project
  $0 list

EOF
}

# Main execution
main() {
    local command="${1:-}"
    
    if [[ -z "$command" ]]; then
        show_usage
        exit 1
    fi
    
    case "$command" in
        "list")
            check_prerequisites
            list_secrets
            ;;
        "get")
            if [[ $# -lt 2 ]]; then
                log_error "Secret name required"
                exit 1
            fi
            check_prerequisites
            local show_value="false"
            if [[ "${3:-}" == "--show" ]]; then
                show_value="true"
            fi
            get_secret "$2" "$show_value"
            ;;
        "set")
            if [[ $# -lt 3 ]]; then
                log_error "Secret name and value required"
                exit 1
            fi
            check_prerequisites
            set_secret "$2" "$3"
            ;;
        "delete")
            if [[ $# -lt 2 ]]; then
                log_error "Secret name required"
                exit 1
            fi
            check_prerequisites
            delete_secret "$2"
            ;;
        "init")
            check_prerequisites
            init_secrets
            ;;
        "migrate")
            if [[ $# -lt 3 ]]; then
                log_error "Source and target providers required"
                exit 1
            fi
            migrate_secrets "$2" "$3"
            ;;
        "generate-env")
            check_prerequisites
            generate_env_file "${2:-}"
            ;;
        "health")
            check_prerequisites
            health_check
            ;;
        "--help"|"-h"|"help")
            show_usage
            ;;
        *)
            log_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
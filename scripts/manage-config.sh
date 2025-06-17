#!/bin/bash

# Dev-Assist Configuration Management Script
# Manages environment-specific configurations and deployment profiles

set -euo pipefail

# Configuration
CONFIG_DIR="config"
DEFAULT_ENV="development"
CURRENT_ENV_FILE=".current-env"

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
    if [[ ! -d "$CONFIG_DIR" ]]; then
        log_error "Configuration directory not found: $CONFIG_DIR"
        exit 1
    fi
    
    if [[ ! -f "supervisor_agent/__init__.py" ]]; then
        log_error "This script must be run from the dev-assist root directory"
        exit 1
    fi
}

# List available environments
list_environments() {
    log_info "Available environments:"
    echo ""
    
    for env_file in "$CONFIG_DIR"/*.env; do
        if [[ -f "$env_file" ]]; then
            local env_name=$(basename "$env_file" .env)
            local current_marker=""
            
            if [[ -f "$CURRENT_ENV_FILE" ]]; then
                local current_env=$(cat "$CURRENT_ENV_FILE")
                if [[ "$current_env" == "$env_name" ]]; then
                    current_marker=" (current)"
                fi
            fi
            
            echo "  - $env_name$current_marker"
            
            # Show brief description from first comment line
            local description=$(grep "^#" "$env_file" | head -1 | sed 's/^# //')
            if [[ -n "$description" ]]; then
                echo "    $description"
            fi
        fi
    done
    
    echo ""
}

# Get current environment
get_current_environment() {
    if [[ -f "$CURRENT_ENV_FILE" ]]; then
        cat "$CURRENT_ENV_FILE"
    else
        echo "$DEFAULT_ENV"
    fi
}

# Switch to environment
switch_environment() {
    local target_env="$1"
    local env_file="$CONFIG_DIR/$target_env.env"
    
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment configuration not found: $env_file"
        exit 1
    fi
    
    log_info "Switching to environment: $target_env"
    
    # Backup current .env if it exists
    if [[ -f ".env" ]]; then
        local current_env=$(get_current_environment)
        local backup_file=".env.backup.$current_env.$(date +%Y%m%d_%H%M%S)"
        cp ".env" "$backup_file"
        log_info "Backed up current .env to: $backup_file"
    fi
    
    # Copy environment configuration
    cp "$env_file" ".env"
    echo "$target_env" > "$CURRENT_ENV_FILE"
    
    log_success "Switched to environment: $target_env"
    
    # Show warnings for production environment
    if [[ "$target_env" == "production" ]]; then
        log_warning "You are now using PRODUCTION configuration!"
        log_warning "Ensure all secrets are properly configured before deployment"
    fi
    
    # Validate configuration
    validate_configuration
}

# Validate current configuration
validate_configuration() {
    log_info "Validating configuration..."
    
    local errors=0
    local warnings=0
    
    # Check for required variables
    local required_vars=(
        "DATABASE_URL"
        "REDIS_URL"
        "CLAUDE_API_KEYS"
        "SECRET_KEY"
    )
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" .env 2>/dev/null; then
            log_error "Required variable missing: $var"
            ((errors++))
        fi
    done
    
    # Check for placeholder values
    local placeholder_patterns=(
        "your-.*-here"
        "change-in-production"
        "placeholder"
        "example"
    )
    
    for pattern in "${placeholder_patterns[@]}"; do
        if grep -qi "$pattern" .env 2>/dev/null; then
            log_warning "Placeholder values detected - update before deployment"
            ((warnings++))
        fi
    done
    
    # Environment-specific validations
    local current_env=$(get_current_environment)
    case "$current_env" in
        "production")
            # Production-specific checks
            if grep -q "APP_DEBUG=true" .env 2>/dev/null; then
                log_error "Debug mode enabled in production"
                ((errors++))
            fi
            
            if grep -q "LOG_LEVEL=DEBUG" .env 2>/dev/null; then
                log_warning "Debug logging enabled in production"
                ((warnings++))
            fi
            ;;
        "development")
            # Development-specific checks
            if grep -q "APP_DEBUG=false" .env 2>/dev/null; then
                log_warning "Debug mode disabled in development"
                ((warnings++))
            fi
            ;;
    esac
    
    # Report results
    if [[ $errors -eq 0 && $warnings -eq 0 ]]; then
        log_success "Configuration validation passed"
    elif [[ $errors -eq 0 ]]; then
        log_warning "Configuration validation passed with $warnings warnings"
    else
        log_error "Configuration validation failed with $errors errors and $warnings warnings"
        return 1
    fi
}

# Compare configurations
compare_configurations() {
    local env1="${1:-}"
    local env2="${2:-}"
    
    if [[ -z "$env1" || -z "$env2" ]]; then
        log_error "Two environment names required for comparison"
        exit 1
    fi
    
    local file1="$CONFIG_DIR/$env1.env"
    local file2="$CONFIG_DIR/$env2.env"
    
    if [[ ! -f "$file1" ]]; then
        log_error "Environment configuration not found: $file1"
        exit 1
    fi
    
    if [[ ! -f "$file2" ]]; then
        log_error "Environment configuration not found: $file2"
        exit 1
    fi
    
    log_info "Comparing configurations: $env1 vs $env2"
    echo ""
    
    # Show differences
    if command -v diff >/dev/null 2>&1; then
        diff -u "$file1" "$file2" || true
    else
        log_warning "diff command not available, showing side-by-side comparison"
        echo "=== $env1 ==="
        cat "$file1"
        echo ""
        echo "=== $env2 ==="
        cat "$file2"
    fi
}

# Generate Docker Compose override for environment
generate_compose_override() {
    local env_name="${1:-$(get_current_environment)}"
    local output_file="docker-compose.$env_name.yml"
    
    log_info "Generating Docker Compose override for: $env_name"
    
    case "$env_name" in
        "development")
            cat > "$output_file" << 'EOF'
version: '3.8'

# Development Docker Compose Override
# Enables development-specific features and relaxed settings

services:
  api:
    build:
      context: .
      target: development
    environment:
      - APP_DEBUG=true
      - LOG_LEVEL=DEBUG
    volumes:
      - .:/app
      - /app/venv  # Exclude venv from bind mount
    ports:
      - "8000:8000"
    restart: "no"
    
  worker:
    build:
      context: .
      target: development
    environment:
      - APP_DEBUG=true
      - LOG_LEVEL=DEBUG
    volumes:
      - .:/app
      - /app/venv
    restart: "no"
    
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    environment:
      - NODE_ENV=development
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    command: npm run dev
    
  postgres:
    environment:
      - POSTGRES_DB=supervisor_agent_dev
    ports:
      - "5432:5432"
    
  redis:
    ports:
      - "6379:6379"
EOF
            ;;
        "staging")
            cat > "$output_file" << 'EOF'
version: '3.8'

# Staging Docker Compose Override
# Production-like settings with staging-specific configurations

services:
  api:
    environment:
      - APP_DEBUG=false
      - LOG_LEVEL=INFO
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
    restart: unless-stopped
    
  worker:
    environment:
      - WORKER_CONCURRENCY=3
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1.5G
          cpus: '1.5'
    restart: unless-stopped
    
  frontend:
    environment:
      - NODE_ENV=production
    restart: unless-stopped
    
  postgres:
    environment:
      - POSTGRES_DB=supervisor_agent_staging
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
    restart: unless-stopped
    
  redis:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    restart: unless-stopped
EOF
            ;;
        "production")
            # Production override already exists as docker-compose.prod.yml
            log_info "Production configuration uses docker-compose.prod.yml"
            return
            ;;
        *)
            log_warning "No specific Docker Compose configuration for: $env_name"
            log_info "Using base docker-compose.yml"
            return
            ;;
    esac
    
    log_success "Docker Compose override generated: $output_file"
}

# Show environment status
show_status() {
    local current_env=$(get_current_environment)
    
    echo ""
    log_info "Environment Status"
    echo "=================="
    echo "Current environment: $current_env"
    echo "Configuration file: $CONFIG_DIR/$current_env.env"
    echo "Active .env file: $(if [[ -f .env ]]; then echo "present"; else echo "missing"; fi)"
    echo ""
    
    # Show key configuration values (non-sensitive)
    if [[ -f ".env" ]]; then
        echo "Key Configuration:"
        echo "------------------"
        grep -E "^(APP_DEBUG|LOG_LEVEL|ENVIRONMENT|SECRETS_PROVIDER)" .env 2>/dev/null || echo "No key configurations found"
        echo ""
    fi
    
    # Show last modification time
    if [[ -f ".env" ]]; then
        echo "Last modified: $(stat -c %y .env 2>/dev/null || stat -f %Sm .env 2>/dev/null || echo "unknown")"
    fi
    echo ""
}

# Create new environment
create_environment() {
    local env_name="$1"
    local template="${2:-development}"
    
    local new_file="$CONFIG_DIR/$env_name.env"
    local template_file="$CONFIG_DIR/$template.env"
    
    if [[ -f "$new_file" ]]; then
        log_error "Environment already exists: $env_name"
        exit 1
    fi
    
    if [[ ! -f "$template_file" ]]; then
        log_error "Template environment not found: $template"
        exit 1
    fi
    
    log_info "Creating new environment: $env_name (based on $template)"
    
    # Copy template and update header comment
    cp "$template_file" "$new_file"
    sed -i "1s/.*# $env_name Environment Configuration/" "$new_file" 2>/dev/null || true
    
    log_success "Environment created: $new_file"
    log_info "Edit the file to customize for your specific needs"
}

# Show usage
show_usage() {
    cat << EOF
Usage: $0 <command> [options]

Commands:
  list                         List available environments
  current                      Show current environment
  switch <env>                 Switch to environment
  validate                     Validate current configuration
  compare <env1> <env2>        Compare two environments
  status                       Show environment status
  create <name> [template]     Create new environment
  generate-compose [env]       Generate Docker Compose override

Examples:
  $0 list                      # List all environments
  $0 switch production         # Switch to production
  $0 compare development staging
  $0 create testing staging    # Create 'testing' based on 'staging'
  $0 generate-compose development

Environment Files:
  config/development.env       Development configuration
  config/staging.env          Staging configuration  
  config/production.env       Production configuration

EOF
}

# Main execution
main() {
    local command="${1:-}"
    
    if [[ -z "$command" ]]; then
        show_usage
        exit 1
    fi
    
    check_prerequisites
    
    case "$command" in
        "list")
            list_environments
            ;;
        "current")
            echo "Current environment: $(get_current_environment)"
            ;;
        "switch")
            if [[ $# -lt 2 ]]; then
                log_error "Environment name required"
                exit 1
            fi
            switch_environment "$2"
            ;;
        "validate")
            validate_configuration
            ;;
        "compare")
            if [[ $# -lt 3 ]]; then
                log_error "Two environment names required"
                exit 1
            fi
            compare_configurations "$2" "$3"
            ;;
        "status")
            show_status
            ;;
        "create")
            if [[ $# -lt 2 ]]; then
                log_error "Environment name required"
                exit 1
            fi
            create_environment "$2" "${3:-development}"
            ;;
        "generate-compose")
            generate_compose_override "${2:-}"
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
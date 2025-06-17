#!/bin/bash

# Dev-Assist Rolling Update Script
# Zero-downtime deployment with health checks and rollback capability

set -euo pipefail

# Configuration
UPDATE_STRATEGY="${UPDATE_STRATEGY:-rolling}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-300}"
HEALTH_CHECK_INTERVAL="${HEALTH_CHECK_INTERVAL:-10}"
ROLLBACK_ON_FAILURE="${ROLLBACK_ON_FAILURE:-true}"
PRE_UPDATE_BACKUP="${PRE_UPDATE_BACKUP:-true}"
DEPLOYMENT_TIMEOUT="${DEPLOYMENT_TIMEOUT:-600}"

# Global variables
BACKUP_TAG=""
DEPLOYMENT_START_TIME=""
ORIGINAL_COMPOSE_STATE=""

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
    
    if [[ ! -f "docker-compose.yml" ]]; then
        log_error "docker-compose.yml not found. Run from dev-assist root directory."
        exit 1
    fi
    
    if [[ ! -f "docker-compose.prod.yml" ]]; then
        log_error "docker-compose.prod.yml not found."
        exit 1
    fi
    
    # Check if Docker and Docker Compose are available
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    # Check if services are running
    if ! docker-compose ps | grep -q "Up"; then
        log_error "No services are currently running. Start the system first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Wait for service health
wait_for_service_health() {
    local service="$1"
    local endpoint="$2"
    local timeout="${3:-$HEALTH_CHECK_TIMEOUT}"
    local interval="${4:-$HEALTH_CHECK_INTERVAL}"
    
    log_info "Waiting for $service to be healthy..."
    
    local start_time=$(date +%s)
    local end_time=$((start_time + timeout))
    
    while [[ $(date +%s) -lt $end_time ]]; do
        if curl -f -s --max-time 5 "$endpoint" >/dev/null 2>&1; then
            log_success "$service is healthy"
            return 0
        fi
        
        log_info "Waiting for $service... ($(( ($(date +%s) - start_time) ))s elapsed)"
        sleep "$interval"
    done
    
    log_error "$service failed to become healthy within ${timeout}s"
    return 1
}

# Create backup before update
create_backup() {
    if [[ "$PRE_UPDATE_BACKUP" != "true" ]]; then
        log_info "Pre-update backup disabled"
        return 0
    fi
    
    log_info "Creating pre-update backup..."
    
    BACKUP_TAG="pre-update-$(date +%Y%m%d_%H%M%S)"
    
    # Create backup using the backup script
    if [[ -f "scripts/backup-system.sh" ]]; then
        if BACKUP_DIR="/tmp/pre-update-backups" ./scripts/backup-system.sh; then
            log_success "Pre-update backup created with tag: $BACKUP_TAG"
        else
            log_warning "Failed to create pre-update backup"
            if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
                log_error "Aborting update due to backup failure"
                exit 1
            fi
        fi
    else
        log_warning "Backup script not found, skipping backup"
    fi
}

# Save current state
save_current_state() {
    log_info "Saving current deployment state..."
    
    # Save current container states
    ORIGINAL_COMPOSE_STATE=$(docker-compose ps --format json)
    
    # Save current image tags
    docker-compose images > "/tmp/pre-update-images-$(date +%Y%m%d_%H%M%S).txt"
    
    log_success "Current state saved"
}

# Update application code
update_application_code() {
    log_info "Updating application code..."
    
    # Pull latest code from repository
    if [[ -d ".git" ]]; then
        local current_commit=$(git rev-parse HEAD)
        log_info "Current commit: $current_commit"
        
        git fetch origin
        local latest_commit=$(git rev-parse origin/main)
        
        if [[ "$current_commit" == "$latest_commit" ]]; then
            log_info "Already at latest commit"
        else
            log_info "Updating from $current_commit to $latest_commit"
            git reset --hard origin/main
            log_success "Code updated successfully"
        fi
    else
        log_warning "Not a git repository, skipping code update"
    fi
}

# Build new images
build_new_images() {
    log_info "Building new Docker images..."
    
    # Build with build cache for faster builds
    if docker-compose -f docker-compose.yml -f docker-compose.prod.yml build --parallel; then
        log_success "Images built successfully"
    else
        log_error "Failed to build images"
        return 1
    fi
}

# Rolling update strategy
rolling_update() {
    log_info "Starting rolling update..."
    
    # Define service update order (dependencies first)
    local services=("postgres" "redis" "api" "worker" "beat" "frontend")
    local updated_services=()
    
    for service in "${services[@]}"; do
        log_info "Updating service: $service"
        
        # Check if service exists in compose file
        if ! docker-compose ps "$service" >/dev/null 2>&1; then
            log_warning "Service $service not found, skipping"
            continue
        fi
        
        # For stateful services (postgres, redis), be more careful
        if [[ "$service" == "postgres" || "$service" == "redis" ]]; then
            log_info "Updating stateful service $service with care..."
            
            # Just restart to pick up any configuration changes
            docker-compose restart "$service"
            
            # Wait for service to be ready
            local max_wait=60
            local waited=0
            while [[ $waited -lt $max_wait ]]; do
                if docker-compose exec "$service" echo "Service check" >/dev/null 2>&1; then
                    break
                fi
                sleep 2
                ((waited+=2))
            done
            
            if [[ $waited -ge $max_wait ]]; then
                log_error "$service failed to restart properly"
                return 1
            fi
        else
            # For stateless services, do proper rolling update
            local replicas=1
            if [[ "$service" == "worker" ]]; then
                replicas=2  # Workers typically have multiple replicas
            fi
            
            # Update service with zero downtime
            if [[ $replicas -gt 1 ]]; then
                # Update replicas one by one
                for ((i=1; i<=replicas; i++)); do
                    log_info "Updating $service replica $i/$replicas"
                    docker-compose up -d --no-deps --scale "$service"=$replicas "$service"
                    sleep 5  # Brief pause between replica updates
                done
            else
                # Single replica update
                docker-compose up -d --no-deps "$service"
            fi
            
            # Health check for this service
            case "$service" in
                "api")
                    if ! wait_for_service_health "API" "http://localhost:8000/api/v1/healthz" 120; then
                        log_error "API service failed health check"
                        return 1
                    fi
                    ;;
                "frontend")
                    if ! wait_for_service_health "Frontend" "http://localhost:3000" 60; then
                        log_error "Frontend service failed health check"
                        return 1
                    fi
                    ;;
                "worker"|"beat")
                    # For workers, check if containers are running
                    sleep 10  # Allow time for workers to start
                    if ! docker-compose ps "$service" | grep -q "Up"; then
                        log_error "$service containers are not running properly"
                        return 1
                    fi
                    ;;
            esac
        fi
        
        updated_services+=("$service")
        log_success "Service $service updated successfully"
    done
    
    log_success "Rolling update completed for services: $(IFS=', '; echo "${updated_services[*]}")"
}

# Blue-green update strategy (alternative)
blue_green_update() {
    log_info "Blue-green deployment not implemented yet"
    log_info "Falling back to rolling update strategy"
    rolling_update
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    # Wait for API service to be ready
    if ! wait_for_service_health "API" "http://localhost:8000/api/v1/healthz" 120; then
        log_error "API service not ready for migrations"
        return 1
    fi
    
    # Run Alembic migrations
    if docker-compose exec -T api alembic upgrade head; then
        log_success "Database migrations completed successfully"
    else
        log_error "Database migrations failed"
        return 1
    fi
}

# Post-update health checks
post_update_health_checks() {
    log_info "Running post-update health checks..."
    
    local services_to_check=(
        "API:http://localhost:8000/api/v1/healthz"
        "Frontend:http://localhost:3000"
    )
    
    local failed_checks=()
    
    for check in "${services_to_check[@]}"; do
        local service=$(echo "$check" | cut -d: -f1)
        local endpoint=$(echo "$check" | cut -d: -f2)
        
        if wait_for_service_health "$service" "$endpoint" 60 5; then
            log_success "$service health check passed"
        else
            failed_checks+=("$service")
        fi
    done
    
    # Check detailed API health
    if curl -f -s "http://localhost:8000/api/v1/health/detailed" >/dev/null 2>&1; then
        log_success "Detailed API health check passed"
    else
        failed_checks+=("Detailed API")
    fi
    
    # Check worker health
    if docker-compose exec -T worker celery -A supervisor_agent.queue.celery_app inspect ping >/dev/null 2>&1; then
        log_success "Worker health check passed"
    else
        failed_checks+=("Workers")
    fi
    
    if [[ ${#failed_checks[@]} -eq 0 ]]; then
        log_success "All post-update health checks passed"
        return 0
    else
        log_error "Failed health checks: $(IFS=', '; echo "${failed_checks[*]}")"
        return 1
    fi
}

# Rollback deployment
rollback_deployment() {
    log_warning "Starting deployment rollback..."
    
    # Stop current services
    docker-compose down
    
    # Restore from backup if available
    if [[ -n "$BACKUP_TAG" && -f "scripts/restore-system.sh" ]]; then
        log_info "Restoring from backup: $BACKUP_TAG"
        
        local backup_file="/tmp/pre-update-backups/dev-assist-backup-${BACKUP_TAG#pre-update-}.tar.gz"
        if [[ -f "$backup_file" ]]; then
            FORCE_RESTORE=true ./scripts/restore-system.sh "$backup_file"
        else
            log_warning "Backup file not found, attempting simple restart"
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
        fi
    else
        log_warning "No backup available, attempting simple restart"
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    fi
    
    # Wait for rollback to complete
    if wait_for_service_health "API" "http://localhost:8000/api/v1/healthz" 120; then
        log_success "Rollback completed successfully"
    else
        log_error "Rollback failed - manual intervention required"
        exit 1
    fi
}

# Cleanup old images and containers
cleanup() {
    log_info "Cleaning up old images and containers..."
    
    # Remove dangling images
    docker image prune -f >/dev/null 2>&1 || true
    
    # Remove unused containers
    docker container prune -f >/dev/null 2>&1 || true
    
    # Remove unused networks
    docker network prune -f >/dev/null 2>&1 || true
    
    log_success "Cleanup completed"
}

# Send deployment notification
send_notification() {
    local status="$1"
    local message="$2"
    local duration="$3"
    
    # This could be extended to send Slack/email notifications
    log_info "Deployment $status: $message (Duration: ${duration}s)"
    
    # Example webhook notification
    if [[ -n "${WEBHOOK_URL:-}" ]]; then
        local payload=$(cat <<EOF
{
    "text": "🚀 Dev-Assist Deployment $status",
    "attachments": [
        {
            "color": "$([ "$status" = "SUCCESS" ] && echo "good" || echo "danger")",
            "title": "Deployment Update",
            "fields": [
                {
                    "title": "Status",
                    "value": "$status",
                    "short": true
                },
                {
                    "title": "Duration",
                    "value": "${duration}s",
                    "short": true
                },
                {
                    "title": "Message",
                    "value": "$message",
                    "short": false
                },
                {
                    "title": "Timestamp",
                    "value": "$(date)",
                    "short": true
                }
            ]
        }
    ]
}
EOF
        )
        
        curl -X POST -H 'Content-type: application/json' \
             --data "$payload" \
             "$WEBHOOK_URL" >/dev/null 2>&1 || true
    fi
}

# Main update process
main_update() {
    DEPLOYMENT_START_TIME=$(date +%s)
    
    log_info "Starting Dev-Assist deployment update at $(date)"
    
    # Setup error handling
    trap 'handle_error' ERR
    
    check_prerequisites
    save_current_state
    create_backup
    update_application_code
    build_new_images
    
    # Execute update strategy
    case "$UPDATE_STRATEGY" in
        "rolling")
            rolling_update
            ;;
        "blue-green")
            blue_green_update
            ;;
        *)
            log_error "Unknown update strategy: $UPDATE_STRATEGY"
            exit 1
            ;;
    esac
    
    run_migrations
    
    if post_update_health_checks; then
        cleanup
        
        local end_time=$(date +%s)
        local duration=$((end_time - DEPLOYMENT_START_TIME))
        
        log_success "Deployment completed successfully in ${duration} seconds"
        send_notification "SUCCESS" "Rolling update completed successfully" "$duration"
    else
        log_error "Post-update health checks failed"
        handle_error
    fi
}

# Error handling
handle_error() {
    local exit_code=$?
    log_error "Deployment failed with exit code $exit_code"
    
    if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
        rollback_deployment
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - DEPLOYMENT_START_TIME))
    send_notification "FAILED" "Deployment failed and was rolled back" "$duration"
    
    exit $exit_code
}

# Show usage
show_usage() {
    cat << EOF
Usage: $0 [options]

Options:
  --strategy STRATEGY      Update strategy (rolling|blue-green) [default: rolling]
  --no-backup             Skip pre-update backup
  --no-rollback           Don't rollback on failure
  --timeout SECONDS       Health check timeout [default: 300]
  --help, -h              Show this help message

Environment Variables:
  UPDATE_STRATEGY         Update strategy (default: rolling)
  HEALTH_CHECK_TIMEOUT    Health check timeout in seconds (default: 300)
  ROLLBACK_ON_FAILURE     Rollback on failure (default: true)
  PRE_UPDATE_BACKUP       Create backup before update (default: true)
  WEBHOOK_URL             Notification webhook URL

Examples:
  $0                           # Standard rolling update
  $0 --strategy blue-green     # Blue-green deployment
  $0 --no-backup --no-rollback # Quick update without safety nets
  $0 --timeout 600             # Extended health check timeout

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --strategy)
            UPDATE_STRATEGY="$2"
            shift 2
            ;;
        --no-backup)
            PRE_UPDATE_BACKUP="false"
            shift
            ;;
        --no-rollback)
            ROLLBACK_ON_FAILURE="false"
            shift
            ;;
        --timeout)
            HEALTH_CHECK_TIMEOUT="$2"
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

# Run main update process
main_update
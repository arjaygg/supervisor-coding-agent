#!/bin/bash

# Dev-Assist System Restore Script
# Restores system from backup created by backup-system.sh

set -euo pipefail

# Configuration
BACKUP_FILE="${1:-}"
BACKUP_BASE_DIR="${BACKUP_DIR:-/opt/dev-assist/backups}"
RESTORE_DATABASE="${RESTORE_DATABASE:-true}"
RESTORE_REDIS="${RESTORE_REDIS:-true}"
RESTORE_CONFIG="${RESTORE_CONFIG:-true}"
FORCE_RESTORE="${FORCE_RESTORE:-false}"

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

# Show usage
show_usage() {
    cat << EOF
Usage: $0 <backup-file> [options]

Arguments:
  backup-file           Path to backup file (.tar.gz)

Environment Variables:
  BACKUP_DIR           Base backup directory (default: /opt/dev-assist/backups)
  RESTORE_DATABASE     Restore database (default: true)
  RESTORE_REDIS        Restore Redis data (default: true)
  RESTORE_CONFIG       Restore configuration (default: true)
  FORCE_RESTORE        Skip confirmation prompts (default: false)

Examples:
  $0 /path/to/dev-assist-backup-20240101_120000.tar.gz
  
  # Restore only database
  RESTORE_REDIS=false RESTORE_CONFIG=false $0 backup.tar.gz
  
  # Force restore without prompts
  FORCE_RESTORE=true $0 backup.tar.gz

EOF
}

# Validate inputs
validate_inputs() {
    if [[ -z "$BACKUP_FILE" ]]; then
        log_error "Backup file not specified"
        show_usage
        exit 1
    fi
    
    if [[ ! -f "$BACKUP_FILE" ]]; then
        log_error "Backup file does not exist: $BACKUP_FILE"
        exit 1
    fi
    
    if [[ ! -f "docker-compose.yml" ]]; then
        log_error "This script must be run from the dev-assist root directory"
        exit 1
    fi
    
    log_success "Input validation passed"
}

# Extract backup
extract_backup() {
    log_info "Extracting backup file: $BACKUP_FILE"
    
    # Create temporary directory for extraction
    EXTRACT_DIR=$(mktemp -d)
    
    # Extract backup
    tar -xzf "$BACKUP_FILE" -C "$EXTRACT_DIR"
    
    # Find the backup directory (should be the only directory in extract dir)
    BACKUP_DATA_DIR=$(find "$EXTRACT_DIR" -maxdepth 1 -type d -not -path "$EXTRACT_DIR" | head -1)
    
    if [[ -z "$BACKUP_DATA_DIR" ]]; then
        log_error "Invalid backup file structure"
        rm -rf "$EXTRACT_DIR"
        exit 1
    fi
    
    log_success "Backup extracted to: $BACKUP_DATA_DIR"
}

# Verify backup integrity
verify_backup() {
    log_info "Verifying backup integrity..."
    
    # Check for required files
    local required_files=("metadata.json")
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$BACKUP_DATA_DIR/$file" ]]; then
            log_error "Missing required backup file: $file"
            exit 1
        fi
    done
    
    # Read backup metadata
    if command -v jq &> /dev/null; then
        BACKUP_DATE=$(jq -r '.backup_date' "$BACKUP_DATA_DIR/metadata.json")
        BACKUP_COMPONENTS=$(jq -r '.components[]' "$BACKUP_DATA_DIR/metadata.json")
        log_info "Backup date: $BACKUP_DATE"
        log_info "Backup components: $(echo $BACKUP_COMPONENTS | tr '\n' ' ')"
    fi
    
    log_success "Backup integrity verified"
}

# Confirmation prompt
confirm_restore() {
    if [[ "$FORCE_RESTORE" == "true" ]]; then
        return 0
    fi
    
    echo ""
    log_warning "This will restore the Dev-Assist system from backup and may overwrite current data!"
    echo ""
    echo "Restore options:"
    echo "  Database: $RESTORE_DATABASE"
    echo "  Redis: $RESTORE_REDIS"
    echo "  Configuration: $RESTORE_CONFIG"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " confirm
    
    if [[ "$confirm" != "yes" ]]; then
        log_info "Restore cancelled by user"
        exit 0
    fi
}

# Stop services
stop_services() {
    log_info "Stopping Dev-Assist services..."
    
    # Stop Docker Compose services
    docker-compose down || log_warning "Failed to stop some services"
    
    # Stop systemd service if it exists
    sudo systemctl stop dev-assist 2>/dev/null || log_warning "Systemd service not found or already stopped"
    
    log_success "Services stopped"
}

# Restore database
restore_database() {
    if [[ "$RESTORE_DATABASE" != "true" ]]; then
        log_info "Skipping database restore"
        return 0
    fi
    
    log_info "Restoring database..."
    
    # Start only PostgreSQL for restore
    docker-compose up -d postgres
    
    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    until docker-compose exec postgres pg_isready -U supervisor -d supervisor_agent; do
        echo "Waiting for PostgreSQL..."
        sleep 2
    done
    
    # Drop existing database and recreate
    docker-compose exec postgres psql -U supervisor -d postgres -c "DROP DATABASE IF EXISTS supervisor_agent;"
    docker-compose exec postgres psql -U supervisor -d postgres -c "CREATE DATABASE supervisor_agent OWNER supervisor;"
    
    # Restore from custom format dump if available
    if [[ -f "$BACKUP_DATA_DIR/database.pgdump" ]]; then
        log_info "Restoring from custom format dump..."
        docker cp "$BACKUP_DATA_DIR/database.pgdump" $(docker-compose ps -q postgres):/tmp/restore.pgdump
        docker-compose exec postgres pg_restore -U supervisor -d supervisor_agent --verbose --clean --if-exists /tmp/restore.pgdump
    elif [[ -f "$BACKUP_DATA_DIR/database.sql.gz" ]]; then
        log_info "Restoring from SQL dump..."
        gunzip -c "$BACKUP_DATA_DIR/database.sql.gz" | docker-compose exec -T postgres psql -U supervisor -d supervisor_agent
    else
        log_error "No database backup found"
        exit 1
    fi
    
    log_success "Database restored successfully"
}

# Restore Redis data
restore_redis() {
    if [[ "$RESTORE_REDIS" != "true" ]]; then
        log_info "Skipping Redis restore"
        return 0
    fi
    
    log_info "Restoring Redis data..."
    
    # Start Redis
    docker-compose up -d redis
    
    # Wait for Redis to be ready
    until docker-compose exec redis redis-cli ping; do
        echo "Waiting for Redis..."
        sleep 2
    done
    
    # Stop Redis to replace data file
    docker-compose stop redis
    
    # Replace Redis dump file if it exists
    if [[ -f "$BACKUP_DATA_DIR/redis.rdb" ]]; then
        # Copy the backup file to Redis container
        docker-compose up -d redis
        docker cp "$BACKUP_DATA_DIR/redis.rdb" $(docker-compose ps -q redis):/data/dump.rdb
        docker-compose restart redis
        
        # Wait for Redis to load the data
        until docker-compose exec redis redis-cli ping; do
            echo "Waiting for Redis to restart..."
            sleep 2
        done
        
        log_success "Redis data restored successfully"
    else
        log_warning "No Redis backup found, starting with empty Redis"
        docker-compose up -d redis
    fi
}

# Restore configuration
restore_configuration() {
    if [[ "$RESTORE_CONFIG" != "true" ]]; then
        log_info "Skipping configuration restore"
        return 0
    fi
    
    log_info "Restoring configuration..."
    
    # Backup current configuration
    mkdir -p "config-backup-$(date +%Y%m%d_%H%M%S)"
    cp .env "config-backup-$(date +%Y%m%d_%H%M%S)/" 2>/dev/null || true
    cp .env.prod "config-backup-$(date +%Y%m%d_%H%M%S)/" 2>/dev/null || true
    
    # Restore environment files
    if [[ -f "$BACKUP_DATA_DIR/env" ]]; then
        cp "$BACKUP_DATA_DIR/env" .env
        log_info "Restored .env file"
    fi
    
    if [[ -f "$BACKUP_DATA_DIR/env.prod" ]]; then
        cp "$BACKUP_DATA_DIR/env.prod" .env.prod
        log_info "Restored .env.prod file"
    fi
    
    # Restore deployment configurations
    if [[ -d "$BACKUP_DATA_DIR/deployment" ]]; then
        cp -r "$BACKUP_DATA_DIR/deployment" ./
        log_info "Restored deployment configuration"
    fi
    
    # Restore scripts
    if [[ -d "$BACKUP_DATA_DIR/scripts" ]]; then
        cp -r "$BACKUP_DATA_DIR/scripts" ./
        chmod +x scripts/*.sh
        log_info "Restored scripts"
    fi
    
    # Restore Nginx configuration (if exists)
    if [[ -f "$BACKUP_DATA_DIR/nginx/dev-assist.conf" ]]; then
        sudo cp "$BACKUP_DATA_DIR/nginx/dev-assist.conf" /etc/nginx/sites-available/dev-assist 2>/dev/null || log_warning "Could not restore Nginx configuration"
    fi
    
    # Restore SSL certificates
    if [[ -f "$BACKUP_DATA_DIR/ssl/letsencrypt.tar.gz" ]]; then
        sudo tar -xzf "$BACKUP_DATA_DIR/ssl/letsencrypt.tar.gz" -C /etc/ 2>/dev/null || log_warning "Could not restore SSL certificates"
    fi
    
    log_success "Configuration restored successfully"
}

# Start services
start_services() {
    log_info "Starting Dev-Assist services..."
    
    # Start all services
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to start..."
    sleep 30
    
    # Check service health
    if curl -f http://localhost:8000/api/v1/healthz &> /dev/null; then
        log_success "API service is healthy"
    else
        log_warning "API service may not be ready yet"
    fi
    
    # Start systemd service if it exists
    sudo systemctl start dev-assist 2>/dev/null || log_warning "Systemd service not configured"
    
    log_success "Services started"
}

# Run post-restore tasks
post_restore_tasks() {
    log_info "Running post-restore tasks..."
    
    # Run database migrations to ensure schema is up to date
    if [[ "$RESTORE_DATABASE" == "true" ]]; then
        log_info "Running database migrations..."
        docker-compose exec api alembic upgrade head || log_warning "Database migrations failed"
    fi
    
    # Clear caches
    docker-compose exec redis redis-cli FLUSHALL || log_warning "Could not clear Redis cache"
    
    # Restart workers to pick up any configuration changes
    docker-compose restart worker beat || log_warning "Could not restart workers"
    
    log_success "Post-restore tasks completed"
}

# Cleanup
cleanup() {
    log_info "Cleaning up temporary files..."
    
    if [[ -n "${EXTRACT_DIR:-}" && -d "$EXTRACT_DIR" ]]; then
        rm -rf "$EXTRACT_DIR"
    fi
    
    log_success "Cleanup completed"
}

# Verify restore
verify_restore() {
    log_info "Verifying restore..."
    
    # Check API health
    local retries=5
    while [[ $retries -gt 0 ]]; do
        if curl -f http://localhost:8000/api/v1/healthz &> /dev/null; then
            log_success "API is responding correctly"
            break
        else
            log_info "Waiting for API to be ready... ($retries retries left)"
            sleep 10
            ((retries--))
        fi
    done
    
    if [[ $retries -eq 0 ]]; then
        log_warning "API health check failed - system may need manual intervention"
    fi
    
    # Check database connectivity
    if docker-compose exec api python -c "from supervisor_agent.db.database import engine; print('Database OK' if engine.execute('SELECT 1').scalar() == 1 else 'Database Error')" 2>/dev/null | grep -q "Database OK"; then
        log_success "Database connectivity verified"
    else
        log_warning "Database connectivity check failed"
    fi
    
    # Check Redis connectivity
    if docker-compose exec redis redis-cli ping | grep -q "PONG"; then
        log_success "Redis connectivity verified"
    else
        log_warning "Redis connectivity check failed"
    fi
    
    log_success "Restore verification completed"
}

# Main execution
main() {
    local start_time=$(date +%s)
    
    log_info "Starting Dev-Assist system restore at $(date)"
    
    trap 'log_error "Restore failed!"; cleanup; exit 1' ERR
    trap 'cleanup' EXIT
    
    validate_inputs
    extract_backup
    verify_backup
    confirm_restore
    stop_services
    restore_database
    restore_redis
    restore_configuration
    start_services
    post_restore_tasks
    verify_restore
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_success "Restore completed successfully in ${duration} seconds"
    echo ""
    log_info "System has been restored from backup. Please verify that all services are working correctly."
    log_info "Check the application at: http://localhost:8000/docs"
}

# Check arguments
if [[ $# -eq 0 || "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    show_usage
    exit 0
fi

# Run main function
main "$@"
#!/bin/bash

# Dev-Assist System Backup Script
# Creates comprehensive backups of database, configuration, and application data

set -euo pipefail

# Configuration
BACKUP_BASE_DIR="${BACKUP_DIR:-/opt/dev-assist/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
GCS_BUCKET="${GCS_BACKUP_BUCKET:-}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_BASE_DIR/$TIMESTAMP"

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

# Check if running from correct directory
check_environment() {
    if [[ ! -f "docker-compose.yml" ]]; then
        log_error "This script must be run from the dev-assist root directory"
        exit 1
    fi
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    log_info "Created backup directory: $BACKUP_DIR"
}

# Backup PostgreSQL database
backup_database() {
    log_info "Starting database backup..."
    
    # Create database dump
    docker-compose exec -T postgres pg_dump -U supervisor -d supervisor_agent --verbose \
        --format=custom --compress=9 --no-owner --no-privileges \
        > "$BACKUP_DIR/database.pgdump"
    
    # Create plain SQL dump as well for easier inspection
    docker-compose exec -T postgres pg_dump -U supervisor -d supervisor_agent \
        --verbose --no-owner --no-privileges \
        | gzip > "$BACKUP_DIR/database.sql.gz"
    
    # Backup database schema only
    docker-compose exec -T postgres pg_dump -U supervisor -d supervisor_agent \
        --schema-only --verbose --no-owner --no-privileges \
        > "$BACKUP_DIR/schema.sql"
    
    log_success "Database backup completed"
}

# Backup Redis data
backup_redis() {
    log_info "Starting Redis backup..."
    
    # Create Redis snapshot
    docker-compose exec redis redis-cli BGSAVE
    
    # Wait for background save to complete
    while [[ $(docker-compose exec redis redis-cli LASTSAVE) == $(docker-compose exec redis redis-cli LASTSAVE) ]]; do
        sleep 1
    done
    
    # Copy Redis dump file
    docker-compose exec redis cp /data/dump.rdb /tmp/redis-backup.rdb
    docker cp $(docker-compose ps -q redis):/tmp/redis-backup.rdb "$BACKUP_DIR/redis.rdb"
    
    # Also backup Redis configuration
    docker-compose exec redis cat /usr/local/etc/redis/redis.conf > "$BACKUP_DIR/redis.conf"
    
    log_success "Redis backup completed"
}

# Backup application configuration
backup_configuration() {
    log_info "Starting configuration backup..."
    
    # Backup environment files
    cp .env "$BACKUP_DIR/env" 2>/dev/null || log_warning ".env file not found"
    cp .env.prod "$BACKUP_DIR/env.prod" 2>/dev/null || log_warning ".env.prod file not found"
    
    # Backup Docker Compose files
    cp docker-compose.yml "$BACKUP_DIR/"
    cp docker-compose.prod.yml "$BACKUP_DIR/"
    
    # Backup deployment configurations
    cp -r deployment "$BACKUP_DIR/" 2>/dev/null || log_warning "deployment directory not found"
    
    # Backup custom scripts
    cp -r scripts "$BACKUP_DIR/" 2>/dev/null || log_warning "scripts directory not found"
    
    # Backup Nginx configurations (if running outside Docker)
    if [[ -d "/etc/nginx/sites-available" ]]; then
        mkdir -p "$BACKUP_DIR/nginx"
        cp /etc/nginx/sites-available/dev-assist "$BACKUP_DIR/nginx/dev-assist.conf" 2>/dev/null || true
        cp /etc/nginx/nginx.conf "$BACKUP_DIR/nginx/nginx.conf" 2>/dev/null || true
    fi
    
    # Backup SSL certificates
    if [[ -d "/etc/letsencrypt" ]]; then
        mkdir -p "$BACKUP_DIR/ssl"
        sudo tar -czf "$BACKUP_DIR/ssl/letsencrypt.tar.gz" -C /etc letsencrypt 2>/dev/null || true
    fi
    
    log_success "Configuration backup completed"
}

# Backup application logs
backup_logs() {
    log_info "Starting logs backup..."
    
    mkdir -p "$BACKUP_DIR/logs"
    
    # Docker container logs
    docker-compose logs --no-color > "$BACKUP_DIR/logs/docker-compose.log" 2>/dev/null || true
    
    # Individual service logs
    for service in api worker beat postgres redis; do
        docker-compose logs --no-color "$service" > "$BACKUP_DIR/logs/$service.log" 2>/dev/null || true
    done
    
    # System logs
    sudo journalctl -u dev-assist --no-pager > "$BACKUP_DIR/logs/systemd.log" 2>/dev/null || true
    
    # Nginx logs (if available)
    if [[ -d "/var/log/nginx" ]]; then
        sudo cp /var/log/nginx/access.log "$BACKUP_DIR/logs/nginx-access.log" 2>/dev/null || true
        sudo cp /var/log/nginx/error.log "$BACKUP_DIR/logs/nginx-error.log" 2>/dev/null || true
    fi
    
    log_success "Logs backup completed"
}

# Create system information snapshot
backup_system_info() {
    log_info "Creating system information snapshot..."
    
    mkdir -p "$BACKUP_DIR/system"
    
    # System information
    uname -a > "$BACKUP_DIR/system/uname.txt"
    lsb_release -a > "$BACKUP_DIR/system/os-release.txt" 2>/dev/null || true
    df -h > "$BACKUP_DIR/system/disk-usage.txt"
    free -h > "$BACKUP_DIR/system/memory.txt"
    ps aux > "$BACKUP_DIR/system/processes.txt"
    
    # Docker information
    docker version > "$BACKUP_DIR/system/docker-version.txt" 2>/dev/null || true
    docker-compose version > "$BACKUP_DIR/system/docker-compose-version.txt" 2>/dev/null || true
    docker images > "$BACKUP_DIR/system/docker-images.txt" 2>/dev/null || true
    docker-compose ps > "$BACKUP_DIR/system/docker-services.txt" 2>/dev/null || true
    
    # Network information
    ip addr show > "$BACKUP_DIR/system/network.txt" 2>/dev/null || true
    netstat -tlnp > "$BACKUP_DIR/system/ports.txt" 2>/dev/null || true
    
    # Package information
    dpkg -l > "$BACKUP_DIR/system/packages.txt" 2>/dev/null || true
    
    log_success "System information snapshot completed"
}

# Create backup metadata
create_metadata() {
    log_info "Creating backup metadata..."
    
    cat > "$BACKUP_DIR/metadata.json" << EOF
{
    "backup_timestamp": "$TIMESTAMP",
    "backup_date": "$(date -Iseconds)",
    "hostname": "$(hostname)",
    "system": "$(uname -s)",
    "architecture": "$(uname -m)",
    "backup_type": "full",
    "components": [
        "database",
        "redis",
        "configuration",
        "logs",
        "system_info"
    ],
    "database_size": "$(du -sh "$BACKUP_DIR/database.pgdump" | cut -f1)",
    "total_size": "$(du -sh "$BACKUP_DIR" | cut -f1)",
    "retention_days": $RETENTION_DAYS
}
EOF
    
    log_success "Backup metadata created"
}

# Compress backup
compress_backup() {
    log_info "Compressing backup..."
    
    cd "$BACKUP_BASE_DIR"
    tar -czf "dev-assist-backup-$TIMESTAMP.tar.gz" "$TIMESTAMP/"
    
    # Remove uncompressed directory
    rm -rf "$TIMESTAMP"
    
    COMPRESSED_SIZE=$(du -sh "dev-assist-backup-$TIMESTAMP.tar.gz" | cut -f1)
    log_success "Backup compressed to: dev-assist-backup-$TIMESTAMP.tar.gz ($COMPRESSED_SIZE)"
}

# Upload to Google Cloud Storage
upload_to_gcs() {
    if [[ -z "$GCS_BUCKET" ]]; then
        log_info "GCS bucket not configured, skipping upload"
        return
    fi
    
    log_info "Uploading backup to Google Cloud Storage..."
    
    gsutil cp "$BACKUP_BASE_DIR/dev-assist-backup-$TIMESTAMP.tar.gz" "gs://$GCS_BUCKET/backups/"
    
    log_success "Backup uploaded to gs://$GCS_BUCKET/backups/dev-assist-backup-$TIMESTAMP.tar.gz"
}

# Cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups (older than $RETENTION_DAYS days)..."
    
    # Local cleanup
    find "$BACKUP_BASE_DIR" -name "dev-assist-backup-*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete
    
    # GCS cleanup
    if [[ -n "$GCS_BUCKET" ]]; then
        gsutil -m rm gs://$GCS_BUCKET/backups/dev-assist-backup-$(date -d "$RETENTION_DAYS days ago" +%Y%m%d)\*.tar.gz 2>/dev/null || true
    fi
    
    log_success "Cleanup completed"
}

# Verify backup integrity
verify_backup() {
    log_info "Verifying backup integrity..."
    
    # Test tar file
    if tar -tzf "$BACKUP_BASE_DIR/dev-assist-backup-$TIMESTAMP.tar.gz" > /dev/null; then
        log_success "Backup archive is valid"
    else
        log_error "Backup archive is corrupted!"
        exit 1
    fi
}

# Send notification
send_notification() {
    local status=$1
    local message=$2
    
    # This could be extended to send Slack/email notifications
    log_info "Backup $status: $message"
    
    # Example: Send to webhook
    # curl -X POST -H 'Content-type: application/json' \
    #     --data "{\"text\":\"Dev-Assist Backup $status: $message\"}" \
    #     "$SLACK_WEBHOOK_URL" 2>/dev/null || true
}

# Main execution
main() {
    local start_time=$(date +%s)
    
    log_info "Starting Dev-Assist system backup at $(date)"
    
    trap 'log_error "Backup failed!"; send_notification "FAILED" "Backup process encountered an error"; exit 1' ERR
    
    check_environment
    backup_database
    backup_redis
    backup_configuration
    backup_logs
    backup_system_info
    create_metadata
    compress_backup
    verify_backup
    upload_to_gcs
    cleanup_old_backups
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_success "Backup completed successfully in ${duration} seconds"
    send_notification "SUCCESS" "Backup completed in ${duration}s"
}

# Show usage if no arguments provided
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: $0 [options]"
    echo ""
    echo "Environment Variables:"
    echo "  BACKUP_DIR            : Base backup directory (default: /opt/dev-assist/backups)"
    echo "  RETENTION_DAYS        : Days to keep backups (default: 7)"
    echo "  GCS_BACKUP_BUCKET     : GCS bucket for remote backup (optional)"
    echo ""
    echo "Example:"
    echo "  export BACKUP_DIR=/backups"
    echo "  export GCS_BACKUP_BUCKET=my-backup-bucket"
    echo "  $0"
    exit 0
fi

# Run main function
main "$@"
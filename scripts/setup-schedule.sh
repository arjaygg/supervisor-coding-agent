#!/bin/bash

# Setup automated start/stop schedule for development VM
# Configures cron jobs to save costs during non-work hours

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_START_HOUR="${WORK_START_HOUR:-3}"    # 3 AM
WORK_END_HOUR="${WORK_END_HOUR:-15}"       # 3 PM
TIMEZONE="${TIMEZONE:-Asia/Singapore}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_usage() {
    cat << EOF
Setup automated VM scheduling for cost optimization

Usage: $0 [OPTIONS]

Options:
    --install       Install cron schedule
    --remove        Remove cron schedule  
    --status        Show current schedule
    --work-hours    Set work hours (default: 3-15)
    --timezone      Set timezone (default: Asia/Singapore)
    --help          Show this help

Examples:
    # Install default schedule (3 AM - 3 PM, Mon-Fri)
    $0 --install
    
    # Custom work hours (9 AM - 7 PM)
    WORK_START_HOUR=9 WORK_END_HOUR=19 $0 --install
    
    # Different timezone
    TIMEZONE=America/New_York $0 --install

Schedule Details:
    - VM starts at ${WORK_START_HOUR}:00 AM, Monday-Friday
    - VM stops at ${WORK_END_HOUR}:00 PM, Monday-Friday  
    - VM stops Friday evening, starts Monday morning
    - Timezone: ${TIMEZONE}

Cost Savings:
    - ~70% cost reduction for development environments
    - VM runs only ~50 hours/week instead of 168 hours/week
EOF
}

install_schedule() {
    log "Installing automated VM schedule..."
    
    # Validate environment
    if [[ -z "${GCP_PROJECT_ID:-}" ]]; then
        error "GCP_PROJECT_ID environment variable is required"
        exit 1
    fi
    
    # Make scripts executable
    chmod +x "$SCRIPT_DIR/auto-startup.sh"
    chmod +x "$SCRIPT_DIR/auto-shutdown.sh"
    
    # Create cron jobs
    CRON_TEMP=$(mktemp)
    
    # Existing cron jobs (excluding our VM automation)
    crontab -l 2>/dev/null | grep -v "dev-assist-vm" > "$CRON_TEMP" || true
    
    # Add our schedule
    cat >> "$CRON_TEMP" << EOF

# Dev-Assist VM Automation (${TIMEZONE})
# Start VM at ${WORK_START_HOUR} AM, Monday-Friday
0 ${WORK_START_HOUR} * * 1-5 TZ=${TIMEZONE} $SCRIPT_DIR/auto-startup.sh

# Stop VM at ${WORK_END_HOUR} PM, Monday-Friday  
0 ${WORK_END_HOUR} * * 1-5 TZ=${TIMEZONE} $SCRIPT_DIR/auto-shutdown.sh

# Stop VM Friday evening (in case it's still running)
0 20 * * 5 TZ=${TIMEZONE} $SCRIPT_DIR/auto-shutdown.sh

# Stop VM weekend (safety check)
0 20 * * 0,6 TZ=${TIMEZONE} $SCRIPT_DIR/auto-shutdown.sh

EOF
    
    # Install new crontab
    crontab "$CRON_TEMP"
    rm "$CRON_TEMP"
    
    success "Automated schedule installed successfully!"
    
    log "Schedule details:"
    echo "  • Start: ${WORK_START_HOUR}:00 AM (Mon-Fri)"
    echo "  • Stop:  ${WORK_END_HOUR}:00 PM (Mon-Fri)"
    echo "  • Timezone: ${TIMEZONE}"
    echo "  • Weekend: VM automatically stopped"
    
    warning "Cost savings: ~70% reduction in compute costs"
    warning "Next startup: $(date -d "next Monday ${WORK_START_HOUR}:00" 2>/dev/null || echo "Monday ${WORK_START_HOUR}:00 AM")"
}

remove_schedule() {
    log "Removing automated VM schedule..."
    
    # Remove our cron jobs
    CRON_TEMP=$(mktemp)
    crontab -l 2>/dev/null | grep -v "dev-assist-vm" > "$CRON_TEMP" || true
    crontab "$CRON_TEMP"
    rm "$CRON_TEMP"
    
    success "Automated schedule removed"
}

show_status() {
    log "Current automated schedule:"
    
    if crontab -l 2>/dev/null | grep -q "dev-assist-vm"; then
        success "Schedule is active:"
        crontab -l | grep -A 10 -B 2 "dev-assist-vm"
    else
        warning "No automated schedule found"
        echo "Use '$0 --install' to set up cost-saving automation"
    fi
}

# Parse arguments
case "${1:-}" in
    --install)
        install_schedule
        ;;
    --remove)
        remove_schedule
        ;;
    --status)
        show_status
        ;;
    --help)
        show_usage
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
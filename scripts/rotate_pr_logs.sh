#!/bin/bash
# PR Monitoring Log Rotation Script
#
# Automatically rotates PR monitoring logs to prevent disk space issues
# Usage: Add to crontab to run daily
#   0 2 * * * /path/to/rotate_pr_logs.sh

set -e

# Configuration
LOG_DIR="${SUPERVISOR_LOG_DIR:-/var/log/supervisor-agent}"
LOG_FILE="$LOG_DIR/pr_monitoring_cron.log"
MAX_SIZE_MB=10       # Rotate when log exceeds this size
KEEP_DAYS=30         # Keep rotated logs for this many days
MAX_ARCHIVES=10      # Maximum number of archived logs to keep

# Function to get file size in MB
get_file_size_mb() {
    if [[ -f "$1" ]]; then
        local size_bytes=$(stat -c%s "$1")
        echo $((size_bytes / 1024 / 1024))
    else
        echo 0
    fi
}

# Function to rotate log file
rotate_log() {
    local log_file="$1"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local rotated_file="${log_file}.${timestamp}"
    
    echo "$(date): Rotating log file $log_file (size: $(get_file_size_mb "$log_file")MB)"
    
    # Copy current log to rotated file with compression
    cp "$log_file" "$rotated_file"
    gzip "$rotated_file"
    
    # Truncate original log file (preserving file descriptor for running processes)
    > "$log_file"
    
    echo "$(date): Log rotated to ${rotated_file}.gz"
}

# Function to cleanup old log files
cleanup_old_logs() {
    local log_dir="$1"
    
    echo "$(date): Cleaning up logs older than $KEEP_DAYS days..."
    
    # Remove logs older than KEEP_DAYS
    find "$log_dir" -name "*.log.*.gz" -type f -mtime +$KEEP_DAYS -delete
    
    # Keep only MAX_ARCHIVES most recent archives
    local archives_count=$(find "$log_dir" -name "*.log.*.gz" -type f | wc -l)
    if [[ $archives_count -gt $MAX_ARCHIVES ]]; then
        echo "$(date): Found $archives_count archives, keeping only $MAX_ARCHIVES most recent"
        find "$log_dir" -name "*.log.*.gz" -type f -printf '%T@ %p\n' | \
            sort -n | head -n -$MAX_ARCHIVES | cut -d' ' -f2- | xargs rm -f
    fi
}

# Function to generate log summary
generate_summary() {
    local log_file="$1"
    
    if [[ ! -f "$log_file" ]]; then
        return
    fi
    
    echo "$(date): Current log statistics:"
    echo "  File: $log_file"
    echo "  Size: $(get_file_size_mb "$log_file")MB"
    echo "  Lines: $(wc -l < "$log_file")"
    echo "  Last modified: $(stat -c %y "$log_file")"
    
    # Recent activity summary
    echo "  Recent activity (last 10 entries):"
    tail -n 10 "$log_file" | sed 's/^/    /'
}

# Main execution
main() {
    echo "$(date): Starting PR monitoring log rotation"
    
    # Check if log file exists
    if [[ ! -f "$LOG_FILE" ]]; then
        echo "$(date): Log file $LOG_FILE not found, nothing to rotate"
        exit 0
    fi
    
    # Get current log file size
    local current_size_mb=$(get_file_size_mb "$LOG_FILE")
    
    echo "$(date): Current log size: ${current_size_mb}MB (threshold: ${MAX_SIZE_MB}MB)"
    
    # Rotate if file exceeds size threshold
    if [[ $current_size_mb -gt $MAX_SIZE_MB ]]; then
        rotate_log "$LOG_FILE"
    else
        echo "$(date): Log file under size threshold, no rotation needed"
    fi
    
    # Always cleanup old logs
    cleanup_old_logs "$LOG_DIR"
    
    # Generate summary
    generate_summary "$LOG_FILE"
    
    echo "$(date): Log rotation completed"
}

# Run main function
main "$@"
#!/bin/bash
# PR Monitoring Cron Setup Script
#
# This script sets up automated PR monitoring that runs every 10 minutes
# using the enhanced PR reviewer and merger system.
#
# Usage:
#     bash scripts/setup_pr_monitoring_cron.sh
#     bash scripts/setup_pr_monitoring_cron.sh --interval 15  # Custom interval
#     bash scripts/setup_pr_monitoring_cron.sh --remove      # Remove cron job

set -e  # Exit on any error

# Default configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PR_SCRIPT="$PROJECT_ROOT/scripts/pr_reviewer_and_merger.py"
LOG_FILE="$PROJECT_ROOT/pr_monitoring_cron.log"
INTERVAL_MINUTES=10
REMOVE_CRON=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --interval)
            INTERVAL_MINUTES="$2"
            shift 2
            ;;
        --remove)
            REMOVE_CRON=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--interval MINUTES] [--remove] [--help]"
            echo "  --interval MINUTES  Set cron interval (default: 10)"
            echo "  --remove           Remove existing cron job"
            echo "  --help             Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to remove existing cron job
remove_cron_job() {
    echo "🗑️  Removing existing PR monitoring cron job..."
    
    # Get current crontab without our job
    crontab -l 2>/dev/null | grep -v "pr_reviewer_and_merger.py" | crontab - || true
    
    echo "✅ PR monitoring cron job removed"
    exit 0
}

# Function to validate script exists and is executable
validate_script() {
    if [[ ! -f "$PR_SCRIPT" ]]; then
        echo "❌ Error: PR script not found at $PR_SCRIPT"
        exit 1
    fi
    
    if [[ ! -x "$PR_SCRIPT" ]]; then
        echo "🔧 Making PR script executable..."
        chmod +x "$PR_SCRIPT"
    fi
    
    echo "✅ PR script validated: $PR_SCRIPT"
}

# Function to test the script
test_script() {
    echo "🧪 Testing PR script in dry-run mode..."
    
    cd "$PROJECT_ROOT"
    if python3 "$PR_SCRIPT" --dry-run >/dev/null 2>&1; then
        echo "✅ PR script test successful"
    else
        echo "❌ PR script test failed. Please check the script manually:"
        echo "   cd $PROJECT_ROOT && python3 $PR_SCRIPT --dry-run"
        exit 1
    fi
}

# Function to setup cron job
setup_cron_job() {
    echo "⏰ Setting up PR monitoring cron job (every $INTERVAL_MINUTES minutes)..."
    
    # Create cron command
    CRON_COMMAND="cd $PROJECT_ROOT && python3 $PR_SCRIPT >> $LOG_FILE 2>&1"
    
    # Calculate cron schedule
    if [[ $INTERVAL_MINUTES -eq 10 ]]; then
        CRON_SCHEDULE="*/10 * * * *"
    elif [[ $INTERVAL_MINUTES -eq 15 ]]; then
        CRON_SCHEDULE="*/15 * * * *"
    elif [[ $INTERVAL_MINUTES -eq 5 ]]; then
        CRON_SCHEDULE="*/5 * * * *"
    elif [[ $INTERVAL_MINUTES -eq 30 ]]; then
        CRON_SCHEDULE="*/30 * * * *"
    elif [[ $INTERVAL_MINUTES -eq 60 ]]; then
        CRON_SCHEDULE="0 * * * *"
    else
        # For custom intervals, use the closest standard interval
        if [[ $INTERVAL_MINUTES -lt 8 ]]; then
            CRON_SCHEDULE="*/5 * * * *"
            echo "⚠️  Interval $INTERVAL_MINUTES minutes rounded to 5 minutes"
        elif [[ $INTERVAL_MINUTES -lt 13 ]]; then
            CRON_SCHEDULE="*/10 * * * *"
            echo "⚠️  Interval $INTERVAL_MINUTES minutes rounded to 10 minutes"
        elif [[ $INTERVAL_MINUTES -lt 23 ]]; then
            CRON_SCHEDULE="*/15 * * * *"
            echo "⚠️  Interval $INTERVAL_MINUTES minutes rounded to 15 minutes"
        elif [[ $INTERVAL_MINUTES -lt 45 ]]; then
            CRON_SCHEDULE="*/30 * * * *"
            echo "⚠️  Interval $INTERVAL_MINUTES minutes rounded to 30 minutes"
        else
            CRON_SCHEDULE="0 * * * *"
            echo "⚠️  Interval $INTERVAL_MINUTES minutes rounded to 60 minutes"
        fi
    fi
    
    # Remove any existing PR monitoring cron job
    crontab -l 2>/dev/null | grep -v "pr_reviewer_and_merger.py" | crontab - || true
    
    # Add new cron job
    (crontab -l 2>/dev/null; echo "$CRON_SCHEDULE $CRON_COMMAND") | crontab -
    
    echo "✅ Cron job added successfully!"
    echo "   Schedule: $CRON_SCHEDULE"
    echo "   Command: $CRON_COMMAND"
    echo "   Log file: $LOG_FILE"
}

# Function to show current status
show_status() {
    echo "📊 PR Monitoring Status:"
    echo "   Project: $PROJECT_ROOT"
    echo "   Script: $PR_SCRIPT"
    echo "   Log: $LOG_FILE"
    echo ""
    
    if crontab -l 2>/dev/null | grep -q "pr_reviewer_and_merger.py"; then
        echo "✅ Cron job is active:"
        crontab -l | grep "pr_reviewer_and_merger.py"
    else
        echo "❌ No cron job found"
    fi
    
    echo ""
    
    if [[ -f "$LOG_FILE" ]]; then
        echo "📋 Recent log entries:"
        tail -10 "$LOG_FILE" 2>/dev/null || echo "   (log file empty)"
    else
        echo "📋 No log file found (will be created on first run)"
    fi
}

# Main execution
main() {
    echo "🤖 Enhanced PR Monitoring Setup"
    echo "================================"
    
    if [[ "$REMOVE_CRON" == "true" ]]; then
        remove_cron_job
        return
    fi
    
    validate_script
    test_script
    setup_cron_job
    
    echo ""
    show_status
    
    echo ""
    echo "🎉 PR monitoring setup complete!"
    echo ""
    echo "The system will now:"
    echo "  • Check for open PRs every $INTERVAL_MINUTES minutes"
    echo "  • Analyze and fix failing checks automatically" 
    echo "  • Approve and merge PRs that pass all criteria"
    echo "  • Log all activity to $LOG_FILE"
    echo ""
    echo "💡 Monitor activity with: tail -f $LOG_FILE"
    echo "💡 View cron job with: crontab -l"
    echo "💡 Remove cron job with: $0 --remove"
}

# Run main function
main "$@"
#!/bin/bash

echo "🔴 LIVE PR MONITOR ACTIVITY VIEWER"
echo "=================================="
echo "Press Ctrl+C to stop watching"
echo ""

# Create a function to show timestamped activity
show_activity() {
    echo "$(date '+%H:%M:%S') - $1"
}

# Track the last known state
last_pr77_status=""
last_pr78_status=""
last_workflow_count=0

while true; do
    clear
    echo "🔴 LIVE PR MONITOR ACTIVITY - $(date)"
    echo "====================================="
    echo ""
    
    # Show monitor process status
    if pgrep -f 'pr_monitor.py' > /dev/null; then
        echo "🟢 Monitor Status: ACTIVE (PID: $(pgrep -f 'pr_monitor.py' | head -1))"
    else
        echo "🔴 Monitor Status: NOT RUNNING"
    fi
    echo ""
    
    # Show recent monitor activity (last 5 minutes)
    echo "📝 Recent Monitor Activity (last 5 minutes):"
    echo "--------------------------------------------"
    if [ -f /tmp/pr_monitor_continuous.log ]; then
        # Show only recent entries (last 5 minutes)
        recent_time=$(date -d '5 minutes ago' '+%Y-%m-%d %H:%M:%S')
        tail -20 /tmp/pr_monitor_continuous.log | while read line; do
            if [[ $line =~ [0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2} ]]; then
                timestamp=$(echo "$line" | cut -d',' -f1)
                if [[ "$timestamp" > "$recent_time" ]]; then
                    if [[ $line == *"ERROR"* ]]; then
                        echo "❌ $line"
                    elif [[ $line == *"Processing PR"* ]]; then
                        echo "🔄 $line"
                    elif [[ $line == *"Triggering workflow"* ]]; then
                        echo "🚀 $line"
                    elif [[ $line == *"Successfully"* ]]; then
                        echo "✅ $line"
                    else
                        echo "ℹ️  $line"
                    fi
                fi
            fi
        done
    else
        echo "❌ No monitor log found"
    fi
    echo ""
    
    # Show PR status changes
    echo "📊 Current PR Status:"
    echo "--------------------"
    
    # Check PR #77
    pr77_status=$(gh pr view 77 --json statusCheckRollup 2>/dev/null | jq -r '.statusCheckRollup | map(select(.conclusion == "FAILURE")) | length')
    pr77_workflow=$(gh pr view 77 --json statusCheckRollup 2>/dev/null | jq -r '.statusCheckRollup | map(select(.status == "IN_PROGRESS")) | length')
    
    if [ "$pr77_status" != "$last_pr77_status" ]; then
        show_activity "PR #77 status changed: $pr77_status failing checks"
        last_pr77_status="$pr77_status"
    fi
    
    echo "🔍 PR #77: $pr77_status failing checks, $pr77_workflow in progress"
    
    # Check PR #78  
    pr78_status=$(gh pr view 78 --json statusCheckRollup 2>/dev/null | jq -r '.statusCheckRollup | map(select(.conclusion == "FAILURE")) | length')
    pr78_workflow=$(gh pr view 78 --json statusCheckRollup 2>/dev/null | jq -r '.statusCheckRollup | map(select(.status == "IN_PROGRESS")) | length')
    
    if [ "$pr78_status" != "$last_pr78_status" ]; then
        show_activity "PR #78 status changed: $pr78_status failing checks"
        last_pr78_status="$pr78_status"
    fi
    
    echo "🔍 PR #78: $pr78_status failing checks, $pr78_workflow in progress"
    echo ""
    
    # Show running workflows
    echo "🚀 Active Workflows:"
    echo "-------------------"
    running_workflows=$(gh run list --status in_progress --limit=3 2>/dev/null | tail -n +2)
    if [ -n "$running_workflows" ]; then
        echo "$running_workflows"
    else
        echo "No workflows currently running"
    fi
    echo ""
    
    # Show next check countdown
    if [ -f /tmp/pr_monitor_continuous.log ]; then
        last_activity=$(stat -c %Y /tmp/pr_monitor_continuous.log 2>/dev/null || echo 0)
        now=$(date +%s)
        seconds_since=$((now - last_activity))
        next_check=$((300 - seconds_since))
        
        if [ $next_check -gt 0 ]; then
            echo "⏰ Next monitor check in: ${next_check}s"
        else
            echo "⏰ Monitor check should happen soon..."
        fi
    fi
    
    echo ""
    echo "📋 Commands:"
    echo "  - Ctrl+C: Stop watching"
    echo "  - ./verify_monitoring.sh: Full verification"
    echo "  - ./pr_status.sh: Detailed status"
    
    sleep 5
done
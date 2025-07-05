#!/bin/bash
# PR Monitor Status Checker

echo "🤖 PR Monitor Status Check"
echo "=========================="

# Check if process is running
PID=$(pgrep -f "pr_monitor.py")
if [ -n "$PID" ]; then
    echo "✅ Process Status: RUNNING (PID: $PID)"
    
    # Get process start time
    STARTED=$(ps -o lstart= -p $PID)
    echo "📅 Started: $STARTED"
    
    # Get CPU and memory usage
    USAGE=$(ps -o %cpu,%mem,time= -p $PID)
    echo "💻 Usage: CPU/MEM/TIME = $USAGE"
else
    echo "❌ Process Status: NOT RUNNING"
fi

echo ""

# Check log file
if [ -f "pr_monitor.log" ]; then
    LOG_SIZE=$(du -h pr_monitor.log | cut -f1)
    LOG_LINES=$(wc -l < pr_monitor.log)
    LAST_UPDATE=$(stat -c %y pr_monitor.log | cut -d. -f1)
    
    echo "📋 Log Status:"
    echo "   Size: $LOG_SIZE"
    echo "   Lines: $LOG_LINES"
    echo "   Last Update: $LAST_UPDATE"
    
    echo ""
    echo "📝 Last 5 Log Entries:"
    echo "----------------------"
    tail -5 pr_monitor.log | while read line; do
        echo "   $line"
    done
else
    echo "❌ Log file not found"
fi

echo ""

# Check for recent PR activity
echo "🔍 Current PRs:"
gh pr list --state open --json number,title,updatedAt 2>/dev/null | jq -r '.[] | "   PR #\(.number): \(.title) (updated: \(.updatedAt))"' 2>/dev/null || echo "   Unable to fetch PR list"

echo ""
echo "⏰ Next check in ~5 minutes (every 300 seconds)"
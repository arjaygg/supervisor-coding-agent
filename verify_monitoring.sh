#!/bin/bash

echo "🔍 PR MONITORING VERIFICATION DASHBOARD"
echo "======================================"
echo ""

# Function to check if process is running
check_process() {
    if pgrep -f "$1" > /dev/null; then
        echo "✅ RUNNING"
    else
        echo "❌ NOT RUNNING"
    fi
}

# Function to get time since last activity
time_since() {
    if [ -f "$1" ]; then
        local last_mod=$(stat -c %Y "$1" 2>/dev/null || echo 0)
        local now=$(date +%s)
        local diff=$((now - last_mod))
        local minutes=$((diff / 60))
        echo "${minutes}m ago"
    else
        echo "No activity"
    fi
}

echo "1️⃣ MONITORING PROCESSES STATUS:"
echo "------------------------------"
echo "PR Monitor Process: $(check_process 'pr_monitor.py')"
echo "Active Monitor PIDs: $(pgrep -f 'pr_monitor.py' | tr '\n' ' ')"
echo ""

echo "2️⃣ RECENT ACTIVITY VERIFICATION:"
echo "--------------------------------"
echo "Last Log Activity: $(time_since '/tmp/pr_monitor_continuous.log')"
echo "Last General Activity: $(time_since '/tmp/pr_monitor.log')"
echo ""

echo "3️⃣ WORKFLOW RUNS (LAST 24 HOURS):"
echo "----------------------------------"
echo "Recent workflow triggers by monitor:"
gh run list --workflow="PR Merge Gate - Integration Tests" --created=">=2025-07-04" --limit=10 | head -11
echo ""

echo "4️⃣ LIVE MONITORING LOG (LAST 10 ENTRIES):"
echo "------------------------------------------"
if [ -f /tmp/pr_monitor_continuous.log ]; then
    echo "Continuous Monitor Activity:"
    tail -10 /tmp/pr_monitor_continuous.log | while read line; do
        if [[ $line == *"INFO"* ]]; then
            echo "ℹ️  $line"
        elif [[ $line == *"ERROR"* ]]; then
            echo "❌ $line"
        elif [[ $line == *"WARNING"* ]]; then
            echo "⚠️  $line"
        else
            echo "   $line"
        fi
    done
else
    echo "❌ No continuous monitor log found"
fi
echo ""

echo "5️⃣ PR STATUS CHANGES VERIFICATION:"
echo "----------------------------------"
echo "Checking for recent status changes..."
for pr_num in $(gh pr list --state open --json number --jq '.[].number'); do
    echo ""
    echo "🔍 PR #$pr_num Status:"
    echo "  Workflow Status: $(gh pr view $pr_num --json statusCheckRollup --jq '.statusCheckRollup[0].status // "No checks"')"
    echo "  Last Updated: $(gh pr view $pr_num --json updatedAt --jq '.updatedAt')"
    
    # Check for recent commits (automated fixes)
    recent_commits=$(gh pr view $pr_num --json commits --jq '.commits[-3:] | map(select(.messageHeadline | contains("automated") or contains("fix:") or contains("🤖"))) | length')
    if [ "$recent_commits" -gt 0 ]; then
        echo "  ✅ Has $recent_commits recent automated fix commits"
        gh pr view $pr_num --json commits --jq '.commits[-3:] | map(select(.messageHeadline | contains("automated") or contains("fix:") or contains("🤖"))) | .[] | "    - \(.messageHeadline)"'
    else
        echo "  ⏳ No recent automated commits detected"
    fi
done
echo ""

echo "6️⃣ AUTO-MERGE VERIFICATION:"
echo "---------------------------"
echo "Checking for recent merges..."
merged_today=$(gh pr list --state merged --search "merged:>=2025-07-04" --json number,title,mergedAt | jq -r '.[] | "✅ PR #\(.number): \(.title) (merged: \(.mergedAt))"')
if [ -n "$merged_today" ]; then
    echo "$merged_today"
else
    echo "⏳ No PRs auto-merged today yet"
fi
echo ""

echo "7️⃣ REAL-TIME WORKFLOW STATUS:"
echo "-----------------------------"
echo "Currently running workflows:"
gh run list --status in_progress --limit=5 | head -6
echo ""

echo "8️⃣ MONITORING HEALTH CHECK:"
echo "---------------------------"
# Check if monitor is stuck or working
if [ -f /tmp/pr_monitor_continuous.log ]; then
    last_activity=$(stat -c %Y /tmp/pr_monitor_continuous.log)
    now=$(date +%s)
    minutes_since=$(( (now - last_activity) / 60 ))
    
    if [ $minutes_since -lt 10 ]; then
        echo "✅ Monitor is ACTIVE (last activity: ${minutes_since}m ago)"
    elif [ $minutes_since -lt 30 ]; then
        echo "⚠️  Monitor may be slow (last activity: ${minutes_since}m ago)"
    else
        echo "❌ Monitor appears STUCK (last activity: ${minutes_since}m ago)"
        echo "   Recommend restarting monitor"
    fi
else
    echo "❌ No monitor log found - monitor may not be running"
fi
echo ""

echo "9️⃣ NEXT EXPECTED ACTIONS:"
echo "-------------------------"
for pr_num in $(gh pr list --state open --json number --jq '.[].number'); do
    status=$(gh pr view $pr_num --json statusCheckRollup --jq '.statusCheckRollup | map(select(.conclusion == "FAILURE")) | length')
    if [ "$status" -gt 0 ]; then
        echo "🔄 PR #$pr_num: Will be processed next (has $status failing checks)"
    else
        in_progress=$(gh pr view $pr_num --json statusCheckRollup --jq '.statusCheckRollup | map(select(.status == "IN_PROGRESS")) | length')
        if [ "$in_progress" -gt 0 ]; then
            echo "⏳ PR #$pr_num: Workflows running ($in_progress in progress)"
        else
            echo "✅ PR #$pr_num: Ready for merge review"
        fi
    fi
done
echo ""

echo "🎯 VERIFICATION SUMMARY:"
echo "----------------------"
echo "✅ Run this script anytime: ./verify_monitoring.sh"
echo "📊 Check detailed status: ./pr_status.sh"
echo "📝 View live logs: tail -f /tmp/pr_monitor_continuous.log"
echo "🔄 Restart monitor if needed: python3 scripts/pr_monitor.py &"
echo ""
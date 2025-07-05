#!/bin/bash

echo "🔍 COMPREHENSIVE PR MONITORING STATUS"
echo "===================================="
echo ""

echo "📊 CURRENT OPEN PRS:"
echo "-------------------"
gh pr list --state open --json number,title,headRefName,updatedAt | jq -r '.[] | "PR #\(.number): \(.title) (\(.headRefName))"'
echo ""

echo "🤖 MONITOR PROCESSES:"
echo "--------------------"
ps aux | grep pr_monitor | grep -v grep || echo "No monitor processes running"
echo ""

echo "📈 RECENT WORKFLOW RUNS:"
echo "------------------------"
gh run list --workflow="PR Merge Gate - Integration Tests" --limit=5 | head -6
echo ""

echo "🔍 PR #77 STATUS:"
echo "-----------------"
gh pr view 77 --json statusCheckRollup | jq -r '.statusCheckRollup[] | "\(.name): \(.conclusion) (\(.status))"'
echo ""

echo "🔍 PR #78 STATUS:"
echo "-----------------"
gh pr view 78 --json statusCheckRollup | jq -r '.statusCheckRollup[] | "\(.name): \(.conclusion) (\(.status))"'
echo ""

echo "📝 RECENT MONITOR ACTIVITY:"
echo "---------------------------"
if [ -f /tmp/pr_monitor_continuous.log ]; then
    echo "Continuous Monitor (last 5 lines):"
    tail -5 /tmp/pr_monitor_continuous.log
else
    echo "No continuous monitor log found"
fi
echo ""

echo "⏰ MONITORING STATUS:"
echo "--------------------"
if pgrep -f "pr_monitor.py" > /dev/null; then
    echo "✅ PR Monitor is ACTIVE and running"
    echo "📊 Monitoring frequency: Every 5 minutes"
    echo "🎯 Auto-processing PRs with failing checks"
    echo "🔄 Auto-triggering workflow re-runs"
    echo "✅ Auto-merging when all checks pass"
else
    echo "❌ PR Monitor is NOT running"
fi

echo ""
echo "🎯 NEXT ACTIONS:"
echo "---------------"
echo "• Monitor will automatically:"
echo "  - Process PRs with failing checks"
echo "  - Apply code quality fixes"
echo "  - Re-trigger workflows"
echo "  - Auto-merge when ready"
echo "• Manual intervention only needed for complex issues"
echo ""
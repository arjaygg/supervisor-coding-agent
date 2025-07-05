#!/bin/bash

echo "🔍 PR REVIEW VERIFICATION DASHBOARD"
echo "=================================="
echo ""

echo "1️⃣ REVIEW ACTIVITY VERIFICATION:"
echo "--------------------------------"

echo "📝 Recent Automated Review Comments:"
echo "-----------------------------------"
for pr_num in $(gh pr list --state open --json number --jq '.[].number'); do
    echo ""
    echo "🔍 PR #$pr_num Review History:"
    
    # Check for automated review comments
    automated_reviews=$(gh pr view $pr_num --json comments --jq '[.comments[] | select(.body | contains("🤖 Automated review")) | {author: .author.login, createdAt: .createdAt, preview: .body[0:100]}]')
    
    if [ "$automated_reviews" != "[]" ]; then
        echo "✅ Has automated reviews:"
        echo "$automated_reviews" | jq -r '.[] | "  📅 \(.createdAt) by \(.author): \(.preview)..."'
    else
        echo "⏳ No automated reviews yet"
    fi
    
    # Check for manual reviews
    manual_reviews=$(gh pr view $pr_num --json reviews --jq 'length')
    echo "👥 Manual reviews: $manual_reviews"
    
    # Check review requests
    review_requests=$(gh pr view $pr_num --json reviewRequests --jq 'length')
    echo "📋 Review requests: $review_requests"
done

echo ""
echo "2️⃣ REVIEW COMMENT CONTENT VERIFICATION:"
echo "---------------------------------------"
echo "Latest automated review content:"
latest_review=$(gh pr view 77 --json comments --jq '.comments[] | select(.body | contains("🤖 Automated review")) | .body' | tail -1)
if [ -n "$latest_review" ]; then
    echo "$latest_review" | head -20
    echo "..."
    echo "(truncated - full review visible in PR)"
else
    echo "❌ No automated reviews found"
fi

echo ""
echo "3️⃣ APPROVAL STATUS:"
echo "-------------------"
for pr_num in $(gh pr list --state open --json number --jq '.[].number'); do
    echo "🔍 PR #$pr_num:"
    
    # Check approval status
    approvals=$(gh pr view $pr_num --json reviews --jq '[.reviews[] | select(.state == "APPROVED")] | length')
    changes_requested=$(gh pr view $pr_num --json reviews --jq '[.reviews[] | select(.state == "CHANGES_REQUESTED")] | length')
    
    echo "  ✅ Approvals: $approvals"
    echo "  🔴 Changes Requested: $changes_requested"
    
    # Check if ready for merge
    mergeable=$(gh pr view $pr_num --json mergeable --jq '.mergeable')
    echo "  🔀 Mergeable: $mergeable"
done

echo ""
echo "4️⃣ AUTOMATED REVIEW WORKFLOW:"
echo "-----------------------------"
echo "✅ What the system does:"
echo "  1. 🔍 Monitors PRs every 5 minutes"
echo "  2. 🛠️  Applies automated code fixes"
echo "  3. 📝 Posts comprehensive review comments"
echo "  4. 🔄 Re-reviews after workflow completion"
echo "  5. ✅ Auto-approves when all checks pass"
echo "  6. 🔀 Auto-merges ready PRs"

echo ""
echo "5️⃣ MONITOR STATUS:"
echo "-----------------"
if pgrep -f pr_monitor.py > /dev/null; then
    echo "✅ PR Monitor with Reviews: ACTIVE"
    echo "📊 Monitor logs: tail -f /tmp/pr_monitor_with_reviews.log"
else
    echo "❌ PR Monitor: NOT RUNNING"
fi

echo ""
echo "6️⃣ VERIFICATION COMMANDS:"
echo "-------------------------"
echo "# View latest review comments:"
echo "gh pr view 77 --comments"
echo ""
echo "# Check review history:"
echo "gh pr view 77 --json reviews"
echo ""
echo "# Watch live monitor activity:"
echo "tail -f /tmp/pr_monitor_with_reviews.log"
echo ""
echo "# Manual review test:"
echo "python3 scripts/pr_monitor.py --max-iterations 1"
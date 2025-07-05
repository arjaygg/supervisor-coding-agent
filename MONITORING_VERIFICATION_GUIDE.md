# 🔍 PR Monitoring Verification Guide

## How to Verify PR Monitoring, Code Review, and Auto-Merge is Working

### 🚀 **Quick Verification Commands**

```bash
# 1. Check if monitor is running
./verify_monitoring.sh

# 2. Watch live activity  
./watch_monitor.sh

# 3. Check detailed PR status
./pr_status.sh

# 4. View live logs
tail -f /tmp/pr_monitor_continuous.log
```

---

## 📊 **What to Look For**

### ✅ **Signs Monitor is Working:**

1. **Process Running:**
   ```bash
   ps aux | grep pr_monitor
   # Should show: python3 scripts/pr_monitor.py
   ```

2. **Recent Log Activity:**
   ```bash
   tail -5 /tmp/pr_monitor_continuous.log
   # Should show entries within last 5 minutes
   ```

3. **Automated Commits:**
   ```bash
   gh pr view 77 --json commits | jq '.commits[-3:] | map(.messageHeadline)'
   # Should show commits with "automated" or "fix:" or "🤖"
   ```

4. **Workflow Triggers:**
   ```bash
   gh run list --limit 5
   # Should show recent workflow runs
   ```

### 🔄 **Evidence of Code Review:**

- **Automated Commits**: Look for commits with messages like:
  - `fix: automated code quality improvements for PR #77`
  - Messages containing `🤖` emoji
  - Commits by the monitor process

- **Code Changes**: Check for:
  - Black formatting applied
  - Import sorting (isort)
  - Unused import removal
  - Line length fixes

### 🎯 **Evidence of Auto-Merge Attempts:**

- **Monitor Logs**: Look for:
  ```
  INFO - PR #XX ready for auto-merge
  INFO - Successfully auto-merged PR #XX
  ```

- **Merged PRs**: Check for recent merges:
  ```bash
  gh pr list --state merged --search "merged:>=2025-07-04"
  ```

---

## 🔍 **Detailed Verification Steps**

### Step 1: Verify Monitor Health
```bash
./verify_monitoring.sh
```
**Expected Output:**
- ✅ PR Monitor Process: RUNNING  
- ✅ Monitor is ACTIVE (last activity: <5m ago)
- Shows recent workflow runs
- Shows automated commits

### Step 2: Watch Real-Time Activity
```bash
./watch_monitor.sh
```
**What You'll See:**
- Live monitor status updates
- PR status changes in real-time
- Workflow triggers as they happen
- Countdown to next check

### Step 3: Verify Code Review Activity
```bash
# Check for recent automated commits
gh pr view 77 --json commits | jq '.commits[-5:] | map(select(.messageHeadline | contains("automated") or contains("fix:") or contains("🤖")))'

# Check for code formatting changes
git log --oneline -5 | grep -E "(fix:|automated|🤖)"
```

### Step 4: Check Auto-Merge Logic
```bash
# Check if any PRs are ready for merge
gh pr list --state open --json number,mergeable,statusCheckRollup

# Look for merge attempts in logs
grep -i "merge" /tmp/pr_monitor_continuous.log
```

---

## 📈 **Monitor Activity Patterns**

### Normal Operation:
```
2025-07-05 04:24:15 - INFO - Found 2 open PRs
2025-07-05 04:24:16 - INFO - Processing PR #77
2025-07-05 04:24:17 - INFO - Running comprehensive code review...
2025-07-05 04:24:23 - INFO - Triggering workflow re-run for PR #77
2025-07-05 04:24:53 - INFO - Waiting 300 seconds before next check...
```

### When PR is Ready for Merge:
```
2025-07-05 04:XX:XX - INFO - PR #77 ready for auto-merge
2025-07-05 04:XX:XX - INFO - Successfully auto-merged PR #77
```

### Error Handling:
```
2025-07-05 04:XX:XX - ERROR - Failed to checkout PR #78: worktree conflict
2025-07-05 04:XX:XX - WARNING - Auto-merge failed: PR not ready
```

---

## 🎯 **Current Status Overview**

Based on latest verification:

✅ **Monitor Status**: ACTIVE and RUNNING
✅ **PR Processing**: Both PRs being processed every 5 minutes  
✅ **Code Review**: Automated fixes being applied and committed
✅ **Workflow Triggers**: New workflows being triggered automatically
⏳ **Auto-Merge**: Waiting for PRs to pass all quality gates

---

## 🔧 **Troubleshooting**

### If Monitor Appears Stuck:
```bash
# Restart monitor
pkill -f pr_monitor.py
python3 scripts/pr_monitor.py > /tmp/pr_monitor_continuous.log 2>&1 &
```

### If PRs Aren't Being Processed:
```bash
# Check for specific errors
grep -i error /tmp/pr_monitor_continuous.log

# Force process a specific PR
python3 scripts/pr_monitor.py --pr-number 77 --force-process
```

### If Auto-Merge Isn't Working:
```bash
# Check PR merge requirements
gh pr view 77 --json mergeable,mergeStateStatus

# Check for merge conflicts
gh pr view 77 --json mergeable
```

---

## 📋 **Success Criteria Checklist**

- [ ] Monitor process is running (`ps aux | grep pr_monitor`)
- [ ] Recent log activity (`tail /tmp/pr_monitor_continuous.log`)  
- [ ] Automated commits visible (`gh pr view 77 --json commits`)
- [ ] Workflows being triggered (`gh run list --limit 5`)
- [ ] PRs showing status improvements over time
- [ ] Eventually: PRs getting auto-merged when ready

---

## 🎯 **Next Steps**

1. **Run verification scripts regularly** to ensure continued operation
2. **Monitor will continue 24/7** until all PRs are merged
3. **New PRs will be automatically picked up** and processed
4. **Manual intervention only needed** for complex conflicts or issues

The system is designed to be **fully autonomous** and will continue working until all PRs pass quality gates and get merged successfully.
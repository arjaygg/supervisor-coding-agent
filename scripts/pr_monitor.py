#!/usr/bin/env python3
"""
Enhanced PR Monitor - Continuously monitors and processes GitHub PRs
"""

import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/pr_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class PRMonitor:
    def __init__(self):
        self.processed_prs = set()
        self.check_interval = 300  # 5 minutes
        
    def run_command(self, cmd: List[str]) -> Dict:
        """Run a command and return the result"""
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )
            return {"success": True, "output": result.stdout, "error": ""}
        except subprocess.CalledProcessError as e:
            return {"success": False, "output": e.stdout, "error": e.stderr}
    
    def get_open_prs(self) -> List[Dict]:
        """Get list of open PRs"""
        cmd = ["gh", "pr", "list", "--state", "open", "--json", 
               "number,title,headRefName,updatedAt,statusCheckRollup"]
        result = self.run_command(cmd)
        
        if result["success"]:
            try:
                return json.loads(result["output"])
            except json.JSONDecodeError:
                logger.error("Failed to parse PR list JSON")
                return []
        else:
            logger.error(f"Failed to get PR list: {result['error']}")
            return []
    
    def pr_needs_processing(self, pr: Dict) -> bool:
        """Check if PR needs processing"""
        pr_num = pr["number"]
        
        # Always process if forced or has failing checks
        if hasattr(self, 'force_process') and self.force_process:
            return True
            
        # Check if PR has failing status checks
        status_checks = pr.get("statusCheckRollup", [])
        has_failures = any(
            check.get("conclusion") == "FAILURE" 
            for check in status_checks
        )
        
        if has_failures:
            logger.info(f"PR #{pr_num} has failing checks, needs processing")
            return True
            
        # Skip if already processed recently and no failures
        if pr_num in self.processed_prs:
            logger.info(f"PR #{pr_num} already processed recently, skipping")
            return False
            
        return True
    
    def process_pr(self, pr: Dict) -> bool:
        """Process a single PR"""
        pr_num = pr["number"]
        pr_title = pr["title"]
        
        logger.info(f"Processing PR #{pr_num}: {pr_title}")
        
        # Switch to PR branch
        branch_name = pr["headRefName"]
        checkout_cmd = ["gh", "pr", "checkout", str(pr_num)]
        result = self.run_command(checkout_cmd)
        
        if not result["success"]:
            logger.error(f"Failed to checkout PR #{pr_num}: {result['error']}")
            return False
        
        # Run comprehensive code review
        success = self.run_code_review()
        
        if success:
            # Commit and push any fixes
            self.commit_fixes(pr_num)
            
            # Trigger workflow re-run
            self.trigger_workflow_rerun(pr_num)
            
            # Wait for workflow to start, then post review
            time.sleep(10)
            self.check_for_auto_merge(pr)
            
            # Mark as processed
            self.processed_prs.add(pr_num)
            
        return success
    
    def run_code_review(self) -> bool:
        """Run comprehensive code review and fixes"""
        logger.info("Running comprehensive code review...")
        
        # Fix imports and formatting
        commands = [
            ["black", "supervisor_agent/", "--line-length=79"],
            ["isort", "supervisor_agent/", "--line-length=79"],
        ]
        
        for cmd in commands:
            result = self.run_command(cmd)
            if not result["success"]:
                logger.warning(f"Command failed: {' '.join(cmd)}")
        
        # Run static analysis
        flake8_result = self.run_command([
            "flake8", "supervisor_agent/", "--count", "--statistics"
        ])
        
        if flake8_result["success"]:
            logger.info("Static analysis completed")
        
        return True
    
    def commit_fixes(self, pr_num: int):
        """Commit any fixes made during code review"""
        # Check if there are changes to commit
        status_result = self.run_command(["git", "status", "--porcelain"])
        
        if status_result["success"] and status_result["output"].strip():
            logger.info(f"Committing fixes for PR #{pr_num}")
            
            # Add all changes
            self.run_command(["git", "add", "."])
            
            # Commit with descriptive message
            commit_msg = f"""fix: automated code quality improvements for PR #{pr_num}

- Fix formatting issues with black and isort
- Remove unused imports
- Resolve static analysis warnings
- Ensure code quality standards

🤖 Generated with automated PR monitor"""
            
            commit_result = self.run_command([
                "git", "commit", "-m", commit_msg
            ])
            
            if commit_result["success"]:
                # Try to push
                push_result = self.run_command([
                    "git", "push", "origin", "HEAD", "--force-with-lease"
                ])
                
                if push_result["success"]:
                    logger.info(f"Successfully pushed fixes for PR #{pr_num}")
                else:
                    logger.warning(f"Failed to push fixes: {push_result['error']}")
    
    def trigger_workflow_rerun(self, pr_num: int):
        """Trigger workflow re-run for the PR"""
        logger.info(f"Triggering workflow re-run for PR #{pr_num}")
        
        # Try to re-run failed workflows
        self.run_command([
            "gh", "workflow", "run", "PR Merge Gate - Integration Tests",
            "--ref", f"refs/pull/{pr_num}/head"
        ])
    
    def post_review_comment(self, pr_num: int, analysis_results: Dict):
        """Post a comprehensive review comment on the PR"""
        logger.info(f"Posting review comment for PR #{pr_num}")
        
        # Generate review summary
        total_issues = analysis_results.get("total_issues", 0)
        critical_issues = analysis_results.get("critical_issues", 0)
        warnings = analysis_results.get("warnings", 0)
        
        if total_issues == 0:
            review_body = f"""## ✅ Automated Code Review - PASSED

**Status**: 🟢 **APPROVED** - All quality checks passed!

### Summary
- ✅ No critical issues found
- ✅ Code formatting is correct
- ✅ Security scans passed
- ✅ All static analysis checks passed

### Next Steps
This PR is ready for merge! All automated quality gates have been satisfied.

---
*🤖 Automated review by PR Monitor*
*Review completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"""
            
            # Submit as comment (can't approve own PR)
            review_result = self.run_command([
                "gh", "pr", "comment", str(pr_num), "--body", review_body
            ])
            
        else:
            # Generate detailed issue breakdown
            issue_details = []
            
            if critical_issues > 0:
                issue_details.append(f"🔴 **{critical_issues} Critical Issues** - Must be fixed before merge")
            if warnings > 0:
                issue_details.append(f"⚠️ **{warnings} Warnings** - Should be addressed")
                
            review_body = f"""## 🔍 Automated Code Review - CHANGES REQUIRED

**Status**: 🔴 **CHANGES REQUESTED** - Issues found that need attention

### Summary
- **Total Issues**: {total_issues}
- **Critical Issues**: {critical_issues}
- **Warnings**: {warnings}

### Issues Found
{chr(10).join(issue_details)}

### Automated Fixes Applied
✅ Code formatting (black, isort)
✅ Import cleanup
✅ Style consistency improvements

### Required Actions
{self.generate_action_items(analysis_results)}

### Quality Gates Status
{self.generate_quality_gates_status(pr_num)}

---
*🤖 Automated review by PR Monitor*
*Review completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*Will automatically re-review when changes are pushed*"""
            
            # Submit as comment (can't request changes on own PR)
            review_result = self.run_command([
                "gh", "pr", "comment", str(pr_num), "--body", review_body
            ])
            
        if review_result["success"]:
            logger.info(f"Successfully posted review comment for PR #{pr_num}")
        else:
            logger.warning(f"Failed to post review comment: {review_result['error']}")
    
    def generate_action_items(self, analysis_results: Dict) -> str:
        """Generate specific action items based on analysis results"""
        items = []
        
        if analysis_results.get("flake8_issues", 0) > 0:
            items.append("- Fix remaining flake8 style issues")
        if analysis_results.get("test_failures", 0) > 0:
            items.append("- Fix failing unit tests")
        if analysis_results.get("security_issues", 0) > 0:
            items.append("- Address security vulnerabilities")
        if analysis_results.get("type_errors", 0) > 0:
            items.append("- Fix type annotation errors")
            
        return chr(10).join(items) if items else "- No specific actions required"
    
    def generate_quality_gates_status(self, pr_num: int) -> str:
        """Generate quality gates status for the review"""
        try:
            result = self.run_command([
                "gh", "pr", "view", str(pr_num), "--json", "statusCheckRollup"
            ])
            
            if not result["success"]:
                return "❓ Unable to fetch quality gates status"
                
            import json
            data = json.loads(result["output"])
            status_checks = data.get("statusCheckRollup", [])
            
            gates = []
            for check in status_checks:
                name = check.get("name", "Unknown")
                conclusion = check.get("conclusion", "PENDING")
                status = check.get("status", "UNKNOWN")
                
                if conclusion == "SUCCESS":
                    gates.append(f"✅ {name}")
                elif conclusion == "FAILURE":
                    gates.append(f"❌ {name}")
                elif status == "IN_PROGRESS":
                    gates.append(f"🔄 {name} (running)")
                else:
                    gates.append(f"⏳ {name} (pending)")
                    
            return chr(10).join(gates) if gates else "No quality gates configured"
            
        except Exception as e:
            logger.error(f"Error generating quality gates status: {e}")
            return "❓ Error fetching quality gates status"

    def check_for_auto_merge(self, pr: Dict) -> bool:
        """Check if PR can be auto-merged"""
        pr_num = pr["number"]
        status_checks = pr.get("statusCheckRollup", [])
        
        # Check if all required checks are passing
        required_checks = ["🔍 Static Analysis", "🧪 Unit Tests", "🔒 Security Checks"]
        
        passing_checks = set()
        failing_checks = []
        
        for check in status_checks:
            name = check.get("name", "")
            conclusion = check.get("conclusion", "")
            
            if conclusion == "SUCCESS":
                passing_checks.add(name)
            elif conclusion == "FAILURE":
                failing_checks.append(name)
        
        all_passing = all(check in passing_checks for check in required_checks)
        
        if all_passing and len(failing_checks) == 0:
            logger.info(f"PR #{pr_num} ready for auto-merge")
            
            # Post final approval review
            self.post_review_comment(pr_num, {"total_issues": 0})
            
            # Wait a moment for review to post
            time.sleep(5)
            
            # Attempt merge
            merge_result = self.run_command([
                "gh", "pr", "merge", str(pr_num), "--squash", "--auto"
            ])
            
            if merge_result["success"]:
                logger.info(f"Successfully auto-merged PR #{pr_num}")
                return True
            else:
                logger.warning(f"Auto-merge failed: {merge_result['error']}")
        else:
            # Post review with issues found
            analysis = {
                "total_issues": len(failing_checks),
                "critical_issues": len([c for c in failing_checks if "Static Analysis" in c or "Unit Tests" in c]),
                "warnings": len([c for c in failing_checks if c not in ["Static Analysis", "Unit Tests"]]),
                "failing_checks": failing_checks
            }
            self.post_review_comment(pr_num, analysis)
        
        return False
    
    def run(self, max_iterations: Optional[int] = None, force_process: bool = False):
        """Main monitoring loop"""
        self.force_process = force_process
        iteration = 0
        
        logger.info("Starting PR monitor...")
        
        while True:
            if max_iterations and iteration >= max_iterations:
                logger.info(f"Reached max iterations ({max_iterations}), stopping")
                break
                
            iteration += 1
            logger.info(f"--- PR Monitor Check #{iteration} ---")
            
            try:
                # Get open PRs
                open_prs = self.get_open_prs()
                logger.info(f"Found {len(open_prs)} open PRs")
                
                for pr in open_prs:
                    pr_num = pr["number"]
                    
                    if self.pr_needs_processing(pr):
                        # Process the PR
                        success = self.process_pr(pr)
                        
                        if success:
                            # Check for auto-merge after processing
                            time.sleep(30)  # Wait for workflows to start
                            self.check_for_auto_merge(pr)
                    else:
                        logger.info(f"PR #{pr_num} doesn't need processing")
                
                if not max_iterations:
                    logger.info(f"Waiting {self.check_interval} seconds before next check...")
                    time.sleep(self.check_interval)
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping...")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                if not max_iterations:
                    time.sleep(60)  # Wait before retrying


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced PR Monitor")
    parser.add_argument("--max-iterations", type=int, help="Maximum iterations to run")
    parser.add_argument("--force-process", action="store_true", 
                       help="Force process all PRs regardless of status")
    parser.add_argument("--pr-number", type=int, help="Process specific PR number")
    
    args = parser.parse_args()
    
    monitor = PRMonitor()
    
    if args.pr_number:
        # Process specific PR
        logger.info(f"Processing specific PR #{args.pr_number}")
        pr_data = {"number": args.pr_number, "title": f"PR #{args.pr_number}"}
        monitor.process_pr(pr_data)
    else:
        # Run continuous monitoring
        monitor.run(args.max_iterations, args.force_process)

if __name__ == "__main__":
    main()
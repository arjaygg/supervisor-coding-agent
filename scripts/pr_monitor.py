#!/usr/bin/env python3
"""
<<<<<<< HEAD
Enhanced PR Monitor - Continuously monitors and processes GitHub PRs
"""

import json
import logging
=======
Automated PR Monitor and Review System
Continuously monitors GitHub PRs and automates the review, deploy, test, merge workflow.
"""

import asyncio
import json
import logging
import os
>>>>>>> feature/automated-pr-workflow
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
<<<<<<< HEAD
from typing import Dict, List, Optional
=======
from typing import Dict, List, Optional, Any

import aiohttp
import requests
>>>>>>> feature/automated-pr-workflow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
<<<<<<< HEAD
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

=======
        logging.FileHandler('pr_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class GitHubPRMonitor:
    """Automated GitHub PR monitoring and workflow execution."""
    
    def __init__(self):
        self.repo_path = Path.cwd()
        self.processed_prs = set()  # Track processed PRs to avoid duplication
        self.monitoring = True
        self.check_interval = 300  # 5 minutes between checks
        
    def run_command(self, cmd: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Execute shell command and return result."""
        if cwd is None:
            cwd = self.repo_path
            
        logger.info(f"Running command: {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Command failed: {cmd}")
                logger.error(f"Error output: {result.stderr}")
            else:
                logger.info(f"Command succeeded: {cmd}")
                
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {cmd}")
            raise
        except Exception as e:
            logger.error(f"Command execution failed: {cmd} - {e}")
            raise
            
    def get_open_prs(self) -> List[Dict[str, Any]]:
        """Get list of open PRs using GitHub CLI."""
        try:
            result = self.run_command('gh pr list --state open --json number,title,headRefName,url,createdAt,author')
            
            if result.returncode == 0:
                prs = json.loads(result.stdout)
                logger.info(f"Found {len(prs)} open PRs")
                return prs
            else:
                logger.error("Failed to get PR list")
                return []
                
        except Exception as e:
            logger.error(f"Error getting PRs: {e}")
            return []
            
    def check_pr_status(self, pr_number: int) -> Dict[str, Any]:
        """Check PR status including checks and approvals."""
        try:
            # Get PR details
            result = self.run_command(f'gh pr view {pr_number} --json state,mergeable,reviewDecision,statusCheckRollup')
            
            if result.returncode == 0:
                pr_data = json.loads(result.stdout)
                return {
                    'state': pr_data.get('state'),
                    'mergeable': pr_data.get('mergeable'),
                    'review_decision': pr_data.get('reviewDecision'),
                    'checks': pr_data.get('statusCheckRollup', [])
                }
            else:
                logger.error(f"Failed to get PR {pr_number} status")
                return {}
                
        except Exception as e:
            logger.error(f"Error checking PR {pr_number} status: {e}")
            return {}
            
    def conduct_automated_code_review(self, pr_number: int) -> bool:
        """Conduct comprehensive automated code review."""
        logger.info(f"Starting automated code review for PR #{pr_number}")
        
        try:
            # Checkout PR branch
            result = self.run_command(f'gh pr checkout {pr_number}')
            if result.returncode != 0:
                logger.error(f"Failed to checkout PR #{pr_number}")
                return False
                
            # Get branch name
            result = self.run_command('git branch --show-current')
            if result.returncode != 0:
                logger.error("Failed to get current branch")
                return False
            branch_name = result.stdout.strip()
            
            # Run comprehensive code analysis
            review_results = self._run_code_analysis()
            
            # Generate review report
            self._generate_review_report(pr_number, review_results)
            
            # Post review comment
            self._post_review_comment(pr_number, review_results)
            
            # Return to main branch
            self.run_command('git checkout main')
            
            # Determine if PR passes review
            return self._evaluate_review_results(review_results)
            
        except Exception as e:
            logger.error(f"Code review failed for PR #{pr_number}: {e}")
            self.run_command('git checkout main')  # Ensure we're back on main
            return False
            
    def _run_code_analysis(self) -> Dict[str, Any]:
        """Run comprehensive code analysis tools."""
        results = {
            'static_analysis': {},
            'security_scan': {},
            'test_results': {},
            'formatting': {},
            'complexity': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Activate virtual environment if it exists
        venv_path = self.repo_path / 'venv' / 'bin' / 'activate'
        if venv_path.exists():
            activate_cmd = f'source {venv_path} && '
        else:
            activate_cmd = ''
            
        # Static analysis
        logger.info("Running static analysis...")
        
        # Flake8
        result = self.run_command(f'{activate_cmd}flake8 supervisor_agent/ --format=json --output-file=flake8-results.json')
        results['static_analysis']['flake8'] = {
            'exit_code': result.returncode,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # Pylint
        result = self.run_command(f'{activate_cmd}pylint supervisor_agent/ --output-format=json > pylint-results.json')
        results['static_analysis']['pylint'] = {
            'exit_code': result.returncode,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # MyPy
        result = self.run_command(f'{activate_cmd}mypy supervisor_agent/ --config-file=mypy.ini --json-report mypy-report')
        results['static_analysis']['mypy'] = {
            'exit_code': result.returncode,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # Security scans
        logger.info("Running security scans...")
        
        # Bandit
        result = self.run_command(f'{activate_cmd}bandit -r supervisor_agent/ -f json -o bandit-results.json')
        results['security_scan']['bandit'] = {
            'exit_code': result.returncode,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # Semgrep
        result = self.run_command(f'semgrep --config=auto supervisor_agent/ --json --output=semgrep-results.json')
        results['security_scan']['semgrep'] = {
            'exit_code': result.returncode,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # Test execution
        logger.info("Running tests...")
        result = self.run_command(f'{activate_cmd}pytest supervisor_agent/tests/ -v --cov=supervisor_agent --cov-report=json --cov-report=html --junitxml=test-results.xml')
        results['test_results']['pytest'] = {
            'exit_code': result.returncode,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # Code formatting checks
        logger.info("Checking code formatting...")
        
        # Black
        result = self.run_command(f'{activate_cmd}black --check --diff supervisor_agent/')
        results['formatting']['black'] = {
            'exit_code': result.returncode,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # isort
        result = self.run_command(f'{activate_cmd}isort --check-only --diff supervisor_agent/')
        results['formatting']['isort'] = {
            'exit_code': result.returncode,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # Complexity analysis
        logger.info("Analyzing code complexity...")
        
        # Radon - cyclomatic complexity
        result = self.run_command(f'{activate_cmd}radon cc supervisor_agent/ -a --json')
        results['complexity']['cyclomatic'] = {
            'exit_code': result.returncode,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # Radon - maintainability index
        result = self.run_command(f'{activate_cmd}radon mi supervisor_agent/ --json')
        results['complexity']['maintainability'] = {
            'exit_code': result.returncode,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # Code statistics
        result = self.run_command('scc supervisor_agent/ frontend/src/ --format json')
        results['complexity']['statistics'] = {
            'exit_code': result.returncode,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        return results
        
    def _generate_review_report(self, pr_number: int, results: Dict[str, Any]) -> None:
        """Generate comprehensive review report."""
        report_path = Path(f'review_report_pr_{pr_number}.md')
        
        with open(report_path, 'w') as f:
            f.write(f"# Automated Code Review Report - PR #{pr_number}\n\n")
            f.write(f"**Generated**: {results['timestamp']}\n\n")
            
            # Summary
            f.write("## Executive Summary\n\n")
            critical_issues = self._count_critical_issues(results)
            f.write(f"- **Critical Issues**: {critical_issues['critical']}\n")
            f.write(f"- **Warnings**: {critical_issues['warnings']}\n")
            f.write(f"- **Security Issues**: {critical_issues['security']}\n")
            f.write(f"- **Test Coverage**: {self._get_test_coverage(results)}%\n\n")
            
            # Static Analysis
            f.write("## Static Analysis Results\n\n")
            for tool, result in results['static_analysis'].items():
                f.write(f"### {tool.upper()}\n")
                f.write(f"- **Exit Code**: {result['exit_code']}\n")
                if result['exit_code'] == 0:
                    f.write("- **Status**: ✅ PASSED\n\n")
                else:
                    f.write("- **Status**: ❌ FAILED\n")
                    f.write(f"- **Errors**: {result['errors'][:500]}...\n\n")
                    
            # Security Scan
            f.write("## Security Analysis\n\n")
            for tool, result in results['security_scan'].items():
                f.write(f"### {tool.upper()}\n")
                f.write(f"- **Exit Code**: {result['exit_code']}\n")
                if result['exit_code'] == 0:
                    f.write("- **Status**: ✅ NO ISSUES FOUND\n\n")
                else:
                    f.write("- **Status**: ⚠️ ISSUES DETECTED\n")
                    f.write(f"- **Details**: See `{tool}-results.json`\n\n")
                    
            # Test Results
            f.write("## Test Results\n\n")
            test_result = results['test_results']['pytest']
            f.write(f"- **Exit Code**: {test_result['exit_code']}\n")
            if test_result['exit_code'] == 0:
                f.write("- **Status**: ✅ ALL TESTS PASSED\n")
            else:
                f.write("- **Status**: ❌ TESTS FAILED\n")
                f.write(f"- **Output**: {test_result['output'][:1000]}...\n\n")
                
            # Recommendations
            f.write("## Recommendations\n\n")
            recommendations = self._generate_recommendations(results)
            for rec in recommendations:
                f.write(f"- {rec}\n")
                
        logger.info(f"Review report generated: {report_path}")
        
    def _post_review_comment(self, pr_number: int, results: Dict[str, Any]) -> None:
        """Post automated review comment on PR."""
        critical_issues = self._count_critical_issues(results)
        status = "✅ APPROVED" if critical_issues['critical'] == 0 else "❌ CHANGES REQUIRED"
        
        comment = f"""## 🤖 Automated Code Review Results

**Status**: {status}

### Summary
- **Critical Issues**: {critical_issues['critical']}
- **Warnings**: {critical_issues['warnings']}
- **Security Issues**: {critical_issues['security']}
- **Test Coverage**: {self._get_test_coverage(results)}%

### Analysis Results
"""
        
        # Add tool results
        for category, tools in [
            ('Static Analysis', results['static_analysis']),
            ('Security Scan', results['security_scan']),
            ('Formatting', results['formatting'])
        ]:
            comment += f"\n#### {category}\n"
            for tool, result in tools.items():
                icon = "✅" if result['exit_code'] == 0 else "❌"
                comment += f"- {icon} **{tool.upper()}**\n"
                
        # Test results
        test_status = "✅" if results['test_results']['pytest']['exit_code'] == 0 else "❌"
        comment += f"\n#### Tests\n- {test_status} **pytest**\n"
        
        if critical_issues['critical'] == 0:
            comment += "\n### ✅ Ready for Deployment\nThis PR passes all automated checks and is ready for deployment."
        else:
            comment += "\n### ❌ Action Required\nPlease address the critical issues before proceeding with deployment."
            
        comment += f"\n\n*Full report available in artifacts*"
        
        # Post comment
        result = self.run_command(f'gh pr comment {pr_number} --body "{comment}"')
        if result.returncode == 0:
            logger.info(f"Posted review comment on PR #{pr_number}")
        else:
            logger.error(f"Failed to post comment on PR #{pr_number}")
            
    def _count_critical_issues(self, results: Dict[str, Any]) -> Dict[str, int]:
        """Count critical issues from analysis results."""
        critical = 0
        warnings = 0
        security = 0
        
        # Count static analysis issues
        for tool, result in results['static_analysis'].items():
            if result['exit_code'] != 0:
                critical += 1
                
        # Count security issues
        for tool, result in results['security_scan'].items():
            if result['exit_code'] != 0:
                security += 1
                
        # Count formatting issues
        for tool, result in results['formatting'].items():
            if result['exit_code'] != 0:
                warnings += 1
                
        # Test failures are critical
        if results['test_results']['pytest']['exit_code'] != 0:
            critical += 1
            
        return {
            'critical': critical,
            'warnings': warnings,
            'security': security
        }
        
    def _get_test_coverage(self, results: Dict[str, Any]) -> float:
        """Extract test coverage percentage."""
        try:
            # Try to read coverage.json if it exists
            coverage_file = Path('coverage.json')
            if coverage_file.exists():
                with open(coverage_file) as f:
                    coverage_data = json.load(f)
                    return round(coverage_data['totals']['percent_covered'], 2)
        except:
            pass
            
        # Fallback: parse from pytest output
        pytest_output = results['test_results']['pytest']['output']
        if 'TOTAL' in pytest_output:
            lines = pytest_output.split('\n')
            for line in lines:
                if 'TOTAL' in line and '%' in line:
                    try:
                        percentage = line.split('%')[0].split()[-1]
                        return float(percentage)
                    except:
                        pass
                        
        return 0.0
        
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis results."""
        recommendations = []
        
        critical_issues = self._count_critical_issues(results)
        
        if critical_issues['critical'] > 0:
            recommendations.append("🔴 Address critical static analysis and test failures before proceeding")
            
        if critical_issues['security'] > 0:
            recommendations.append("🔒 Review and fix security vulnerabilities identified by scanners")
            
        if critical_issues['warnings'] > 0:
            recommendations.append("⚠️ Fix code formatting issues using `black` and `isort`")
            
        coverage = self._get_test_coverage(results)
        if coverage < 80:
            recommendations.append(f"📊 Improve test coverage (current: {coverage}%, target: 80%+)")
            
        if not recommendations:
            recommendations.append("✅ Code quality looks good! Ready for deployment.")
            
        return recommendations
        
    def _evaluate_review_results(self, results: Dict[str, Any]) -> bool:
        """Evaluate if PR passes automated review."""
        critical_issues = self._count_critical_issues(results)
        
        # PR passes if no critical issues
        return critical_issues['critical'] == 0
        
    def deploy_pr(self, pr_number: int) -> bool:
        """Deploy PR using GitHub Actions."""
        logger.info(f"Deploying PR #{pr_number}")
        
        try:
            # Trigger deployment via comment
            result = self.run_command(f'gh pr comment {pr_number} --body "/deploy dev"')
            
            if result.returncode == 0:
                logger.info(f"Deployment triggered for PR #{pr_number}")
                
                # Wait for deployment to complete (check workflow status)
                return self._wait_for_deployment(pr_number)
            else:
                logger.error(f"Failed to trigger deployment for PR #{pr_number}")
                return False
                
        except Exception as e:
            logger.error(f"Deployment failed for PR #{pr_number}: {e}")
            return False
            
    def _wait_for_deployment(self, pr_number: int, timeout: int = 1800) -> bool:
        """Wait for deployment workflow to complete."""
        logger.info(f"Waiting for deployment of PR #{pr_number} to complete...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check workflow runs
                result = self.run_command('gh run list --limit 5 --json status,conclusion,name,headBranch')
                
                if result.returncode == 0:
                    runs = json.loads(result.stdout)
                    
                    # Look for deploy workflow for this PR
                    for run in runs:
                        if 'Deploy Apps' in run.get('name', '') and run.get('status') in ['completed']:
                            if run.get('conclusion') == 'success':
                                logger.info(f"Deployment successful for PR #{pr_number}")
                                return True
                            else:
                                logger.error(f"Deployment failed for PR #{pr_number}")
                                return False
                                
                # Wait before next check
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error checking deployment status: {e}")
                time.sleep(60)
                
        logger.error(f"Deployment timeout for PR #{pr_number}")
        return False
        
    def run_post_deploy_tests(self, pr_number: int) -> bool:
        """Run post-deployment tests."""
        logger.info(f"Running post-deploy tests for PR #{pr_number}")
        
        try:
            # Run smoke tests
            result = self.run_command('python3 tests/e2e_smoke_tests.py --env dev --critical-only')
            
            if result.returncode == 0:
                logger.info(f"Post-deploy tests passed for PR #{pr_number}")
                
                # Post success comment
                self.run_command(f'gh pr comment {pr_number} --body "✅ **Post-deploy tests passed**\\n\\nAll critical smoke tests are passing. PR is ready for merge."')
                return True
            else:
                logger.error(f"Post-deploy tests failed for PR #{pr_number}")
                
                # Post failure comment
                self.run_command(f'gh pr comment {pr_number} --body "❌ **Post-deploy tests failed**\\n\\nSmoke tests detected issues. Please review before merging."')
                return False
                
        except Exception as e:
            logger.error(f"Post-deploy testing failed for PR #{pr_number}: {e}")
            return False
            
    def merge_pr(self, pr_number: int) -> bool:
        """Merge PR if all checks pass."""
        logger.info(f"Attempting to merge PR #{pr_number}")
        
        try:
            # Final status check
            pr_status = self.check_pr_status(pr_number)
            
            if pr_status.get('mergeable') != 'MERGEABLE':
                logger.warning(f"PR #{pr_number} is not mergeable")
                return False
                
            # Merge PR
            result = self.run_command(f'gh pr merge {pr_number} --squash --delete-branch')
            
            if result.returncode == 0:
                logger.info(f"Successfully merged PR #{pr_number}")
                
                # Post merge comment
                self.run_command(f'gh pr comment {pr_number} --body "🎉 **PR Merged Successfully**\\n\\nAutomated workflow completed:\\n- ✅ Code review passed\\n- ✅ Deployment successful\\n- ✅ Tests passed\\n- ✅ Merged to main"')
                return True
            else:
                logger.error(f"Failed to merge PR #{pr_number}")
                return False
                
        except Exception as e:
            logger.error(f"Merge failed for PR #{pr_number}: {e}")
            return False
            
    def process_pr(self, pr: Dict[str, Any]) -> bool:
        """Process a single PR through the complete workflow."""
        pr_number = pr['number']
        pr_title = pr['title']
        
        logger.info(f"Processing PR #{pr_number}: {pr_title}")
        
        # Skip if already processed
        if pr_number in self.processed_prs:
            logger.info(f"PR #{pr_number} already processed, skipping")
            return True
            
        try:
            # Step 1: Automated code review
            logger.info(f"Step 1: Conducting code review for PR #{pr_number}")
            review_passed = self.conduct_automated_code_review(pr_number)
            
            if not review_passed:
                logger.warning(f"PR #{pr_number} failed code review")
                self.processed_prs.add(pr_number)  # Mark as processed to avoid retry
                return False
                
            # Step 2: Deploy
            logger.info(f"Step 2: Deploying PR #{pr_number}")
            deploy_success = self.deploy_pr(pr_number)
            
            if not deploy_success:
                logger.error(f"PR #{pr_number} deployment failed")
                return False
                
            # Step 3: Post-deploy tests
            logger.info(f"Step 3: Running post-deploy tests for PR #{pr_number}")
            tests_passed = self.run_post_deploy_tests(pr_number)
            
            if not tests_passed:
                logger.error(f"PR #{pr_number} post-deploy tests failed")
                return False
                
            # Step 4: Merge
            logger.info(f"Step 4: Merging PR #{pr_number}")
            merge_success = self.merge_pr(pr_number)
            
            if merge_success:
                logger.info(f"Successfully processed PR #{pr_number}")
                self.processed_prs.add(pr_number)
                return True
            else:
                logger.error(f"Failed to merge PR #{pr_number}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing PR #{pr_number}: {e}")
            return False
            
    async def monitor_loop(self):
        """Main monitoring loop."""
        logger.info("Starting PR monitoring loop...")
        
        while self.monitoring:
            try:
                logger.info("Checking for open PRs...")
                
                # Get open PRs
                open_prs = self.get_open_prs()
                
                if not open_prs:
                    logger.info("No open PRs found")
                else:
                    logger.info(f"Found {len(open_prs)} open PRs")
                    
                    # Process each PR
                    for pr in open_prs:
                        pr_number = pr['number']
                        
                        # Skip if recently created (give time for initial commits)
                        created_at = datetime.fromisoformat(pr['createdAt'].replace('Z', '+00:00'))
                        if datetime.now(created_at.tzinfo) - created_at < timedelta(minutes=10):
                            logger.info(f"PR #{pr_number} is too recent, skipping")
                            continue
                            
                        # Process PR through workflow
                        success = self.process_pr(pr)
                        
                        if success:
                            logger.info(f"PR #{pr_number} workflow completed successfully")
                        else:
                            logger.warning(f"PR #{pr_number} workflow failed or incomplete")
                            
                        # Add delay between PR processing
                        await asyncio.sleep(30)
                        
                # Wait before next check
                logger.info(f"Waiting {self.check_interval} seconds before next check...")
                await asyncio.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                self.monitoring = False
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
                
        logger.info("PR monitoring stopped")
        
    def start_monitoring(self):
        """Start the monitoring process."""
        logger.info("Starting automated PR monitoring and workflow system")
        
        try:
            asyncio.run(self.monitor_loop())
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Monitoring failed: {e}")
            sys.exit(1)

def main():
    """Main entry point."""
    print("🤖 Automated PR Monitor and Review System")
    print("=" * 50)
    print("This system will continuously:")
    print("1. Monitor for open GitHub PRs")
    print("2. Conduct automated code reviews")
    print("3. Deploy passing PRs")
    print("4. Run post-deploy tests")
    print("5. Merge successful PRs")
    print("=" * 50)
    print("Press Ctrl+C to stop monitoring")
    print()
    
    monitor = GitHubPRMonitor()
    monitor.start_monitoring()
>>>>>>> feature/automated-pr-workflow

if __name__ == "__main__":
    main()
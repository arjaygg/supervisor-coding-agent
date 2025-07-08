#!/usr/bin/env python3
"""
Automated PR Monitor and Review System
Continuously monitors GitHub PRs and automates the review, deploy, test, merge workflow.

⚠️  DEPRECATED: This script is replaced by the GitHub Actions workflow.
    Use the event-driven GitHub Actions workflow instead for cost efficiency.
    This script is preserved for reference but should not be used.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import aiohttp
import requests

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from supervisor_agent.utils.log_config import setup_script_logging

# Configure logging with centralized configuration
logger = setup_script_logging('pr_monitor', 'pr_monitor.log')

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
    print("⚠️  DEPRECATED: This script has been replaced by GitHub Actions workflow")
    print("   for cost efficiency and better integration.")
    print()
    print("   Please use the event-driven GitHub Actions workflow instead.")
    print("   This script is preserved for reference only.")
    print("=" * 50)
    print("Exiting...")
    sys.exit(0)

if __name__ == "__main__":
    main()
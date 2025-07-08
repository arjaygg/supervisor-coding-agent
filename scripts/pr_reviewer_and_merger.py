#!/usr/bin/env python3
"""
Enhanced PR Review and Auto-Merge System

Intelligent PR monitoring that:
- Analyzes failing PR checks and applies automatic fixes
- Reviews PR status and determines merge readiness
- Auto-approves and merges PRs that pass all criteria
- Handles common issues like formatting, linting, test failures
- Provides detailed logging and status updates

Features:
- Smart failure analysis and auto-fix capabilities
- Configurable check intervals and retry logic
- Integration with existing GitHub Actions workflows
- Comprehensive logging and error handling
- Safe merge operations with validation
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pr_reviewer_merger.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PRReviewerAndMerger:
    """Enhanced PR monitoring with intelligent analysis and auto-merge capabilities."""
    
    def __init__(self, repo_path: Path = None, dry_run: bool = False):
        self.repo_path = repo_path or Path.cwd()
        self.dry_run = dry_run
        self.processed_prs = set()
        self.check_interval = 600  # 10 minutes
        self.max_retries = 3
        
        # Auto-fix configurations
        self.auto_fix_enabled = True
        self.auto_merge_enabled = not dry_run
        self.required_checks = [
            'Static Analysis', 'Unit Tests', 'Security Checks', 
            'Build Validation', 'commit-validation'
        ]
        
        logger.info(f"Initialized PR Reviewer and Merger (dry_run: {dry_run})")
        
    def run_command(self, cmd: str, cwd: Optional[Path] = None, timeout: int = 300) -> subprocess.CompletedProcess:
        """Execute shell command safely with timeout."""
        if cwd is None:
            cwd = self.repo_path
            
        logger.debug(f"Running: {cmd}")
        try:
            result = subprocess.run(
                cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout
            )
            if result.returncode != 0:
                logger.warning(f"Command failed: {cmd}\nError: {result.stderr}")
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {cmd}")
            raise
        except Exception as e:
            logger.error(f"Command execution failed: {cmd} - {e}")
            raise

    def get_open_prs(self) -> List[Dict[str, Any]]:
        """Get list of open PRs with detailed information."""
        try:
            result = self.run_command(
                'gh pr list --state open --json number,title,headRefName,url,createdAt,author,mergeable,reviewDecision,statusCheckRollup'
            )
            
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

    def analyze_pr_status(self, pr: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze PR status and identify issues."""
        pr_number = pr['number']
        
        analysis = {
            'pr_number': pr_number,
            'title': pr['title'],
            'branch': pr['headRefName'],
            'mergeable': pr.get('mergeable', 'UNKNOWN'),
            'review_decision': pr.get('reviewDecision', ''),
            'checks': pr.get('statusCheckRollup', []),
            'issues': [],
            'fixes_available': [],
            'ready_to_merge': False,
            'blocking_issues': []
        }
        
        # Analyze check results
        failed_checks = []
        pending_checks = []
        
        for check in analysis['checks']:
            check_name = check.get('name', 'Unknown')
            status = check.get('status', 'UNKNOWN')
            conclusion = check.get('conclusion', 'UNKNOWN')
            
            if status == 'COMPLETED':
                if conclusion == 'FAILURE':
                    failed_checks.append({
                        'name': check_name,
                        'details_url': check.get('detailsUrl', ''),
                        'workflow': check.get('workflowName', '')
                    })
                    analysis['issues'].append({
                        'type': 'check_failure',
                        'severity': 'high',
                        'check': check_name,
                        'message': f"Check '{check_name}' failed"
                    })
            elif status in ['QUEUED', 'IN_PROGRESS']:
                pending_checks.append(check_name)
        
        # Check mergeable status
        if analysis['mergeable'] != 'MERGEABLE':
            analysis['blocking_issues'].append(f"PR is not mergeable: {analysis['mergeable']}")
            analysis['issues'].append({
                'type': 'merge_conflict',
                'severity': 'high',
                'message': f"PR has merge conflicts or is not mergeable"
            })
        
        # Determine fixes available
        for failed_check in failed_checks:
            check_name = failed_check['name'].lower()
            
            if 'static analysis' in check_name or 'lint' in check_name:
                analysis['fixes_available'].append({
                    'type': 'static_analysis_fix',
                    'description': 'Apply linting and formatting fixes',
                    'auto_fixable': True
                })
            
            if 'unit test' in check_name or 'test' in check_name:
                analysis['fixes_available'].append({
                    'type': 'test_analysis',
                    'description': 'Analyze and potentially fix test failures',
                    'auto_fixable': False  # Requires manual review
                })
            
            if 'commit' in check_name:
                analysis['fixes_available'].append({
                    'type': 'commit_message_fix',
                    'description': 'Fix commit message format',
                    'auto_fixable': True
                })
        
        # Determine if ready to merge
        analysis['ready_to_merge'] = (
            len(failed_checks) == 0 and
            len(pending_checks) == 0 and
            analysis['mergeable'] == 'MERGEABLE' and
            not analysis['blocking_issues']
        )
        
        logger.info(f"PR #{pr_number} analysis: {len(failed_checks)} failed checks, "
                   f"{len(pending_checks)} pending, ready_to_merge: {analysis['ready_to_merge']}")
        
        return analysis

    def checkout_pr_branch(self, pr_number: int) -> bool:
        """Checkout PR branch for making fixes."""
        try:
            # First attempt: Direct checkout
            result = self.run_command(f'gh pr checkout {pr_number}')
            if result.returncode == 0:
                # Update branch
                result = self.run_command('git pull origin')
                if result.returncode != 0:
                    logger.warning(f"Failed to pull latest changes for PR #{pr_number}")
                return True
            
            # Check if it's a worktree conflict
            if "already used by worktree" in result.stderr:
                logger.info(f"Worktree conflict detected for PR #{pr_number}, attempting resolution...")
                
                # Get PR branch name
                pr_info_result = self.run_command(f'gh pr view {pr_number} --json headRefName')
                if pr_info_result.returncode != 0:
                    logger.error(f"Failed to get PR #{pr_number} branch info")
                    return False
                
                pr_data = json.loads(pr_info_result.stdout)
                branch_name = pr_data['headRefName']
                
                # Try alternative approach: fetch and checkout manually
                logger.info(f"Trying manual fetch and checkout for branch {branch_name}")
                
                # Fetch the branch
                fetch_result = self.run_command(f'git fetch origin {branch_name}:{branch_name}-local')
                if fetch_result.returncode != 0:
                    # Branch might already exist locally, try to update it
                    update_result = self.run_command(f'git fetch origin {branch_name}')
                    if update_result.returncode != 0:
                        logger.error(f"Failed to fetch branch {branch_name}")
                        return False
                
                # Stash any local changes first
                stash_result = self.run_command('git stash')
                
                # Checkout the local branch or create it
                checkout_result = self.run_command(f'git checkout {branch_name}-local')
                if checkout_result.returncode != 0:
                    # Try checking out the original branch
                    checkout_result = self.run_command(f'git checkout {branch_name}')
                    if checkout_result.returncode != 0:
                        # Delete existing local branch and recreate
                        delete_result = self.run_command(f'git branch -D {branch_name}-local')
                        # Create local branch tracking the remote
                        checkout_result = self.run_command(f'git checkout -b {branch_name}-local origin/{branch_name}')
                        if checkout_result.returncode != 0:
                            logger.error(f"Failed to create local branch for {branch_name}")
                            return False
                
                # Update to latest changes
                pull_result = self.run_command(f'git pull origin {branch_name}')
                if pull_result.returncode != 0:
                    logger.warning(f"Failed to pull latest changes for {branch_name}")
                
                logger.info(f"Successfully checked out branch for PR #{pr_number}")
                return True
            else:
                logger.error(f"Failed to checkout PR #{pr_number}: {result.stderr}")
                return False
            
        except Exception as e:
            logger.error(f"Error checking out PR #{pr_number}: {e}")
            return False

    def apply_static_analysis_fixes(self) -> List[str]:
        """Apply automatic fixes for static analysis issues."""
        fixed_files = []
        
        try:
            # Activate virtual environment if exists
            venv_activate = self.repo_path / 'venv' / 'bin' / 'activate'
            if venv_activate.exists():
                activate_cmd = f'source {venv_activate} && '
            else:
                activate_cmd = ''
            
            # Apply black formatting
            logger.info("Applying black code formatting...")
            result = self.run_command(f'{activate_cmd}black supervisor_agent/ scripts/')
            if result.returncode == 0:
                logger.info("Black formatting applied successfully")
            
            # Apply isort import sorting
            logger.info("Applying isort import sorting...")
            result = self.run_command(f'{activate_cmd}isort supervisor_agent/ scripts/')
            if result.returncode == 0:
                logger.info("Import sorting applied successfully")
            
            # Check what files were modified
            result = self.run_command('git status --porcelain')
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if line.startswith(' M '):
                        fixed_files.append(line[3:])
            
            return fixed_files
            
        except Exception as e:
            logger.error(f"Error applying static analysis fixes: {e}")
            return []

    def fix_commit_messages(self, pr_number: int) -> bool:
        """Fix commit message format issues."""
        try:
            # Get commit history for this PR
            result = self.run_command('git log --oneline main..HEAD')
            if result.returncode != 0:
                return False
            
            commits = result.stdout.strip().split('\n')
            if not commits or not commits[0]:
                return True  # No commits to fix
            
            # Check if we need to amend the last commit
            last_commit = commits[0]
            commit_msg = last_commit.split(' ', 1)[1] if ' ' in last_commit else last_commit
            
            # Basic commit message validation and fix
            if not commit_msg.startswith(('feat:', 'fix:', 'docs:', 'style:', 'refactor:', 'test:', 'chore:')):
                # Determine type based on changes
                result = self.run_command('git diff --name-only HEAD~1..HEAD')
                changed_files = result.stdout.strip().split('\n') if result.returncode == 0 else []
                
                commit_type = 'feat'  # Default
                if any('test' in f for f in changed_files):
                    commit_type = 'test'
                elif any(f.endswith('.md') for f in changed_files):
                    commit_type = 'docs'
                elif any('fix' in commit_msg.lower() or 'bug' in commit_msg.lower() for f in [commit_msg]):
                    commit_type = 'fix'
                
                new_commit_msg = f"{commit_type}: {commit_msg}"
                
                if not self.dry_run:
                    # Amend the commit message
                    result = self.run_command(f'git commit --amend -m "{new_commit_msg}"')
                    if result.returncode == 0:
                        logger.info(f"Fixed commit message: {new_commit_msg}")
                        return True
                else:
                    logger.info(f"Would fix commit message: {new_commit_msg}")
                    return True
            
            return True
            
        except Exception as e:
            logger.error(f"Error fixing commit messages: {e}")
            return False

    def commit_and_push_fixes(self, fixed_files: List[str], pr_number: int) -> bool:
        """Commit and push applied fixes."""
        if not fixed_files:
            return True
        
        try:
            # Configure git if needed
            self.run_command('git config user.name "PR Auto-Fixer"')
            self.run_command('git config user.email "pr-auto-fixer@local"')
            
            # Add fixed files
            for file_path in fixed_files:
                self.run_command(f'git add "{file_path}"')
            
            # Check if there are changes to commit
            result = self.run_command("git status --porcelain")
            if not result.stdout.strip():
                logger.info("No changes to commit after fixes")
                return True
            
            if not self.dry_run:
                # Commit changes
                commit_msg = f"""fix: automated code quality improvements for PR #{pr_number}

Applied fixes:
{chr(10).join(f'- {file_path}' for file_path in fixed_files)}

🤖 Auto-generated by PR Reviewer and Merger
Generated at {datetime.now().isoformat()}"""
                
                result = self.run_command(f'git commit -m "{commit_msg}"')
                if result.returncode != 0:
                    logger.error("Failed to commit fixes")
                    return False
                
                # Push changes
                result = self.run_command('git push')
                if result.returncode == 0:
                    logger.info(f"✅ Pushed fixes for PR #{pr_number}")
                    return True
                else:
                    logger.error(f"Failed to push fixes for PR #{pr_number}")
                    return False
            else:
                logger.info(f"Would commit and push fixes for PR #{pr_number}: {fixed_files}")
                return True
                
        except Exception as e:
            logger.error(f"Error committing and pushing fixes: {e}")
            return False

    def apply_fixes_to_pr(self, pr_analysis: Dict[str, Any]) -> bool:
        """Apply available fixes to PR."""
        pr_number = pr_analysis['pr_number']
        
        if not self.auto_fix_enabled:
            logger.info(f"Auto-fix disabled for PR #{pr_number}")
            return False
        
        if not pr_analysis['fixes_available']:
            logger.info(f"No auto-fixes available for PR #{pr_number}")
            return False
        
        logger.info(f"Applying fixes to PR #{pr_number}")
        
        # Checkout PR branch
        if not self.checkout_pr_branch(pr_number):
            return False
        
        try:
            all_fixed_files = []
            fixes_applied = False
            
            # Apply available fixes
            for fix in pr_analysis['fixes_available']:
                if not fix.get('auto_fixable', False):
                    continue
                
                fix_type = fix['type']
                logger.info(f"Applying fix: {fix['description']}")
                
                if fix_type == 'static_analysis_fix':
                    fixed_files = self.apply_static_analysis_fixes()
                    all_fixed_files.extend(fixed_files)
                    if fixed_files:
                        fixes_applied = True
                
                elif fix_type == 'commit_message_fix':
                    if self.fix_commit_messages(pr_number):
                        fixes_applied = True
            
            # Commit and push fixes if any were applied
            if fixes_applied:
                success = self.commit_and_push_fixes(all_fixed_files, pr_number)
                if success:
                    logger.info(f"✅ Successfully applied fixes to PR #{pr_number}")
                    
                    # Add comment about fixes
                    comment = f"""🤖 **Automated Fixes Applied**

Applied the following improvements:
{chr(10).join(f"- {fix['description']}" for fix in pr_analysis['fixes_available'] if fix.get('auto_fixable'))}

The PR checks should re-run automatically. Please review the changes."""
                    
                    if not self.dry_run:
                        self.run_command(f'gh pr comment {pr_number} --body "{comment}"')
                    
                    return True
                else:
                    logger.error(f"Failed to commit fixes for PR #{pr_number}")
                    return False
            else:
                logger.info(f"No fixes were applied for PR #{pr_number}")
                return False
                
        finally:
            # Return to main branch
            self.run_command('git checkout main')
        
        return False

    def wait_for_checks_completion(self, pr_number: int, timeout: int = 1800) -> bool:
        """Wait for PR checks to complete after applying fixes."""
        logger.info(f"Waiting for checks to complete for PR #{pr_number}...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Get current PR status
                result = self.run_command(f'gh pr view {pr_number} --json statusCheckRollup')
                if result.returncode != 0:
                    continue
                
                pr_data = json.loads(result.stdout)
                checks = pr_data.get('statusCheckRollup', [])
                
                pending_checks = [c for c in checks if c.get('status') in ['QUEUED', 'IN_PROGRESS']]
                
                if not pending_checks:
                    logger.info(f"All checks completed for PR #{pr_number}")
                    return True
                
                logger.info(f"Waiting for {len(pending_checks)} checks to complete...")
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error checking PR status: {e}")
                time.sleep(60)
        
        logger.warning(f"Timeout waiting for checks to complete for PR #{pr_number}")
        return False

    def approve_pr(self, pr_number: int) -> bool:
        """Approve PR if it meets criteria."""
        try:
            if not self.dry_run:
                result = self.run_command(f'gh pr review {pr_number} --approve --body "✅ **Automated Review - APPROVED**\\n\\nAll checks passed. This PR is ready for merge."')
                if result.returncode == 0:
                    logger.info(f"✅ Approved PR #{pr_number}")
                    return True
                else:
                    logger.error(f"Failed to approve PR #{pr_number}")
                    return False
            else:
                logger.info(f"Would approve PR #{pr_number}")
                return True
                
        except Exception as e:
            logger.error(f"Error approving PR #{pr_number}: {e}")
            return False

    def merge_pr(self, pr_number: int) -> bool:
        """Merge approved PR."""
        try:
            if not self.auto_merge_enabled:
                logger.info(f"Auto-merge disabled for PR #{pr_number}")
                return False
            
            # Final safety check
            result = self.run_command(f'gh pr view {pr_number} --json mergeable,reviewDecision')
            if result.returncode != 0:
                return False
            
            pr_data = json.loads(result.stdout)
            if pr_data.get('mergeable') != 'MERGEABLE':
                logger.warning(f"PR #{pr_number} is not mergeable")
                return False
            
            if not self.dry_run:
                # Merge PR
                result = self.run_command(f'gh pr merge {pr_number} --squash --delete-branch')
                if result.returncode == 0:
                    logger.info(f"🎉 Successfully merged PR #{pr_number}")
                    return True
                else:
                    logger.error(f"Failed to merge PR #{pr_number}")
                    return False
            else:
                logger.info(f"Would merge PR #{pr_number}")
                return True
                
        except Exception as e:
            logger.error(f"Error merging PR #{pr_number}: {e}")
            return False

    def process_pr(self, pr: Dict[str, Any]) -> bool:
        """Process a single PR through the review and merge workflow."""
        pr_number = pr['number']
        pr_title = pr['title']
        
        logger.info(f"Processing PR #{pr_number}: {pr_title}")
        
        # Skip if already processed recently
        if pr_number in self.processed_prs:
            logger.info(f"PR #{pr_number} already processed recently, skipping")
            return True
        
        try:
            # Analyze PR status
            analysis = self.analyze_pr_status(pr)
            
            # If ready to merge, approve and merge
            if analysis['ready_to_merge']:
                logger.info(f"PR #{pr_number} is ready to merge")
                
                if self.approve_pr(pr_number):
                    if self.merge_pr(pr_number):
                        self.processed_prs.add(pr_number)
                        return True
                return False
            
            # If has fixable issues, apply fixes
            if analysis['fixes_available'] and any(f.get('auto_fixable') for f in analysis['fixes_available']):
                logger.info(f"PR #{pr_number} has auto-fixable issues, applying fixes")
                
                if self.apply_fixes_to_pr(analysis):
                    # Wait for checks to complete
                    if self.wait_for_checks_completion(pr_number):
                        # Re-analyze after fixes
                        updated_analysis = self.analyze_pr_status(pr)
                        
                        if updated_analysis['ready_to_merge']:
                            if self.approve_pr(pr_number):
                                if self.merge_pr(pr_number):
                                    self.processed_prs.add(pr_number)
                                    return True
                    else:
                        logger.warning(f"Checks did not complete in time for PR #{pr_number}")
                else:
                    logger.warning(f"Failed to apply fixes to PR #{pr_number}")
            else:
                logger.info(f"PR #{pr_number} has no auto-fixable issues or requires manual review")
                
                # Add comment about issues found
                if analysis['issues']:
                    issues_summary = '\n'.join(f"- {issue['message']}" for issue in analysis['issues'])
                    comment = f"""🔍 **Automated Review - Issues Found**

The following issues were detected:
{issues_summary}

Please review and address these issues before the PR can be merged."""
                    
                    if not self.dry_run:
                        self.run_command(f'gh pr comment {pr_number} --body "{comment}"')
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing PR #{pr_number}: {e}")
            return False

    def run_monitoring_cycle(self) -> None:
        """Run a single monitoring cycle."""
        logger.info("Starting PR monitoring cycle...")
        
        # Get open PRs
        open_prs = self.get_open_prs()
        
        if not open_prs:
            logger.info("No open PRs found")
            return
        
        logger.info(f"Processing {len(open_prs)} open PRs")
        
        for pr in open_prs:
            pr_number = pr['number']
            
            # Skip very recent PRs to allow initial setup
            try:
                created_at = datetime.fromisoformat(pr['createdAt'].replace('Z', '+00:00'))
                if datetime.now(created_at.tzinfo) - created_at < timedelta(minutes=5):
                    logger.info(f"PR #{pr_number} is too recent, skipping")
                    continue
            except:
                pass  # Continue if date parsing fails
            
            # Process PR
            try:
                success = self.process_pr(pr)
                if success:
                    logger.info(f"✅ PR #{pr_number} processed successfully")
                else:
                    logger.info(f"⏳ PR #{pr_number} requires further attention")
                
                # Small delay between PRs
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Error processing PR #{pr_number}: {e}")
                continue
        
        logger.info("PR monitoring cycle completed")

    def start_monitoring(self, continuous: bool = False) -> None:
        """Start PR monitoring (single cycle or continuous)."""
        logger.info(f"Starting PR Reviewer and Merger (continuous: {continuous})")
        
        if continuous:
            try:
                while True:
                    self.run_monitoring_cycle()
                    logger.info(f"Waiting {self.check_interval} seconds before next cycle...")
                    time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
            except Exception as e:
                logger.error(f"Monitoring failed: {e}")
                sys.exit(1)
        else:
            self.run_monitoring_cycle()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Enhanced PR Review and Auto-Merge System")
    parser.add_argument("--continuous", action="store_true", help="Run continuously (for daemon mode)")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (no actual changes)")
    parser.add_argument("--interval", type=int, default=600, help="Check interval in seconds (default: 600)")
    parser.add_argument("--repo-path", help="Repository path (defaults to current directory)")
    parser.add_argument("--no-auto-fix", action="store_true", help="Disable automatic fixes")
    parser.add_argument("--no-auto-merge", action="store_true", help="Disable automatic merging")
    
    args = parser.parse_args()
    
    # Initialize monitor
    repo_path = Path(args.repo_path) if args.repo_path else None
    monitor = PRReviewerAndMerger(repo_path, dry_run=args.dry_run)
    
    # Configure based on arguments
    monitor.check_interval = args.interval
    monitor.auto_fix_enabled = not args.no_auto_fix
    monitor.auto_merge_enabled = not args.no_auto_merge and not args.dry_run
    
    # Start monitoring
    monitor.start_monitoring(continuous=args.continuous)


if __name__ == "__main__":
    main()
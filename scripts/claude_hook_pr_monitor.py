#!/usr/bin/env python3
"""
Claude Code Hook - PR Monitoring Script

This script is triggered by Claude Code hooks to monitor PR status and provide
session completion feedback.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/claude_hook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_git_status():
    """Get current git repository status."""
    try:
        # Get current branch
        branch_result = subprocess.run(
            ['git', 'branch', '--show-current'], 
            capture_output=True, 
            text=True, 
            check=True
        )
        current_branch = branch_result.stdout.strip()
        
        # Get git status
        status_result = subprocess.run(
            ['git', 'status', '--porcelain'], 
            capture_output=True, 
            text=True, 
            check=True
        )
        has_changes = bool(status_result.stdout.strip())
        
        # Get recent commits
        log_result = subprocess.run(
            ['git', 'log', '--oneline', '-3'], 
            capture_output=True, 
            text=True, 
            check=True
        )
        recent_commits = log_result.stdout.strip().split('\n')
        
        return {
            "current_branch": current_branch,
            "has_uncommitted_changes": has_changes,
            "recent_commits": recent_commits
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get git status: {e}")
        return None


def get_pr_status():
    """Get PR status for current branch."""
    try:
        # Check if there's an open PR for current branch
        result = subprocess.run(
            ['gh', 'pr', 'list', '--head', '$(git branch --show-current)', '--json', 'number,title,state'], 
            capture_output=True, 
            text=True, 
            shell=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            prs = json.loads(result.stdout)
            if prs:
                return prs[0]  # Return first (current) PR
        
        return None
    except Exception as e:
        logger.error(f"Failed to get PR status: {e}")
        return None


def session_complete_summary():
    """Generate session completion summary."""
    logger.info("🤖 Claude Code Session Complete - PR Monitor")
    
    git_status = get_git_status()
    pr_status = get_pr_status()
    
    print("\n" + "="*60)
    print("🤖 CLAUDE CODE SESSION SUMMARY")
    print("="*60)
    
    if git_status:
        print(f"📁 Current Branch: {git_status['current_branch']}")
        print(f"📝 Uncommitted Changes: {'Yes' if git_status['has_uncommitted_changes'] else 'No'}")
        
        if git_status['recent_commits']:
            print("📊 Recent Commits:")
            for commit in git_status['recent_commits'][:3]:
                print(f"   • {commit}")
    
    if pr_status:
        print(f"\n🔄 Active PR: #{pr_status['number']} - {pr_status['title']}")
        print(f"📋 Status: {pr_status['state']}")
        print(f"🔗 URL: https://github.com/arjaygg/supervisor-coding-agent/pull/{pr_status['number']}")
    else:
        print("\n📌 No active PR found for current branch")
    
    print("\n💡 Next Steps:")
    if git_status and git_status['has_uncommitted_changes']:
        print("   • Commit any remaining changes")
    if not pr_status and git_status and git_status['current_branch'] != 'main':
        print("   • Consider creating a PR for your branch")
    if pr_status and pr_status['state'] == 'OPEN':
        print("   • Review and merge your PR when ready")
    
    print("\n🚀 Session completed successfully!")
    print("="*60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Claude Code Hook - PR Monitor')
    parser.add_argument('--session-complete', action='store_true', 
                       help='Generate session completion summary')
    parser.add_argument('--git-status', action='store_true',
                       help='Show git repository status')
    parser.add_argument('--pr-status', action='store_true',
                       help='Show PR status for current branch')
    
    # Claude Code hook arguments
    parser.add_argument('--file', help='File path from Claude Code hook')
    parser.add_argument('--tool', help='Tool name from Claude Code hook')
    parser.add_argument('--action', help='Action from Claude Code hook')
    
    args = parser.parse_args()
    
    try:
        # Log hook activity if called by Claude Code
        if args.file or args.tool or args.action:
            logger.info(f"Claude Code Hook: tool={args.tool}, action={args.action}, file={args.file}")
            
            # For file operations, just log and continue silently
            if args.tool in ['Write', 'Edit', 'MultiEdit']:
                logger.info(f"File operation completed: {args.action}")
                return
        
        if args.session_complete:
            session_complete_summary()
        elif args.git_status:
            git_status = get_git_status()
            if git_status:
                print(json.dumps(git_status, indent=2))
        elif args.pr_status:
            pr_status = get_pr_status()
            if pr_status:
                print(json.dumps(pr_status, indent=2))
            else:
                print("No PR found for current branch")
        else:
            # Silent mode for hook calls without specific actions
            if not (args.file or args.tool or args.action):
                print("Claude Code Hook - PR Monitor")
                print("Use --session-complete for session summary")
            
    except Exception as e:
        logger.error(f"Hook execution failed: {e}")
        # Don't exit with error for hook calls to avoid disrupting Claude Code
        if not args.session_complete:
            return
        sys.exit(1)


if __name__ == "__main__":
    main()
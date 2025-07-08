#!/usr/bin/env python3
"""
Claude Hook-based PR Monitor

Intelligent PR monitoring that triggers via Claude Code hooks.
Provides real-time code analysis and automatic fixes when Claude makes changes.

This replaces:
- GitHub Actions continuous monitoring
- Polling-based PR monitoring
- Manual code review processes

Features:
- Event-driven analysis (only when code changes)
- AI-powered code improvements
- Automatic PR updates
- Context-aware fixes
- Cost-efficient operation
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from supervisor_agent.utils.log_config import setup_script_logging

# Configure logging with centralized configuration
logger = setup_script_logging('claude_hook_monitor', 'claude_hook_monitor.log')


class ClaudeHookPRMonitor:
    """Hook-based PR monitoring with intelligent analysis and auto-fixes."""
    
    def __init__(self, repo_path: Path = None):
        self.repo_path = repo_path or Path.cwd()
        self.session_files = set()  # Track files modified in this session
        self.analysis_cache = {}  # Cache analysis results
        
    def run_command(self, cmd: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Execute shell command safely."""
        if cwd is None:
            cwd = self.repo_path
            
        logger.info(f"Running: {cmd}")
        try:
            result = subprocess.run(
                cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                logger.error(f"Command failed: {cmd}\nError: {result.stderr}")
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {cmd}")
            raise
        except Exception as e:
            logger.error(f"Command execution failed: {cmd} - {e}")
            raise

    def is_in_git_repo(self) -> bool:
        """Check if we're in a git repository."""
        result = self.run_command("git rev-parse --is-inside-work-tree")
        return result.returncode == 0

    def get_current_branch(self) -> Optional[str]:
        """Get current git branch."""
        result = self.run_command("git branch --show-current")
        return result.stdout.strip() if result.returncode == 0 else None

    def is_pr_branch(self) -> bool:
        """Check if current branch is a PR branch (feature/*, fix/*, etc.)."""
        branch = self.get_current_branch()
        if not branch:
            return False
        
        pr_prefixes = ['feature/', 'fix/', 'bugfix/', 'hotfix/', 'improvement/', 'enhancement/']
        return any(branch.startswith(prefix) for prefix in pr_prefixes) or branch != 'main'

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze a single file for issues and improvements."""
        logger.info(f"Analyzing file: {file_path}")
        
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            logger.warning(f"File not found: {file_path}")
            return {"status": "file_not_found", "fixes": []}
        
        # Cache key based on file content hash
        try:
            content = file_path_obj.read_text()
            content_hash = hash(content)
            cache_key = f"{file_path}:{content_hash}"
            
            if cache_key in self.analysis_cache:
                logger.info(f"Using cached analysis for {file_path}")
                return self.analysis_cache[cache_key]
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return {"status": "read_error", "fixes": []}

        analysis_result = {
            "status": "analyzed",
            "file_path": file_path,
            "timestamp": datetime.now().isoformat(),
            "issues": [],
            "fixes": [],
            "metrics": {}
        }

        # Python file analysis
        if file_path_obj.suffix == '.py':
            analysis_result.update(self._analyze_python_file(file_path_obj))
        
        # TypeScript/JavaScript analysis
        elif file_path_obj.suffix in ['.ts', '.js', '.tsx', '.jsx']:
            analysis_result.update(self._analyze_typescript_file(file_path_obj))
        
        # YAML/JSON analysis
        elif file_path_obj.suffix in ['.yml', '.yaml', '.json']:
            analysis_result.update(self._analyze_config_file(file_path_obj))

        # Cache the result
        self.analysis_cache[cache_key] = analysis_result
        return analysis_result

    def _analyze_python_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze Python file for issues and potential fixes."""
        fixes = []
        issues = []
        
        try:
            # Check formatting with black
            black_result = self.run_command(f"black --check --diff {file_path}")
            if black_result.returncode != 0:
                issues.append({
                    "type": "formatting",
                    "severity": "warning",
                    "message": "Code formatting issues detected",
                    "tool": "black"
                })
                fixes.append({
                    "type": "auto_fix",
                    "command": f"black {file_path}",
                    "description": "Auto-fix code formatting with black"
                })
            
            # Check import sorting with isort
            isort_result = self.run_command(f"isort --check-only --diff {file_path}")
            if isort_result.returncode != 0:
                issues.append({
                    "type": "import_sorting",
                    "severity": "warning", 
                    "message": "Import sorting issues detected",
                    "tool": "isort"
                })
                fixes.append({
                    "type": "auto_fix",
                    "command": f"isort {file_path}",
                    "description": "Auto-fix import sorting with isort"
                })
            
            # Check linting with flake8
            flake8_result = self.run_command(f"flake8 {file_path}")
            if flake8_result.returncode != 0:
                issues.append({
                    "type": "linting",
                    "severity": "error",
                    "message": "Linting issues detected",
                    "tool": "flake8",
                    "details": flake8_result.stdout
                })
            
            # Security scan with bandit
            bandit_result = self.run_command(f"bandit -f json {file_path}")
            if bandit_result.returncode != 0 and bandit_result.stdout:
                try:
                    bandit_data = json.loads(bandit_result.stdout)
                    if bandit_data.get("results"):
                        issues.append({
                            "type": "security",
                            "severity": "high",
                            "message": "Security issues detected",
                            "tool": "bandit",
                            "count": len(bandit_data["results"])
                        })
                except json.JSONDecodeError:
                    pass
            
        except Exception as e:
            logger.error(f"Error analyzing Python file {file_path}: {e}")
        
        return {"issues": issues, "fixes": fixes}

    def _analyze_typescript_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze TypeScript/JavaScript file."""
        fixes = []
        issues = []
        
        try:
            # Check if prettier is available
            prettier_result = self.run_command(f"npx prettier --check {file_path}")
            if prettier_result.returncode != 0:
                issues.append({
                    "type": "formatting",
                    "severity": "warning",
                    "message": "Code formatting issues detected",
                    "tool": "prettier"
                })
                fixes.append({
                    "type": "auto_fix",
                    "command": f"npx prettier --write {file_path}",
                    "description": "Auto-fix code formatting with prettier"
                })
            
            # Check ESLint if available
            eslint_result = self.run_command(f"npx eslint {file_path}")
            if eslint_result.returncode != 0:
                issues.append({
                    "type": "linting",
                    "severity": "error",
                    "message": "ESLint issues detected",
                    "tool": "eslint",
                    "details": eslint_result.stdout
                })
                
                # Check if ESLint can auto-fix
                eslint_fix_result = self.run_command(f"npx eslint --fix-dry-run {file_path}")
                if eslint_fix_result.returncode == 0:
                    fixes.append({
                        "type": "auto_fix",
                        "command": f"npx eslint --fix {file_path}",
                        "description": "Auto-fix ESLint issues"
                    })
            
        except Exception as e:
            logger.error(f"Error analyzing TypeScript file {file_path}: {e}")
        
        return {"issues": issues, "fixes": fixes}

    def _analyze_config_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze configuration files (YAML, JSON)."""
        fixes = []
        issues = []
        
        try:
            # Validate JSON/YAML syntax
            if file_path.suffix == '.json':
                content = file_path.read_text()
                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    issues.append({
                        "type": "syntax",
                        "severity": "error",
                        "message": f"Invalid JSON syntax: {e}",
                        "tool": "json_validator"
                    })
            
            elif file_path.suffix in ['.yml', '.yaml']:
                try:
                    import yaml
                    content = file_path.read_text()
                    yaml.safe_load(content)
                except Exception as e:
                    issues.append({
                        "type": "syntax",
                        "severity": "error",
                        "message": f"Invalid YAML syntax: {e}",
                        "tool": "yaml_validator"
                    })
        
        except Exception as e:
            logger.error(f"Error analyzing config file {file_path}: {e}")
        
        return {"issues": issues, "fixes": fixes}

    def apply_fixes(self, analysis_result: Dict[str, Any]) -> bool:
        """Apply automatic fixes based on analysis results."""
        if not analysis_result.get("fixes"):
            return False
        
        fixes_applied = False
        file_path = analysis_result["file_path"]
        
        logger.info(f"Applying fixes for {file_path}")
        
        for fix in analysis_result["fixes"]:
            if fix["type"] == "auto_fix":
                try:
                    result = self.run_command(fix["command"])
                    if result.returncode == 0:
                        logger.info(f"✅ Applied fix: {fix['description']}")
                        fixes_applied = True
                    else:
                        logger.error(f"❌ Failed to apply fix: {fix['description']}")
                except Exception as e:
                    logger.error(f"Error applying fix {fix['description']}: {e}")
        
        return fixes_applied

    def commit_and_push_fixes(self, files_fixed: List[str]) -> bool:
        """Commit and push automatic fixes to the current branch."""
        if not files_fixed:
            return False
        
        try:
            # Configure git if needed
            self.run_command('git config user.name "Claude Hook Monitor"')
            self.run_command('git config user.email "claude-hook-monitor@local"')
            
            # Add fixed files
            for file_path in files_fixed:
                self.run_command(f'git add "{file_path}"')
            
            # Check if there are changes to commit
            status_result = self.run_command("git status --porcelain")
            if not status_result.stdout.strip():
                logger.info("No changes to commit after fixes")
                return False
            
            # Commit changes
            commit_msg = f"""fix: automatic code quality improvements via Claude hook

Files improved:
{chr(10).join(f'- {file_path}' for file_path in files_fixed)}

🤖 Applied via Claude Code hooks
Generated at {datetime.now().isoformat()}"""
            
            commit_result = self.run_command(f'git commit -m "{commit_msg}"')
            if commit_result.returncode != 0:
                logger.error("Failed to commit fixes")
                return False
            
            # Push to current branch
            branch = self.get_current_branch()
            if branch:
                push_result = self.run_command(f'git push origin "{branch}"')
                if push_result.returncode == 0:
                    logger.info(f"✅ Pushed fixes to branch {branch}")
                    return True
                else:
                    logger.error(f"Failed to push fixes to branch {branch}")
            
        except Exception as e:
            logger.error(f"Error committing and pushing fixes: {e}")
        
        return False

    def handle_file_change(self, file_path: str, tool: str, action: str) -> None:
        """Handle a single file change event from Claude hook."""
        logger.info(f"Processing file change: {file_path} (tool: {tool}, action: {action})")
        
        # Only process if we're in a git repo and on a PR branch
        if not self.is_in_git_repo():
            logger.info("Not in git repository, skipping analysis")
            return
        
        if not self.is_pr_branch():
            logger.info("Not on PR branch, skipping analysis")
            return
        
        # Track this file in the session
        self.session_files.add(file_path)
        
        # Analyze the file
        analysis_result = self.analyze_file(file_path)
        
        # Apply fixes if any are available
        if analysis_result.get("fixes"):
            fixes_applied = self.apply_fixes(analysis_result)
            
            if fixes_applied:
                # Commit and push fixes
                self.commit_and_push_fixes([file_path])
                
                # Log summary
                issue_count = len(analysis_result.get("issues", []))
                fix_count = len(analysis_result.get("fixes", []))
                logger.info(f"✅ Processed {file_path}: {issue_count} issues, {fix_count} fixes applied")
            else:
                logger.info(f"ℹ️ No fixes applied for {file_path}")
        else:
            logger.info(f"✅ No issues found in {file_path}")

    def handle_session_complete(self) -> None:
        """Handle end of Claude session - final review and cleanup."""
        logger.info("Claude session complete - performing final review")
        
        if not self.session_files:
            logger.info("No files modified in this session")
            return
        
        # Generate session summary
        total_files = len(self.session_files)
        logger.info(f"Session summary: {total_files} files modified")
        
        # Could add additional session-level analysis here
        # For example: overall code quality metrics, security summary, etc.
        
        # Log final summary
        logger.info("📊 Session Summary:")
        logger.info(f"  Files analyzed: {total_files}")
        logger.info(f"  Branch: {self.get_current_branch()}")
        logger.info(f"  Repository: {self.repo_path}")


def main():
    """Main entry point for Claude hook integration."""
    parser = argparse.ArgumentParser(description="Claude Hook PR Monitor")
    parser.add_argument("--file", help="File path that was modified")
    parser.add_argument("--tool", help="Claude tool that was used")
    parser.add_argument("--action", help="Action that was performed")
    parser.add_argument("--session-complete", action="store_true", help="Session completion hook")
    parser.add_argument("--repo-path", help="Repository path (defaults to current directory)")
    
    args = parser.parse_args()
    
    # Initialize monitor
    repo_path = Path(args.repo_path) if args.repo_path else None
    monitor = ClaudeHookPRMonitor(repo_path)
    
    try:
        if args.session_complete:
            monitor.handle_session_complete()
        elif args.file:
            monitor.handle_file_change(
                file_path=args.file,
                tool=args.tool or "unknown",
                action=args.action or "unknown"
            )
        else:
            logger.error("No valid action specified")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Hook execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
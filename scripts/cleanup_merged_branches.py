#!/usr/bin/env python3
"""
Branch Cleanup Script

Automated cleanup of merged feature branches both locally and remotely.
This script should be run after successful PR merges to keep the repository clean.

Usage:
    python3 scripts/cleanup_merged_branches.py --dry-run
    python3 scripts/cleanup_merged_branches.py --force
    python3 scripts/cleanup_merged_branches.py --branch feature/my-branch
"""

import argparse
import re
import subprocess
import sys
from typing import List, Tuple


class BranchCleanupManager:
    """Manages cleanup of merged feature branches"""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.main_branches = {"main", "master", "develop", "main-updated"}

    def run_command(self, command: List[str]) -> Tuple[bool, str, str]:
        """Run a command and return success, stdout, stderr"""
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def get_merged_branches(self) -> List[str]:
        """Get list of local branches that have been merged to main"""
        # First, update from remote
        success, _, _ = self.run_command(["git", "fetch", "origin"])
        if not success:
            print("⚠️  Warning: Could not fetch from remote")

        # Get merged branches
        success, output, _ = self.run_command(["git", "branch", "--merged", "main"])
        if not success:
            # Try with main-updated if main doesn't exist
            success, output, _ = self.run_command(
                ["git", "branch", "--merged", "main-updated"]
            )

        if not success:
            print("❌ Could not get merged branches")
            return []

        branches = []
        for line in output.split("\n"):
            branch = line.strip().lstrip("* ").strip()
            if branch and branch not in self.main_branches:
                # Filter out branches that shouldn't be deleted
                if not any(
                    pattern in branch
                    for pattern in ["main", "master", "HEAD", "develop"]
                ):
                    branches.append(branch)

        return branches

    def get_remote_merged_branches(self) -> List[str]:
        """Get list of remote branches that have been merged"""
        success, output, _ = self.run_command(
            ["git", "branch", "-r", "--merged", "origin/main"]
        )
        if not success:
            return []

        branches = []
        for line in output.split("\n"):
            branch = line.strip()
            if (
                branch
                and "origin/" in branch
                and not any(main in branch for main in self.main_branches)
            ):
                # Extract branch name without origin/
                branch_name = branch.replace("origin/", "")
                if branch_name not in self.main_branches:
                    branches.append(branch_name)

        return branches

    def delete_local_branch(self, branch: str) -> bool:
        """Delete a local branch"""
        if self.dry_run:
            print(f"🔍 DRY RUN: Would delete local branch '{branch}'")
            return True

        success, _, error = self.run_command(["git", "branch", "-d", branch])
        if success:
            print(f"✅ Deleted local branch '{branch}'")
            return True
        else:
            # Try force delete if regular delete failed
            success, _, error = self.run_command(["git", "branch", "-D", branch])
            if success:
                print(f"✅ Force deleted local branch '{branch}'")
                return True
            else:
                print(f"❌ Failed to delete local branch '{branch}': {error}")
                return False

    def delete_remote_branch(self, branch: str) -> bool:
        """Delete a remote branch"""
        if self.dry_run:
            print(f"🔍 DRY RUN: Would delete remote branch 'origin/{branch}'")
            return True

        success, _, error = self.run_command(
            ["git", "push", "origin", "--delete", branch]
        )
        if success:
            print(f"✅ Deleted remote branch 'origin/{branch}'")
            return True
        else:
            print(f"❌ Failed to delete remote branch 'origin/{branch}': {error}")
            return False

    def cleanup_specific_branch(self, branch_name: str) -> bool:
        """Clean up a specific branch"""
        print(f"🧹 Cleaning up branch: {branch_name}")

        success = True

        # Check if branch exists locally
        local_success, output, _ = self.run_command(
            ["git", "branch", "--list", branch_name]
        )
        if local_success and output.strip():
            if not self.delete_local_branch(branch_name):
                success = False

        # Check if branch exists remotely
        remote_success, output, _ = self.run_command(
            ["git", "branch", "-r", "--list", f"origin/{branch_name}"]
        )
        if remote_success and output.strip():
            if not self.delete_remote_branch(branch_name):
                success = False

        return success

    def cleanup_merged_branches(self) -> bool:
        """Clean up all merged branches"""
        print("🔍 Finding merged branches...")

        # Get merged branches
        local_merged = self.get_merged_branches()
        remote_merged = self.get_remote_merged_branches()

        print(f"📋 Found {len(local_merged)} local merged branches")
        print(f"📋 Found {len(remote_merged)} remote merged branches")

        if not local_merged and not remote_merged:
            print("✨ No merged branches to clean up")
            return True

        if self.dry_run:
            print(f"\n🔍 DRY RUN MODE - No changes will be made")

        success = True

        # Clean up local branches
        if local_merged:
            print(f"\n🧹 Cleaning up local branches:")
            for branch in local_merged:
                if not self.delete_local_branch(branch):
                    success = False

        # Clean up remote branches
        if remote_merged:
            print(f"\n🧹 Cleaning up remote branches:")
            for branch in remote_merged:
                if not self.delete_remote_branch(branch):
                    success = False

        # Clean up remote tracking references
        if not self.dry_run:
            print(f"\n🔄 Pruning remote tracking references...")
            prune_success, _, _ = self.run_command(["git", "remote", "prune", "origin"])
            if prune_success:
                print("✅ Pruned remote tracking references")
            else:
                print("⚠️  Could not prune remote tracking references")

        return success

    def interactive_cleanup(self) -> bool:
        """Interactive cleanup with user confirmation"""
        local_merged = self.get_merged_branches()
        remote_merged = self.get_remote_merged_branches()

        if not local_merged and not remote_merged:
            print("✨ No merged branches to clean up")
            return True

        print("📋 Merged branches found:")

        if local_merged:
            print("  Local branches:")
            for branch in local_merged:
                print(f"    - {branch}")

        if remote_merged:
            print("  Remote branches:")
            for branch in remote_merged:
                print(f"    - origin/{branch}")

        if self.dry_run:
            print("\n🔍 DRY RUN: Use --force to actually delete branches")
            return True

        response = input(f"\n❓ Delete these branches? [y/N]: ").strip().lower()
        if response not in ["y", "yes"]:
            print("⏹️  Cleanup cancelled")
            return True

        return self.cleanup_merged_branches()


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Clean up merged feature branches")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without making changes",
    )
    parser.add_argument(
        "--force", action="store_true", help="Delete branches without confirmation"
    )
    parser.add_argument("--branch", help="Clean up a specific branch")
    parser.add_argument(
        "--interactive", action="store_true", help="Interactive mode with confirmation"
    )

    args = parser.parse_args()

    # Determine mode
    dry_run = args.dry_run or not args.force

    if dry_run and not args.dry_run:
        print("🔍 Running in dry-run mode (use --force to actually delete)")

    cleanup_manager = BranchCleanupManager(dry_run=dry_run)

    try:
        if args.branch:
            # Clean up specific branch
            success = cleanup_manager.cleanup_specific_branch(args.branch)
        elif args.interactive:
            # Interactive cleanup
            success = cleanup_manager.interactive_cleanup()
        else:
            # Automatic cleanup
            success = cleanup_manager.cleanup_merged_branches()

        if success:
            print(f"\n🎉 Branch cleanup completed successfully")
        else:
            print(f"\n⚠️  Branch cleanup completed with some errors")
            sys.exit(1)

    except KeyboardInterrupt:
        print(f"\n⏹️  Cleanup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Cleanup failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

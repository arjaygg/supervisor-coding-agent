#!/usr/bin/env python3

"""
Environment State Management for Dev-Assist
Tracks deployment state across ephemeral and persistent environments
"""

import json
import os
import sys
import argparse
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class EnvironmentType(Enum):
    EPHEMERAL = "ephemeral"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DeploymentStatus(Enum):
    PENDING = "pending"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentState:
    """Represents the state of a deployment."""

    environment: str
    environment_type: EnvironmentType
    pr_number: Optional[int]
    branch: str
    commit_sha: str
    deployer: str
    status: DeploymentStatus
    timestamp: str
    backup_tag: Optional[str] = None
    images: Dict[str, str] = None
    endpoints: Dict[str, str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.images is None:
            self.images = {}
        if self.endpoints is None:
            self.endpoints = {}
        if self.metadata is None:
            self.metadata = {}


class EnvironmentStateManager:
    """Manages environment deployment state."""

    def __init__(self, state_dir: str = ".github/state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "environments.json"
        self.history_file = self.state_dir / "deployment_history.json"

    def _load_state(self) -> Dict[str, Dict]:
        """Load current environment state."""
        if not self.state_file.exists():
            return {}

        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load state file: {e}", file=sys.stderr)
            return {}

    def _save_state(self, state: Dict[str, Dict]):
        """Save current environment state."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2, sort_keys=True)
        except IOError as e:
            print(f"Error: Failed to save state file: {e}", file=sys.stderr)
            sys.exit(1)

    def _load_history(self) -> List[Dict]:
        """Load deployment history."""
        if not self.history_file.exists():
            return []

        try:
            with open(self.history_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load history file: {e}", file=sys.stderr)
            return []

    def _save_history(self, history: List[Dict]):
        """Save deployment history."""
        try:
            with open(self.history_file, "w") as f:
                json.dump(history, f, indent=2)
        except IOError as e:
            print(f"Error: Failed to save history file: {e}", file=sys.stderr)
            sys.exit(1)

    def _add_to_history(self, deployment: DeploymentState):
        """Add deployment to history."""
        history = self._load_history()
        history.append(asdict(deployment))

        # Keep only last 100 deployments
        if len(history) > 100:
            history = history[-100:]

        self._save_history(history)

    def update_deployment(self, deployment: DeploymentState):
        """Update deployment state."""
        state = self._load_state()

        # Convert enum values to strings for JSON serialization
        deployment_dict = asdict(deployment)
        deployment_dict["environment_type"] = deployment.environment_type.value
        deployment_dict["status"] = deployment.status.value

        state[deployment.environment] = deployment_dict
        self._save_state(state)
        self._add_to_history(deployment)

        print(f"✅ Updated state for environment: {deployment.environment}")

    def get_deployment(self, environment: str) -> Optional[DeploymentState]:
        """Get current deployment state for an environment."""
        state = self._load_state()

        if environment not in state:
            return None

        env_data = state[environment]
        env_data["environment_type"] = EnvironmentType(env_data["environment_type"])
        env_data["status"] = DeploymentStatus(env_data["status"])

        return DeploymentState(**env_data)

    def list_environments(self) -> List[DeploymentState]:
        """List all environments and their states."""
        state = self._load_state()
        environments = []

        for env_name, env_data in state.items():
            env_data["environment_type"] = EnvironmentType(env_data["environment_type"])
            env_data["status"] = DeploymentStatus(env_data["status"])
            environments.append(DeploymentState(**env_data))

        return environments

    def cleanup_ephemeral(self, max_age_hours: int = 24):
        """Clean up old ephemeral environments."""
        state = self._load_state()
        now = datetime.datetime.now()
        cleaned = []

        for env_name, env_data in list(state.items()):
            if env_data.get("environment_type") == EnvironmentType.EPHEMERAL.value:
                deployment_time = datetime.datetime.fromisoformat(
                    env_data["timestamp"].replace("Z", "+00:00")
                )
                age_hours = (
                    now - deployment_time.replace(tzinfo=None)
                ).total_seconds() / 3600

                if age_hours > max_age_hours:
                    del state[env_name]
                    cleaned.append(env_name)

        if cleaned:
            self._save_state(state)
            print(f"🧹 Cleaned up {len(cleaned)} old ephemeral environments")
            for env in cleaned:
                print(f"  - {env}")
        else:
            print("No ephemeral environments to clean up")

    def get_history(
        self, environment: Optional[str] = None, limit: int = 10
    ) -> List[Dict]:
        """Get deployment history."""
        history = self._load_history()

        if environment:
            history = [h for h in history if h["environment"] == environment]

        return history[-limit:]

    def export_state(self, format_type: str = "json") -> str:
        """Export current state in specified format."""
        state = self._load_state()

        if format_type == "json":
            return json.dumps(state, indent=2, sort_keys=True)
        elif format_type == "summary":
            summary = []
            for env_name, env_data in state.items():
                summary.append(
                    f"{env_name}: {env_data['status']} "
                    f"(PR#{env_data.get('pr_number', 'N/A')}, "
                    f"{env_data['branch']}, "
                    f"{env_data['deployer']})"
                )
            return "\n".join(summary)
        else:
            raise ValueError(f"Unsupported format: {format_type}")


def create_deployment_from_env() -> DeploymentState:
    """Create deployment state from environment variables."""
    return DeploymentState(
        environment=os.getenv("ENVIRONMENT", "unknown"),
        environment_type=EnvironmentType(os.getenv("ENVIRONMENT_TYPE", "ephemeral")),
        pr_number=int(os.getenv("PR_NUMBER", 0)) if os.getenv("PR_NUMBER") else None,
        branch=os.getenv("BRANCH", os.getenv("GITHUB_REF_NAME", "unknown")),
        commit_sha=os.getenv("COMMIT_SHA", os.getenv("GITHUB_SHA", "unknown")),
        deployer=os.getenv("DEPLOYER", os.getenv("GITHUB_ACTOR", "unknown")),
        status=DeploymentStatus(os.getenv("STATUS", "deployed")),
        timestamp=datetime.datetime.now().isoformat(),
        backup_tag=os.getenv("BACKUP_TAG"),
        images={
            "api": os.getenv("API_IMAGE", ""),
            "frontend": os.getenv("FRONTEND_IMAGE", ""),
        },
        endpoints={
            "api": os.getenv("API_URL", ""),
            "frontend": os.getenv("FRONTEND_URL", ""),
        },
        metadata={
            "github_run_id": os.getenv("GITHUB_RUN_ID"),
            "github_run_number": os.getenv("GITHUB_RUN_NUMBER"),
            "workflow": os.getenv("GITHUB_WORKFLOW"),
        },
    )


def main():
    parser = argparse.ArgumentParser(description="Manage Dev-Assist environment state")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update deployment state")
    update_parser.add_argument(
        "--from-env",
        action="store_true",
        help="Create deployment from environment variables",
    )
    update_parser.add_argument("--environment", help="Environment name")
    update_parser.add_argument(
        "--status",
        choices=[s.value for s in DeploymentStatus],
        help="Deployment status",
    )

    # Get command
    get_parser = subparsers.add_parser("get", help="Get deployment state")
    get_parser.add_argument("environment", help="Environment name")

    # List command
    list_parser = subparsers.add_parser("list", help="List all environments")
    list_parser.add_argument(
        "--format",
        choices=["json", "table", "summary"],
        default="table",
        help="Output format",
    )

    # Cleanup command
    cleanup_parser = subparsers.add_parser(
        "cleanup", help="Clean up old ephemeral environments"
    )
    cleanup_parser.add_argument(
        "--max-age-hours",
        type=int,
        default=24,
        help="Maximum age in hours for ephemeral environments",
    )

    # History command
    history_parser = subparsers.add_parser("history", help="Show deployment history")
    history_parser.add_argument("--environment", help="Filter by environment")
    history_parser.add_argument(
        "--limit", type=int, default=10, help="Number of entries to show"
    )

    # Export command
    export_parser = subparsers.add_parser("export", help="Export current state")
    export_parser.add_argument(
        "--format", choices=["json", "summary"], default="json", help="Export format"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    manager = EnvironmentStateManager()

    if args.command == "update":
        if args.from_env:
            deployment = create_deployment_from_env()
        else:
            if not args.environment:
                print(
                    "Error: --environment required when not using --from-env",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Create minimal deployment state
            deployment = DeploymentState(
                environment=args.environment,
                environment_type=EnvironmentType.DEVELOPMENT,  # Default
                pr_number=None,
                branch="unknown",
                commit_sha="unknown",
                deployer="manual",
                status=(
                    DeploymentStatus(args.status)
                    if args.status
                    else DeploymentStatus.DEPLOYED
                ),
                timestamp=datetime.datetime.now().isoformat(),
            )

        manager.update_deployment(deployment)

    elif args.command == "get":
        deployment = manager.get_deployment(args.environment)
        if deployment:
            print(json.dumps(asdict(deployment), indent=2, default=str))
        else:
            print(f"Environment '{args.environment}' not found", file=sys.stderr)
            sys.exit(1)

    elif args.command == "list":
        environments = manager.list_environments()

        if args.format == "json":
            print(
                json.dumps([asdict(env) for env in environments], indent=2, default=str)
            )
        elif args.format == "summary":
            for env in environments:
                pr_info = f"PR#{env.pr_number}" if env.pr_number else "N/A"
                print(
                    f"{env.environment}: {env.status.value} ({pr_info}, {env.branch}, {env.deployer})"
                )
        else:  # table format
            if not environments:
                print("No environments found")
                return

            print(
                f"{'Environment':<20} {'Type':<12} {'Status':<12} {'PR':<8} {'Branch':<20} {'Deployer':<15} {'Timestamp'}"
            )
            print("-" * 110)
            for env in environments:
                pr_info = str(env.pr_number) if env.pr_number else "N/A"
                timestamp = (
                    env.timestamp[:16] if len(env.timestamp) > 16 else env.timestamp
                )
                print(
                    f"{env.environment:<20} {env.environment_type.value:<12} {env.status.value:<12} "
                    f"{pr_info:<8} {env.branch:<20} {env.deployer:<15} {timestamp}"
                )

    elif args.command == "cleanup":
        manager.cleanup_ephemeral(args.max_age_hours)

    elif args.command == "history":
        history = manager.get_history(args.environment, args.limit)

        if not history:
            print("No deployment history found")
            return

        print(
            f"{'Timestamp':<20} {'Environment':<20} {'Status':<12} {'PR':<8} {'Deployer':<15}"
        )
        print("-" * 85)
        for entry in history:
            timestamp = (
                entry["timestamp"][:16]
                if len(entry["timestamp"]) > 16
                else entry["timestamp"]
            )
            pr_info = str(entry.get("pr_number", "N/A"))
            print(
                f"{timestamp:<20} {entry['environment']:<20} {entry['status']:<12} "
                f"{pr_info:<8} {entry['deployer']:<15}"
            )

    elif args.command == "export":
        output = manager.export_state(args.format)
        print(output)


if __name__ == "__main__":
    main()

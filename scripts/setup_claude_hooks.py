#!/usr/bin/env python3
"""
Setup Claude Code Hooks for PR Monitoring

This script configures Claude Code to use hook-based PR monitoring,
replacing GitHub Actions and continuous polling with intelligent,
event-driven analysis.
"""

import json
import os
import shutil
import sys
from pathlib import Path


def find_claude_settings_path():
    """Find the Claude settings directory."""
    # Common Claude settings locations
    possible_paths = [
        Path.home() / ".claude",
        Path.home() / ".config" / "claude",
        Path.home() / "Library" / "Application Support" / "claude",  # macOS
        Path.home() / "AppData" / "Roaming" / "claude",  # Windows
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    # Default to ~/.claude if none found
    return Path.home() / ".claude"


def backup_existing_settings(settings_path):
    """Backup existing Claude settings."""
    settings_file = settings_path / "settings.json"
    
    if settings_file.exists():
        backup_file = settings_path / "settings.json.backup"
        shutil.copy2(settings_file, backup_file)
        print(f"✅ Backed up existing settings to {backup_file}")
        return True
    return False


def load_existing_settings(settings_path):
    """Load existing Claude settings."""
    settings_file = settings_path / "settings.json"
    
    if settings_file.exists():
        try:
            with open(settings_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"⚠️ Error reading existing settings: {e}")
            return {}
    return {}


def setup_hooks_configuration():
    """Setup Claude Code hooks configuration."""
    print("🔧 Setting up Claude Code hooks for PR monitoring...")
    
    # Find Claude settings directory
    settings_path = find_claude_settings_path()
    settings_path.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Claude settings directory: {settings_path}")
    
    # Backup existing settings
    backup_existing_settings(settings_path)
    
    # Load existing settings
    existing_settings = load_existing_settings(settings_path)
    
    # Get the current repository path
    repo_path = Path.cwd()
    
    # Load our hooks configuration
    hooks_config_path = repo_path / "claude_hooks_config.json"
    
    if not hooks_config_path.exists():
        print(f"❌ Hook configuration file not found: {hooks_config_path}")
        print("   Please ensure you're running this from the repository root.")
        sys.exit(1)
    
    with open(hooks_config_path, 'r') as f:
        hooks_config = json.load(f)
    
    # Update hooks configuration with absolute paths
    for hook_type, hook_configs in hooks_config["hooks"].items():
        for hook_config in hook_configs:
            for hook in hook_config["hooks"]:
                if "command" in hook:
                    # Replace relative paths with absolute paths
                    command = hook["command"]
                    if command.startswith("python3 scripts/"):
                        command = command.replace("python3 scripts/", f"python3 {repo_path}/scripts/")
                        hook["command"] = command
    
    # Merge with existing settings
    if "hooks" in existing_settings:
        print("⚠️ Existing hooks configuration found. Merging...")
        # For now, we'll replace existing hooks
        # In a production setup, you might want to merge more intelligently
    
    existing_settings["hooks"] = hooks_config["hooks"]
    
    # Write updated settings
    settings_file = settings_path / "settings.json"
    with open(settings_file, 'w') as f:
        json.dump(existing_settings, f, indent=2)
    
    print(f"✅ Claude hooks configuration updated: {settings_file}")
    
    # Make the hook script executable
    hook_script = repo_path / "scripts" / "claude_hook_pr_monitor.py"
    hook_script.chmod(0o755)
    
    print("📋 Configuration Summary:")
    print(f"   Repository: {repo_path}")
    print(f"   Hook script: {hook_script}")
    print(f"   Settings file: {settings_file}")
    print()
    print("🎯 Hooks configured for:")
    print("   - PostToolUse: Edit, Write, MultiEdit")
    print("   - Stop: Session completion")
    print()
    print("✅ Setup complete! Claude Code will now use hook-based PR monitoring.")
    print()
    print("🚀 Next steps:")
    print("   1. The hooks will automatically trigger when Claude edits files")
    print("   2. Monitor logs in claude_hook_monitor.log")
    print("   3. Consider disabling GitHub Actions PR monitoring to save costs")
    
    return True


def verify_dependencies():
    """Verify required dependencies are available."""
    print("🔍 Verifying dependencies...")
    
    # Check Python modules
    required_modules = ["json", "subprocess", "pathlib"]
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"❌ Missing required modules: {missing_modules}")
        return False
    
    # Check git availability
    if not shutil.which("git"):
        print("❌ Git is not available in PATH")
        return False
    
    # Check code quality tools
    tools = ["black", "isort", "flake8", "bandit"]
    missing_tools = []
    
    for tool in tools:
        if not shutil.which(tool):
            missing_tools.append(tool)
    
    if missing_tools:
        print(f"⚠️ Some code quality tools are missing: {missing_tools}")
        print("   Install with: pip install black isort flake8 bandit")
        print("   Hooks will still work but some features may be limited.")
    
    print("✅ Dependencies verified")
    return True


def main():
    """Main setup function."""
    print("🤖 Claude Code Hook-based PR Monitor Setup")
    print("=" * 50)
    
    if not verify_dependencies():
        print("❌ Dependency verification failed")
        sys.exit(1)
    
    if not setup_hooks_configuration():
        print("❌ Hook configuration failed")
        sys.exit(1)
    
    print()
    print("🎉 Setup completed successfully!")
    print()
    print("💡 Tips:")
    print("   - Test the setup by having Claude edit a file in a PR branch")
    print("   - Check claude_hook_monitor.log for activity")
    print("   - Hooks only activate on PR branches (feature/*, fix/*, etc.)")
    print("   - Consider adding this setup to your team's onboarding docs")


if __name__ == "__main__":
    main()
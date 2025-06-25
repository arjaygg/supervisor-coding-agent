#!/usr/bin/env python3
"""
Multi-Provider Migration Tool

Helps users migrate from legacy agent configuration to the new multi-provider
architecture with minimal downtime and automated configuration conversion.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


class MultiProviderMigrator:
    """Handles migration from legacy agents to multi-provider system"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent
        self.backup_dir = self.project_root / "migration_backup"
        self.config_files = [
            ".env",
            ".env.local", 
            "supervisor_agent/config.py",
            "docker-compose.yml"
        ]
        
    def analyze_current_setup(self) -> Dict[str, Any]:
        """Analyze current configuration and agent setup"""
        print("🔍 Analyzing current configuration...")
        
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "legacy_agents": [],
            "environment_variables": {},
            "config_files_found": [],
            "migration_recommendations": [],
            "estimated_downtime": "< 5 minutes"
        }
        
        try:
            # Try to load current configuration
            from supervisor_agent.config import settings
            
            # Analyze legacy agents
            api_keys = settings.claude_api_keys_list
            analysis["legacy_agents"] = [
                {
                    "id": f"claude-agent-{i+1}",
                    "api_key_configured": bool(key.strip()),
                    "estimated_quota": "Unknown"
                }
                for i, key in enumerate(api_keys)
            ]
            
            # Check current multi-provider status
            analysis["multi_provider_enabled"] = settings.multi_provider_enabled
            analysis["current_strategy"] = settings.default_load_balancing_strategy
            
            # Environment analysis
            for key in ["CLAUDE_API_KEYS", "CLAUDE_CLI_PATH", "DATABASE_URL"]:
                if key in os.environ:
                    analysis["environment_variables"][key] = "SET" if os.environ[key] else "EMPTY"
                    
        except Exception as e:
            analysis["config_error"] = str(e)
            analysis["migration_recommendations"].append(
                "Configuration loading failed - manual migration may be required"
            )
            
        # Check for config files
        for config_file in self.config_files:
            file_path = self.project_root / config_file
            if file_path.exists():
                analysis["config_files_found"].append(str(file_path))
                
        # Generate recommendations
        if len(analysis["legacy_agents"]) > 0:
            analysis["migration_recommendations"].extend([
                f"Found {len(analysis['legacy_agents'])} legacy agents ready for migration",
                "Multi-provider system will provide better load balancing and failover",
                "Consider setting up provider priorities based on quota limits"
            ])
        else:
            analysis["migration_recommendations"].append(
                "No legacy agents found - fresh multi-provider setup recommended"
            )
            
        return analysis
        
    def create_backup(self) -> bool:
        """Create backup of current configuration"""
        print("💾 Creating configuration backup...")
        
        try:
            self.backup_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_subdir = self.backup_dir / f"backup_{timestamp}"
            backup_subdir.mkdir()
            
            files_backed_up = 0
            for config_file in self.config_files:
                source_path = self.project_root / config_file
                if source_path.exists():
                    dest_path = backup_subdir / config_file
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, dest_path)
                    files_backed_up += 1
                    
            print(f"✅ Backed up {files_backed_up} configuration files to {backup_subdir}")
            return True
            
        except Exception as e:
            print(f"❌ Backup failed: {str(e)}")
            return False
            
    def generate_provider_config(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate multi-provider configuration from legacy setup"""
        print("⚙️  Generating provider configuration...")
        
        config = {
            "providers": []
        }
        
        # Convert legacy agents to providers
        for i, agent in enumerate(analysis.get("legacy_agents", [])):
            if agent.get("api_key_configured"):
                provider_config = {
                    "id": f"claude-migrated-{i+1}",
                    "name": f"Claude Provider {i+1} (Migrated)",
                    "type": "claude_cli",
                    "priority": i + 1,  # First agent gets highest priority
                    "enabled": True,
                    "config": {
                        "api_keys": ["${CLAUDE_API_KEY_" + str(i+1) + "}"],  # Reference to env var
                        "cli_path": "${CLAUDE_CLI_PATH:-claude}",
                        "max_tokens_per_request": 4000,
                        "rate_limit_per_minute": 60,
                        "rate_limit_per_hour": 1000,
                        "rate_limit_per_day": 10000,
                        "mock_mode": False
                    },
                    "capabilities": {
                        "supported_tasks": [
                            "code_review", "bug_fix", "feature_development",
                            "code_analysis", "refactoring", "documentation",
                            "testing", "security_analysis", "performance_optimization",
                            "general_coding"
                        ]
                    }
                }
                config["providers"].append(provider_config)
                
        # Always add mock provider as fallback
        mock_provider = {
            "id": "local-mock-fallback",
            "name": "Local Mock Provider (Fallback)",
            "type": "local_mock", 
            "priority": 9,
            "enabled": True,
            "config": {
                "response_delay_min": 0.5,
                "response_delay_max": 2.0,
                "failure_rate": 0.05,
                "deterministic": True
            },
            "capabilities": {
                "supported_tasks": [
                    "code_review", "bug_fix", "feature_development",
                    "code_analysis", "refactoring", "documentation",
                    "testing", "security_analysis", "performance_optimization",
                    "general_coding"
                ]
            }
        }
        config["providers"].append(mock_provider)
        
        return config
        
    def update_environment_file(self, provider_config: Dict[str, Any]) -> bool:
        """Update .env file with multi-provider settings"""
        print("🔧 Updating environment configuration...")
        
        try:
            env_file = self.project_root / ".env"
            env_lines = []
            
            # Read existing .env if it exists
            if env_file.exists():
                with open(env_file, 'r') as f:
                    env_lines = f.readlines()
                    
            # Remove old multi-provider settings
            env_lines = [line for line in env_lines 
                        if not any(key in line for key in [
                            "ENABLE_MULTI_PROVIDER",
                            "PROVIDERS_CONFIG", 
                            "DEFAULT_LOAD_BALANCING_STRATEGY"
                        ])]
            
            # Add new multi-provider settings
            env_lines.extend([
                "\n# Multi-Provider Configuration (Added by migration tool)\n",
                "ENABLE_MULTI_PROVIDER=true\n",
                f"PROVIDERS_CONFIG='{json.dumps(provider_config)}'\n",
                "DEFAULT_LOAD_BALANCING_STRATEGY=priority_based\n",
                "PROVIDER_HEALTH_CHECK_INTERVAL=60\n",
                "PROVIDER_FAILURE_THRESHOLD=3\n",
                "PROVIDER_RECOVERY_TIMEOUT=300\n",
                "\n"
            ])
            
            # Write updated .env file
            with open(env_file, 'w') as f:
                f.writelines(env_lines)
                
            print(f"✅ Updated {env_file}")
            return True
            
        except Exception as e:
            print(f"❌ Environment file update failed: {str(e)}")
            return False
            
    def create_provider_config_file(self, provider_config: Dict[str, Any]) -> bool:
        """Create dedicated provider configuration file"""
        print("📄 Creating provider configuration file...")
        
        try:
            config_file = self.project_root / "providers.json"
            
            with open(config_file, 'w') as f:
                json.dump(provider_config, f, indent=2)
                
            print(f"✅ Created {config_file}")
            
            # Also create a template for easy editing
            template_file = self.project_root / "providers.template.json"
            template_config = self._create_config_template()
            
            with open(template_file, 'w') as f:
                json.dump(template_config, f, indent=2)
                
            print(f"✅ Created {template_file} for reference")
            return True
            
        except Exception as e:
            print(f"❌ Provider config file creation failed: {str(e)}")
            return False
            
    def _create_config_template(self) -> Dict[str, Any]:
        """Create a template configuration for reference"""
        return {
            "_description": "Multi-Provider Configuration Template",
            "_instructions": [
                "Copy this template to customize your provider setup",
                "Replace placeholder values with your actual configuration",
                "See documentation for all available options"
            ],
            "providers": [
                {
                    "id": "claude-primary",
                    "name": "Claude Primary Subscription",
                    "type": "claude_cli",
                    "priority": 1,
                    "enabled": True,
                    "config": {
                        "api_keys": ["your-primary-api-key-here"],
                        "cli_path": "claude",
                        "rate_limit_per_day": 10000,
                        "_note": "Adjust rate limits based on your subscription"
                    },
                    "capabilities": {
                        "supported_tasks": ["code_review", "bug_fix", "feature_development"]
                    }
                },
                {
                    "id": "claude-secondary", 
                    "name": "Claude Secondary Subscription",
                    "type": "claude_cli",
                    "priority": 2,
                    "enabled": True,
                    "config": {
                        "api_keys": ["your-secondary-api-key-here"],
                        "rate_limit_per_day": 5000
                    }
                }
            ]
        }
        
    def validate_migration(self) -> Dict[str, Any]:
        """Validate the migration was successful"""
        print("✅ Validating migration...")
        
        validation = {
            "success": False,
            "checks": {},
            "warnings": [],
            "next_steps": []
        }
        
        try:
            # Import and test configuration
            from supervisor_agent.config import settings
            
            validation["checks"]["config_loads"] = True
            validation["checks"]["multi_provider_enabled"] = settings.multi_provider_enabled
            validation["checks"]["provider_configs"] = len(settings.get_provider_configs())
            
            if settings.multi_provider_enabled:
                validation["checks"]["provider_config_valid"] = True
                validation["next_steps"].extend([
                    "Test the system with: python3 integration_test.py",
                    "Start the application and verify provider health",
                    "Update API keys in environment variables as needed"
                ])
            else:
                validation["warnings"].append("Multi-provider is not enabled in configuration")
                
            # Check if provider config file exists
            provider_file = self.project_root / "providers.json"
            validation["checks"]["provider_file_exists"] = provider_file.exists()
            
            if all(validation["checks"].values()):
                validation["success"] = True
            
        except Exception as e:
            validation["checks"]["config_loads"] = False
            validation["warnings"].append(f"Configuration validation failed: {str(e)}")
            
        return validation
        
    def run_migration(self, dry_run: bool = False) -> bool:
        """Run the complete migration process"""
        print(f"🚀 Starting migration to multi-provider architecture...")
        print(f"{'🔍 DRY RUN MODE - No changes will be made' if dry_run else '⚠️  LIVE MODE - Changes will be applied'}")
        
        # Step 1: Analyze current setup
        analysis = self.analyze_current_setup()
        print(f"\n📊 Analysis Results:")
        print(f"   - Legacy agents found: {len(analysis.get('legacy_agents', []))}")
        print(f"   - Multi-provider enabled: {analysis.get('multi_provider_enabled', False)}")
        print(f"   - Config files found: {len(analysis.get('config_files_found', []))}")
        
        if not dry_run and len(analysis.get("legacy_agents", [])) == 0:
            print("⚠️  No legacy agents found. Migration may not be necessary.")
            return False
            
        # Step 2: Create backup (only in live mode)
        if not dry_run:
            if not self.create_backup():
                print("❌ Migration aborted due to backup failure")
                return False
                
        # Step 3: Generate provider configuration
        provider_config = self.generate_provider_config(analysis)
        print(f"📋 Generated configuration for {len(provider_config['providers'])} providers")
        
        if dry_run:
            print("\n🔍 DRY RUN: Would create the following provider configuration:")
            print(json.dumps(provider_config, indent=2))
            return True
            
        # Step 4: Update configuration files
        if not self.update_environment_file(provider_config):
            print("❌ Migration failed during environment file update")
            return False
            
        if not self.create_provider_config_file(provider_config):
            print("❌ Migration failed during provider config creation")
            return False
            
        # Step 5: Validate migration
        validation = self.validate_migration()
        
        if validation["success"]:
            print("\n🎉 Migration completed successfully!")
            print("\n📋 Next Steps:")
            for step in validation["next_steps"]:
                print(f"   - {step}")
                
            if validation["warnings"]:
                print("\n⚠️  Warnings:")
                for warning in validation["warnings"]:
                    print(f"   - {warning}")
        else:
            print("\n❌ Migration validation failed")
            print("Check the errors above and consider manual configuration")
            return False
            
        return True


def main():
    """Main CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate from legacy agents to multi-provider architecture"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Analyze and show what would be changed without making changes"
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true", 
        help="Only analyze current setup and exit"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Path to project root directory"
    )
    
    args = parser.parse_args()
    
    migrator = MultiProviderMigrator(args.project_root)
    
    try:
        if args.analyze_only:
            analysis = migrator.analyze_current_setup()
            print(json.dumps(analysis, indent=2))
            return
            
        success = migrator.run_migration(dry_run=args.dry_run)
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
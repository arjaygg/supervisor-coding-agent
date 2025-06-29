import json
import os
import secrets
from typing import Any, Dict, List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./supervisor_agent.db", description="Database connection URL"
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )

    # Celery
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0", description="Celery broker URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0", description="Celery result backend URL"
    )

    # Claude Configuration
    claude_cli_path: str = Field(default="claude")
    claude_api_keys: str = Field(
        default="", description="Comma-separated list of Claude API keys"
    )
    claude_quota_limit_per_agent: int = Field(default=1000)
    claude_quota_reset_hours: int = Field(default=24)

    # Notifications
    slack_bot_token: str = Field(default="")
    slack_channel: str = Field(default="#alerts")
    email_smtp_host: str = Field(default="")
    email_smtp_port: int = Field(default=587)
    email_username: str = Field(default="")
    email_password: str = Field(default="")
    email_from: str = Field(default="")
    email_to: str = Field(default="")

    # Application
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    app_debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # Task Configuration
    batch_size: int = Field(default=10)
    batch_interval_seconds: int = Field(default=60)
    max_retries: int = Field(default=3)

    # Development Features
    redis_required: bool = Field(default=True)
    celery_required: bool = Field(default=True)
    enable_mock_responses: bool = Field(default=False)
    enable_debug_endpoints: bool = Field(default=False)
    skip_auth_for_development: bool = Field(default=False)

    # Security and Authentication
    jwt_secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(64),
        description="JWT signing secret key",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)

    # Security hardening
    security_enabled: bool = Field(default=True)
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests_per_minute: int = Field(default=60)
    rate_limit_burst: int = Field(default=120)

    # CORS settings
    cors_allow_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )
    cors_allow_credentials: bool = Field(default=True)

    # OAuth settings
    oauth_google_client_id: Optional[str] = Field(default=None)
    oauth_google_client_secret: Optional[str] = Field(default=None)
    oauth_github_client_id: Optional[str] = Field(default=None)
    oauth_github_client_secret: Optional[str] = Field(default=None)

    # Session management
    session_cleanup_interval_hours: int = Field(default=24)
    max_sessions_per_user: int = Field(default=10)

    # Provider Configuration
    providers_config: str = Field(
        default="",
        description="JSON string or file path containing provider configurations",
    )
    enable_multi_provider: bool = Field(
        default=False, description="Enable multi-provider functionality"
    )
    default_load_balancing_strategy: str = Field(
        default="priority_based",
        description="Default load balancing strategy: round_robin, least_loaded, fastest_response, priority_based, capability_based",
    )
    provider_health_check_interval: int = Field(
        default=60, description="Health check interval for providers in seconds"
    )
    provider_failure_threshold: int = Field(
        default=3,
        description="Number of consecutive failures before marking provider as unhealthy",
    )
    provider_recovery_timeout: int = Field(
        default=300,
        description="Time in seconds to wait before retrying failed provider",
    )

    @property
    def claude_api_keys_list(self) -> List[str]:
        if not self.claude_api_keys:
            return []
        return [key.strip() for key in self.claude_api_keys.split(",") if key.strip()]

    @property
    def providers_config_dict(self) -> Dict[str, Any]:
        """Parse provider configuration from JSON string or file."""
        if not self.providers_config:
            return self._get_default_provider_config()

        # Try to parse as JSON string first
        try:
            return json.loads(self.providers_config)
        except json.JSONDecodeError:
            pass

        # Try to read as file path
        try:
            if os.path.isfile(self.providers_config):
                with open(self.providers_config, "r") as f:
                    return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            pass

        # Return default configuration if parsing fails
        return self._get_default_provider_config()

    def _get_default_provider_config(self) -> Dict[str, Any]:
        """Get default provider configuration based on existing settings."""
        config = {"providers": []}

        # If we have Claude API keys, create Claude providers
        if self.claude_api_keys_list:
            # Primary Claude provider
            claude_config = {
                "id": "claude-primary",
                "name": "Claude CLI Primary",
                "type": "claude_cli",
                "priority": 1,
                "enabled": True,
                "config": {
                    "api_keys": self.claude_api_keys_list,
                    "cli_path": self.claude_cli_path,
                    "max_tokens_per_request": 4000,
                    "rate_limit_per_minute": 60,
                    "rate_limit_per_hour": 1000,
                    "rate_limit_per_day": 10000,
                    "mock_mode": self.enable_mock_responses,
                },
                "capabilities": {
                    "supported_tasks": [
                        "code_review",
                        "bug_fix",
                        "feature_development",
                        "code_analysis",
                        "refactoring",
                        "documentation",
                        "testing",
                        "security_analysis",
                        "performance_optimization",
                        "general_coding",
                    ]
                },
            }
            config["providers"].append(claude_config)

        # Always include a mock provider for testing/fallback
        mock_config = {
            "id": "local-mock",
            "name": "Local Mock Provider",
            "type": "local_mock",
            "priority": 9,  # Low priority
            "enabled": True,
            "config": {
                "response_delay_min": 0.5,
                "response_delay_max": 2.0,
                "failure_rate": 0.05,
                "deterministic": True,
            },
            "capabilities": {
                "supported_tasks": [
                    "code_review",
                    "bug_fix",
                    "feature_development",
                    "code_analysis",
                    "refactoring",
                    "documentation",
                    "testing",
                    "security_analysis",
                    "performance_optimization",
                    "general_coding",
                ]
            },
        }
        config["providers"].append(mock_config)

        return config

    def get_provider_configs(self) -> List[Dict[str, Any]]:
        """Get list of provider configurations."""
        return self.providers_config_dict.get("providers", [])

    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of warnings"""
        warnings = []

        # Legacy configuration validation
        if not self.claude_api_keys and not self.enable_multi_provider:
            warnings.append(
                "No Claude API keys configured - agent functionality will be limited"
            )
        elif self.claude_cli_path == "mock":
            warnings.append(
                "Running in mock mode - Claude CLI responses will be simulated"
            )

        # Provider configuration validation
        if self.enable_multi_provider:
            try:
                provider_configs = self.get_provider_configs()
                if not provider_configs:
                    warnings.append(
                        "Multi-provider enabled but no providers configured"
                    )
                else:
                    enabled_providers = [
                        p for p in provider_configs if p.get("enabled", True)
                    ]
                    if not enabled_providers:
                        warnings.append(
                            "Multi-provider enabled but no providers are enabled"
                        )
                    else:
                        warnings.append(
                            f"Multi-provider enabled with {len(enabled_providers)} provider(s)"
                        )

                # Validate load balancing strategy
                valid_strategies = [
                    "round_robin",
                    "least_loaded",
                    "fastest_response",
                    "priority_based",
                    "capability_based",
                ]
                if self.default_load_balancing_strategy not in valid_strategies:
                    warnings.append(
                        f"Invalid load balancing strategy: {self.default_load_balancing_strategy}"
                    )

            except Exception as e:
                warnings.append(f"Provider configuration validation failed: {str(e)}")

        if "localhost" in self.database_url and "sqlite" not in self.database_url:
            warnings.append(
                "Using localhost database - ensure PostgreSQL/MySQL is running"
            )

        if "localhost" in self.redis_url:
            warnings.append("Using localhost Redis - ensure Redis is running")

        # Check for missing required environment variables
        if self.database_url == "sqlite:///./supervisor_agent.db":
            warnings.append(
                "Using default SQLite database - consider PostgreSQL for production"
            )

        if self.app_debug:
            warnings.append("Debug mode is enabled - disable in production")

        return warnings

    def get_startup_info(self) -> dict:
        """Get startup configuration information"""
        info = {
            "mode": "mock" if self.claude_cli_path == "mock" else "production",
            "database_type": (
                "sqlite" if "sqlite" in self.database_url else "postgresql"
            ),
            "redis_connected": "localhost" in self.redis_url,
            "debug_mode": self.app_debug,
            "log_level": self.log_level,
        }

        # Add provider information
        if self.enable_multi_provider:
            try:
                provider_configs = self.get_provider_configs()
                enabled_providers = [
                    p for p in provider_configs if p.get("enabled", True)
                ]
                info.update(
                    {
                        "multi_provider_enabled": True,
                        "total_providers": len(provider_configs),
                        "enabled_providers": len(enabled_providers),
                        "load_balancing_strategy": self.default_load_balancing_strategy,
                        "provider_types": list(
                            set(p.get("type") for p in enabled_providers)
                        ),
                    }
                )
            except Exception:
                info.update(
                    {"multi_provider_enabled": True, "provider_config_error": True}
                )
        else:
            info.update(
                {
                    "multi_provider_enabled": False,
                    "agents_configured": len(self.claude_api_keys_list),
                }
            )

        return info

    @property
    def multi_provider_enabled(self) -> bool:
        """Check if multi-provider functionality is enabled"""
        return self.enable_multi_provider


def create_settings():
    """Create settings instance, allows for reloading in tests"""
    return Settings()


try:
    settings = create_settings()
    warnings = settings.validate_configuration()
    if warnings:
        import logging

        logger = logging.getLogger(__name__)
        for warning in warnings:
            logger.warning(f"Configuration: {warning}")
except Exception as e:
    import logging

    logging.error(f"Failed to load configuration: {str(e)}")
    raise

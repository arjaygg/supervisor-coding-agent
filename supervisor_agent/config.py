from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    # Database
    database_url: str = Field(
        default="sqlite:///./supervisor_agent.db", 
        description="Database connection URL"
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0", 
        description="Redis connection URL"
    )

    # Celery
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0", 
        description="Celery broker URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0", 
        description="Celery result backend URL"
    )

    # Claude Configuration
    claude_cli_path: str = Field(default="claude")
    claude_api_keys: str = Field(
        default="", 
        description="Comma-separated list of Claude API keys"
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

    @property
    def claude_api_keys_list(self) -> List[str]:
        if not self.claude_api_keys:
            return []
        return [key.strip() for key in self.claude_api_keys.split(",") if key.strip()]

    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of warnings"""
        warnings = []
        
        if not self.claude_api_keys:
            warnings.append("No Claude API keys configured - agent functionality will be limited")
        elif self.claude_cli_path == "mock":
            warnings.append("Running in mock mode - Claude CLI responses will be simulated")
        
        if "localhost" in self.database_url and "sqlite" not in self.database_url:
            warnings.append("Using localhost database - ensure PostgreSQL/MySQL is running")
        
        if "localhost" in self.redis_url:
            warnings.append("Using localhost Redis - ensure Redis is running")
        
        # Check for missing required environment variables
        if self.database_url == "sqlite:///./supervisor_agent.db":
            warnings.append("Using default SQLite database - consider PostgreSQL for production")
        
        if self.app_debug:
            warnings.append("Debug mode is enabled - disable in production")
            
        return warnings
    
    def get_startup_info(self) -> dict:
        """Get startup configuration information"""
        return {
            "mode": "mock" if self.claude_cli_path == "mock" else "production",
            "database_type": "sqlite" if "sqlite" in self.database_url else "postgresql",
            "redis_connected": "localhost" in self.redis_url,
            "agents_configured": len(self.claude_api_keys_list),
            "debug_mode": self.app_debug,
            "log_level": self.log_level
        }


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

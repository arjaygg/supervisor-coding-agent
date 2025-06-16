from pydantic import Field  
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Redis
    redis_url: str = Field(..., env="REDIS_URL")
    
    # Celery
    celery_broker_url: str = Field(..., env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(..., env="CELERY_RESULT_BACKEND")
    
    # Claude Configuration
    claude_cli_path: str = Field(default="claude", env="CLAUDE_CLI_PATH")
    claude_api_keys: str = Field(..., env="CLAUDE_API_KEYS")
    claude_quota_limit_per_agent: int = Field(default=1000, env="CLAUDE_QUOTA_LIMIT_PER_AGENT")
    claude_quota_reset_hours: int = Field(default=24, env="CLAUDE_QUOTA_RESET_HOURS")
    
    # Notifications
    slack_bot_token: str = Field(default="", env="SLACK_BOT_TOKEN")
    slack_channel: str = Field(default="#alerts", env="SLACK_CHANNEL")
    email_smtp_host: str = Field(default="", env="EMAIL_SMTP_HOST")
    email_smtp_port: int = Field(default=587, env="EMAIL_SMTP_PORT")
    email_username: str = Field(default="", env="EMAIL_USERNAME")
    email_password: str = Field(default="", env="EMAIL_PASSWORD")
    email_from: str = Field(default="", env="EMAIL_FROM")
    email_to: str = Field(default="", env="EMAIL_TO")
    
    # Application
    app_host: str = Field(default="0.0.0.0", env="APP_HOST")
    app_port: int = Field(default=8000, env="APP_PORT")
    app_debug: bool = Field(default=False, env="APP_DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Task Configuration
    batch_size: int = Field(default=10, env="BATCH_SIZE")
    batch_interval_seconds: int = Field(default=60, env="BATCH_INTERVAL_SECONDS")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    
    class Config:
        env_file = ".env"
        
    @property
    def claude_api_keys_list(self) -> List[str]:
        return [key.strip() for key in self.claude_api_keys.split(",")]


settings = Settings()
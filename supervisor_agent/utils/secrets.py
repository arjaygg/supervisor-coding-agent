"""
Secure Secrets Management for Dev-Assist System

Provides a unified interface for managing secrets across different environments:
- Local development: Environment variables and local files
- Production: Google Secret Manager integration
- Testing: Mock secrets for testing

Follows security best practices with encryption and access logging.
"""

import base64
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Union

try:
    from google.api_core import exceptions as gcp_exceptions
    from google.cloud import secretmanager

    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    secretmanager = None

from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class SecretProvider(Enum):
    """Available secret providers."""

    ENVIRONMENT = "environment"
    FILE = "file"
    GOOGLE_SECRET_MANAGER = "google_secret_manager"
    MOCK = "mock"


@dataclass
class SecretMetadata:
    """Metadata for a secret."""

    name: str
    provider: SecretProvider
    created_at: datetime
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    encrypted: bool = False
    version: str = "latest"


class SecretNotFoundError(Exception):
    """Raised when a secret is not found."""

    pass


class SecretProviderError(Exception):
    """Raised when there's an error with the secret provider."""

    pass


class SecretsManager:
    """
    Unified secrets management system with multiple provider support.

    Provides secure access to secrets across different environments with
    audit logging and caching capabilities.
    """

    def __init__(
        self,
        provider: SecretProvider = SecretProvider.ENVIRONMENT,
        project_id: Optional[str] = None,
        cache_ttl: int = 300,  # 5 minutes
        audit_logging: bool = True,
    ):
        """
        Initialize secrets manager.

        Args:
            provider: Default secret provider to use
            project_id: GCP project ID for Google Secret Manager
            cache_ttl: Cache time-to-live in seconds
            audit_logging: Enable audit logging for secret access
        """
        self.provider = provider
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.cache_ttl = cache_ttl
        self.audit_logging = audit_logging

        # Internal cache for secrets
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._metadata: Dict[str, SecretMetadata] = {}

        # Initialize Google Secret Manager client if available
        self._gsm_client = None
        if provider == SecretProvider.GOOGLE_SECRET_MANAGER:
            self._init_google_secret_manager()

        logger.info(
            f"Secrets manager initialized with provider: {provider.value}"
        )

    def _init_google_secret_manager(self):
        """Initialize Google Secret Manager client."""
        if not GOOGLE_CLOUD_AVAILABLE:
            raise SecretProviderError(
                "Google Cloud SDK not available. Install google-cloud-secret-manager"
            )

        if not self.project_id:
            raise SecretProviderError(
                "GCP project ID required for Google Secret Manager"
            )

        try:
            self._gsm_client = secretmanager.SecretManagerServiceClient()
            logger.info("Google Secret Manager client initialized")
        except Exception as e:
            raise SecretProviderError(
                f"Failed to initialize Google Secret Manager: {e}"
            )

    def _is_cache_valid(self, secret_name: str) -> bool:
        """Check if cached secret is still valid."""
        if secret_name not in self._cache:
            return False

        cached_at = self._cache[secret_name].get("cached_at")
        if not cached_at:
            return False

        return datetime.now() < cached_at + timedelta(seconds=self.cache_ttl)

    def _cache_secret(self, secret_name: str, value: Any):
        """Cache a secret value."""
        self._cache[secret_name] = {
            "value": value,
            "cached_at": datetime.now(),
        }

    def _log_access(
        self, secret_name: str, provider: SecretProvider, success: bool
    ):
        """Log secret access for audit purposes."""
        if not self.audit_logging:
            return

        # Update metadata
        if secret_name in self._metadata:
            self._metadata[secret_name].last_accessed = datetime.now()
            self._metadata[secret_name].access_count += 1

        # Log access
        status = "SUCCESS" if success else "FAILED"
        logger.info(
            f"Secret access [{status}]: {secret_name} from {provider.value}",
            extra={
                "secret_name": secret_name,
                "provider": provider.value,
                "success": success,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def _get_from_environment(self, secret_name: str) -> Optional[str]:
        """Get secret from environment variables."""
        value = os.getenv(secret_name)
        if value is None:
            # Try with common prefixes
            for prefix in ["SECRET_", "CRED_", ""]:
                env_name = f"{prefix}{secret_name.upper()}"
                value = os.getenv(env_name)
                if value is not None:
                    break

        return value

    def _get_from_file(self, secret_name: str) -> Optional[str]:
        """Get secret from local file."""
        # Try multiple file locations
        file_paths = [
            Path(f"/run/secrets/{secret_name}"),  # Docker secrets
            Path(f"/var/secrets/{secret_name}"),  # Custom secrets dir
            Path(f".secrets/{secret_name}"),  # Local secrets dir
            Path(f"secrets/{secret_name}"),  # Project secrets dir
        ]

        for file_path in file_paths:
            if file_path.exists() and file_path.is_file():
                try:
                    return file_path.read_text().strip()
                except Exception as e:
                    logger.warning(
                        f"Failed to read secret file {file_path}: {e}"
                    )

        return None

    def _get_from_google_secret_manager(
        self, secret_name: str, version: str = "latest"
    ) -> Optional[str]:
        """Get secret from Google Secret Manager."""
        if not self._gsm_client:
            raise SecretProviderError(
                "Google Secret Manager client not initialized"
            )

        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            response = self._gsm_client.access_secret_version(
                request={"name": name}
            )
            return response.payload.data.decode("UTF-8")
        except gcp_exceptions.NotFound:
            return None
        except Exception as e:
            logger.error(f"Failed to get secret from GSM: {e}")
            raise SecretProviderError(f"Google Secret Manager error: {e}")

    def get_secret(
        self,
        secret_name: str,
        provider: Optional[SecretProvider] = None,
        version: str = "latest",
        default: Optional[str] = None,
        required: bool = True,
    ) -> Optional[str]:
        """
        Get a secret value from the configured provider.

        Args:
            secret_name: Name of the secret
            provider: Override default provider
            version: Secret version (for GSM)
            default: Default value if secret not found
            required: Raise exception if secret not found and no default

        Returns:
            Secret value or None if not found

        Raises:
            SecretNotFoundError: If secret not found and required=True
            SecretProviderError: If provider error occurs
        """
        provider = provider or self.provider

        # Check cache first
        if self._is_cache_valid(secret_name):
            self._log_access(secret_name, provider, True)
            return self._cache[secret_name]["value"]

        try:
            value = None

            # Get secret from provider
            if provider == SecretProvider.ENVIRONMENT:
                value = self._get_from_environment(secret_name)
            elif provider == SecretProvider.FILE:
                value = self._get_from_file(secret_name)
            elif provider == SecretProvider.GOOGLE_SECRET_MANAGER:
                value = self._get_from_google_secret_manager(
                    secret_name, version
                )
            elif provider == SecretProvider.MOCK:
                value = f"mock-{secret_name}"  # For testing
            else:
                raise SecretProviderError(f"Unknown provider: {provider}")

            # Handle not found
            if value is None:
                if default is not None:
                    value = default
                elif required:
                    self._log_access(secret_name, provider, False)
                    raise SecretNotFoundError(
                        f"Secret '{secret_name}' not found in {provider.value}"
                    )
                else:
                    self._log_access(secret_name, provider, False)
                    return None

            # Cache the value
            self._cache_secret(secret_name, value)

            # Update metadata
            if secret_name not in self._metadata:
                self._metadata[secret_name] = SecretMetadata(
                    name=secret_name,
                    provider=provider,
                    created_at=datetime.now(),
                    version=version,
                )

            self._log_access(secret_name, provider, True)
            return value

        except (SecretNotFoundError, SecretProviderError):
            raise
        except Exception as e:
            self._log_access(secret_name, provider, False)
            raise SecretProviderError(f"Unexpected error getting secret: {e}")

    def get_secrets_batch(
        self,
        secret_names: list[str],
        provider: Optional[SecretProvider] = None,
    ) -> Dict[str, Optional[str]]:
        """Get multiple secrets in batch."""
        results = {}
        for name in secret_names:
            try:
                results[name] = self.get_secret(name, provider, required=False)
            except SecretProviderError:
                results[name] = None

        return results

    def set_secret(
        self,
        secret_name: str,
        value: str,
        provider: Optional[SecretProvider] = None,
    ) -> bool:
        """
        Set a secret value (only supported for some providers).

        Args:
            secret_name: Name of the secret
            value: Secret value
            provider: Provider to use

        Returns:
            True if successful

        Raises:
            SecretProviderError: If provider doesn't support setting secrets
        """
        provider = provider or self.provider

        if provider == SecretProvider.GOOGLE_SECRET_MANAGER:
            return self._set_in_google_secret_manager(secret_name, value)
        elif provider == SecretProvider.FILE:
            return self._set_in_file(secret_name, value)
        else:
            raise SecretProviderError(
                f"Provider {provider.value} doesn't support setting secrets"
            )

    def _set_in_google_secret_manager(
        self, secret_name: str, value: str
    ) -> bool:
        """Set secret in Google Secret Manager."""
        if not self._gsm_client:
            raise SecretProviderError(
                "Google Secret Manager client not initialized"
            )

        try:
            # Create secret if it doesn't exist
            parent = f"projects/{self.project_id}"
            try:
                self._gsm_client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": secret_name,
                        "secret": {"replication": {"automatic": {}}},
                    }
                )
            except gcp_exceptions.AlreadyExists:
                pass  # Secret already exists

            # Add secret version
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
            self._gsm_client.add_secret_version(
                request={
                    "parent": secret_path,
                    "payload": {"data": value.encode("UTF-8")},
                }
            )

            # Clear cache
            if secret_name in self._cache:
                del self._cache[secret_name]

            logger.info(f"Secret '{secret_name}' set in Google Secret Manager")
            return True

        except Exception as e:
            logger.error(f"Failed to set secret in GSM: {e}")
            raise SecretProviderError(f"Google Secret Manager error: {e}")

    def _set_in_file(self, secret_name: str, value: str) -> bool:
        """Set secret in file."""
        secrets_dir = Path(".secrets")
        secrets_dir.mkdir(exist_ok=True)

        file_path = secrets_dir / secret_name
        try:
            file_path.write_text(value)
            file_path.chmod(0o600)  # Restrict permissions

            # Clear cache
            if secret_name in self._cache:
                del self._cache[secret_name]

            logger.info(f"Secret '{secret_name}' set in file")
            return True

        except Exception as e:
            logger.error(f"Failed to set secret in file: {e}")
            return False

    def list_secrets(self) -> Dict[str, SecretMetadata]:
        """List all known secrets with metadata."""
        return self._metadata.copy()

    def clear_cache(self, secret_name: Optional[str] = None):
        """Clear secret cache."""
        if secret_name:
            self._cache.pop(secret_name, None)
        else:
            self._cache.clear()

        logger.info(f"Secret cache cleared: {secret_name or 'all'}")

    def health_check(self) -> Dict[str, Any]:
        """Check health of secrets manager."""
        health = {
            "provider": self.provider.value,
            "cache_size": len(self._cache),
            "known_secrets": len(self._metadata),
            "healthy": True,
            "details": {},
        }

        try:
            if self.provider == SecretProvider.GOOGLE_SECRET_MANAGER:
                # Test GSM connectivity
                if self._gsm_client:
                    parent = f"projects/{self.project_id}"
                    self._gsm_client.list_secrets(
                        request={"parent": parent, "page_size": 1}
                    )
                    health["details"]["gsm_connection"] = "ok"
                else:
                    health["healthy"] = False
                    health["details"][
                        "gsm_connection"
                    ] = "client_not_initialized"

        except Exception as e:
            health["healthy"] = False
            health["details"]["error"] = str(e)

        return health


# Global secrets manager instance
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Get global secrets manager instance."""
    global _secrets_manager

    if _secrets_manager is None:
        # Determine provider from environment
        provider_name = os.getenv("SECRETS_PROVIDER", "environment").lower()

        try:
            provider = SecretProvider(provider_name)
        except ValueError:
            logger.warning(
                f"Unknown secrets provider '{provider_name}', using environment"
            )
            provider = SecretProvider.ENVIRONMENT

        project_id = os.getenv("GCP_PROJECT_ID")

        _secrets_manager = SecretsManager(
            provider=provider,
            project_id=project_id,
            cache_ttl=int(os.getenv("SECRETS_CACHE_TTL", "300")),
            audit_logging=os.getenv("SECRETS_AUDIT_LOGGING", "true").lower()
            == "true",
        )

    return _secrets_manager


def get_secret(
    secret_name: str, default: Optional[str] = None, required: bool = True
) -> Optional[str]:
    """Convenience function to get a secret."""
    return get_secrets_manager().get_secret(
        secret_name, default=default, required=required
    )


def get_database_url() -> str:
    """Get database URL from secrets."""
    return get_secret("DATABASE_URL", required=True)


def get_redis_url() -> str:
    """Get Redis URL from secrets."""
    return get_secret("REDIS_URL", required=True)


def get_claude_api_keys() -> list[str]:
    """Get Claude API keys from secrets."""
    keys_str = get_secret("CLAUDE_API_KEYS", required=True)
    return [key.strip() for key in keys_str.split(",") if key.strip()]


def get_notification_config() -> Dict[str, str]:
    """Get notification configuration from secrets."""
    return {
        "slack_token": get_secret(
            "SLACK_BOT_TOKEN", default="", required=False
        ),
        "slack_channel": get_secret(
            "SLACK_CHANNEL", default="#alerts", required=False
        ),
        "email_smtp_host": get_secret(
            "EMAIL_SMTP_HOST", default="", required=False
        ),
        "email_username": get_secret(
            "EMAIL_USERNAME", default="", required=False
        ),
        "email_password": get_secret(
            "EMAIL_PASSWORD", default="", required=False
        ),
    }

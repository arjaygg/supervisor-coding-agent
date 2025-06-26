"""
Provider Management Service
Responsible for registering, unregistering, and configuring providers.
"""
import logging
from typing import Dict, Any

from supervisor_agent.config import settings
from supervisor_agent.providers.provider_registry import ProviderRegistry
from supervisor_agent.providers.claude_cli_provider import ClaudeCliProvider
from supervisor_agent.providers.local_mock_provider import LocalMockProvider

logger = logging.getLogger(__name__)


class ProviderManager:
    """Handles provider registration and management."""
    
    def __init__(self, provider_registry: ProviderRegistry):
        self.provider_registry = provider_registry
    
    async def register_provider(
        self,
        provider_id: str,
        provider_type: str,
        config: Dict[str, Any]
    ) -> bool:
        """Register a new provider."""
        try:
            if provider_type == "claude_cli":
                provider = ClaudeCliProvider(provider_id, config)
            elif provider_type == "local_mock":
                provider = LocalMockProvider(provider_id, config)
            else:
                logger.error(f"Unknown provider type: {provider_type}")
                return False
                
            await self.provider_registry.register_provider(provider_id, provider)
            logger.info(f"Registered provider {provider_id} of type {provider_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering provider {provider_id}: {str(e)}")
            return False
    
    async def unregister_provider(self, provider_id: str) -> bool:
        """Unregister a provider."""
        try:
            await self.provider_registry.unregister_provider(provider_id)
            logger.info(f"Unregistered provider {provider_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error unregistering provider {provider_id}: {str(e)}")
            return False
    
    async def register_providers_from_config(self) -> None:
        """Register providers from configuration."""
        try:
            provider_configs = settings.get_provider_configs()
            
            if not provider_configs:
                # Fallback to legacy configuration
                await self._register_legacy_providers()
                return
                
            for config in provider_configs:
                provider_id = config.get("id")
                provider_type = config.get("type")
                provider_config = config.get("config", {})
                
                if not provider_id or not provider_type:
                    logger.warning(f"Invalid provider configuration: {config}")
                    continue
                    
                success = await self.register_provider(provider_id, provider_type, provider_config)
                if not success:
                    logger.warning(f"Failed to register provider {provider_id}")
                    
        except Exception as e:
            logger.error(f"Error registering providers from config: {str(e)}")
            # Fallback to legacy providers
            await self._register_legacy_providers()
    
    async def _register_legacy_providers(self) -> None:
        """Register providers using legacy configuration for backward compatibility."""
        try:
            # Register Claude CLI providers based on API keys
            claude_keys = settings.claude_api_keys_list
            if claude_keys:
                for i, api_key in enumerate(claude_keys):
                    provider_id = f"claude-cli-{i+1}"
                    config = {
                        "api_keys": [api_key],
                        "rate_limit_per_day": 1000,
                        "priority": i + 1
                    }
                    await self.register_provider(provider_id, "claude_cli", config)
                    
            # Always register local mock provider for testing
            mock_config = {
                "deterministic": True,
                "failure_rate": 0.01,
                "response_delay_seconds": 1.0
            }
            await self.register_provider("local-mock", "local_mock", mock_config)
            
            logger.info("Registered legacy providers for backward compatibility")
            
        except Exception as e:
            logger.error(f"Error registering legacy providers: {str(e)}")
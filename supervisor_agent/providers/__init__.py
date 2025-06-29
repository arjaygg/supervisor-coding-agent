"""
Provider abstraction layer for multi-provider AI coordination.

This module provides the foundational interfaces and utilities for integrating
multiple AI providers with intelligent task distribution and optimization.
"""

from .base_provider import (AIProvider, CostEstimate, ProviderCapabilities,
                            ProviderError, ProviderHealth, ProviderResponse,
                            ProviderUnavailableError, QuotaExceededError,
                            RateLimitError)
from .claude_cli_provider import ClaudeCliProvider
from .local_mock_provider import LocalMockProvider
from .provider_registry import (LoadBalancingStrategy, ProviderConfig,
                                ProviderFactory, ProviderRegistry)

__all__ = [
    "AIProvider",
    "ProviderCapabilities",
    "ProviderHealth",
    "ProviderResponse",
    "CostEstimate",
    "ProviderError",
    "ProviderUnavailableError",
    "QuotaExceededError",
    "RateLimitError",
    "ProviderRegistry",
    "ProviderFactory",
    "ProviderConfig",
    "LoadBalancingStrategy",
    "ClaudeCliProvider",
    "LocalMockProvider",
]

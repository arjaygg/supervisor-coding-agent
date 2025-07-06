"""
Base provider interface for AI provider abstraction.

This module defines the abstract base class and supporting types for AI providers,
enabling consistent integration across different AI services while maintaining
flexibility for provider-specific implementations.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class ProviderType(str, Enum):
    """Types of AI providers supported by the system."""

    CLAUDE_CLI = "claude_cli"
    LOCAL_MOCK = "local_mock"
    OPENAI = "openai"
    ANTHROPIC_API = "anthropic_api"
    CUSTOM = "custom"


class ProviderStatus(str, Enum):
    """Current status of a provider."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class TaskCapability(str, Enum):
    """Capabilities that providers can support."""

    CODE_REVIEW = "code_review"
    BUG_FIX = "bug_fix"
    FEATURE_DEVELOPMENT = "feature_development"
    CODE_ANALYSIS = "code_analysis"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    SECURITY_ANALYSIS = "security_analysis"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    GENERAL_CODING = "general_coding"


@dataclass
class ProviderCapabilities:
    """Defines what capabilities a provider supports."""

    supported_tasks: List[TaskCapability] = field(default_factory=list)
    max_tokens_per_request: int = 4000
    supports_batching: bool = True
    supports_streaming: bool = False
    supports_function_calling: bool = False
    max_concurrent_requests: int = 10
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    rate_limit_per_day: int = 10000

    def supports_task(self, task_type: Union[str, TaskCapability]) -> bool:
        """Check if provider supports a specific task type."""
        if isinstance(task_type, str):
            try:
                task_type = TaskCapability(task_type)
            except ValueError:
                return False
        return task_type in self.supported_tasks

    def can_handle_request_size(self, estimated_tokens: int) -> bool:
        """Check if provider can handle request of given size."""
        return estimated_tokens <= self.max_tokens_per_request


@dataclass
class ProviderHealth:
    """Health status and metrics for a provider."""

    status: ProviderStatus
    response_time_ms: float
    success_rate: float
    error_count: int
    last_error: Optional[str] = None
    last_check_time: datetime = field(default_factory=datetime.now)
    quota_remaining: Optional[int] = None
    quota_reset_time: Optional[datetime] = None

    @property
    def is_healthy(self) -> bool:
        """Check if provider is in a healthy state."""
        return (
            self.status == ProviderStatus.ACTIVE
            and self.success_rate >= 0.8
            and self.response_time_ms < 30000  # 30 seconds
        )

    @property
    def is_available(self) -> bool:
        """Check if provider is available for new requests."""
        return self.status in [ProviderStatus.ACTIVE, ProviderStatus.DEGRADED]


@dataclass
class CostEstimate:
    """Cost estimation for a provider request."""

    estimated_tokens: int
    cost_per_token: float
    estimated_cost_usd: float
    currency: str = "USD"
    model_used: Optional[str] = None

    @classmethod
    def from_tokens(
        cls, tokens: int, cost_per_token: float, model: str = None
    ) -> "CostEstimate":
        """Create cost estimate from token count."""
        return cls(
            estimated_tokens=tokens,
            cost_per_token=cost_per_token,
            estimated_cost_usd=tokens * cost_per_token,
            model_used=model,
        )


@dataclass
class ProviderResponse:
    """Response from a provider execution."""

    success: bool
    result: Any
    provider_id: str
    execution_time_ms: int
    tokens_used: int = 0
    cost_usd: float = 0.0
    model_used: Optional[str] = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def was_successful(self) -> bool:
        """Check if the response was successful."""
        return self.success and self.error_message is None


class ProviderError(Exception):
    """Base exception for provider-related errors."""

    def __init__(self, message: str, provider_id: str = None, error_code: str = None):
        self.provider_id = provider_id
        self.error_code = error_code
        super().__init__(message)


class ProviderUnavailableError(ProviderError):
    """Raised when a provider is temporarily unavailable."""

    pass


class QuotaExceededError(ProviderError):
    """Raised when provider quota is exceeded."""

    def __init__(
        self,
        message: str,
        provider_id: str = None,
        quota_reset_time: datetime = None,
    ):
        self.quota_reset_time = quota_reset_time
        super().__init__(message, provider_id, "QUOTA_EXCEEDED")


class RateLimitError(ProviderError):
    """Raised when provider rate limit is hit."""

    def __init__(
        self,
        message: str,
        provider_id: str = None,
        retry_after_seconds: int = None,
    ):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message, provider_id, "RATE_LIMITED")


@dataclass
class Task:
    """Represents a task to be executed by a provider."""

    id: Union[str, int]
    type: str
    payload: Dict[str, Any]
    priority: int = 5
    status: str = "pending"
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary format."""
        return {
            "id": self.id,
            "type": self.type,
            "payload": self.payload,
            "priority": self.priority,
            "status": self.status,
            "context": self.context,
        }


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    This class defines the interface that all AI providers must implement,
    ensuring consistent behavior across different provider implementations.
    """

    def __init__(self, provider_id: str, config: Dict[str, Any]):
        self.provider_id = provider_id
        self.config = config
        self._initialized = False
        self._health_cache: Optional[ProviderHealth] = None
        self._health_cache_time: Optional[datetime] = None

    @property
    def is_initialized(self) -> bool:
        """Check if provider has been initialized."""
        return self._initialized

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider with its configuration."""
        pass

    @abstractmethod
    async def execute_task(
        self, task: Task, context: Dict[str, Any] = None
    ) -> ProviderResponse:
        """
        Execute a single task using this provider.

        Args:
            task: The task to execute
            context: Additional context for task execution

        Returns:
            ProviderResponse containing the execution result

        Raises:
            ProviderError: If execution fails
        """
        pass

    @abstractmethod
    async def execute_batch(
        self, tasks: List[Task], context: Dict[str, Any] = None
    ) -> List[ProviderResponse]:
        """
        Execute multiple tasks as a batch.

        Args:
            tasks: List of tasks to execute
            context: Additional context for batch execution

        Returns:
            List of ProviderResponse objects

        Raises:
            ProviderError: If batch execution fails
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """
        Get the capabilities of this provider.

        Returns:
            ProviderCapabilities describing what this provider can do
        """
        pass

    @abstractmethod
    async def get_health_status(self, use_cache: bool = True) -> ProviderHealth:
        """
        Get the current health status of the provider.

        Args:
            use_cache: Whether to use cached health data if available

        Returns:
            ProviderHealth containing current status and metrics
        """
        pass

    @abstractmethod
    def estimate_cost(self, task: Task) -> CostEstimate:
        """
        Estimate the cost of executing a task.

        Args:
            task: The task to estimate cost for

        Returns:
            CostEstimate with projected costs
        """
        pass

    async def can_execute_task(self, task: Task) -> bool:
        """
        Check if this provider can execute the given task.

        Args:
            task: The task to check

        Returns:
            True if the provider can handle this task
        """
        capabilities = self.get_capabilities()

        # Check if provider supports this task type
        if not capabilities.supports_task(task.type):
            return False

        # Check if provider is healthy
        health = await self.get_health_status()
        if not health.is_available:
            return False

        # Estimate tokens and check if provider can handle the request size
        cost_estimate = self.estimate_cost(task)
        if not capabilities.can_handle_request_size(cost_estimate.estimated_tokens):
            return False

        return True

    async def validate_configuration(self) -> List[str]:
        """
        Validate the provider configuration.

        Returns:
            List of validation errors, empty if configuration is valid
        """
        errors = []

        if not self.provider_id:
            errors.append("Provider ID is required")

        if not isinstance(self.config, dict):
            errors.append("Configuration must be a dictionary")

        return errors

    async def shutdown(self) -> None:
        """
        Gracefully shutdown the provider.

        Override this method to implement provider-specific cleanup.
        """
        pass

    def _estimate_tokens_from_text(self, text: str) -> int:
        """
        Estimate token count from text (rough approximation).

        Args:
            text: The text to estimate tokens for

        Returns:
            Estimated token count
        """
        # Rough approximation: 1 token per 4 characters
        return max(len(text) // 4, 1)

    def _should_cache_health(self, cache_duration_seconds: int = 30) -> bool:
        """Check if health status should be cached."""
        if not self._health_cache or not self._health_cache_time:
            return False

        elapsed = (datetime.now() - self._health_cache_time).total_seconds()
        return elapsed < cache_duration_seconds

    def _cache_health(self, health: ProviderHealth) -> None:
        """Cache health status."""
        self._health_cache = health
        self._health_cache_time = datetime.now()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(id={self.provider_id})"

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id='{self.provider_id}', config={self.config})"
        )

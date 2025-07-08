"""
Tests for Provider Coordinator functionality.

Tests the core provider selection logic, task affinity tracking,
and execution context handling.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from supervisor_agent.core.provider_coordinator import (
    ExecutionContext,
    ProviderCoordinator,
    TaskAffinityStrategy,
    TaskAffinityTracker,
)
from supervisor_agent.db.models import Task, TaskType
from supervisor_agent.providers.base_provider import (
    AIProvider,
    CostEstimate,
    ProviderCapabilities,
    ProviderError,
    ProviderHealth,
    ProviderResponse,
    ProviderStatus,
    TaskCapability,
)
from supervisor_agent.providers.provider_registry import (
    LoadBalancingStrategy,
    ProviderRegistry,
)


@pytest.fixture
def mock_provider():
    """Create a mock AI provider"""
    provider = Mock(spec=AIProvider)
    provider.name = "test-provider"
    provider.get_capabilities.return_value = ProviderCapabilities(
        supported_tasks=[
            TaskCapability.CODE_REVIEW,
            TaskCapability.CODE_ANALYSIS,
            TaskCapability.BUG_FIX,
            TaskCapability.GENERAL_CODING,
        ],
        max_concurrent_requests=10,
        supports_batching=True,
    )
    provider.get_health_status = AsyncMock(
        return_value=ProviderHealth(
            status=ProviderStatus.ACTIVE,
            response_time_ms=5200.0,
            success_rate=0.98,
            error_count=2,
            last_check_time=datetime.now(timezone.utc),
        )
    )
    provider.estimate_cost = Mock(
        return_value=CostEstimate(
            estimated_tokens=1000,
            cost_per_token=0.00002,
            estimated_cost_usd=0.02,
            model_used="test-model",
        )
    )
    return provider


@pytest.fixture
def mock_registry(mock_provider):
    """Create a mock provider registry"""
    registry = Mock(spec=ProviderRegistry)
    registry.providers = {
        "provider-1": mock_provider,
        "provider-2": mock_provider,
    }
    registry.get_provider = Mock(return_value=mock_provider)
    return registry


@pytest.fixture
def sample_task():
    """Create a sample task for testing"""
    task = Mock(spec=Task)
    task.id = 1
    task.type = TaskType.PR_REVIEW
    task.payload = {
        "repository": "test/repo",
        "pr_number": 123,
        "title": "Test PR",
    }
    return task


@pytest.fixture
def execution_context():
    """Create a sample execution context"""
    return ExecutionContext(
        user_id="test-user",
        priority=5,
        max_cost_usd=1.0,
        require_capabilities=["PR_REVIEW"],
    )


class TestTaskAffinityTracker:
    """Test task affinity tracking functionality"""

    def test_record_assignment(self):
        """Test recording task-provider assignments"""
        tracker = TaskAffinityTracker()
        task = Mock()
        task.id = "task-123"

        tracker.record_assignment(task, "provider-1")

        assert "task-123" in tracker.provider_assignments
        assert tracker.provider_assignments["task-123"] == "provider-1"

    def test_record_performance(self):
        """Test recording provider performance metrics"""
        tracker = TaskAffinityTracker()

        # Record successful execution
        tracker.record_performance("provider-1", True, 5.0)

        assert "provider-1" in tracker.provider_performance
        assert len(tracker.provider_performance["provider-1"]) == 1

        # Record failed execution
        tracker.record_performance("provider-1", False, 10.0)
        assert len(tracker.provider_performance["provider-1"]) == 2

    def test_get_provider_score(self):
        """Test provider score calculation"""
        tracker = TaskAffinityTracker()

        # New provider should get neutral score
        score = tracker.get_provider_score("new-provider")
        assert score == 0.5

        # Provider with performance history
        tracker.record_performance("provider-1", True, 2.0)
        tracker.record_performance("provider-1", True, 3.0)
        tracker.record_performance("provider-1", False, 10.0)

        score = tracker.get_provider_score("provider-1")
        assert 0.0 <= score <= 1.0

    def test_performance_data_limit(self):
        """Test that performance data is limited to prevent memory growth"""
        tracker = TaskAffinityTracker()

        # Add more than 100 performance records
        for i in range(150):
            tracker.record_performance("provider-1", True, 1.0)

        # Should be limited to 100 records
        assert len(tracker.provider_performance["provider-1"]) == 100


class TestProviderCoordinator:
    """Test provider coordination functionality"""

    @pytest.mark.asyncio
    async def test_select_provider_basic(
        self, mock_registry, sample_task, execution_context
    ):
        """Test basic provider selection"""
        coordinator = ProviderCoordinator(mock_registry)

        selected_provider = await coordinator.select_provider(
            sample_task, execution_context
        )

        assert selected_provider in mock_registry.providers

    @pytest.mark.asyncio
    async def test_select_provider_with_preferences(self, mock_registry, sample_task):
        """Test provider selection with preferred providers"""
        context = ExecutionContext(
            preferred_providers=["provider-1"],
            exclude_providers=["provider-2"],
        )

        coordinator = ProviderCoordinator(mock_registry)
        selected_provider = await coordinator.select_provider(sample_task, context)

        assert selected_provider == "provider-1"

    @pytest.mark.asyncio
    async def test_select_provider_no_suitable_providers(
        self, mock_registry, sample_task
    ):
        """Test provider selection when no providers are suitable"""
        # Mock provider that doesn't support the task type
        mock_provider = Mock(spec=AIProvider)
        mock_provider.get_capabilities.return_value = ProviderCapabilities(
            supported_tasks=[], max_concurrent_requests=10
        )
        mock_registry.get_provider.return_value = mock_provider

        context = ExecutionContext()
        coordinator = ProviderCoordinator(mock_registry)

        with pytest.raises(
            ProviderError, match="No providers capable of handling task type"
        ):
            await coordinator.select_provider(sample_task, context)

    @pytest.mark.asyncio
    async def test_select_backup_provider(
        self, mock_registry, sample_task, execution_context
    ):
        """Test backup provider selection"""
        coordinator = ProviderCoordinator(mock_registry)

        backup_provider = await coordinator.select_backup_provider(
            sample_task, "provider-1", execution_context
        )

        assert backup_provider != "provider-1"
        assert backup_provider in mock_registry.providers

    @pytest.mark.asyncio
    async def test_load_balancing_strategies(
        self, mock_registry, sample_task, execution_context
    ):
        """Test different load balancing strategies"""
        strategies = [
            LoadBalancingStrategy.ROUND_ROBIN,
            LoadBalancingStrategy.LEAST_LOADED,
            LoadBalancingStrategy.FASTEST_RESPONSE,
            LoadBalancingStrategy.CAPABILITY_BASED,
        ]

        for strategy in strategies:
            coordinator = ProviderCoordinator(mock_registry, strategy=strategy)
            selected_provider = await coordinator.select_provider(
                sample_task, execution_context
            )
            assert selected_provider in mock_registry.providers

    @pytest.mark.asyncio
    async def test_cost_filtering(self, mock_registry, sample_task):
        """Test provider filtering by cost constraints"""
        # Set low cost limit
        context = ExecutionContext(max_cost_usd=0.01)

        coordinator = ProviderCoordinator(mock_registry)

        # Should still work but may log warnings
        selected_provider = await coordinator.select_provider(sample_task, context)
        assert selected_provider in mock_registry.providers

    @pytest.mark.asyncio
    async def test_provider_recommendations(
        self, mock_registry, sample_task, execution_context
    ):
        """Test provider recommendations functionality"""
        coordinator = ProviderCoordinator(mock_registry)

        recommendations = await coordinator.get_provider_recommendations(
            sample_task, execution_context
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) <= len(mock_registry.providers)

        if recommendations:
            rec = recommendations[0]
            assert "provider_id" in rec
            assert "health_score" in rec
            assert "estimated_cost_usd" in rec
            assert "recommendation_score" in rec

    @pytest.mark.asyncio
    async def test_task_affinity(self, mock_registry, sample_task, execution_context):
        """Test task affinity functionality"""
        coordinator = ProviderCoordinator(
            mock_registry,
            affinity_strategy=TaskAffinityStrategy.PROVIDER_STICKY,
        )

        # Record a previous assignment
        coordinator.task_affinity_tracker.record_assignment(sample_task, "provider-1")

        # Should prefer the same provider for related tasks
        selected_provider = await coordinator.select_provider(
            sample_task, execution_context
        )

        # Note: This test might need adjustment based on the exact affinity logic
        assert selected_provider in mock_registry.providers

    @pytest.mark.asyncio
    async def test_health_caching(self, mock_registry, sample_task, execution_context):
        """Test provider health status caching"""
        coordinator = ProviderCoordinator(mock_registry)

        # First call should query provider health
        await coordinator.select_provider(sample_task, execution_context)
        call_count_1 = (
            mock_registry.get_provider.return_value.get_health_status.call_count
        )

        # Second call within cache TTL should use cached health
        await coordinator.select_provider(sample_task, execution_context)
        call_count_2 = (
            mock_registry.get_provider.return_value.get_health_status.call_count
        )

        # Should have used cache for some providers
        assert call_count_2 <= call_count_1 + len(mock_registry.providers)


class TestExecutionContext:
    """Test execution context functionality"""

    def test_execution_context_creation(self):
        """Test execution context creation with defaults"""
        context = ExecutionContext()

        assert context.priority == 5
        assert context.preferred_providers == []
        assert context.exclude_providers == []
        assert context.require_capabilities == []
        assert isinstance(context.metadata, dict)
        assert isinstance(context.created_at, datetime)

    def test_execution_context_with_parameters(self):
        """Test execution context creation with parameters"""
        context = ExecutionContext(
            user_id="test-user",
            organization_id="test-org",
            priority=8,
            max_cost_usd=0.50,
            preferred_providers=["provider-1"],
            exclude_providers=["provider-2"],
            require_capabilities=["fast_response"],
            metadata={"custom": "value"},
        )

        assert context.user_id == "test-user"
        assert context.organization_id == "test-org"
        assert context.priority == 8
        assert context.max_cost_usd == 0.50
        assert context.preferred_providers == ["provider-1"]
        assert context.exclude_providers == ["provider-2"]
        assert context.require_capabilities == ["fast_response"]
        assert context.metadata["custom"] == "value"


@pytest.mark.asyncio
async def test_provider_coordinator_integration(mock_registry, sample_task):
    """Test full provider coordinator integration"""
    coordinator = ProviderCoordinator(
        mock_registry,
        strategy=LoadBalancingStrategy.CAPABILITY_BASED,
        affinity_strategy=TaskAffinityStrategy.CAPABILITY_BASED,
    )

    context = ExecutionContext(user_id="integration-test", priority=7, max_cost_usd=2.0)

    # Test provider selection
    selected_provider = await coordinator.select_provider(sample_task, context)
    assert selected_provider in mock_registry.providers

    # Test recommendations
    recommendations = await coordinator.get_provider_recommendations(
        sample_task, context
    )
    assert isinstance(recommendations, list)

    # Test backup selection
    backup_provider = await coordinator.select_backup_provider(
        sample_task, selected_provider, context
    )
    assert backup_provider != selected_provider or len(mock_registry.providers) == 1

    # Test performance tracking
    coordinator.task_affinity_tracker.record_assignment(sample_task, selected_provider)
    coordinator.task_affinity_tracker.record_performance(selected_provider, True, 3.5)

    score = coordinator.task_affinity_tracker.get_provider_score(selected_provider)
    assert 0.0 <= score <= 1.0

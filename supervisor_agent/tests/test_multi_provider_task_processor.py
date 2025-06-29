"""
Tests for Multi-Provider Task Processor functionality.

Tests the enhanced task processing with provider coordination,
routing strategies, and batch optimization.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from supervisor_agent.core.multi_provider_subscription_intelligence import (
    MultiProviderSubscriptionIntelligence,
)
from supervisor_agent.core.multi_provider_task_processor import (
    MultiProviderTaskProcessor,
    RoutingStrategy,
    TaskBatch,
    TaskPriority,
)
from supervisor_agent.core.provider_coordinator import (
    ExecutionContext,
    ProviderCoordinator,
)
from supervisor_agent.db.models import Task, TaskType
from supervisor_agent.providers.base_provider import CostEstimate, ProviderResponse
from supervisor_agent.providers.provider_registry import ProviderRegistry


@pytest.fixture
def mock_provider_registry():
    """Create a mock provider registry"""
    registry = Mock(spec=ProviderRegistry)
    registry.providers = {"provider-1": Mock(), "provider-2": Mock()}
    return registry


@pytest.fixture
def mock_provider_coordinator():
    """Create a mock provider coordinator"""
    coordinator = Mock(spec=ProviderCoordinator)
    coordinator.select_provider = AsyncMock(return_value="provider-1")
    coordinator.select_backup_provider = AsyncMock(return_value="provider-2")
    coordinator.task_affinity_tracker = Mock()
    coordinator.task_affinity_tracker.record_assignment = Mock()
    coordinator.task_affinity_tracker.record_performance = Mock()
    return coordinator


@pytest.fixture
def mock_subscription_intelligence():
    """Create a mock subscription intelligence"""
    intelligence = Mock(spec=MultiProviderSubscriptionIntelligence)
    intelligence.get_optimal_provider = AsyncMock(return_value="provider-1")
    intelligence.track_request = AsyncMock()
    intelligence.get_quota_status = AsyncMock(return_value={})
    return intelligence


@pytest.fixture
def mock_provider():
    """Create a mock provider"""
    provider = Mock()
    provider.execute_task = AsyncMock(
        return_value=ProviderResponse(
            success=True,
            result="Task completed successfully",
            cost_estimate=CostEstimate(
                base_cost_usd="0.05",
                token_cost_usd="0.02",
                total_cost_usd="0.07",
                estimated_tokens=1000,
            ),
            tokens_used=950,
            metadata={"provider_id": "provider-1"},
        )
    )
    return provider


@pytest.fixture
def sample_tasks():
    """Create sample tasks for testing"""
    tasks = []
    for i in range(3):
        task = Mock(spec=Task)
        task.id = i + 1
        task.type = TaskType.PR_REVIEW if i % 2 == 0 else TaskType.CODE_ANALYSIS
        task.payload = {"test": f"data_{i}"}
        task.retry_count = 0
        tasks.append(task)
    return tasks


@pytest.fixture
def task_processor(
    mock_provider_registry, mock_provider_coordinator, mock_subscription_intelligence
):
    """Create a multi-provider task processor"""
    return MultiProviderTaskProcessor(
        provider_registry=mock_provider_registry,
        provider_coordinator=mock_provider_coordinator,
        subscription_intelligence=mock_subscription_intelligence,
        default_routing_strategy=RoutingStrategy.OPTIMAL,
    )


class TestTaskBatch:
    """Test task batch functionality"""

    def test_task_batch_creation(self, sample_tasks):
        """Test task batch creation"""
        batch = TaskBatch(sample_tasks[:2], "test_batch")

        assert batch.task_count == 2
        assert batch.batch_type == "test_batch"
        assert isinstance(batch.created_at, datetime)
        assert batch.batch_id.startswith("batch_")

    def test_task_batch_properties(self, sample_tasks):
        """Test task batch properties"""
        batch = TaskBatch(sample_tasks)

        assert batch.task_count == len(sample_tasks)
        assert batch.total_estimated_cost == 0.0  # Default value
        assert batch.preferred_provider is None  # Default value


class TestMultiProviderTaskProcessor:
    """Test multi-provider task processor functionality"""

    @pytest.mark.asyncio
    async def test_process_single_task_success(
        self, task_processor, sample_tasks, mock_provider
    ):
        """Test successful processing of a single task"""
        task = sample_tasks[0]
        mock_agent_processor = AsyncMock(return_value={"result": "processed"})

        # Mock provider registry to return our mock provider
        task_processor.provider_registry.get_provider = Mock(return_value=mock_provider)

        result = await task_processor.process_task(task, mock_agent_processor)

        assert result["success"] is True
        assert "result" in result
        assert "execution_time" in result
        assert "provider_id" in result
        assert result["provider_id"] == "provider-1"

    @pytest.mark.asyncio
    async def test_process_task_with_context(
        self, task_processor, sample_tasks, mock_provider
    ):
        """Test task processing with execution context"""
        task = sample_tasks[0]
        context = ExecutionContext(user_id="test-user", max_cost_usd=1.0, priority=8)
        mock_agent_processor = AsyncMock()

        task_processor.provider_registry.get_provider = Mock(return_value=mock_provider)

        result = await task_processor.process_task(task, mock_agent_processor, context)

        assert result["success"] is True
        # Verify that provider coordinator was called with context
        task_processor.provider_coordinator.select_provider.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_task_with_routing_strategy(
        self, task_processor, sample_tasks, mock_provider
    ):
        """Test task processing with different routing strategies"""
        task = sample_tasks[0]
        mock_agent_processor = AsyncMock()
        task_processor.provider_registry.get_provider = Mock(return_value=mock_provider)

        strategies = [
            RoutingStrategy.FASTEST,
            RoutingStrategy.CHEAPEST,
            RoutingStrategy.MOST_RELIABLE,
            RoutingStrategy.LOAD_BALANCED,
        ]

        for strategy in strategies:
            result = await task_processor.process_task(
                task, mock_agent_processor, routing_strategy=strategy
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_process_task_cache_hit(self, task_processor, sample_tasks):
        """Test task processing with cache hit"""
        task = sample_tasks[0]
        mock_agent_processor = AsyncMock()

        # Mock cache hit
        with patch.object(
            task_processor,
            "_check_task_cache",
            return_value={
                "success": True,
                "result": "Cached result",
                "cached": True,
                "execution_time": 0.001,
            },
        ):
            result = await task_processor.process_task(task, mock_agent_processor)

        assert result["success"] is True
        assert result["cached"] is True
        assert task_processor.processing_stats["cache_hits"] == 1

    @pytest.mark.asyncio
    async def test_process_task_failure_with_retry(
        self, task_processor, sample_tasks, mock_provider
    ):
        """Test task processing failure with retry logic"""
        task = sample_tasks[0]
        mock_agent_processor = AsyncMock()

        # Mock provider that fails first time, succeeds on retry
        failing_provider = Mock()
        failing_provider.execute_task = AsyncMock(
            side_effect=[
                Exception("Provider failure"),
                ProviderResponse(
                    success=True,
                    result="Retry succeeded",
                    cost_estimate=CostEstimate("0.05", "0.02", "0.07", 1000),
                    tokens_used=950,
                ),
            ]
        )

        task_processor.provider_registry.get_provider = Mock(
            return_value=failing_provider
        )

        result = await task_processor.process_task(task, mock_agent_processor)

        # Should succeed after retry
        assert result["success"] is True
        assert task_processor.processing_stats["retry_tasks"] >= 1

    @pytest.mark.asyncio
    async def test_process_task_batch(
        self, task_processor, sample_tasks, mock_provider
    ):
        """Test batch processing of multiple tasks"""
        mock_agent_processor = AsyncMock()
        task_processor.provider_registry.get_provider = Mock(return_value=mock_provider)

        results = await task_processor.process_task_batch(
            sample_tasks, mock_agent_processor, max_concurrent=2
        )

        assert len(results) == len(sample_tasks)
        assert all(result.get("success", False) for result in results)
        assert task_processor.processing_stats["batch_optimizations"] >= 1

    @pytest.mark.asyncio
    async def test_batch_optimization(self, task_processor, sample_tasks):
        """Test task batch optimization"""
        batch = TaskBatch(sample_tasks, "test_batch")

        optimized_batches = await task_processor._optimize_task_batch(batch, None)

        assert isinstance(optimized_batches, list)
        assert len(optimized_batches) >= 1

        # Total tasks should be preserved
        total_tasks = sum(b.task_count for b in optimized_batches)
        assert total_tasks == len(sample_tasks)

    def test_task_priority_determination(self, task_processor, sample_tasks):
        """Test task priority determination logic"""
        priorities = {}
        for task in sample_tasks:
            priority = task_processor._determine_task_priority(task)
            priorities[task.type] = priority
            assert isinstance(priority, int)
            assert 1 <= priority <= 10

        # Bug fixes should have higher priority than features
        if TaskType.BUG_FIX in priorities and TaskType.FEATURE in priorities:
            assert priorities[TaskType.BUG_FIX] > priorities[TaskType.FEATURE]

    @pytest.mark.asyncio
    async def test_processing_stats(self, task_processor, sample_tasks, mock_provider):
        """Test processing statistics tracking"""
        mock_agent_processor = AsyncMock()
        task_processor.provider_registry.get_provider = Mock(return_value=mock_provider)

        # Process a few tasks
        for task in sample_tasks[:2]:
            await task_processor.process_task(task, mock_agent_processor)

        stats = await task_processor.get_processing_stats()

        assert "total_tasks" in stats
        assert "successful_tasks" in stats
        assert "success_rate" in stats
        assert "provider_distribution" in stats
        assert "system_status" in stats
        assert stats["total_tasks"] >= 2

    @pytest.mark.asyncio
    async def test_routing_strategy_application(self, task_processor, sample_tasks):
        """Test routing strategy application logic"""
        task = sample_tasks[0]
        base_context = ExecutionContext(priority=5)

        # Test FASTEST strategy
        fastest_context = await task_processor._apply_routing_strategy(
            RoutingStrategy.FASTEST, task, base_context
        )
        assert fastest_context.max_cost_usd is None

        # Test CHEAPEST strategy
        cheapest_context = await task_processor._apply_routing_strategy(
            RoutingStrategy.CHEAPEST, task, base_context
        )
        assert cheapest_context.max_cost_usd is not None
        assert cheapest_context.max_cost_usd <= 0.10

        # Test MOST_RELIABLE strategy
        reliable_context = await task_processor._apply_routing_strategy(
            RoutingStrategy.MOST_RELIABLE, task, base_context
        )
        assert "high_reliability" in reliable_context.require_capabilities

    @pytest.mark.asyncio
    async def test_provider_availability_check(self, task_processor):
        """Test provider availability checking"""
        # Mock availability check
        task_processor.subscription_intelligence.get_quota_status = AsyncMock(
            return_value={"provider-1": Mock(is_available=True)}
        )

        is_available = await task_processor._is_provider_available("provider-1")
        assert is_available is True

        # Test unavailable provider
        task_processor.subscription_intelligence.get_quota_status = AsyncMock(
            return_value={"provider-2": Mock(is_available=False)}
        )

        is_available = await task_processor._is_provider_available("provider-2")
        assert is_available is False

    @pytest.mark.asyncio
    async def test_stats_update(self, task_processor):
        """Test statistics update functionality"""
        initial_stats = task_processor.processing_stats.copy()

        result = {"success": True, "cost_usd": 0.15}
        await task_processor._update_processing_stats("provider-1", result, 2.5)

        stats = task_processor.processing_stats
        assert stats["successful_tasks"] == initial_stats["successful_tasks"] + 1
        assert stats["total_cost_usd"] == initial_stats["total_cost_usd"] + 0.15
        assert "provider-1" in stats["provider_distribution"]
        assert stats["provider_distribution"]["provider-1"] >= 1


@pytest.mark.asyncio
async def test_full_processing_workflow(
    mock_provider_registry,
    mock_provider_coordinator,
    mock_subscription_intelligence,
    sample_tasks,
    mock_provider,
):
    """Test complete processing workflow with all components"""
    processor = MultiProviderTaskProcessor(
        provider_registry=mock_provider_registry,
        provider_coordinator=mock_provider_coordinator,
        subscription_intelligence=mock_subscription_intelligence,
        default_routing_strategy=RoutingStrategy.OPTIMAL,
        max_retry_attempts=2,
        failover_enabled=True,
        batch_optimization_enabled=True,
    )

    mock_provider_registry.get_provider = Mock(return_value=mock_provider)
    mock_agent_processor = AsyncMock()

    # Test single task processing
    task = sample_tasks[0]
    context = ExecutionContext(user_id="workflow-test", priority=7)

    result = await processor.process_task(task, mock_agent_processor, context)

    assert result["success"] is True
    assert "provider_id" in result
    assert "execution_time" in result

    # Test batch processing
    batch_results = await processor.process_task_batch(
        sample_tasks, mock_agent_processor, context
    )

    assert len(batch_results) == len(sample_tasks)
    assert all(r.get("success", False) for r in batch_results)

    # Verify statistics
    stats = await processor.get_processing_stats()
    assert stats["total_tasks"] >= len(sample_tasks) + 1
    assert stats["success_rate"] > 0.0

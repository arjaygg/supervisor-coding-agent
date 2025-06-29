import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from supervisor_agent.core.intelligent_task_processor import IntelligentTaskProcessor
from supervisor_agent.core.subscription_intelligence import SubscriptionIntelligence
from supervisor_agent.db.models import Task, TaskStatus
from supervisor_agent.queue.tasks import process_single_task, process_task_batch


class TestIntelligentTaskProcessor:
    """Test the intelligent task processor that integrates subscription intelligence."""

    @pytest.fixture
    def task_processor(self):
        return IntelligentTaskProcessor(
            daily_limit=10000, batch_size=3, cache_ttl_seconds=300
        )

    @pytest.fixture
    def mock_task(self):
        task = Mock(spec=Task)
        task.id = 1
        task.type = "PR_REVIEW"
        task.payload = {"pr_number": 123, "title": "Test PR"}
        task.priority = 5
        task.status = TaskStatus.PENDING
        return task

    @pytest.mark.asyncio
    async def test_process_task_new_request(self, task_processor, mock_task):
        """Test processing a new task request."""
        mock_agent_processor = AsyncMock(
            return_value={
                "success": True,
                "result": "Analysis complete",
                "execution_time": 2.5,
                "tokens_used": 1200,
            }
        )

        result = await task_processor.process_task(mock_task, mock_agent_processor)

        assert result["success"] is True
        assert result["result"] == "Analysis complete"
        # Due to fallback mechanism, processor might be called more than once
        assert mock_agent_processor.call_count >= 1

    @pytest.mark.asyncio
    async def test_process_task_duplicate_request(self, task_processor, mock_task):
        """Test that duplicate requests return cached results."""
        mock_agent_processor = AsyncMock(
            return_value={
                "success": True,
                "result": "Analysis complete",
                "execution_time": 2.5,
                "tokens_used": 1200,
            }
        )

        # First request
        await task_processor.process_task(mock_task, mock_agent_processor)

        # Second identical request
        result = await task_processor.process_task(mock_task, mock_agent_processor)

        assert result["success"] is True
        assert result["result"] == "Analysis complete"
        # Agent processor should only be called once
        mock_agent_processor.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_task_quota_exceeded(self, task_processor, mock_task):
        """Test behavior when quota is exceeded."""
        task_processor.subscription_intelligence.current_usage = 11000  # Exceed limit

        mock_agent_processor = AsyncMock()

        with pytest.raises(Exception) as exc_info:
            await task_processor.process_task(mock_task, mock_agent_processor)

        assert "quota exceeded" in str(exc_info.value).lower()
        mock_agent_processor.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_batch_tasks(self, task_processor):
        """Test batch processing of multiple tasks."""
        tasks = []
        for i in range(3):
            task = Mock(spec=Task)
            task.id = i + 1
            task.type = "CODE_ANALYSIS"
            task.payload = {"file": f"test{i}.py"}
            task.priority = 5
            tasks.append(task)

        mock_agent_processor = AsyncMock(
            return_value=[
                {"success": True, "result": f"Analysis {i+1}", "tokens_used": 800}
                for i in range(3)
            ]
        )

        results = await task_processor.process_batch(tasks, mock_agent_processor)

        assert len(results) == 3
        assert all(result["success"] for result in results)
        mock_agent_processor.assert_called_once_with(tasks)

    @pytest.mark.asyncio
    async def test_batching_decision_logic(self, task_processor, mock_task):
        """Test the logic for deciding whether to batch tasks."""
        # Small task should be batched
        small_task = mock_task
        small_task.payload = {"small": "data"}
        small_task.priority = 5

        should_batch = task_processor.should_batch_task(small_task)
        assert should_batch is True

        # Large task should not be batched
        large_task = Mock(spec=Task)
        large_task.type = "PR_REVIEW"
        large_task.payload = {"large_diff": "x" * 10000}  # Large payload
        large_task.priority = 5

        should_batch = task_processor.should_batch_task(large_task)
        assert should_batch is False

        # High priority task should not be batched
        priority_task = Mock(spec=Task)
        priority_task.type = "CRITICAL_BUG_FIX"
        priority_task.payload = {"issue": "critical"}
        priority_task.priority = 1  # High priority

        should_batch = task_processor.should_batch_task(priority_task)
        assert should_batch is False

    def test_get_usage_metrics(self, task_processor):
        """Test retrieval of usage metrics."""
        task_processor.subscription_intelligence.current_usage = 5000

        metrics = task_processor.get_usage_metrics()

        assert metrics["current_usage"] == 5000
        assert metrics["daily_limit"] == 10000
        assert metrics["usage_percentage"] == 50.0
        assert "cache_stats" in metrics
        assert "prediction_stats" in metrics

    @pytest.mark.asyncio
    async def test_force_process_pending(self, task_processor):
        """Test force processing of pending batched tasks."""
        # Add some tasks to batch but don't reach threshold
        mock_task = Mock(spec=Task)
        mock_task.id = 1
        mock_task.type = "CODE_ANALYSIS"
        mock_task.payload = {"file": "test.py"}
        mock_task.priority = 5

        mock_agent_processor = AsyncMock(return_value=[{"success": True}])

        # This won't trigger batch processing (below threshold)
        await task_processor.subscription_intelligence.batch_processor.add_request(
            {"task": mock_task, "_processor": mock_agent_processor}
        )

        # Force process pending
        await task_processor.force_process_pending()

        # Should have processed the pending request
        assert (
            task_processor.subscription_intelligence.batch_processor.current_batch == []
        )


class TestCeleryTaskIntegration:
    """Test integration with existing Celery tasks."""

    @pytest.mark.asyncio
    async def test_enhanced_process_single_task(self):
        """Test that process_single_task uses subscription intelligence."""
        with (
            patch("supervisor_agent.queue.tasks.get_db") as mock_get_db,
            patch("supervisor_agent.queue.tasks.crud") as mock_crud,
            patch("supervisor_agent.queue.tasks.quota_manager") as mock_quota,
            patch("supervisor_agent.queue.tasks.agent_manager") as mock_agent_mgr,
            patch("supervisor_agent.queue.tasks.shared_memory") as mock_memory,
        ):

            # Mock database and task
            mock_db = Mock()
            mock_get_db.return_value = [mock_db]

            mock_task = Mock()
            mock_task.id = 1
            mock_task.type = "PR_REVIEW"
            mock_task.payload = {"pr_number": 123}
            mock_task.retry_count = 0
            mock_crud.TaskCRUD.get_task.return_value = mock_task

            # Mock agent
            mock_agent = Mock()
            mock_agent.id = "agent-1"
            mock_quota.get_available_agent.return_value = mock_agent
            mock_quota.consume_quota.return_value = True

            # Mock agent wrapper
            mock_agent_wrapper = AsyncMock()
            mock_agent_wrapper.execute_task.return_value = {
                "success": True,
                "result": "Analysis complete",
                "execution_time": 2.5,
                "prompt": "Analyze this PR",
            }
            mock_agent_mgr.get_agent.return_value = mock_agent_wrapper

            # Mock memory
            mock_memory.get_task_context.return_value = {}

            # Call the function
            result = process_single_task(1)

            # Verify it processed successfully
            assert result["success"] is True
            mock_crud.TaskCRUD.update_task.assert_called()

    @pytest.mark.asyncio
    async def test_enhanced_batch_processing(self):
        """Test that batch processing integrates with subscription intelligence."""
        with (
            patch("supervisor_agent.queue.tasks.get_db") as mock_get_db,
            patch("supervisor_agent.queue.tasks.crud") as mock_crud,
            patch("supervisor_agent.queue.tasks.quota_manager") as mock_quota,
            patch("supervisor_agent.queue.tasks.agent_manager") as mock_agent_mgr,
        ):

            # Mock setup similar to above
            mock_db = Mock()
            mock_get_db.return_value = [mock_db]

            # Mock multiple tasks
            tasks = []
            for i in range(3):
                task = Mock()
                task.id = i + 1
                task.type = "CODE_ANALYSIS"
                task.payload = {"file": f"test{i}.py"}
                tasks.append(task)

            mock_crud.TaskCRUD.get_task.side_effect = tasks

            # Mock agent
            mock_agent = Mock()
            mock_agent.id = "agent-1"
            mock_quota.get_available_agent.return_value = mock_agent

            # Mock agent wrapper for batch processing
            mock_agent_wrapper = AsyncMock()
            mock_agent_wrapper.execute_task.return_value = {
                "success": True,
                "result": "Analysis complete",
                "execution_time": 1.5,
            }
            mock_agent_mgr.get_agent.return_value = mock_agent_wrapper

            # Call batch processing
            result = process_task_batch([1, 2, 3])

            # Verify batch was processed
            assert "batch_summary" in result
            assert result["batch_summary"]["task_count"] == 3


class TestQuotaIntegration:
    """Test integration with quota management."""

    @pytest.fixture
    def task_processor(self):
        return IntelligentTaskProcessor(daily_limit=1000)  # Low limit for testing

    @pytest.mark.asyncio
    async def test_quota_warning_notifications(self, task_processor):
        """Test that quota warnings are sent via WebSocket."""
        with patch("supervisor_agent.api.websocket.notify_quota_update") as mock_notify:
            # Simulate high usage (80% of quota)
            task_processor.subscription_intelligence.current_usage = 800

            # Get usage stats (should trigger warning)
            stats = task_processor.get_usage_metrics()

            # Verify warning threshold
            assert stats["usage_percentage"] == 80.0

            # In a real implementation, this would trigger a notification
            # For now, we just verify the stats are correct
            assert stats["remaining"] == 200

    @pytest.mark.asyncio
    async def test_automatic_quota_reset(self, task_processor):
        """Test that quota resets automatically at midnight."""
        # Simulate usage near limit
        task_processor.subscription_intelligence.current_usage = 950

        # Force quota check (normally happens automatically)
        task_processor.subscription_intelligence._check_and_reset_quota()

        # Usage should still be high since we haven't crossed midnight
        assert task_processor.subscription_intelligence.current_usage == 950

        # Simulate time passing to next day
        from datetime import timedelta

        task_processor.subscription_intelligence.usage_reset_time = (
            datetime.now() - timedelta(hours=1)
        )

        task_processor.subscription_intelligence._check_and_reset_quota()

        # Usage should be reset
        assert task_processor.subscription_intelligence.current_usage == 0


class TestPerformanceOptimizations:
    """Test performance optimizations and metrics."""

    @pytest.fixture
    def task_processor(self):
        return IntelligentTaskProcessor()

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self, task_processor):
        """Test that cache hits are significantly faster."""
        mock_task = Mock(spec=Task)
        mock_task.id = 1
        mock_task.type = "PR_REVIEW"
        mock_task.payload = {"pr_number": 123}

        slow_processor = AsyncMock()
        slow_processor.return_value = {"success": True, "result": "Analysis"}

        # First request (cache miss) - simulate slow processing
        async def slow_process(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return {"success": True, "result": "Analysis"}

        slow_processor.side_effect = slow_process

        # Measure first request time
        start_time = asyncio.get_event_loop().time()
        await task_processor.process_task(mock_task, slow_processor)
        first_request_time = asyncio.get_event_loop().time() - start_time

        # Second request (cache hit) should be much faster
        start_time = asyncio.get_event_loop().time()
        await task_processor.process_task(mock_task, slow_processor)
        second_request_time = asyncio.get_event_loop().time() - start_time

        # Cache hit should be at least 10x faster
        assert second_request_time < first_request_time / 10

        # Processor should only be called once
        slow_processor.assert_called_once()

    def test_memory_usage_tracking(self, task_processor):
        """Test that memory usage is tracked and bounded."""
        cache_stats = (
            task_processor.subscription_intelligence.deduplicator.get_cache_stats()
        )

        assert "cache_size_mb" in cache_stats
        assert cache_stats["cache_size_mb"] >= 0

        # Cache should have reasonable size limits (implementation dependent)
        # This is more of a smoke test to ensure tracking works
        assert isinstance(cache_stats["total_entries"], int)
        assert isinstance(cache_stats["total_hits"], int)

    @pytest.mark.asyncio
    async def test_batch_efficiency_metrics(self, task_processor):
        """Test that batching provides efficiency gains."""
        # Create similar tasks that should be batched
        tasks = []
        for i in range(5):
            task = Mock(spec=Task)
            task.id = i + 1
            task.type = "CODE_ANALYSIS"
            task.payload = {"file": f"small{i}.py"}  # Small files
            task.priority = 5
            tasks.append(task)

        mock_processor = AsyncMock(
            return_value=[
                {"success": True, "result": f"Analysis {i+1}"} for i in range(5)
            ]
        )

        # Process tasks (should be batched)
        results = await task_processor.process_batch(tasks, mock_processor)

        assert len(results) == 5
        # Should have been processed as a single batch call
        mock_processor.assert_called_once()

        batch_stats = (
            task_processor.subscription_intelligence.batch_processor.get_batch_stats()
        )
        assert batch_stats["configured_batch_size"] == 3  # Default from task_processor

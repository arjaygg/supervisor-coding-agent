"""
Tests for Analytics System

Comprehensive test suite for analytics functionality including metrics collection,
processing, and real-time dashboard features.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from supervisor_agent.core.analytics_engine import AnalyticsEngine
from supervisor_agent.core.analytics_models import (
    AggregationType,
    AnalyticsQuery,
    Insight,
    MetricType,
    SystemMetrics,
    TaskMetrics,
    TimeRange,
    TrendPrediction,
    UserMetrics,
    WorkflowMetrics,
)
from supervisor_agent.core.metrics_collector import MetricsCollector
from supervisor_agent.db.models import Task, TaskStatus, TaskType


class TestMetricsCollector:
    """Test metrics collection functionality"""

    @pytest.fixture
    def metrics_collector(self):
        """Create metrics collector instance"""
        return MetricsCollector()

    @pytest.fixture
    def mock_task(self):
        """Mock task for testing"""
        task = Mock(spec=Task)
        task.id = 1
        task.type = TaskType.CODE_ANALYSIS
        task.status = TaskStatus.COMPLETED
        task.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        task.updated_at = datetime.now(timezone.utc)
        task.error_message = None
        return task

    @pytest.mark.asyncio
    async def test_collect_task_metrics_success(self, metrics_collector, mock_task):
        """Test successful task metrics collection"""

        with patch.object(metrics_collector, "session_factory") as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_task
            )
            mock_db.query.return_value.params.return_value.first.return_value = None

            metrics = await metrics_collector.collect_task_metrics(1)

            assert isinstance(metrics, TaskMetrics)
            assert metrics.task_id == 1
            assert metrics.task_type == "CODE_ANALYSIS"
            assert metrics.success is True
            assert metrics.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_collect_task_metrics_not_found(self, metrics_collector):
        """Test task metrics collection for non-existent task"""

        with patch.object(metrics_collector, "session_factory") as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            with pytest.raises(ValueError, match="Task 999 not found"):
                await metrics_collector.collect_task_metrics(999)

    @pytest.mark.asyncio
    async def test_collect_system_metrics(self, metrics_collector):
        """Test system metrics collection"""

        with patch("psutil.cpu_percent", return_value=45.5):
            with patch("psutil.virtual_memory") as mock_memory:
                mock_memory.return_value.percent = 62.3
                with patch("psutil.disk_usage") as mock_disk:
                    mock_disk.return_value.used = 50 * 1024**3  # 50GB
                    mock_disk.return_value.total = 100 * 1024**3  # 100GB

                    with patch.object(
                        metrics_collector, "session_factory"
                    ) as mock_session:
                        mock_db = Mock()
                        mock_session.return_value = mock_db
                        mock_db.query.return_value.filter.return_value.count.return_value = (
                            5
                        )
                        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
                            []
                        )

                        metrics = await metrics_collector.collect_system_metrics()

                        assert isinstance(metrics, SystemMetrics)
                        assert metrics.cpu_usage_percent == 45.5
                        assert metrics.memory_usage_percent == 62.3
                        assert metrics.disk_usage_percent == 50.0
                        assert metrics.active_tasks_count == 5

    @pytest.mark.asyncio
    async def test_store_metric(self, metrics_collector):
        """Test metric storage"""

        with patch.object(metrics_collector, "session_factory") as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db

            await metrics_collector.store_metric(
                MetricType.TASK_EXECUTION,
                150.5,
                labels={"task_type": "CODE_ANALYSIS"},
                metadata={"unit": "milliseconds"},
            )

            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_string_metric(self, metrics_collector):
        """Test storing string-valued metrics"""

        with patch.object(metrics_collector, "session_factory") as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db

            await metrics_collector.store_metric(
                MetricType.SYSTEM_PERFORMANCE,
                "healthy",
                labels={"component": "api"},
                metadata={"check_type": "health"},
            )

            mock_db.add.assert_called_once()
            # Verify string values are handled correctly
            call_args = mock_db.add.call_args[0][0]
            assert call_args.string_value == "healthy"
            assert call_args.value == 0.0  # Default for string values


class TestAnalyticsEngine:
    """Test analytics processing functionality"""

    @pytest.fixture
    def analytics_engine(self):
        """Create analytics engine instance"""
        return AnalyticsEngine()

    @pytest.fixture
    def sample_query(self):
        """Sample analytics query"""
        return AnalyticsQuery(
            metric_type=MetricType.TASK_EXECUTION,
            time_range=TimeRange.DAY,
            aggregation=AggregationType.COUNT,
        )

    @pytest.mark.asyncio
    async def test_process_metrics_with_cache_miss(
        self, analytics_engine, sample_query
    ):
        """Test metrics processing with cache miss"""

        with patch.object(analytics_engine, "session_factory") as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db

            # Mock cache miss
            mock_db.query.return_value.filter.return_value.first.return_value = None

            # Mock query execution
            with patch.object(
                analytics_engine, "_execute_query", new_callable=AsyncMock
            ) as mock_execute:
                mock_execute.return_value = []

                with patch.object(
                    analytics_engine, "_cache_result", new_callable=AsyncMock
                ):
                    result = await analytics_engine.process_metrics(sample_query)

                    assert result.cache_hit is False
                    assert result.total_points == 0
                    assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_process_metrics_with_cache_hit(self, analytics_engine, sample_query):
        """Test metrics processing with cache hit"""

        with patch.object(analytics_engine, "session_factory") as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db

            # Mock cache hit
            mock_cache = Mock()
            mock_cache.result_data = {
                "data": [
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "value": 42,
                        "labels": {},
                        "metadata": {},
                    }
                ],
                "total_points": 1,
            }
            mock_cache.hit_count = 1
            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_cache
            )

            result = await analytics_engine.process_metrics(sample_query)

            assert result.cache_hit is True
            assert result.total_points == 1

    @pytest.mark.asyncio
    async def test_generate_insights(self, analytics_engine):
        """Test insight generation"""

        with patch.object(
            analytics_engine, "process_metrics", new_callable=AsyncMock
        ) as mock_process:
            # Mock high error rate scenario
            mock_process.side_effect = [
                Mock(data=[Mock(value=15)]),  # 15 errors
                Mock(data=[Mock(value=100)]),  # 100 total tasks
                Mock(data=[Mock(value=85)]),  # 85% CPU usage
            ]

            insights = await analytics_engine.generate_insights(TimeRange.DAY)

            assert len(insights) >= 1
            assert any("High Error Rate" in insight.title for insight in insights)
            assert any("High CPU Usage" in insight.title for insight in insights)

    @pytest.mark.asyncio
    async def test_predict_trends_insufficient_data(self, analytics_engine):
        """Test trend prediction with insufficient data"""

        with patch.object(analytics_engine, "session_factory") as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
                []
            )

            prediction = await analytics_engine.predict_trends(
                MetricType.TASK_EXECUTION
            )

            assert prediction.confidence_score == 0.0
            assert prediction.trend_direction == "unknown"
            assert prediction.model_used == "insufficient_data"

    @pytest.mark.asyncio
    async def test_predict_trends_with_data(self, analytics_engine):
        """Test trend prediction with sufficient data"""

        # Create mock historical data with increasing trend
        base_time = datetime.now(timezone.utc) - timedelta(days=1)
        mock_data = []
        for i in range(20):
            mock_entry = Mock()
            mock_entry.timestamp = base_time + timedelta(hours=i)
            mock_entry.value = 10 + i * 2  # Increasing trend
            mock_data.append(mock_entry)

        with patch.object(analytics_engine, "session_factory") as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
                mock_data
            )

            prediction = await analytics_engine.predict_trends(
                MetricType.TASK_EXECUTION, 12
            )

            assert prediction.trend_direction == "increasing"
            assert len(prediction.predicted_values) == 12
            assert prediction.confidence_score > 0

    @pytest.mark.asyncio
    async def test_get_summary_analytics(self, analytics_engine):
        """Test summary analytics generation"""

        with patch.object(
            analytics_engine, "process_metrics", new_callable=AsyncMock
        ) as mock_process:
            # Mock summary data
            mock_process.side_effect = [
                Mock(data=[Mock(value=150)]),  # total tasks
                Mock(data=[Mock(value=140)]),  # successful tasks
                Mock(data=[Mock(value=1250)]),  # avg execution time
                Mock(data=[Mock(value=5)]),  # queue depth
                Mock(data=[Mock(value=25)]),  # CPU usage
                Mock(data=[Mock(value=12.50)]),  # cost
            ]

            summary = await analytics_engine.get_summary_analytics()

            assert summary.total_tasks == 150
            assert summary.successful_tasks == 140
            assert summary.failed_tasks == 10
            assert summary.system_health_score == 75.0  # 100 - 25 CPU


class TestAnalyticsIntegration:
    """Integration tests for analytics system"""

    @pytest.mark.asyncio
    async def test_metrics_collection_and_processing_flow(self):
        """Test complete flow from collection to processing"""

        collector = MetricsCollector()
        engine = AnalyticsEngine()

        # Mock database operations
        with patch.object(collector, "session_factory") as mock_collector_session:
            with patch.object(engine, "session_factory") as mock_engine_session:
                mock_db = Mock()
                mock_collector_session.return_value.__aenter__.return_value = mock_db
                mock_engine_session.return_value.__aenter__.return_value = mock_db

                # Test metric storage
                await collector.store_metric(
                    MetricType.TASK_EXECUTION,
                    150,
                    labels={"task_type": "CODE_ANALYSIS", "success": "True"},
                )

                # Mock query processing
                mock_db.query.return_value.filter.return_value.first.return_value = (
                    None  # Cache miss
                )
                mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
                    []
                )

                query = AnalyticsQuery(
                    metric_type=MetricType.TASK_EXECUTION,
                    time_range=TimeRange.HOUR,
                    aggregation=AggregationType.COUNT,
                )

                result = await engine.process_metrics(query)

                assert result is not None
                assert result.cache_hit is False

    @pytest.mark.asyncio
    async def test_real_time_metrics_simulation(self):
        """Test simulation of real-time metrics collection"""

        collector = MetricsCollector()

        with patch.object(collector, "session_factory") as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db

            # Simulate collecting metrics for multiple tasks
            task_ids = [1, 2, 3, 4, 5]

            for task_id in task_ids:
                # Mock task data
                mock_task = Mock()
                mock_task.id = task_id
                mock_task.type = TaskType.CODE_ANALYSIS
                mock_task.status = (
                    TaskStatus.COMPLETED if task_id <= 4 else TaskStatus.FAILED
                )
                mock_task.created_at = datetime.now(timezone.utc) - timedelta(
                    minutes=task_id
                )
                mock_task.updated_at = datetime.now(timezone.utc)
                mock_task.error_message = "Test error" if task_id == 5 else None

                mock_db.query.return_value.filter.return_value.first.return_value = (
                    mock_task
                )
                mock_db.query.return_value.params.return_value.first.return_value = None

                await collector.collect_and_store_task_metrics(task_id)

            # Verify all tasks were processed
            assert mock_db.add.call_count >= len(task_ids)

    @pytest.mark.asyncio
    async def test_analytics_error_handling(self):
        """Test error handling in analytics system"""

        engine = AnalyticsEngine()

        # Test with invalid query that should be handled gracefully
        invalid_query = AnalyticsQuery(
            metric_type=MetricType.TASK_EXECUTION,
            time_range=TimeRange.DAY,
            aggregation=AggregationType.COUNT,
            filters={"invalid_filter": "invalid_value"},
        )

        with patch.object(engine, "session_factory") as mock_session:
            mock_db = Mock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            # This should not raise an exception but handle gracefully
            try:
                result = await engine.process_metrics(invalid_query)
                assert result is not None
            except Exception as e:
                # If an exception occurs, it should be a handled analytics exception
                assert "analytics" in str(e).lower() or "query" in str(e).lower()


class TestAnalyticsModels:
    """Test analytics data models"""

    def test_metric_point_creation(self):
        """Test MetricPoint model creation"""
        from supervisor_agent.core.analytics_models import MetricPoint

        point = MetricPoint(
            timestamp=datetime.now(timezone.utc),
            value=42.5,
            labels={"component": "api"},
            metadata={"unit": "ms"},
        )

        assert point.value == 42.5
        assert point.labels["component"] == "api"
        assert point.metadata["unit"] == "ms"

    def test_analytics_query_validation(self):
        """Test AnalyticsQuery model validation"""

        # Valid query
        query = AnalyticsQuery(
            metric_type=MetricType.TASK_EXECUTION,
            time_range=TimeRange.DAY,
            aggregation=AggregationType.AVERAGE,
        )

        assert query.metric_type == MetricType.TASK_EXECUTION
        assert query.time_range == TimeRange.DAY
        assert query.aggregation == AggregationType.AVERAGE
        assert query.filters == {}
        assert query.group_by == []

    def test_insight_creation(self):
        """Test Insight model creation"""

        insight = Insight(
            title="High Error Rate",
            description="Error rate exceeds threshold",
            severity="warning",
            metric_type=MetricType.ERROR_RATE,
            value=15.5,
            threshold=10.0,
            recommendation="Review recent failed tasks",
        )

        assert insight.severity == "warning"
        assert insight.value == 15.5
        assert insight.threshold == 10.0

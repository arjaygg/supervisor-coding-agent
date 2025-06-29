"""
Analytics Engine

Processes metrics data and generates insights for the dashboard.
Implements analytics processing with caching and trend analysis.
"""

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func

from supervisor_agent.core.analytics_models import (
    AggregationType,
    AnalyticsCache,
    AnalyticsQuery,
    AnalyticsResult,
    AnalyticsSummary,
    Insight,
    MetricEntry,
    MetricPoint,
    MetricType,
    TimeRange,
    TrendPrediction,
)
from supervisor_agent.db.database import SessionLocal


class AnalyticsEngineInterface(ABC):
    """Abstract interface for analytics processing"""

    @abstractmethod
    async def process_metrics(self, query: AnalyticsQuery) -> AnalyticsResult:
        """Process metrics based on query parameters"""
        pass

    @abstractmethod
    async def generate_insights(self, timeframe: TimeRange) -> List[Insight]:
        """Generate actionable insights from metrics"""
        pass

    @abstractmethod
    async def predict_trends(
        self, metric_type: MetricType, prediction_hours: int = 24
    ) -> TrendPrediction:
        """Predict metric trends using historical data"""
        pass

    @abstractmethod
    async def get_summary_analytics(self) -> AnalyticsSummary:
        """Get high-level summary analytics"""
        pass


class AnalyticsEngine(AnalyticsEngineInterface):
    """Concrete implementation of analytics processing"""

    def __init__(self, cache_ttl_minutes: int = 15):
        self.session_factory = SessionLocal
        self.cache_ttl_minutes = cache_ttl_minutes

    def _generate_query_hash(self, query: AnalyticsQuery) -> str:
        """Generate unique hash for query caching"""
        query_str = json.dumps(query.model_dump(), sort_keys=True, default=str)
        return hashlib.md5(query_str.encode(), usedforsecurity=False).hexdigest()

    def _parse_time_range(self, time_range: TimeRange) -> timedelta:
        """Convert TimeRange enum to timedelta"""
        ranges = {
            TimeRange.HOUR: timedelta(hours=1),
            TimeRange.DAY: timedelta(days=1),
            TimeRange.WEEK: timedelta(days=7),
            TimeRange.MONTH: timedelta(days=30),
            TimeRange.QUARTER: timedelta(days=90),
            TimeRange.YEAR: timedelta(days=365),
        }
        return ranges.get(time_range, timedelta(days=1))

    async def process_metrics(self, query: AnalyticsQuery) -> AnalyticsResult:
        """Process metrics with caching support"""
        start_time = datetime.now(timezone.utc)
        query_hash = self._generate_query_hash(query)

        session = self.session_factory()
        try:
            # Check cache first
            cached_result = await self._get_cached_result(session, query_hash)
            if cached_result:
                return AnalyticsResult(
                    query=query,
                    data=cached_result["data"],
                    total_points=cached_result["total_points"],
                    processing_time_ms=int(
                        (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    ),
                    cache_hit=True,
                )

            # Process query
            data = await self._execute_query(session, query)

            # Cache result
            await self._cache_result(session, query_hash, query, data)

            processing_time = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )

            return AnalyticsResult(
                query=query,
                data=data,
                total_points=len(data),
                processing_time_ms=processing_time,
                cache_hit=False,
            )
        finally:
            session.close()

    async def _get_cached_result(self, session, query_hash: str) -> Optional[Dict]:
        """Retrieve cached analytics result"""
        cache_entry = (
            session.query(AnalyticsCache)
            .filter(
                AnalyticsCache.query_hash == query_hash,
                AnalyticsCache.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )

        if cache_entry:
            # Update hit count
            cache_entry.hit_count += 1
            session.commit()
            return cache_entry.result_data

        return None

    async def _cache_result(
        self, session, query_hash: str, query: AnalyticsQuery, data: List[MetricPoint]
    ):
        """Cache analytics result"""
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self.cache_ttl_minutes
        )

        # Convert data to serializable format
        serializable_data = [
            {
                "timestamp": point.timestamp.isoformat(),
                "value": point.value,
                "labels": point.labels,
                "metadata": point.metadata,
            }
            for point in data
        ]

        result_data = {"data": serializable_data, "total_points": len(data)}

        # Remove existing cache entry
        session.query(AnalyticsCache).filter(
            AnalyticsCache.query_hash == query_hash
        ).delete()

        # Create new cache entry
        cache_entry = AnalyticsCache(
            query_hash=query_hash,
            query_config=query.model_dump(),
            result_data=result_data,
            expires_at=expires_at,
        )

        session.add(cache_entry)
        session.commit()

    async def _execute_query(self, session, query: AnalyticsQuery) -> List[MetricPoint]:
        """Execute analytics query against database"""
        # Calculate time window
        time_delta = self._parse_time_range(query.time_range)
        start_time = datetime.now(timezone.utc) - time_delta

        # Build base query
        base_query = session.query(MetricEntry).filter(
            MetricEntry.metric_type == query.metric_type.value,
            MetricEntry.timestamp >= start_time,
        )

        # Apply filters
        for key, value in query.filters.items():
            if key == "labels":
                for label_key, label_value in value.items():
                    # For SQLite, use JSON_EXTRACT or simpler comparison
                    base_query = base_query.filter(
                        MetricEntry.labels.op("->>")(label_key) == label_value
                    )
            elif key == "value_range":
                if "min" in value:
                    base_query = base_query.filter(MetricEntry.value >= value["min"])
                if "max" in value:
                    base_query = base_query.filter(MetricEntry.value <= value["max"])

        # Apply aggregation
        if query.aggregation == AggregationType.COUNT:
            # Count aggregation
            if query.group_by:
                # Group by time intervals or labels
                grouped_data = self._apply_grouping(
                    base_query, query.group_by, query.aggregation
                )
                return grouped_data
            else:
                count = base_query.count()
                return [
                    MetricPoint(
                        timestamp=datetime.now(timezone.utc),
                        value=count,
                        labels={},
                        metadata={"aggregation": "count"},
                    )
                ]

        elif query.aggregation in [
            AggregationType.SUM,
            AggregationType.AVERAGE,
            AggregationType.MIN,
            AggregationType.MAX,
        ]:
            return await self._apply_numeric_aggregation(base_query, query)

        else:
            # Raw data (with limit)
            limit = query.limit or 1000
            entries = (
                base_query.order_by(MetricEntry.timestamp.desc()).limit(limit).all()
            )

            return [
                MetricPoint(
                    timestamp=entry.timestamp,
                    value=(
                        entry.value
                        if entry.string_value is None
                        else entry.string_value
                    ),
                    labels=entry.labels,
                    metadata=entry.metadata,
                )
                for entry in entries
            ]

    async def _apply_numeric_aggregation(
        self, base_query, query: AnalyticsQuery
    ) -> List[MetricPoint]:
        """Apply numeric aggregation functions"""
        if query.group_by:
            return self._apply_grouping(base_query, query.group_by, query.aggregation)

        # Single aggregated value
        if query.aggregation == AggregationType.SUM:
            result = base_query.with_entities(func.sum(MetricEntry.value)).scalar()
        elif query.aggregation == AggregationType.AVERAGE:
            result = base_query.with_entities(func.avg(MetricEntry.value)).scalar()
        elif query.aggregation == AggregationType.MIN:
            result = base_query.with_entities(func.min(MetricEntry.value)).scalar()
        elif query.aggregation == AggregationType.MAX:
            result = base_query.with_entities(func.max(MetricEntry.value)).scalar()
        else:
            result = 0

        return [
            MetricPoint(
                timestamp=datetime.now(timezone.utc),
                value=float(result) if result is not None else 0.0,
                labels={},
                metadata={"aggregation": query.aggregation.value},
            )
        ]

    def _apply_grouping(
        self, base_query, group_by: List[str], aggregation: AggregationType
    ) -> List[MetricPoint]:
        """Apply grouping to query results"""
        # This is a simplified implementation
        # In production, you'd use more sophisticated time-series grouping

        results = []
        entries = base_query.all()

        # Group by time intervals (simplified)
        if "time" in group_by:
            # Group by hour intervals
            grouped = {}
            for entry in entries:
                hour_key = entry.timestamp.replace(minute=0, second=0, microsecond=0)
                if hour_key not in grouped:
                    grouped[hour_key] = []
                grouped[hour_key].append(entry.value)

            for timestamp, values in grouped.items():
                if aggregation == AggregationType.SUM:
                    agg_value = sum(values)
                elif aggregation == AggregationType.AVERAGE:
                    agg_value = sum(values) / len(values)
                elif aggregation == AggregationType.COUNT:
                    agg_value = len(values)
                elif aggregation == AggregationType.MIN:
                    agg_value = min(values)
                elif aggregation == AggregationType.MAX:
                    agg_value = max(values)
                else:
                    agg_value = sum(values)

                results.append(
                    MetricPoint(
                        timestamp=timestamp,
                        value=agg_value,
                        labels={"group": "time"},
                        metadata={
                            "aggregation": aggregation.value,
                            "count": len(values),
                        },
                    )
                )

        return sorted(results, key=lambda x: x.timestamp)

    async def generate_insights(self, timeframe: TimeRange) -> List[Insight]:
        """Generate actionable insights from metrics"""
        insights = []

        session = self.session_factory()
        try:
            time_delta = self._parse_time_range(timeframe)
            start_time = datetime.now(timezone.utc) - time_delta

            # Insight 1: High error rate
            error_query = AnalyticsQuery(
                metric_type=MetricType.TASK_EXECUTION,
                time_range=timeframe,
                aggregation=AggregationType.COUNT,
                filters={"labels": {"success": "False"}},
            )

            total_query = AnalyticsQuery(
                metric_type=MetricType.TASK_EXECUTION,
                time_range=timeframe,
                aggregation=AggregationType.COUNT,
            )

            error_result = await self.process_metrics(error_query)
            total_result = await self.process_metrics(total_query)

            if total_result.data and total_result.data[0].value > 0:
                error_rate = (
                    error_result.data[0].value / total_result.data[0].value
                ) * 100

                if error_rate > 10:  # More than 10% error rate
                    insights.append(
                        Insight(
                            title="High Error Rate Detected",
                            description=f"Task error rate is {error_rate:.1f}% in the last {timeframe.value}",
                            severity="critical" if error_rate > 25 else "warning",
                            metric_type=MetricType.ERROR_RATE,
                            value=error_rate,
                            threshold=10,
                            recommendation="Review recent failed tasks and check for common error patterns",
                        )
                    )

            # Insight 2: System resource usage
            cpu_query = AnalyticsQuery(
                metric_type=MetricType.SYSTEM_PERFORMANCE,
                time_range=timeframe,
                aggregation=AggregationType.AVERAGE,
                filters={"labels": {"component": "cpu"}},
            )

            cpu_result = await self.process_metrics(cpu_query)
            if cpu_result.data and cpu_result.data[0].value > 80:
                insights.append(
                    Insight(
                        title="High CPU Usage",
                        description=f"Average CPU usage is {cpu_result.data[0].value:.1f}%",
                        severity=(
                            "warning" if cpu_result.data[0].value < 90 else "critical"
                        ),
                        metric_type=MetricType.SYSTEM_PERFORMANCE,
                        value=cpu_result.data[0].value,
                        threshold=80,
                        recommendation="Consider scaling up resources or optimizing task processing",
                    )
                )

            # Insight 3: Queue depth trends
            queue_query = AnalyticsQuery(
                metric_type=MetricType.SYSTEM_PERFORMANCE,
                time_range=timeframe,
                aggregation=AggregationType.AVERAGE,
                filters={"labels": {"component": "queue"}},
            )

            queue_result = await self.process_metrics(queue_query)
            if queue_result.data and queue_result.data[0].value > 50:
                insights.append(
                    Insight(
                        title="High Queue Depth",
                        description=f"Average queue depth is {queue_result.data[0].value:.0f} tasks",
                        severity="warning",
                        metric_type=MetricType.SYSTEM_PERFORMANCE,
                        value=queue_result.data[0].value,
                        threshold=50,
                        recommendation="Consider adding more workers or optimizing task processing speed",
                    )
                )

            return insights
        finally:
            session.close()

    async def predict_trends(
        self, metric_type: MetricType, prediction_hours: int = 24
    ) -> TrendPrediction:
        """Simple trend prediction using linear regression"""
        session = self.session_factory()
        try:
            # Get historical data (last 7 days for prediction)
            start_time = datetime.now(timezone.utc) - timedelta(days=7)

            historical_data = (
                session.query(MetricEntry)
                .filter(
                    MetricEntry.metric_type == metric_type.value,
                    MetricEntry.timestamp >= start_time,
                )
                .order_by(MetricEntry.timestamp)
                .all()
            )

            if len(historical_data) < 10:
                # Not enough data for prediction
                return TrendPrediction(
                    metric_type=metric_type,
                    predicted_values=[],
                    confidence_score=0.0,
                    trend_direction="unknown",
                    model_used="insufficient_data",
                )

            # Simple linear trend calculation
            timestamps = [
                (entry.timestamp - historical_data[0].timestamp).total_seconds()
                for entry in historical_data
            ]
            values = [entry.value for entry in historical_data]

            # Calculate slope (simple linear regression)
            n = len(timestamps)
            sum_x = sum(timestamps)
            sum_y = sum(values)
            sum_xy = sum(x * y for x, y in zip(timestamps, values))
            sum_x2 = sum(x * x for x in timestamps)

            if n * sum_x2 - sum_x * sum_x == 0:
                slope = 0
            else:
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

            intercept = (sum_y - slope * sum_x) / n

            # Generate predictions
            base_time = datetime.now(timezone.utc)
            prediction_points = []

            for i in range(prediction_hours):
                future_time = base_time + timedelta(hours=i)
                seconds_offset = (
                    future_time - historical_data[0].timestamp
                ).total_seconds()
                predicted_value = slope * seconds_offset + intercept

                prediction_points.append(
                    MetricPoint(
                        timestamp=future_time,
                        value=max(0, predicted_value),  # Ensure non-negative
                        labels={"prediction": "true"},
                        metadata={"model": "linear_regression"},
                    )
                )

            # Determine trend direction
            if abs(slope) < 0.001:
                trend_direction = "stable"
            elif slope > 0:
                trend_direction = "increasing"
            else:
                trend_direction = "decreasing"

            # Calculate confidence (simplified based on data consistency)
            confidence_score = min(0.95, max(0.1, 1.0 - abs(slope) * 1000))

            return TrendPrediction(
                metric_type=metric_type,
                predicted_values=prediction_points,
                confidence_score=confidence_score,
                trend_direction=trend_direction,
                model_used="linear_regression",
            )
        finally:
            session.close()

    async def get_summary_analytics(self) -> AnalyticsSummary:
        """Get high-level summary analytics for dashboard"""
        session = self.session_factory()
        try:
            # Get current date range (last 24 hours)
            start_time = datetime.now(timezone.utc) - timedelta(days=1)

            # Total tasks
            total_tasks_query = AnalyticsQuery(
                metric_type=MetricType.TASK_EXECUTION,
                time_range=TimeRange.DAY,
                aggregation=AggregationType.COUNT,
            )
            total_result = await self.process_metrics(total_tasks_query)
            total_tasks = int(total_result.data[0].value) if total_result.data else 0

            # Successful tasks
            success_query = AnalyticsQuery(
                metric_type=MetricType.TASK_EXECUTION,
                time_range=TimeRange.DAY,
                aggregation=AggregationType.COUNT,
                filters={"labels": {"success": "True"}},
            )
            success_result = await self.process_metrics(success_query)
            successful_tasks = (
                int(success_result.data[0].value) if success_result.data else 0
            )

            failed_tasks = total_tasks - successful_tasks

            # Average execution time
            exec_time_query = AnalyticsQuery(
                metric_type=MetricType.TASK_EXECUTION,
                time_range=TimeRange.DAY,
                aggregation=AggregationType.AVERAGE,
            )
            exec_time_result = await self.process_metrics(exec_time_query)
            avg_execution_time = (
                exec_time_result.data[0].value if exec_time_result.data else 0
            )

            # Current queue depth
            queue_query = AnalyticsQuery(
                metric_type=MetricType.SYSTEM_PERFORMANCE,
                time_range=TimeRange.HOUR,
                aggregation=AggregationType.AVERAGE,
                filters={"labels": {"component": "queue"}},
            )
            queue_result = await self.process_metrics(queue_query)
            current_queue_depth = (
                int(queue_result.data[0].value) if queue_result.data else 0
            )

            # System health score (simplified)
            cpu_query = AnalyticsQuery(
                metric_type=MetricType.SYSTEM_PERFORMANCE,
                time_range=TimeRange.HOUR,
                aggregation=AggregationType.AVERAGE,
                filters={"labels": {"component": "cpu"}},
            )
            cpu_result = await self.process_metrics(cpu_query)
            cpu_usage = cpu_result.data[0].value if cpu_result.data else 0

            # Health score: 100 - cpu_usage (simplified)
            system_health_score = max(0, 100 - cpu_usage)

            # Active workflows (would need workflow table)
            active_workflows = 0  # Placeholder

            # Cost today
            cost_query = AnalyticsQuery(
                metric_type=MetricType.COST_TRACKING,
                time_range=TimeRange.DAY,
                aggregation=AggregationType.SUM,
            )
            cost_result = await self.process_metrics(cost_query)
            cost_today = cost_result.data[0].value if cost_result.data else 0

            return AnalyticsSummary(
                total_tasks=total_tasks,
                successful_tasks=successful_tasks,
                failed_tasks=failed_tasks,
                average_execution_time_ms=avg_execution_time,
                current_queue_depth=current_queue_depth,
                system_health_score=system_health_score,
                active_workflows=active_workflows,
                cost_today_usd=f"{cost_today:.2f}",
            )
        finally:
            session.close()

"""Dynamic Resource Allocation Engine
Real-time resource monitoring and intelligent allocation system.

This module implements advanced resource management capabilities including:
- Real-time resource monitoring and usage tracking
- Predictive resource demand forecasting
- Dynamic allocation optimization strategies
- Cost-aware resource management
- Integration with multi-provider systems

Follows SOLID principles and integrates with existing orchestration infrastructure.
"""

import asyncio
import json
import math
import statistics
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple, Union

import structlog

from supervisor_agent.core.provider_coordinator import ProviderCoordinator
from supervisor_agent.db.enums import TaskStatus
from supervisor_agent.db.models import Provider, Task
from supervisor_agent.providers.base_provider import (ProviderType,
                                                      TaskCapability)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
structured_logger = structlog.get_logger(__name__)


class ResourceType(Enum):
    """Types of resources that can be allocated."""

    CPU_CORES = "cpu_cores"
    MEMORY_MB = "memory_mb"
    TOKENS = "tokens"
    CONCURRENT_REQUESTS = "concurrent_requests"
    STORAGE_MB = "storage_mb"
    NETWORK_BANDWIDTH = "network_bandwidth"
    GPU_UNITS = "gpu_units"


class AllocationStrategy(Enum):
    """Resource allocation strategies."""

    FAIR_SHARE = "fair_share"  # Equal distribution among tasks
    PRIORITY_BASED = "priority_based"  # Allocate based on task priority
    DEADLINE_AWARE = "deadline_aware"  # Consider task deadlines
    COST_OPTIMIZED = "cost_optimized"  # Minimize total cost
    PERFORMANCE_OPTIMIZED = "performance_optimized"  # Maximize performance
    LOAD_BALANCED = "load_balanced"  # Balance load across providers
    ADAPTIVE = "adaptive"  # Adapt based on current conditions


class ResourceStatus(Enum):
    """Resource allocation status."""

    AVAILABLE = "available"
    ALLOCATED = "allocated"
    RESERVED = "reserved"
    EXHAUSTED = "exhausted"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"


@dataclass
class ResourceMetrics:
    """Metrics for a specific resource."""

    resource_type: ResourceType
    total_capacity: float
    allocated: float
    reserved: float
    available: float
    utilization_percent: float
    peak_usage: float
    average_usage: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ResourceUsage:
    """Current resource usage for a provider or system."""

    provider_id: str
    metrics: Dict[ResourceType, ResourceMetrics]
    overall_utilization: float
    status: ResourceStatus
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    health_score: float = 1.0  # 0.0-1.0, 1.0 = perfect health


@dataclass
class ResourceAllocation:
    """Resource allocation for a specific task."""

    allocation_id: str
    task_id: str
    provider_id: str
    resources: Dict[ResourceType, float]
    priority: int
    deadline: Optional[datetime] = None
    allocated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    status: ResourceStatus = ResourceStatus.ALLOCATED
    cost_per_hour: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DemandPrediction:
    """Predicted resource demand for future time periods."""

    prediction_id: str
    time_horizon: int  # minutes into the future
    predicted_demand: Dict[ResourceType, float]
    confidence_score: float  # 0.0-1.0
    prediction_factors: List[str]  # Factors considered in prediction
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AllocationOptimization:
    """Result of allocation optimization."""

    optimization_id: str
    strategy_used: AllocationStrategy
    recommendations: List[Dict[str, Any]]
    potential_savings: float
    performance_impact: float
    confidence_score: float
    implementation_effort: str  # "low", "medium", "high"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ScalingAction:
    """Action to scale resources up or down."""

    action_id: str
    provider_id: str
    resource_type: ResourceType
    action_type: str  # "scale_up", "scale_down", "maintain"
    target_capacity: float
    current_capacity: float
    justification: str
    estimated_cost_impact: float
    estimated_time_to_execute: int  # minutes
    priority: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ResourceAlert:
    """Alert for resource-related issues."""

    alert_id: str
    alert_type: str  # "threshold_exceeded", "prediction_warning", "allocation_failed"
    severity: str  # "low", "medium", "high", "critical"
    resource_type: ResourceType
    provider_id: str
    message: str
    current_value: float
    threshold_value: float
    suggested_actions: List[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False


class RealTimeResourceMonitor:
    """Real-time resource monitoring system."""

    def __init__(self):
        self.logger = structured_logger.bind(component="resource_monitor")
        self._usage_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._alert_thresholds = self._load_alert_thresholds()
        self._monitoring_active = False
        self._monitor_task = None

    def _load_alert_thresholds(self) -> Dict[str, Dict[ResourceType, float]]:
        """Load alert thresholds for different resource types."""
        return {
            "warning": {
                ResourceType.CPU_CORES: 0.8,
                ResourceType.MEMORY_MB: 0.85,
                ResourceType.TOKENS: 0.9,
                ResourceType.CONCURRENT_REQUESTS: 0.8,
                ResourceType.STORAGE_MB: 0.8,
                ResourceType.NETWORK_BANDWIDTH: 0.85,
                ResourceType.GPU_UNITS: 0.9,
            },
            "critical": {
                ResourceType.CPU_CORES: 0.95,
                ResourceType.MEMORY_MB: 0.95,
                ResourceType.TOKENS: 0.98,
                ResourceType.CONCURRENT_REQUESTS: 0.95,
                ResourceType.STORAGE_MB: 0.95,
                ResourceType.NETWORK_BANDWIDTH: 0.95,
                ResourceType.GPU_UNITS: 0.98,
            },
        }

    async def start_monitoring(self, interval_seconds: int = 30):
        """Start continuous resource monitoring."""
        if self._monitoring_active:
            self.logger.warning("Monitoring already active")
            return

        self._monitoring_active = True
        self._monitor_task = asyncio.create_task(self._monitor_loop(interval_seconds))
        self.logger.info("Resource monitoring started", interval=interval_seconds)

    async def stop_monitoring(self):
        """Stop resource monitoring."""
        self._monitoring_active = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Resource monitoring stopped")

    async def _monitor_loop(self, interval_seconds: int):
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                await self._collect_all_metrics()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in monitoring loop", error=str(e))
                await asyncio.sleep(interval_seconds)

    async def _collect_all_metrics(self):
        """Collect metrics from all providers."""
        # This would integrate with actual provider monitoring
        # For now, simulate data collection
        providers = await self._get_active_providers()

        for provider_id in providers:
            try:
                usage = await self.collect_system_metrics(provider_id)
                self._usage_history[provider_id].append(usage)

                # Check for alerts
                alerts = self._check_alert_conditions(usage)
                for alert in alerts:
                    await self._emit_alert(alert)

            except Exception as e:
                self.logger.error(
                    "Failed to collect metrics for provider",
                    provider_id=provider_id,
                    error=str(e),
                )

    async def _get_active_providers(self) -> List[str]:
        """Get list of active provider IDs."""
        # This would query the actual provider registry
        return ["claude_cli_1", "openai_1", "local_1"]

    async def collect_system_metrics(self, provider_id: str) -> ResourceUsage:
        """Collect real-time system metrics for a provider."""
        self.logger.debug("Collecting metrics", provider_id=provider_id)

        # Simulate metric collection - in reality, this would integrate with
        # actual monitoring systems (Prometheus, CloudWatch, etc.)

        current_time = datetime.now(timezone.utc)

        # Generate realistic metrics with some variation
        base_cpu = 0.4 + (time.time() % 100) / 200  # 0.4-0.9
        base_memory = 0.3 + (time.time() % 150) / 300  # 0.3-0.8

        metrics = {
            ResourceType.CPU_CORES: ResourceMetrics(
                resource_type=ResourceType.CPU_CORES,
                total_capacity=8.0,
                allocated=base_cpu * 8.0,
                reserved=0.5,
                available=8.0 - (base_cpu * 8.0) - 0.5,
                utilization_percent=base_cpu * 100,
                peak_usage=min(8.0, base_cpu * 8.0 * 1.2),
                average_usage=base_cpu * 8.0 * 0.8,
                timestamp=current_time,
            ),
            ResourceType.MEMORY_MB: ResourceMetrics(
                resource_type=ResourceType.MEMORY_MB,
                total_capacity=16384.0,
                allocated=base_memory * 16384.0,
                reserved=1024.0,
                available=16384.0 - (base_memory * 16384.0) - 1024.0,
                utilization_percent=base_memory * 100,
                peak_usage=min(16384.0, base_memory * 16384.0 * 1.1),
                average_usage=base_memory * 16384.0 * 0.9,
                timestamp=current_time,
            ),
            ResourceType.TOKENS: ResourceMetrics(
                resource_type=ResourceType.TOKENS,
                total_capacity=1000000.0,
                allocated=50000.0,
                reserved=10000.0,
                available=940000.0,
                utilization_percent=6.0,
                peak_usage=80000.0,
                average_usage=45000.0,
                timestamp=current_time,
            ),
            ResourceType.CONCURRENT_REQUESTS: ResourceMetrics(
                resource_type=ResourceType.CONCURRENT_REQUESTS,
                total_capacity=100.0,
                allocated=12.0,
                reserved=5.0,
                available=83.0,
                utilization_percent=17.0,
                peak_usage=25.0,
                average_usage=15.0,
                timestamp=current_time,
            ),
        }

        # Calculate overall utilization
        utilizations = [m.utilization_percent for m in metrics.values()]
        overall_utilization = statistics.mean(utilizations)

        # Determine status based on utilization
        if overall_utilization > 95:
            status = ResourceStatus.EXHAUSTED
        elif overall_utilization > 85:
            status = ResourceStatus.DEGRADED
        else:
            status = ResourceStatus.AVAILABLE

        # Calculate health score
        health_score = max(0.0, 1.0 - (overall_utilization / 100) ** 2)

        usage = ResourceUsage(
            provider_id=provider_id,
            metrics=metrics,
            overall_utilization=overall_utilization,
            status=status,
            last_updated=current_time,
            health_score=health_score,
        )

        self.logger.debug(
            "Metrics collected",
            provider_id=provider_id,
            utilization=overall_utilization,
            status=status.value,
            health_score=health_score,
        )

        return usage

    def _check_alert_conditions(self, usage: ResourceUsage) -> List[ResourceAlert]:
        """Check for alert conditions in resource usage."""
        alerts = []

        for resource_type, metrics in usage.metrics.items():
            utilization = metrics.utilization_percent / 100

            # Check critical threshold
            critical_threshold = self._alert_thresholds["critical"][resource_type]
            if utilization >= critical_threshold:
                alerts.append(
                    ResourceAlert(
                        alert_id=str(uuid.uuid4()),
                        alert_type="threshold_exceeded",
                        severity="critical",
                        resource_type=resource_type,
                        provider_id=usage.provider_id,
                        message=f"{resource_type.value} utilization critically high",
                        current_value=utilization,
                        threshold_value=critical_threshold,
                        suggested_actions=[
                            "Scale up resources immediately",
                            "Redistribute workload",
                            "Enable emergency throttling",
                        ],
                    )
                )

            # Check warning threshold
            elif utilization >= self._alert_thresholds["warning"][resource_type]:
                alerts.append(
                    ResourceAlert(
                        alert_id=str(uuid.uuid4()),
                        alert_type="threshold_exceeded",
                        severity="medium",
                        resource_type=resource_type,
                        provider_id=usage.provider_id,
                        message=f"{resource_type.value} utilization approaching limits",
                        current_value=utilization,
                        threshold_value=self._alert_thresholds["warning"][
                            resource_type
                        ],
                        suggested_actions=[
                            "Consider scaling up",
                            "Monitor closely",
                            "Optimize resource usage",
                        ],
                    )
                )

        return alerts

    async def _emit_alert(self, alert: ResourceAlert):
        """Emit a resource alert."""
        self.logger.warning(
            "Resource alert",
            alert_id=alert.alert_id,
            severity=alert.severity,
            resource_type=alert.resource_type.value,
            provider_id=alert.provider_id,
            message=alert.message,
            current_value=alert.current_value,
            threshold_value=alert.threshold_value,
        )

        # Here you would integrate with alerting systems
        # (Slack, PagerDuty, email, etc.)

    async def track_provider_capacity(self, provider_id: str) -> Dict[str, Any]:
        """Track capacity trends for a specific provider."""
        if provider_id not in self._usage_history:
            return {"error": "No data available for provider"}

        history = list(self._usage_history[provider_id])
        if len(history) < 2:
            return {"error": "Insufficient data for analysis"}

        # Analyze trends
        cpu_trend = self._calculate_trend(
            [h.metrics[ResourceType.CPU_CORES].utilization_percent for h in history]
        )
        memory_trend = self._calculate_trend(
            [h.metrics[ResourceType.MEMORY_MB].utilization_percent for h in history]
        )

        latest = history[-1]

        return {
            "provider_id": provider_id,
            "current_status": latest.status.value,
            "overall_utilization": latest.overall_utilization,
            "health_score": latest.health_score,
            "trends": {"cpu": cpu_trend, "memory": memory_trend},
            "data_points": len(history),
            "time_span_minutes": (
                history[-1].last_updated - history[0].last_updated
            ).total_seconds()
            / 60,
        }

    def _calculate_trend(self, values: List[float]) -> Dict[str, Any]:
        """Calculate trend analysis for a series of values."""
        if len(values) < 2:
            return {"trend": "insufficient_data"}

        # Simple linear regression
        n = len(values)
        x = list(range(n))

        mean_x = statistics.mean(x)
        mean_y = statistics.mean(values)

        numerator = sum((x[i] - mean_x) * (values[i] - mean_y) for i in range(n))
        denominator = sum((x[i] - mean_x) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator

        # Classify trend
        if abs(slope) < 0.1:
            trend = "stable"
        elif slope > 0:
            trend = "increasing"
        else:
            trend = "decreasing"

        return {
            "trend": trend,
            "slope": slope,
            "current_value": values[-1],
            "average_value": mean_y,
            "variance": statistics.variance(values) if len(values) > 1 else 0,
        }

    async def detect_resource_bottlenecks(
        self, time_window_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Detect resource bottlenecks across all providers."""
        bottlenecks = []

        for provider_id, history in self._usage_history.items():
            recent_data = [
                usage
                for usage in history
                if (datetime.now(timezone.utc) - usage.last_updated).total_seconds()
                <= time_window_minutes * 60
            ]

            if not recent_data:
                continue

            for resource_type in ResourceType:
                utilizations = [
                    usage.metrics.get(
                        resource_type,
                        ResourceMetrics(
                            resource_type=resource_type,
                            total_capacity=0,
                            allocated=0,
                            reserved=0,
                            available=0,
                            utilization_percent=0,
                            peak_usage=0,
                            average_usage=0,
                        ),
                    ).utilization_percent
                    for usage in recent_data
                ]

                if not utilizations:
                    continue

                avg_utilization = statistics.mean(utilizations)
                max_utilization = max(utilizations)

                # Detect bottleneck conditions
                if avg_utilization > 80 or max_utilization > 95:
                    bottlenecks.append(
                        {
                            "provider_id": provider_id,
                            "resource_type": resource_type.value,
                            "average_utilization": avg_utilization,
                            "peak_utilization": max_utilization,
                            "severity": "high" if max_utilization > 95 else "medium",
                            "recommendation": self._get_bottleneck_recommendation(
                                resource_type, avg_utilization
                            ),
                        }
                    )

        return bottlenecks

    def _get_bottleneck_recommendation(
        self, resource_type: ResourceType, utilization: float
    ) -> str:
        """Get recommendation for addressing a bottleneck."""
        if resource_type == ResourceType.CPU_CORES:
            if utilization > 90:
                return "Scale up CPU capacity immediately or redistribute CPU-intensive tasks"
            else:
                return "Monitor CPU usage and consider optimizing task scheduling"
        elif resource_type == ResourceType.MEMORY_MB:
            if utilization > 90:
                return (
                    "Increase memory allocation or optimize memory-intensive operations"
                )
            else:
                return "Review memory usage patterns and consider caching optimizations"
        elif resource_type == ResourceType.TOKENS:
            return "Implement token usage optimization or increase token limits"
        elif resource_type == ResourceType.CONCURRENT_REQUESTS:
            return "Implement request queuing or increase concurrency limits"
        else:
            return f"Optimize {resource_type.value} usage or scale capacity"

    async def generate_capacity_alerts(
        self, thresholds: Dict[str, float]
    ) -> List[ResourceAlert]:
        """Generate capacity alerts based on custom thresholds."""
        alerts = []

        for provider_id, history in self._usage_history.items():
            if not history:
                continue

            latest_usage = history[-1]

            for resource_type, metrics in latest_usage.metrics.items():
                utilization = metrics.utilization_percent / 100

                # Check custom thresholds
                threshold_key = f"{resource_type.value}_threshold"
                if (
                    threshold_key in thresholds
                    and utilization >= thresholds[threshold_key]
                ):
                    alerts.append(
                        ResourceAlert(
                            alert_id=str(uuid.uuid4()),
                            alert_type="custom_threshold_exceeded",
                            severity="medium",
                            resource_type=resource_type,
                            provider_id=provider_id,
                            message=f"Custom threshold exceeded for {resource_type.value}",
                            current_value=utilization,
                            threshold_value=thresholds[threshold_key],
                            suggested_actions=[
                                f"Review {resource_type.value} allocation",
                                "Consider capacity adjustment",
                                "Analyze usage patterns",
                            ],
                        )
                    )

        return alerts


class DynamicResourceAllocator:
    """Dynamic resource allocator with intelligent optimization."""

    def __init__(self, monitor: Optional[RealTimeResourceMonitor] = None):
        self.logger = structured_logger.bind(component="resource_allocator")
        self.monitor = monitor or RealTimeResourceMonitor()
        self._allocations: Dict[str, ResourceAllocation] = {}
        self._allocation_history: deque = deque(maxlen=10000)
        self._optimization_cache: Dict[str, AllocationOptimization] = {}

    async def monitor_resource_usage(self) -> Dict[str, ResourceUsage]:
        """Get current resource usage across all providers."""
        providers = await self.monitor._get_active_providers()
        usage_report = {}

        for provider_id in providers:
            try:
                usage = await self.monitor.collect_system_metrics(provider_id)
                usage_report[provider_id] = usage
            except Exception as e:
                self.logger.error(
                    "Failed to get usage for provider",
                    provider_id=provider_id,
                    error=str(e),
                )

        return usage_report

    async def predict_resource_demand(self, time_horizon: int) -> DemandPrediction:
        """Predict resource demand for the specified time horizon."""
        self.logger.info("Predicting resource demand", time_horizon=time_horizon)

        # Analyze historical patterns
        current_usage = await self.monitor_resource_usage()
        historical_data = self._get_historical_patterns()

        # Simple prediction based on trends and patterns
        predicted_demand = {}
        prediction_factors = []

        for resource_type in ResourceType:
            # Get current average usage
            current_avg = (
                statistics.mean(
                    [
                        usage.metrics.get(
                            resource_type,
                            ResourceMetrics(
                                resource_type=resource_type,
                                total_capacity=0,
                                allocated=0,
                                reserved=0,
                                available=0,
                                utilization_percent=0,
                                peak_usage=0,
                                average_usage=0,
                            ),
                        ).utilization_percent
                        for usage in current_usage.values()
                    ]
                )
                if current_usage
                else 0
            )

            # Apply trend factor
            trend_factor = self._calculate_demand_trend_factor(
                resource_type, time_horizon
            )

            # Apply time-of-day factor
            time_factor = self._calculate_time_factor(time_horizon)

            # Apply load pattern factor
            load_factor = self._calculate_load_pattern_factor(resource_type)

            predicted_value = current_avg * trend_factor * time_factor * load_factor
            predicted_demand[resource_type] = max(
                0, min(100, predicted_value)
            )  # Clamp to 0-100%

            prediction_factors.extend(
                [
                    f"{resource_type.value}_trend_factor: {trend_factor:.2f}",
                    f"{resource_type.value}_time_factor: {time_factor:.2f}",
                    f"{resource_type.value}_load_factor: {load_factor:.2f}",
                ]
            )

        # Calculate confidence score
        confidence_score = self._calculate_prediction_confidence(
            historical_data, time_horizon
        )

        prediction = DemandPrediction(
            prediction_id=str(uuid.uuid4()),
            time_horizon=time_horizon,
            predicted_demand=predicted_demand,
            confidence_score=confidence_score,
            prediction_factors=prediction_factors,
            metadata={
                "model_version": "1.0",
                "factors_considered": len(prediction_factors),
                "historical_data_points": len(historical_data),
            },
        )

        self.logger.info(
            "Resource demand prediction completed",
            prediction_id=prediction.prediction_id,
            confidence=confidence_score,
            time_horizon=time_horizon,
        )

        return prediction

    def _get_historical_patterns(self) -> List[Dict[str, Any]]:
        """Get historical usage patterns for analysis."""
        # This would analyze historical data from the monitor
        # For now, return simulated patterns
        return [
            {"hour": i, "avg_cpu": 30 + 20 * math.sin(i * math.pi / 12)}
            for i in range(24)
        ]

    def _calculate_demand_trend_factor(
        self, resource_type: ResourceType, time_horizon: int
    ) -> float:
        """Calculate demand trend factor for a resource type."""
        # Simulate trend analysis based on resource type and time
        base_factor = 1.0

        if resource_type == ResourceType.CPU_CORES:
            # CPU tends to have cyclical patterns
            return base_factor + 0.1 * math.sin(
                time_horizon * math.pi / 720
            )  # 24-hour cycle
        elif resource_type == ResourceType.MEMORY_MB:
            # Memory usage tends to be more stable
            return base_factor + 0.05 * math.sin(time_horizon * math.pi / 1440)
        elif resource_type == ResourceType.TOKENS:
            # Token usage might have business hour patterns
            hour_of_day = (datetime.now().hour + time_horizon // 60) % 24
            if 9 <= hour_of_day <= 17:  # Business hours
                return base_factor * 1.3
            else:
                return base_factor * 0.7
        else:
            return base_factor

    def _calculate_time_factor(self, time_horizon: int) -> float:
        """Calculate time-based factor for demand prediction."""
        future_time = datetime.now() + timedelta(minutes=time_horizon)
        hour = future_time.hour

        # Business hours factor
        if 9 <= hour <= 17:
            return 1.2  # Higher demand during business hours
        elif 18 <= hour <= 22:
            return 1.0  # Moderate demand in evening
        else:
            return 0.6  # Lower demand during night/early morning

    def _calculate_load_pattern_factor(self, resource_type: ResourceType) -> float:
        """Calculate load pattern factor based on resource type."""
        # This would analyze actual load patterns
        # For now, return resource-specific factors
        patterns = {
            ResourceType.CPU_CORES: 1.1,
            ResourceType.MEMORY_MB: 1.0,
            ResourceType.TOKENS: 1.2,
            ResourceType.CONCURRENT_REQUESTS: 1.15,
            ResourceType.STORAGE_MB: 0.95,
            ResourceType.NETWORK_BANDWIDTH: 1.05,
            ResourceType.GPU_UNITS: 1.3,
        }
        return patterns.get(resource_type, 1.0)

    def _calculate_prediction_confidence(
        self, historical_data: List[Dict[str, Any]], time_horizon: int
    ) -> float:
        """Calculate confidence score for the prediction."""
        base_confidence = 0.7

        # Reduce confidence for longer horizons
        horizon_factor = max(0.3, 1.0 - (time_horizon / 1440))  # Reduce over 24 hours

        # Increase confidence with more historical data
        data_factor = min(1.0, len(historical_data) / 100)

        # Time-based confidence (higher for near-term predictions)
        time_factor = 1.0 if time_horizon <= 60 else 0.8 if time_horizon <= 360 else 0.6

        confidence = base_confidence * horizon_factor * data_factor * time_factor
        return max(0.1, min(1.0, confidence))

    async def optimize_allocation_strategy(
        self, current_usage: Dict[str, ResourceUsage]
    ) -> AllocationOptimization:
        """Optimize resource allocation strategy based on current usage."""
        self.logger.info("Optimizing allocation strategy")

        recommendations = []
        potential_savings = 0.0
        performance_impact = 0.0

        for provider_id, usage in current_usage.items():
            provider_recommendations = self._analyze_provider_optimization(
                provider_id, usage
            )
            recommendations.extend(provider_recommendations)

            # Calculate potential savings
            for rec in provider_recommendations:
                if rec["type"] == "cost_reduction":
                    potential_savings += rec.get("estimated_savings", 0)
                elif rec["type"] == "performance_improvement":
                    performance_impact += rec.get("performance_gain", 0)

        # Determine best strategy
        if potential_savings > performance_impact:
            strategy = AllocationStrategy.COST_OPTIMIZED
        elif performance_impact > potential_savings * 2:
            strategy = AllocationStrategy.PERFORMANCE_OPTIMIZED
        else:
            strategy = AllocationStrategy.ADAPTIVE

        # Calculate confidence
        confidence = min(
            1.0, len(recommendations) / 10
        )  # More recommendations = higher confidence

        optimization = AllocationOptimization(
            optimization_id=str(uuid.uuid4()),
            strategy_used=strategy,
            recommendations=recommendations,
            potential_savings=potential_savings,
            performance_impact=performance_impact,
            confidence_score=confidence,
            implementation_effort="medium",
        )

        # Cache the optimization
        self._optimization_cache[optimization.optimization_id] = optimization

        self.logger.info(
            "Allocation optimization completed",
            optimization_id=optimization.optimization_id,
            strategy=strategy.value,
            recommendations_count=len(recommendations),
            potential_savings=potential_savings,
        )

        return optimization

    def _analyze_provider_optimization(
        self, provider_id: str, usage: ResourceUsage
    ) -> List[Dict[str, Any]]:
        """Analyze optimization opportunities for a specific provider."""
        recommendations = []

        for resource_type, metrics in usage.metrics.items():
            utilization = metrics.utilization_percent

            # Under-utilization recommendations
            if utilization < 30:
                recommendations.append(
                    {
                        "type": "cost_reduction",
                        "provider_id": provider_id,
                        "resource_type": resource_type.value,
                        "issue": "under_utilization",
                        "description": f"{resource_type.value} is under-utilized at {utilization:.1f}%",
                        "recommendation": "Scale down or consolidate workload",
                        "estimated_savings": metrics.allocated
                        * 0.3
                        * 0.01,  # 30% savings estimate
                        "priority": "medium",
                    }
                )

            # Over-utilization recommendations
            elif utilization > 85:
                recommendations.append(
                    {
                        "type": "performance_improvement",
                        "provider_id": provider_id,
                        "resource_type": resource_type.value,
                        "issue": "over_utilization",
                        "description": f"{resource_type.value} is over-utilized at {utilization:.1f}%",
                        "recommendation": "Scale up or distribute load",
                        "performance_gain": (utilization - 85) / 15,  # Relative gain
                        "priority": "high" if utilization > 95 else "medium",
                    }
                )

            # Efficiency recommendations
            if metrics.peak_usage > metrics.average_usage * 1.5:
                recommendations.append(
                    {
                        "type": "efficiency_improvement",
                        "provider_id": provider_id,
                        "resource_type": resource_type.value,
                        "issue": "high_variance",
                        "description": f"{resource_type.value} has high usage variance",
                        "recommendation": "Implement load smoothing or auto-scaling",
                        "estimated_savings": metrics.allocated * 0.1 * 0.01,
                        "priority": "low",
                    }
                )

        return recommendations

    async def implement_cost_optimization(
        self, allocation: ResourceAllocation
    ) -> Dict[str, Any]:
        """Implement cost optimization for a specific allocation."""
        self.logger.info(
            "Implementing cost optimization", allocation_id=allocation.allocation_id
        )

        optimization_actions = []
        total_savings = 0.0

        for resource_type, amount in allocation.resources.items():
            # Analyze if resource can be optimized
            optimization = self._calculate_resource_optimization(resource_type, amount)

            if optimization["potential_savings"] > 0:
                optimization_actions.append(
                    {
                        "resource_type": resource_type.value,
                        "current_allocation": amount,
                        "optimized_allocation": optimization["optimized_amount"],
                        "savings": optimization["potential_savings"],
                        "action": optimization["action"],
                    }
                )
                total_savings += optimization["potential_savings"]

        # Create optimized allocation
        if optimization_actions:
            optimized_resources = {}
            for resource_type, amount in allocation.resources.items():
                action = next(
                    (
                        a
                        for a in optimization_actions
                        if a["resource_type"] == resource_type.value
                    ),
                    None,
                )
                if action:
                    optimized_resources[resource_type] = action["optimized_allocation"]
                else:
                    optimized_resources[resource_type] = amount

            # Update allocation
            allocation.resources = optimized_resources
            allocation.cost_per_hour *= 1.0 - total_savings / 100  # Reduce cost
            allocation.metadata["optimized"] = True
            allocation.metadata["optimization_date"] = datetime.now(
                timezone.utc
            ).isoformat()

            self._allocations[allocation.allocation_id] = allocation

        result = {
            "success": True,
            "allocation_id": allocation.allocation_id,
            "optimization_actions": optimization_actions,
            "total_savings_percent": total_savings,
            "new_cost_per_hour": allocation.cost_per_hour,
        }

        self.logger.info(
            "Cost optimization implemented",
            allocation_id=allocation.allocation_id,
            savings_percent=total_savings,
            actions_count=len(optimization_actions),
        )

        return result

    def _calculate_resource_optimization(
        self, resource_type: ResourceType, current_amount: float
    ) -> Dict[str, Any]:
        """Calculate optimization for a specific resource."""
        # Different optimization strategies per resource type
        if resource_type == ResourceType.CPU_CORES:
            # CPU can often be optimized by 10-20%
            optimized_amount = current_amount * 0.85
            savings = 15.0
            action = "Reduce CPU allocation using efficient scheduling"

        elif resource_type == ResourceType.MEMORY_MB:
            # Memory optimization is typically more conservative
            optimized_amount = current_amount * 0.9
            savings = 10.0
            action = "Optimize memory usage with better caching"

        elif resource_type == ResourceType.TOKENS:
            # Token optimization through better prompt engineering
            optimized_amount = current_amount * 0.8
            savings = 20.0
            action = "Implement prompt optimization and caching"

        else:
            # Conservative optimization for other resources
            optimized_amount = current_amount * 0.95
            savings = 5.0
            action = f"Minor optimization for {resource_type.value}"

        return {
            "optimized_amount": max(
                optimized_amount, current_amount * 0.5
            ),  # Don't reduce by more than 50%
            "potential_savings": savings,
            "action": action,
        }

    async def scale_resources_dynamically(
        self, demand: DemandPrediction
    ) -> List[ScalingAction]:
        """Generate dynamic scaling actions based on demand prediction."""
        self.logger.info(
            "Generating scaling actions", prediction_id=demand.prediction_id
        )

        scaling_actions = []
        current_usage = await self.monitor_resource_usage()

        for provider_id, usage in current_usage.items():
            provider_actions = self._generate_provider_scaling_actions(
                provider_id, usage, demand
            )
            scaling_actions.extend(provider_actions)

        # Sort by priority
        scaling_actions.sort(key=lambda x: x.priority, reverse=True)

        self.logger.info(
            "Scaling actions generated",
            actions_count=len(scaling_actions),
            prediction_id=demand.prediction_id,
        )

        return scaling_actions

    def _generate_provider_scaling_actions(
        self, provider_id: str, usage: ResourceUsage, demand: DemandPrediction
    ) -> List[ScalingAction]:
        """Generate scaling actions for a specific provider."""
        actions = []

        for resource_type, metrics in usage.metrics.items():
            current_utilization = metrics.utilization_percent
            predicted_demand = demand.predicted_demand.get(
                resource_type, current_utilization
            )

            # Determine if scaling is needed
            scaling_needed = self._determine_scaling_need(
                current_utilization, predicted_demand, resource_type
            )

            if scaling_needed["action"] != "maintain":
                action = ScalingAction(
                    action_id=str(uuid.uuid4()),
                    provider_id=provider_id,
                    resource_type=resource_type,
                    action_type=scaling_needed["action"],
                    target_capacity=scaling_needed["target_capacity"],
                    current_capacity=metrics.total_capacity,
                    justification=scaling_needed["justification"],
                    estimated_cost_impact=scaling_needed["cost_impact"],
                    estimated_time_to_execute=scaling_needed["execution_time"],
                    priority=scaling_needed["priority"],
                )
                actions.append(action)

        return actions

    def _determine_scaling_need(
        self,
        current_utilization: float,
        predicted_demand: float,
        resource_type: ResourceType,
    ) -> Dict[str, Any]:
        """Determine if and how to scale a specific resource."""
        utilization_threshold_high = 75.0
        utilization_threshold_low = 25.0

        if predicted_demand > utilization_threshold_high:
            # Scale up needed
            scale_factor = min(2.0, predicted_demand / current_utilization)
            return {
                "action": "scale_up",
                "target_capacity": current_utilization * scale_factor,
                "justification": f"Predicted demand ({predicted_demand:.1f}%) exceeds threshold",
                "cost_impact": scale_factor * 100 - 100,  # Percentage increase
                "execution_time": 5,  # minutes
                "priority": 8 if predicted_demand > 90 else 6,
            }

        elif (
            predicted_demand < utilization_threshold_low
            and current_utilization < utilization_threshold_low
        ):
            # Scale down possible
            scale_factor = max(0.5, predicted_demand / current_utilization)
            return {
                "action": "scale_down",
                "target_capacity": current_utilization * scale_factor,
                "justification": f"Low predicted demand ({predicted_demand:.1f}%) allows scaling down",
                "cost_impact": -(100 - scale_factor * 100),  # Negative = savings
                "execution_time": 3,  # minutes
                "priority": 4,
            }

        else:
            # No scaling needed
            return {
                "action": "maintain",
                "target_capacity": current_utilization,
                "justification": "Current capacity is appropriate for predicted demand",
                "cost_impact": 0,
                "execution_time": 0,
                "priority": 1,
            }

    async def allocate_resources(
        self,
        task_id: str,
        provider_id: str,
        resources: Dict[ResourceType, float],
        priority: int = 5,
        deadline: Optional[datetime] = None,
    ) -> ResourceAllocation:
        """Allocate resources for a specific task."""
        allocation_id = str(uuid.uuid4())

        self.logger.info(
            "Allocating resources",
            allocation_id=allocation_id,
            task_id=task_id,
            provider_id=provider_id,
            resources={k.value: v for k, v in resources.items()},
        )

        # Calculate cost
        cost_per_hour = self._calculate_allocation_cost(provider_id, resources)

        # Create allocation
        allocation = ResourceAllocation(
            allocation_id=allocation_id,
            task_id=task_id,
            provider_id=provider_id,
            resources=resources,
            priority=priority,
            deadline=deadline,
            cost_per_hour=cost_per_hour,
            metadata={
                "allocation_strategy": "direct",
                "created_by": "resource_allocator",
            },
        )

        # Store allocation
        self._allocations[allocation_id] = allocation
        self._allocation_history.append(allocation)

        self.logger.info(
            "Resources allocated",
            allocation_id=allocation_id,
            cost_per_hour=cost_per_hour,
        )

        return allocation

    def _calculate_allocation_cost(
        self, provider_id: str, resources: Dict[ResourceType, float]
    ) -> float:
        """Calculate cost per hour for resource allocation."""
        # Cost rates per unit per hour (example values)
        cost_rates = {
            ResourceType.CPU_CORES: 0.10,
            ResourceType.MEMORY_MB: 0.0001,
            ResourceType.TOKENS: 0.00001,
            ResourceType.CONCURRENT_REQUESTS: 0.01,
            ResourceType.STORAGE_MB: 0.00005,
            ResourceType.NETWORK_BANDWIDTH: 0.001,
            ResourceType.GPU_UNITS: 0.50,
        }

        # Provider multipliers
        provider_multipliers = {
            "claude_cli_1": 1.0,
            "openai_1": 1.2,
            "local_1": 0.0,  # Local has no cost
        }

        total_cost = 0.0
        multiplier = provider_multipliers.get(provider_id, 1.0)

        for resource_type, amount in resources.items():
            rate = cost_rates.get(resource_type, 0.01)
            total_cost += amount * rate * multiplier

        return round(total_cost, 4)

    def get_allocation(self, allocation_id: str) -> Optional[ResourceAllocation]:
        """Get resource allocation by ID."""
        return self._allocations.get(allocation_id)

    def get_task_allocations(self, task_id: str) -> List[ResourceAllocation]:
        """Get all allocations for a specific task."""
        return [
            allocation
            for allocation in self._allocations.values()
            if allocation.task_id == task_id
        ]

    async def deallocate_resources(self, allocation_id: str) -> bool:
        """Deallocate resources for a completed task."""
        if allocation_id not in self._allocations:
            return False

        allocation = self._allocations[allocation_id]
        allocation.status = ResourceStatus.AVAILABLE

        # Calculate actual cost based on duration
        duration_hours = (
            datetime.now(timezone.utc) - allocation.allocated_at
        ).total_seconds() / 3600
        actual_cost = allocation.cost_per_hour * duration_hours
        allocation.metadata["actual_cost"] = actual_cost
        allocation.metadata["deallocated_at"] = datetime.now(timezone.utc).isoformat()

        del self._allocations[allocation_id]

        self.logger.info(
            "Resources deallocated",
            allocation_id=allocation_id,
            duration_hours=duration_hours,
            actual_cost=actual_cost,
        )

        return True

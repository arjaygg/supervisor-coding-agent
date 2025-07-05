# supervisor_agent/core/performance_optimizer.py
import asyncio
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from supervisor_agent.models.task import Task


class OptimizationTarget(Enum):
    """Optimization targets for performance tuning."""

    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    RESOURCE_UTILIZATION = "resource_utilization"
    COST_EFFICIENCY = "cost_efficiency"
    ERROR_RATE = "error_rate"
    SCALABILITY = "scalability"


class OptimizationTechnique(Enum):
    """Performance optimization techniques."""

    CACHING = "caching"
    LOAD_BALANCING = "load_balancing"
    CONNECTION_POOLING = "connection_pooling"
    ASYNC_PROCESSING = "async_processing"
    BATCHING = "batching"
    COMPRESSION = "compression"
    INDEXING = "indexing"
    PREFETCHING = "prefetching"
    LAZY_LOADING = "lazy_loading"
    CIRCUIT_BREAKER = "circuit_breaker"


class PerformanceLevel(Enum):
    """Performance levels for optimization."""

    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"
    OPTIMAL = "optimal"


@dataclass
class PerformanceMetric:
    """Performance metric measurement."""

    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    category: str = "general"
    target_value: Optional[float] = None


@dataclass
class OptimizationAction:
    """Specific optimization action to take."""

    action_id: str
    technique: OptimizationTechnique
    target: OptimizationTarget
    description: str
    estimated_impact: str
    implementation_steps: List[str]
    estimated_effort: str  # low, medium, high
    estimated_cost: float
    priority: int  # 1-10, 1 being highest
    prerequisites: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


@dataclass
class OptimizationPlan:
    """Comprehensive optimization plan."""

    plan_id: str
    target_system: str
    optimization_goals: List[OptimizationTarget]
    actions: List[OptimizationAction]
    estimated_total_cost: float
    estimated_timeline: str
    expected_improvements: Dict[str, str]
    implementation_phases: List[Dict] = field(default_factory=list)
    success_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class OptimizationResult:
    """Results of an optimization implementation."""

    action_id: str
    implemented_at: datetime
    success: bool
    actual_improvement: Dict[str, float]
    unexpected_effects: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)


class PerformanceOptimizer:
    """Advanced performance optimization engine with ML-powered recommendations."""

    def __init__(self):
        self.performance_metrics: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self.optimization_history: List[OptimizationResult] = []
        self.active_optimizations: Dict[str, OptimizationAction] = {}
        self.performance_baselines: Dict[str, Dict[str, float]] = {}
        self.optimization_rules = self._setup_optimization_rules()
        self.learning_enabled = True

        # Performance targets
        self.performance_targets = {
            OptimizationTarget.RESPONSE_TIME: 1000.0,  # 1 second
            OptimizationTarget.THROUGHPUT: 1000.0,  # 1000 requests/min
            OptimizationTarget.RESOURCE_UTILIZATION: 70.0,  # 70% optimal
            OptimizationTarget.COST_EFFICIENCY: 0.01,  # $0.01 per request
            OptimizationTarget.ERROR_RATE: 0.1,  # 0.1%
            OptimizationTarget.SCALABILITY: 80.0,  # 80% scalability score
        }

    def _setup_optimization_rules(self) -> Dict:
        """Set up optimization rules based on patterns and best practices."""
        return {
            "high_response_time": {
                "condition": lambda metrics: self._get_latest_metric(
                    "response_time", metrics
                )
                > 3000,
                "techniques": [
                    OptimizationTechnique.CACHING,
                    OptimizationTechnique.ASYNC_PROCESSING,
                ],
                "priority": 1,
            },
            "low_throughput": {
                "condition": lambda metrics: self._get_latest_metric(
                    "throughput", metrics
                )
                < 100,
                "techniques": [
                    OptimizationTechnique.LOAD_BALANCING,
                    OptimizationTechnique.BATCHING,
                ],
                "priority": 2,
            },
            "high_resource_usage": {
                "condition": lambda metrics: self._get_latest_metric(
                    "cpu_usage", metrics
                )
                > 80,
                "techniques": [
                    OptimizationTechnique.CONNECTION_POOLING,
                    OptimizationTechnique.LAZY_LOADING,
                ],
                "priority": 1,
            },
            "high_error_rate": {
                "condition": lambda metrics: self._get_latest_metric(
                    "error_rate", metrics
                )
                > 5.0,
                "techniques": [
                    OptimizationTechnique.CIRCUIT_BREAKER,
                    OptimizationTechnique.PREFETCHING,
                ],
                "priority": 1,
            },
            "memory_pressure": {
                "condition": lambda metrics: self._get_latest_metric(
                    "memory_usage", metrics
                )
                > 85,
                "techniques": [
                    OptimizationTechnique.COMPRESSION,
                    OptimizationTechnique.LAZY_LOADING,
                ],
                "priority": 2,
            },
        }

    def _get_latest_metric(self, metric_name: str, metrics: Dict) -> float:
        """Get the latest value for a metric."""
        if metric_name in metrics and metrics[metric_name]:
            return (
                metrics[metric_name][-1].value
                if hasattr(metrics[metric_name][-1], "value")
                else metrics[metric_name][-1]
            )
        return 0.0

    async def analyze_performance_patterns(self, time_window: Dict) -> Dict:
        """Analyze performance patterns over specified time window."""
        start_time = datetime.fromisoformat(
            time_window.get("start", (datetime.now() - timedelta(hours=24)).isoformat())
        )
        end_time = datetime.fromisoformat(
            time_window.get("end", datetime.now().isoformat())
        )

        patterns = {
            "time_based_patterns": await self._analyze_time_based_patterns(
                start_time, end_time
            ),
            "correlation_patterns": await self._analyze_correlation_patterns(),
            "anomaly_patterns": await self._detect_performance_anomalies(
                start_time, end_time
            ),
            "cyclical_patterns": await self._detect_cyclical_patterns(),
            "trend_patterns": await self._analyze_trend_patterns(start_time, end_time),
        }

        return {
            "analysis_period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration_hours": (end_time - start_time).total_seconds() / 3600,
            },
            "patterns": patterns,
            "insights": await self._generate_pattern_insights(patterns),
            "recommendations": await self._patterns_to_recommendations(patterns),
        }

    async def _analyze_time_based_patterns(
        self, start_time: datetime, end_time: datetime
    ) -> Dict:
        """Analyze patterns based on time of day, day of week, etc."""
        hourly_patterns = defaultdict(list)
        daily_patterns = defaultdict(list)

        # Analyze metrics by hour and day
        for metric_name, metric_history in self.performance_metrics.items():
            for metric in metric_history:
                if start_time <= metric.timestamp <= end_time:
                    hour = metric.timestamp.hour
                    day = metric.timestamp.weekday()  # 0=Monday, 6=Sunday

                    hourly_patterns[hour].append(metric.value)
                    daily_patterns[day].append(metric.value)

        # Calculate averages for each hour/day
        hourly_averages = {
            hour: statistics.mean(values) for hour, values in hourly_patterns.items()
        }
        daily_averages = {
            day: statistics.mean(values) for day, values in daily_patterns.items()
        }

        # Identify peak and low periods
        peak_hours = sorted(hourly_averages.items(), key=lambda x: x[1], reverse=True)[
            :3
        ]
        low_hours = sorted(hourly_averages.items(), key=lambda x: x[1])[:3]

        return {
            "hourly_patterns": hourly_averages,
            "daily_patterns": daily_averages,
            "peak_hours": [{"hour": h, "avg_load": v} for h, v in peak_hours],
            "low_hours": [{"hour": h, "avg_load": v} for h, v in low_hours],
            "business_hours_impact": self._analyze_business_hours_impact(
                hourly_averages
            ),
        }

    def _analyze_business_hours_impact(self, hourly_averages: Dict) -> Dict:
        """Analyze impact during business hours vs off-hours."""
        business_hours = list(range(9, 18))  # 9 AM to 6 PM
        off_hours = [h for h in range(24) if h not in business_hours]

        business_avg = statistics.mean(
            [hourly_averages.get(h, 0) for h in business_hours]
        )
        off_hours_avg = statistics.mean([hourly_averages.get(h, 0) for h in off_hours])

        return {
            "business_hours_average": business_avg,
            "off_hours_average": off_hours_avg,
            "business_hours_multiplier": business_avg / max(0.1, off_hours_avg),
            "recommendation": (
                "Scale resources during business hours"
                if business_avg > off_hours_avg * 1.5
                else "Uniform resource allocation sufficient"
            ),
        }

    async def _analyze_correlation_patterns(self) -> Dict:
        """Analyze correlations between different metrics."""
        correlations = {}
        metric_names = list(self.performance_metrics.keys())

        for i, metric1 in enumerate(metric_names):
            for metric2 in metric_names[i + 1 :]:
                correlation = self._calculate_correlation(metric1, metric2)
                if abs(correlation) > 0.3:  # Only significant correlations
                    correlations[f"{metric1}_vs_{metric2}"] = {
                        "correlation": correlation,
                        "strength": (
                            "strong" if abs(correlation) > 0.7 else "moderate"
                        ),
                        "direction": ("positive" if correlation > 0 else "negative"),
                    }

        return {
            "significant_correlations": correlations,
            "correlation_insights": self._interpret_correlations(correlations),
        }

    def _calculate_correlation(self, metric1: str, metric2: str) -> float:
        """Calculate correlation between two metrics."""
        if (
            metric1 not in self.performance_metrics
            or metric2 not in self.performance_metrics
        ):
            return 0.0

        values1 = [
            m.value for m in list(self.performance_metrics[metric1])[-50:]
        ]  # Last 50 values
        values2 = [m.value for m in list(self.performance_metrics[metric2])[-50:]]

        if len(values1) < 10 or len(values2) < 10:
            return 0.0

        # Align the arrays (take minimum length)
        min_length = min(len(values1), len(values2))
        values1 = values1[-min_length:]
        values2 = values2[-min_length:]

        try:
            correlation = statistics.correlation(values1, values2)
            return correlation
        except:
            return 0.0

    def _interpret_correlations(self, correlations: Dict) -> List[str]:
        """Interpret correlation patterns and provide insights."""
        insights = []

        for correlation_name, data in correlations.items():
            metric1, metric2 = correlation_name.split("_vs_")
            correlation = data["correlation"]

            if (
                "cpu" in metric1.lower()
                and "response_time" in metric2.lower()
                and correlation > 0.5
            ):
                insights.append(
                    f"High CPU usage strongly correlates with response time - consider CPU optimization"
                )

            if (
                "memory" in metric1.lower()
                and "error_rate" in metric2.lower()
                and correlation > 0.4
            ):
                insights.append(
                    f"Memory pressure correlates with errors - monitor memory usage closely"
                )

            if (
                "throughput" in metric1.lower()
                and "response_time" in metric2.lower()
                and correlation < -0.4
            ):
                insights.append(
                    f"Higher throughput correlates with lower response time - system is well-optimized"
                )

        return insights

    async def _detect_performance_anomalies(
        self, start_time: datetime, end_time: datetime
    ) -> Dict:
        """Detect performance anomalies in the specified time window."""
        anomalies = []

        for metric_name, metric_history in self.performance_metrics.items():
            # Filter metrics in time window
            window_metrics = [
                m for m in metric_history if start_time <= m.timestamp <= end_time
            ]

            if len(window_metrics) < 10:
                continue

            values = [m.value for m in window_metrics]
            mean_val = statistics.mean(values)
            stdev_val = statistics.stdev(values) if len(values) > 1 else 0

            # Detect outliers (values beyond 2 standard deviations)
            for metric in window_metrics:
                if stdev_val > 0 and abs(metric.value - mean_val) > 2 * stdev_val:
                    anomalies.append(
                        {
                            "metric": metric_name,
                            "value": metric.value,
                            "expected_range": f"{mean_val - 2*stdev_val:.2f} - {mean_val + 2*stdev_val:.2f}",
                            "timestamp": metric.timestamp.isoformat(),
                            "severity": (
                                "high"
                                if abs(metric.value - mean_val) > 3 * stdev_val
                                else "medium"
                            ),
                        }
                    )

        return {
            "total_anomalies": len(anomalies),
            "high_severity_count": len(
                [a for a in anomalies if a["severity"] == "high"]
            ),
            "anomalies": sorted(anomalies, key=lambda x: x["timestamp"], reverse=True)[
                :20
            ],  # Latest 20
        }

    async def _detect_cyclical_patterns(self) -> Dict:
        """Detect cyclical patterns in performance metrics."""
        cycles = {}

        for metric_name, metric_history in self.performance_metrics.items():
            if len(metric_history) < 100:  # Need sufficient data
                continue

            values = [m.value for m in list(metric_history)[-100:]]  # Last 100 values

            # Simple cycle detection using autocorrelation
            cycle_detected = self._detect_cycle_in_series(values)

            if cycle_detected:
                cycles[metric_name] = cycle_detected

        return {
            "detected_cycles": cycles,
            "cycle_insights": self._interpret_cycles(cycles),
        }

    def _detect_cycle_in_series(self, values: List[float]) -> Optional[Dict]:
        """Detect cycles in a time series (simplified implementation)."""
        if len(values) < 20:
            return None

        # Calculate rolling averages to smooth the data
        window_size = 5
        smoothed = []
        for i in range(window_size, len(values)):
            avg = sum(values[i - window_size : i]) / window_size
            smoothed.append(avg)

        # Look for repeating patterns
        min_cycle_length = 5
        max_cycle_length = min(20, len(smoothed) // 3)

        for cycle_length in range(min_cycle_length, max_cycle_length):
            correlation = self._test_cycle_length(smoothed, cycle_length)
            if correlation > 0.6:  # Strong cyclical pattern
                return {
                    "cycle_length": cycle_length,
                    "correlation": correlation,
                    "pattern_type": "periodic",
                }

        return None

    def _test_cycle_length(self, values: List[float], cycle_length: int) -> float:
        """Test if a specific cycle length exists in the data."""
        if len(values) < cycle_length * 2:
            return 0.0

        # Compare first cycle with subsequent cycles
        first_cycle = values[:cycle_length]
        correlations = []

        for start in range(cycle_length, len(values) - cycle_length, cycle_length):
            cycle = values[start : start + cycle_length]
            if len(cycle) == cycle_length:
                try:
                    corr = statistics.correlation(first_cycle, cycle)
                    correlations.append(corr)
                except:
                    continue

        return statistics.mean(correlations) if correlations else 0.0

    def _interpret_cycles(self, cycles: Dict) -> List[str]:
        """Interpret detected cycles and provide insights."""
        insights = []

        for metric_name, cycle_data in cycles.items():
            cycle_length = cycle_data["cycle_length"]

            if cycle_length <= 24:  # Daily cycle
                insights.append(
                    f"{metric_name} shows daily cyclical pattern - consider time-based optimization"
                )
            elif cycle_length <= 168:  # Weekly cycle (24*7)
                insights.append(
                    f"{metric_name} shows weekly cyclical pattern - plan capacity for weekly variations"
                )
            else:
                insights.append(
                    f"{metric_name} shows longer-term cyclical pattern - monitor for business cycle impacts"
                )

        return insights

    async def _analyze_trend_patterns(
        self, start_time: datetime, end_time: datetime
    ) -> Dict:
        """Analyze long-term trends in performance metrics."""
        trends = {}

        for metric_name, metric_history in self.performance_metrics.items():
            # Filter metrics in time window
            window_metrics = [
                m for m in metric_history if start_time <= m.timestamp <= end_time
            ]

            if len(window_metrics) < 20:  # Need sufficient data for trend analysis
                continue

            values = [m.value for m in window_metrics]
            trend = self._calculate_trend(values)

            if abs(trend) > 0.1:  # Significant trend
                trends[metric_name] = {
                    "slope": trend,
                    "direction": "increasing" if trend > 0 else "decreasing",
                    "significance": ("strong" if abs(trend) > 0.5 else "moderate"),
                    "projection": self._project_trend(values, trend),
                }

        return {
            "detected_trends": trends,
            "trend_alerts": self._generate_trend_alerts(trends),
        }

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate linear trend in a series of values."""
        if len(values) < 2:
            return 0.0

        n = len(values)
        x = list(range(n))

        # Calculate linear regression slope
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))

        denominator = n * sum_x2 - sum_x**2
        if denominator == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope

    def _project_trend(self, values: List[float], trend: float) -> Dict:
        """Project trend into the future."""
        current_value = values[-1] if values else 0

        # Project 24 hours ahead (assuming hourly data points)
        projected_24h = current_value + (trend * 24)
        projected_7d = current_value + (trend * 24 * 7)

        return {
            "current_value": current_value,
            "projected_24h": projected_24h,
            "projected_7d": projected_7d,
            "trend_per_hour": trend,
        }

    def _generate_trend_alerts(self, trends: Dict) -> List[str]:
        """Generate alerts based on trend analysis."""
        alerts = []

        for metric_name, trend_data in trends.items():
            slope = trend_data["slope"]
            direction = trend_data["direction"]
            projection = trend_data["projection"]

            if "response_time" in metric_name.lower() and direction == "increasing":
                alerts.append(
                    f"WARNING: {metric_name} is trending upward - response times may degrade"
                )

            if "error_rate" in metric_name.lower() and direction == "increasing":
                alerts.append(
                    f"CRITICAL: {metric_name} is increasing - investigate error sources"
                )

            if "throughput" in metric_name.lower() and direction == "decreasing":
                alerts.append(
                    f"WARNING: {metric_name} is declining - capacity issues may develop"
                )

            if "memory" in metric_name.lower() and direction == "increasing":
                alerts.append(
                    f"WARNING: {metric_name} is trending upward - potential memory leak"
                )

        return alerts

    async def _generate_pattern_insights(self, patterns: Dict) -> List[str]:
        """Generate insights from analyzed patterns."""
        insights = []

        # Time-based insights
        time_patterns = patterns.get("time_based_patterns", {})
        if (
            time_patterns.get("business_hours_impact", {}).get(
                "business_hours_multiplier", 1
            )
            > 2
        ):
            insights.append(
                "System load is significantly higher during business hours - consider auto-scaling"
            )

        # Correlation insights
        correlation_patterns = patterns.get("correlation_patterns", {})
        insights.extend(correlation_patterns.get("correlation_insights", []))

        # Anomaly insights
        anomaly_patterns = patterns.get("anomaly_patterns", {})
        if anomaly_patterns.get("high_severity_count", 0) > 5:
            insights.append(
                "High number of performance anomalies detected - investigate system stability"
            )

        # Cyclical insights
        cyclical_patterns = patterns.get("cyclical_patterns", {})
        insights.extend(cyclical_patterns.get("cycle_insights", []))

        # Trend insights
        trend_patterns = patterns.get("trend_patterns", {})
        insights.extend(trend_patterns.get("trend_alerts", []))

        return insights

    async def _patterns_to_recommendations(self, patterns: Dict) -> List[str]:
        """Convert patterns into actionable recommendations."""
        recommendations = []

        # Business hours recommendations
        time_patterns = patterns.get("time_based_patterns", {})
        business_impact = time_patterns.get("business_hours_impact", {})
        if business_impact.get("business_hours_multiplier", 1) > 1.5:
            recommendations.append(
                "Implement time-based auto-scaling for business hours"
            )

        # Correlation-based recommendations
        correlations = patterns.get("correlation_patterns", {}).get(
            "significant_correlations", {}
        )
        for correlation_name, data in correlations.items():
            if (
                "cpu" in correlation_name
                and "response_time" in correlation_name
                and data["correlation"] > 0.5
            ):
                recommendations.append(
                    "Optimize CPU-intensive operations to improve response times"
                )

        # Trend-based recommendations
        trends = patterns.get("trend_patterns", {}).get("detected_trends", {})
        for metric_name, trend_data in trends.items():
            if (
                "memory" in metric_name.lower()
                and trend_data["direction"] == "increasing"
            ):
                recommendations.append(
                    "Investigate potential memory leaks and implement memory optimization"
                )

        return recommendations

    async def generate_optimization_recommendations(
        self, analysis: Dict
    ) -> List[OptimizationAction]:
        """Generate specific optimization recommendations based on analysis."""
        system_metrics = analysis.get("current_metrics", {})
        bottlenecks = await self.analyze_performance_bottlenecks(system_metrics)

        recommendations = []

        for i, bottleneck in enumerate(bottlenecks):
            # Generate actions for each suggested technique
            for technique_name in bottleneck.get("suggested_techniques", []):
                try:
                    technique = OptimizationTechnique(technique_name)
                    action = await self._create_optimization_action(
                        bottleneck, technique, i, analysis
                    )
                    recommendations.append(action)
                except ValueError:
                    # Skip invalid technique names
                    continue

        # Add pattern-based recommendations
        pattern_recommendations = await self._pattern_based_recommendations(analysis)
        recommendations.extend(pattern_recommendations)

        return sorted(recommendations, key=lambda x: x.priority)

    async def analyze_performance_bottlenecks(self, system_metrics: Dict) -> List[Dict]:
        """Analyze system metrics to identify performance bottlenecks."""
        bottlenecks = []

        # Record current metrics
        for metric_name, value in system_metrics.items():
            if isinstance(value, (int, float)):
                self.performance_metrics[metric_name].append(
                    PerformanceMetric(name=metric_name, value=value, unit="units")
                )

        # Analyze each metric against optimization rules
        for rule_name, rule in self.optimization_rules.items():
            if rule["condition"](self.performance_metrics):
                bottlenecks.append(
                    {
                        "type": rule_name,
                        "priority": rule["priority"],
                        "affected_metrics": self._get_affected_metrics(rule_name),
                        "suggested_techniques": [
                            tech.value for tech in rule["techniques"]
                        ],
                        "severity": self._calculate_bottleneck_severity(rule_name),
                        "impact_estimate": self._estimate_bottleneck_impact(rule_name),
                    }
                )

        return sorted(bottlenecks, key=lambda x: x["priority"])

    def _get_affected_metrics(self, rule_name: str) -> List[str]:
        """Get metrics affected by a specific bottleneck type."""
        metric_mappings = {
            "high_response_time": ["response_time", "user_satisfaction"],
            "low_throughput": ["throughput", "requests_per_second"],
            "high_resource_usage": ["cpu_usage", "memory_usage"],
            "high_error_rate": ["error_rate", "availability"],
            "memory_pressure": ["memory_usage", "gc_frequency"],
        }
        return metric_mappings.get(rule_name, [])

    def _calculate_bottleneck_severity(self, rule_name: str) -> str:
        """Calculate severity of a bottleneck."""
        severity_mapping = {
            "high_response_time": "high",
            "low_throughput": "medium",
            "high_resource_usage": "high",
            "high_error_rate": "critical",
            "memory_pressure": "high",
        }
        return severity_mapping.get(rule_name, "medium")

    def _estimate_bottleneck_impact(self, rule_name: str) -> str:
        """Estimate the impact of a bottleneck on system performance."""
        impact_mapping = {
            "high_response_time": "30-50% performance degradation",
            "low_throughput": "40-60% capacity reduction",
            "high_resource_usage": "20-40% efficiency loss",
            "high_error_rate": "Critical user experience impact",
            "memory_pressure": "25-45% performance degradation",
        }
        return impact_mapping.get(rule_name, "Moderate performance impact")

    async def _create_optimization_action(
        self,
        bottleneck: Dict,
        technique: OptimizationTechnique,
        index: int,
        context: Dict,
    ) -> OptimizationAction:
        """Create a specific optimization action."""
        action_id = f"{technique.value}_{bottleneck['type']}_{index}_{int(datetime.now().timestamp())}"

        # Get technique-specific details
        technique_details = self._get_technique_details(technique, bottleneck, context)

        return OptimizationAction(
            action_id=action_id,
            technique=technique,
            target=self._map_bottleneck_to_target(bottleneck["type"]),
            description=technique_details["description"],
            estimated_impact=technique_details["estimated_impact"],
            implementation_steps=technique_details["implementation_steps"],
            estimated_effort=technique_details["estimated_effort"],
            estimated_cost=technique_details["estimated_cost"],
            priority=self._calculate_action_priority(bottleneck, technique),
            prerequisites=technique_details.get("prerequisites", []),
            risks=technique_details.get("risks", []),
        )

    def _get_technique_details(
        self, technique: OptimizationTechnique, bottleneck: Dict, context: Dict
    ) -> Dict:
        """Get detailed information about an optimization technique."""
        technique_info = {
            OptimizationTechnique.CACHING: {
                "description": "Implement intelligent caching to reduce computation and I/O overhead",
                "estimated_impact": "40-70% response time improvement",
                "implementation_steps": [
                    "Identify frequently accessed data",
                    "Design cache invalidation strategy",
                    "Implement cache layer (Redis/Memcached)",
                    "Monitor cache hit rates and performance",
                ],
                "estimated_effort": "medium",
                "estimated_cost": 50.0,
                "prerequisites": ["Cache infrastructure"],
                "risks": ["Cache invalidation complexity", "Memory overhead"],
            },
            OptimizationTechnique.ASYNC_PROCESSING: {
                "description": "Convert blocking operations to asynchronous processing",
                "estimated_impact": "50-200% throughput improvement",
                "implementation_steps": [
                    "Identify blocking operations",
                    "Refactor to async/await patterns",
                    "Implement proper error handling",
                    "Monitor async operation performance",
                ],
                "estimated_effort": "high",
                "estimated_cost": 80.0,
                "prerequisites": ["Async runtime support"],
                "risks": ["Complexity increase", "Debugging difficulty"],
            },
        }

        return technique_info.get(
            technique,
            {
                "description": f"Apply {technique.value} optimization",
                "estimated_impact": "Moderate performance improvement",
                "implementation_steps": [
                    "Analyze current implementation",
                    "Apply optimization",
                    "Test and monitor",
                ],
                "estimated_effort": "medium",
                "estimated_cost": 50.0,
                "prerequisites": [],
                "risks": [],
            },
        )

    def _map_bottleneck_to_target(self, bottleneck_type: str) -> OptimizationTarget:
        """Map bottleneck type to optimization target."""
        mapping = {
            "high_response_time": OptimizationTarget.RESPONSE_TIME,
            "low_throughput": OptimizationTarget.THROUGHPUT,
            "high_resource_usage": OptimizationTarget.RESOURCE_UTILIZATION,
            "high_error_rate": OptimizationTarget.ERROR_RATE,
            "memory_pressure": OptimizationTarget.RESOURCE_UTILIZATION,
        }
        return mapping.get(bottleneck_type, OptimizationTarget.RESPONSE_TIME)

    def _calculate_action_priority(
        self, bottleneck: Dict, technique: OptimizationTechnique
    ) -> int:
        """Calculate priority for an optimization action."""
        base_priority = bottleneck["priority"]

        # Adjust based on technique effectiveness
        technique_priorities = {
            OptimizationTechnique.CACHING: 1,
            OptimizationTechnique.ASYNC_PROCESSING: 2,
            OptimizationTechnique.LOAD_BALANCING: 1,
        }

        technique_priority = technique_priorities.get(technique, 3)

        # Combine priorities (lower is higher priority)
        return min(10, base_priority + technique_priority - 1)

    async def _pattern_based_recommendations(
        self, analysis: Dict
    ) -> List[OptimizationAction]:
        """Generate recommendations based on detected patterns."""
        recommendations = []
        patterns = analysis.get("patterns", {})

        # Time-based recommendations
        time_patterns = patterns.get("time_based_patterns", {})
        business_impact = time_patterns.get("business_hours_impact", {})

        if business_impact.get("business_hours_multiplier", 1) > 1.5:
            action = OptimizationAction(
                action_id=f"time_based_scaling_{int(datetime.now().timestamp())}",
                technique=OptimizationTechnique.LOAD_BALANCING,
                target=OptimizationTarget.SCALABILITY,
                description="Implement time-based auto-scaling for business hours",
                estimated_impact="30-50% cost efficiency improvement",
                implementation_steps=[
                    "Analyze traffic patterns",
                    "Configure auto-scaling policies",
                    "Implement time-based triggers",
                    "Monitor scaling effectiveness",
                ],
                estimated_effort="medium",
                estimated_cost=75.0,
                priority=2,
            )
            recommendations.append(action)

        return recommendations

    async def implement_automatic_adjustments(
        self, recommendations: List[OptimizationAction]
    ) -> List[Dict]:
        """Implement automatic performance adjustments."""
        implemented_adjustments = []

        for rec in recommendations:
            # Only auto-implement low-risk, low-effort optimizations
            if rec.estimated_effort == "low" and not rec.risks:
                try:
                    result = await self._simulate_implementation(rec)
                    implemented_adjustments.append(
                        {
                            "action_id": rec.action_id,
                            "technique": rec.technique.value,
                            "status": "implemented",
                            "result": result,
                        }
                    )
                except Exception as e:
                    implemented_adjustments.append(
                        {
                            "action_id": rec.action_id,
                            "technique": rec.technique.value,
                            "status": "failed",
                            "error": str(e),
                        }
                    )

        return implemented_adjustments

    async def _simulate_implementation(self, action: OptimizationAction) -> Dict:
        """Simulate implementation of an optimization action."""
        # Simulate implementation delay
        await asyncio.sleep(0.1)

        # Simulate success/failure
        success_rate = 0.8  # 80% success rate for auto-implementations
        import random

        success = random.random() < success_rate

        if success:
            # Simulate performance improvement
            improvement = random.uniform(10, 30)  # 10-30% improvement
            return {
                "success": True,
                "improvement_percentage": improvement,
                "implementation_time": "0.1 seconds",
            }
        else:
            return {
                "success": False,
                "error": "Simulated implementation failure",
            }

    async def detect_performance_regressions(self, baseline: Dict) -> List[Dict]:
        """Detect performance regressions compared to baseline."""
        regressions = []

        for metric_name, baseline_value in baseline.items():
            if (
                metric_name in self.performance_metrics
                and self.performance_metrics[metric_name]
            ):
                current_metric = self.performance_metrics[metric_name][-1]
                current_value = current_metric.value

                # Calculate regression percentage
                regression_percent = (
                    (current_value - baseline_value) / max(0.1, baseline_value)
                ) * 100

                # Define regression thresholds (worse performance)
                threshold = 10.0  # 10% degradation threshold

                is_regression = False
                if metric_name in [
                    "response_time",
                    "error_rate",
                    "cpu_usage",
                    "memory_usage",
                ]:
                    # Higher values are worse
                    is_regression = regression_percent > threshold
                elif metric_name in ["throughput", "success_rate"]:
                    # Lower values are worse
                    is_regression = regression_percent < -threshold

                if is_regression:
                    severity = (
                        "critical"
                        if abs(regression_percent) > 25
                        else ("high" if abs(regression_percent) > 15 else "medium")
                    )

                    regressions.append(
                        {
                            "metric": metric_name,
                            "baseline_value": baseline_value,
                            "current_value": current_value,
                            "regression_percent": regression_percent,
                            "severity": severity,
                            "detected_at": current_metric.timestamp.isoformat(),
                            "recommended_action": self._suggest_regression_action(
                                metric_name, regression_percent
                            ),
                        }
                    )

        return sorted(
            regressions,
            key=lambda x: abs(x["regression_percent"]),
            reverse=True,
        )

    def _suggest_regression_action(
        self, metric_name: str, regression_percent: float
    ) -> str:
        """Suggest action to address performance regression."""
        if "response_time" in metric_name:
            return "Investigate recent changes, check for resource bottlenecks, consider rollback"
        elif "throughput" in metric_name:
            return "Check system capacity, investigate blocking operations, scale resources"
        elif "error_rate" in metric_name:
            return (
                "Investigate error logs, check dependencies, verify recent deployments"
            )
        elif "cpu_usage" in metric_name:
            return "Profile CPU-intensive operations, check for inefficient algorithms"
        elif "memory_usage" in metric_name:
            return "Check for memory leaks, optimize data structures, monitor garbage collection"
        else:
            return "Investigate recent changes and monitor system health"

    async def optimize_provider_selection(self, task: Dict) -> Dict:
        """Optimize provider selection based on performance characteristics."""
        task_requirements = task.get("requirements", {})

        # Simulate provider performance characteristics
        providers = {
            "provider_a": {
                "response_time": 800,
                "throughput": 1200,
                "cost_per_request": 0.008,
                "reliability": 99.5,
                "cpu_efficiency": 85,
                "memory_efficiency": 80,
            },
            "provider_b": {
                "response_time": 600,
                "throughput": 1500,
                "cost_per_request": 0.012,
                "reliability": 99.8,
                "cpu_efficiency": 90,
                "memory_efficiency": 85,
            },
            "provider_c": {
                "response_time": 1000,
                "throughput": 1000,
                "cost_per_request": 0.005,
                "reliability": 99.2,
                "cpu_efficiency": 75,
                "memory_efficiency": 88,
            },
        }

        # Score providers based on task requirements
        provider_scores = {}

        for provider_name, metrics in providers.items():
            score = 0

            # Response time priority
            if task_requirements.get("priority", "medium") == "high":
                score += (
                    2000 - metrics["response_time"]
                ) / 20  # Lower response time = higher score

            # Throughput requirement
            required_throughput = task_requirements.get("throughput", 1000)
            if metrics["throughput"] >= required_throughput:
                score += 50  # Meets throughput requirement

            # Cost consideration
            max_cost = task_requirements.get("max_cost_per_request", 0.01)
            if metrics["cost_per_request"] <= max_cost:
                score += 30  # Within budget

            # Reliability requirement
            score += metrics["reliability"]  # Direct reliability score

            # Resource efficiency (if specified)
            if task_requirements.get("cpu_intensive", False):
                score += metrics["cpu_efficiency"] / 2

            if task_requirements.get("memory_intensive", False):
                score += metrics["memory_efficiency"] / 2

            provider_scores[provider_name] = score

        # Select best provider
        best_provider = max(provider_scores.items(), key=lambda x: x[1])

        return {
            "selected_provider": best_provider[0],
            "selection_score": best_provider[1],
            "provider_metrics": providers[best_provider[0]],
            "all_scores": provider_scores,
            "selection_reasoning": self._generate_selection_reasoning(
                best_provider[0],
                providers[best_provider[0]],
                task_requirements,
            ),
        }

    def _generate_selection_reasoning(
        self, provider: str, metrics: Dict, requirements: Dict
    ) -> str:
        """Generate reasoning for provider selection."""
        reasons = []

        if requirements.get("priority") == "high" and metrics["response_time"] < 700:
            reasons.append("Low response time meets high priority requirement")

        if metrics["cost_per_request"] <= requirements.get(
            "max_cost_per_request", 0.01
        ):
            reasons.append("Cost-effective within budget constraints")

        if metrics["reliability"] > 99.5:
            reasons.append("High reliability score ensures service stability")

        if requirements.get("cpu_intensive") and metrics["cpu_efficiency"] > 85:
            reasons.append("High CPU efficiency for CPU-intensive tasks")

        if not reasons:
            reasons.append("Best overall performance characteristics for this task")

        return "; ".join(reasons)

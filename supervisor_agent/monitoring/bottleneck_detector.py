# supervisor_agent/monitoring/bottleneck_detector.py
import asyncio
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple


class BottleneckType(Enum):
    """Types of performance bottlenecks."""

    CPU_BOTTLENECK = "cpu_bottleneck"
    MEMORY_BOTTLENECK = "memory_bottleneck"
    IO_BOTTLENECK = "io_bottleneck"
    NETWORK_BOTTLENECK = "network_bottleneck"
    DATABASE_BOTTLENECK = "database_bottleneck"
    QUEUE_BOTTLENECK = "queue_bottleneck"
    DEPENDENCY_BOTTLENECK = "dependency_bottleneck"
    ALGORITHM_BOTTLENECK = "algorithm_bottleneck"


class ComponentType(Enum):
    """Types of system components."""

    TASK_PROCESSOR = "task_processor"
    RESOURCE_ALLOCATOR = "resource_allocator"
    CONFLICT_RESOLVER = "conflict_resolver"
    DATABASE_CONNECTION = "database_connection"
    EXTERNAL_API = "external_api"
    MESSAGE_QUEUE = "message_queue"
    WORKER_POOL = "worker_pool"
    CACHE_LAYER = "cache_layer"


class OptimizationStrategy(Enum):
    """Optimization strategies for bottlenecks."""

    SCALE_HORIZONTALLY = "scale_horizontally"
    SCALE_VERTICALLY = "scale_vertically"
    OPTIMIZE_ALGORITHM = "optimize_algorithm"
    ADD_CACHING = "add_caching"
    IMPLEMENT_BATCHING = "implement_batching"
    REDUCE_DEPENDENCIES = "reduce_dependencies"
    ASYNC_PROCESSING = "async_processing"
    CONNECTION_POOLING = "connection_pooling"
    LOAD_BALANCING = "load_balancing"
    CODE_OPTIMIZATION = "code_optimization"


@dataclass
class ComponentMetrics:
    """Metrics for a system component."""

    component_name: str
    component_type: ComponentType
    response_times: List[float] = field(default_factory=list)
    throughput: float = 0.0
    error_rate: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    queue_depth: int = 0
    active_connections: int = 0
    cache_hit_rate: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BottleneckAnalysis:
    """Analysis of a detected bottleneck."""

    bottleneck_id: str
    bottleneck_type: BottleneckType
    component_name: str
    component_type: ComponentType
    severity: str  # low, medium, high, critical
    impact_score: float  # 0-100
    description: str
    root_cause: str
    affected_metrics: Dict[str, float]
    detection_time: datetime = field(default_factory=datetime.now)


@dataclass
class OptimizationRecommendation:
    """Optimization recommendation for a bottleneck."""

    recommendation_id: str
    bottleneck_id: str
    strategy: OptimizationStrategy
    description: str
    estimated_improvement: str
    implementation_effort: str  # low, medium, high
    estimated_cost: float
    priority: int  # 1-10, 1 being highest
    implementation_steps: List[str] = field(default_factory=list)
    expected_metrics_impact: Dict[str, str] = field(default_factory=dict)


@dataclass
class PipelineStage:
    """Pipeline execution stage."""

    stage_name: str
    stage_type: ComponentType
    execution_time: float
    throughput: float
    dependencies: List[str] = field(default_factory=list)
    parallel_capacity: int = 1
    current_load: float = 0.0


class BottleneckDetector:
    """Advanced bottleneck detection and analysis system."""

    def __init__(self):
        self.component_metrics: Dict[str, ComponentMetrics] = {}
        self.bottleneck_history: List[BottleneckAnalysis] = []
        self.optimization_recommendations: Dict[
            str, List[OptimizationRecommendation]
        ] = defaultdict(list)
        self.performance_baselines: Dict[str, Dict[str, float]] = {}
        self.analysis_rules = self._setup_analysis_rules()
        self.monitoring_active = True

        # Detection thresholds
        self.thresholds = {
            "response_time_threshold": 3000.0,  # 3 seconds
            "cpu_threshold": 80.0,  # 80%
            "memory_threshold": 85.0,  # 85%
            "error_rate_threshold": 5.0,  # 5%
            "queue_depth_threshold": 100,
            "throughput_degradation": 30.0,  # 30% below baseline
        }

    def _setup_analysis_rules(self) -> Dict:
        """Set up rules for bottleneck analysis."""
        return {
            "cpu_bottleneck": {
                "condition": lambda metrics: metrics.cpu_usage > 80.0,
                "severity_fn": lambda metrics: (
                    "critical"
                    if metrics.cpu_usage > 95
                    else "high" if metrics.cpu_usage > 85 else "medium"
                ),
            },
            "memory_bottleneck": {
                "condition": lambda metrics: metrics.memory_usage > 85.0,
                "severity_fn": lambda metrics: (
                    "critical"
                    if metrics.memory_usage > 95
                    else "high" if metrics.memory_usage > 90 else "medium"
                ),
            },
            "response_time_bottleneck": {
                "condition": lambda metrics: statistics.mean(
                    metrics.response_times[-10:] or [0]
                )
                > 3000,
                "severity_fn": lambda metrics: (
                    "critical"
                    if statistics.mean(metrics.response_times[-5:] or [0])
                    > 10000
                    else "high"
                ),
            },
            "throughput_bottleneck": {
                "condition": lambda metrics: self._is_throughput_degraded(
                    metrics
                ),
                "severity_fn": lambda metrics: (
                    "high"
                    if metrics.throughput
                    < self._get_baseline_throughput(metrics.component_name)
                    * 0.5
                    else "medium"
                ),
            },
            "queue_bottleneck": {
                "condition": lambda metrics: metrics.queue_depth > 100,
                "severity_fn": lambda metrics: (
                    "critical"
                    if metrics.queue_depth > 500
                    else "high" if metrics.queue_depth > 200 else "medium"
                ),
            },
        }

    async def analyze_execution_pipeline(self, pipeline: Dict) -> Dict:
        """Analyze the execution pipeline for bottlenecks and inefficiencies."""
        stages = pipeline.get("stages", [])

        # Convert stages to PipelineStage objects
        pipeline_stages = []
        for stage_data in stages:
            stage = PipelineStage(
                stage_name=stage_data.get(
                    "name", f"stage_{len(pipeline_stages)}"
                ),
                stage_type=ComponentType(
                    stage_data.get("type", "task_processor")
                ),
                execution_time=stage_data.get("execution_time", 1000.0),
                throughput=stage_data.get("throughput", 10.0),
                dependencies=stage_data.get("dependencies", []),
                parallel_capacity=stage_data.get("parallel_capacity", 1),
                current_load=stage_data.get("current_load", 0.5),
            )
            pipeline_stages.append(stage)

        # Analyze pipeline characteristics
        analysis = {
            "pipeline_id": pipeline.get("pipeline_id", "unknown"),
            "total_stages": len(pipeline_stages),
            "critical_path": await self._identify_critical_path(
                pipeline_stages
            ),
            "bottleneck_stages": await self._identify_bottleneck_stages(
                pipeline_stages
            ),
            "parallelization_opportunities": await self._identify_parallelization_opportunities(
                pipeline_stages
            ),
            "resource_utilization": await self._analyze_resource_utilization(
                pipeline_stages
            ),
            "performance_metrics": await self._calculate_pipeline_metrics(
                pipeline_stages
            ),
            "optimization_opportunities": await self._identify_optimization_opportunities(
                pipeline_stages
            ),
        }

        return analysis

    async def _identify_critical_path(
        self, stages: List[PipelineStage]
    ) -> Dict:
        """Identify the critical path through the pipeline."""
        # Build dependency graph and find longest path
        stage_map = {stage.stage_name: stage for stage in stages}

        def calculate_path_length(stage_name: str, visited: set) -> float:
            if stage_name in visited:
                return 0  # Circular dependency

            visited.add(stage_name)
            stage = stage_map.get(stage_name)
            if not stage:
                return 0

            max_dependency_time = 0
            for dep in stage.dependencies:
                dep_time = calculate_path_length(dep, visited.copy())
                max_dependency_time = max(max_dependency_time, dep_time)

            return max_dependency_time + stage.execution_time

        critical_path = []
        max_time = 0

        for stage in stages:
            if (
                not stage.dependencies
            ):  # Start from stages with no dependencies
                path_time = calculate_path_length(stage.stage_name, set())
                if path_time > max_time:
                    max_time = path_time
                    # Rebuild path (simplified)
                    critical_path = [stage.stage_name]

        return {
            "path": critical_path,
            "total_time": max_time,
            "bottleneck_stage": critical_path[0] if critical_path else None,
        }

    async def _identify_bottleneck_stages(
        self, stages: List[PipelineStage]
    ) -> List[Dict]:
        """Identify stages that are bottlenecks in the pipeline."""
        bottlenecks = []

        for stage in stages:
            # Calculate utilization ratio
            utilization = stage.current_load / max(1, stage.parallel_capacity)

            # Check if stage is a bottleneck
            if utilization > 0.8:  # 80% utilization threshold
                severity = (
                    "critical"
                    if utilization > 0.95
                    else "high" if utilization > 0.9 else "medium"
                )

                bottlenecks.append(
                    {
                        "stage_name": stage.stage_name,
                        "stage_type": stage.stage_type.value,
                        "utilization": utilization,
                        "severity": severity,
                        "execution_time": stage.execution_time,
                        "throughput": stage.throughput,
                        "recommendation": self._get_stage_recommendation(
                            stage, utilization
                        ),
                    }
                )

        return sorted(
            bottlenecks, key=lambda x: x["utilization"], reverse=True
        )

    def _get_stage_recommendation(
        self, stage: PipelineStage, utilization: float
    ) -> str:
        """Get optimization recommendation for a stage."""
        if utilization > 0.9:
            if stage.parallel_capacity == 1:
                return "Scale horizontally: Add parallel processing capacity"
            else:
                return "Scale vertically: Increase processing power or optimize algorithm"
        elif utilization > 0.8:
            return "Monitor closely and prepare for scaling"
        else:
            return "Optimize resource allocation"

    async def _identify_parallelization_opportunities(
        self, stages: List[PipelineStage]
    ) -> List[Dict]:
        """Identify opportunities for parallelization."""
        opportunities = []

        # Group stages by dependency levels
        dependency_levels = self._build_dependency_levels(stages)

        for level, level_stages in dependency_levels.items():
            if len(level_stages) > 1:
                # Multiple stages at same level can potentially be parallelized
                total_execution_time = sum(
                    stage.execution_time for stage in level_stages
                )
                max_execution_time = max(
                    stage.execution_time for stage in level_stages
                )

                parallelization_benefit = (
                    total_execution_time - max_execution_time
                )

                if (
                    parallelization_benefit > 1000
                ):  # 1 second benefit threshold
                    opportunities.append(
                        {
                            "level": level,
                            "stages": [
                                stage.stage_name for stage in level_stages
                            ],
                            "current_total_time": total_execution_time,
                            "parallel_time": max_execution_time,
                            "time_savings": parallelization_benefit,
                            "feasibility": (
                                "high"
                                if all(
                                    stage.parallel_capacity > 1
                                    for stage in level_stages
                                )
                                else "medium"
                            ),
                        }
                    )

        return opportunities

    def _build_dependency_levels(
        self, stages: List[PipelineStage]
    ) -> Dict[int, List[PipelineStage]]:
        """Build dependency levels for stages."""
        levels = defaultdict(list)
        stage_map = {stage.stage_name: stage for stage in stages}

        def get_stage_level(stage: PipelineStage, visited: set) -> int:
            if stage.stage_name in visited:
                return 0  # Circular dependency

            visited.add(stage.stage_name)

            if not stage.dependencies:
                return 0

            max_dep_level = 0
            for dep_name in stage.dependencies:
                dep_stage = stage_map.get(dep_name)
                if dep_stage:
                    dep_level = get_stage_level(dep_stage, visited.copy())
                    max_dep_level = max(max_dep_level, dep_level)

            return max_dep_level + 1

        for stage in stages:
            level = get_stage_level(stage, set())
            levels[level].append(stage)

        return dict(levels)

    async def _analyze_resource_utilization(
        self, stages: List[PipelineStage]
    ) -> Dict:
        """Analyze resource utilization across pipeline stages."""
        total_cpu = sum(
            getattr(stage, "cpu_usage", 50.0) for stage in stages
        ) / len(stages)
        total_memory = sum(
            getattr(stage, "memory_usage", 60.0) for stage in stages
        ) / len(stages)

        return {
            "average_cpu_utilization": total_cpu,
            "average_memory_utilization": total_memory,
            "resource_efficiency": self._calculate_resource_efficiency(stages),
            "underutilized_stages": [
                stage.stage_name
                for stage in stages
                if stage.current_load < 0.3
            ],
            "overutilized_stages": [
                stage.stage_name
                for stage in stages
                if stage.current_load > 0.8
            ],
        }

    def _calculate_resource_efficiency(
        self, stages: List[PipelineStage]
    ) -> float:
        """Calculate overall resource efficiency."""
        if not stages:
            return 0.0

        efficiency_scores = []
        for stage in stages:
            # Efficiency = actual throughput / (resources used * capacity)
            resource_usage = stage.current_load
            if resource_usage > 0:
                efficiency = stage.throughput / (
                    resource_usage * stage.parallel_capacity
                )
                efficiency_scores.append(
                    min(100, efficiency * 10)
                )  # Scale to 0-100

        return (
            sum(efficiency_scores) / len(efficiency_scores)
            if efficiency_scores
            else 0.0
        )

    async def _calculate_pipeline_metrics(
        self, stages: List[PipelineStage]
    ) -> Dict:
        """Calculate comprehensive pipeline performance metrics."""
        total_execution_time = sum(stage.execution_time for stage in stages)
        min_throughput = (
            min(stage.throughput for stage in stages) if stages else 0
        )

        return {
            "total_execution_time": total_execution_time,
            "bottleneck_throughput": min_throughput,
            "average_stage_time": (
                total_execution_time / len(stages) if stages else 0
            ),
            "pipeline_efficiency": self._calculate_pipeline_efficiency(stages),
            "scalability_score": self._calculate_scalability_score(stages),
        }

    def _calculate_pipeline_efficiency(
        self, stages: List[PipelineStage]
    ) -> float:
        """Calculate pipeline efficiency score."""
        if not stages:
            return 0.0

        # Efficiency based on resource utilization and throughput
        utilization_scores = [stage.current_load for stage in stages]
        avg_utilization = sum(utilization_scores) / len(utilization_scores)

        # Penalize both under and over utilization
        if avg_utilization < 0.3:
            efficiency = avg_utilization * 100  # Underutilized
        elif avg_utilization > 0.8:
            efficiency = (
                1.0 - (avg_utilization - 0.8) * 2
            ) * 100  # Overutilized
        else:
            efficiency = 100  # Optimal range

        return max(0, min(100, efficiency))

    def _calculate_scalability_score(
        self, stages: List[PipelineStage]
    ) -> float:
        """Calculate scalability score for the pipeline."""
        if not stages:
            return 0.0

        # Score based on parallel capacity and current utilization
        scalability_scores = []
        for stage in stages:
            if stage.parallel_capacity > 1:
                # Can scale horizontally
                scalability = min(
                    100,
                    (stage.parallel_capacity / max(1, stage.current_load))
                    * 20,
                )
            else:
                # Limited scalability
                scalability = 30 if stage.current_load < 0.8 else 10

            scalability_scores.append(scalability)

        return sum(scalability_scores) / len(scalability_scores)

    async def _identify_optimization_opportunities(
        self, stages: List[PipelineStage]
    ) -> List[Dict]:
        """Identify specific optimization opportunities."""
        opportunities = []

        for stage in stages:
            stage_opportunities = []

            # High utilization -> scale
            if stage.current_load > 0.8:
                if stage.parallel_capacity == 1:
                    stage_opportunities.append(
                        {
                            "type": "horizontal_scaling",
                            "description": f"Add parallel processing capacity to {stage.stage_name}",
                            "impact": "high",
                            "effort": "medium",
                        }
                    )
                else:
                    stage_opportunities.append(
                        {
                            "type": "vertical_scaling",
                            "description": f"Increase processing power for {stage.stage_name}",
                            "impact": "medium",
                            "effort": "low",
                        }
                    )

            # Low utilization -> optimize or consolidate
            elif stage.current_load < 0.3:
                stage_opportunities.append(
                    {
                        "type": "resource_optimization",
                        "description": f"Optimize resource allocation for {stage.stage_name}",
                        "impact": "low",
                        "effort": "low",
                    }
                )

            # High execution time -> algorithm optimization
            if stage.execution_time > 5000:  # 5 seconds
                stage_opportunities.append(
                    {
                        "type": "algorithm_optimization",
                        "description": f"Optimize algorithms in {stage.stage_name}",
                        "impact": "high",
                        "effort": "high",
                    }
                )

            if stage_opportunities:
                opportunities.append(
                    {
                        "stage_name": stage.stage_name,
                        "opportunities": stage_opportunities,
                    }
                )

        return opportunities

    async def identify_slow_components(
        self, component_metrics: Dict
    ) -> List[Dict]:
        """Identify slow components based on performance metrics."""
        slow_components = []

        for component_name, metrics_data in component_metrics.items():
            # Create ComponentMetrics object
            metrics = ComponentMetrics(
                component_name=component_name,
                component_type=ComponentType(
                    metrics_data.get("type", "task_processor")
                ),
                response_times=metrics_data.get("response_times", []),
                throughput=metrics_data.get("throughput", 0.0),
                error_rate=metrics_data.get("error_rate", 0.0),
                cpu_usage=metrics_data.get("cpu_usage", 0.0),
                memory_usage=metrics_data.get("memory_usage", 0.0),
            )

            # Analyze component performance
            issues = await self._analyze_component_performance(metrics)

            if issues:
                slow_components.append(
                    {
                        "component_name": component_name,
                        "component_type": metrics.component_type.value,
                        "issues": issues,
                        "performance_score": self._calculate_performance_score(
                            metrics
                        ),
                        "priority": self._calculate_priority(issues),
                    }
                )

        # Sort by priority (higher priority first)
        return sorted(
            slow_components, key=lambda x: x["priority"], reverse=True
        )

    async def _analyze_component_performance(
        self, metrics: ComponentMetrics
    ) -> List[Dict]:
        """Analyze performance issues for a component."""
        issues = []

        # Response time analysis
        if metrics.response_times:
            avg_response_time = statistics.mean(metrics.response_times)
            p95_response_time = (
                statistics.quantiles(metrics.response_times, n=20)[18]
                if len(metrics.response_times) > 10
                else avg_response_time
            )

            if avg_response_time > self.thresholds["response_time_threshold"]:
                issues.append(
                    {
                        "type": "slow_response",
                        "severity": (
                            "high" if avg_response_time > 5000 else "medium"
                        ),
                        "description": f"Average response time {avg_response_time:.0f}ms exceeds threshold",
                        "metric_value": avg_response_time,
                        "threshold": self.thresholds[
                            "response_time_threshold"
                        ],
                    }
                )

            if p95_response_time > avg_response_time * 2:
                issues.append(
                    {
                        "type": "response_variability",
                        "severity": "medium",
                        "description": f"High response time variability (P95: {p95_response_time:.0f}ms)",
                        "metric_value": p95_response_time,
                        "threshold": avg_response_time * 2,
                    }
                )

        # Throughput analysis
        baseline_throughput = self._get_baseline_throughput(
            metrics.component_name
        )
        if (
            baseline_throughput > 0
            and metrics.throughput < baseline_throughput * 0.7
        ):
            issues.append(
                {
                    "type": "low_throughput",
                    "severity": (
                        "high"
                        if metrics.throughput < baseline_throughput * 0.5
                        else "medium"
                    ),
                    "description": f"Throughput {metrics.throughput:.1f} below baseline {baseline_throughput:.1f}",
                    "metric_value": metrics.throughput,
                    "threshold": baseline_throughput * 0.7,
                }
            )

        # Resource usage analysis
        if metrics.cpu_usage > self.thresholds["cpu_threshold"]:
            issues.append(
                {
                    "type": "high_cpu_usage",
                    "severity": (
                        "critical" if metrics.cpu_usage > 95 else "high"
                    ),
                    "description": f"CPU usage {metrics.cpu_usage:.1f}% exceeds threshold",
                    "metric_value": metrics.cpu_usage,
                    "threshold": self.thresholds["cpu_threshold"],
                }
            )

        if metrics.memory_usage > self.thresholds["memory_threshold"]:
            issues.append(
                {
                    "type": "high_memory_usage",
                    "severity": (
                        "critical" if metrics.memory_usage > 95 else "high"
                    ),
                    "description": f"Memory usage {metrics.memory_usage:.1f}% exceeds threshold",
                    "metric_value": metrics.memory_usage,
                    "threshold": self.thresholds["memory_threshold"],
                }
            )

        # Error rate analysis
        if metrics.error_rate > self.thresholds["error_rate_threshold"]:
            issues.append(
                {
                    "type": "high_error_rate",
                    "severity": (
                        "critical" if metrics.error_rate > 10 else "high"
                    ),
                    "description": f"Error rate {metrics.error_rate:.1f}% exceeds threshold",
                    "metric_value": metrics.error_rate,
                    "threshold": self.thresholds["error_rate_threshold"],
                }
            )

        return issues

    def _calculate_performance_score(self, metrics: ComponentMetrics) -> float:
        """Calculate overall performance score for a component."""
        scores = []

        # Response time score
        if metrics.response_times:
            avg_response = statistics.mean(metrics.response_times)
            response_score = max(
                0, 100 - (avg_response / 50)
            )  # Scale response time
            scores.append(response_score)

        # Throughput score (normalized to baseline)
        baseline = self._get_baseline_throughput(metrics.component_name)
        if baseline > 0:
            throughput_score = min(100, (metrics.throughput / baseline) * 100)
            scores.append(throughput_score)

        # Resource efficiency score
        cpu_score = max(0, 100 - metrics.cpu_usage)
        memory_score = max(0, 100 - metrics.memory_usage)
        error_score = max(0, 100 - metrics.error_rate * 10)

        scores.extend([cpu_score, memory_score, error_score])

        return sum(scores) / len(scores) if scores else 0.0

    def _calculate_priority(self, issues: List[Dict]) -> int:
        """Calculate priority for component optimization."""
        priority = 0

        for issue in issues:
            severity = issue["severity"]
            if severity == "critical":
                priority += 10
            elif severity == "high":
                priority += 5
            elif severity == "medium":
                priority += 2
            else:
                priority += 1

        return min(100, priority)

    def _get_baseline_throughput(self, component_name: str) -> float:
        """Get baseline throughput for a component."""
        return self.performance_baselines.get(component_name, {}).get(
            "throughput", 10.0
        )

    def _is_throughput_degraded(self, metrics: ComponentMetrics) -> bool:
        """Check if throughput is degraded compared to baseline."""
        baseline = self._get_baseline_throughput(metrics.component_name)
        if baseline <= 0:
            return False

        return metrics.throughput < baseline * (
            1 - self.thresholds["throughput_degradation"] / 100
        )

    async def suggest_optimization_strategies(
        self, bottlenecks: List[Dict]
    ) -> List[OptimizationRecommendation]:
        """Suggest optimization strategies for detected bottlenecks."""
        recommendations = []

        for i, bottleneck in enumerate(bottlenecks):
            # Generate recommendations based on bottleneck type and severity
            bottleneck_recommendations = (
                await self._generate_bottleneck_recommendations(bottleneck, i)
            )
            recommendations.extend(bottleneck_recommendations)

        # Sort recommendations by priority
        return sorted(recommendations, key=lambda x: x.priority)

    async def _generate_bottleneck_recommendations(
        self, bottleneck: Dict, index: int
    ) -> List[OptimizationRecommendation]:
        """Generate specific recommendations for a bottleneck."""
        recommendations = []
        bottleneck_id = f"bottleneck_{index}_{int(datetime.now().timestamp())}"

        # CPU bottleneck recommendations
        if "cpu" in bottleneck.get("type", "").lower():
            recommendations.append(
                OptimizationRecommendation(
                    recommendation_id=f"{bottleneck_id}_cpu_scale",
                    bottleneck_id=bottleneck_id,
                    strategy=OptimizationStrategy.SCALE_VERTICALLY,
                    description="Increase CPU resources or optimize CPU-intensive operations",
                    estimated_improvement="20-40% performance improvement",
                    implementation_effort="medium",
                    estimated_cost=100.0,
                    priority=2,
                    implementation_steps=[
                        "Analyze CPU-intensive code paths",
                        "Implement CPU optimizations",
                        "Scale CPU resources if needed",
                        "Monitor performance improvements",
                    ],
                    expected_metrics_impact={
                        "cpu_usage": "decrease by 20-30%",
                        "response_time": "improve by 15-25%",
                    },
                )
            )

        # Memory bottleneck recommendations
        if "memory" in bottleneck.get("type", "").lower():
            recommendations.extend(
                [
                    OptimizationRecommendation(
                        recommendation_id=f"{bottleneck_id}_memory_optimize",
                        bottleneck_id=bottleneck_id,
                        strategy=OptimizationStrategy.OPTIMIZE_ALGORITHM,
                        description="Optimize memory usage patterns and implement memory pooling",
                        estimated_improvement="30-50% memory reduction",
                        implementation_effort="high",
                        estimated_cost=50.0,
                        priority=1,
                        implementation_steps=[
                            "Profile memory usage patterns",
                            "Implement memory pooling",
                            "Optimize data structures",
                            "Add memory monitoring",
                        ],
                    ),
                    OptimizationRecommendation(
                        recommendation_id=f"{bottleneck_id}_memory_cache",
                        bottleneck_id=bottleneck_id,
                        strategy=OptimizationStrategy.ADD_CACHING,
                        description="Implement intelligent caching to reduce memory pressure",
                        estimated_improvement="25-40% memory efficiency",
                        implementation_effort="medium",
                        estimated_cost=30.0,
                        priority=3,
                    ),
                ]
            )

        # Queue bottleneck recommendations
        if "queue" in bottleneck.get("type", "").lower():
            recommendations.extend(
                [
                    OptimizationRecommendation(
                        recommendation_id=f"{bottleneck_id}_queue_parallel",
                        bottleneck_id=bottleneck_id,
                        strategy=OptimizationStrategy.SCALE_HORIZONTALLY,
                        description="Add more workers to process queue faster",
                        estimated_improvement="50-100% throughput increase",
                        implementation_effort="low",
                        estimated_cost=75.0,
                        priority=1,
                    ),
                    OptimizationRecommendation(
                        recommendation_id=f"{bottleneck_id}_queue_batch",
                        bottleneck_id=bottleneck_id,
                        strategy=OptimizationStrategy.IMPLEMENT_BATCHING,
                        description="Implement batching to process multiple items together",
                        estimated_improvement="30-60% efficiency gain",
                        implementation_effort="medium",
                        estimated_cost=25.0,
                        priority=2,
                    ),
                ]
            )

        # Response time bottleneck recommendations
        if "response" in bottleneck.get("type", "").lower():
            recommendations.extend(
                [
                    OptimizationRecommendation(
                        recommendation_id=f"{bottleneck_id}_async",
                        bottleneck_id=bottleneck_id,
                        strategy=OptimizationStrategy.ASYNC_PROCESSING,
                        description="Implement asynchronous processing for long-running operations",
                        estimated_improvement="40-70% response time improvement",
                        implementation_effort="high",
                        estimated_cost=80.0,
                        priority=1,
                    ),
                    OptimizationRecommendation(
                        recommendation_id=f"{bottleneck_id}_cache",
                        bottleneck_id=bottleneck_id,
                        strategy=OptimizationStrategy.ADD_CACHING,
                        description="Add response caching for frequently requested data",
                        estimated_improvement="60-80% response time reduction",
                        implementation_effort="medium",
                        estimated_cost=40.0,
                        priority=2,
                    ),
                ]
            )

        return recommendations

    async def update_component_metrics(
        self, component_name: str, metrics_data: Dict
    ):
        """Update metrics for a component."""
        component_type = ComponentType(
            metrics_data.get("type", "task_processor")
        )

        self.component_metrics[component_name] = ComponentMetrics(
            component_name=component_name,
            component_type=component_type,
            response_times=metrics_data.get("response_times", []),
            throughput=metrics_data.get("throughput", 0.0),
            error_rate=metrics_data.get("error_rate", 0.0),
            cpu_usage=metrics_data.get("cpu_usage", 0.0),
            memory_usage=metrics_data.get("memory_usage", 0.0),
            queue_depth=metrics_data.get("queue_depth", 0),
            active_connections=metrics_data.get("active_connections", 0),
            cache_hit_rate=metrics_data.get("cache_hit_rate", 0.0),
        )

    async def get_optimization_report(self) -> Dict:
        """Generate comprehensive optimization report."""
        # Analyze all components
        slow_components = await self.identify_slow_components(
            {
                name: {
                    "type": metrics.component_type.value,
                    "response_times": metrics.response_times,
                    "throughput": metrics.throughput,
                    "error_rate": metrics.error_rate,
                    "cpu_usage": metrics.cpu_usage,
                    "memory_usage": metrics.memory_usage,
                }
                for name, metrics in self.component_metrics.items()
            }
        )

        # Generate optimization strategies
        bottlenecks = [
            comp for comp in slow_components if comp["priority"] > 5
        ]
        recommendations = await self.suggest_optimization_strategies(
            bottlenecks
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_components_analyzed": len(self.component_metrics),
                "slow_components_detected": len(slow_components),
                "critical_bottlenecks": len(
                    [
                        b
                        for b in bottlenecks
                        if any(
                            issue["severity"] == "critical"
                            for issue in b["issues"]
                        )
                    ]
                ),
                "optimization_recommendations": len(recommendations),
            },
            "slow_components": slow_components,
            "optimization_recommendations": [
                {
                    "strategy": rec.strategy.value,
                    "description": rec.description,
                    "estimated_improvement": rec.estimated_improvement,
                    "implementation_effort": rec.implementation_effort,
                    "priority": rec.priority,
                    "estimated_cost": rec.estimated_cost,
                }
                for rec in recommendations[:10]  # Top 10 recommendations
            ],
            "performance_trends": await self._analyze_performance_trends(),
            "system_health_score": await self._calculate_system_health_score(),
        }

    async def _analyze_performance_trends(self) -> Dict:
        """Analyze performance trends across components."""
        trends = {
            "improving_components": [],
            "degrading_components": [],
            "stable_components": [],
        }

        for component_name, metrics in self.component_metrics.items():
            # Simplified trend analysis
            baseline_score = self._get_baseline_performance_score(
                component_name
            )
            current_score = self._calculate_performance_score(metrics)

            change_percent = (
                (current_score - baseline_score) / max(1, baseline_score)
            ) * 100

            if change_percent > 10:
                trends["improving_components"].append(
                    {
                        "component": component_name,
                        "improvement": f"{change_percent:.1f}%",
                    }
                )
            elif change_percent < -10:
                trends["degrading_components"].append(
                    {
                        "component": component_name,
                        "degradation": f"{abs(change_percent):.1f}%",
                    }
                )
            else:
                trends["stable_components"].append(component_name)

        return trends

    def _get_baseline_performance_score(self, component_name: str) -> float:
        """Get baseline performance score for a component."""
        return self.performance_baselines.get(component_name, {}).get(
            "performance_score", 70.0
        )

    async def _calculate_system_health_score(self) -> float:
        """Calculate overall system health score."""
        if not self.component_metrics:
            return 0.0

        scores = []
        for metrics in self.component_metrics.values():
            component_score = self._calculate_performance_score(metrics)
            scores.append(component_score)

        return sum(scores) / len(scores)

    def set_performance_baseline(
        self, component_name: str, baseline_metrics: Dict
    ):
        """Set performance baseline for a component."""
        self.performance_baselines[component_name] = baseline_metrics

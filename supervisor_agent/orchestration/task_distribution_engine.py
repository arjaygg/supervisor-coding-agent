"""Task Distribution Engine
Intelligent task splitting and distribution across providers.

This module implements advanced task distribution capabilities including:
- Intelligent task complexity analysis and splitting
- Dependency-aware distribution with execution planning
- Cross-provider coordination and load balancing
- Integration with agent specialization and multi-provider systems

Follows SOLID principles and integrates seamlessly with existing architecture.
"""

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import structlog

from supervisor_agent.core.dag_resolver import DAGResolver
from supervisor_agent.core.multi_provider_service import MultiProviderService
from supervisor_agent.db.enums import TaskStatus
from supervisor_agent.db.models import Task, TaskType
from supervisor_agent.orchestration.agent_specialization_engine import (
    AgentSpecializationEngine,
    AgentSpecialty,
)
from supervisor_agent.orchestration.multi_provider_coordinator import (
    CoordinationStrategy,
    MultiProviderCoordinator,
    ProviderMetrics,
)
from supervisor_agent.providers.base_provider import (
    AIProvider,
    ProviderType,
    TaskCapability,
)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
structured_logger = structlog.get_logger(__name__)


class DistributionStrategy(Enum):
    """Task distribution strategies."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEPENDENCY_AWARE = "dependency_aware"
    LOAD_BALANCED = "load_balanced"
    CAPABILITY_OPTIMIZED = "capability_optimized"
    COST_OPTIMIZED = "cost_optimized"
    PERFORMANCE_OPTIMIZED = "performance_optimized"


class TaskComplexity(Enum):
    """Task complexity levels for splitting decisions."""

    SIMPLE = "simple"  # Single-step, atomic tasks
    MODERATE = "moderate"  # 2-5 logical steps
    COMPLEX = "complex"  # 6-20 steps with dependencies
    HIGHLY_COMPLEX = "highly_complex"  # >20 steps, complex dependencies


class SplittingStrategy(Enum):
    """Strategies for task splitting."""

    NO_SPLIT = "no_split"  # Keep task atomic
    LINEAR_SPLIT = "linear_split"  # Sequential subtasks
    PARALLEL_SPLIT = "parallel_split"  # Independent parallel subtasks
    HIERARCHICAL_SPLIT = "hierarchical_split"  # Tree-like dependency structure
    PIPELINE_SPLIT = "pipeline_split"  # Data pipeline stages


@dataclass
class ComplexityAnalysis:
    """Analysis result for task complexity."""

    complexity_level: TaskComplexity
    estimated_steps: int
    identified_dependencies: List[str]
    splitting_recommendation: SplittingStrategy
    estimated_execution_time: int  # seconds
    resource_requirements: Dict[str, Any]
    confidence_score: float  # 0.0-1.0
    reasoning: str


@dataclass
class TaskSplit:
    """Represents a split task with enhanced metadata."""

    split_id: str
    original_task_id: str
    subtask_index: int
    task_type: TaskCapability
    agent_specialty: AgentSpecialty
    priority: int
    estimated_duration: int  # seconds
    dependencies: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    provider_preferences: List[ProviderType] = field(default_factory=list)
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    parallelizable: bool = True
    critical_path: bool = False


@dataclass
class DependencyGraph:
    """Represents task dependencies and execution order."""

    nodes: Dict[str, TaskSplit]
    edges: Dict[str, List[str]]  # node_id -> list of dependent node_ids
    execution_levels: List[List[str]]  # Levels for parallel execution
    critical_path: List[str]
    total_estimated_time: int
    parallelization_potential: float  # 0.0-1.0


@dataclass
class ExecutionPlan:
    """Execution plan for distributed task."""

    plan_id: str
    original_task_id: str
    dependency_graph: DependencyGraph
    provider_assignments: Dict[str, ProviderType]  # split_id -> provider
    execution_strategy: DistributionStrategy
    estimated_total_time: int
    estimated_cost: float
    resource_allocation: Dict[str, Dict[str, Any]]
    fallback_plans: List["ExecutionPlan"] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DistributionResult:
    """Result of task distribution with comprehensive metadata."""

    original_task_id: str
    strategy_used: DistributionStrategy
    task_splits: List[TaskSplit]
    execution_plan: Optional[ExecutionPlan]
    complexity_analysis: ComplexityAnalysis
    success: bool
    processing_time: float  # seconds
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class IntelligentTaskSplitter:
    """Analyzes task complexity and generates optimal splitting strategies."""

    def __init__(self):
        self.logger = structured_logger.bind(component="task_splitter")
        self._complexity_patterns = self._load_complexity_patterns()
        self._splitting_rules = self._load_splitting_rules()

    def _load_complexity_patterns(self) -> Dict[str, Any]:
        """Load patterns for complexity analysis."""
        return {
            "keywords": {
                "simple": ["show", "display", "get", "fetch", "read"],
                "moderate": ["create", "update", "process", "transform", "validate"],
                "complex": [
                    "analyze",
                    "optimize",
                    "integrate",
                    "coordinate",
                    "orchestrate",
                ],
                "highly_complex": [
                    "architect",
                    "design system",
                    "full implementation",
                    "end-to-end",
                ],
            },
            "step_indicators": ["then", "after", "next", "followed by", "subsequently"],
            "dependency_indicators": [
                "depends on",
                "requires",
                "needs",
                "after completing",
            ],
            "parallel_indicators": [
                "simultaneously",
                "in parallel",
                "concurrently",
                "at the same time",
            ],
        }

    def _load_splitting_rules(self) -> Dict[str, Any]:
        """Load rules for splitting decisions."""
        return {
            "no_split_conditions": [
                "atomic operation",
                "single API call",
                "simple query",
                "basic transformation",
            ],
            "linear_split_indicators": [
                "step-by-step",
                "sequential process",
                "workflow",
                "procedure",
            ],
            "parallel_split_indicators": [
                "independent tasks",
                "multiple components",
                "parallel processing",
                "concurrent execution",
            ],
        }

    def analyze_task_complexity(self, task: Task) -> ComplexityAnalysis:
        """Analyze task complexity and determine splitting strategy."""
        self.logger.info("Analyzing task complexity", task_id=task.id)

        try:
            # Extract task content for analysis
            task_content = self._extract_task_content(task)

            # Analyze complexity indicators
            complexity_score = self._calculate_complexity_score(task_content)
            estimated_steps = self._estimate_steps(task_content)
            dependencies = self._identify_dependencies(task_content)

            # Determine complexity level
            complexity_level = self._determine_complexity_level(
                complexity_score, estimated_steps
            )

            # Recommend splitting strategy
            splitting_strategy = self._recommend_splitting_strategy(
                complexity_level, task_content, dependencies
            )

            # Estimate resource requirements
            resource_requirements = self._estimate_resource_requirements(
                complexity_level, estimated_steps
            )

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                complexity_score, len(dependencies), task_content
            )

            # Generate reasoning
            reasoning = self._generate_reasoning(
                complexity_level, splitting_strategy, estimated_steps, dependencies
            )

            analysis = ComplexityAnalysis(
                complexity_level=complexity_level,
                estimated_steps=estimated_steps,
                identified_dependencies=dependencies,
                splitting_recommendation=splitting_strategy,
                estimated_execution_time=self._estimate_execution_time(
                    estimated_steps, complexity_level
                ),
                resource_requirements=resource_requirements,
                confidence_score=confidence_score,
                reasoning=reasoning,
            )

            self.logger.info(
                "Task complexity analysis completed",
                task_id=task.id,
                complexity=complexity_level.value,
                estimated_steps=estimated_steps,
                confidence=confidence_score,
            )

            return analysis

        except Exception as e:
            self.logger.error(
                "Error analyzing task complexity", task_id=task.id, error=str(e)
            )
            # Return safe default analysis
            return ComplexityAnalysis(
                complexity_level=TaskComplexity.MODERATE,
                estimated_steps=3,
                identified_dependencies=[],
                splitting_recommendation=SplittingStrategy.LINEAR_SPLIT,
                estimated_execution_time=300,  # 5 minutes
                resource_requirements={"cpu": "medium", "memory": "medium"},
                confidence_score=0.3,
                reasoning="Default analysis due to processing error",
            )

    def _extract_task_content(self, task: Task) -> str:
        """Extract analyzable content from task."""
        content_parts = []

        if task.payload:
            if isinstance(task.payload, dict):
                # Extract text from common payload fields
                for field in [
                    "description",
                    "prompt",
                    "instructions",
                    "content",
                    "message",
                ]:
                    if field in task.payload:
                        content_parts.append(str(task.payload[field]))
            else:
                content_parts.append(str(task.payload))

        return " ".join(content_parts).lower()

    def _calculate_complexity_score(self, content: str) -> float:
        """Calculate complexity score based on content analysis."""
        score = 0.0

        # Keyword-based scoring
        for complexity, keywords in self._complexity_patterns["keywords"].items():
            matches = sum(1 for keyword in keywords if keyword in content)
            if complexity == "simple":
                score += matches * 0.1
            elif complexity == "moderate":
                score += matches * 0.3
            elif complexity == "complex":
                score += matches * 0.6
            elif complexity == "highly_complex":
                score += matches * 1.0

        # Step indicator scoring
        step_matches = sum(
            1
            for indicator in self._complexity_patterns["step_indicators"]
            if indicator in content
        )
        score += step_matches * 0.2

        # Dependency indicator scoring
        dep_matches = sum(
            1
            for indicator in self._complexity_patterns["dependency_indicators"]
            if indicator in content
        )
        score += dep_matches * 0.3

        # Length-based scoring
        word_count = len(content.split())
        if word_count > 100:
            score += 0.5
        elif word_count > 50:
            score += 0.3
        elif word_count > 20:
            score += 0.1

        return min(score, 3.0)  # Cap at 3.0

    def _estimate_steps(self, content: str) -> int:
        """Estimate number of logical steps in task."""
        base_steps = 1

        # Count step indicators
        step_count = sum(
            1
            for indicator in self._complexity_patterns["step_indicators"]
            if indicator in content
        )

        # Count bullet points, numbers, etc.
        step_count += content.count("1.")
        step_count += content.count("2.")
        step_count += content.count("3.")
        step_count += content.count("•")
        step_count += content.count("-")

        # Estimate based on length and complexity keywords
        word_count = len(content.split())
        estimated_from_length = max(1, word_count // 20)

        return max(base_steps, step_count, estimated_from_length)

    def _identify_dependencies(self, content: str) -> List[str]:
        """Identify potential dependencies in task content."""
        dependencies = []

        # Look for explicit dependency indicators
        for indicator in self._complexity_patterns["dependency_indicators"]:
            if indicator in content:
                # Try to extract what comes after the indicator
                parts = content.split(indicator, 1)
                if len(parts) > 1:
                    dependency_text = parts[1].split(".")[0].strip()
                    if dependency_text and len(dependency_text) < 100:
                        dependencies.append(dependency_text)

        # Look for references to other systems, APIs, or components
        common_dependencies = [
            "database",
            "api",
            "service",
            "component",
            "module",
            "authentication",
            "authorization",
            "validation",
            "configuration",
        ]

        for dep in common_dependencies:
            if dep in content:
                dependencies.append(dep)

        return list(set(dependencies))  # Remove duplicates

    def _determine_complexity_level(self, score: float, steps: int) -> TaskComplexity:
        """Determine overall complexity level."""
        if score <= 0.5 and steps <= 2:
            return TaskComplexity.SIMPLE
        elif score <= 1.0 and steps <= 5:
            return TaskComplexity.MODERATE
        elif score <= 2.0 and steps <= 20:
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.HIGHLY_COMPLEX

    def _recommend_splitting_strategy(
        self, complexity: TaskComplexity, content: str, dependencies: List[str]
    ) -> SplittingStrategy:
        """Recommend optimal splitting strategy."""
        # Simple tasks shouldn't be split
        if complexity == TaskComplexity.SIMPLE:
            return SplittingStrategy.NO_SPLIT

        # Check for parallel indicators
        parallel_indicators = sum(
            1
            for indicator in self._complexity_patterns["parallel_indicators"]
            if indicator in content
        )

        if parallel_indicators > 0 and len(dependencies) <= 2:
            return SplittingStrategy.PARALLEL_SPLIT

        # Check for linear process indicators
        linear_indicators = sum(
            1
            for indicator in self._splitting_rules["linear_split_indicators"]
            if indicator in content
        )

        if linear_indicators > 0:
            return SplittingStrategy.LINEAR_SPLIT

        # Complex tasks with many dependencies need hierarchical splitting
        if (
            complexity in [TaskComplexity.COMPLEX, TaskComplexity.HIGHLY_COMPLEX]
            and len(dependencies) > 3
        ):
            return SplittingStrategy.HIERARCHICAL_SPLIT

        # Default to linear for moderate complexity
        return SplittingStrategy.LINEAR_SPLIT

    def _estimate_resource_requirements(
        self, complexity: TaskComplexity, steps: int
    ) -> Dict[str, Any]:
        """Estimate resource requirements based on complexity."""
        base_requirements = {
            TaskComplexity.SIMPLE: {"cpu": "low", "memory": "low", "io": "low"},
            TaskComplexity.MODERATE: {
                "cpu": "medium",
                "memory": "medium",
                "io": "medium",
            },
            TaskComplexity.COMPLEX: {"cpu": "high", "memory": "high", "io": "medium"},
            TaskComplexity.HIGHLY_COMPLEX: {
                "cpu": "very_high",
                "memory": "very_high",
                "io": "high",
            },
        }

        requirements = base_requirements[complexity].copy()
        requirements["estimated_tokens"] = steps * 1000  # Rough estimate
        requirements["concurrent_limit"] = min(5, max(1, steps // 3))

        return requirements

    def _calculate_confidence_score(
        self, complexity_score: float, dependency_count: int, content: str
    ) -> float:
        """Calculate confidence in the analysis."""
        confidence = 0.5  # Base confidence

        # Higher confidence for clear indicators
        if complexity_score > 1.0:
            confidence += 0.2

        # Higher confidence for explicit dependencies
        if dependency_count > 0:
            confidence += 0.1

        # Higher confidence for longer, more detailed content
        word_count = len(content.split())
        if word_count > 50:
            confidence += 0.1
        elif word_count < 10:
            confidence -= 0.2

        return max(0.1, min(1.0, confidence))

    def _generate_reasoning(
        self,
        complexity: TaskComplexity,
        strategy: SplittingStrategy,
        steps: int,
        dependencies: List[str],
    ) -> str:
        """Generate human-readable reasoning for the analysis."""
        reasoning_parts = [
            f"Task classified as {complexity.value} based on estimated {steps} steps"
        ]

        if dependencies:
            reasoning_parts.append(
                f"Identified {len(dependencies)} dependencies: {', '.join(dependencies[:3])}"
            )

        strategy_explanations = {
            SplittingStrategy.NO_SPLIT: "Task is atomic and should not be split",
            SplittingStrategy.LINEAR_SPLIT: "Task has sequential dependencies requiring linear execution",
            SplittingStrategy.PARALLEL_SPLIT: "Task has independent components suitable for parallel execution",
            SplittingStrategy.HIERARCHICAL_SPLIT: "Task has complex dependencies requiring hierarchical coordination",
            SplittingStrategy.PIPELINE_SPLIT: "Task follows a data pipeline pattern",
        }

        reasoning_parts.append(strategy_explanations[strategy])

        return ". ".join(reasoning_parts)

    def _estimate_execution_time(self, steps: int, complexity: TaskComplexity) -> int:
        """Estimate execution time in seconds."""
        base_time_per_step = {
            TaskComplexity.SIMPLE: 30,
            TaskComplexity.MODERATE: 60,
            TaskComplexity.COMPLEX: 120,
            TaskComplexity.HIGHLY_COMPLEX: 300,
        }

        return steps * base_time_per_step[complexity]


class DependencyManager:
    """Manages task dependencies and execution ordering."""

    def __init__(self, dag_resolver: Optional[DAGResolver] = None):
        self.logger = structured_logger.bind(component="dependency_manager")
        self.dag_resolver = dag_resolver or DAGResolver()

    def build_dependency_graph(self, tasks: List[TaskSplit]) -> DependencyGraph:
        """Build dependency graph from task splits."""
        self.logger.info("Building dependency graph", task_count=len(tasks))

        # Create nodes dictionary
        nodes = {task.split_id: task for task in tasks}

        # Build edges from dependencies
        edges = {}
        for task in tasks:
            edges[task.split_id] = task.dependencies.copy()

        # Validate no circular dependencies
        if self._has_circular_dependencies(edges):
            self.logger.warning("Circular dependencies detected")
            # Try to resolve by removing problematic edges
            edges = self._resolve_circular_dependencies(edges)

        # Calculate execution levels
        execution_levels = self._calculate_execution_levels(tasks, edges)

        # Identify critical path
        critical_path = self._identify_critical_path(tasks, edges)

        # Calculate total time and parallelization potential
        total_time = sum(
            max(nodes[task_id].estimated_duration for task_id in level)
            for level in execution_levels
        )

        parallelization_potential = self._calculate_parallelization_potential(
            execution_levels, tasks
        )

        graph = DependencyGraph(
            nodes=nodes,
            edges=edges,
            execution_levels=execution_levels,
            critical_path=critical_path,
            total_estimated_time=total_time,
            parallelization_potential=parallelization_potential,
        )

        self.logger.info(
            "Dependency graph built",
            nodes=len(nodes),
            edges=sum(len(deps) for deps in edges.values()),
            levels=len(execution_levels),
            total_time=total_time,
            parallelization=parallelization_potential,
        )

        return graph

    def _has_circular_dependencies(self, edges: Dict[str, List[str]]) -> bool:
        """Check for circular dependencies using DFS."""
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            if node in rec_stack:
                return True
            if node in visited:
                return False

            visited.add(node)
            rec_stack.add(node)

            for neighbor in edges.get(node, []):
                if has_cycle(neighbor):
                    return True

            rec_stack.remove(node)
            return False

        for node in edges:
            if node not in visited:
                if has_cycle(node):
                    return True

        return False

    def _resolve_circular_dependencies(
        self, edges: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """Attempt to resolve circular dependencies by removing problematic edges."""
        # Simple strategy: remove edges that create cycles
        resolved_edges = {node: [] for node in edges}

        # Add edges one by one, skipping those that create cycles
        for node, deps in edges.items():
            for dep in deps:
                test_edges = {k: v.copy() for k, v in resolved_edges.items()}
                test_edges[node].append(dep)

                if not self._has_circular_dependencies(test_edges):
                    resolved_edges[node].append(dep)
                else:
                    self.logger.warning(
                        "Removing circular dependency", from_node=node, to_node=dep
                    )

        return resolved_edges

    def _calculate_execution_levels(
        self, tasks: List[TaskSplit], edges: Dict[str, List[str]]
    ) -> List[List[str]]:
        """Calculate execution levels for parallel execution."""
        levels = []
        processed = set()

        while len(processed) < len(tasks):
            current_level = []

            for task in tasks:
                if task.split_id in processed:
                    continue

                # Check if all dependencies are satisfied
                dependencies_satisfied = all(
                    dep in processed for dep in edges.get(task.split_id, [])
                )

                if dependencies_satisfied:
                    current_level.append(task.split_id)

            if not current_level:
                # Break to avoid infinite loop
                break

            levels.append(current_level)
            processed.update(current_level)

        return levels

    def _identify_critical_path(
        self, tasks: List[TaskSplit], edges: Dict[str, List[str]]
    ) -> List[str]:
        """Identify the critical path through the dependency graph."""
        task_dict = {task.split_id: task for task in tasks}

        # Use topological sort to find longest path
        in_degree = {task.split_id: 0 for task in tasks}
        for deps in edges.values():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] += 1

        # Find path with maximum total duration
        distances = {task.split_id: 0 for task in tasks}
        predecessors = {task.split_id: None for task in tasks}

        # Process nodes in topological order
        queue = [node for node, degree in in_degree.items() if degree == 0]

        while queue:
            current = queue.pop(0)
            current_distance = (
                distances[current] + task_dict[current].estimated_duration
            )

            # Update distances to dependent nodes
            dependents = [node for node, deps in edges.items() if current in deps]
            for dependent in dependents:
                if current_distance > distances[dependent]:
                    distances[dependent] = current_distance
                    predecessors[dependent] = current

                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Reconstruct critical path
        max_distance_node = max(distances, key=distances.get)
        critical_path = []
        current = max_distance_node

        while current is not None:
            critical_path.append(current)
            current = predecessors[current]

        return list(reversed(critical_path))

    def _calculate_parallelization_potential(
        self, execution_levels: List[List[str]], tasks: List[TaskSplit]
    ) -> float:
        """Calculate parallelization potential (0.0-1.0)."""
        if not execution_levels or len(tasks) <= 1:
            return 0.0

        # Calculate what percentage of tasks can run in parallel
        max_parallel = max(len(level) for level in execution_levels)
        total_tasks = len(tasks)

        return min(1.0, max_parallel / total_tasks)


class TaskDistributionEngine:
    """Advanced task distribution engine with intelligent splitting and coordination."""

    def __init__(
        self,
        agent_specialization_engine: Optional[AgentSpecializationEngine] = None,
        multi_provider_coordinator: Optional[MultiProviderCoordinator] = None,
        task_splitter: Optional[IntelligentTaskSplitter] = None,
        dependency_manager: Optional[DependencyManager] = None,
    ):
        self.logger = structured_logger.bind(component="task_distribution_engine")

        # Initialize components
        self.agent_specialization_engine = (
            agent_specialization_engine or AgentSpecializationEngine()
        )
        if multi_provider_coordinator is None:
            # Create a default MultiProviderService for the coordinator
            provider_service = MultiProviderService()
            self.multi_provider_coordinator = MultiProviderCoordinator(
                provider_service=provider_service
            )
        else:
            self.multi_provider_coordinator = multi_provider_coordinator
        self.task_splitter = task_splitter or IntelligentTaskSplitter()
        self.dependency_manager = dependency_manager or DependencyManager()

        # Internal state
        self._execution_plans: Dict[str, ExecutionPlan] = {}
        self._active_distributions: Dict[str, DistributionResult] = {}

    async def distribute_task(
        self,
        task: Union[Task, str],
        strategy: DistributionStrategy = DistributionStrategy.DEPENDENCY_AWARE,
        providers: Optional[List[ProviderType]] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> DistributionResult:
        """Distribute a task using intelligent analysis and optimization."""
        start_time = datetime.now(timezone.utc)

        try:
            # Handle both Task objects and task IDs
            if isinstance(task, str):
                task_obj = await self._load_task(task)
                task_id = task
            else:
                task_obj = task
                task_id = str(task.id)

            self.logger.info(
                "Starting task distribution", task_id=task_id, strategy=strategy.value
            )

            # Step 1: Analyze task complexity
            complexity_analysis = self.task_splitter.analyze_task_complexity(task_obj)

            self.logger.info(
                "Task complexity analyzed",
                task_id=task_id,
                complexity=complexity_analysis.complexity_level.value,
                estimated_steps=complexity_analysis.estimated_steps,
                splitting_strategy=complexity_analysis.splitting_recommendation.value,
            )

            # Step 2: Generate task splits based on complexity
            task_splits = await self._generate_task_splits(
                task_obj, complexity_analysis
            )

            # Step 3: Build dependency graph
            dependency_graph = self.dependency_manager.build_dependency_graph(
                task_splits
            )

            # Step 4: Optimize distribution strategy
            optimized_strategy = await self._optimize_distribution_strategy(
                task_obj, strategy, complexity_analysis, dependency_graph, constraints
            )

            # Step 5: Create execution plan
            execution_plan = await self._create_execution_plan(
                task_obj, dependency_graph, optimized_strategy, providers, constraints
            )

            # Step 6: Validate execution plan
            validation_result = await self._validate_execution_plan(execution_plan)

            recommendations = []
            warnings = []

            if not validation_result["valid"]:
                warnings.extend(validation_result["warnings"])
                recommendations.extend(validation_result["recommendations"])

            # Step 7: Store execution plan
            self._execution_plans[execution_plan.plan_id] = execution_plan

            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            result = DistributionResult(
                original_task_id=task_id,
                strategy_used=optimized_strategy,
                task_splits=task_splits,
                execution_plan=execution_plan,
                complexity_analysis=complexity_analysis,
                success=True,
                processing_time=processing_time,
                recommendations=recommendations,
                warnings=warnings,
                metadata={
                    "total_subtasks": len(task_splits),
                    "execution_levels": len(dependency_graph.execution_levels),
                    "parallelization_potential": dependency_graph.parallelization_potential,
                    "critical_path_length": len(dependency_graph.critical_path),
                    "estimated_total_time": dependency_graph.total_estimated_time,
                },
            )

            self._active_distributions[task_id] = result

            self.logger.info(
                "Task distribution completed successfully",
                task_id=task_id,
                subtasks=len(task_splits),
                strategy=optimized_strategy.value,
                processing_time=processing_time,
            )

            return result

        except Exception as e:
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            error_msg = f"Task distribution failed: {str(e)}"

            self.logger.error(
                "Task distribution failed",
                task_id=task_id if "task_id" in locals() else "unknown",
                error=str(e),
                processing_time=processing_time,
            )

            return DistributionResult(
                original_task_id=task_id if "task_id" in locals() else "unknown",
                strategy_used=strategy,
                task_splits=[],
                execution_plan=None,
                complexity_analysis=ComplexityAnalysis(
                    complexity_level=TaskComplexity.SIMPLE,
                    estimated_steps=1,
                    identified_dependencies=[],
                    splitting_recommendation=SplittingStrategy.NO_SPLIT,
                    estimated_execution_time=300,
                    resource_requirements={},
                    confidence_score=0.0,
                    reasoning="Error occurred during analysis",
                ),
                success=False,
                processing_time=processing_time,
                error_message=error_msg,
            )

    async def _load_task(self, task_id: str) -> Task:
        """Load task from database."""
        # This would typically query the database
        # For now, create a mock task object
        return Task(
            id=int(task_id),
            type=TaskType.ANALYSIS,
            status=TaskStatus.PENDING,
            payload={"description": f"Task {task_id}"},
            priority=5,
        )

    async def _generate_task_splits(
        self, task: Task, analysis: ComplexityAnalysis
    ) -> List[TaskSplit]:
        """Generate task splits based on complexity analysis."""
        self.logger.info("Generating task splits", task_id=task.id)

        if analysis.splitting_recommendation == SplittingStrategy.NO_SPLIT:
            # Single task, no splitting
            return [
                TaskSplit(
                    split_id=f"{task.id}_0",
                    original_task_id=str(task.id),
                    subtask_index=0,
                    task_type=TaskCapability.GENERAL,
                    agent_specialty=AgentSpecialty.GENERAL_DEVELOPER,
                    priority=task.priority or 5,
                    estimated_duration=analysis.estimated_execution_time,
                    metadata={"original_task": True, "no_split": True},
                )
            ]

        # Generate splits based on strategy
        task_splits = self._create_task_splits_by_strategy(task, analysis)

        self.logger.info(
            "Task splits generated", task_id=task.id, splits_count=len(task_splits)
        )

        return task_splits

    def _create_task_splits_by_strategy(
        self, task: Task, analysis: ComplexityAnalysis
    ) -> List[TaskSplit]:
        """Create task splits based on splitting strategy."""
        task_splits = []

        if analysis.splitting_recommendation == SplittingStrategy.LINEAR_SPLIT:
            # Create sequential subtasks
            step_duration = (
                analysis.estimated_execution_time // analysis.estimated_steps
            )

            for i in range(analysis.estimated_steps):
                task_splits.append(
                    TaskSplit(
                        split_id=f"{task.id}_{i}",
                        original_task_id=str(task.id),
                        subtask_index=i,
                        task_type=self._determine_subtask_type(
                            i, analysis.estimated_steps
                        ),
                        agent_specialty=self._determine_agent_specialty(
                            i, analysis.estimated_steps
                        ),
                        priority=task.priority or 5,
                        estimated_duration=step_duration,
                        dependencies=[f"{task.id}_{i-1}"] if i > 0 else [],
                        parallelizable=False,
                    )
                )

        elif analysis.splitting_recommendation == SplittingStrategy.PARALLEL_SPLIT:
            # Create parallel subtasks
            parallel_count = min(4, max(2, analysis.estimated_steps // 2))
            step_duration = analysis.estimated_execution_time // parallel_count

            for i in range(parallel_count):
                task_splits.append(
                    TaskSplit(
                        split_id=f"{task.id}_{i}",
                        original_task_id=str(task.id),
                        subtask_index=i,
                        task_type=self._determine_subtask_type(i, parallel_count),
                        agent_specialty=self._determine_agent_specialty(
                            i, parallel_count
                        ),
                        priority=task.priority or 5,
                        estimated_duration=step_duration,
                        parallelizable=True,
                    )
                )

        elif analysis.splitting_recommendation == SplittingStrategy.HIERARCHICAL_SPLIT:
            # Create hierarchical subtasks
            task_splits.extend(self._create_hierarchical_subtasks(task, analysis))

        return task_splits

    def _determine_subtask_type(self, index: int, total: int) -> TaskCapability:
        """Determine task capability for subtask based on position."""
        if index == 0:
            return TaskCapability.ANALYSIS
        elif index == total - 1:
            return TaskCapability.VALIDATION
        else:
            return TaskCapability.PROCESSING

    def _determine_agent_specialty(self, index: int, total: int) -> AgentSpecialty:
        """Determine agent specialty for subtask based on position."""
        specialties = [
            AgentSpecialty.CODE_ARCHITECT,
            AgentSpecialty.GENERAL_DEVELOPER,
            AgentSpecialty.CODE_REVIEWER,
            AgentSpecialty.TEST_ENGINEER,
        ]
        return specialties[index % len(specialties)]

    def _create_hierarchical_subtasks(
        self, task: Task, analysis: ComplexityAnalysis
    ) -> List[TaskSplit]:
        """Create hierarchical subtask structure."""
        subtasks = []

        # Planning phase
        subtasks.append(
            TaskSplit(
                split_id=f"{task.id}_plan",
                original_task_id=str(task.id),
                subtask_index=0,
                task_type=TaskCapability.ANALYSIS,
                agent_specialty=AgentSpecialty.CODE_ARCHITECT,
                priority=task.priority or 5,
                estimated_duration=analysis.estimated_execution_time // 10,
                parallelizable=False,
            )
        )

        # Implementation phases
        impl_count = max(2, analysis.estimated_steps - 2)
        impl_duration = int((analysis.estimated_execution_time * 0.7) // impl_count)

        for i in range(impl_count):
            subtasks.append(
                TaskSplit(
                    split_id=f"{task.id}_impl_{i}",
                    original_task_id=str(task.id),
                    subtask_index=i + 1,
                    task_type=TaskCapability.PROCESSING,
                    agent_specialty=AgentSpecialty.GENERAL_DEVELOPER,
                    priority=task.priority or 5,
                    estimated_duration=impl_duration,
                    dependencies=[f"{task.id}_plan"],
                    parallelizable=True,
                )
            )

        # Validation phase
        subtasks.append(
            TaskSplit(
                split_id=f"{task.id}_validate",
                original_task_id=str(task.id),
                subtask_index=len(subtasks),
                task_type=TaskCapability.VALIDATION,
                agent_specialty=AgentSpecialty.TEST_ENGINEER,
                priority=task.priority or 5,
                estimated_duration=analysis.estimated_execution_time // 5,
                dependencies=[f"{task.id}_impl_{i}" for i in range(impl_count)],
                parallelizable=False,
            )
        )

        return subtasks

    async def _optimize_distribution_strategy(
        self,
        task: Task,
        requested_strategy: DistributionStrategy,
        complexity_analysis: ComplexityAnalysis,
        dependency_graph: DependencyGraph,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> DistributionStrategy:
        """Optimize the distribution strategy based on analysis."""
        constraints = constraints or {}

        self.logger.info(
            "Optimizing distribution strategy",
            task_id=task.id,
            requested_strategy=requested_strategy.value,
        )

        # If task is simple, force sequential
        if complexity_analysis.complexity_level == TaskComplexity.SIMPLE:
            return DistributionStrategy.SEQUENTIAL

        # Check for parallelization potential
        if dependency_graph.parallelization_potential > 0.7:
            if requested_strategy in [
                DistributionStrategy.PARALLEL,
                DistributionStrategy.DEPENDENCY_AWARE,
            ]:
                return DistributionStrategy.PARALLEL

        # Check for cost optimization requirements
        if constraints.get("optimize_cost", False):
            return DistributionStrategy.COST_OPTIMIZED

        # Check for performance optimization requirements
        if constraints.get("optimize_performance", False):
            return DistributionStrategy.PERFORMANCE_OPTIMIZED

        # Default to dependency-aware for complex tasks
        if complexity_analysis.complexity_level in [
            TaskComplexity.COMPLEX,
            TaskComplexity.HIGHLY_COMPLEX,
        ]:
            return DistributionStrategy.DEPENDENCY_AWARE

        return requested_strategy

    async def _create_execution_plan(
        self,
        task: Task,
        dependency_graph: DependencyGraph,
        strategy: DistributionStrategy,
        providers: Optional[List[ProviderType]] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPlan:
        """Create detailed execution plan."""
        self.logger.info("Creating execution plan", task_id=task.id)

        # Generate provider assignments
        provider_assignments = await self._assign_providers(
            list(dependency_graph.nodes.values()), providers, strategy
        )

        # Calculate resource allocation
        resource_allocation = self._calculate_resource_allocation(
            list(dependency_graph.nodes.values()), provider_assignments
        )

        # Estimate cost
        estimated_cost = self._estimate_execution_cost(
            list(dependency_graph.nodes.values()), provider_assignments
        )

        plan = ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            original_task_id=str(task.id),
            dependency_graph=dependency_graph,
            provider_assignments=provider_assignments,
            execution_strategy=strategy,
            estimated_total_time=dependency_graph.total_estimated_time,
            estimated_cost=estimated_cost,
            resource_allocation=resource_allocation,
        )

        self.logger.info(
            "Execution plan created",
            plan_id=plan.plan_id,
            estimated_time=plan.estimated_total_time,
            estimated_cost=plan.estimated_cost,
        )

        return plan

    async def _assign_providers(
        self,
        task_splits: List[TaskSplit],
        preferred_providers: Optional[List[ProviderType]] = None,
        strategy: DistributionStrategy = DistributionStrategy.LOAD_BALANCED,
    ) -> Dict[str, ProviderType]:
        """Assign providers to task splits."""
        assignments = {}

        # Get available providers
        try:
            available_providers = (
                await self.multi_provider_coordinator.get_available_providers()
            )
        except:
            available_providers = [ProviderType.CLAUDE_CLI]  # Fallback

        if preferred_providers:
            available_providers = [
                p for p in available_providers if p in preferred_providers
            ]

        if not available_providers:
            available_providers = [ProviderType.CLAUDE_CLI]

        # Assign based on strategy
        if strategy == DistributionStrategy.LOAD_BALANCED:
            # Round-robin assignment
            for i, split in enumerate(task_splits):
                assignments[split.split_id] = available_providers[
                    i % len(available_providers)
                ]
        else:
            # Default assignment
            primary_provider = available_providers[0]
            for split in task_splits:
                assignments[split.split_id] = primary_provider

        return assignments

    def _calculate_resource_allocation(
        self,
        task_splits: List[TaskSplit],
        provider_assignments: Dict[str, ProviderType],
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate resource allocation for each task split."""
        allocation = {}

        for split in task_splits:
            allocation[split.split_id] = {
                "cpu_cores": min(2, 1 + (1 if split.critical_path else 0)),
                "memory_mb": min(
                    2048, 512 * (2 if split.estimated_duration > 300 else 1)
                ),
                "estimated_tokens": split.resource_requirements.get(
                    "estimated_tokens", 1000
                ),
                "concurrent_limit": 1,
                "priority": split.priority,
            }

        return allocation

    def _estimate_execution_cost(
        self,
        task_splits: List[TaskSplit],
        provider_assignments: Dict[str, ProviderType],
    ) -> float:
        """Estimate total execution cost."""
        total_cost = 0.0

        # Provider cost rates (example values)
        provider_rates = {
            ProviderType.CLAUDE_CLI: 0.01,
            ProviderType.OPENAI: 0.02,
            ProviderType.LOCAL: 0.0,
        }

        for split in task_splits:
            provider = provider_assignments.get(split.split_id, ProviderType.CLAUDE_CLI)
            rate = provider_rates.get(provider, 0.01)

            # Estimate based on tokens and duration
            estimated_tokens = split.resource_requirements.get("estimated_tokens", 1000)
            cost = (estimated_tokens / 1000) * rate

            total_cost += cost

        return round(total_cost, 4)

    async def _validate_execution_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Validate execution plan for potential issues."""
        warnings = []
        recommendations = []
        valid = True

        # Check for resource constraints
        if plan.estimated_cost > 10.0:
            warnings.append(f"High estimated cost: ${plan.estimated_cost:.2f}")
            recommendations.append("Consider using cost optimization strategy")

        # Check for long execution time
        if plan.estimated_total_time > 3600:
            warnings.append(
                f"Long estimated execution time: {plan.estimated_total_time // 60} minutes"
            )
            recommendations.append("Consider increasing parallelization")

        return {
            "valid": valid,
            "warnings": warnings,
            "recommendations": recommendations,
        }

    def get_execution_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Get execution plan by ID."""
        return self._execution_plans.get(plan_id)

    def get_distribution_result(self, task_id: str) -> Optional[DistributionResult]:
        """Get distribution result by task ID."""
        return self._active_distributions.get(task_id)


def create_task_distribution_engine(
    agent_specialization_engine: Optional[AgentSpecializationEngine] = None,
    multi_provider_coordinator: Optional[MultiProviderCoordinator] = None,
    multi_provider_service: Optional[MultiProviderService] = None,
) -> TaskDistributionEngine:
    """Factory function to create TaskDistributionEngine with dependencies."""
    # If no coordinator is provided but a service is, create the coordinator
    if multi_provider_coordinator is None and multi_provider_service is not None:
        multi_provider_coordinator = MultiProviderCoordinator(
            provider_service=multi_provider_service
        )

    return TaskDistributionEngine(
        agent_specialization_engine=agent_specialization_engine,
        multi_provider_coordinator=multi_provider_coordinator,
    )

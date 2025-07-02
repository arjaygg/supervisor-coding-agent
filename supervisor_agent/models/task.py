# supervisor_agent/models/task.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


@dataclass
class Task:
    id: str
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskSplit:
    task_id: str
    parent_task_id: str
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplexityAnalysis:
    complexity_score: float
    requires_splitting: bool


@dataclass
class SubtaskGraph:
    subtasks: List[TaskSplit]
    dependencies: List[tuple[str, str]]


class SplittingStrategy(Enum):
    DEFAULT = "default"


@dataclass
class DependencyGraph:
    nodes: List[str]
    edges: List[tuple[str, str]]
    critical_path: List[str] = field(default_factory=list)
    parallelization_potential: float = 0.0


@dataclass
class ExecutionOrder:
    order: List[str]


@dataclass
class CircularDependency:
    nodes: List[str]


class TaskComplexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


@dataclass
class ExecutionPlan:
    steps: List[str] = field(default_factory=list)
    estimated_time: Optional[float] = None
    cost_estimate: Optional[float] = None
    # Extended fields for comprehensive execution planning
    plan_id: Optional[str] = None
    original_task_id: Optional[str] = None
    dependency_graph: Optional[Any] = None
    provider_assignments: Optional[Dict[str, Any]] = None
    execution_strategy: Optional['DistributionStrategy'] = None
    estimated_total_time: Optional[float] = None
    estimated_cost: Optional[float] = None
    resource_allocation: Optional[Dict[str, Any]] = None


class DistributionStrategy(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


@dataclass
class DistributionResult:
    task_splits: List[TaskSplit]
    dependencies: DependencyGraph
    execution_plan: ExecutionPlan

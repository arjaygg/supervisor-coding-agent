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
    dependencies: List[str] = field(default_factory=list)
    parallelizable: bool = True
    split_id: Optional[str] = None

    def __post_init__(self):
        # Set split_id to task_id if not provided
        if self.split_id is None:
            self.split_id = self.task_id


@dataclass
class ComplexityAnalysis:
    complexity_level: "TaskComplexity"
    estimated_steps: int
    identified_dependencies: List[str]
    splitting_recommendation: "SplittingStrategy"
    estimated_execution_time: float
    resource_requirements: Dict[str, Any]
    confidence_score: float
    reasoning: str
    # Legacy fields for backward compatibility
    complexity_score: float = 0.0
    requires_splitting: bool = False


@dataclass
class SubtaskGraph:
    subtasks: List[TaskSplit]
    dependencies: List[tuple[str, str]]


class SplittingStrategy(Enum):
    NO_SPLIT = "no_split"
    LINEAR_SPLIT = "linear_split"
    PARALLEL_SPLIT = "parallel_split"
    HIERARCHICAL_SPLIT = "hierarchical_split"
    DEFAULT = "default"


@dataclass
class DependencyGraph:
    nodes: List[str]
    edges: List[tuple[str, str]]
    critical_path: List[str] = field(default_factory=list)
    parallelization_potential: float = 0.0
    execution_levels: List[List[str]] = field(default_factory=list)
    total_estimated_time: float = 0.0


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
    HIGHLY_COMPLEX = "highly_complex"


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
    execution_strategy: Optional["DistributionStrategy"] = None
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
    success: bool = True
    original_task_id: Optional[str] = None
    processing_time: float = 0.0
    error_message: Optional[str] = None

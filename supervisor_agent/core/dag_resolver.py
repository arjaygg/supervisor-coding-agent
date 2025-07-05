"""
DAG Resolver for Workflow Dependencies

Implements topological sorting and dependency resolution for workflow tasks.
Validates DAG structure and provides execution planning capabilities.

Follows SOLID principles:
- Single Responsibility: Only handles DAG resolution
- Open-Closed: Extensible for different dependency types
- Liskov Substitution: Consistent interface implementations
- Interface Segregation: Focused DAG resolution interface
- Dependency Inversion: Abstract dependency checking
"""

from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

from supervisor_agent.core.workflow_models import (
    DependencyCondition,
    DependencyDefinition,
    ExecutionPlan,
    TaskDefinition,
    WorkflowDefinition,
)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """DAG validation result"""

    def __init__(
        self,
        is_valid: bool,
        error_message: str = None,
        warnings: List[str] = None,
    ):
        self.is_valid = is_valid
        self.error_message = error_message
        self.warnings = warnings or []

    def __bool__(self) -> bool:
        return self.is_valid


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected"""

    pass


class InvalidDAGError(Exception):
    """Raised when DAG structure is invalid"""

    pass


class DependencyResolverInterface(ABC):
    """Abstract interface for dependency resolution"""

    @abstractmethod
    def resolve_dependencies(
        self, tasks: List[TaskDefinition]
    ) -> "ExecutionPlan":
        """Resolve task dependencies and create execution plan"""
        pass

    @abstractmethod
    def validate_dag(self, workflow: WorkflowDefinition) -> ValidationResult:
        """Validate DAG structure for cycles and consistency"""
        pass


class DAGResolver(DependencyResolverInterface):
    """
    Advanced DAG resolver with topological sorting, cycle detection,
    and parallel execution planning capabilities.

    Implements sophisticated dependency resolution algorithms:
    - Kahn's algorithm for topological sorting
    - DFS-based cycle detection
    - Critical path analysis for optimization
    - Parallel execution level calculation
    """

    def __init__(self):
        self.logger = get_logger(__name__)

    def resolve_dependencies(
        self, tasks: List[TaskDefinition]
    ) -> ExecutionPlan:
        """
        Resolve task dependencies using topological sorting and create execution plan.

        Returns an ExecutionPlan with:
        - Execution order for sequential processing
        - Parallel execution levels for concurrent processing
        - Critical path analysis
        - Dependency graph information
        """
        if not tasks:
            return ExecutionPlan(
                task_order=[],
                parallel_levels=[],
                critical_path=[],
                execution_graph={},
            )

        # Build dependency graph
        graph = self._build_dependency_graph(tasks)

        # Validate for cycles
        if self._has_cycles(graph):
            raise CircularDependencyError(
                "Circular dependency detected in task graph"
            )

        # Perform topological sort
        task_order = self._topological_sort(graph)

        # Calculate parallel execution levels
        parallel_levels = self._calculate_parallel_levels(graph, task_order)

        # Find critical path
        critical_path = self._find_critical_path(graph, tasks)

        execution_plan = ExecutionPlan(
            task_order=task_order,
            parallel_levels=parallel_levels,
            critical_path=critical_path,
            execution_graph=graph,
            metadata={
                "total_tasks": len(tasks),
                "max_parallel_level": len(
                    max(parallel_levels, key=len, default=[])
                ),
                "critical_path_length": len(critical_path),
                "estimated_duration": self._estimate_execution_time(
                    critical_path, tasks
                ),
            },
        )

        self.logger.info(
            f"Resolved dependencies for {len(tasks)} tasks with {len(parallel_levels)} execution levels"
        )
        return execution_plan

    def validate_dag(self, workflow: WorkflowDefinition) -> ValidationResult:
        """
        Comprehensive DAG validation including:
        - Cycle detection
        - Orphaned task detection
        - Dependency consistency checks
        - Resource constraint validation
        """
        try:
            warnings = []

            # Basic structure validation
            if not workflow.tasks:
                return ValidationResult(
                    False, "Workflow must contain at least one task"
                )

            # Build task lookup
            task_map = {task.id: task for task in workflow.tasks}

            # Validate all dependencies exist
            for task in workflow.tasks:
                for dep in task.dependencies:
                    if dep.depends_on not in task_map:
                        return ValidationResult(
                            False,
                            f"Task '{task.id}' has dependency on non-existent task '{dep.depends_on}'",
                        )

            # Build dependency graph
            graph = self._build_dependency_graph(workflow.tasks)

            # Check for cycles
            if self._has_cycles(graph):
                return ValidationResult(False, "Circular dependency detected")

            # Check for orphaned tasks (tasks with no path to/from root)
            orphaned = self._find_orphaned_tasks(graph)
            if orphaned:
                warnings.append(
                    f"Found {len(orphaned)} orphaned tasks: {', '.join(orphaned)}"
                )

            # Check for overly complex dependencies
            max_dependencies = 10  # Configurable threshold
            complex_tasks = [
                task.id
                for task in workflow.tasks
                if len(task.dependencies) > max_dependencies
            ]
            if complex_tasks:
                warnings.append(
                    f"Tasks with many dependencies (>{max_dependencies}): {', '.join(complex_tasks)}"
                )

            # Validate parallel execution feasibility
            parallel_levels = self._calculate_parallel_levels(
                graph, self._topological_sort(graph)
            )
            max_parallel = len(max(parallel_levels, key=len, default=[]))
            if max_parallel > 50:  # Configurable threshold
                warnings.append(
                    f"High parallelism detected: {max_parallel} concurrent tasks"
                )

            return ValidationResult(True, warnings=warnings)

        except Exception as e:
            return ValidationResult(False, f"Validation failed: {str(e)}")

    def _build_dependency_graph(
        self, tasks: List[TaskDefinition]
    ) -> Dict[str, Set[str]]:
        """Build adjacency list representation of dependency graph"""
        graph = defaultdict(set)

        # Initialize all tasks in graph
        for task in tasks:
            graph[task.id] = set()

        # Add dependencies
        for task in tasks:
            for dep in task.dependencies:
                graph[dep.depends_on].add(task.id)

        return dict(graph)

    def _has_cycles(self, graph: Dict[str, Set[str]]) -> bool:
        """Detect cycles using DFS with coloring"""
        WHITE, GRAY, BLACK = 0, 1, 2
        colors = {node: WHITE for node in graph}

        def dfs(node: str) -> bool:
            if colors[node] == GRAY:  # Back edge found
                return True
            if colors[node] == BLACK:  # Already processed
                return False

            colors[node] = GRAY
            for neighbor in graph[node]:
                if dfs(neighbor):
                    return True
            colors[node] = BLACK
            return False

        for node in graph:
            if colors[node] == WHITE:
                if dfs(node):
                    return True
        return False

    def _topological_sort(self, graph: Dict[str, Set[str]]) -> List[str]:
        """Perform topological sort using Kahn's algorithm"""
        # Calculate in-degrees
        in_degree = {node: 0 for node in graph}
        for node in graph:
            for neighbor in graph[node]:
                in_degree[neighbor] += 1

        # Start with nodes having no dependencies
        queue = deque([node for node in in_degree if in_degree[node] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            # Remove edges and update in-degrees
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(graph):
            raise CircularDependencyError(
                "Cannot perform topological sort: cycle detected"
            )

        return result

    def _calculate_parallel_levels(
        self, graph: Dict[str, Set[str]], task_order: List[str]
    ) -> List[List[str]]:
        """Calculate parallel execution levels"""
        levels = []
        remaining_tasks = set(task_order)
        completed_tasks = set()

        while remaining_tasks:
            # Find tasks that can run now (all dependencies completed)
            current_level = []
            for task in list(remaining_tasks):
                # Get all tasks this task depends on
                dependencies = set()
                for potential_dep in graph:
                    if task in graph[potential_dep]:
                        dependencies.add(potential_dep)

                # Check if all dependencies are completed
                if dependencies.issubset(completed_tasks):
                    current_level.append(task)

            if not current_level:
                raise InvalidDAGError(
                    "Cannot create execution levels: circular dependency or invalid graph"
                )

            levels.append(current_level)
            completed_tasks.update(current_level)
            remaining_tasks -= set(current_level)

        return levels

    def _find_critical_path(
        self, graph: Dict[str, Set[str]], tasks: List[TaskDefinition]
    ) -> List[str]:
        """Find critical path (longest path through the DAG)"""
        # Create task duration mapping
        task_durations = {
            task.id: getattr(task, "estimated_duration", 1.0) for task in tasks
        }

        # Calculate longest paths using dynamic programming
        longest_path = {}
        path_predecessor = {}

        def calculate_longest_path(node: str) -> float:
            if node in longest_path:
                return longest_path[node]

            max_path = 0
            best_predecessor = None

            # Find all predecessors (tasks that this task depends on)
            for potential_pred in graph:
                if node in graph[potential_pred]:
                    pred_path = calculate_longest_path(potential_pred)
                    if pred_path > max_path:
                        max_path = pred_path
                        best_predecessor = potential_pred

            longest_path[node] = max_path + task_durations.get(node, 1.0)
            if best_predecessor:
                path_predecessor[node] = best_predecessor

            return longest_path[node]

        # Calculate longest paths for all nodes
        for node in graph:
            calculate_longest_path(node)

        # Find the end node with the longest path
        if not longest_path:
            return []

        end_node = max(longest_path.keys(), key=lambda x: longest_path[x])

        # Reconstruct critical path
        critical_path = []
        current = end_node
        while current:
            critical_path.append(current)
            current = path_predecessor.get(current)

        return list(reversed(critical_path))

    def _find_orphaned_tasks(self, graph: Dict[str, Set[str]]) -> List[str]:
        """Find tasks that are not connected to the main workflow"""
        # Find nodes with no incoming or outgoing edges
        has_incoming = set()
        has_outgoing = set()

        for node, neighbors in graph.items():
            if neighbors:
                has_outgoing.add(node)
            for neighbor in neighbors:
                has_incoming.add(neighbor)

        all_nodes = set(graph.keys())
        orphaned = all_nodes - (has_incoming | has_outgoing)

        return list(orphaned)

    def _estimate_execution_time(
        self, critical_path: List[str], tasks: List[TaskDefinition]
    ) -> float:
        """Estimate total execution time based on critical path"""
        task_durations = {
            task.id: getattr(task, "estimated_duration", 1.0) for task in tasks
        }

        return sum(
            task_durations.get(task_id, 1.0) for task_id in critical_path
        )

    def analyze_parallelization_potential(
        self, workflow: WorkflowDefinition
    ) -> Dict[str, Any]:
        """Analyze potential for parallel execution optimization"""
        if not workflow.tasks:
            return {"error": "No tasks to analyze"}

        graph = self._build_dependency_graph(workflow.tasks)
        task_order = self._topological_sort(graph)
        parallel_levels = self._calculate_parallel_levels(graph, task_order)
        critical_path = self._find_critical_path(graph, workflow.tasks)

        total_tasks = len(workflow.tasks)
        max_parallel = len(max(parallel_levels, key=len, default=[]))

        # Calculate parallelization metrics
        sequential_time = sum(
            getattr(task, "estimated_duration", 1.0) for task in workflow.tasks
        )

        parallel_time = sum(
            max(
                getattr(
                    next(t for t in workflow.tasks if t.id == task_id),
                    "estimated_duration",
                    1.0,
                )
                for task_id in level
            )
            for level in parallel_levels
        )

        speedup_potential = (
            sequential_time / parallel_time if parallel_time > 0 else 1.0
        )
        efficiency = (
            speedup_potential / max_parallel if max_parallel > 0 else 0.0
        )

        return {
            "total_tasks": total_tasks,
            "execution_levels": len(parallel_levels),
            "max_parallel_tasks": max_parallel,
            "critical_path_length": len(critical_path),
            "sequential_execution_time": sequential_time,
            "parallel_execution_time": parallel_time,
            "speedup_potential": speedup_potential,
            "parallel_efficiency": efficiency,
            "bottleneck_tasks": critical_path,
            "parallel_levels": [
                {"level": i, "tasks": level, "task_count": len(level)}
                for i, level in enumerate(parallel_levels)
            ],
        }


class DependencyChecker(ABC):
    """Abstract dependency checker for different condition types"""

    @abstractmethod
    def can_execute(
        self,
        task_id: str,
        dependency_task_id: str,
        dependency_result: dict,
        condition: DependencyCondition,
        condition_value: str = None,
    ) -> bool:
        """Check if dependency condition is satisfied"""
        pass


class StandardDependencyChecker(DependencyChecker):
    """Standard implementation of dependency checking"""

    def can_execute(
        self,
        task_id: str,
        dependency_task_id: str,
        dependency_result: dict,
        condition: DependencyCondition,
        condition_value: str = None,
    ) -> bool:
        """Check if dependency condition is satisfied"""

        if not dependency_result:
            return False

        task_status = dependency_result.get("status", "")

        if condition == DependencyCondition.SUCCESS:
            return task_status == "COMPLETED" and dependency_result.get(
                "success", False
            )
        elif condition == DependencyCondition.FAILURE:
            return task_status == "FAILED" or not dependency_result.get(
                "success", True
            )
        elif condition == DependencyCondition.COMPLETION:
            return task_status in ["COMPLETED", "FAILED"]
        elif condition == DependencyCondition.CUSTOM:
            # Simple expression evaluation for custom conditions
            # In production, you might want a more sophisticated expression evaluator
            return self._evaluate_custom_condition(
                dependency_result, condition_value
            )

        return False

    def _evaluate_custom_condition(
        self, result: dict, condition_expr: str
    ) -> bool:
        """Evaluate custom condition expression"""
        if not condition_expr:
            return True

        try:
            # Simple variable substitution and evaluation
            # Security note: In production, use a proper expression evaluator
            # This is a simplified implementation for demonstration
            context = {
                "result": result,
                "status": result.get("status", ""),
                "success": result.get("success", False),
                "error_count": result.get("error_count", 0),
            }

            # Replace variables in expression
            expr = condition_expr
            for key, value in context.items():
                expr = expr.replace(f"{{{key}}}", str(value))

            # Simple boolean expression evaluation
            # WARNING: In production, use ast.literal_eval or similar safe evaluator
            return eval(expr) if expr else True

        except Exception as e:
            logger.warning(
                f"Failed to evaluate custom condition '{condition_expr}': {e}"
            )
            return False


class DAGResolver:
    """
    Resolves task dependencies and creates execution plans.

    Implements topological sorting to determine task execution order
    while respecting dependencies and enabling parallel execution.
    """

    def __init__(self, dependency_checker: DependencyChecker = None):
        self.dependency_checker = (
            dependency_checker or StandardDependencyChecker()
        )

    def create_execution_plan(
        self, workflow_def: WorkflowDefinition
    ) -> ExecutionPlan:
        """
        Create execution plan from workflow definition.

        Returns an ExecutionPlan with parallel execution groups.
        """
        logger.info(
            f"Creating execution plan for workflow: {workflow_def.name}"
        )

        # Validate DAG structure first
        validation_result = self.validate_dag(workflow_def)
        if not validation_result.is_valid:
            raise InvalidDAGError(validation_result.error_message)

        # Build task and dependency maps
        task_map = {
            task["id"]: TaskDefinition(**task) for task in workflow_def.tasks
        }
        dependency_map = self._build_dependency_map(workflow_def.dependencies)

        # Perform topological sort with parallel group identification
        execution_order = self._topological_sort_parallel(
            task_map.keys(), dependency_map
        )

        logger.info(
            f"Created execution plan with {len(execution_order)} parallel groups"
        )

        return ExecutionPlan(
            execution_order=execution_order,
            task_map=task_map,
            dependency_map=dependency_map,
        )

    def validate_dag(
        self, workflow_def: WorkflowDefinition
    ) -> ValidationResult:
        """Validate DAG structure and dependencies"""

        warnings = []

        try:
            # Check for empty workflow
            if not workflow_def.tasks:
                return ValidationResult(
                    False, "Workflow must contain at least one task"
                )

            # Validate task IDs are unique
            task_ids = [task["id"] for task in workflow_def.tasks]
            if len(task_ids) != len(set(task_ids)):
                return ValidationResult(False, "Task IDs must be unique")

            task_id_set = set(task_ids)

            # Validate dependencies reference existing tasks
            for dep in workflow_def.dependencies:
                task_id = dep["task_id"]
                depends_on = dep["depends_on"]

                if task_id not in task_id_set:
                    return ValidationResult(
                        False,
                        f"Dependency references non-existent task: {task_id}",
                    )

                if depends_on not in task_id_set:
                    return ValidationResult(
                        False,
                        f"Dependency references non-existent task: {depends_on}",
                    )

                if task_id == depends_on:
                    return ValidationResult(
                        False, f"Task cannot depend on itself: {task_id}"
                    )

            # Check for circular dependencies
            dependency_map = self._build_dependency_map(
                workflow_def.dependencies
            )
            self._detect_circular_dependencies(task_id_set, dependency_map)

            # Check for disconnected components
            if self._has_disconnected_components(task_id_set, dependency_map):
                warnings.append("Workflow contains disconnected task groups")

            # Validate task configurations
            for task in workflow_def.tasks:
                task_warnings = self._validate_task_config(task)
                warnings.extend(task_warnings)

            logger.info(
                f"DAG validation passed for workflow: {workflow_def.name}"
            )
            return ValidationResult(True, warnings=warnings)

        except CircularDependencyError as e:
            return ValidationResult(False, str(e))
        except Exception as e:
            logger.error(f"DAG validation failed: {e}")
            return ValidationResult(False, f"Validation error: {str(e)}")

    def _build_dependency_map(
        self, dependencies: List[Dict]
    ) -> Dict[str, List[str]]:
        """Build dependency map from dependency definitions"""
        dep_map = defaultdict(list)

        for dep in dependencies:
            task_id = dep["task_id"]
            depends_on = dep["depends_on"]
            dep_map[task_id].append(depends_on)

        return dict(dep_map)

    def _detect_circular_dependencies(
        self, task_ids: Set[str], dependency_map: Dict[str, List[str]]
    ):
        """Detect circular dependencies using DFS"""

        # Colors: 0 = white (unvisited), 1 = gray (visiting), 2 = black (visited)
        colors = {task_id: 0 for task_id in task_ids}
        path = []

        def dfs(task_id: str):
            if colors[task_id] == 1:  # Gray - found cycle
                cycle_start = path.index(task_id)
                cycle = path[cycle_start:] + [task_id]
                raise CircularDependencyError(
                    f"Circular dependency detected: {' -> '.join(cycle)}"
                )

            if colors[task_id] == 2:  # Already processed
                return

            colors[task_id] = 1  # Mark as visiting
            path.append(task_id)

            # Visit dependencies
            for dep_task in dependency_map.get(task_id, []):
                dfs(dep_task)

            path.pop()
            colors[task_id] = 2  # Mark as visited

        # Check each task
        for task_id in task_ids:
            if colors[task_id] == 0:
                dfs(task_id)

    def _topological_sort_parallel(
        self, task_ids: Set[str], dependency_map: Dict[str, List[str]]
    ) -> List[List[str]]:
        """
        Perform topological sort with parallel execution group identification.

        Returns list of lists, where each inner list contains tasks that can run in parallel.
        """

        # Calculate in-degrees (number of dependencies)
        in_degree = {task_id: 0 for task_id in task_ids}

        for task_id, deps in dependency_map.items():
            in_degree[task_id] = len(deps)

        # Initialize queue with tasks that have no dependencies
        current_level = deque(
            [task_id for task_id in task_ids if in_degree[task_id] == 0]
        )
        execution_order = []

        while current_level:
            # All tasks in current_level can execute in parallel
            parallel_group = list(current_level)
            execution_order.append(parallel_group)

            next_level = deque()

            # Process all tasks in current parallel group
            for task_id in current_level:
                # Update in-degrees for dependent tasks
                for dependent_task, deps in dependency_map.items():
                    if task_id in deps:
                        in_degree[dependent_task] -= 1

                        # If all dependencies satisfied, add to next level
                        if in_degree[dependent_task] == 0:
                            next_level.append(dependent_task)

            current_level = next_level

        # Verify all tasks were processed
        processed_tasks = {task for group in execution_order for task in group}
        if len(processed_tasks) != len(task_ids):
            unprocessed = task_ids - processed_tasks
            raise InvalidDAGError(
                f"Unable to resolve dependencies for tasks: {unprocessed}"
            )

        return execution_order

    def _has_disconnected_components(
        self, task_ids: Set[str], dependency_map: Dict[str, List[str]]
    ) -> bool:
        """Check if workflow has disconnected task groups"""

        if len(task_ids) <= 1:
            return False

        # Build undirected graph for connectivity check
        graph = defaultdict(set)

        for task_id, deps in dependency_map.items():
            for dep in deps:
                graph[task_id].add(dep)
                graph[dep].add(task_id)

        # Add isolated nodes
        for task_id in task_ids:
            if task_id not in graph:
                graph[task_id] = set()

        # DFS to find connected components
        visited = set()

        def dfs(node):
            visited.add(node)
            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor)

        # Start DFS from first task
        first_task = next(iter(task_ids))
        dfs(first_task)

        # Check if all tasks are connected
        return len(visited) < len(task_ids)

    def _validate_task_config(self, task: Dict[str, any]) -> List[str]:
        """Validate individual task configuration"""
        warnings = []

        # Check required fields
        required_fields = ["id", "name", "type", "config"]
        for field in required_fields:
            if field not in task:
                warnings.append(
                    f"Task {task.get('id', 'unknown')} missing required field: {field}"
                )

        # Validate config structure
        config = task.get("config", {})
        if not isinstance(config, dict):
            warnings.append(
                f"Task {task.get('id')} config must be a dictionary"
            )

        # Task type specific validation
        task_type = task.get("type", "")
        if task_type and not self._is_valid_task_type(task_type):
            warnings.append(
                f"Task {task.get('id')} has unknown type: {task_type}"
            )

        return warnings

    def _is_valid_task_type(self, task_type: str) -> bool:
        """Check if task type is valid"""
        # This should be updated based on available task types in your system
        valid_types = {
            "PR_REVIEW",
            "ISSUE_SUMMARY",
            "CODE_ANALYSIS",
            "REFACTOR",
            "BUG_FIX",
            "FEATURE",
            "CUSTOM",
        }
        return task_type in valid_types

    def can_task_execute(
        self,
        task_id: str,
        dependency_results: Dict[str, dict],
        dependencies: List[DependencyDefinition],
    ) -> bool:
        """Check if a task can execute based on dependency results"""

        for dep in dependencies:
            if dep.task_id == task_id:
                dep_result = dependency_results.get(dep.depends_on, {})

                if not self.dependency_checker.can_execute(
                    task_id,
                    dep.depends_on,
                    dep_result,
                    dep.condition,
                    dep.condition_value,
                ):
                    return False

        return True

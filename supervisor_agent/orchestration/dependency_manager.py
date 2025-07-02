# supervisor_agent/orchestration/dependency_manager.py
from typing import Any, Dict, List

from supervisor_agent.models.task import (
    CircularDependency,
    DependencyGraph,
    ExecutionOrder,
    Task,
)


class DependencyManager:
    def _has_circular_dependencies(self, edges: Dict[str, List[str]]) -> bool:
        """Check for circular dependencies using DFS."""
        white_set = set(edges.keys())
        gray_set = set()
        black_set = set()

        def visit(node):
            if node in black_set:
                return False
            if node in gray_set:
                return True  # Cycle detected

            gray_set.add(node)
            white_set.discard(node)

            for neighbor in edges.get(node, []):
                if visit(neighbor):
                    return True

            gray_set.remove(node)
            black_set.add(node)
            return False

        while white_set:
            node = white_set.pop()
            white_set.add(node)
            if visit(node):
                return True

        return False

    def _calculate_execution_levels(
        self, tasks: List[Any], edges: Dict[str, List[str]]
    ) -> List[List[str]]:
        """Calculate execution levels for parallel processing."""
        # Create reverse dependency map
        dependencies = {}
        for task_id in edges.keys():
            dependencies[task_id] = []

        for task_id, deps in edges.items():
            for dep in deps:
                if dep not in dependencies:
                    dependencies[dep] = []
                dependencies[dep].append(task_id)

        levels = []
        remaining = set(edges.keys())

        while remaining:
            # Find tasks with no dependencies
            current_level = []
            for task_id in list(remaining):
                if not edges.get(task_id, []) or all(
                    dep not in remaining for dep in edges.get(task_id, [])
                ):
                    current_level.append(task_id)

            if not current_level:
                # Handle circular dependencies by breaking the cycle
                current_level = [list(remaining)[0]]

            levels.append(current_level)
            for task_id in current_level:
                remaining.remove(task_id)

        return levels

    def _calculate_parallelization_potential(
        self, levels: List[List[str]], tasks: List[Any]
    ) -> float:
        """Calculate parallelization potential based on execution levels."""
        if not tasks or not levels:
            return 0.0

        total_tasks = len(tasks)
        max_parallel = max(len(level) for level in levels) if levels else 1
        avg_parallel = (
            sum(len(level) for level in levels) / len(levels) if levels else 1
        )

        # Parallelization potential is the ratio of average parallel tasks to total tasks
        potential = avg_parallel / total_tasks
        return min(potential, 1.0)

    def build_dependency_graph(self, tasks: List[Task]) -> DependencyGraph:
        """
        Builds a dependency graph for a list of tasks.
        """
        nodes = [task.id for task in tasks]
        edges = []

        # Simple dependency logic: sequential execution by default
        if len(tasks) > 1:
            edges.append((tasks[0].id, tasks[1].id))

        # Calculate critical path (simplified)
        critical_path = nodes if nodes else []

        # Create edge dictionary for analysis
        edge_dict = {}
        for node in nodes:
            edge_dict[node] = []
        for edge in edges:
            edge_dict[edge[1]].append(edge[0])

        # Calculate parallelization potential
        levels = self._calculate_execution_levels(tasks, edge_dict)
        parallelization_potential = self._calculate_parallelization_potential(
            levels, tasks
        )

        return DependencyGraph(
            nodes=nodes,
            edges=edges,
            critical_path=critical_path,
            parallelization_potential=parallelization_potential,
        )

    def resolve_execution_order(self, graph: DependencyGraph) -> ExecutionOrder:
        """
        Resolves the execution order of tasks from a dependency graph.
        This is a placeholder implementation (topological sort).
        """
        # A real implementation would perform a topological sort of the graph.
        return ExecutionOrder(order=graph.nodes)

    def detect_circular_dependencies(
        self, graph: DependencyGraph
    ) -> List[CircularDependency]:
        """
        Detects circular dependencies in a task graph.
        This is a placeholder implementation.
        """
        # A real implementation would use an algorithm like Tarjan's or Kosaraju's.
        return []

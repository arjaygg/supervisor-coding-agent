# supervisor_agent/orchestration/task_distribution_engine.py
from typing import List

from supervisor_agent.models.providers import Provider

# Re-export classes that the tests expect to import from this module
from supervisor_agent.models.task import (
    ComplexityAnalysis,
    DependencyGraph,
    DistributionResult,
    DistributionStrategy,
    ExecutionOrder,
    ExecutionPlan,
    SplittingStrategy,
    Task,
    TaskComplexity,
    TaskSplit,
)
from supervisor_agent.orchestration.agent_specialization_engine import (
    AgentSpecializationEngine,
)
from supervisor_agent.orchestration.dependency_manager import DependencyManager
from supervisor_agent.orchestration.multi_provider_coordinator import (
    MultiProviderCoordinator,
    create_multi_provider_coordinator,
)
from supervisor_agent.orchestration.task_splitter import IntelligentTaskSplitter


class TaskDistributionEngine:
    def __init__(
        self,
        agent_specialization_engine=None,
        multi_provider_coordinator=None,
        task_splitter=None,
        dependency_manager=None,
    ):
        self.agent_specialization_engine = (
            agent_specialization_engine or AgentSpecializationEngine()
        )
        self.task_splitter = task_splitter or IntelligentTaskSplitter()
        self.dependency_manager = dependency_manager or DependencyManager()

        # Create a mock multi_provider_coordinator if none provided
        if multi_provider_coordinator:
            self.multi_provider_coordinator = multi_provider_coordinator
        else:
            # Create a mock provider service for testing
            from unittest.mock import Mock

            mock_provider_service = Mock()
            from supervisor_agent.orchestration.multi_provider_coordinator import (
                create_multi_provider_coordinator,
            )

            self.multi_provider_coordinator = create_multi_provider_coordinator(
                mock_provider_service
            )

    async def distribute_task(
        self, task: Task, strategy: DistributionStrategy
    ) -> DistributionResult:
        """
        Distributes a task by splitting it and analyzing dependencies.
        """
        # 1. Split the task if necessary
        complexity_analysis = self.task_splitter.analyze_task_complexity(task)
        if complexity_analysis.requires_splitting:
            subtask_graph = self.task_splitter.generate_subtask_graph(task)
            task_splits = subtask_graph.subtasks
        else:
            # If not splitting, treat the original task as a single split
            task_splits = [
                TaskSplit(task_id=task.id, parent_task_id=task.id, config=task.config)
            ]

        # 2. Analyze dependencies
        dependency_graph = self.dependency_manager.build_dependency_graph(
            [task_split_to_task(ts) for ts in task_splits]
        )

        # 3. Optimize distribution strategy (placeholder)
        optimized_strategy = await self.optimize_distribution_strategy(task, [])

        # 4. Coordinate parallel execution (placeholder)
        execution_plan = await self.coordinate_parallel_execution(task_splits)

        return DistributionResult(
            task_splits=task_splits,
            dependencies=dependency_graph,
            execution_plan=execution_plan,
        )

    async def split_complex_task(self, task: Task) -> List[TaskSplit]:
        """
        Splits a complex task into smaller, manageable subtasks.
        """
        complexity_analysis = self.task_splitter.analyze_task_complexity(task)
        if complexity_analysis.requires_splitting:
            subtask_graph = self.task_splitter.generate_subtask_graph(task)
            return subtask_graph.subtasks
        return [TaskSplit(task_id=task.id, parent_task_id=task.id, config=task.config)]

    async def analyze_task_dependencies(self, task: Task) -> DependencyGraph:
        """
        Analyzes the dependencies of a task or its subtasks.
        """
        # This is a simplified version. A real implementation would be more complex.
        return self.dependency_manager.build_dependency_graph([task])

    async def optimize_distribution_strategy(
        self, task: Task, providers: List[Provider]
    ) -> DistributionStrategy:
        """
        Optimizes the distribution strategy based on the task and available providers.
        This is a placeholder implementation.
        """
        return DistributionStrategy.SEQUENTIAL  # Default strategy

    async def coordinate_parallel_execution(
        self, task_splits: List[TaskSplit]
    ) -> ExecutionPlan:
        """
        Coordinates the parallel execution of task splits.
        This is a placeholder implementation.
        """
        steps = [f"Execute task {ts.task_id}" for ts in task_splits]
        return ExecutionPlan(steps=steps, estimated_time=60.0, cost_estimate=10.0)


def task_split_to_task(task_split: TaskSplit) -> Task:
    """Converts a TaskSplit to a Task."""
    return Task(id=task_split.task_id, config=task_split.config)


def create_task_distribution_engine(
    agent_specialization_engine=None,
    multi_provider_coordinator=None,
    task_splitter=None,
    dependency_manager=None,
) -> TaskDistributionEngine:
    """Factory function to create a TaskDistributionEngine instance."""
    return TaskDistributionEngine(
        agent_specialization_engine=agent_specialization_engine,
        multi_provider_coordinator=multi_provider_coordinator,
        task_splitter=task_splitter,
        dependency_manager=dependency_manager,
    )

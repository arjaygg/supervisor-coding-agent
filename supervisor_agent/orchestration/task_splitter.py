# supervisor_agent/orchestration/task_splitter.py
import re
from typing import Any, Dict, List

from supervisor_agent.db.models import Task as DbTask
from supervisor_agent.models.task import (
    ComplexityAnalysis,
    SplittingStrategy,
    SubtaskGraph,
    Task,
    TaskComplexity,
    TaskSplit,
)


class IntelligentTaskSplitter:
    def _extract_task_content(self, task) -> str:
        """Extract task content from either Task or DbTask object."""
        if hasattr(task, "payload") and isinstance(task.payload, dict):
            return task.payload.get("description", "")
        elif hasattr(task, "config") and isinstance(task.config, dict):
            return task.config.get("description", "")
        return str(task)

    def _calculate_complexity_score(self, content: str) -> float:
        """Calculate complexity score based on task content."""
        if not content:
            return 0.0

        # Factors that increase complexity
        word_count = len(content.split())
        sentence_count = len(re.split(r"[.!?]+", content))
        keyword_count = len(
            re.findall(
                r"\b(analyze|optimize|integrate|process|validate|implement|configure)\b",
                content.lower(),
            )
        )
        conjunction_count = len(
            re.findall(
                r"\b(and|then|after|followed by|subsequently)\b",
                content.lower(),
            )
        )

        # Calculate score based on various factors
        complexity_score = (
            (word_count / 50)  # Base complexity from word count
            + (sentence_count / 10)  # Multiple sentences increase complexity
            + (keyword_count * 0.3)  # Technical keywords
            + (conjunction_count * 0.4)  # Conjunctions indicate multiple steps
        )

        return min(complexity_score, 3.0)  # Cap at 3.0

    def _estimate_steps(self, content: str) -> int:
        """Estimate number of steps required for a task."""
        if not content:
            return 1

        # Look for step indicators
        step_indicators = re.findall(
            r"\b(first|then|next|after|finally|followed by|subsequently)\b",
            content.lower(),
        )
        explicit_steps = re.findall(r"\b\d+\.\s", content)  # Numbered lists
        conjunctions = re.findall(r"\b(and|or|but)\b", content.lower())

        estimated_steps = max(
            len(step_indicators) + 1,  # Add 1 for the initial step
            len(explicit_steps),
            len(conjunctions) + 1,
            1,  # Minimum 1 step
        )

        return estimated_steps

    def _identify_dependencies(self, content: str) -> List[str]:
        """Identify dependencies from task content."""
        dependencies = []

        # Look for dependency patterns
        dependency_patterns = [
            r"depends on (\w+)",
            r"requires (\w+)",
            r"needs (\w+)",
            r"after (\w+)",
            r"following (\w+)",
        ]

        for pattern in dependency_patterns:
            matches = re.findall(pattern, content.lower())
            dependencies.extend(matches)

        return list(set(dependencies))  # Remove duplicates

    def _determine_complexity_level(self, score: float) -> TaskComplexity:
        """Determine complexity level from score."""
        if score <= 0.5:
            return TaskComplexity.SIMPLE
        elif score <= 1.0:
            return TaskComplexity.MODERATE
        elif score <= 2.0:
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.VERY_COMPLEX

    def _recommend_splitting_strategy(
        self, complexity: TaskComplexity, steps: int
    ) -> SplittingStrategy:
        """Recommend a splitting strategy based on complexity and steps."""
        if complexity == TaskComplexity.SIMPLE or steps <= 2:
            return SplittingStrategy.DEFAULT
        else:
            return SplittingStrategy.DEFAULT  # For now, only DEFAULT is implemented

    def analyze_task_complexity(self, task) -> ComplexityAnalysis:
        """
        Analyzes the complexity of a task to determine if it needs to be split.
        """
        content = self._extract_task_content(task)
        complexity_score = self._calculate_complexity_score(content)

        # Task requires splitting if complexity score is above threshold
        requires_splitting = complexity_score > 1.0

        return ComplexityAnalysis(
            complexity_score=complexity_score,
            requires_splitting=requires_splitting,
        )

    def generate_subtask_graph(self, task: Task) -> SubtaskGraph:
        """
        Generates a graph of subtasks from a complex task.
        This is a placeholder implementation.
        """
        # This would involve identifying logical sub-components of the task.
        subtasks = [
            TaskSplit(
                task_id=f"{task.id}_part1",
                parent_task_id=task.id,
                config={"description": "Part 1"},
            ),
            TaskSplit(
                task_id=f"{task.id}_part2",
                parent_task_id=task.id,
                config={"description": "Part 2"},
            ),
        ]
        dependencies = [(subtasks[0].task_id, subtasks[1].task_id)]
        return SubtaskGraph(subtasks=subtasks, dependencies=dependencies)

    def optimize_splitting_strategy(self, task: Task) -> SplittingStrategy:
        """
        Determines the optimal strategy for splitting a task.
        This is a placeholder implementation.
        """
        # This could be based on provider capabilities, cost, etc.
        return SplittingStrategy.DEFAULT

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
        if hasattr(task, "payload") and task.payload is None:
            # Handle invalid tasks - return special marker for error cases
            return "INVALID_TASK"
        elif hasattr(task, "payload") and isinstance(task.payload, dict):
            return task.payload.get("description", "")
        elif hasattr(task, "config") and isinstance(task.config, dict):
            return task.config.get("description", "")
        return str(task)

    def _calculate_complexity_score(self, content: str) -> float:
        """Calculate complexity score based on task content."""
        if not content:
            return 0.0
        
        # Handle invalid tasks with moderate complexity (defensive programming)
        if content == "INVALID_TASK":
            return 0.8  # This will map to MODERATE complexity level

        # Handle invalid tasks with moderate complexity (defensive programming)
        if content == "INVALID_TASK":
            return 0.8  # This will map to MODERATE complexity level

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

    def _determine_complexity_level(
        self, score: float, steps: int = 0
    ) -> TaskComplexity:
        """Determine complexity level from score and steps."""
        if score <= 0.5:
            return TaskComplexity.SIMPLE
        elif score <= 1.0:
            return TaskComplexity.MODERATE
        elif score <= 2.0:
            return TaskComplexity.COMPLEX
        elif score <= 2.5 and steps <= 20:
            return TaskComplexity.VERY_COMPLEX
        else:
            return TaskComplexity.HIGHLY_COMPLEX

    def _recommend_splitting_strategy(
        self, complexity: TaskComplexity, content: str, dependencies: list
    ) -> SplittingStrategy:
        """Recommend a splitting strategy based on complexity, content, and dependencies."""
        if complexity == TaskComplexity.SIMPLE:
            return SplittingStrategy.NO_SPLIT
        elif complexity == TaskComplexity.COMPLEX and len(dependencies) >= 3:
            return SplittingStrategy.HIERARCHICAL_SPLIT
        elif complexity == TaskComplexity.HIGHLY_COMPLEX:
            return SplittingStrategy.HIERARCHICAL_SPLIT
        else:
            return SplittingStrategy.DEFAULT  # For now, only DEFAULT is implemented

    def analyze_task_complexity(self, task) -> ComplexityAnalysis:
        """
        Analyzes the complexity of a task to determine if it needs to be split.
        """
        content = self._extract_task_content(task)
        complexity_score = self._calculate_complexity_score(content)
        estimated_steps = self._estimate_steps(content)
        identified_dependencies = self._identify_dependencies(content)

        # Determine complexity level from score and steps
        complexity_level = self._determine_complexity_level(
            complexity_score, estimated_steps
        )
        # Get splitting recommendation
        splitting_recommendation = self._recommend_splitting_strategy(
            complexity_level, content, identified_dependencies
        )

        # Task requires splitting if complexity score is above threshold
        requires_splitting = complexity_score > 1.0
        
        # Calculate estimated execution time (simple heuristic)
        estimated_execution_time = estimated_steps * 30.0  # 30 seconds per step
        
        # Basic resource requirements
        resource_requirements = {
            "cpu": "standard",
            "memory": "standard" if complexity_score <= 2.0 else "high",
            "disk": "standard"
        }
        
        # Calculate confidence score
        if content == "INVALID_TASK":
            confidence_score = 0.3  # Low confidence for invalid tasks
        else:
            confidence_score = min(0.9, 0.5 + (0.1 * estimated_steps))
        
        # Generate reasoning
        if content == "INVALID_TASK":
            reasoning = "Error handling: Invalid task detected, using default moderate complexity analysis"
        else:
            reasoning = f"Task complexity score: {complexity_score:.2f}, estimated steps: {estimated_steps}, dependencies: {len(identified_dependencies)}"

        # Calculate estimated execution time (simple heuristic)
        estimated_execution_time = estimated_steps * 30.0  # 30 seconds per step

        # Basic resource requirements
        resource_requirements = {
            "cpu": "standard",
            "memory": "standard" if complexity_score <= 2.0 else "high",
            "disk": "standard",
        }

        # Calculate confidence score
        if content == "INVALID_TASK":
            confidence_score = 0.3  # Low confidence for invalid tasks
        else:
            confidence_score = min(0.9, 0.5 + (0.1 * estimated_steps))

        # Generate reasoning
        if content == "INVALID_TASK":
            reasoning = "Error handling: Invalid task detected, using default moderate complexity analysis"
        else:
            reasoning = f"Task complexity score: {complexity_score:.2f}, estimated steps: {estimated_steps}, dependencies: {len(identified_dependencies)}"

        return ComplexityAnalysis(
            complexity_level=complexity_level,
            estimated_steps=estimated_steps,
            identified_dependencies=identified_dependencies,
            splitting_recommendation=splitting_recommendation,
            estimated_execution_time=estimated_execution_time,
            resource_requirements=resource_requirements,
            confidence_score=confidence_score,
            reasoning=reasoning,
            complexity_score=complexity_score,
            requires_splitting=requires_splitting,
        )

    def generate_subtask_graph(self, task: Task) -> SubtaskGraph:
        """
        Generates a graph of subtasks from a complex task using intelligent analysis.
        """
        content = self._extract_task_content(task)
        estimated_steps = self._estimate_steps(content)
        dependencies_found = self._identify_dependencies(content)

        # Analyze content for logical break points
        subtasks = self._create_intelligent_subtasks(task, content, estimated_steps)

        # Build dependency relationships
        dependencies = self._build_subtask_dependencies(subtasks, dependencies_found)

        return SubtaskGraph(subtasks=subtasks, dependencies=dependencies)

    def _create_intelligent_subtasks(
        self, task: Task, content: str, estimated_steps: int
    ) -> List[TaskSplit]:
        """Create intelligent subtasks based on content analysis."""
        subtasks = []

        # Split based on identified patterns
        if "analyze" in content.lower() and "implement" in content.lower():
            # Analysis + Implementation pattern
            subtasks.extend(
                [
                    TaskSplit(
                        task_id=f"{task.id}_analysis",
                        parent_task_id=task.id,
                        config={
                            "description": f"Analyze requirements for {content[:50]}..."
                        },
                    ),
                    TaskSplit(
                        task_id=f"{task.id}_implementation",
                        parent_task_id=task.id,
                        config={
                            "description": f"Implement solution for {content[:50]}..."
                        },
                    ),
                ]
            )
        elif "setup" in content.lower() and "configure" in content.lower():
            # Setup + Configuration pattern
            subtasks.extend(
                [
                    TaskSplit(
                        task_id=f"{task.id}_setup",
                        parent_task_id=task.id,
                        config={
                            "description": f"Setup environment for {content[:50]}..."
                        },
                    ),
                    TaskSplit(
                        task_id=f"{task.id}_configure",
                        parent_task_id=task.id,
                        config={
                            "description": f"Configure system for {content[:50]}..."
                        },
                    ),
                ]
            )
        elif estimated_steps > 2:
            # Generic multi-step splitting
            for i in range(min(estimated_steps, 4)):  # Cap at 4 subtasks
                subtasks.append(
                    TaskSplit(
                        task_id=f"{task.id}_step{i+1}",
                        parent_task_id=task.id,
                        config={"description": f"Step {i+1}: {content[:30]}..."},
                    )
                )
        else:
            # Single subtask for simple tasks
            subtasks.append(
                TaskSplit(
                    task_id=f"{task.id}_main",
                    parent_task_id=task.id,
                    config=(
                        task.config
                        if hasattr(task, "config")
                        else {"description": content}
                    ),
                )
            )

        return subtasks

    def _build_subtask_dependencies(
        self, subtasks: List[TaskSplit], dependencies_found: List[str]
    ) -> List[tuple]:
        """Build dependency relationships between subtasks."""
        dependencies = []

        if len(subtasks) <= 1:
            return dependencies

        # Create sequential dependencies for most patterns
        for i in range(len(subtasks) - 1):
            dependencies.append((subtasks[i].task_id, subtasks[i + 1].task_id))

        # Add special dependency patterns based on content analysis
        for subtask in subtasks:
            if "_analysis" in subtask.task_id:
                # Analysis tasks should come before implementation
                impl_tasks = [
                    st
                    for st in subtasks
                    if "_implementation" in st.task_id or "_configure" in st.task_id
                ]
                for impl_task in impl_tasks:
                    dependencies.append((subtask.task_id, impl_task.task_id))

        return dependencies

    def optimize_splitting_strategy(self, task: Task) -> SplittingStrategy:
        """
        Determines the optimal strategy for splitting a task.
        This is a placeholder implementation.
        """
        # This could be based on provider capabilities, cost, etc.
        return SplittingStrategy.DEFAULT

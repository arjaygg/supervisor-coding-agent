"""Tests for Task Distribution Engine
Comprehensive testing of the intelligent task distribution system.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from supervisor_agent.db.enums import TaskStatus, TaskType
from supervisor_agent.db.models import Task
from supervisor_agent.orchestration.agent_specialization_engine import (
    AgentSpecialty,
)
from supervisor_agent.orchestration.multi_provider_coordinator import (
    MultiProviderCoordinator,
)
from supervisor_agent.orchestration.task_distribution_engine import (
    ComplexityAnalysis,
    DependencyGraph,
    DependencyManager,
    DistributionResult,
    DistributionStrategy,
    ExecutionPlan,
    IntelligentTaskSplitter,
    SplittingStrategy,
    TaskComplexity,
    TaskDistributionEngine,
    TaskSplit,
    create_task_distribution_engine,
)
from supervisor_agent.providers.base_provider import (
    ProviderType,
    TaskCapability,
)


class TestIntelligentTaskSplitter:
    """Test the IntelligentTaskSplitter component."""

    @pytest.fixture
    def task_splitter(self):
        """Create a task splitter instance."""
        return IntelligentTaskSplitter()

    @pytest.fixture
    def simple_task(self):
        """Create a simple task for testing."""
        return Task(
            id=1,
            type=TaskType.CODE_ANALYSIS,
            status=TaskStatus.PENDING,
            payload={"description": "Display the current status"},
            priority=5,
        )

    @pytest.fixture
    def complex_task(self):
        """Create a complex task for testing."""
        return Task(
            id=2,
            type=TaskType.REFACTOR,
            status=TaskStatus.PENDING,
            payload={
                "description": "Analyze and optimize the multi-provider system architecture, "
                "then integrate with the new workflow engine, followed by "
                "comprehensive testing and validation. The system requires "
                "database integration, API coordination, and authentication."
            },
            priority=8,
        )

    def test_extract_task_content(self, task_splitter, simple_task):
        """Test task content extraction."""
        content = task_splitter._extract_task_content(simple_task)
        assert "display the current status" in content.lower()
        assert isinstance(content, str)

    def test_calculate_complexity_score(self, task_splitter):
        """Test complexity score calculation."""
        simple_content = "show the status"
        complex_content = (
            "analyze and optimize the system architecture then integrate with databases"
        )

        simple_score = task_splitter._calculate_complexity_score(simple_content)
        complex_score = task_splitter._calculate_complexity_score(complex_content)

        assert simple_score < complex_score
        assert simple_score >= 0
        assert complex_score <= 3.0

    def test_estimate_steps(self, task_splitter):
        """Test step estimation."""
        content_with_steps = (
            "First, analyze the data. Then, process the results. Finally, validate."
        )
        content_simple = "show status"

        steps_complex = task_splitter._estimate_steps(content_with_steps)
        steps_simple = task_splitter._estimate_steps(content_simple)

        assert steps_complex > steps_simple
        assert steps_simple >= 1

    def test_identify_dependencies(self, task_splitter):
        """Test dependency identification."""
        content_with_deps = (
            "This requires database access and needs authentication system"
        )
        content_no_deps = "simple display task"

        deps_found = task_splitter._identify_dependencies(content_with_deps)
        deps_none = task_splitter._identify_dependencies(content_no_deps)

        assert len(deps_found) > 0
        assert "database" in deps_found
        assert "authentication" in deps_found
        assert len(deps_none) == 0

    def test_determine_complexity_level(self, task_splitter):
        """Test complexity level determination."""
        # Test simple task
        assert (
            task_splitter._determine_complexity_level(0.3, 2) == TaskComplexity.SIMPLE
        )

        # Test moderate task
        assert (
            task_splitter._determine_complexity_level(0.8, 4) == TaskComplexity.MODERATE
        )

        # Test complex task
        assert (
            task_splitter._determine_complexity_level(1.5, 10) == TaskComplexity.COMPLEX
        )

        # Test highly complex task
        assert (
            task_splitter._determine_complexity_level(2.5, 25)
            == TaskComplexity.HIGHLY_COMPLEX
        )

    def test_recommend_splitting_strategy(self, task_splitter):
        """Test splitting strategy recommendation."""
        # Simple task should not be split
        strategy = task_splitter._recommend_splitting_strategy(
            TaskComplexity.SIMPLE, "simple task", []
        )
        assert strategy == SplittingStrategy.NO_SPLIT

        # Complex task with many dependencies should use hierarchical splitting
        strategy = task_splitter._recommend_splitting_strategy(
            TaskComplexity.COMPLEX,
            "complex task",
            ["dep1", "dep2", "dep3", "dep4"],
        )
        assert strategy == SplittingStrategy.HIERARCHICAL_SPLIT

    def test_analyze_task_complexity_simple(self, task_splitter, simple_task):
        """Test complexity analysis for simple task."""
        analysis = task_splitter.analyze_task_complexity(simple_task)

        assert isinstance(analysis, ComplexityAnalysis)
        assert analysis.complexity_level == TaskComplexity.SIMPLE
        assert analysis.splitting_recommendation == SplittingStrategy.NO_SPLIT
        assert analysis.estimated_steps >= 1
        assert analysis.confidence_score > 0
        assert isinstance(analysis.reasoning, str)

    def test_analyze_task_complexity_complex(self, task_splitter, complex_task):
        """Test complexity analysis for complex task."""
        analysis = task_splitter.analyze_task_complexity(complex_task)

        assert isinstance(analysis, ComplexityAnalysis)
        assert analysis.complexity_level in [
            TaskComplexity.MODERATE,
            TaskComplexity.COMPLEX,
            TaskComplexity.HIGHLY_COMPLEX,
        ]
        assert analysis.estimated_steps > 1
        assert len(analysis.identified_dependencies) > 0
        assert analysis.confidence_score > 0

    def test_error_handling(self, task_splitter):
        """Test error handling in complexity analysis."""
        # Create invalid task
        invalid_task = Mock()
        invalid_task.id = 999
        invalid_task.payload = None

        analysis = task_splitter.analyze_task_complexity(invalid_task)

        # Should return default analysis
        assert analysis.complexity_level == TaskComplexity.MODERATE
        assert analysis.confidence_score == 0.3
        assert "error" in analysis.reasoning.lower()


class TestDependencyManager:
    """Test the DependencyManager component."""

    @pytest.fixture
    def dependency_manager(self):
        """Create a dependency manager instance."""
        return DependencyManager()

    @pytest.fixture
    def sample_task_splits(self):
        """Create sample task splits for testing."""
        return [
            TaskSplit(
                split_id="task_1_0",
                original_task_id="1",
                subtask_index=0,
                task_type=TaskCapability.ANALYSIS,
                agent_specialty=AgentSpecialty.CODE_ARCHITECT,
                priority=5,
                estimated_duration=300,
                dependencies=[],
            ),
            TaskSplit(
                split_id="task_1_1",
                original_task_id="1",
                subtask_index=1,
                task_type=TaskCapability.PROCESSING,
                agent_specialty=AgentSpecialty.GENERAL_DEVELOPER,
                priority=5,
                estimated_duration=600,
                dependencies=["task_1_0"],
            ),
            TaskSplit(
                split_id="task_1_2",
                original_task_id="1",
                subtask_index=2,
                task_type=TaskCapability.VALIDATION,
                agent_specialty=AgentSpecialty.TEST_ENGINEER,
                priority=5,
                estimated_duration=300,
                dependencies=["task_1_1"],
            ),
        ]

    def test_build_dependency_graph(self, dependency_manager, sample_task_splits):
        """Test dependency graph building."""
        graph = dependency_manager.build_dependency_graph(sample_task_splits)

        assert isinstance(graph, DependencyGraph)
        assert len(graph.nodes) == 3
        assert len(graph.execution_levels) > 0
        assert graph.total_estimated_time > 0
        assert 0 <= graph.parallelization_potential <= 1.0

    def test_circular_dependency_detection(self, dependency_manager):
        """Test circular dependency detection."""
        edges_with_cycle = {
            "A": ["B"],
            "B": ["C"],
            "C": ["A"],
        }  # Creates cycle

        edges_no_cycle = {"A": ["B"], "B": ["C"], "C": []}

        assert dependency_manager._has_circular_dependencies(edges_with_cycle) is True
        assert dependency_manager._has_circular_dependencies(edges_no_cycle) is False

    def test_execution_levels_calculation(self, dependency_manager, sample_task_splits):
        """Test execution levels calculation."""
        edges = {
            "task_1_0": [],
            "task_1_1": ["task_1_0"],
            "task_1_2": ["task_1_1"],
        }

        levels = dependency_manager._calculate_execution_levels(
            sample_task_splits, edges
        )

        assert len(levels) == 3  # Sequential tasks
        assert levels[0] == ["task_1_0"]
        assert levels[1] == ["task_1_1"]
        assert levels[2] == ["task_1_2"]

    def test_critical_path_identification(self, dependency_manager, sample_task_splits):
        """Test critical path identification."""
        graph = dependency_manager.build_dependency_graph(sample_task_splits)

        assert len(graph.critical_path) > 0
        assert "task_1_0" in graph.critical_path  # Should be in critical path

    def test_parallelization_potential(self, dependency_manager):
        """Test parallelization potential calculation."""
        # All tasks can run in parallel
        parallel_levels = [["A", "B", "C"]]
        parallel_tasks = [Mock(split_id=f"task_{i}") for i in range(3)]

        potential_high = dependency_manager._calculate_parallelization_potential(
            parallel_levels, parallel_tasks
        )

        # All tasks must run sequentially
        sequential_levels = [["A"], ["B"], ["C"]]

        potential_low = dependency_manager._calculate_parallelization_potential(
            sequential_levels, parallel_tasks
        )

        assert potential_high > potential_low
        assert 0 <= potential_high <= 1.0
        assert 0 <= potential_low <= 1.0


class TestTaskDistributionEngine:
    """Test the main TaskDistributionEngine."""

    @pytest.fixture
    def mock_agent_specialization_engine(self):
        """Create mock agent specialization engine."""
        mock = Mock()
        mock.determine_agent_specialty = AsyncMock(
            return_value=AgentSpecialty.GENERAL_DEVELOPER
        )
        return mock

    @pytest.fixture
    def mock_multi_provider_coordinator(self):
        """Create mock multi-provider coordinator."""
        mock = Mock()
        mock.get_available_providers = AsyncMock(
            return_value=[ProviderType.CLAUDE_CLI, ProviderType.OPENAI]
        )
        return mock

    @pytest.fixture
    def distribution_engine(
        self, mock_agent_specialization_engine, mock_multi_provider_coordinator
    ):
        """Create distribution engine with mocked dependencies."""
        return TaskDistributionEngine(
            agent_specialization_engine=mock_agent_specialization_engine,
            multi_provider_coordinator=mock_multi_provider_coordinator,
        )

    @pytest.fixture
    def sample_task(self):
        """Create a sample task for testing."""
        return Task(
            id=123,
            type=TaskType.REFACTOR,
            status=TaskStatus.PENDING,
            payload={
                "description": "Create a new feature with validation and testing. "
                "This requires database integration and API development."
            },
            priority=7,
        )

    @pytest.mark.asyncio
    async def test_distribute_task_simple(self, distribution_engine, sample_task):
        """Test task distribution for simple case."""
        # Mock task loading
        with patch.object(distribution_engine, "_load_task", return_value=sample_task):
            result = await distribution_engine.distribute_task(
                sample_task, strategy=DistributionStrategy.DEPENDENCY_AWARE
            )

        assert isinstance(result, DistributionResult)
        assert result.success is True
        assert result.original_task_id == str(sample_task.id)
        assert len(result.task_splits) > 0
        assert result.execution_plan is not None
        assert result.processing_time > 0

    @pytest.mark.asyncio
    async def test_distribute_task_with_string_id(self, distribution_engine):
        """Test task distribution with string task ID."""
        task_id = "456"

        result = await distribution_engine.distribute_task(
            task_id, strategy=DistributionStrategy.PARALLEL
        )

        assert isinstance(result, DistributionResult)
        assert result.original_task_id == task_id
        # Should handle string IDs gracefully

    @pytest.mark.asyncio
    async def test_distribute_task_error_handling(self, distribution_engine):
        """Test error handling in task distribution."""
        # Create invalid task that will cause errors
        invalid_task = Mock()
        invalid_task.id = None
        invalid_task.payload = {"invalid": "data"}

        result = await distribution_engine.distribute_task(invalid_task)

        assert result.success is False
        assert result.error_message is not None
        assert "failed" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_strategy_optimization(self, distribution_engine, sample_task):
        """Test distribution strategy optimization."""
        # Test with different constraints
        constraints_cost = {"optimize_cost": True}
        constraints_performance = {"optimize_performance": True}

        with patch.object(distribution_engine, "_load_task", return_value=sample_task):
            result_cost = await distribution_engine.distribute_task(
                sample_task,
                strategy=DistributionStrategy.DEPENDENCY_AWARE,
                constraints=constraints_cost,
            )

            result_performance = await distribution_engine.distribute_task(
                sample_task,
                strategy=DistributionStrategy.DEPENDENCY_AWARE,
                constraints=constraints_performance,
            )

        # Strategies should be optimized based on constraints
        assert result_cost.strategy_used == DistributionStrategy.COST_OPTIMIZED
        assert (
            result_performance.strategy_used
            == DistributionStrategy.PERFORMANCE_OPTIMIZED
        )

    @pytest.mark.asyncio
    async def test_provider_assignment(self, distribution_engine, sample_task):
        """Test provider assignment logic."""
        preferred_providers = [ProviderType.CLAUDE_CLI]

        with patch.object(distribution_engine, "_load_task", return_value=sample_task):
            result = await distribution_engine.distribute_task(
                sample_task, providers=preferred_providers
            )

        assert result.success is True
        assert result.execution_plan is not None

        # Check that preferred providers are used
        assigned_providers = set(result.execution_plan.provider_assignments.values())
        assert ProviderType.CLAUDE_CLI in assigned_providers

    def test_resource_allocation_calculation(self, distribution_engine):
        """Test resource allocation calculation."""
        task_splits = [
            TaskSplit(
                split_id="test_1",
                original_task_id="1",
                subtask_index=0,
                task_type=TaskCapability.PROCESSING,
                agent_specialty=AgentSpecialty.GENERAL_DEVELOPER,
                priority=5,
                estimated_duration=300,
                critical_path=True,
            )
        ]

        provider_assignments = {"test_1": ProviderType.CLAUDE_CLI}

        allocation = distribution_engine._calculate_resource_allocation(
            task_splits, provider_assignments
        )

        assert "test_1" in allocation
        assert "cpu_cores" in allocation["test_1"]
        assert "memory_mb" in allocation["test_1"]
        assert allocation["test_1"]["cpu_cores"] >= 1
        assert allocation["test_1"]["memory_mb"] >= 512

    def test_execution_cost_estimation(self, distribution_engine):
        """Test execution cost estimation."""
        task_splits = [
            TaskSplit(
                split_id="test_1",
                original_task_id="1",
                subtask_index=0,
                task_type=TaskCapability.PROCESSING,
                agent_specialty=AgentSpecialty.GENERAL_DEVELOPER,
                priority=5,
                estimated_duration=300,
                resource_requirements={"estimated_tokens": 2000},
            )
        ]

        provider_assignments = {"test_1": ProviderType.CLAUDE_CLI}

        cost = distribution_engine._estimate_execution_cost(
            task_splits, provider_assignments
        )

        assert isinstance(cost, float)
        assert cost >= 0

    @pytest.mark.asyncio
    async def test_execution_plan_validation(self, distribution_engine):
        """Test execution plan validation."""
        # Create a plan with high cost
        execution_plan = ExecutionPlan(
            plan_id="test_plan",
            original_task_id="1",
            dependency_graph=Mock(),
            provider_assignments={},
            execution_strategy=DistributionStrategy.PARALLEL,
            estimated_total_time=7200,  # 2 hours
            estimated_cost=15.0,  # High cost
            resource_allocation={},
        )

        validation = await distribution_engine._validate_execution_plan(execution_plan)

        assert "valid" in validation
        assert "warnings" in validation
        assert "recommendations" in validation
        assert len(validation["warnings"]) > 0  # Should warn about high cost and time

    def test_get_execution_plan(self, distribution_engine):
        """Test execution plan retrieval."""
        plan_id = "test_plan_123"
        mock_plan = Mock()
        distribution_engine._execution_plans[plan_id] = mock_plan

        retrieved_plan = distribution_engine.get_execution_plan(plan_id)
        assert retrieved_plan == mock_plan

        # Test non-existent plan
        non_existent = distribution_engine.get_execution_plan("non_existent")
        assert non_existent is None

    def test_get_distribution_result(self, distribution_engine):
        """Test distribution result retrieval."""
        task_id = "task_123"
        mock_result = Mock()
        distribution_engine._active_distributions[task_id] = mock_result

        retrieved_result = distribution_engine.get_distribution_result(task_id)
        assert retrieved_result == mock_result

        # Test non-existent result
        non_existent = distribution_engine.get_distribution_result("non_existent")
        assert non_existent is None


class TestTaskSplitGeneration:
    """Test task split generation strategies."""

    @pytest.fixture
    def distribution_engine(self):
        """Create distribution engine for testing."""
        return TaskDistributionEngine()

    @pytest.fixture
    def sample_task(self):
        """Create sample task."""
        return Task(
            id=789,
            type=TaskType.REFACTOR,
            status=TaskStatus.PENDING,
            payload={"description": "Multi-step processing task"},
            priority=5,
        )

    def test_no_split_strategy(self, distribution_engine, sample_task):
        """Test no-split strategy."""
        analysis = ComplexityAnalysis(
            complexity_level=TaskComplexity.SIMPLE,
            estimated_steps=1,
            identified_dependencies=[],
            splitting_recommendation=SplittingStrategy.NO_SPLIT,
            estimated_execution_time=180,
            resource_requirements={},
            confidence_score=0.9,
            reasoning="Simple atomic task",
        )

        splits = distribution_engine._create_task_splits_by_strategy(
            sample_task, analysis
        )

        assert len(splits) == 0  # No splits created for NO_SPLIT strategy

    def test_linear_split_strategy(self, distribution_engine, sample_task):
        """Test linear split strategy."""
        analysis = ComplexityAnalysis(
            complexity_level=TaskComplexity.MODERATE,
            estimated_steps=4,
            identified_dependencies=["database"],
            splitting_recommendation=SplittingStrategy.LINEAR_SPLIT,
            estimated_execution_time=1200,
            resource_requirements={},
            confidence_score=0.8,
            reasoning="Sequential processing task",
        )

        splits = distribution_engine._create_task_splits_by_strategy(
            sample_task, analysis
        )

        assert len(splits) == 4
        # Check dependencies are set up correctly for linear execution
        for i, split in enumerate(splits):
            if i > 0:
                assert f"{sample_task.id}_{i-1}" in split.dependencies
            else:
                assert len(split.dependencies) == 0
            assert split.parallelizable is False

    def test_parallel_split_strategy(self, distribution_engine, sample_task):
        """Test parallel split strategy."""
        analysis = ComplexityAnalysis(
            complexity_level=TaskComplexity.MODERATE,
            estimated_steps=6,
            identified_dependencies=[],
            splitting_recommendation=SplittingStrategy.PARALLEL_SPLIT,
            estimated_execution_time=900,
            resource_requirements={},
            confidence_score=0.7,
            reasoning="Independent parallel components",
        )

        splits = distribution_engine._create_task_splits_by_strategy(
            sample_task, analysis
        )

        assert len(splits) >= 2
        assert len(splits) <= 4  # Capped at 4 parallel tasks

        # All splits should be parallelizable with no dependencies
        for split in splits:
            assert split.parallelizable is True
            assert len(split.dependencies) == 0

    def test_hierarchical_split_strategy(self, distribution_engine, sample_task):
        """Test hierarchical split strategy."""
        analysis = ComplexityAnalysis(
            complexity_level=TaskComplexity.COMPLEX,
            estimated_steps=8,
            identified_dependencies=["database", "api", "auth", "validation"],
            splitting_recommendation=SplittingStrategy.HIERARCHICAL_SPLIT,
            estimated_execution_time=2400,
            resource_requirements={},
            confidence_score=0.85,
            reasoning="Complex hierarchical dependencies",
        )

        splits = distribution_engine._create_task_splits_by_strategy(
            sample_task, analysis
        )

        assert len(splits) >= 3  # At least planning, implementation, validation

        # Check for planning phase
        planning_tasks = [s for s in splits if "plan" in s.split_id]
        assert len(planning_tasks) == 1

        # Check for validation phase
        validation_tasks = [s for s in splits if "validate" in s.split_id]
        assert len(validation_tasks) == 1

        # Validation should depend on implementation tasks
        validation_task = validation_tasks[0]
        assert len(validation_task.dependencies) > 0


class TestDistributionStrategies:
    """Test different distribution strategies."""

    @pytest.fixture
    def distribution_engine(self):
        """Create distribution engine."""
        return TaskDistributionEngine()

    def test_strategy_optimization_simple_task(self, distribution_engine):
        """Test strategy optimization for simple tasks."""
        simple_task = Mock()
        simple_task.id = 1

        analysis = ComplexityAnalysis(
            complexity_level=TaskComplexity.SIMPLE,
            estimated_steps=1,
            identified_dependencies=[],
            splitting_recommendation=SplittingStrategy.NO_SPLIT,
            estimated_execution_time=60,
            resource_requirements={},
            confidence_score=0.9,
            reasoning="Simple task",
        )

        dependency_graph = Mock()
        dependency_graph.parallelization_potential = 0.1

        # Even if we request parallel, should be optimized to sequential for simple tasks
        optimized = asyncio.run(
            distribution_engine._optimize_distribution_strategy(
                simple_task,
                DistributionStrategy.PARALLEL,
                analysis,
                dependency_graph,
            )
        )

        assert optimized == DistributionStrategy.SEQUENTIAL

    def test_strategy_optimization_high_parallelization(self, distribution_engine):
        """Test strategy optimization for high parallelization potential."""
        complex_task = Mock()
        complex_task.id = 2

        analysis = ComplexityAnalysis(
            complexity_level=TaskComplexity.COMPLEX,
            estimated_steps=6,
            identified_dependencies=["database"],
            splitting_recommendation=SplittingStrategy.PARALLEL_SPLIT,
            estimated_execution_time=1800,
            resource_requirements={},
            confidence_score=0.8,
            reasoning="High parallelization potential",
        )

        dependency_graph = Mock()
        dependency_graph.parallelization_potential = 0.8  # High potential

        optimized = asyncio.run(
            distribution_engine._optimize_distribution_strategy(
                complex_task,
                DistributionStrategy.DEPENDENCY_AWARE,
                analysis,
                dependency_graph,
            )
        )

        assert optimized == DistributionStrategy.PARALLEL

    def test_strategy_optimization_with_constraints(self, distribution_engine):
        """Test strategy optimization with constraints."""
        task = Mock()
        task.id = 3

        analysis = Mock()
        analysis.complexity_level = TaskComplexity.MODERATE

        dependency_graph = Mock()
        dependency_graph.parallelization_potential = 0.5

        # Test cost optimization constraint
        cost_optimized = asyncio.run(
            distribution_engine._optimize_distribution_strategy(
                task,
                DistributionStrategy.DEPENDENCY_AWARE,
                analysis,
                dependency_graph,
                {"optimize_cost": True},
            )
        )

        assert cost_optimized == DistributionStrategy.COST_OPTIMIZED

        # Test performance optimization constraint
        perf_optimized = asyncio.run(
            distribution_engine._optimize_distribution_strategy(
                task,
                DistributionStrategy.DEPENDENCY_AWARE,
                analysis,
                dependency_graph,
                {"optimize_performance": True},
            )
        )

        assert perf_optimized == DistributionStrategy.PERFORMANCE_OPTIMIZED


class TestFactoryFunction:
    """Test the factory function."""

    def test_create_task_distribution_engine(self):
        """Test the factory function."""
        engine = create_task_distribution_engine()

        assert isinstance(engine, TaskDistributionEngine)
        assert engine.agent_specialization_engine is not None
        assert engine.multi_provider_coordinator is not None
        assert engine.task_splitter is not None
        assert engine.dependency_manager is not None

    def test_create_with_custom_dependencies(self):
        """Test factory function with custom dependencies."""
        mock_agent_engine = Mock()
        mock_coordinator = Mock()

        engine = create_task_distribution_engine(
            agent_specialization_engine=mock_agent_engine,
            multi_provider_coordinator=mock_coordinator,
        )

        assert engine.agent_specialization_engine == mock_agent_engine
        assert engine.multi_provider_coordinator == mock_coordinator


class TestIntegration:
    """Integration tests for the complete system."""

    @pytest.mark.asyncio
    async def test_end_to_end_task_distribution(self):
        """Test complete end-to-end task distribution."""
        # Create a real task
        task = Task(
            id=999,
            type=TaskType.REFACTOR,
            status=TaskStatus.PENDING,
            payload={
                "description": "Implement a comprehensive user authentication system. "
                "This requires database schema design, API endpoint creation, "
                "security validation, and comprehensive testing. The system "
                "must integrate with existing authorization mechanisms."
            },
            priority=8,
        )

        # Create engine with mocked external dependencies
        mock_coordinator = Mock()
        mock_coordinator.get_available_providers = AsyncMock(
            return_value=[ProviderType.CLAUDE_CLI, ProviderType.OPENAI]
        )

        engine = TaskDistributionEngine(multi_provider_coordinator=mock_coordinator)

        # Mock task loading
        with patch.object(engine, "_load_task", return_value=task):
            result = await engine.distribute_task(
                task,
                strategy=DistributionStrategy.DEPENDENCY_AWARE,
                providers=[ProviderType.CLAUDE_CLI],
            )

        # Verify complete result
        assert result.success is True
        assert len(result.task_splits) > 1  # Should be split into multiple tasks
        assert result.complexity_analysis.complexity_level in [
            TaskComplexity.MODERATE,
            TaskComplexity.COMPLEX,
            TaskComplexity.HIGHLY_COMPLEX,
        ]
        assert result.execution_plan is not None
        assert len(result.execution_plan.dependency_graph.execution_levels) > 0
        assert result.execution_plan.estimated_cost > 0
        assert result.processing_time > 0

        # Verify task splits have proper structure
        for split in result.task_splits:
            assert split.split_id.startswith(str(task.id))
            assert isinstance(split.agent_specialty, AgentSpecialty)
            assert isinstance(split.task_type, TaskCapability)
            assert split.estimated_duration > 0
            assert split.priority > 0

        # Verify execution plan completeness
        plan = result.execution_plan
        assert len(plan.provider_assignments) == len(result.task_splits)
        assert len(plan.resource_allocation) == len(result.task_splits)
        assert plan.estimated_total_time > 0

        # Verify dependency graph integrity
        graph = plan.dependency_graph
        assert len(graph.nodes) == len(result.task_splits)
        assert graph.total_estimated_time > 0
        assert 0 <= graph.parallelization_potential <= 1.0

    @pytest.mark.asyncio
    async def test_error_recovery_and_fallbacks(self):
        """Test error recovery and fallback mechanisms."""
        # Create engine with failing coordinator
        mock_coordinator = Mock()
        mock_coordinator.get_available_providers = AsyncMock(
            side_effect=Exception("Provider coordinator failed")
        )

        engine = TaskDistributionEngine(multi_provider_coordinator=mock_coordinator)

        task = Task(
            id=888,
            type=TaskType.ANALYSIS,
            status=TaskStatus.PENDING,
            payload={"description": "Simple analysis task"},
            priority=3,
        )

        with patch.object(engine, "_load_task", return_value=task):
            result = await engine.distribute_task(task)

        # Should still succeed with fallback mechanisms
        assert result.success is True
        assert len(result.task_splits) > 0

        # Should use fallback provider
        assigned_providers = set(result.execution_plan.provider_assignments.values())
        assert ProviderType.CLAUDE_CLI in assigned_providers

    def test_performance_characteristics(self):
        """Test performance characteristics of the system."""
        engine = TaskDistributionEngine()

        # Test with various complexity levels
        complexity_levels = [
            TaskComplexity.SIMPLE,
            TaskComplexity.MODERATE,
            TaskComplexity.COMPLEX,
            TaskComplexity.HIGHLY_COMPLEX,
        ]

        for complexity in complexity_levels:
            analysis = ComplexityAnalysis(
                complexity_level=complexity,
                estimated_steps=complexity.value == "simple"
                and 1
                or complexity.value == "moderate"
                and 3
                or complexity.value == "complex"
                and 10
                or 25,
                identified_dependencies=[],
                splitting_recommendation=SplittingStrategy.LINEAR_SPLIT,
                estimated_execution_time=300,
                resource_requirements={},
                confidence_score=0.8,
                reasoning=f"Test {complexity.value} task",
            )

            task = Task(
                id=100 + len(complexity.value),
                type=TaskType.REFACTOR,
                status=TaskStatus.PENDING,
                payload={"description": f"Test {complexity.value} task"},
                priority=5,
            )

            # Generate splits
            splits = engine._create_task_splits_by_strategy(task, analysis)

            # Verify reasonable split counts
            if complexity == TaskComplexity.SIMPLE:
                assert len(splits) <= 1
            elif complexity == TaskComplexity.MODERATE:
                assert 1 <= len(splits) <= 5
            elif complexity == TaskComplexity.COMPLEX:
                assert 3 <= len(splits) <= 15
            else:  # HIGHLY_COMPLEX
                assert len(splits) >= 3

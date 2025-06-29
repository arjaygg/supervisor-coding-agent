"""
Tests for DAG Resolver

Test suite for dependency resolution, topological sorting, and DAG validation.
Implements comprehensive test cases following TDD principles.
"""

import pytest

from supervisor_agent.core.dag_resolver import (CircularDependencyError,
                                                DAGResolver, InvalidDAGError,
                                                StandardDependencyChecker,
                                                ValidationResult)
from supervisor_agent.core.workflow_models import (DependencyCondition,
                                                   DependencyDefinition,
                                                   WorkflowDefinition)


class TestDAGResolver:
    """Test DAG resolution and validation"""

    @pytest.fixture
    def dag_resolver(self):
        """Create DAG resolver instance"""
        return DAGResolver()

    @pytest.fixture
    def simple_linear_workflow(self):
        """Simple linear workflow: A → B → C"""
        return WorkflowDefinition(
            name="Linear Workflow",
            description="Simple linear workflow",
            tasks=[
                {"id": "A", "name": "Task A", "type": "CODE_ANALYSIS", "config": {}},
                {"id": "B", "name": "Task B", "type": "PR_REVIEW", "config": {}},
                {"id": "C", "name": "Task C", "type": "BUG_FIX", "config": {}},
            ],
            dependencies=[
                {"task_id": "B", "depends_on": "A", "condition": "SUCCESS"},
                {"task_id": "C", "depends_on": "B", "condition": "SUCCESS"},
            ],
        )

    @pytest.fixture
    def parallel_workflow(self):
        """Parallel workflow: A → [B, C] → D"""
        return WorkflowDefinition(
            name="Parallel Workflow",
            description="Workflow with parallel execution",
            tasks=[
                {"id": "A", "name": "Task A", "type": "CODE_ANALYSIS", "config": {}},
                {"id": "B", "name": "Task B", "type": "PR_REVIEW", "config": {}},
                {"id": "C", "name": "Task C", "type": "REFACTOR", "config": {}},
                {"id": "D", "name": "Task D", "type": "BUG_FIX", "config": {}},
            ],
            dependencies=[
                {"task_id": "B", "depends_on": "A", "condition": "SUCCESS"},
                {"task_id": "C", "depends_on": "A", "condition": "SUCCESS"},
                {"task_id": "D", "depends_on": "B", "condition": "SUCCESS"},
                {"task_id": "D", "depends_on": "C", "condition": "SUCCESS"},
            ],
        )

    @pytest.fixture
    def circular_workflow(self):
        """Circular dependency workflow: A → B → C → A"""
        return WorkflowDefinition(
            name="Circular Workflow",
            description="Workflow with circular dependency",
            tasks=[
                {"id": "A", "name": "Task A", "type": "CODE_ANALYSIS", "config": {}},
                {"id": "B", "name": "Task B", "type": "PR_REVIEW", "config": {}},
                {"id": "C", "name": "Task C", "type": "BUG_FIX", "config": {}},
            ],
            dependencies=[
                {"task_id": "B", "depends_on": "A", "condition": "SUCCESS"},
                {"task_id": "C", "depends_on": "B", "condition": "SUCCESS"},
                {
                    "task_id": "A",
                    "depends_on": "C",
                    "condition": "SUCCESS",
                },  # Creates cycle
            ],
        )

    def test_validate_simple_linear_workflow(
        self, dag_resolver, simple_linear_workflow
    ):
        """Test validation of simple linear workflow"""

        result = dag_resolver.validate_dag(simple_linear_workflow)

        assert result.is_valid is True
        assert result.error_message is None

    def test_validate_parallel_workflow(self, dag_resolver, parallel_workflow):
        """Test validation of parallel workflow"""

        result = dag_resolver.validate_dag(parallel_workflow)

        assert result.is_valid is True
        assert result.error_message is None

    def test_validate_circular_dependency(self, dag_resolver, circular_workflow):
        """Test detection of circular dependencies"""

        result = dag_resolver.validate_dag(circular_workflow)

        assert result.is_valid is False
        assert "circular dependency" in result.error_message.lower()

    def test_validate_empty_workflow(self, dag_resolver):
        """Test validation of empty workflow"""

        empty_workflow = WorkflowDefinition(
            name="Empty", description="Empty workflow", tasks=[], dependencies=[]
        )

        result = dag_resolver.validate_dag(empty_workflow)

        assert result.is_valid is False
        assert "at least one task" in result.error_message

    def test_validate_duplicate_task_ids(self, dag_resolver):
        """Test detection of duplicate task IDs"""

        duplicate_workflow = WorkflowDefinition(
            name="Duplicate IDs",
            description="Workflow with duplicate task IDs",
            tasks=[
                {"id": "A", "name": "Task A1", "type": "CODE_ANALYSIS", "config": {}},
                {
                    "id": "A",
                    "name": "Task A2",
                    "type": "PR_REVIEW",
                    "config": {},
                },  # Duplicate ID
            ],
            dependencies=[],
        )

        result = dag_resolver.validate_dag(duplicate_workflow)

        assert result.is_valid is False
        assert "unique" in result.error_message.lower()

    def test_validate_invalid_dependency_reference(self, dag_resolver):
        """Test detection of invalid dependency references"""

        invalid_workflow = WorkflowDefinition(
            name="Invalid Dependency",
            description="Workflow with invalid dependency",
            tasks=[
                {"id": "A", "name": "Task A", "type": "CODE_ANALYSIS", "config": {}},
                {"id": "B", "name": "Task B", "type": "PR_REVIEW", "config": {}},
            ],
            dependencies=[
                {
                    "task_id": "B",
                    "depends_on": "NONEXISTENT",
                    "condition": "SUCCESS",
                }  # Invalid reference
            ],
        )

        result = dag_resolver.validate_dag(invalid_workflow)

        assert result.is_valid is False
        assert "non-existent" in result.error_message.lower()

    def test_validate_self_dependency(self, dag_resolver):
        """Test detection of self-dependencies"""

        self_dep_workflow = WorkflowDefinition(
            name="Self Dependency",
            description="Workflow with self dependency",
            tasks=[
                {"id": "A", "name": "Task A", "type": "CODE_ANALYSIS", "config": {}}
            ],
            dependencies=[
                {
                    "task_id": "A",
                    "depends_on": "A",
                    "condition": "SUCCESS",
                }  # Self dependency
            ],
        )

        result = dag_resolver.validate_dag(self_dep_workflow)

        assert result.is_valid is False
        assert "cannot depend on itself" in result.error_message

    def test_create_execution_plan_linear(self, dag_resolver, simple_linear_workflow):
        """Test execution plan creation for linear workflow"""

        plan = dag_resolver.create_execution_plan(simple_linear_workflow)

        # Verify execution order
        assert len(plan.execution_order) == 3  # Three sequential groups
        assert plan.execution_order[0] == ["A"]  # A runs first
        assert plan.execution_order[1] == ["B"]  # B runs after A
        assert plan.execution_order[2] == ["C"]  # C runs after B

        # Verify task map
        assert len(plan.task_map) == 3
        assert "A" in plan.task_map
        assert "B" in plan.task_map
        assert "C" in plan.task_map

        # Verify dependency map
        assert plan.dependency_map == {"B": ["A"], "C": ["B"]}

    def test_create_execution_plan_parallel(self, dag_resolver, parallel_workflow):
        """Test execution plan creation for parallel workflow"""

        plan = dag_resolver.create_execution_plan(parallel_workflow)

        # Verify execution order
        assert len(plan.execution_order) == 3  # Three groups
        assert plan.execution_order[0] == ["A"]  # A runs first
        assert set(plan.execution_order[1]) == {"B", "C"}  # B and C run in parallel
        assert plan.execution_order[2] == ["D"]  # D runs after B and C

        # Verify dependency map
        assert plan.dependency_map == {"B": ["A"], "C": ["A"], "D": ["B", "C"]}

    def test_create_execution_plan_invalid_dag(self, dag_resolver, circular_workflow):
        """Test execution plan creation with invalid DAG"""

        with pytest.raises(InvalidDAGError):
            dag_resolver.create_execution_plan(circular_workflow)

    def test_build_dependency_map(self, dag_resolver):
        """Test dependency map building"""

        dependencies = [
            {"task_id": "B", "depends_on": "A", "condition": "SUCCESS"},
            {"task_id": "C", "depends_on": "A", "condition": "SUCCESS"},
            {"task_id": "D", "depends_on": "B", "condition": "SUCCESS"},
            {"task_id": "D", "depends_on": "C", "condition": "SUCCESS"},
        ]

        dep_map = dag_resolver._build_dependency_map(dependencies)

        expected = {"B": ["A"], "C": ["A"], "D": ["B", "C"]}

        assert dep_map == expected

    def test_detect_circular_dependencies_simple_cycle(self, dag_resolver):
        """Test circular dependency detection for simple cycle"""

        task_ids = {"A", "B", "C"}
        dependency_map = {
            "B": ["A"],
            "C": ["B"],
            "A": ["C"],  # Creates A → C → B → A cycle
        }

        with pytest.raises(
            CircularDependencyError, match="Circular dependency detected"
        ):
            dag_resolver._detect_circular_dependencies(task_ids, dependency_map)

    def test_detect_circular_dependencies_no_cycle(self, dag_resolver):
        """Test circular dependency detection with no cycle"""

        task_ids = {"A", "B", "C", "D"}
        dependency_map = {"B": ["A"], "C": ["A"], "D": ["B", "C"]}

        # Should not raise exception
        dag_resolver._detect_circular_dependencies(task_ids, dependency_map)

    def test_topological_sort_parallel_linear(self, dag_resolver):
        """Test topological sort for linear dependencies"""

        task_ids = {"A", "B", "C"}
        dependency_map = {"B": ["A"], "C": ["B"]}

        execution_order = dag_resolver._topological_sort_parallel(
            task_ids, dependency_map
        )

        assert execution_order == [["A"], ["B"], ["C"]]

    def test_topological_sort_parallel_diamond(self, dag_resolver):
        """Test topological sort for diamond pattern"""

        task_ids = {"A", "B", "C", "D"}
        dependency_map = {"B": ["A"], "C": ["A"], "D": ["B", "C"]}

        execution_order = dag_resolver._topological_sort_parallel(
            task_ids, dependency_map
        )

        assert len(execution_order) == 3
        assert execution_order[0] == ["A"]
        assert set(execution_order[1]) == {"B", "C"}  # Parallel execution
        assert execution_order[2] == ["D"]

    def test_topological_sort_parallel_no_dependencies(self, dag_resolver):
        """Test topological sort with no dependencies"""

        task_ids = {"A", "B", "C"}
        dependency_map = {}

        execution_order = dag_resolver._topological_sort_parallel(
            task_ids, dependency_map
        )

        # All tasks should execute in parallel
        assert len(execution_order) == 1
        assert set(execution_order[0]) == {"A", "B", "C"}

    def test_has_disconnected_components_connected(self, dag_resolver):
        """Test disconnected components detection with connected graph"""

        task_ids = {"A", "B", "C"}
        dependency_map = {"B": ["A"], "C": ["B"]}

        result = dag_resolver._has_disconnected_components(task_ids, dependency_map)

        assert result is False

    def test_has_disconnected_components_disconnected(self, dag_resolver):
        """Test disconnected components detection with disconnected graph"""

        task_ids = {"A", "B", "C", "D"}
        dependency_map = {"B": ["A"]}  # C and D are disconnected

        result = dag_resolver._has_disconnected_components(task_ids, dependency_map)

        assert result is True

    def test_has_disconnected_components_single_task(self, dag_resolver):
        """Test disconnected components with single task"""

        task_ids = {"A"}
        dependency_map = {}

        result = dag_resolver._has_disconnected_components(task_ids, dependency_map)

        assert result is False

    def test_can_task_execute_success_condition(self, dag_resolver):
        """Test task execution permission with success condition"""

        dependency_results = {"task_a": {"status": "COMPLETED", "success": True}}

        dependencies = [
            DependencyDefinition("task_b", "task_a", DependencyCondition.SUCCESS)
        ]

        result = dag_resolver.can_task_execute(
            "task_b", dependency_results, dependencies
        )

        assert result is True

    def test_can_task_execute_failure_condition(self, dag_resolver):
        """Test task execution permission with failure condition"""

        dependency_results = {"task_a": {"status": "FAILED", "success": False}}

        dependencies = [
            DependencyDefinition("task_b", "task_a", DependencyCondition.FAILURE)
        ]

        result = dag_resolver.can_task_execute(
            "task_b", dependency_results, dependencies
        )

        assert result is True

    def test_can_task_execute_completion_condition(self, dag_resolver):
        """Test task execution permission with completion condition"""

        dependency_results = {"task_a": {"status": "FAILED", "success": False}}

        dependencies = [
            DependencyDefinition("task_b", "task_a", DependencyCondition.COMPLETION)
        ]

        result = dag_resolver.can_task_execute(
            "task_b", dependency_results, dependencies
        )

        assert result is True  # Should be true for any completion

    def test_can_task_execute_unmet_dependency(self, dag_resolver):
        """Test task execution permission with unmet dependency"""

        dependency_results = {"task_a": {"status": "FAILED", "success": False}}

        dependencies = [
            DependencyDefinition("task_b", "task_a", DependencyCondition.SUCCESS)
        ]

        result = dag_resolver.can_task_execute(
            "task_b", dependency_results, dependencies
        )

        assert result is False


class TestStandardDependencyChecker:
    """Test standard dependency checker implementation"""

    @pytest.fixture
    def dependency_checker(self):
        """Create standard dependency checker"""
        return StandardDependencyChecker()

    def test_success_condition_met(self, dependency_checker):
        """Test success condition when met"""

        result = {"status": "COMPLETED", "success": True}

        can_execute = dependency_checker.can_execute(
            "task_b", "task_a", result, DependencyCondition.SUCCESS
        )

        assert can_execute is True

    def test_success_condition_not_met(self, dependency_checker):
        """Test success condition when not met"""

        result = {"status": "FAILED", "success": False}

        can_execute = dependency_checker.can_execute(
            "task_b", "task_a", result, DependencyCondition.SUCCESS
        )

        assert can_execute is False

    def test_failure_condition_met(self, dependency_checker):
        """Test failure condition when met"""

        result = {"status": "FAILED", "success": False}

        can_execute = dependency_checker.can_execute(
            "task_b", "task_a", result, DependencyCondition.FAILURE
        )

        assert can_execute is True

    def test_failure_condition_not_met(self, dependency_checker):
        """Test failure condition when not met"""

        result = {"status": "COMPLETED", "success": True}

        can_execute = dependency_checker.can_execute(
            "task_b", "task_a", result, DependencyCondition.FAILURE
        )

        assert can_execute is False

    def test_completion_condition_success(self, dependency_checker):
        """Test completion condition with success"""

        result = {"status": "COMPLETED", "success": True}

        can_execute = dependency_checker.can_execute(
            "task_b", "task_a", result, DependencyCondition.COMPLETION
        )

        assert can_execute is True

    def test_completion_condition_failure(self, dependency_checker):
        """Test completion condition with failure"""

        result = {"status": "FAILED", "success": False}

        can_execute = dependency_checker.can_execute(
            "task_b", "task_a", result, DependencyCondition.COMPLETION
        )

        assert can_execute is True

    def test_custom_condition_simple(self, dependency_checker):
        """Test simple custom condition"""

        result = {"status": "COMPLETED", "success": True, "error_count": 0}

        can_execute = dependency_checker.can_execute(
            "task_b", "task_a", result, DependencyCondition.CUSTOM, "{error_count} == 0"
        )

        assert can_execute is True

    def test_custom_condition_complex(self, dependency_checker):
        """Test complex custom condition"""

        result = {"status": "COMPLETED", "success": True, "error_count": 2}

        can_execute = dependency_checker.can_execute(
            "task_b",
            "task_a",
            result,
            DependencyCondition.CUSTOM,
            "{success} and {error_count} < 5",
        )

        assert can_execute is True

    def test_custom_condition_invalid_expression(self, dependency_checker):
        """Test custom condition with invalid expression"""

        result = {"status": "COMPLETED", "success": True}

        # Should handle invalid expression gracefully
        can_execute = dependency_checker.can_execute(
            "task_b", "task_a", result, DependencyCondition.CUSTOM, "invalid syntax {{"
        )

        assert can_execute is False

    def test_empty_result(self, dependency_checker):
        """Test with empty dependency result"""

        can_execute = dependency_checker.can_execute(
            "task_b", "task_a", {}, DependencyCondition.SUCCESS
        )

        assert can_execute is False

    def test_none_result(self, dependency_checker):
        """Test with None dependency result"""

        can_execute = dependency_checker.can_execute(
            "task_b", "task_a", None, DependencyCondition.SUCCESS
        )

        assert can_execute is False

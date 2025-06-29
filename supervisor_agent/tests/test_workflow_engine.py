"""
Tests for Workflow Engine

Comprehensive test suite for workflow orchestration functionality.
Follows TDD principles with test cases covering DAG resolution,
workflow execution, and error handling.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from supervisor_agent.core.dag_resolver import DAGResolver, ValidationResult
from supervisor_agent.core.workflow_engine import WorkflowEngine, WorkflowExecutor
from supervisor_agent.core.workflow_models import (
    WorkflowContext,
    WorkflowDefinition,
    WorkflowResult,
    WorkflowStatus,
)
from supervisor_agent.db.models import TaskStatus, TaskType


class TestWorkflowEngine:
    """Test workflow engine functionality"""

    @pytest.fixture
    def mock_dag_resolver(self):
        """Mock DAG resolver"""
        resolver = Mock(spec=DAGResolver)
        resolver.validate_dag.return_value = ValidationResult(True)
        return resolver

    @pytest.fixture
    def mock_task_processor(self):
        """Mock task processor"""
        processor = Mock()
        processor.queue_task = AsyncMock()
        return processor

    @pytest.fixture
    def workflow_engine(self, mock_dag_resolver):
        """Create workflow engine with mocked dependencies"""
        return WorkflowEngine(mock_dag_resolver)

    @pytest.fixture
    def simple_workflow_def(self):
        """Simple linear workflow definition"""
        return WorkflowDefinition(
            name="Test Workflow",
            description="Simple test workflow",
            tasks=[
                {
                    "id": "task1",
                    "name": "First Task",
                    "type": "CODE_ANALYSIS",
                    "config": {"input": "test"},
                },
                {
                    "id": "task2",
                    "name": "Second Task",
                    "type": "PR_REVIEW",
                    "config": {"pr_number": 123},
                },
            ],
            dependencies=[
                {"task_id": "task2", "depends_on": "task1", "condition": "SUCCESS"}
            ],
        )

    @pytest.mark.asyncio
    async def test_create_workflow_success(self, workflow_engine, simple_workflow_def):
        """Test successful workflow creation"""

        with patch(
            "supervisor_agent.core.workflow_engine.SessionLocal"
        ) as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            workflow_id = await workflow_engine.create_workflow(
                simple_workflow_def, created_by="test_user"
            )

            # Verify workflow ID is generated
            assert workflow_id is not None
            assert len(workflow_id) == 36  # UUID length

            # Verify database interaction
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_workflow_invalid_dag(
        self, workflow_engine, simple_workflow_def
    ):
        """Test workflow creation with invalid DAG"""

        # Mock invalid DAG validation
        workflow_engine.dag_resolver.validate_dag.return_value = ValidationResult(
            False, "Circular dependency detected"
        )

        with pytest.raises(ValueError, match="Invalid workflow definition"):
            await workflow_engine.create_workflow(simple_workflow_def)

    @pytest.mark.asyncio
    async def test_execute_workflow_success(self, workflow_engine):
        """Test successful workflow execution"""

        workflow_id = "test-workflow-id"

        with patch(
            "supervisor_agent.core.workflow_engine.SessionLocal"
        ) as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock workflow lookup
            mock_workflow = Mock()
            mock_workflow.id = workflow_id
            mock_workflow.is_active = True
            mock_workflow.definition = {
                "name": "Test Workflow",
                "description": "Test workflow for execution",
                "tasks": [],
                "dependencies": [],
            }
            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_workflow
            )

            # Mock execution creation
            with patch(
                "supervisor_agent.core.workflow_engine.WorkflowExecutor"
            ) as mock_executor_class:
                mock_executor = Mock()
                mock_executor_class.return_value = mock_executor

                with patch("asyncio.create_task") as mock_create_task:
                    execution_id = await workflow_engine.execute_workflow(
                        workflow_id=workflow_id, context={"test": "data"}
                    )

                    # Verify execution ID is generated
                    assert execution_id is not None
                    assert len(execution_id) == 36  # UUID length

                    # Verify executor is created and started
                    mock_executor_class.assert_called_once()
                    mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_workflow_not_found(self, workflow_engine):
        """Test workflow execution with non-existent workflow"""

        with patch(
            "supervisor_agent.core.workflow_engine.SessionLocal"
        ) as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            with pytest.raises(ValueError, match="Workflow not found"):
                await workflow_engine.execute_workflow("non-existent-id")

    @pytest.mark.asyncio
    async def test_cancel_execution_success(self, workflow_engine):
        """Test successful execution cancellation"""

        execution_id = "test-execution-id"

        # Add mock executor to active executions
        mock_executor = Mock()
        mock_executor.cancel = AsyncMock()
        workflow_engine._active_executions[execution_id] = mock_executor

        with patch(
            "supervisor_agent.core.workflow_engine.SessionLocal"
        ) as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock execution lookup
            mock_execution = Mock()
            mock_execution.status = WorkflowStatus.RUNNING
            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_execution
            )

            result = await workflow_engine.cancel_execution(execution_id)

            # Verify cancellation
            assert result is True
            mock_executor.cancel.assert_called_once()
            assert execution_id not in workflow_engine._active_executions
            assert mock_execution.status == WorkflowStatus.CANCELLED


class TestWorkflowExecutor:
    """Test workflow executor functionality"""

    @pytest.fixture
    def mock_dag_resolver(self):
        """Mock DAG resolver with execution plan"""
        resolver = Mock(spec=DAGResolver)

        # Mock execution plan
        from supervisor_agent.core.workflow_models import ExecutionPlan, TaskDefinition

        execution_plan = ExecutionPlan(
            execution_order=[["task1"], ["task2"]],
            task_map={
                "task1": TaskDefinition(
                    "task1", "First Task", "CODE_ANALYSIS", {"input": "test"}
                ),
                "task2": TaskDefinition(
                    "task2", "Second Task", "PR_REVIEW", {"pr_number": 123}
                ),
            },
            dependency_map={"task2": ["task1"]},
        )
        resolver.create_execution_plan.return_value = execution_plan

        return resolver

    @pytest.fixture
    def mock_task_processor(self):
        """Mock task processor"""
        processor = Mock()
        processor.queue_task = AsyncMock()
        return processor

    @pytest.fixture
    def workflow_executor(
        self, mock_dag_resolver, mock_task_processor, simple_workflow_def
    ):
        """Create workflow executor"""
        context = WorkflowContext(
            workflow_execution_id="test-execution-id", variables={"test": "data"}
        )

        return WorkflowExecutor(
            execution_id="test-execution-id",
            workflow_def=simple_workflow_def,
            context=context,
            dag_resolver=mock_dag_resolver,
            task_processor=mock_task_processor,
        )

    @pytest.fixture
    def simple_workflow_def(self):
        """Simple workflow definition"""
        return WorkflowDefinition(
            name="Test Workflow",
            description="Test",
            tasks=[
                {
                    "id": "task1",
                    "name": "Task 1",
                    "type": "CODE_ANALYSIS",
                    "config": {},
                },
                {"id": "task2", "name": "Task 2", "type": "PR_REVIEW", "config": {}},
            ],
            dependencies=[],
        )

    @pytest.mark.asyncio
    async def test_execute_success(self, workflow_executor):
        """Test successful workflow execution"""

        with patch.object(
            workflow_executor, "_update_execution_status", new_callable=AsyncMock
        ):
            with patch.object(
                workflow_executor, "_execute_plan", new_callable=AsyncMock
            ):
                with patch.object(
                    workflow_executor, "_has_failed_tasks", return_value=False
                ):

                    result = await workflow_executor.execute()

                    # Verify result
                    assert isinstance(result, WorkflowResult)
                    assert result.status == WorkflowStatus.COMPLETED
                    assert result.workflow_execution_id == "test-execution-id"
                    assert result.execution_time_seconds is not None

    @pytest.mark.asyncio
    async def test_execute_with_failed_tasks(self, workflow_executor):
        """Test workflow execution with failed tasks"""

        with patch.object(
            workflow_executor, "_update_execution_status", new_callable=AsyncMock
        ):
            with patch.object(
                workflow_executor, "_execute_plan", new_callable=AsyncMock
            ):
                with patch.object(
                    workflow_executor, "_has_failed_tasks", return_value=True
                ):

                    result = await workflow_executor.execute()

                    # Verify result
                    assert result.status == WorkflowStatus.FAILED
                    assert result.error_message == "One or more tasks failed"

    @pytest.mark.asyncio
    async def test_execute_cancelled(self, workflow_executor):
        """Test cancelled workflow execution"""

        # Set cancelled flag
        workflow_executor._cancelled = True

        with patch.object(
            workflow_executor, "_update_execution_status", new_callable=AsyncMock
        ):
            with patch.object(
                workflow_executor, "_execute_plan", new_callable=AsyncMock
            ):

                result = await workflow_executor.execute()

                # Verify result
                assert result.status == WorkflowStatus.CANCELLED
                assert result.error_message == "Workflow execution was cancelled"

    @pytest.mark.asyncio
    async def test_execute_task_success(self, workflow_executor):
        """Test successful task execution"""

        from supervisor_agent.core.workflow_models import TaskDefinition

        task_def = TaskDefinition(
            "test-task", "Test Task", "CODE_ANALYSIS", {"test": "config"}
        )

        with patch.object(
            workflow_executor, "_create_task_record", new_callable=AsyncMock
        ) as mock_create:
            with patch.object(
                workflow_executor,
                "_create_task_execution_record",
                new_callable=AsyncMock,
            ):
                with patch.object(
                    workflow_executor,
                    "_wait_for_task_completion",
                    new_callable=AsyncMock,
                ) as mock_wait:
                    with patch.object(
                        workflow_executor,
                        "_update_task_execution_result",
                        new_callable=AsyncMock,
                    ):

                        # Mock task record
                        mock_task = Mock()
                        mock_task.id = 123
                        mock_create.return_value = mock_task

                        # Mock task completion
                        mock_wait.return_value = {
                            "status": "COMPLETED",
                            "success": True,
                            "result": {"output": "test"},
                        }

                        result = await workflow_executor._execute_task(task_def)

                        # Verify result
                        assert result["status"] == "COMPLETED"
                        assert result["success"] is True
                        assert "result" in result

    @pytest.mark.asyncio
    async def test_cancel_execution(self, workflow_executor):
        """Test execution cancellation"""

        # Add mock active tasks
        mock_task1 = Mock()
        mock_task2 = Mock()
        workflow_executor._active_tasks = {"task1": mock_task1, "task2": mock_task2}

        with patch.object(
            workflow_executor, "_update_execution_status", new_callable=AsyncMock
        ):
            await workflow_executor.cancel()

            # Verify cancellation
            assert workflow_executor._cancelled is True
            mock_task1.cancel.assert_called_once()
            mock_task2.cancel.assert_called_once()

    def test_map_task_type(self, workflow_executor):
        """Test task type mapping"""

        # Test standard mappings
        assert workflow_executor._map_task_type("PR_REVIEW") == TaskType.PR_REVIEW
        assert (
            workflow_executor._map_task_type("CODE_ANALYSIS") == TaskType.CODE_ANALYSIS
        )
        assert workflow_executor._map_task_type("BUG_FIX") == TaskType.BUG_FIX

        # Test unknown type (should default to CODE_ANALYSIS)
        assert (
            workflow_executor._map_task_type("UNKNOWN_TYPE") == TaskType.CODE_ANALYSIS
        )

    def test_has_failed_tasks(self, workflow_executor):
        """Test failed tasks detection"""

        # No tasks - should return False
        assert workflow_executor._has_failed_tasks() is False

        # All successful tasks
        workflow_executor._task_results = {
            "task1": {"success": True},
            "task2": {"success": True},
        }
        assert workflow_executor._has_failed_tasks() is False

        # One failed task
        workflow_executor._task_results = {
            "task1": {"success": True},
            "task2": {"success": False},
        }
        assert workflow_executor._has_failed_tasks() is True

        # Missing success field (should be treated as failed)
        workflow_executor._task_results = {
            "task1": {"success": True},
            "task2": {"status": "FAILED"},  # No success field
        }
        assert workflow_executor._has_failed_tasks() is True


class TestWorkflowIntegration:
    """Integration tests for workflow system"""

    @pytest.mark.asyncio
    async def test_end_to_end_workflow_execution(self):
        """Test complete workflow execution flow"""

        # This would be a more comprehensive integration test
        # involving real database connections and task processing
        # For now, we'll skip this to avoid complex setup requirements
        pytest.skip("Integration test requires full database setup")

    @pytest.mark.asyncio
    async def test_parallel_task_execution(self):
        """Test parallel task execution in workflow"""

        # Test that tasks with no dependencies can execute in parallel
        pytest.skip("Integration test for parallel execution")

    @pytest.mark.asyncio
    async def test_workflow_with_conditional_dependencies(self):
        """Test workflow with conditional dependencies"""

        # Test different dependency conditions (success, failure, completion)
        pytest.skip("Integration test for conditional dependencies")

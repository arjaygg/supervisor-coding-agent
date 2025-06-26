"""
Test Suite for AI-Enhanced DAG Resolver

Comprehensive tests for AI-powered workflow optimization, parallel execution
planning, and bottleneck prediction capabilities.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from supervisor_agent.intelligence.ai_enhanced_dag_resolver import (
    AIEnhancedDAGResolver,
    OptimizedExecutionPlan,
    PerformanceMetrics,
    create_ai_enhanced_dag_resolver
)
from supervisor_agent.intelligence.workflow_synthesizer import (
    EnhancedWorkflowDefinition,
    ClaudeAgentWrapper
)
from supervisor_agent.db.workflow_models import (
    TaskDefinition, ExecutionPlan
)


class TestAIEnhancedDAGResolver:
    """Test AI-enhanced DAG resolver functionality"""
    
    @pytest.fixture
    def mock_claude_agent(self):
        """Create mock Claude agent for testing"""
        agent = AsyncMock(spec=ClaudeAgentWrapper)
        agent.execute_task = AsyncMock()
        return agent
    
    @pytest.fixture
    def sample_workflow(self):
        """Create sample workflow for testing"""
        return EnhancedWorkflowDefinition(
            name="Test Workflow",
            description="Test workflow for AI optimization",
            tasks=[
                TaskDefinition(
                    id="task-1",
                    name="Analysis Task",
                    type="CODE_ANALYSIS",
                    config={"timeout_minutes": 30},
                    dependencies=[]
                ),
                TaskDefinition(
                    id="task-2",
                    name="Implementation Task",
                    type="CODE_IMPLEMENTATION", 
                    config={"timeout_minutes": 60},
                    dependencies=["task-1"]
                ),
                TaskDefinition(
                    id="task-3",
                    name="Testing Task",
                    type="TESTING",
                    config={"timeout_minutes": 45},
                    dependencies=["task-2"]
                ),
                TaskDefinition(
                    id="task-4",
                    name="Parallel Analysis",
                    type="CODE_ANALYSIS",
                    config={"timeout_minutes": 30},
                    dependencies=[]
                )
            ],
            version="1.0"
        )
    
    @pytest.fixture
    def resolver(self, mock_claude_agent):
        """Create AI-enhanced DAG resolver for testing"""
        return AIEnhancedDAGResolver(claude_agent=mock_claude_agent)
    
    @pytest.mark.asyncio
    async def test_create_intelligent_execution_plan(self, resolver, mock_claude_agent, sample_workflow):
        """Test creation of AI-optimized execution plan"""
        # Given: Mock AI optimization response
        mock_ai_optimizations = {
            "parallel_opportunities": [
                {
                    "group": ["task-1", "task-4"],
                    "efficiency_gain": 0.6,
                    "reasoning": "Independent analysis tasks can run in parallel"
                }
            ],
            "bottleneck_predictions": [
                {
                    "task_id": "task-2",
                    "type": "compute_intensive",
                    "probability": 0.7,
                    "impact": "medium"
                }
            ],
            "resource_optimization": {
                "cpu_allocation": {"task-1": 1, "task-2": 2, "task-3": 1, "task-4": 1},
                "memory_allocation": {"task-1": 1024, "task-2": 2048, "task-3": 1024, "task-4": 1024}
            },
            "execution_time_estimate": 90,
            "confidence_score": 0.85
        }
        
        mock_claude_agent.execute_task.return_value = {
            "result": json.dumps(mock_ai_optimizations)
        }
        
        # When: Creating intelligent execution plan
        plan = await resolver.create_intelligent_execution_plan(sample_workflow)
        
        # Then: Optimized plan is created
        assert isinstance(plan, OptimizedExecutionPlan)
        assert plan.confidence_score == 0.85
        assert plan.estimated_execution_time_minutes == 90
        assert len(plan.bottleneck_predictions) == 1
        assert plan.parallel_efficiency_score >= 0.0
        
        # And: AI was called for optimization
        mock_claude_agent.execute_task.assert_called_once()
        call_args = mock_claude_agent.execute_task.call_args[0][0]
        assert call_args["type"] == "execution_plan_optimization"
    
    @pytest.mark.asyncio
    async def test_create_execution_plan_fallback_without_ai(self, sample_workflow):
        """Test execution plan creation without AI (fallback mode)"""
        # Given: Resolver without Claude agent
        resolver = AIEnhancedDAGResolver(claude_agent=None)
        
        # When: Creating execution plan
        plan = await resolver.create_intelligent_execution_plan(sample_workflow)
        
        # Then: Fallback plan is created
        assert isinstance(plan, OptimizedExecutionPlan)
        assert plan.confidence_score == 0.5  # Conservative score
        assert len(plan.execution_order) > 0
        assert len(plan.task_map) == 4
    
    @pytest.mark.asyncio
    async def test_predict_execution_bottlenecks_with_ai(self, resolver, mock_claude_agent):
        """Test AI-powered bottleneck prediction"""
        # Given: Sample execution plan
        execution_plan = ExecutionPlan(
            execution_order=[["task-1"], ["task-2"], ["task-3"]],
            task_map={
                "task-1": TaskDefinition("task-1", "Task 1", "ANALYSIS", {}),
                "task-2": TaskDefinition("task-2", "Task 2", "IMPLEMENTATION", {}),
                "task-3": TaskDefinition("task-3", "Task 3", "TESTING", {})
            },
            dependency_map={"task-2": ["task-1"], "task-3": ["task-2"]}
        )
        
        # And: Mock AI bottleneck prediction
        mock_bottlenecks = {
            "bottlenecks": [
                {
                    "type": "resource_contention",
                    "task_id": "task-2",
                    "description": "High CPU usage task may cause delays",
                    "probability": 0.8,
                    "impact": "high",
                    "mitigation_strategies": ["increase_cpu_allocation", "break_into_subtasks"]
                }
            ]
        }
        
        mock_claude_agent.execute_task.return_value = {
            "result": json.dumps(mock_bottlenecks)
        }
        
        # When: Predicting bottlenecks
        bottlenecks = await resolver.predict_execution_bottlenecks(execution_plan)
        
        # Then: Bottlenecks are predicted
        assert len(bottlenecks) == 1
        assert bottlenecks[0]["type"] == "resource_contention"
        assert bottlenecks[0]["task_id"] == "task-2"
        assert bottlenecks[0]["probability"] == 0.8
        assert "mitigation_strategies" in bottlenecks[0]
    
    @pytest.mark.asyncio
    async def test_predict_bottlenecks_heuristic_fallback(self):
        """Test heuristic bottleneck prediction when AI is unavailable"""
        # Given: Resolver without AI
        resolver = AIEnhancedDAGResolver(claude_agent=None)
        
        # And: Execution plan with dependency-heavy task
        execution_plan = ExecutionPlan(
            execution_order=[["task-1", "task-2", "task-3", "task-4", "task-5", "task-6"]],
            task_map={f"task-{i}": TaskDefinition(f"task-{i}", f"Task {i}", "ANALYSIS", {}) for i in range(1, 7)},
            dependency_map={"bottleneck-task": ["task-1", "task-2", "task-3", "task-4"]}
        )
        
        # When: Predicting bottlenecks
        bottlenecks = await resolver.predict_execution_bottlenecks(execution_plan)
        
        # Then: Heuristic bottlenecks are identified
        assert len(bottlenecks) >= 1
        # Should detect resource contention from large parallel group
        resource_bottlenecks = [b for b in bottlenecks if b["type"] == "resource_contention"]
        assert len(resource_bottlenecks) > 0
    
    @pytest.mark.asyncio
    async def test_optimize_parallel_execution(self, resolver, mock_claude_agent, sample_workflow):
        """Test parallel execution optimization"""
        # Given: Mock parallel optimization response
        mock_optimization = {
            "parallel_groups": [
                {
                    "group_id": "group_1",
                    "tasks": ["task-1", "task-4"],
                    "estimated_speedup": 1.8,
                    "resource_requirements": {"cpu": 2, "memory": "4GB"}
                }
            ],
            "optimization_metrics": {
                "total_speedup": 1.8,
                "resource_efficiency": 0.85,
                "complexity_increase": 0.1
            }
        }
        
        mock_claude_agent.execute_task.return_value = {
            "result": json.dumps(mock_optimization)
        }
        
        # When: Optimizing parallel execution
        optimization = await resolver.optimize_parallel_execution(sample_workflow)
        
        # Then: Optimization recommendations are returned
        assert "parallel_groups" in optimization
        assert len(optimization["parallel_groups"]) == 1
        assert optimization["optimization_metrics"]["total_speedup"] == 1.8
        
        # And: AI was called for optimization
        mock_claude_agent.execute_task.assert_called_once()
        call_args = mock_claude_agent.execute_task.call_args[0][0]
        assert call_args["type"] == "parallel_optimization"
    
    @pytest.mark.asyncio
    async def test_suggest_resource_allocation(self, resolver, mock_claude_agent):
        """Test resource allocation suggestions"""
        # Given: Optimized execution plan
        execution_plan = OptimizedExecutionPlan(
            execution_order=[["task-1"], ["task-2"]],
            task_map={
                "task-1": TaskDefinition("task-1", "Task 1", "CODE_ANALYSIS", {}),
                "task-2": TaskDefinition("task-2", "Task 2", "CODE_IMPLEMENTATION", {})
            },
            dependency_map={"task-2": ["task-1"]},
            parallel_efficiency_score=0.7,
            bottleneck_predictions=[],
            optimization_suggestions=[],
            resource_allocation_hints={},
            estimated_execution_time_minutes=60,
            confidence_score=0.8
        )
        
        # And: Mock resource allocation response
        mock_allocation = {
            "cpu_allocation": {"task-1": 1, "task-2": 2},
            "memory_allocation": {"task-1": 1024, "task-2": 2048},
            "io_optimization": ["enable_caching", "use_ssd"],
            "cost_optimization": {
                "estimated_cost_usd": 15.50,
                "optimization_opportunities": ["use_spot_instances"]
            }
        }
        
        mock_claude_agent.execute_task.return_value = {
            "result": json.dumps(mock_allocation)
        }
        
        # When: Getting resource allocation suggestions
        allocation = await resolver.suggest_resource_allocation(execution_plan)
        
        # Then: Resource allocation is suggested
        assert "cpu_allocation" in allocation
        assert allocation["cpu_allocation"]["task-1"] == 1
        assert allocation["cpu_allocation"]["task-2"] == 2
        assert "memory_allocation" in allocation
        assert "io_optimization" in allocation
    
    @pytest.mark.asyncio
    async def test_resource_allocation_heuristic_fallback(self):
        """Test heuristic resource allocation when AI is unavailable"""
        # Given: Resolver without AI
        resolver = AIEnhancedDAGResolver(claude_agent=None)
        
        # And: Execution plan
        execution_plan = OptimizedExecutionPlan(
            execution_order=[["task-1"], ["task-2"]],
            task_map={
                "task-1": TaskDefinition("task-1", "Task 1", "CODE_ANALYSIS", {}),
                "task-2": TaskDefinition("task-2", "Task 2", "CODE_IMPLEMENTATION", {})
            },
            dependency_map={"task-2": ["task-1"]},
            parallel_efficiency_score=0.7,
            bottleneck_predictions=[],
            optimization_suggestions=[],
            resource_allocation_hints={},
            estimated_execution_time_minutes=60,
            confidence_score=0.8
        )
        
        # When: Getting resource allocation suggestions
        allocation = await resolver.suggest_resource_allocation(execution_plan)
        
        # Then: Heuristic allocation is provided
        assert "cpu_allocation" in allocation
        assert "memory_allocation" in allocation
        # CODE_ANALYSIS should get less resources than CODE_IMPLEMENTATION
        assert allocation["cpu_allocation"]["task-1"] == 1
        assert allocation["cpu_allocation"]["task-2"] == 2
        assert allocation["memory_allocation"]["task-1"] == 1024
        assert allocation["memory_allocation"]["task-2"] == 2048
    
    @pytest.mark.asyncio
    async def test_ai_optimization_failure_graceful_fallback(self, resolver, mock_claude_agent, sample_workflow):
        """Test graceful fallback when AI optimization fails"""
        # Given: Claude agent that fails
        mock_claude_agent.execute_task.side_effect = Exception("AI service unavailable")
        
        # When: Creating execution plan
        plan = await resolver.create_intelligent_execution_plan(sample_workflow)
        
        # Then: Fallback plan is created
        assert isinstance(plan, OptimizedExecutionPlan)
        assert plan.confidence_score == 0.5  # Fallback confidence
        assert len(plan.task_map) == 4
        assert len(plan.execution_order) > 0
    
    @pytest.mark.asyncio
    async def test_parallel_efficiency_calculation(self, resolver):
        """Test parallel efficiency score calculation"""
        # Given: Base and optimized execution orders
        base_order = [["task-1"], ["task-2"], ["task-3"], ["task-4"]]  # 4 sequential steps
        optimized_order = [["task-1", "task-4"], ["task-2"], ["task-3"]]  # 3 steps with parallelism
        
        # When: Calculating efficiency score
        efficiency = resolver._calculate_efficiency_score(base_order, optimized_order)
        
        # Then: Efficiency improvement is calculated correctly
        expected_improvement = (4 - 3) / 4  # 25% improvement
        assert efficiency == expected_improvement
        assert 0.0 <= efficiency <= 1.0
    
    def test_merge_into_parallel_groups(self, resolver):
        """Test merging tasks into parallel execution groups"""
        # Given: Sequential execution order
        execution_order = [["task-1"], ["task-2"], ["task-3"]]
        
        # When: Merging task-1 and task-3 into parallel group
        resolver._merge_into_parallel_groups(execution_order, ["task-1", "task-3"])
        
        # Then: Tasks are merged into same group
        # task-3 should be moved to group with task-1
        assert "task-1" in execution_order[0]
        assert "task-3" in execution_order[0]
        # Verify task-3 was removed from its original group
        for group in execution_order:
            count_task_3 = group.count("task-3")
            assert count_task_3 <= 1  # Should appear at most once
    
    @pytest.mark.asyncio
    async def test_performance_metrics_integration(self, resolver):
        """Test integration with performance metrics"""
        # Given: Performance history
        resolver.performance_history["CODE_ANALYSIS"] = PerformanceMetrics(
            task_type="CODE_ANALYSIS",
            average_execution_time_minutes=15.0,
            success_rate=0.95,
            typical_resource_usage={"cpu": 1, "memory_mb": 1024},
            common_failure_modes=["timeout", "memory_error"],
            parallel_scalability=0.8
        )
        
        # And: Execution plan
        execution_plan = OptimizedExecutionPlan(
            execution_order=[["task-1"]],
            task_map={"task-1": TaskDefinition("task-1", "Task 1", "CODE_ANALYSIS", {})},
            dependency_map={},
            parallel_efficiency_score=0.8,
            bottleneck_predictions=[],
            optimization_suggestions=[],
            resource_allocation_hints={},
            estimated_execution_time_minutes=60,
            confidence_score=0.8
        )
        
        # When: Getting performance data
        performance_data = await resolver._get_performance_data(execution_plan)
        
        # Then: Performance history is used
        assert "task-1" in performance_data
        assert performance_data["task-1"]["average_execution_time"] == 15.0
        assert performance_data["task-1"]["success_rate"] == 0.95
        assert performance_data["task-1"]["parallel_scalability"] == 0.8


class TestFactoryFunction:
    """Test factory function for AI-enhanced DAG resolver"""
    
    @pytest.mark.asyncio
    async def test_create_ai_enhanced_dag_resolver(self):
        """Test factory function creates resolver correctly"""
        # Given: Mock dependencies
        mock_claude_agent = AsyncMock(spec=ClaudeAgentWrapper)
        mock_provider_coordinator = MagicMock()
        
        # When: Creating resolver via factory
        resolver = await create_ai_enhanced_dag_resolver(
            claude_agent=mock_claude_agent,
            provider_coordinator=mock_provider_coordinator
        )
        
        # Then: Resolver is properly configured
        assert isinstance(resolver, AIEnhancedDAGResolver)
        assert resolver.claude_agent == mock_claude_agent
        assert resolver.provider_coordinator == mock_provider_coordinator
    
    @pytest.mark.asyncio
    async def test_create_resolver_without_dependencies(self):
        """Test factory function works without optional dependencies"""
        # When: Creating resolver without dependencies
        resolver = await create_ai_enhanced_dag_resolver()
        
        # Then: Resolver is created with None dependencies
        assert isinstance(resolver, AIEnhancedDAGResolver)
        assert resolver.claude_agent is None
        assert resolver.provider_coordinator is None


class TestOptimizedExecutionPlan:
    """Test optimized execution plan functionality"""
    
    def test_optimized_execution_plan_creation(self):
        """Test creation of optimized execution plan"""
        # Given: Plan data
        execution_order = [["task-1"], ["task-2"]]
        task_map = {
            "task-1": TaskDefinition("task-1", "Task 1", "ANALYSIS", {}),
            "task-2": TaskDefinition("task-2", "Task 2", "IMPLEMENTATION", {})
        }
        dependency_map = {"task-2": ["task-1"]}
        
        # When: Creating optimized plan
        plan = OptimizedExecutionPlan(
            execution_order=execution_order,
            task_map=task_map,
            dependency_map=dependency_map,
            parallel_efficiency_score=0.8,
            bottleneck_predictions=[],
            optimization_suggestions=[],
            resource_allocation_hints={},
            estimated_execution_time_minutes=45,
            confidence_score=0.9
        )
        
        # Then: Plan is properly created
        assert plan.parallel_efficiency_score == 0.8
        assert plan.estimated_execution_time_minutes == 45
        assert plan.confidence_score == 0.9
        assert len(plan.execution_order) == 2
        assert len(plan.task_map) == 2
    
    def test_optimized_execution_plan_serialization(self):
        """Test serialization of optimized execution plan"""
        # Given: Optimized execution plan
        plan = OptimizedExecutionPlan(
            execution_order=[["task-1"]],
            task_map={"task-1": TaskDefinition("task-1", "Task 1", "ANALYSIS", {})},
            dependency_map={},
            parallel_efficiency_score=0.75,
            bottleneck_predictions=[{"type": "resource_contention", "task_id": "task-1"}],
            optimization_suggestions=[{"suggestion": "increase_memory"}],
            resource_allocation_hints={"cpu": {"task-1": 2}},
            estimated_execution_time_minutes=30,
            confidence_score=0.85
        )
        
        # When: Serializing to dict
        plan_dict = plan.to_dict()
        
        # Then: All fields are included
        assert plan_dict["parallel_efficiency_score"] == 0.75
        assert plan_dict["estimated_execution_time_minutes"] == 30
        assert plan_dict["confidence_score"] == 0.85
        assert "bottleneck_predictions" in plan_dict
        assert "optimization_suggestions" in plan_dict
        assert "resource_allocation_hints" in plan_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
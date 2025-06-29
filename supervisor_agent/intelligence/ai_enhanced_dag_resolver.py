"""
AI-Enhanced DAG Resolver

Extends the existing DAG resolver with AI-powered optimization capabilities.
Uses Claude CLI integration to generate optimal execution plans, identify
parallel opportunities, and predict performance bottlenecks.

Follows SOLID principles and integrates seamlessly with existing architecture.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

from supervisor_agent.core.dag_resolver import DAGResolver, ValidationResult
from supervisor_agent.core.workflow_models import (DependencyDefinition,
                                                   ExecutionPlan,
                                                   TaskDefinition,
                                                   WorkflowDefinition)
from supervisor_agent.db.models import TaskType
from supervisor_agent.intelligence.workflow_synthesizer import (
    ClaudeAgentWrapper, EnhancedWorkflowDefinition)

logger = structlog.get_logger(__name__)


@dataclass
class OptimizedExecutionPlan(ExecutionPlan):
    """AI-optimized execution plan with additional intelligence"""

    parallel_efficiency_score: float
    bottleneck_predictions: List[Dict[str, Any]]
    optimization_suggestions: List[Dict[str, Any]]
    resource_allocation_hints: Dict[str, Any]
    estimated_execution_time_minutes: int
    confidence_score: float

    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update(
            {
                "parallel_efficiency_score": self.parallel_efficiency_score,
                "bottleneck_predictions": self.bottleneck_predictions,
                "optimization_suggestions": self.optimization_suggestions,
                "resource_allocation_hints": self.resource_allocation_hints,
                "estimated_execution_time_minutes": self.estimated_execution_time_minutes,
                "confidence_score": self.confidence_score,
            }
        )
        return base_dict


@dataclass
class PerformanceMetrics:
    """Historical performance metrics for AI learning"""

    task_type: str
    average_execution_time_minutes: float
    success_rate: float
    typical_resource_usage: Dict[str, Any]
    common_failure_modes: List[str]
    parallel_scalability: float


class AIEnhancedDAGResolver(DAGResolver):
    """
    AI-enhanced DAG resolver that extends the base resolver with intelligent optimization.

    Provides AI-powered capabilities:
    - Optimal parallel execution planning
    - Bottleneck prediction and prevention
    - Resource allocation optimization
    - Performance-based task ordering
    """

    def __init__(
        self, claude_agent: ClaudeAgentWrapper = None, provider_coordinator=None
    ):
        """
        Initialize AI-enhanced DAG resolver.

        Args:
            claude_agent: Claude CLI wrapper for AI capabilities
            provider_coordinator: Provider coordinator for task execution intelligence
        """
        super().__init__()
        self.claude_agent = claude_agent
        self.provider_coordinator = provider_coordinator
        self.performance_history: Dict[str, PerformanceMetrics] = {}
        self.logger = logger.bind(component="ai_enhanced_dag_resolver")

    async def create_intelligent_execution_plan(
        self,
        workflow: EnhancedWorkflowDefinition,
        historical_data: Dict[str, Any] = None,
    ) -> OptimizedExecutionPlan:
        """
        Create an AI-optimized execution plan for a workflow.

        Uses AI to analyze task dependencies, predict performance, and optimize
        for parallel execution and resource efficiency.

        Args:
            workflow: Enhanced workflow definition with AI features
            historical_data: Optional historical performance data

        Returns:
            Optimized execution plan with AI insights
        """
        self.logger.info(
            "Creating intelligent execution plan",
            workflow_name=workflow.name,
            task_count=len(workflow.tasks),
        )

        try:
            # Create base execution plan using existing logic
            base_plan = self._create_base_execution_plan(workflow)

            # Get AI-powered optimizations
            ai_optimizations = await self._get_ai_optimizations(
                workflow, base_plan, historical_data
            )

            # Apply optimizations to create enhanced plan
            optimized_plan = await self._apply_ai_optimizations(
                base_plan, ai_optimizations
            )

            self.logger.info(
                "Intelligent execution plan created",
                parallel_groups=len(optimized_plan.execution_order),
                efficiency_score=optimized_plan.parallel_efficiency_score,
                estimated_time=optimized_plan.estimated_execution_time_minutes,
            )

            return optimized_plan

        except Exception as e:
            self.logger.error(
                "Failed to create intelligent execution plan", error=str(e)
            )
            # Fall back to base plan if AI optimization fails
            return await self._create_fallback_plan(workflow)

    async def predict_execution_bottlenecks(
        self, execution_plan: ExecutionPlan, current_state: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Predict potential bottlenecks in workflow execution using AI.

        Args:
            execution_plan: Current execution plan
            current_state: Optional current execution state

        Returns:
            List of predicted bottlenecks with mitigation suggestions
        """
        self.logger.info("Predicting execution bottlenecks")

        if not self.claude_agent:
            return self._predict_bottlenecks_heuristic(execution_plan)

        try:
            # Build analysis prompt for Claude
            analysis_prompt = self._build_bottleneck_analysis_prompt(
                execution_plan, current_state
            )

            # Get AI analysis
            result = await self.claude_agent.execute_task(
                {"type": "bottleneck_prediction", "prompt": analysis_prompt}
            )

            # Parse AI response
            bottlenecks = self._parse_bottleneck_predictions(result["result"])

            self.logger.info(
                "Bottleneck prediction completed", bottleneck_count=len(bottlenecks)
            )

            return bottlenecks

        except Exception as e:
            self.logger.error("AI bottleneck prediction failed", error=str(e))
            return self._predict_bottlenecks_heuristic(execution_plan)

    async def optimize_parallel_execution(
        self, workflow: EnhancedWorkflowDefinition
    ) -> Dict[str, Any]:
        """
        Optimize parallel execution strategy using AI analysis.

        Args:
            workflow: Workflow to optimize

        Returns:
            Parallel execution optimization recommendations
        """
        self.logger.info("Optimizing parallel execution strategy")

        if not self.claude_agent:
            return self._optimize_parallel_heuristic(workflow)

        try:
            # Build optimization prompt
            optimization_prompt = self._build_parallel_optimization_prompt(workflow)

            # Get AI recommendations
            result = await self.claude_agent.execute_task(
                {"type": "parallel_optimization", "prompt": optimization_prompt}
            )

            # Parse optimization recommendations
            optimizations = self._parse_parallel_optimizations(result["result"])

            self.logger.info(
                "Parallel execution optimization completed",
                strategies=len(optimizations),
            )

            return optimizations

        except Exception as e:
            self.logger.error("Parallel execution optimization failed", error=str(e))
            return self._optimize_parallel_heuristic(workflow)

    async def suggest_resource_allocation(
        self,
        execution_plan: OptimizedExecutionPlan,
        resource_constraints: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Suggest optimal resource allocation for workflow execution.

        Args:
            execution_plan: Optimized execution plan
            resource_constraints: Optional resource constraints

        Returns:
            Resource allocation recommendations
        """
        self.logger.info("Generating resource allocation suggestions")

        try:
            # Get historical performance data
            performance_data = await self._get_performance_data(execution_plan)

            # Use AI to generate allocation strategy
            if self.claude_agent:
                allocation_prompt = self._build_resource_allocation_prompt(
                    execution_plan, performance_data, resource_constraints
                )

                result = await self.claude_agent.execute_task(
                    {"type": "resource_allocation", "prompt": allocation_prompt}
                )

                return self._parse_resource_allocation(result["result"])
            else:
                return self._suggest_resource_allocation_heuristic(
                    execution_plan, resource_constraints
                )

        except Exception as e:
            self.logger.error("Resource allocation suggestion failed", error=str(e))
            return self._suggest_resource_allocation_heuristic(
                execution_plan, resource_constraints
            )

    def _create_base_execution_plan(
        self, workflow: EnhancedWorkflowDefinition
    ) -> ExecutionPlan:
        """Create base execution plan using existing DAG resolution logic"""

        # Convert enhanced workflow to standard format for base resolver
        standard_workflow = WorkflowDefinition(
            name=workflow.name,
            description=workflow.description,
            tasks=[task.to_dict() for task in workflow.tasks],
            dependencies=self._extract_dependencies(workflow.tasks),
            variables={},
        )

        # Use base DAG resolver logic (synchronous method)
        return super().create_execution_plan(standard_workflow)

    async def _get_ai_optimizations(
        self,
        workflow: EnhancedWorkflowDefinition,
        base_plan: ExecutionPlan,
        historical_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Get AI-powered optimization recommendations"""

        if not self.claude_agent:
            return self._get_heuristic_optimizations(workflow, base_plan)

        optimization_prompt = f"""
        Analyze this workflow execution plan and provide optimization recommendations:
        
        Workflow: {workflow.name}
        Tasks: {len(workflow.tasks)}
        Base Execution Plan: {json.dumps(base_plan.to_dict(), indent=2)}
        Historical Data: {json.dumps(historical_data or {}, indent=2)}
        
        Provide optimization recommendations in JSON format:
        {{
            "parallel_opportunities": [
                {{"group": ["task1", "task2"], "efficiency_gain": 0.4, "reasoning": "..."}}
            ],
            "bottleneck_predictions": [
                {{"task_id": "task3", "type": "resource_contention", "probability": 0.7, "impact": "high"}}
            ],
            "resource_optimization": {{
                "cpu_allocation": {{"task1": "2 cores", "task2": "1 core"}},
                "memory_allocation": {{"task1": "4GB", "task2": "2GB"}},
                "io_optimization": ["use_ssd", "enable_caching"]
            }},
            "execution_time_estimate": 45,
            "confidence_score": 0.85
        }}
        
        Focus on:
        1. Maximizing parallel execution while respecting dependencies
        2. Predicting resource bottlenecks and conflicts
        3. Optimizing task ordering for fastest completion
        4. Suggesting resource allocation strategies
        """

        try:
            result = await self.claude_agent.execute_task(
                {"type": "execution_plan_optimization", "prompt": optimization_prompt}
            )

            return json.loads(result["result"])

        except Exception as e:
            self.logger.error("AI optimization generation failed", error=str(e))
            return self._get_heuristic_optimizations(workflow, base_plan)

    async def _apply_ai_optimizations(
        self, base_plan: ExecutionPlan, optimizations: Dict[str, Any]
    ) -> OptimizedExecutionPlan:
        """Apply AI optimizations to create enhanced execution plan"""

        # Apply parallel optimization recommendations
        optimized_execution_order = await self._optimize_execution_order(
            base_plan.execution_order, optimizations.get("parallel_opportunities", [])
        )

        # Calculate efficiency metrics
        parallel_efficiency_score = self._calculate_efficiency_score(
            base_plan.execution_order, optimized_execution_order
        )

        # Extract predictions and suggestions
        bottleneck_predictions = optimizations.get("bottleneck_predictions", [])
        optimization_suggestions = optimizations.get("optimization_suggestions", [])
        resource_allocation_hints = optimizations.get("resource_optimization", {})

        return OptimizedExecutionPlan(
            execution_order=optimized_execution_order,
            task_map=base_plan.task_map,
            dependency_map=base_plan.dependency_map,
            parallel_efficiency_score=parallel_efficiency_score,
            bottleneck_predictions=bottleneck_predictions,
            optimization_suggestions=optimization_suggestions,
            resource_allocation_hints=resource_allocation_hints,
            estimated_execution_time_minutes=optimizations.get(
                "execution_time_estimate", 60
            ),
            confidence_score=optimizations.get("confidence_score", 0.8),
        )

    async def _create_fallback_plan(
        self, workflow: EnhancedWorkflowDefinition
    ) -> OptimizedExecutionPlan:
        """Create fallback plan when AI optimization fails"""

        base_plan = self._create_base_execution_plan(workflow)

        return OptimizedExecutionPlan(
            execution_order=base_plan.execution_order,
            task_map=base_plan.task_map,
            dependency_map=base_plan.dependency_map,
            parallel_efficiency_score=0.6,  # Conservative estimate
            bottleneck_predictions=[],
            optimization_suggestions=[],
            resource_allocation_hints={},
            estimated_execution_time_minutes=len(workflow.tasks)
            * 15,  # Conservative estimate
            confidence_score=0.5,
        )

    def _extract_dependencies(
        self, tasks: List[TaskDefinition]
    ) -> List[Dict[str, Any]]:
        """Extract dependency definitions from tasks"""
        dependencies = []

        for task in tasks:
            for dep_task_id in task.dependencies or []:
                dependencies.append(
                    {
                        "task_id": task.id,
                        "depends_on": dep_task_id,
                        "condition": "SUCCESS",
                        "condition_value": None,
                    }
                )

        return dependencies

    def _build_bottleneck_analysis_prompt(
        self, execution_plan: ExecutionPlan, current_state: Dict[str, Any] = None
    ) -> str:
        """Build prompt for AI bottleneck analysis"""

        return f"""
        Analyze this execution plan for potential bottlenecks:
        
        Execution Plan: {json.dumps(execution_plan.to_dict(), indent=2)}
        Current State: {json.dumps(current_state or {}, indent=2)}
        
        Identify potential bottlenecks and provide mitigation strategies:
        {{
            "bottlenecks": [
                {{
                    "type": "dependency_bottleneck|resource_contention|io_wait|compute_intensive",
                    "task_id": "affected_task_id",
                    "description": "detailed description",
                    "probability": 0.0-1.0,
                    "impact": "low|medium|high",
                    "mitigation_strategies": ["strategy1", "strategy2"],
                    "monitoring_indicators": ["metric1", "metric2"]
                }}
            ]
        }}
        """

    def _build_parallel_optimization_prompt(
        self, workflow: EnhancedWorkflowDefinition
    ) -> str:
        """Build prompt for parallel execution optimization"""

        return f"""
        Optimize parallel execution for this workflow:
        
        Workflow: {workflow.name}
        Tasks: {json.dumps([task.to_dict() for task in workflow.tasks], indent=2)}
        
        Provide parallel execution optimization:
        {{
            "parallel_groups": [
                {{
                    "group_id": "group_1",
                    "tasks": ["task1", "task2"],
                    "estimated_speedup": 1.8,
                    "resource_requirements": {{"cpu": 4, "memory": "8GB"}},
                    "dependencies_satisfied": true
                }}
            ],
            "sequential_groups": [
                {{
                    "group_id": "seq_1", 
                    "tasks": ["task3"],
                    "reason": "depends on parallel_group_1"
                }}
            ],
            "optimization_metrics": {{
                "total_speedup": 2.1,
                "resource_efficiency": 0.85,
                "complexity_increase": 0.2
            }}
        }}
        """

    def _build_resource_allocation_prompt(
        self,
        execution_plan: OptimizedExecutionPlan,
        performance_data: Dict[str, Any],
        constraints: Dict[str, Any] = None,
    ) -> str:
        """Build prompt for resource allocation optimization"""

        return f"""
        Suggest optimal resource allocation for this execution plan:
        
        Execution Plan: {json.dumps(execution_plan.to_dict(), indent=2)}
        Performance Data: {json.dumps(performance_data, indent=2)}
        Resource Constraints: {json.dumps(constraints or {}, indent=2)}
        
        Provide resource allocation strategy:
        {{
            "cpu_allocation": {{"task_id": "cores_needed"}},
            "memory_allocation": {{"task_id": "memory_mb"}},
            "io_optimization": ["strategy1", "strategy2"],
            "scaling_recommendations": {{
                "auto_scale_triggers": ["condition1", "condition2"],
                "max_parallel_tasks": 10,
                "resource_buffer_percent": 20
            }},
            "cost_optimization": {{
                "estimated_cost_usd": 25.50,
                "cost_per_hour": 12.75,
                "optimization_opportunities": ["opt1", "opt2"]
            }}
        }}
        """

    def _parse_bottleneck_predictions(self, ai_response: str) -> List[Dict[str, Any]]:
        """Parse AI bottleneck predictions from response"""
        try:
            data = json.loads(ai_response)
            return data.get("bottlenecks", [])
        except json.JSONDecodeError:
            return []

    def _parse_parallel_optimizations(self, ai_response: str) -> Dict[str, Any]:
        """Parse AI parallel optimization recommendations"""
        try:
            return json.loads(ai_response)
        except json.JSONDecodeError:
            return {"parallel_groups": [], "optimization_metrics": {}}

    def _parse_resource_allocation(self, ai_response: str) -> Dict[str, Any]:
        """Parse AI resource allocation recommendations"""
        try:
            return json.loads(ai_response)
        except json.JSONDecodeError:
            return {"cpu_allocation": {}, "memory_allocation": {}}

    async def _optimize_execution_order(
        self, base_order: List[List[str]], parallel_opportunities: List[Dict[str, Any]]
    ) -> List[List[str]]:
        """Optimize execution order based on AI recommendations"""

        # Start with base order
        optimized_order = [group.copy() for group in base_order]

        # Apply parallel optimization recommendations
        for opportunity in parallel_opportunities:
            group_tasks = opportunity.get("group", [])
            efficiency_gain = opportunity.get("efficiency_gain", 0)

            if efficiency_gain > 0.2:  # Only apply if significant gain
                # Try to merge tasks into parallel groups where possible
                self._merge_into_parallel_groups(optimized_order, group_tasks)

        return optimized_order

    def _merge_into_parallel_groups(
        self, execution_order: List[List[str]], tasks_to_merge: List[str]
    ):
        """Merge tasks into parallel execution groups"""

        # Find groups containing the tasks
        task_groups = {}
        for i, group in enumerate(execution_order):
            for task in tasks_to_merge:
                if task in group:
                    task_groups[task] = i

        # If tasks are in different sequential groups and can be parallelized
        if len(set(task_groups.values())) > 1:
            # Find the earliest group
            earliest_group_idx = min(task_groups.values())

            # Move all tasks to the earliest group
            for task in tasks_to_merge:
                current_group_idx = task_groups[task]
                if current_group_idx != earliest_group_idx:
                    # Remove from current group
                    execution_order[current_group_idx].remove(task)
                    # Add to earliest group
                    execution_order[earliest_group_idx].append(task)

            # Remove empty groups
            execution_order[:] = [group for group in execution_order if group]

    def _calculate_efficiency_score(
        self, base_order: List[List[str]], optimized_order: List[List[str]]
    ) -> float:
        """Calculate parallel efficiency improvement score"""

        base_sequential_time = len(base_order)
        optimized_sequential_time = len(optimized_order)

        if base_sequential_time == 0:
            return 1.0

        improvement = (
            base_sequential_time - optimized_sequential_time
        ) / base_sequential_time
        return min(1.0, max(0.0, improvement))

    def _predict_bottlenecks_heuristic(
        self, execution_plan: ExecutionPlan
    ) -> List[Dict[str, Any]]:
        """Heuristic bottleneck prediction when AI is unavailable"""

        bottlenecks = []

        # Check for tasks with many dependencies
        for task_id, dependencies in execution_plan.dependency_map.items():
            if len(dependencies) > 3:
                bottlenecks.append(
                    {
                        "type": "dependency_bottleneck",
                        "task_id": task_id,
                        "description": f"Task has {len(dependencies)} dependencies",
                        "probability": min(0.9, len(dependencies) * 0.2),
                        "impact": "medium",
                        "mitigation_strategies": [
                            "consider_breaking_dependencies",
                            "parallel_preparation",
                        ],
                    }
                )

        # Check for large parallel groups (resource contention)
        for i, group in enumerate(execution_plan.execution_order):
            if len(group) > 5:
                bottlenecks.append(
                    {
                        "type": "resource_contention",
                        "task_id": f"group_{i}",
                        "description": f"Large parallel group with {len(group)} tasks",
                        "probability": 0.6,
                        "impact": "medium",
                        "mitigation_strategies": [
                            "resource_scaling",
                            "batch_execution",
                        ],
                    }
                )

        return bottlenecks

    def _optimize_parallel_heuristic(
        self, workflow: EnhancedWorkflowDefinition
    ) -> Dict[str, Any]:
        """Heuristic parallel optimization when AI is unavailable"""

        # Simple heuristic: group tasks with no dependencies
        independent_tasks = []
        dependent_tasks = []

        for task in workflow.tasks:
            if not task.dependencies:
                independent_tasks.append(task.id)
            else:
                dependent_tasks.append(task.id)

        parallel_groups = []
        if independent_tasks:
            parallel_groups.append(
                {
                    "group_id": "independent_group",
                    "tasks": independent_tasks,
                    "estimated_speedup": min(
                        len(independent_tasks), 4
                    ),  # Cap at 4x speedup
                    "resource_requirements": {
                        "cpu": len(independent_tasks),
                        "memory": "2GB",
                    },
                }
            )

        return {
            "parallel_groups": parallel_groups,
            "optimization_metrics": {
                "total_speedup": len(independent_tasks) if independent_tasks else 1,
                "resource_efficiency": 0.7,
                "complexity_increase": 0.1,
            },
        }

    def _suggest_resource_allocation_heuristic(
        self, execution_plan: OptimizedExecutionPlan, constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Heuristic resource allocation when AI is unavailable"""

        cpu_allocation = {}
        memory_allocation = {}

        # Simple allocation based on task type
        for task_id, task in execution_plan.task_map.items():
            task_type = task.type

            if task_type in ["CODE_ANALYSIS", "TESTING"]:
                cpu_allocation[task_id] = 1
                memory_allocation[task_id] = 1024  # 1GB
            elif task_type in ["CODE_IMPLEMENTATION", "COMPILATION"]:
                cpu_allocation[task_id] = 2
                memory_allocation[task_id] = 2048  # 2GB
            else:
                cpu_allocation[task_id] = 1
                memory_allocation[task_id] = 512  # 512MB

        return {
            "cpu_allocation": cpu_allocation,
            "memory_allocation": memory_allocation,
            "io_optimization": ["enable_caching", "use_ssd"],
            "scaling_recommendations": {
                "max_parallel_tasks": 8,
                "resource_buffer_percent": 15,
            },
        }

    def _get_heuristic_optimizations(
        self, workflow: EnhancedWorkflowDefinition, base_plan: ExecutionPlan
    ) -> Dict[str, Any]:
        """Get heuristic optimizations when AI is unavailable"""

        return {
            "parallel_opportunities": [],
            "bottleneck_predictions": self._predict_bottlenecks_heuristic(base_plan),
            "resource_optimization": self._suggest_resource_allocation_heuristic(
                OptimizedExecutionPlan(
                    execution_order=base_plan.execution_order,
                    task_map=base_plan.task_map,
                    dependency_map=base_plan.dependency_map,
                    parallel_efficiency_score=0.5,
                    bottleneck_predictions=[],
                    optimization_suggestions=[],
                    resource_allocation_hints={},
                    estimated_execution_time_minutes=60,
                    confidence_score=0.5,
                )
            ),
            "execution_time_estimate": len(workflow.tasks) * 10,
            "confidence_score": 0.6,
        }

    async def _get_performance_data(
        self, execution_plan: OptimizedExecutionPlan
    ) -> Dict[str, Any]:
        """Get historical performance data for tasks"""

        performance_data = {}

        for task_id, task in execution_plan.task_map.items():
            task_type = task.type

            if task_type in self.performance_history:
                metrics = self.performance_history[task_type]
                performance_data[task_id] = {
                    "average_execution_time": metrics.average_execution_time_minutes,
                    "success_rate": metrics.success_rate,
                    "resource_usage": metrics.typical_resource_usage,
                    "parallel_scalability": metrics.parallel_scalability,
                }
            else:
                # Default performance estimates
                performance_data[task_id] = {
                    "average_execution_time": 10,
                    "success_rate": 0.9,
                    "resource_usage": {"cpu": 1, "memory_mb": 1024},
                    "parallel_scalability": 0.8,
                }

        return performance_data


# Factory function for dependency injection
async def create_ai_enhanced_dag_resolver(
    claude_agent: ClaudeAgentWrapper = None, provider_coordinator=None
) -> AIEnhancedDAGResolver:
    """
    Factory function to create AI-enhanced DAG resolver.

    Args:
        claude_agent: Optional Claude CLI wrapper for AI capabilities
        provider_coordinator: Optional provider coordinator for task intelligence

    Returns:
        Configured AIEnhancedDAGResolver instance
    """
    return AIEnhancedDAGResolver(claude_agent, provider_coordinator)

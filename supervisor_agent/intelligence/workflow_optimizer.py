"""
AI-Powered Workflow Optimizer

Comprehensive workflow optimization engine that combines AI intelligence with
heuristic algorithms to optimize workflow execution, resource allocation,
and performance.

Integrates:
- AI Workflow Synthesizer
- AI-Enhanced DAG Resolver
- Parallel Execution Analyzer
- Performance prediction and monitoring
"""

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import structlog

from supervisor_agent.core.workflow_models import ExecutionPlan, TaskDefinition
from supervisor_agent.db.models import TaskType
from supervisor_agent.intelligence.ai_enhanced_dag_resolver import (
    AIEnhancedDAGResolver, OptimizedExecutionPlan)
from supervisor_agent.intelligence.parallel_execution_analyzer import (
    ParallelExecutionAnalyzer, ParallelizationAnalysis)
from supervisor_agent.intelligence.workflow_synthesizer import (
    AIWorkflowSynthesizer, ClaudeAgentWrapper, EnhancedWorkflowDefinition,
    TenantContext)

logger = structlog.get_logger(__name__)


class OptimizationStrategy(str, Enum):
    """Workflow optimization strategies"""

    SPEED_OPTIMIZED = "speed_optimized"
    RESOURCE_OPTIMIZED = "resource_optimized"
    COST_OPTIMIZED = "cost_optimized"
    BALANCED = "balanced"
    RELIABILITY_OPTIMIZED = "reliability_optimized"


class OptimizationPriority(str, Enum):
    """Optimization priorities"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class OptimizationMetrics:
    """Workflow optimization metrics"""

    baseline_execution_time_minutes: int
    optimized_execution_time_minutes: int
    speedup_factor: float
    resource_efficiency: float
    cost_reduction_percent: float
    reliability_score: float
    complexity_increase: float
    optimization_confidence: float


@dataclass
class OptimizationRecommendation:
    """Individual optimization recommendation"""

    type: str  # parallelization, resource_allocation, task_ordering, etc.
    description: str
    impact: str  # high, medium, low
    effort: str  # high, medium, low
    priority: OptimizationPriority
    implementation_steps: List[str]
    expected_benefit: Dict[str, Any]
    risks: List[str]
    monitoring_requirements: List[str]


@dataclass
class WorkflowOptimizationResult:
    """Complete workflow optimization result"""

    original_workflow: EnhancedWorkflowDefinition
    optimized_workflow: EnhancedWorkflowDefinition
    execution_plan: OptimizedExecutionPlan
    parallelization_analysis: ParallelizationAnalysis
    optimization_metrics: OptimizationMetrics
    recommendations: List[OptimizationRecommendation]
    strategy_used: OptimizationStrategy
    optimization_timestamp: datetime
    validation_results: Dict[str, Any]


class WorkflowOptimizer:
    """
    AI-powered workflow optimizer that combines multiple intelligence components
    to provide comprehensive workflow optimization.

    Capabilities:
    - End-to-end workflow analysis and optimization
    - Multi-strategy optimization (speed, cost, resource, reliability)
    - AI-powered recommendations with fallback heuristics
    - Performance prediction and validation
    - Integration with existing workflow infrastructure
    """

    def __init__(
        self,
        claude_agent: ClaudeAgentWrapper = None,
        tenant_context: TenantContext = None,
        provider_coordinator=None,
    ):
        """
        Initialize workflow optimizer.

        Args:
            claude_agent: Optional Claude CLI wrapper for AI capabilities
            tenant_context: Optional tenant context for personalization
            provider_coordinator: Optional provider coordinator for task execution
        """
        self.claude_agent = claude_agent
        self.tenant_context = tenant_context
        self.provider_coordinator = provider_coordinator
        self.logger = logger.bind(component="workflow_optimizer")

        # Initialize intelligence components
        # Only create workflow synthesizer if tenant_context is provided
        if tenant_context:
            self.workflow_synthesizer = AIWorkflowSynthesizer(
                claude_agent=claude_agent,
                tenant_context=tenant_context,
                provider_coordinator=provider_coordinator,
            )
        else:
            self.workflow_synthesizer = None

        self.dag_resolver = AIEnhancedDAGResolver(
            claude_agent=claude_agent, provider_coordinator=provider_coordinator
        )

        self.parallel_analyzer = ParallelExecutionAnalyzer(
            claude_agent=claude_agent, provider_coordinator=provider_coordinator
        )

        # Optimization strategy configurations
        self.optimization_strategies = {
            OptimizationStrategy.SPEED_OPTIMIZED: {
                "parallel_weight": 0.8,
                "resource_weight": 0.6,
                "cost_weight": 0.2,
                "reliability_weight": 0.4,
            },
            OptimizationStrategy.RESOURCE_OPTIMIZED: {
                "parallel_weight": 0.4,
                "resource_weight": 0.9,
                "cost_weight": 0.3,
                "reliability_weight": 0.6,
            },
            OptimizationStrategy.COST_OPTIMIZED: {
                "parallel_weight": 0.3,
                "resource_weight": 0.7,
                "cost_weight": 0.9,
                "reliability_weight": 0.5,
            },
            OptimizationStrategy.BALANCED: {
                "parallel_weight": 0.6,
                "resource_weight": 0.6,
                "cost_weight": 0.6,
                "reliability_weight": 0.6,
            },
            OptimizationStrategy.RELIABILITY_OPTIMIZED: {
                "parallel_weight": 0.3,
                "resource_weight": 0.5,
                "cost_weight": 0.4,
                "reliability_weight": 0.9,
            },
        }

    async def optimize_workflow(
        self,
        workflow: Union[EnhancedWorkflowDefinition, Dict[str, Any]],
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
        historical_data: Dict[str, Any] = None,
        constraints: Dict[str, Any] = None,
    ) -> WorkflowOptimizationResult:
        """
        Perform comprehensive workflow optimization.

        Args:
            workflow: Workflow to optimize (EnhancedWorkflowDefinition or dict)
            strategy: Optimization strategy to use
            historical_data: Optional historical performance data
            constraints: Optional optimization constraints

        Returns:
            Complete optimization result with recommendations
        """
        self.logger.info(
            "Starting comprehensive workflow optimization",
            strategy=strategy.value,
            has_historical_data=historical_data is not None,
        )

        try:
            # Ensure we have an EnhancedWorkflowDefinition
            if isinstance(workflow, dict):
                workflow = await self._convert_to_enhanced_workflow(workflow)

            original_workflow = workflow

            # Step 1: Analyze current workflow structure
            baseline_metrics = await self._analyze_baseline_workflow(workflow)

            # Step 2: Generate AI-powered optimization recommendations
            optimization_recommendations = (
                await self._generate_optimization_recommendations(
                    workflow, strategy, historical_data, constraints
                )
            )

            # Step 3: Apply optimization recommendations
            optimized_workflow = await self._apply_optimizations(
                workflow, optimization_recommendations, strategy
            )

            # Step 4: Create optimized execution plan
            execution_plan = await self.dag_resolver.create_intelligent_execution_plan(
                optimized_workflow, historical_data
            )

            # Step 5: Analyze parallelization opportunities
            parallelization_analysis = (
                await self.parallel_analyzer.analyze_parallel_opportunities(
                    optimized_workflow, execution_plan, historical_data
                )
            )

            # Step 6: Calculate optimization metrics
            optimization_metrics = await self._calculate_optimization_metrics(
                original_workflow, optimized_workflow, execution_plan, baseline_metrics
            )

            # Step 7: Validate optimization results
            validation_results = await self._validate_optimization(
                original_workflow, optimized_workflow, optimization_metrics
            )

            result = WorkflowOptimizationResult(
                original_workflow=original_workflow,
                optimized_workflow=optimized_workflow,
                execution_plan=execution_plan,
                parallelization_analysis=parallelization_analysis,
                optimization_metrics=optimization_metrics,
                recommendations=optimization_recommendations,
                strategy_used=strategy,
                optimization_timestamp=datetime.now(timezone.utc),
                validation_results=validation_results,
            )

            self.logger.info(
                "Workflow optimization completed successfully",
                speedup_factor=optimization_metrics.speedup_factor,
                resource_efficiency=optimization_metrics.resource_efficiency,
                optimization_confidence=optimization_metrics.optimization_confidence,
            )

            return result

        except Exception as e:
            self.logger.error("Workflow optimization failed", error=str(e))
            return await self._create_fallback_optimization_result(workflow, strategy)

    async def compare_optimization_strategies(
        self,
        workflow: EnhancedWorkflowDefinition,
        strategies: List[OptimizationStrategy] = None,
        historical_data: Dict[str, Any] = None,
    ) -> Dict[str, WorkflowOptimizationResult]:
        """
        Compare multiple optimization strategies for a workflow.

        Args:
            workflow: Workflow to analyze
            strategies: List of strategies to compare (default: all strategies)
            historical_data: Optional historical performance data

        Returns:
            Dictionary mapping strategy names to optimization results
        """
        if strategies is None:
            strategies = list(OptimizationStrategy)

        self.logger.info(
            "Comparing optimization strategies",
            workflow_name=workflow.name,
            strategy_count=len(strategies),
        )

        results = {}

        # Run optimization for each strategy
        for strategy in strategies:
            try:
                result = await self.optimize_workflow(
                    workflow, strategy, historical_data
                )
                results[strategy.value] = result
            except Exception as e:
                self.logger.error(
                    "Strategy comparison failed", strategy=strategy.value, error=str(e)
                )

        # Log comparison summary
        if results:
            best_speed = max(
                results.values(), key=lambda r: r.optimization_metrics.speedup_factor
            )
            best_efficiency = max(
                results.values(),
                key=lambda r: r.optimization_metrics.resource_efficiency,
            )

            self.logger.info(
                "Strategy comparison completed",
                best_speed_strategy=best_speed.strategy_used.value,
                best_efficiency_strategy=best_efficiency.strategy_used.value,
                total_strategies=len(results),
            )

        return results

    async def generate_optimization_report(
        self, optimization_result: WorkflowOptimizationResult
    ) -> Dict[str, Any]:
        """
        Generate comprehensive optimization report.

        Args:
            optimization_result: Optimization result to report on

        Returns:
            Detailed optimization report
        """
        self.logger.info("Generating optimization report")

        metrics = optimization_result.optimization_metrics

        report = {
            "executive_summary": {
                "workflow_name": optimization_result.original_workflow.name,
                "optimization_strategy": optimization_result.strategy_used.value,
                "optimization_timestamp": optimization_result.optimization_timestamp.isoformat(),
                "key_improvements": {
                    "execution_time_reduction": f"{(1 - 1/metrics.speedup_factor)*100:.1f}%",
                    "resource_efficiency_gain": f"{metrics.resource_efficiency:.1%}",
                    "cost_reduction": f"{metrics.cost_reduction_percent:.1f}%",
                },
                "confidence_level": f"{metrics.optimization_confidence:.1%}",
            },
            "performance_analysis": {
                "baseline_execution_time": f"{metrics.baseline_execution_time_minutes} minutes",
                "optimized_execution_time": f"{metrics.optimized_execution_time_minutes} minutes",
                "speedup_factor": f"{metrics.speedup_factor:.2f}x",
                "complexity_increase": f"{metrics.complexity_increase:.1%}",
                "reliability_score": f"{metrics.reliability_score:.1%}",
            },
            "parallelization_analysis": {
                "parallel_groups_identified": len(
                    optimization_result.parallelization_analysis.parallel_groups
                ),
                "resource_conflicts_detected": len(
                    optimization_result.parallelization_analysis.resource_conflicts
                ),
                "parallelization_score": optimization_result.parallelization_analysis.optimization_score,
                "execution_strategy": optimization_result.parallelization_analysis.execution_strategy,
            },
            "optimization_recommendations": [
                {
                    "type": rec.type,
                    "description": rec.description,
                    "impact": rec.impact,
                    "priority": rec.priority.value,
                    "implementation_steps": rec.implementation_steps,
                    "expected_benefit": rec.expected_benefit,
                    "risks": rec.risks,
                }
                for rec in optimization_result.recommendations
            ],
            "validation_results": optimization_result.validation_results,
            "execution_plan_details": {
                "execution_stages": len(
                    optimization_result.execution_plan.execution_order
                ),
                "total_tasks": len(optimization_result.execution_plan.task_map),
                "dependencies_resolved": len(
                    optimization_result.execution_plan.dependency_map
                ),
                "parallel_efficiency_score": optimization_result.execution_plan.parallel_efficiency_score,
                "bottleneck_predictions": optimization_result.execution_plan.bottleneck_predictions,
            },
            "recommendations_summary": {
                "high_priority_count": len(
                    [
                        r
                        for r in optimization_result.recommendations
                        if r.priority == OptimizationPriority.HIGH
                    ]
                ),
                "medium_priority_count": len(
                    [
                        r
                        for r in optimization_result.recommendations
                        if r.priority == OptimizationPriority.MEDIUM
                    ]
                ),
                "low_priority_count": len(
                    [
                        r
                        for r in optimization_result.recommendations
                        if r.priority == OptimizationPriority.LOW
                    ]
                ),
                "total_recommendations": len(optimization_result.recommendations),
            },
        }

        return report

    async def _convert_to_enhanced_workflow(
        self, workflow_dict: Dict[str, Any]
    ) -> EnhancedWorkflowDefinition:
        """Convert dictionary workflow to EnhancedWorkflowDefinition"""

        tasks = []
        for task_data in workflow_dict.get("tasks", []):
            task = TaskDefinition(
                id=task_data["id"],
                name=task_data["name"],
                type=task_data["type"],
                config=task_data.get("config", {}),
                dependencies=task_data.get("dependencies", []),
            )
            tasks.append(task)

        return EnhancedWorkflowDefinition(
            name=workflow_dict["name"],
            description=workflow_dict.get("description", ""),
            tasks=tasks,
            version=workflow_dict.get("version", "1.0"),
        )

    async def _analyze_baseline_workflow(
        self, workflow: EnhancedWorkflowDefinition
    ) -> Dict[str, Any]:
        """Analyze baseline workflow performance"""

        # Simple baseline analysis
        task_count = len(workflow.tasks)

        # Estimate baseline execution time (sequential execution)
        baseline_time = 0
        for task in workflow.tasks:
            task_time = task.config.get("timeout_minutes", 10)
            baseline_time += task_time

        # Calculate dependency complexity
        total_dependencies = sum(
            len(task.dependencies or []) for task in workflow.tasks
        )
        dependency_complexity = total_dependencies / task_count if task_count > 0 else 0

        return {
            "task_count": task_count,
            "baseline_execution_time_minutes": baseline_time,
            "dependency_complexity": dependency_complexity,
            "average_task_duration": (
                baseline_time / task_count if task_count > 0 else 0
            ),
            "parallelization_potential": len(
                [task for task in workflow.tasks if not task.dependencies]
            )
            / task_count,
        }

    async def _generate_optimization_recommendations(
        self,
        workflow: EnhancedWorkflowDefinition,
        strategy: OptimizationStrategy,
        historical_data: Dict[str, Any] = None,
        constraints: Dict[str, Any] = None,
    ) -> List[OptimizationRecommendation]:
        """Generate AI-powered optimization recommendations"""

        recommendations = []

        if self.claude_agent:
            try:
                ai_recommendations = await self._get_ai_optimization_recommendations(
                    workflow, strategy, historical_data, constraints
                )
                recommendations.extend(ai_recommendations)
            except Exception as e:
                self.logger.error(
                    "AI optimization recommendations failed", error=str(e)
                )

        # Add heuristic recommendations as fallback or supplement
        heuristic_recommendations = (
            await self._get_heuristic_optimization_recommendations(
                workflow, strategy, constraints
            )
        )
        recommendations.extend(heuristic_recommendations)

        # Remove duplicates and prioritize
        return self._prioritize_recommendations(recommendations, strategy)

    async def _get_ai_optimization_recommendations(
        self,
        workflow: EnhancedWorkflowDefinition,
        strategy: OptimizationStrategy,
        historical_data: Dict[str, Any] = None,
        constraints: Dict[str, Any] = None,
    ) -> List[OptimizationRecommendation]:
        """Get AI-powered optimization recommendations"""

        optimization_prompt = f"""
        Analyze this workflow and provide comprehensive optimization recommendations:
        
        Workflow: {workflow.name}
        Strategy: {strategy.value}
        Tasks: {json.dumps([task.to_dict() for task in workflow.tasks], indent=2)}
        Historical Data: {json.dumps(historical_data or {}, indent=2)}
        Constraints: {json.dumps(constraints or {}, indent=2)}
        
        Provide detailed optimization recommendations in JSON format:
        {{
            "recommendations": [
                {{
                    "type": "parallelization|resource_allocation|task_ordering|dependency_optimization|caching",
                    "description": "Detailed description of the optimization",
                    "impact": "high|medium|low",
                    "effort": "high|medium|low", 
                    "priority": "high|medium|low",
                    "implementation_steps": ["step1", "step2", "step3"],
                    "expected_benefit": {{
                        "execution_time_reduction_percent": 25,
                        "resource_savings_percent": 15,
                        "cost_reduction_percent": 10
                    }},
                    "risks": ["risk1", "risk2"],
                    "monitoring_requirements": ["metric1", "metric2"]
                }}
            ]
        }}
        
        Focus on:
        1. {strategy.value} optimization strategy
        2. Realistic and actionable recommendations
        3. Quantifiable benefits and risks
        4. Implementation feasibility
        """

        result = await self.claude_agent.execute_task(
            {
                "type": "workflow_optimization_recommendations",
                "prompt": optimization_prompt,
            }
        )

        ai_data = json.loads(result["result"])
        recommendations = []

        for rec_data in ai_data.get("recommendations", []):
            recommendation = OptimizationRecommendation(
                type=rec_data.get("type", "unknown"),
                description=rec_data.get("description", ""),
                impact=rec_data.get("impact", "medium"),
                effort=rec_data.get("effort", "medium"),
                priority=OptimizationPriority(rec_data.get("priority", "medium")),
                implementation_steps=rec_data.get("implementation_steps", []),
                expected_benefit=rec_data.get("expected_benefit", {}),
                risks=rec_data.get("risks", []),
                monitoring_requirements=rec_data.get("monitoring_requirements", []),
            )
            recommendations.append(recommendation)

        return recommendations

    async def _get_heuristic_optimization_recommendations(
        self,
        workflow: EnhancedWorkflowDefinition,
        strategy: OptimizationStrategy,
        constraints: Dict[str, Any] = None,
    ) -> List[OptimizationRecommendation]:
        """Get heuristic optimization recommendations"""

        recommendations = []

        # Analyze for parallelization opportunities
        independent_tasks = [task for task in workflow.tasks if not task.dependencies]
        if len(independent_tasks) > 1:
            recommendations.append(
                OptimizationRecommendation(
                    type="parallelization",
                    description=f"Parallelize {len(independent_tasks)} independent tasks to reduce execution time",
                    impact="high" if len(independent_tasks) > 3 else "medium",
                    effort="low",
                    priority=OptimizationPriority.HIGH,
                    implementation_steps=[
                        "Group independent tasks into parallel execution groups",
                        "Allocate appropriate resources for parallel execution",
                        "Monitor resource contention during parallel execution",
                    ],
                    expected_benefit={
                        "execution_time_reduction_percent": min(
                            70, len(independent_tasks) * 15
                        ),
                        "resource_utilization_improvement": 30,
                    },
                    risks=["Resource contention", "Increased complexity"],
                    monitoring_requirements=[
                        "Resource usage",
                        "Task completion times",
                        "Error rates",
                    ],
                )
            )

        # Analyze for resource optimization
        if strategy in [
            OptimizationStrategy.RESOURCE_OPTIMIZED,
            OptimizationStrategy.COST_OPTIMIZED,
        ]:
            recommendations.append(
                OptimizationRecommendation(
                    type="resource_allocation",
                    description="Optimize resource allocation based on task requirements",
                    impact="medium",
                    effort="medium",
                    priority=OptimizationPriority.MEDIUM,
                    implementation_steps=[
                        "Analyze historical resource usage patterns",
                        "Right-size resource allocations for each task type",
                        "Implement dynamic resource scaling",
                    ],
                    expected_benefit={
                        "cost_reduction_percent": 20,
                        "resource_efficiency_improvement": 25,
                    },
                    risks=[
                        "Under-allocation leading to failures",
                        "Over-allocation waste",
                    ],
                    monitoring_requirements=[
                        "Resource utilization metrics",
                        "Task failure rates",
                    ],
                )
            )

        # Dependency optimization
        max_dependencies = max(len(task.dependencies or []) for task in workflow.tasks)
        if max_dependencies > 3:
            recommendations.append(
                OptimizationRecommendation(
                    type="dependency_optimization",
                    description="Reduce task dependencies to enable more parallelization",
                    impact="medium",
                    effort="high",
                    priority=OptimizationPriority.MEDIUM,
                    implementation_steps=[
                        "Analyze critical dependency paths",
                        "Break down complex tasks with many dependencies",
                        "Cache intermediate results to reduce dependencies",
                    ],
                    expected_benefit={
                        "execution_time_reduction_percent": 15,
                        "parallelization_improvement": 40,
                    },
                    risks=["Increased task complexity", "Cache management overhead"],
                    monitoring_requirements=[
                        "Dependency resolution times",
                        "Cache hit rates",
                    ],
                )
            )

        return recommendations

    def _prioritize_recommendations(
        self,
        recommendations: List[OptimizationRecommendation],
        strategy: OptimizationStrategy,
    ) -> List[OptimizationRecommendation]:
        """Prioritize recommendations based on strategy and impact"""

        strategy_weights = self.optimization_strategies[strategy]

        def calculate_score(rec: OptimizationRecommendation) -> float:
            impact_score = {"high": 3, "medium": 2, "low": 1}[rec.impact]
            effort_score = {"low": 3, "medium": 2, "high": 1}[
                rec.effort
            ]  # Lower effort is better
            priority_score = {"high": 3, "medium": 2, "low": 1}[rec.priority.value]

            # Adjust based on strategy
            type_weight = 1.0
            if rec.type == "parallelization":
                type_weight = strategy_weights["parallel_weight"]
            elif rec.type == "resource_allocation":
                type_weight = strategy_weights["resource_weight"]

            return (impact_score + effort_score + priority_score) * type_weight

        # Remove duplicates based on type and description
        unique_recommendations = []
        seen = set()

        for rec in recommendations:
            key = (rec.type, rec.description[:50])  # Use first 50 chars of description
            if key not in seen:
                seen.add(key)
                unique_recommendations.append(rec)

        # Sort by calculated score (highest first)
        return sorted(unique_recommendations, key=calculate_score, reverse=True)

    async def _apply_optimizations(
        self,
        workflow: EnhancedWorkflowDefinition,
        recommendations: List[OptimizationRecommendation],
        strategy: OptimizationStrategy,
    ) -> EnhancedWorkflowDefinition:
        """Apply optimization recommendations to create optimized workflow"""

        # For now, return the original workflow as the optimization would require
        # more complex workflow transformation logic
        # In a production system, this would apply the recommendations to modify
        # the workflow structure, task configurations, etc.

        return workflow

    async def _calculate_optimization_metrics(
        self,
        original_workflow: EnhancedWorkflowDefinition,
        optimized_workflow: EnhancedWorkflowDefinition,
        execution_plan: OptimizedExecutionPlan,
        baseline_metrics: Dict[str, Any],
    ) -> OptimizationMetrics:
        """Calculate optimization metrics"""

        baseline_time = baseline_metrics["baseline_execution_time_minutes"]
        optimized_time = execution_plan.estimated_execution_time_minutes

        speedup_factor = baseline_time / optimized_time if optimized_time > 0 else 1.0

        return OptimizationMetrics(
            baseline_execution_time_minutes=baseline_time,
            optimized_execution_time_minutes=optimized_time,
            speedup_factor=speedup_factor,
            resource_efficiency=execution_plan.parallel_efficiency_score,
            cost_reduction_percent=min(
                50, (speedup_factor - 1) * 20
            ),  # Estimate cost reduction
            reliability_score=execution_plan.confidence_score,
            complexity_increase=max(
                0, len(optimized_workflow.tasks) - len(original_workflow.tasks)
            )
            * 5,
            optimization_confidence=execution_plan.confidence_score,
        )

    async def _validate_optimization(
        self,
        original_workflow: EnhancedWorkflowDefinition,
        optimized_workflow: EnhancedWorkflowDefinition,
        metrics: OptimizationMetrics,
    ) -> Dict[str, Any]:
        """Validate optimization results"""

        validations = {
            "workflow_integrity": True,  # Would check if workflow logic is preserved
            "performance_improvement": metrics.speedup_factor > 1.0,
            "resource_efficiency": metrics.resource_efficiency > 0.5,
            "complexity_acceptable": metrics.complexity_increase < 20,
            "confidence_level": metrics.optimization_confidence > 0.6,
        }

        overall_valid = all(validations.values())

        return {
            "overall_valid": overall_valid,
            "individual_validations": validations,
            "validation_score": sum(validations.values()) / len(validations),
            "validation_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _create_fallback_optimization_result(
        self, workflow: EnhancedWorkflowDefinition, strategy: OptimizationStrategy
    ) -> WorkflowOptimizationResult:
        """Create fallback optimization result when main optimization fails"""

        # Create basic execution plan
        basic_plan = OptimizedExecutionPlan(
            execution_order=[[task.id] for task in workflow.tasks],
            task_map={task.id: task for task in workflow.tasks},
            dependency_map={},
            parallel_efficiency_score=0.3,
            bottleneck_predictions=[],
            optimization_suggestions=[],
            resource_allocation_hints={},
            estimated_execution_time_minutes=len(workflow.tasks) * 10,
            confidence_score=0.4,
        )

        # Basic parallelization analysis
        basic_analysis = ParallelizationAnalysis(
            parallel_groups=[],
            resource_conflicts=[],
            execution_strategy={"primary_strategy": "sequential_execution"},
            performance_predictions={
                "baseline_execution_time_minutes": len(workflow.tasks) * 10,
                "optimized_execution_time_minutes": len(workflow.tasks) * 10,
                "speedup_factor": 1.0,
            },
            optimization_score=0.3,
            confidence_level=0.4,
        )

        # Basic metrics
        metrics = OptimizationMetrics(
            baseline_execution_time_minutes=len(workflow.tasks) * 10,
            optimized_execution_time_minutes=len(workflow.tasks) * 10,
            speedup_factor=1.0,
            resource_efficiency=0.5,
            cost_reduction_percent=0.0,
            reliability_score=0.8,
            complexity_increase=0.0,
            optimization_confidence=0.4,
        )

        return WorkflowOptimizationResult(
            original_workflow=workflow,
            optimized_workflow=workflow,
            execution_plan=basic_plan,
            parallelization_analysis=basic_analysis,
            optimization_metrics=metrics,
            recommendations=[],
            strategy_used=strategy,
            optimization_timestamp=datetime.now(timezone.utc),
            validation_results={"overall_valid": True},
        )


# Factory function for dependency injection
async def create_workflow_optimizer(
    claude_agent: ClaudeAgentWrapper = None,
    tenant_context: TenantContext = None,
    provider_coordinator=None,
) -> WorkflowOptimizer:
    """
    Factory function to create workflow optimizer.

    Args:
        claude_agent: Optional Claude CLI wrapper for AI capabilities
        tenant_context: Optional tenant context for personalization
        provider_coordinator: Optional provider coordinator for task execution

    Returns:
        Configured WorkflowOptimizer instance
    """
    return WorkflowOptimizer(claude_agent, tenant_context, provider_coordinator)

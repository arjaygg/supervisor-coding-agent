"""
Parallel Execution Analyzer

Intelligent analysis of workflow tasks to identify optimal parallelization
opportunities, resource conflicts, and execution strategies.

Implements advanced algorithms for:
- Dependency graph analysis
- Resource contention detection
- Parallel group optimization
- Performance prediction
"""

import asyncio
import json
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict, deque

import structlog

from supervisor_agent.intelligence.workflow_synthesizer import (
    ClaudeAgentWrapper, EnhancedWorkflowDefinition
)
from supervisor_agent.db.workflow_models import TaskDefinition, ExecutionPlan
from supervisor_agent.db.models import TaskType


logger = structlog.get_logger(__name__)


@dataclass
class ParallelGroup:
    """A group of tasks that can execute in parallel"""
    group_id: str
    tasks: List[str]
    estimated_speedup: float
    resource_requirements: Dict[str, Any]
    dependencies_satisfied: bool
    conflict_risk: float
    priority_score: float


@dataclass 
class ResourceConflict:
    """Detected resource conflict between tasks"""
    conflict_type: str  # cpu, memory, io, network, database
    conflicting_tasks: List[str]
    severity: str  # low, medium, high, critical
    estimated_impact: float
    mitigation_strategies: List[str]


@dataclass
class ParallelizationAnalysis:
    """Complete parallelization analysis results"""
    parallel_groups: List[ParallelGroup]
    resource_conflicts: List[ResourceConflict]
    execution_strategy: Dict[str, Any]
    performance_predictions: Dict[str, Any]
    optimization_score: float
    confidence_level: float


class ParallelExecutionAnalyzer:
    """
    Analyzes workflows for optimal parallel execution strategies.
    
    Uses both AI-powered analysis and heuristic algorithms to:
    - Identify tasks that can safely run in parallel
    - Detect resource conflicts and bottlenecks
    - Optimize task grouping for maximum efficiency
    - Predict performance improvements
    """
    
    def __init__(self, claude_agent: ClaudeAgentWrapper = None, provider_coordinator=None):
        """
        Initialize parallel execution analyzer.
        
        Args:
            claude_agent: Optional Claude CLI wrapper for AI analysis
            provider_coordinator: Optional provider coordinator for resource intelligence
        """
        self.claude_agent = claude_agent
        self.provider_coordinator = provider_coordinator
        self.logger = logger.bind(component="parallel_execution_analyzer")
        
        # Resource type mappings for conflict detection
        self.resource_intensive_tasks = {
            TaskType.CODE_ANALYSIS: {"cpu": "medium", "memory": "low", "io": "low"},
            TaskType.CODE_IMPLEMENTATION: {"cpu": "high", "memory": "medium", "io": "medium"},
            TaskType.TESTING: {"cpu": "medium", "memory": "medium", "io": "high"},
            TaskType.FEATURE: {"cpu": "high", "memory": "medium", "io": "medium"},
            TaskType.REFACTOR: {"cpu": "high", "memory": "high", "io": "medium"},
            TaskType.BUG_FIX: {"cpu": "medium", "memory": "medium", "io": "low"},
            TaskType.PR_REVIEW: {"cpu": "low", "memory": "low", "io": "low"},
            TaskType.ISSUE_SUMMARY: {"cpu": "low", "memory": "low", "io": "low"},
            TaskType.DESIGN_TASK: {"cpu": "low", "memory": "low", "io": "low"},
            TaskType.SETUP: {"cpu": "medium", "memory": "low", "io": "high"},
            TaskType.WORKFLOW_SYNTHESIS: {"cpu": "medium", "memory": "medium", "io": "low"},
            TaskType.REQUIREMENT_ANALYSIS: {"cpu": "low", "memory": "low", "io": "low"},
            TaskType.WORKFLOW_ADAPTATION: {"cpu": "medium", "memory": "medium", "io": "low"},
            TaskType.HUMAN_LOOP_ANALYSIS: {"cpu": "low", "memory": "low", "io": "low"},
        }
    
    async def analyze_parallel_opportunities(self, 
                                           workflow: EnhancedWorkflowDefinition,
                                           execution_plan: ExecutionPlan = None,
                                           historical_data: Dict[str, Any] = None) -> ParallelizationAnalysis:
        """
        Analyze workflow for parallel execution opportunities.
        
        Args:
            workflow: Workflow to analyze
            execution_plan: Optional existing execution plan
            historical_data: Optional historical performance data
            
        Returns:
            Complete parallelization analysis with recommendations
        """
        self.logger.info("Starting parallel execution analysis",
                        workflow_name=workflow.name,
                        task_count=len(workflow.tasks))
        
        try:
            # Build dependency graph
            dependency_graph = self._build_dependency_graph(workflow.tasks)
            
            # Identify independent task groups
            independent_groups = self._identify_independent_groups(workflow.tasks, dependency_graph)
            
            # Analyze resource conflicts
            resource_conflicts = await self._analyze_resource_conflicts(workflow.tasks, independent_groups)
            
            # Use AI for advanced analysis if available
            if self.claude_agent:
                ai_analysis = await self._get_ai_parallelization_analysis(
                    workflow, dependency_graph, resource_conflicts, historical_data
                )
            else:
                ai_analysis = self._get_heuristic_parallelization_analysis(
                    workflow, dependency_graph, resource_conflicts
                )
            
            # Create optimized parallel groups
            parallel_groups = await self._create_optimized_parallel_groups(
                independent_groups, resource_conflicts, ai_analysis
            )
            
            # Generate execution strategy
            execution_strategy = await self._generate_execution_strategy(
                parallel_groups, resource_conflicts, workflow
            )
            
            # Predict performance improvements
            performance_predictions = await self._predict_performance_improvements(
                workflow, parallel_groups, historical_data
            )
            
            # Calculate optimization score
            optimization_score = self._calculate_optimization_score(
                parallel_groups, resource_conflicts, performance_predictions
            )
            
            analysis = ParallelizationAnalysis(
                parallel_groups=parallel_groups,
                resource_conflicts=resource_conflicts,
                execution_strategy=execution_strategy,
                performance_predictions=performance_predictions,
                optimization_score=optimization_score,
                confidence_level=ai_analysis.get("confidence", 0.7)
            )
            
            self.logger.info("Parallel execution analysis completed",
                           parallel_groups=len(parallel_groups),
                           resource_conflicts=len(resource_conflicts),
                           optimization_score=optimization_score)
            
            return analysis
            
        except Exception as e:
            self.logger.error("Parallel execution analysis failed", error=str(e))
            return await self._create_fallback_analysis(workflow)
    
    async def identify_bottlenecks(self, 
                                 analysis: ParallelizationAnalysis,
                                 current_execution_state: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Identify execution bottlenecks from parallelization analysis.
        
        Args:
            analysis: Parallelization analysis results
            current_execution_state: Optional current execution state
            
        Returns:
            List of identified bottlenecks with mitigation strategies
        """
        self.logger.info("Identifying execution bottlenecks")
        
        bottlenecks = []
        
        # Check for critical resource conflicts
        for conflict in analysis.resource_conflicts:
            if conflict.severity in ["high", "critical"]:
                bottlenecks.append({
                    "type": "resource_conflict",
                    "description": f"{conflict.conflict_type.upper()} contention between tasks",
                    "affected_tasks": conflict.conflicting_tasks,
                    "severity": conflict.severity,
                    "probability": conflict.estimated_impact,
                    "mitigation_strategies": conflict.mitigation_strategies,
                    "monitoring_indicators": [
                        f"{conflict.conflict_type}_usage_high",
                        "task_queue_delays",
                        "execution_time_variance"
                    ]
                })
        
        # Check for dependency bottlenecks
        dependency_bottlenecks = self._identify_dependency_bottlenecks(analysis.parallel_groups)
        bottlenecks.extend(dependency_bottlenecks)
        
        # Check for scalability bottlenecks
        scalability_bottlenecks = self._identify_scalability_bottlenecks(analysis)
        bottlenecks.extend(scalability_bottlenecks)
        
        self.logger.info("Bottleneck identification completed", bottleneck_count=len(bottlenecks))
        return bottlenecks
    
    async def optimize_resource_allocation(self,
                                         analysis: ParallelizationAnalysis,
                                         resource_constraints: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Optimize resource allocation based on parallelization analysis.
        
        Args:
            analysis: Parallelization analysis results
            resource_constraints: Optional resource constraints
            
        Returns:
            Optimized resource allocation strategy
        """
        self.logger.info("Optimizing resource allocation")
        
        resource_allocation = {
            "cpu_allocation": {},
            "memory_allocation": {},
            "io_optimization": [],
            "scheduling_strategy": {},
            "scaling_recommendations": {}
        }
        
        # Allocate resources based on parallel groups
        for group in analysis.parallel_groups:
            group_resources = group.resource_requirements
            
            for task_id in group.tasks:
                # CPU allocation
                cpu_need = group_resources.get("cpu", 1)
                resource_allocation["cpu_allocation"][task_id] = cpu_need
                
                # Memory allocation (in MB)
                memory_need = group_resources.get("memory_mb", 1024)
                resource_allocation["memory_allocation"][task_id] = memory_need
        
        # Add I/O optimizations based on conflicts
        io_optimizations = set()
        for conflict in analysis.resource_conflicts:
            if conflict.conflict_type == "io":
                io_optimizations.update(conflict.mitigation_strategies)
        
        resource_allocation["io_optimization"] = list(io_optimizations)
        
        # Scheduling strategy
        resource_allocation["scheduling_strategy"] = {
            "parallel_execution_mode": "adaptive",
            "resource_aware_scheduling": True,
            "conflict_avoidance": True,
            "priority_based_allocation": True
        }
        
        # Scaling recommendations
        total_parallel_capacity = sum(len(group.tasks) for group in analysis.parallel_groups)
        resource_allocation["scaling_recommendations"] = {
            "min_worker_instances": max(1, len(analysis.parallel_groups)),
            "max_worker_instances": min(10, total_parallel_capacity),
            "auto_scaling_triggers": ["cpu_usage > 80%", "memory_usage > 85%", "queue_depth > 5"],
            "resource_buffer_percent": 20
        }
        
        self.logger.info("Resource allocation optimization completed")
        return resource_allocation
    
    def _build_dependency_graph(self, tasks: List[TaskDefinition]) -> Dict[str, Set[str]]:
        """Build dependency graph from task definitions"""
        graph = defaultdict(set)
        
        for task in tasks:
            task_id = task.id
            dependencies = task.dependencies or []
            
            for dep_id in dependencies:
                graph[task_id].add(dep_id)
        
        return dict(graph)
    
    def _identify_independent_groups(self, 
                                   tasks: List[TaskDefinition],
                                   dependency_graph: Dict[str, Set[str]]) -> List[List[str]]:
        """Identify groups of tasks with no interdependencies"""
        
        # Start with all tasks
        task_ids = {task.id for task in tasks}
        independent_groups = []
        processed = set()
        
        # Find strongly connected components using DFS
        for task_id in task_ids:
            if task_id in processed:
                continue
                
            # Find all tasks reachable from this task
            reachable = self._get_reachable_tasks(task_id, dependency_graph)
            
            # Find all tasks that reach this task
            reaching = self._get_reaching_tasks(task_id, dependency_graph, task_ids)
            
            # Tasks in the same strongly connected component
            component = reachable.intersection(reaching)
            component.add(task_id)
            
            if len(component) > 1:
                independent_groups.append(list(component))
            
            processed.update(component)
        
        # Add remaining isolated tasks as individual groups
        remaining = task_ids - processed
        for task_id in remaining:
            independent_groups.append([task_id])
        
        return independent_groups
    
    def _get_reachable_tasks(self, start_task: str, graph: Dict[str, Set[str]]) -> Set[str]:
        """Get all tasks reachable from start_task following dependencies"""
        reachable = set()
        stack = [start_task]
        
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
                
            reachable.add(current)
            dependencies = graph.get(current, set())
            stack.extend(dependencies)
        
        reachable.discard(start_task)  # Remove self
        return reachable
    
    def _get_reaching_tasks(self, target_task: str, graph: Dict[str, Set[str]], all_tasks: Set[str]) -> Set[str]:
        """Get all tasks that can reach target_task"""
        reaching = set()
        
        for task_id in all_tasks:
            if target_task in self._get_reachable_tasks(task_id, graph):
                reaching.add(task_id)
        
        return reaching
    
    async def _analyze_resource_conflicts(self, 
                                        tasks: List[TaskDefinition],
                                        independent_groups: List[List[str]]) -> List[ResourceConflict]:
        """Analyze potential resource conflicts between parallel tasks"""
        
        conflicts = []
        task_map = {task.id: task for task in tasks}
        
        for group in independent_groups:
            if len(group) <= 1:
                continue
                
            # Analyze resource usage patterns within the group
            group_tasks = [task_map[task_id] for task_id in group]
            
            # Check CPU conflicts
            cpu_intensive_tasks = [
                task.id for task in group_tasks 
                if self._get_resource_intensity(task.type, "cpu") in ["high", "very_high"]
            ]
            
            if len(cpu_intensive_tasks) > 2:
                conflicts.append(ResourceConflict(
                    conflict_type="cpu",
                    conflicting_tasks=cpu_intensive_tasks,
                    severity="medium" if len(cpu_intensive_tasks) <= 4 else "high",
                    estimated_impact=min(0.9, len(cpu_intensive_tasks) * 0.2),
                    mitigation_strategies=[
                        "distribute_across_workers",
                        "increase_cpu_allocation",
                        "implement_cpu_throttling"
                    ]
                ))
            
            # Check memory conflicts
            memory_intensive_tasks = [
                task.id for task in group_tasks
                if self._get_resource_intensity(task.type, "memory") in ["high", "very_high"]
            ]
            
            if len(memory_intensive_tasks) > 1:
                conflicts.append(ResourceConflict(
                    conflict_type="memory",
                    conflicting_tasks=memory_intensive_tasks,
                    severity="high" if len(memory_intensive_tasks) > 2 else "medium",
                    estimated_impact=min(0.8, len(memory_intensive_tasks) * 0.3),
                    mitigation_strategies=[
                        "increase_memory_allocation",
                        "implement_memory_pooling",
                        "sequential_execution_fallback"
                    ]
                ))
            
            # Check I/O conflicts
            io_intensive_tasks = [
                task.id for task in group_tasks
                if self._get_resource_intensity(task.type, "io") in ["high", "very_high"]
            ]
            
            if len(io_intensive_tasks) > 1:
                conflicts.append(ResourceConflict(
                    conflict_type="io",
                    conflicting_tasks=io_intensive_tasks,
                    severity="medium",
                    estimated_impact=min(0.7, len(io_intensive_tasks) * 0.25),
                    mitigation_strategies=[
                        "implement_io_queuing",
                        "use_ssd_storage",
                        "enable_async_io"
                    ]
                ))
        
        return conflicts
    
    def _get_resource_intensity(self, task_type: str, resource_type: str) -> str:
        """Get resource intensity level for a task type"""
        
        # Convert TaskType enum to string if needed
        if hasattr(task_type, 'value'):
            task_type = task_type.value
        
        # Get resource mapping or use default
        resource_map = self.resource_intensive_tasks.get(task_type, {
            "cpu": "low", "memory": "low", "io": "low"
        })
        
        return resource_map.get(resource_type, "low")
    
    async def _get_ai_parallelization_analysis(self,
                                             workflow: EnhancedWorkflowDefinition,
                                             dependency_graph: Dict[str, Set[str]],
                                             resource_conflicts: List[ResourceConflict],
                                             historical_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get AI-powered parallelization analysis"""
        
        analysis_prompt = f"""
        Analyze this workflow for optimal parallel execution:
        
        Workflow: {workflow.name}
        Tasks: {json.dumps([task.to_dict() for task in workflow.tasks], indent=2)}
        Dependencies: {json.dumps({k: list(v) for k, v in dependency_graph.items()}, indent=2)}
        Resource Conflicts: {len(resource_conflicts)} detected conflicts
        Historical Data: {json.dumps(historical_data or {}, indent=2)}
        
        Provide detailed parallelization analysis:
        {{
            "optimal_parallel_groups": [
                {{
                    "group_id": "group_1",
                    "tasks": ["task1", "task2"],
                    "estimated_speedup": 1.8,
                    "resource_requirements": {{"cpu": 4, "memory_mb": 4096}},
                    "conflict_risk": 0.2,
                    "priority_score": 0.9
                }}
            ],
            "execution_strategy": {{
                "primary_strategy": "aggressive_parallelization|conservative_parallelization|hybrid",
                "fallback_strategy": "sequential_execution",
                "resource_allocation_mode": "dynamic|static|adaptive"
            }},
            "performance_predictions": {{
                "baseline_execution_time_minutes": 120,
                "optimized_execution_time_minutes": 75,
                "speedup_factor": 1.6,
                "resource_efficiency": 0.85,
                "success_probability": 0.92
            }},
            "confidence": 0.87
        }}
        
        Focus on:
        1. Maximizing parallelization while respecting dependencies
        2. Minimizing resource conflicts and contention
        3. Providing realistic performance predictions
        4. Considering failure modes and fallback strategies
        """
        
        try:
            result = await self.claude_agent.execute_task({
                "type": "parallelization_analysis",
                "prompt": analysis_prompt
            })
            
            return json.loads(result["result"])
            
        except Exception as e:
            self.logger.error("AI parallelization analysis failed", error=str(e))
            return self._get_heuristic_parallelization_analysis(workflow, dependency_graph, resource_conflicts)
    
    def _get_heuristic_parallelization_analysis(self,
                                              workflow: EnhancedWorkflowDefinition,
                                              dependency_graph: Dict[str, Set[str]],
                                              resource_conflicts: List[ResourceConflict]) -> Dict[str, Any]:
        """Get heuristic parallelization analysis when AI is unavailable"""
        
        # Simple heuristic analysis
        task_count = len(workflow.tasks)
        conflict_count = len(resource_conflicts)
        
        # Estimate speedup based on task independence
        independent_tasks = sum(1 for task in workflow.tasks if not task.dependencies)
        potential_speedup = min(4.0, 1.0 + (independent_tasks / task_count) * 2.0)
        
        # Reduce speedup based on conflicts
        conflict_penalty = min(0.5, conflict_count * 0.1)
        estimated_speedup = max(1.0, potential_speedup - conflict_penalty)
        
        return {
            "optimal_parallel_groups": [
                {
                    "group_id": "independent_tasks",
                    "tasks": [task.id for task in workflow.tasks if not task.dependencies],
                    "estimated_speedup": estimated_speedup,
                    "resource_requirements": {"cpu": independent_tasks, "memory_mb": independent_tasks * 1024},
                    "conflict_risk": conflict_penalty,
                    "priority_score": 0.7
                }
            ],
            "execution_strategy": {
                "primary_strategy": "conservative_parallelization",
                "fallback_strategy": "sequential_execution",
                "resource_allocation_mode": "static"
            },
            "performance_predictions": {
                "baseline_execution_time_minutes": task_count * 10,
                "optimized_execution_time_minutes": int((task_count * 10) / estimated_speedup),
                "speedup_factor": estimated_speedup,
                "resource_efficiency": max(0.5, 1.0 - conflict_penalty),
                "success_probability": 0.8
            },
            "confidence": 0.6
        }
    
    async def _create_optimized_parallel_groups(self,
                                              independent_groups: List[List[str]],
                                              resource_conflicts: List[ResourceConflict],
                                              ai_analysis: Dict[str, Any]) -> List[ParallelGroup]:
        """Create optimized parallel groups from analysis results"""
        
        parallel_groups = []
        
        # Use AI recommendations if available
        ai_groups = ai_analysis.get("optimal_parallel_groups", [])
        
        for i, ai_group in enumerate(ai_groups):
            group = ParallelGroup(
                group_id=ai_group.get("group_id", f"ai_group_{i}"),
                tasks=ai_group.get("tasks", []),
                estimated_speedup=ai_group.get("estimated_speedup", 1.0),
                resource_requirements=ai_group.get("resource_requirements", {}),
                dependencies_satisfied=True,  # AI should ensure this
                conflict_risk=ai_group.get("conflict_risk", 0.0),
                priority_score=ai_group.get("priority_score", 0.5)
            )
            parallel_groups.append(group)
        
        # If no AI groups, use heuristic groups
        if not parallel_groups:
            for i, group_tasks in enumerate(independent_groups):
                if len(group_tasks) > 1:
                    group = ParallelGroup(
                        group_id=f"heuristic_group_{i}",
                        tasks=group_tasks,
                        estimated_speedup=min(len(group_tasks), 4),
                        resource_requirements={"cpu": len(group_tasks), "memory_mb": len(group_tasks) * 1024},
                        dependencies_satisfied=True,
                        conflict_risk=0.3,
                        priority_score=0.6
                    )
                    parallel_groups.append(group)
        
        return parallel_groups
    
    async def _generate_execution_strategy(self,
                                         parallel_groups: List[ParallelGroup],
                                         resource_conflicts: List[ResourceConflict],
                                         workflow: EnhancedWorkflowDefinition) -> Dict[str, Any]:
        """Generate execution strategy based on analysis"""
        
        # Determine primary strategy based on conflicts and group characteristics
        high_conflict_count = sum(1 for c in resource_conflicts if c.severity in ["high", "critical"])
        
        if high_conflict_count > 2:
            primary_strategy = "conservative_parallelization"
        elif len(parallel_groups) > 3 and high_conflict_count == 0:
            primary_strategy = "aggressive_parallelization"
        else:
            primary_strategy = "hybrid_parallelization"
        
        return {
            "primary_strategy": primary_strategy,
            "fallback_strategy": "sequential_execution",
            "resource_allocation_mode": "adaptive",
            "conflict_resolution": "resource_throttling",
            "monitoring_strategy": "real_time_adjustment",
            "failure_handling": "graceful_degradation"
        }
    
    async def _predict_performance_improvements(self,
                                              workflow: EnhancedWorkflowDefinition,
                                              parallel_groups: List[ParallelGroup],
                                              historical_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Predict performance improvements from parallelization"""
        
        baseline_time = len(workflow.tasks) * 10  # Assume 10 minutes per task baseline
        
        # Calculate parallelized time
        max_group_time = 0
        for group in parallel_groups:
            group_time = len(group.tasks) * 10 / group.estimated_speedup
            max_group_time = max(max_group_time, group_time)
        
        optimized_time = max(baseline_time * 0.6, max_group_time)  # At least 40% improvement
        
        return {
            "baseline_execution_time_minutes": baseline_time,
            "optimized_execution_time_minutes": int(optimized_time),
            "speedup_factor": baseline_time / optimized_time,
            "resource_efficiency": 0.8,
            "success_probability": 0.85,
            "improvement_breakdown": {
                "parallelization_gain": baseline_time - optimized_time,
                "resource_optimization_gain": baseline_time * 0.1,
                "dependency_optimization_gain": baseline_time * 0.05
            }
        }
    
    def _calculate_optimization_score(self,
                                    parallel_groups: List[ParallelGroup],
                                    resource_conflicts: List[ResourceConflict], 
                                    performance_predictions: Dict[str, Any]) -> float:
        """Calculate overall optimization score"""
        
        # Base score from speedup
        speedup_score = min(1.0, performance_predictions.get("speedup_factor", 1.0) / 3.0)
        
        # Penalty for resource conflicts
        conflict_penalty = sum(
            0.1 if c.severity == "low" else
            0.2 if c.severity == "medium" else
            0.3 if c.severity == "high" else 0.4
            for c in resource_conflicts
        )
        
        # Bonus for parallel opportunities
        parallel_bonus = min(0.3, len(parallel_groups) * 0.1)
        
        # Combine scores
        final_score = max(0.0, min(1.0, speedup_score + parallel_bonus - conflict_penalty))
        
        return final_score
    
    def _identify_dependency_bottlenecks(self, parallel_groups: List[ParallelGroup]) -> List[Dict[str, Any]]:
        """Identify dependency-based bottlenecks"""
        
        bottlenecks = []
        
        # Check for groups with single-task dependencies (potential bottlenecks)
        for group in parallel_groups:
            if len(group.tasks) == 1 and group.estimated_speedup < 1.2:
                bottlenecks.append({
                    "type": "dependency_bottleneck",
                    "description": f"Task {group.tasks[0]} may block parallel execution",
                    "affected_tasks": group.tasks,
                    "severity": "medium",
                    "probability": 0.6,
                    "mitigation_strategies": [
                        "break_task_dependencies",
                        "optimize_task_execution",
                        "pre_compute_dependencies"
                    ]
                })
        
        return bottlenecks
    
    def _identify_scalability_bottlenecks(self, analysis: ParallelizationAnalysis) -> List[Dict[str, Any]]:
        """Identify scalability bottlenecks"""
        
        bottlenecks = []
        
        # Check if parallelization is limited
        max_parallel_tasks = max(len(group.tasks) for group in analysis.parallel_groups) if analysis.parallel_groups else 1
        
        if max_parallel_tasks > 8:
            bottlenecks.append({
                "type": "scalability_bottleneck",
                "description": f"Large parallel group ({max_parallel_tasks} tasks) may exceed resource capacity",
                "affected_tasks": [],
                "severity": "medium",
                "probability": 0.5,
                "mitigation_strategies": [
                    "implement_batch_processing",
                    "add_resource_scaling",
                    "break_into_smaller_groups"
                ]
            })
        
        return bottlenecks
    
    async def _create_fallback_analysis(self, workflow: EnhancedWorkflowDefinition) -> ParallelizationAnalysis:
        """Create fallback analysis when main analysis fails"""
        
        return ParallelizationAnalysis(
            parallel_groups=[],
            resource_conflicts=[],
            execution_strategy={
                "primary_strategy": "sequential_execution",
                "fallback_strategy": "sequential_execution",
                "resource_allocation_mode": "static"
            },
            performance_predictions={
                "baseline_execution_time_minutes": len(workflow.tasks) * 10,
                "optimized_execution_time_minutes": len(workflow.tasks) * 10,
                "speedup_factor": 1.0,
                "resource_efficiency": 0.5,
                "success_probability": 0.9
            },
            optimization_score=0.1,
            confidence_level=0.3
        )


# Factory function for dependency injection
async def create_parallel_execution_analyzer(claude_agent: ClaudeAgentWrapper = None,
                                           provider_coordinator=None) -> ParallelExecutionAnalyzer:
    """
    Factory function to create parallel execution analyzer.
    
    Args:
        claude_agent: Optional Claude CLI wrapper for AI capabilities
        provider_coordinator: Optional provider coordinator for resource intelligence
        
    Returns:
        Configured ParallelExecutionAnalyzer instance
    """
    return ParallelExecutionAnalyzer(claude_agent, provider_coordinator)
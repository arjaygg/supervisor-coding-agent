"""
Workflow Integration Service

This service integrates the AI Workflow Synthesizer with the existing
multi-provider architecture, workflow engine, and task management system.

Follows SOLID principles:
- Single Responsibility: Handles only integration concerns
- Open-Closed: Extensible for new workflow types
- Dependency Inversion: Depends on abstractions, not concretions
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel

from supervisor_agent.core.provider_coordinator import ProviderCoordinator
from supervisor_agent.core.workflow_engine import WorkflowEngine
from supervisor_agent.core.workflow_models import WorkflowDefinition
from supervisor_agent.db.crud import TaskCRUD, WorkflowCRUD
from supervisor_agent.db.models import Task, TaskStatus, TaskType
from supervisor_agent.intelligence.workflow_synthesizer import (
    AIWorkflowSynthesizer,
    EnhancedWorkflowDefinition,
    RequirementAnalysis,
    TenantContext,
    create_workflow_synthesizer,
)

logger = logging.getLogger(__name__)
structured_logger = structlog.get_logger(__name__)


class WorkflowSynthesisRequest(BaseModel):
    """Request model for workflow synthesis"""

    description: str
    tenant_id: str
    user_id: Optional[str] = None
    priority: int = 5
    context: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {}


class WorkflowSynthesisResult(BaseModel):
    """Result model for workflow synthesis"""

    workflow_id: str
    workflow_name: str
    estimated_duration_hours: float
    task_count: int
    parallel_opportunities: List[List[str]]
    quality_gates: List[Dict[str, Any]]
    synthesis_metadata: Dict[str, Any]


class WorkflowIntegrationService:
    """
    Integration service for AI Workflow Synthesizer.

    Provides a clean interface between the AI workflow synthesis capabilities
    and the existing task management, provider coordination, and workflow execution systems.
    """

    def __init__(
        self,
        provider_coordinator: ProviderCoordinator,
        workflow_engine: WorkflowEngine,
        task_crud: TaskCRUD,
        workflow_crud: WorkflowCRUD,
    ):
        """
        Initialize the integration service.

        Args:
            provider_coordinator: Existing provider coordination system
            workflow_engine: Existing workflow execution engine
            task_crud: Task database operations
            workflow_crud: Workflow database operations
        """
        self.provider_coordinator = provider_coordinator
        self.workflow_engine = workflow_engine
        self.task_crud = task_crud
        self.workflow_crud = workflow_crud
        self.synthesizer_cache: Dict[str, AIWorkflowSynthesizer] = {}
        self.logger = structured_logger.bind(component="workflow_integration_service")

    async def synthesize_and_create_workflow(
        self, request: WorkflowSynthesisRequest
    ) -> WorkflowSynthesisResult:
        """
        Synthesize an AI-generated workflow and create it in the system.

        Args:
            request: Workflow synthesis request with requirements and context

        Returns:
            WorkflowSynthesisResult with created workflow details
        """
        self.logger.info(
            "Starting workflow synthesis",
            tenant_id=request.tenant_id,
            description=request.description[:100],
        )

        try:
            # Get or create synthesizer for tenant
            synthesizer = await self._get_synthesizer_for_tenant(request.tenant_id)

            # Analyze requirements using AI
            requirements = await synthesizer.analyze_requirements(
                request.description, request.context
            )

            # Synthesize optimal workflow
            enhanced_workflow = await synthesizer.synthesize_optimal_workflow(
                requirements
            )

            # Convert to standard workflow definition
            standard_workflow = await self._convert_to_standard_workflow(
                enhanced_workflow, request
            )

            # Create workflow in database
            created_workflow = await self.workflow_crud.create(standard_workflow)

            # Create result
            result = WorkflowSynthesisResult(
                workflow_id=str(created_workflow.id),
                workflow_name=enhanced_workflow.name,
                estimated_duration_hours=requirements.estimated_duration_hours,
                task_count=len(enhanced_workflow.tasks),
                parallel_opportunities=enhanced_workflow.optimization_hints.get(
                    "parallel_groups", []
                ),
                quality_gates=enhanced_workflow.quality_gates or [],
                synthesis_metadata={
                    "ai_confidence": 0.85,  # TODO: Get from synthesizer
                    "synthesis_time": datetime.now(timezone.utc).isoformat(),
                    "requirements_complexity": requirements.complexity.value,
                    "domain": requirements.domain.value,
                },
            )

            self.logger.info(
                "Workflow synthesis completed successfully",
                workflow_id=result.workflow_id,
                task_count=result.task_count,
            )

            return result

        except Exception as e:
            self.logger.error(
                "Workflow synthesis failed", error=str(e), tenant_id=request.tenant_id
            )
            raise

    async def execute_synthesized_workflow(
        self, workflow_id: str, execution_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a synthesized workflow using the existing workflow engine.

        Args:
            workflow_id: ID of the workflow to execute
            execution_context: Additional context for execution

        Returns:
            Execution result with status and details
        """
        self.logger.info(
            "Starting synthesized workflow execution", workflow_id=workflow_id
        )

        try:
            # Get workflow from database
            workflow = await self.workflow_crud.get(workflow_id)
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")

            # Execute using existing workflow engine
            execution_result = await self.workflow_engine.execute_workflow(
                workflow, execution_context or {}
            )

            self.logger.info(
                "Synthesized workflow execution completed",
                workflow_id=workflow_id,
                status=execution_result.status,
            )

            return execution_result

        except Exception as e:
            self.logger.error(
                "Synthesized workflow execution failed",
                workflow_id=workflow_id,
                error=str(e),
            )
            raise

    async def adapt_running_workflow(
        self, workflow_execution_id: str, performance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Adapt a running workflow based on real-time performance data.

        Args:
            workflow_execution_id: ID of the running workflow execution
            performance_data: Current performance metrics and state

        Returns:
            Adaptation recommendations and actions taken
        """
        self.logger.info(
            "Starting workflow adaptation", execution_id=workflow_execution_id
        )

        try:
            # Get workflow execution details
            execution = await self.workflow_crud.get_execution(workflow_execution_id)
            if not execution:
                raise ValueError(
                    f"Workflow execution {workflow_execution_id} not found"
                )

            # Get synthesizer for the tenant
            tenant_id = execution.get("tenant_id")
            synthesizer = await self._get_synthesizer_for_tenant(tenant_id)

            # Get adaptation recommendations
            adaptation = await synthesizer.adapt_workflow_realtime(
                workflow_execution_id, performance_data
            )

            # Apply adaptation actions (TODO: Implement adaptation actions)
            adaptation_result = await self._apply_workflow_adaptations(
                workflow_execution_id, adaptation
            )

            self.logger.info(
                "Workflow adaptation completed",
                execution_id=workflow_execution_id,
                adaptation_type=adaptation.adaptation_type,
            )

            return {
                "adaptation": adaptation,
                "actions_taken": adaptation_result,
                "status": "completed",
            }

        except Exception as e:
            self.logger.error(
                "Workflow adaptation failed",
                execution_id=workflow_execution_id,
                error=str(e),
            )
            raise

    async def get_workflow_intelligence_metrics(
        self, tenant_id: str, time_range: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get intelligence metrics for workflow synthesis and execution.

        Args:
            tenant_id: Tenant to get metrics for
            time_range: Optional time range filter

        Returns:
            Intelligence metrics and insights
        """
        self.logger.info("Getting workflow intelligence metrics", tenant_id=tenant_id)

        try:
            # Get workflow performance data
            workflows = await self.workflow_crud.get_by_tenant(tenant_id, time_range)

            # Calculate metrics
            metrics = {
                "total_workflows_synthesized": len(workflows),
                "average_synthesis_confidence": 0.85,  # TODO: Calculate from actual data
                "workflow_success_rate": await self._calculate_success_rate(workflows),
                "average_execution_time_improvement": 0.6,  # TODO: Calculate vs baseline
                "human_intervention_rate": await self._calculate_human_intervention_rate(
                    workflows
                ),
                "most_common_domains": await self._get_domain_distribution(workflows),
                "optimization_impact": await self._calculate_optimization_impact(
                    workflows
                ),
            }

            self.logger.info(
                "Workflow intelligence metrics calculated",
                tenant_id=tenant_id,
                total_workflows=metrics["total_workflows_synthesized"],
            )

            return metrics

        except Exception as e:
            self.logger.error(
                "Failed to get workflow intelligence metrics",
                tenant_id=tenant_id,
                error=str(e),
            )
            raise

    async def _get_synthesizer_for_tenant(
        self, tenant_id: str
    ) -> AIWorkflowSynthesizer:
        """Get or create AI workflow synthesizer for tenant"""

        if tenant_id not in self.synthesizer_cache:
            # Create tenant context (TODO: Get from database/config)
            tenant_context = TenantContext(
                tenant_id=tenant_id,
                org_profile={"name": f"Organization-{tenant_id}"},
                team_skills=["Python", "FastAPI", "AI", "DevOps"],
                team_hierarchy={"lead": "system"},
                approval_policies={"production_deploy": "lead_approval"},
                resource_limits={"max_parallel_tasks": 10},
                quality_standards={"code_coverage": 0.8, "security_scan": True},
            )

            # Create synthesizer with provider integration
            synthesizer = await create_workflow_synthesizer(
                tenant_context=tenant_context,
                provider_coordinator=self.provider_coordinator,
            )

            self.synthesizer_cache[tenant_id] = synthesizer

        return self.synthesizer_cache[tenant_id]

    async def _convert_to_standard_workflow(
        self,
        enhanced_workflow: EnhancedWorkflowDefinition,
        request: WorkflowSynthesisRequest,
    ) -> WorkflowDefinition:
        """Convert enhanced workflow to standard workflow definition"""

        # Convert enhanced workflow to standard format
        standard_workflow = WorkflowDefinition(
            name=enhanced_workflow.name,
            description=enhanced_workflow.description,
            tasks=enhanced_workflow.tasks,
            version=enhanced_workflow.version,
            # Add enhanced metadata as config
            config={
                "ai_generated": True,
                "synthesis_request": request.dict(),
                "dynamic_task_templates": enhanced_workflow.dynamic_task_templates,
                "conditional_branches": enhanced_workflow.conditional_branches,
                "optimization_hints": enhanced_workflow.optimization_hints,
                "risk_mitigation": enhanced_workflow.risk_mitigation,
                "quality_gates": enhanced_workflow.quality_gates,
            },
        )

        return standard_workflow

    async def _apply_workflow_adaptations(
        self, execution_id: str, adaptation
    ) -> List[str]:
        """Apply workflow adaptation recommendations"""

        actions_taken = []

        for action in adaptation.recommended_actions:
            if action == "add_parallel_agent":
                # TODO: Implement adding parallel agents
                actions_taken.append("increased_parallelism")
            elif action == "increase_memory":
                # TODO: Implement resource adjustments
                actions_taken.append("adjusted_resources")
            elif action == "optimize_resource_allocation":
                # TODO: Implement resource optimization
                actions_taken.append("optimized_allocation")
            # Add more adaptation actions as needed

        return actions_taken

    async def _calculate_success_rate(self, workflows: List[Dict[str, Any]]) -> float:
        """Calculate workflow success rate"""
        if not workflows:
            return 0.0

        successful = sum(1 for w in workflows if w.get("status") == "completed")
        return successful / len(workflows)

    async def _calculate_human_intervention_rate(
        self, workflows: List[Dict[str, Any]]
    ) -> float:
        """Calculate rate of workflows requiring human intervention"""
        if not workflows:
            return 0.0

        # TODO: Implement based on actual workflow execution data
        return 0.15  # Mock 15% intervention rate

    async def _get_domain_distribution(
        self, workflows: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Get distribution of workflow domains"""
        domains = {}
        for workflow in workflows:
            domain = (
                workflow.get("config", {})
                .get("synthesis_request", {})
                .get("domain", "unknown")
            )
            domains[domain] = domains.get(domain, 0) + 1
        return domains

    async def _calculate_optimization_impact(
        self, workflows: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate impact of AI optimizations"""
        # TODO: Implement based on actual performance data
        return {
            "execution_time_improvement": 0.6,
            "resource_efficiency_gain": 0.35,
            "error_rate_reduction": 0.4,
            "parallel_execution_increase": 0.8,
        }


# Service factory for dependency injection
async def create_workflow_integration_service(
    provider_coordinator: ProviderCoordinator,
    workflow_engine: WorkflowEngine,
    task_crud: TaskCRUD,
    workflow_crud: WorkflowCRUD,
) -> WorkflowIntegrationService:
    """
    Factory function to create workflow integration service.

    This follows the Dependency Inversion Principle by accepting
    abstractions rather than concrete implementations.
    """
    return WorkflowIntegrationService(
        provider_coordinator=provider_coordinator,
        workflow_engine=workflow_engine,
        task_crud=task_crud,
        workflow_crud=workflow_crud,
    )

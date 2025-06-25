"""
Provider Management API Routes

Provides endpoints for managing and monitoring the multi-provider system.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

from supervisor_agent.core.multi_provider_service import multi_provider_service
from supervisor_agent.db.models import Task, TaskType
from supervisor_agent.db.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


class ProviderConfig(BaseModel):
    """Provider configuration model"""
    type: str = Field(..., description="Provider type (claude_cli, local_mock, etc.)")
    config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")
    priority: Optional[int] = Field(None, description="Provider priority (1-10)")
    enabled: bool = Field(True, description="Whether provider is enabled")


class TaskExecutionRequest(BaseModel):
    """Task execution request model"""
    task_type: str = Field(..., description="Type of task to execute")
    payload: Dict[str, Any] = Field(..., description="Task payload data")
    routing_strategy: Optional[str] = Field(None, description="Routing strategy (optimal, fastest, cheapest, etc.)")
    context: Optional[Dict[str, Any]] = Field(None, description="Execution context")
    shared_memory: Optional[Dict[str, Any]] = Field(None, description="Shared memory between tasks")


class BatchExecutionRequest(BaseModel):
    """Batch task execution request model"""
    tasks: List[TaskExecutionRequest] = Field(..., description="List of tasks to execute")
    max_concurrent: int = Field(5, description="Maximum concurrent executions")
    context: Optional[Dict[str, Any]] = Field(None, description="Shared execution context")


class ProviderRecommendationRequest(BaseModel):
    """Provider recommendation request model"""
    task_type: str = Field(..., description="Type of task")
    payload: Dict[str, Any] = Field(..., description="Task payload")
    context: Optional[Dict[str, Any]] = Field(None, description="Execution context")


@router.get("/status")
async def get_provider_status():
    """
    Get status of all providers including health, quotas, and metrics
    """
    try:
        if not multi_provider_service.is_enabled():
            return {
                "enabled": False,
                "message": "Multi-provider system is not enabled"
            }
            
        status = await multi_provider_service.get_provider_status()
        status["enabled"] = True
        return status
        
    except Exception as e:
        logger.error(f"Error getting provider status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
async def get_provider_analytics():
    """
    Get cross-provider analytics and performance metrics
    """
    try:
        if not multi_provider_service.is_enabled():
            raise HTTPException(status_code=503, detail="Multi-provider system not enabled")
            
        analytics = await multi_provider_service.get_analytics()
        return analytics
        
    except Exception as e:
        logger.error(f"Error getting provider analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_task(request: TaskExecutionRequest):
    """
    Execute a single task using the multi-provider system
    """
    try:
        if not multi_provider_service.is_enabled():
            raise HTTPException(status_code=503, detail="Multi-provider system not enabled")
            
        # Create task object
        task = Task(
            type=TaskType(request.task_type),
            payload=request.payload,
            status="pending"
        )
        
        # Mock agent processor for demonstration
        async def mock_agent_processor(task, shared_memory):
            return {"processed": True, "task_id": task.id}
            
        result = await multi_provider_service.process_task(
            task=task,
            agent_processor=mock_agent_processor,
            context=request.context,
            routing_strategy=request.routing_strategy,
            shared_memory=request.shared_memory
        )
        
        return {
            "success": True,
            "result": result,
            "task_id": task.id
        }
        
    except Exception as e:
        logger.error(f"Error executing task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/batch")
async def execute_task_batch(request: BatchExecutionRequest):
    """
    Execute multiple tasks with batch optimization
    """
    try:
        if not multi_provider_service.is_enabled():
            raise HTTPException(status_code=503, detail="Multi-provider system not enabled")
            
        # Create task objects
        tasks = []
        for i, task_req in enumerate(request.tasks):
            task = Task(
                id=i + 1,  # Temporary ID
                type=TaskType(task_req.task_type),
                payload=task_req.payload,
                status="pending"
            )
            tasks.append(task)
            
        # Mock agent processor
        async def mock_agent_processor(task, shared_memory):
            return {"processed": True, "task_id": task.id}
            
        results = await multi_provider_service.process_task_batch(
            tasks=tasks,
            agent_processor=mock_agent_processor,
            context=request.context,
            max_concurrent=request.max_concurrent
        )
        
        return {
            "success": True,
            "results": results,
            "task_count": len(tasks),
            "processed_count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error executing task batch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendations")
async def get_provider_recommendations(request: ProviderRecommendationRequest):
    """
    Get provider recommendations for a specific task
    """
    try:
        if not multi_provider_service.is_enabled():
            raise HTTPException(status_code=503, detail="Multi-provider system not enabled")
            
        # Create task object for recommendation
        task = Task(
            type=TaskType(request.task_type),
            payload=request.payload,
            status="pending"
        )
        
        recommendations = await multi_provider_service.get_provider_recommendations(
            task=task,
            context=request.context
        )
        
        return {
            "success": True,
            "recommendations": recommendations,
            "task_type": request.task_type
        }
        
    except Exception as e:
        logger.error(f"Error getting provider recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider_id}/register")
async def register_provider(provider_id: str, config: ProviderConfig):
    """
    Register a new provider
    """
    try:
        if not multi_provider_service.is_enabled():
            raise HTTPException(status_code=503, detail="Multi-provider system not enabled")
            
        success = await multi_provider_service.register_provider(
            provider_id=provider_id,
            provider_type=config.type,
            config=config.config
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to register provider")
            
        return {
            "success": True,
            "message": f"Provider {provider_id} registered successfully",
            "provider_id": provider_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering provider {provider_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{provider_id}")
async def unregister_provider(provider_id: str):
    """
    Unregister a provider
    """
    try:
        if not multi_provider_service.is_enabled():
            raise HTTPException(status_code=503, detail="Multi-provider system not enabled")
            
        success = await multi_provider_service.unregister_provider(provider_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Provider not found or failed to unregister")
            
        return {
            "success": True,
            "message": f"Provider {provider_id} unregistered successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unregistering provider {provider_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider_id}/health")
async def get_provider_health(provider_id: str):
    """
    Get health status for a specific provider
    """
    try:
        if not multi_provider_service.is_enabled():
            raise HTTPException(status_code=503, detail="Multi-provider system not enabled")
            
        status = await multi_provider_service.get_provider_status()
        
        if provider_id not in status.get("providers", {}):
            raise HTTPException(status_code=404, detail="Provider not found")
            
        provider_info = status["providers"][provider_id]
        quota_info = status.get("quota_status", {}).get(provider_id, {})
        
        return {
            "provider_id": provider_id,
            "health": provider_info,
            "quota": quota_info,
            "timestamp": status.get("timestamp")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider health for {provider_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider_id}/usage")
async def get_provider_usage(
    provider_id: str,
    days: int = Query(7, description="Number of days to retrieve usage for")
):
    """
    Get usage statistics for a specific provider
    """
    try:
        if not multi_provider_service.is_enabled():
            raise HTTPException(status_code=503, detail="Multi-provider system not enabled")
            
        # Get analytics data
        analytics = await multi_provider_service.get_analytics()
        
        # Extract provider-specific usage data
        provider_usage = {
            "provider_id": provider_id,
            "usage_data": {
                "requests_today": analytics.get("total_requests_today", 0),
                "cost_today": analytics.get("total_cost_today", 0.0),
                "quota_utilization": analytics.get("quota_utilization", {}).get(provider_id, 0.0)
            },
            "period_days": days
        }
        
        return provider_usage
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider usage for {provider_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_providers(
    include_health: bool = Query(False, description="Include health status in response"),
    provider_type: Optional[str] = Query(None, description="Filter by provider type")
):
    """
    List all registered providers
    """
    try:
        if not multi_provider_service.is_enabled():
            return {
                "enabled": False,
                "providers": [],
                "message": "Multi-provider system is not enabled"
            }
            
        status = await multi_provider_service.get_provider_status()
        providers = status.get("providers", {})
        
        # Filter by type if specified
        if provider_type:
            providers = {
                pid: info for pid, info in providers.items()
                if info.get("type", "").lower() == provider_type.lower()
            }
            
        # Include or exclude health details
        if not include_health:
            providers = {
                pid: {
                    "name": info.get("name"),
                    "type": info.get("type"),
                    "capabilities": info.get("capabilities", [])
                }
                for pid, info in providers.items()
            }
            
        return {
            "enabled": True,
            "providers": providers,
            "total_count": len(providers),
            "healthy_count": status.get("healthy_providers", 0)
        }
        
    except Exception as e:
        logger.error(f"Error listing providers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
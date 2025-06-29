from datetime import datetime, timezone

import redis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from supervisor_agent.config import settings
from supervisor_agent.core.notifier import notification_manager
from supervisor_agent.db import crud, schemas
from supervisor_agent.db.database import engine, get_db
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/ping")
async def ping():
    """Simple ping endpoint for basic health check"""
    return {"status": "ok", "message": "pong"}


@router.get("/healthz", response_model=schemas.HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Basic health check endpoint"""
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        database_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        database_healthy = False

    # Test Redis connection (optional in development)
    try:
        redis_client = redis.from_url(settings.redis_url)
        redis_client.ping()
        redis_healthy = True
    except Exception as e:
        if settings.redis_required:
            logger.error(f"Redis health check failed: {str(e)}")
            redis_healthy = False
        else:
            logger.warning(
                f"Redis unavailable but not required in development: {str(e)}"
            )
            redis_healthy = True  # Consider healthy in development mode

    # Count active agents
    try:
        active_agents = crud.AgentCRUD.get_active_agents(db)
        agents_count = len(active_agents)
    except Exception as e:
        logger.error(f"Failed to count active agents: {str(e)}")
        agents_count = 0

    # Determine overall status
    status = "healthy"
    if not database_healthy or not redis_healthy:
        status = "unhealthy"
    elif agents_count == 0:
        status = "degraded"

    return schemas.HealthResponse(
        status=status,
        timestamp=datetime.now(timezone.utc),
        database=database_healthy,
        redis=redis_healthy,
        agents_active=agents_count,
    )


@router.get("/readyz")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness check for Kubernetes/container orchestration"""
    try:
        # More comprehensive checks for readiness

        # Database connectivity and basic query
        db.execute(text("SELECT COUNT(*) FROM agents"))

        # Redis connectivity
        redis_client = redis.from_url(settings.redis_url)
        redis_client.ping()

        # Check if we have at least one active agent
        active_agents = crud.AgentCRUD.get_active_agents(db)
        if len(active_agents) == 0:
            raise Exception("No active agents available")

        return {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}

    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check with component status"""
    health_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "components": {},
        "issues": [],
    }

    # Database health
    try:
        db.execute(text("SELECT 1"))
        # Test some basic operations
        task_count = len(crud.TaskCRUD.get_tasks(db, limit=1))
        agent_count = len(crud.AgentCRUD.get_active_agents(db))

        health_data["components"]["database"] = {
            "status": "healthy",
            "details": {
                "connection": "ok",
                "task_count": task_count,
                "agent_count": agent_count,
            },
        }
    except Exception as e:
        health_data["components"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_data["issues"].append(f"Database: {str(e)}")

    # Redis health
    try:
        redis_client = redis.from_url(settings.redis_url)
        redis_client.ping()
        info = redis_client.info()

        health_data["components"]["redis"] = {
            "status": "healthy",
            "details": {
                "connection": "ok",
                "version": info.get("redis_version"),
                "memory_used": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
            },
        }
    except Exception as e:
        health_data["components"]["redis"] = {"status": "unhealthy", "error": str(e)}
        health_data["issues"].append(f"Redis: {str(e)}")

    # Agent health
    try:
        from supervisor_agent.core.quota import quota_manager

        quota_status = quota_manager.get_quota_status(db)

        health_data["components"]["agents"] = {
            "status": "healthy" if quota_status["available_agents"] > 0 else "degraded",
            "details": quota_status,
        }

        if quota_status["available_agents"] == 0:
            health_data["issues"].append("No agents available for task processing")

    except Exception as e:
        health_data["components"]["agents"] = {"status": "unhealthy", "error": str(e)}
        health_data["issues"].append(f"Agents: {str(e)}")

    # Queue health (basic check)
    try:
        redis_client = redis.from_url(settings.redis_url)

        # Check for any queued tasks (this is a simple check)
        # In a real implementation, you might want to check Celery queue stats
        queue_length = redis_client.llen("celery")  # Default Celery queue

        health_data["components"]["queue"] = {
            "status": "healthy",
            "details": {"connection": "ok", "queue_length": queue_length},
        }
    except Exception as e:
        health_data["components"]["queue"] = {"status": "unhealthy", "error": str(e)}
        health_data["issues"].append(f"Queue: {str(e)}")

    # Overall status
    component_statuses = [comp["status"] for comp in health_data["components"].values()]
    if "unhealthy" in component_statuses:
        health_data["status"] = "unhealthy"
    elif "degraded" in component_statuses:
        health_data["status"] = "degraded"
    else:
        health_data["status"] = "healthy"

    return health_data


@router.post("/health/notifications/test")
async def test_notifications():
    """Test notification channels"""
    try:
        results = notification_manager.test_notifications()
        return {
            "message": "Notification test completed",
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Notification test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """Prometheus-style metrics endpoint"""
    try:
        # Get task statistics
        all_tasks = crud.TaskCRUD.get_tasks(db, limit=10000)

        # Basic metrics
        metrics = {
            "supervisor_agent_tasks_total": len(all_tasks),
            "supervisor_agent_tasks_by_status": {},
            "supervisor_agent_tasks_by_type": {},
            "supervisor_agent_agents_total": 0,
            "supervisor_agent_agents_available": 0,
        }

        # Count tasks by status and type
        for task in all_tasks:
            status_key = f"supervisor_agent_tasks_status_{task.status.lower()}"
            metrics[status_key] = metrics.get(status_key, 0) + 1

            type_key = f"supervisor_agent_tasks_type_{task.type.lower()}"
            metrics[type_key] = metrics.get(type_key, 0) + 1

        # Agent metrics
        from supervisor_agent.core.quota import quota_manager

        quota_status = quota_manager.get_quota_status(db)
        metrics["supervisor_agent_agents_total"] = quota_status["total_agents"]
        metrics["supervisor_agent_agents_available"] = quota_status["available_agents"]

        # Cost and usage metrics
        try:
            cost_summary = crud.CostTrackingCRUD.get_cost_summary(db)
            metrics["supervisor_agent_total_cost_usd"] = float(
                cost_summary["total_cost_usd"]
            )
            metrics["supervisor_agent_total_tokens"] = cost_summary["total_tokens"]
            metrics["supervisor_agent_total_requests"] = cost_summary["total_requests"]
            metrics["supervisor_agent_avg_cost_per_request"] = float(
                cost_summary["avg_cost_per_request"]
            )
        except Exception as cost_error:
            logger.warning(f"Failed to get cost metrics: {str(cost_error)}")
            metrics["supervisor_agent_total_cost_usd"] = 0.0
            metrics["supervisor_agent_total_tokens"] = 0
            metrics["supervisor_agent_total_requests"] = 0

        return metrics

    except Exception as e:
        logger.error(f"Failed to get metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

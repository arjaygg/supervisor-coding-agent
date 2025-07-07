"""
Analytics API Routes

RESTful API endpoints for analytics dashboard functionality.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from supervisor_agent.config import settings
from supervisor_agent.core.analytics_engine import AnalyticsEngine
from supervisor_agent.core.analytics_models import (
    AnalyticsQuery,
    AnalyticsResult,
    AnalyticsSummary,
    Insight,
    MetricEntry,
    MetricEntryResponse,
    MetricType,
    TimeRange,
    TrendPrediction,
)
from supervisor_agent.core.metrics_collector import MetricsCollector
from supervisor_agent.db.database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Initialize services
analytics_engine = AnalyticsEngine()
metrics_collector = MetricsCollector()


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary():
    """Get high-level analytics summary for dashboard overview"""
    try:
        summary = await analytics_engine.get_summary_analytics()
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analytics summary: {str(e)}",
        )


@router.post("/query", response_model=AnalyticsResult)
async def query_metrics(query: AnalyticsQuery):
    """Execute analytics query and return processed results"""
    try:
        result = await analytics_engine.process_metrics(query)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution failed: {str(e)}")


@router.get("/insights", response_model=List[Insight])
async def get_insights(
    timeframe: TimeRange = Query(
        TimeRange.DAY, description="Time range for insight analysis"
    )
):
    """Get actionable insights based on recent metrics"""
    try:
        insights = await analytics_engine.generate_insights(timeframe)
        return insights
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate insights: {str(e)}"
        )


@router.get("/trends/{metric_type}", response_model=TrendPrediction)
async def get_trend_prediction(
    metric_type: MetricType,
    prediction_hours: int = Query(
        24, ge=1, le=168, description="Hours to predict (1-168)"
    ),
):
    """Get trend prediction for specified metric type"""
    try:
        prediction = await analytics_engine.predict_trends(
            metric_type, prediction_hours
        )
        return prediction
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate trend prediction: {str(e)}",
        )


@router.get("/metrics", response_model=List[MetricEntryResponse])
async def get_recent_metrics(
    metric_type: Optional[MetricType] = Query(
        None, description="Filter by metric type"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Number of recent metrics to return"
    ),
    db: Session = Depends(get_db),
):
    """Get recent raw metric entries"""
    try:
        query = db.query(MetricEntry)

        if metric_type:
            query = query.filter(MetricEntry.metric_type == metric_type.value)

        metrics = query.order_by(MetricEntry.timestamp.desc()).limit(limit).all()
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve metrics: {str(e)}"
        )


@router.post("/collect/task/{task_id}")
async def collect_task_metrics(task_id: int, background_tasks: BackgroundTasks):
    """Trigger collection of metrics for a specific task"""
    try:
        background_tasks.add_task(
            metrics_collector.collect_and_store_task_metrics, task_id
        )
        return {"message": f"Metrics collection triggered for task {task_id}"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger metrics collection: {str(e)}",
        )


@router.post("/collect/system")
async def collect_system_metrics(background_tasks: BackgroundTasks):
    """Trigger collection of system metrics"""
    try:
        background_tasks.add_task(metrics_collector.collect_and_store_system_metrics)
        return {"message": "System metrics collection triggered"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger system metrics collection: {str(e)}",
        )


@router.get("/health")
async def analytics_health_check():
    """Health check for analytics system"""
    try:
        summary = await analytics_engine.get_summary_analytics()

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "analytics_engine": "operational",
                "metrics_collector": "operational",
            },
            "metrics": {
                "total_tasks": summary.total_tasks,
                "system_health": summary.system_health_score,
            },
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }


# Provider Analytics Endpoints (Multi-Provider Support)
@router.get("/providers/dashboard")
async def get_provider_dashboard():
    """Get comprehensive provider analytics dashboard data"""
    if not settings.multi_provider_enabled:
        raise HTTPException(
            status_code=400, detail="Multi-provider system is not enabled"
        )

    try:
        from supervisor_agent.core.multi_provider_service import (
            multi_provider_service,
        )

        # Get provider status and analytics
        provider_status = await multi_provider_service.get_provider_status()
        analytics = await multi_provider_service.get_analytics()

        # Get system health information
        from supervisor_agent.core.enhanced_agent_manager import (
            enhanced_agent_manager,
        )

        system_health = await enhanced_agent_manager.get_system_health()

        dashboard_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overview": {
                "total_providers": provider_status.get("total_providers", 0),
                "healthy_providers": provider_status.get("healthy_providers", 0),
                "unhealthy_providers": provider_status.get("unhealthy_providers", 0),
                "total_tasks_today": analytics.get("total_tasks_today", 0),
                "total_cost_today": analytics.get("total_cost_today", 0.0),
                "average_response_time": analytics.get("average_response_time", 0.0),
                "success_rate": analytics.get("success_rate", 0.0),
            },
            "providers": provider_status.get("providers", {}),
            "usage_analytics": analytics,
            "system_health": system_health,
            "cost_breakdown": analytics.get("cost_breakdown", {}),
            "performance_metrics": analytics.get("performance_metrics", {}),
            "quota_status": provider_status.get("quota_status", {}),
        }

        return dashboard_data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get provider dashboard data: {str(e)}",
        )


@router.get("/providers/{provider_id}/metrics")
async def get_provider_metrics(
    provider_id: str,
    time_range: TimeRange = Query(TimeRange.DAY, description="Time range for metrics"),
    db: Session = Depends(get_db),
):
    """Get detailed metrics for a specific provider"""
    if not settings.multi_provider_enabled:
        raise HTTPException(
            status_code=400, detail="Multi-provider system is not enabled"
        )

    try:
        from supervisor_agent.core.multi_provider_service import (
            multi_provider_service,
        )

        # Get provider-specific metrics
        provider_analytics = await multi_provider_service.get_provider_analytics(
            provider_id
        )

        # Get database metrics for this provider
        # This would require extending the existing metrics system to track provider_id
        # For now, return the service-level analytics

        return {
            "provider_id": provider_id,
            "time_range": time_range.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": provider_analytics,
            "performance": {
                "success_rate": provider_analytics.get("success_rate", 0.0),
                "average_response_time": provider_analytics.get(
                    "average_response_time", 0.0
                ),
                "total_requests": provider_analytics.get("total_requests", 0),
                "failed_requests": provider_analytics.get("failed_requests", 0),
                "cost_today": provider_analytics.get("cost_today", 0.0),
                "tokens_used": provider_analytics.get("tokens_used", 0),
            },
            "health": provider_analytics.get("health_status", {}),
            "quota": provider_analytics.get("quota_status", {}),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get provider metrics: {str(e)}"
        )


@router.get("/providers/cost-optimization")
async def get_cost_optimization_recommendations():
    """Get cost optimization recommendations across providers"""
    if not settings.multi_provider_enabled:
        raise HTTPException(
            status_code=400, detail="Multi-provider system is not enabled"
        )

    try:
        from supervisor_agent.core.multi_provider_subscription_intelligence import (
            subscription_intelligence,
        )

        recommendations = (
            await subscription_intelligence.get_cost_optimization_recommendations()
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recommendations": recommendations,
            "potential_savings": recommendations.get("potential_monthly_savings", 0.0),
            "optimization_opportunities": recommendations.get("opportunities", []),
            "provider_efficiency": recommendations.get("provider_efficiency", {}),
            "usage_patterns": recommendations.get("usage_patterns", {}),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cost optimization recommendations: {str(e)}",
        )


@router.get("/providers/performance-comparison")
async def get_provider_performance_comparison(
    time_range: TimeRange = Query(
        TimeRange.DAY, description="Time range for comparison"
    )
):
    """Compare performance metrics across all providers"""
    if not settings.multi_provider_enabled:
        raise HTTPException(
            status_code=400, detail="Multi-provider system is not enabled"
        )

    try:
        from supervisor_agent.core.multi_provider_service import (
            multi_provider_service,
        )

        provider_status = await multi_provider_service.get_provider_status()

        providers = provider_status.get("providers", {})
        comparison_data = {}

        for provider_id, provider_info in providers.items():
            provider_analytics = await multi_provider_service.get_provider_analytics(
                provider_id
            )

            comparison_data[provider_id] = {
                "name": provider_info.get("name", provider_id),
                "type": provider_info.get("type", "unknown"),
                "health_score": provider_info.get("health_score", 0.0),
                "success_rate": provider_analytics.get("success_rate", 0.0),
                "average_response_time": provider_analytics.get(
                    "average_response_time", 0.0
                ),
                "cost_per_request": provider_analytics.get("cost_per_request", 0.0),
                "total_requests": provider_analytics.get("total_requests", 0),
                "uptime_percentage": provider_analytics.get("uptime_percentage", 0.0),
                "quota_utilization": provider_analytics.get("quota_utilization", 0.0),
            }

        # Calculate rankings
        rankings = {
            "fastest": sorted(
                comparison_data.items(),
                key=lambda x: x[1]["average_response_time"],
            ),
            "most_reliable": sorted(
                comparison_data.items(),
                key=lambda x: x[1]["success_rate"],
                reverse=True,
            ),
            "most_cost_effective": sorted(
                comparison_data.items(), key=lambda x: x[1]["cost_per_request"]
            ),
            "healthiest": sorted(
                comparison_data.items(),
                key=lambda x: x[1]["health_score"],
                reverse=True,
            ),
        }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "time_range": time_range.value,
            "comparison": comparison_data,
            "rankings": rankings,
            "summary": {
                "total_providers": len(comparison_data),
                "average_health_score": (
                    sum(p["health_score"] for p in comparison_data.values())
                    / len(comparison_data)
                    if comparison_data
                    else 0
                ),
                "average_success_rate": (
                    sum(p["success_rate"] for p in comparison_data.values())
                    / len(comparison_data)
                    if comparison_data
                    else 0
                ),
                "total_requests": sum(
                    p["total_requests"] for p in comparison_data.values()
                ),
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get provider performance comparison: {str(e)}",
        )

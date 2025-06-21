"""
Analytics API Routes

RESTful API endpoints for analytics dashboard functionality.
"""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session

from supervisor_agent.db.database import get_db
from supervisor_agent.core.analytics_models import (
    AnalyticsQuery, MetricType, TimeRange, AnalyticsResult, AnalyticsSummary,
    TrendPrediction, Insight, MetricEntry, MetricEntryResponse
)
from supervisor_agent.core.analytics_engine import AnalyticsEngine
from supervisor_agent.core.metrics_collector import MetricsCollector


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
        raise HTTPException(status_code=500, detail=f"Failed to get analytics summary: {str(e)}")


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
    timeframe: TimeRange = Query(TimeRange.DAY, description="Time range for insight analysis")
):
    """Get actionable insights based on recent metrics"""
    try:
        insights = await analytics_engine.generate_insights(timeframe)
        return insights
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate insights: {str(e)}")


@router.get("/trends/{metric_type}", response_model=TrendPrediction)
async def get_trend_prediction(
    metric_type: MetricType,
    prediction_hours: int = Query(24, ge=1, le=168, description="Hours to predict (1-168)")
):
    """Get trend prediction for specified metric type"""
    try:
        prediction = await analytics_engine.predict_trends(metric_type, prediction_hours)
        return prediction
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate trend prediction: {str(e)}")


@router.get("/metrics", response_model=List[MetricEntryResponse])
async def get_recent_metrics(
    metric_type: Optional[MetricType] = Query(None, description="Filter by metric type"),
    limit: int = Query(100, ge=1, le=1000, description="Number of recent metrics to return"),
    db: Session = Depends(get_db)
):
    """Get recent raw metric entries"""
    try:
        query = db.query(MetricEntry)
        
        if metric_type:
            query = query.filter(MetricEntry.metric_type == metric_type.value)
        
        metrics = query.order_by(MetricEntry.timestamp.desc()).limit(limit).all()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")


@router.post("/collect/task/{task_id}")
async def collect_task_metrics(
    task_id: int,
    background_tasks: BackgroundTasks
):
    """Trigger collection of metrics for a specific task"""
    try:
        background_tasks.add_task(metrics_collector.collect_and_store_task_metrics, task_id)
        return {"message": f"Metrics collection triggered for task {task_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger metrics collection: {str(e)}")


@router.post("/collect/system")
async def collect_system_metrics(background_tasks: BackgroundTasks):
    """Trigger collection of system metrics"""
    try:
        background_tasks.add_task(metrics_collector.collect_and_store_system_metrics)
        return {"message": "System metrics collection triggered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger system metrics collection: {str(e)}")


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
                "metrics_collector": "operational"
            },
            "metrics": {
                "total_tasks": summary.total_tasks,
                "system_health": summary.system_health_score
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }
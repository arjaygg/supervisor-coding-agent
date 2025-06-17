"""
Analytics and cost tracking API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
from supervisor_agent.db.database import get_db
from supervisor_agent.db import schemas, crud
from supervisor_agent.core.cost_tracker import cost_tracker
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/analytics/costs", response_model=schemas.CostSummaryResponse)
async def get_cost_summary(
    start_date: Optional[datetime] = Query(
        None, description="Start date for cost analysis"
    ),
    end_date: Optional[datetime] = Query(
        None, description="End date for cost analysis"
    ),
    days: Optional[int] = Query(
        30, description="Number of days to analyze (if start_date not provided)"
    ),
    db: Session = Depends(get_db),
):
    """Get cost summary and breakdown"""
    try:
        # Set default date range if not provided
        if not start_date:
            end_date = end_date or datetime.utcnow()
            start_date = end_date - timedelta(days=days)
        elif not end_date:
            end_date = datetime.utcnow()

        cost_summary = cost_tracker.get_cost_summary(db, start_date, end_date)
        return cost_summary

    except Exception as e:
        logger.error(f"Failed to get cost summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/analytics/costs/entries", response_model=List[schemas.CostTrackingEntryResponse]
)
async def get_cost_entries(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    task_id: Optional[int] = Query(None, description="Filter by task ID"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    db: Session = Depends(get_db),
):
    """Get individual cost tracking entries"""
    try:
        entries = crud.CostTrackingCRUD.get_cost_entries(
            db, skip=skip, limit=limit, task_id=task_id, agent_id=agent_id
        )
        return [
            schemas.CostTrackingEntryResponse.model_validate(entry) for entry in entries
        ]

    except Exception as e:
        logger.error(f"Failed to get cost entries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/analytics/usage/metrics", response_model=List[schemas.UsageMetricsResponse]
)
async def get_usage_metrics(
    metric_type: Optional[str] = Query(
        None, description="Filter by metric type (daily, hourly, agent)"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get usage metrics"""
    try:
        metrics = crud.UsageMetricsCRUD.get_metrics(
            db, metric_type=metric_type, skip=skip, limit=limit
        )
        return [
            schemas.UsageMetricsResponse.model_validate(metric) for metric in metrics
        ]

    except Exception as e:
        logger.error(f"Failed to get usage metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/usage/trends")
async def get_usage_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    metric_type: str = Query("daily", description="Metric type (daily, hourly)"),
    db: Session = Depends(get_db),
):
    """Get usage trends over time"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get metrics for the time period
        metrics = crud.UsageMetricsCRUD.get_metrics(
            db, metric_type=metric_type, limit=days * 2
        )

        # Filter by date range and organize data
        trends = {
            "requests": [],
            "tokens": [],
            "costs": [],
            "response_times": [],
            "success_rates": [],
        }

        for metric in metrics:
            # Parse date from metric_key
            try:
                if metric_type == "daily":
                    metric_date = datetime.strptime(metric.metric_key, "%Y-%m-%d")
                elif metric_type == "hourly":
                    metric_date = datetime.strptime(metric.metric_key, "%Y-%m-%d-%H")
                else:
                    continue

                if start_date <= metric_date <= end_date:
                    trends["requests"].append(
                        {"date": metric.metric_key, "value": metric.total_requests}
                    )
                    trends["tokens"].append(
                        {"date": metric.metric_key, "value": metric.total_tokens}
                    )
                    trends["costs"].append(
                        {
                            "date": metric.metric_key,
                            "value": float(metric.total_cost_usd),
                        }
                    )
                    trends["response_times"].append(
                        {
                            "date": metric.metric_key,
                            "value": metric.avg_response_time_ms,
                        }
                    )
                    trends["success_rates"].append(
                        {"date": metric.metric_key, "value": float(metric.success_rate)}
                    )

            except ValueError:
                # Skip metrics with invalid date formats
                continue

        # Sort by date
        for trend_type in trends:
            trends[trend_type].sort(key=lambda x: x["date"])

        return {
            "period": f"{days} days",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "trends": trends,
        }

    except Exception as e:
        logger.error(f"Failed to get usage trends: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/agents/performance")
async def get_agent_performance(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
):
    """Get agent performance analytics"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get agent metrics
        agent_metrics = crud.UsageMetricsCRUD.get_metrics(
            db, metric_type="agent", limit=1000
        )

        # Calculate performance data
        agent_performance = []

        for metric in agent_metrics:
            agent_id = metric.metric_key

            # Get cost data for this agent
            cost_entries = crud.CostTrackingCRUD.get_cost_entries(
                db, agent_id=agent_id, limit=10000
            )

            # Filter by date range
            recent_entries = [
                entry
                for entry in cost_entries
                if start_date <= entry.timestamp <= end_date
            ]

            if recent_entries:
                total_cost = sum(
                    float(entry.estimated_cost_usd) for entry in recent_entries
                )
                total_tokens = sum(entry.total_tokens for entry in recent_entries)
                avg_response_time = sum(
                    entry.execution_time_ms for entry in recent_entries
                ) / len(recent_entries)

                # Calculate efficiency metrics
                cost_per_token = total_cost / total_tokens if total_tokens > 0 else 0
                tokens_per_request = (
                    total_tokens / len(recent_entries) if recent_entries else 0
                )

                agent_performance.append(
                    {
                        "agent_id": agent_id,
                        "total_requests": len(recent_entries),
                        "total_tokens": total_tokens,
                        "total_cost_usd": f"{total_cost:.4f}",
                        "avg_response_time_ms": int(avg_response_time),
                        "success_rate": float(metric.success_rate),
                        "cost_per_token": f"{cost_per_token:.6f}",
                        "tokens_per_request": tokens_per_request,
                        "efficiency_score": float(metric.success_rate)
                        / (cost_per_token * 1000 + 1),  # Higher is better
                    }
                )

        # Sort by efficiency score
        agent_performance.sort(key=lambda x: x["efficiency_score"], reverse=True)

        return {
            "period": f"{days} days",
            "agents": agent_performance,
            "summary": {
                "total_agents": len(agent_performance),
                "total_requests": sum(a["total_requests"] for a in agent_performance),
                "total_cost": sum(
                    float(a["total_cost_usd"]) for a in agent_performance
                ),
                "avg_success_rate": (
                    sum(a["success_rate"] for a in agent_performance)
                    / len(agent_performance)
                    if agent_performance
                    else 0
                ),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get agent performance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/costs/optimization")
async def get_cost_optimization_insights(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
):
    """Get cost optimization insights and recommendations"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get cost entries for analysis
        cost_entries = crud.CostTrackingCRUD.get_cost_entries(db, limit=10000)
        recent_entries = [
            entry for entry in cost_entries if start_date <= entry.timestamp <= end_date
        ]

        if not recent_entries:
            return {
                "period": f"{days} days",
                "insights": [],
                "recommendations": ["No data available for the selected period"],
            }

        insights = []
        recommendations = []

        # Analyze cost patterns
        total_cost = sum(float(entry.estimated_cost_usd) for entry in recent_entries)
        avg_cost_per_request = total_cost / len(recent_entries)

        # Find expensive requests
        expensive_threshold = avg_cost_per_request * 2
        expensive_requests = [
            e
            for e in recent_entries
            if float(e.estimated_cost_usd) > expensive_threshold
        ]

        if expensive_requests:
            insights.append(
                {
                    "type": "expensive_requests",
                    "description": f"Found {len(expensive_requests)} requests costing above ${expensive_threshold:.4f}",
                    "impact": f"${sum(float(e.estimated_cost_usd) for e in expensive_requests):.4f} ({len(expensive_requests)/len(recent_entries)*100:.1f}% of requests)",
                }
            )
            recommendations.append(
                "Review high-cost requests for optimization opportunities"
            )

        # Analyze token efficiency
        token_costs = [
            (e.total_tokens, float(e.estimated_cost_usd)) for e in recent_entries
        ]
        if token_costs:
            avg_cost_per_token = sum(cost for _, cost in token_costs) / sum(
                tokens for tokens, _ in token_costs
            )

            # Find inefficient requests (high cost per token)
            inefficient_threshold = avg_cost_per_token * 1.5
            inefficient_requests = [
                e
                for e in recent_entries
                if e.total_tokens > 0
                and (float(e.estimated_cost_usd) / e.total_tokens)
                > inefficient_threshold
            ]

            if inefficient_requests:
                insights.append(
                    {
                        "type": "token_efficiency",
                        "description": f"Found {len(inefficient_requests)} requests with poor token efficiency",
                        "impact": f"Average cost per token: ${avg_cost_per_token:.6f}",
                    }
                )
                recommendations.append("Optimize prompts to reduce token usage")

        # Analyze model usage
        model_usage = {}
        for entry in recent_entries:
            model = entry.model_used or "unknown"
            if model not in model_usage:
                model_usage[model] = {"count": 0, "cost": 0.0}
            model_usage[model]["count"] += 1
            model_usage[model]["cost"] += float(entry.estimated_cost_usd)

        # Find if expensive models are being overused
        if len(model_usage) > 1:
            most_expensive_model = max(model_usage.items(), key=lambda x: x[1]["cost"])
            if (
                most_expensive_model[1]["cost"] / total_cost > 0.6
            ):  # More than 60% of cost
                insights.append(
                    {
                        "type": "model_usage",
                        "description": f"Model '{most_expensive_model[0]}' accounts for {most_expensive_model[1]['cost']/total_cost*100:.1f}% of costs",
                        "impact": f"${most_expensive_model[1]['cost']:.4f}",
                    }
                )
                recommendations.append(
                    "Consider using more cost-effective models for simpler tasks"
                )

        # Analyze timing patterns
        hour_costs = {}
        for entry in recent_entries:
            hour = entry.timestamp.hour
            if hour not in hour_costs:
                hour_costs[hour] = 0
            hour_costs[hour] += float(entry.estimated_cost_usd)

        if hour_costs:
            peak_hour = max(hour_costs.items(), key=lambda x: x[1])
            if peak_hour[1] / total_cost > 0.2:  # More than 20% in single hour
                insights.append(
                    {
                        "type": "usage_timing",
                        "description": f"Peak usage at hour {peak_hour[0]} accounts for {peak_hour[1]/total_cost*100:.1f}% of costs",
                        "impact": f"${peak_hour[1]:.4f}",
                    }
                )
                recommendations.append(
                    "Consider load balancing across different time periods"
                )

        return {
            "period": f"{days} days",
            "total_cost": f"${total_cost:.4f}",
            "total_requests": len(recent_entries),
            "avg_cost_per_request": f"${avg_cost_per_request:.4f}",
            "insights": insights,
            "recommendations": recommendations,
        }

    except Exception as e:
        logger.error(f"Failed to get cost optimization insights: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analytics/costs/estimate")
async def estimate_task_cost(
    task_type: str,
    prompt_text: str,
    expected_response_length: Optional[int] = Query(
        None, description="Expected response length in characters"
    ),
    model: Optional[str] = Query(
        "claude-3-5-sonnet-20241022", description="Model to use for estimation"
    ),
):
    """Estimate cost for a potential task"""
    try:
        from supervisor_agent.core.cost_tracker import TokenEstimator

        # Estimate prompt tokens
        prompt_tokens = TokenEstimator.estimate_tokens(prompt_text)

        # Estimate completion tokens
        if expected_response_length:
            completion_tokens = TokenEstimator.estimate_tokens(
                "x" * expected_response_length
            )
        else:
            # Use default estimation based on task type
            completion_estimates = {
                "PR_REVIEW": 500,
                "ISSUE_SUMMARY": 300,
                "CODE_ANALYSIS": 400,
                "REFACTOR": 600,
                "BUG_FIX": 400,
                "FEATURE": 800,
            }
            completion_tokens = completion_estimates.get(task_type, 400)

        # Calculate estimated cost
        estimated_cost = TokenEstimator.estimate_cost(
            prompt_tokens, completion_tokens, model
        )

        return {
            "task_type": task_type,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "estimated_completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "estimated_cost_usd": estimated_cost,
            "estimated_execution_time_ms": 5000
            + (prompt_tokens + completion_tokens) * 2,  # Rough estimate
        }

    except Exception as e:
        logger.error(f"Failed to estimate task cost: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

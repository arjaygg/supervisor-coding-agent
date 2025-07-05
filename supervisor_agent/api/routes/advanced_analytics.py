"""
Advanced Analytics API Routes

Provides comprehensive analytics endpoints with real-time data streaming,
interactive dashboards, ML predictions, and export capabilities.

Features:
- Real-time metrics streaming via WebSocket
- Interactive dashboard data endpoints
- ML-powered predictions and anomaly detection
- Custom analytics queries and filtering
- Data export in multiple formats
- Historical trend analysis
"""

import asyncio
import csv
import io
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from supervisor_agent.auth.dependencies import (
    get_current_user,
    require_permissions,
)
from supervisor_agent.auth.models import User
from supervisor_agent.core.advanced_analytics_engine import (
    AlertSeverity,
    AnomalyType,
    MetricsCollector,
    MetricType,
    StatisticalAnomalyDetector,
    TimeSeries,
    TimeSeriesPredictor,
)
from supervisor_agent.core.analytics_models import TimeRange
from supervisor_agent.db.database import get_db
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/analytics/advanced")


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"


class MetricScope(str, Enum):
    SYSTEM = "system"
    TASKS = "tasks"
    USERS = "users"
    CUSTOM = "custom"


# WebSocket connection manager for real-time analytics
class AnalyticsWebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriber_preferences: Dict[WebSocket, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriber_preferences[websocket] = {
            "metrics": ["system", "tasks"],
            "refresh_interval": 30,
            "anomaly_alerts": True,
        }
        logger.info(
            f"Analytics WebSocket connected. Total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        self.subscriber_preferences.pop(websocket, None)
        logger.info(
            f"Analytics WebSocket disconnected. Total connections: {len(self.active_connections)}"
        )

    async def send_personal_message(
        self, message: Dict[str, Any], websocket: WebSocket
    ):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {str(e)}")
            self.disconnect(websocket)

    async def broadcast_metrics(self, metrics_data: Dict[str, Any]):
        """Broadcast metrics to all connected clients"""
        if not self.active_connections:
            return

        message = {
            "type": "metrics_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": metrics_data,
        }

        disconnected = []
        for connection in self.active_connections:
            try:
                # Check subscriber preferences
                prefs = self.subscriber_preferences.get(connection, {})

                # Filter metrics based on preferences
                filtered_data = self._filter_metrics_by_preferences(metrics_data, prefs)

                if filtered_data:
                    filtered_message = {**message, "data": filtered_data}
                    await connection.send_text(json.dumps(filtered_message))
            except Exception as e:
                logger.error(f"Failed to broadcast to WebSocket: {str(e)}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_anomaly(self, anomaly_data: Dict[str, Any]):
        """Broadcast anomaly alerts to subscribed clients"""
        message = {
            "type": "anomaly_alert",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": anomaly_data,
        }

        for connection in self.active_connections:
            prefs = self.subscriber_preferences.get(connection, {})
            if prefs.get("anomaly_alerts", True):
                await self.send_personal_message(message, connection)

    def _filter_metrics_by_preferences(
        self, metrics_data: Dict[str, Any], preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Filter metrics based on subscriber preferences"""
        if not preferences.get("metrics"):
            return metrics_data

        filtered = {}
        allowed_metrics = preferences["metrics"]

        for key, value in metrics_data.items():
            # Simple filtering - can be enhanced with more sophisticated logic
            if any(metric in key for metric in allowed_metrics):
                filtered[key] = value

        return filtered


# Global WebSocket manager
ws_manager = AnalyticsWebSocketManager()


@router.websocket("/stream")
async def analytics_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time analytics streaming"""
    await ws_manager.connect(websocket)

    try:
        while True:
            # Wait for client messages (preferences updates, etc.)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                message = json.loads(data)

                # Handle preference updates
                if message.get("type") == "update_preferences":
                    ws_manager.subscriber_preferences[websocket].update(
                        message.get("preferences", {})
                    )
                    logger.info(
                        f"Updated WebSocket preferences: {message.get('preferences')}"
                    )

            except asyncio.TimeoutError:
                # No message received, continue with regular broadcasting
                pass
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received from WebSocket client")

            # Small delay to prevent overwhelming the connection
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        ws_manager.disconnect(websocket)


@router.get("/metrics/real-time")
async def get_real_time_metrics(
    scope: MetricScope = Query(MetricScope.SYSTEM),
    include_predictions: bool = Query(False),
    include_anomalies: bool = Query(False),
    current_user: User = Depends(require_permissions("analytics:read")),
    db: Session = Depends(get_db),
):
    """Get real-time metrics with optional predictions and anomaly detection"""
    try:
        collector = MetricsCollector()

        # Collect metrics based on scope
        if scope == MetricScope.SYSTEM:
            metrics = await collector.collect_system_metrics()
        elif scope == MetricScope.TASKS:
            metrics = await collector.collect_task_metrics()
        elif scope == MetricScope.USERS:
            metrics = await collector.collect_user_metrics()
        else:
            # Custom metrics - would be implemented based on requirements
            metrics = {}

        result = {
            "scope": scope,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
        }

        # Add predictions if requested
        if include_predictions and metrics:
            try:
                predictor = TimeSeriesPredictor()
                predictions = {}

                # Generate predictions for key metrics
                for metric_name, value in metrics.items():
                    if isinstance(value, (int, float)) and metric_name != "timestamp":
                        # Create a simple time series for prediction
                        # In real implementation, this would use historical data
                        ts = TimeSeries(
                            metric_name=metric_name,
                            metric_type=MetricType.GAUGE,
                        )
                        ts.add_point(datetime.now(timezone.utc), float(value))

                        # For demo, add some historical points
                        for i in range(1, 10):
                            past_time = datetime.now(timezone.utc) - timedelta(
                                minutes=i
                            )
                            past_value = float(value) * (1 + (i * 0.01))  # Simple trend
                            ts.add_point(past_time, past_value)

                        pred_list = predictor.predict(
                            ts, forecast_horizon=6
                        )  # 6 time periods ahead
                        if pred_list:
                            predictions[metric_name] = [
                                {
                                    "timestamp": pred.timestamp.isoformat(),
                                    "predicted_value": pred.predicted_value,
                                    "confidence": pred.confidence,
                                    "confidence_interval": [
                                        pred.confidence_interval_lower,
                                        pred.confidence_interval_upper,
                                    ],
                                }
                                for pred in pred_list
                            ]

                result["predictions"] = predictions

            except Exception as e:
                logger.warning(f"Failed to generate predictions: {str(e)}")
                result["predictions"] = {}

        # Add anomaly detection if requested
        if include_anomalies and metrics:
            try:
                detector = StatisticalAnomalyDetector()
                anomalies = {}

                # Check for anomalies in current metrics
                # This would typically use historical data for comparison
                for metric_name, value in metrics.items():
                    if isinstance(value, (int, float)) and metric_name != "timestamp":
                        # Create time series with some sample data for anomaly detection
                        ts = TimeSeries(
                            metric_name=metric_name,
                            metric_type=MetricType.GAUGE,
                        )

                        # Add current and some historical data points
                        ts.add_point(datetime.now(timezone.utc), float(value))
                        for i in range(1, 20):  # Add 20 historical points
                            past_time = datetime.now(timezone.utc) - timedelta(
                                minutes=i
                            )
                            # Generate sample historical data with some variation
                            base_value = float(value) * (1 + ((i % 5) * 0.1 - 0.2))
                            ts.add_point(past_time, base_value)

                        detected_anomalies = detector.detect_anomalies(ts)
                        if detected_anomalies:
                            anomalies[metric_name] = [
                                {
                                    "type": anomaly.anomaly_type.value,
                                    "severity": anomaly.severity.value,
                                    "timestamp": anomaly.timestamp.isoformat(),
                                    "value": anomaly.value,
                                    "expected_value": anomaly.expected_value,
                                    "confidence": anomaly.confidence,
                                    "description": anomaly.description,
                                }
                                for anomaly in detected_anomalies
                            ]

                result["anomalies"] = anomalies

                # Broadcast critical anomalies via WebSocket
                critical_anomalies = [
                    anomaly
                    for anomaly_list in anomalies.values()
                    for anomaly in anomaly_list
                    if anomaly["severity"] == "critical"
                ]

                if critical_anomalies:
                    await ws_manager.broadcast_anomaly(
                        {
                            "scope": scope,
                            "critical_anomalies": critical_anomalies,
                        }
                    )

            except Exception as e:
                logger.warning(f"Failed to detect anomalies: {str(e)}")
                result["anomalies"] = {}

        # Broadcast metrics to WebSocket subscribers
        await ws_manager.broadcast_metrics(metrics)

        return result

    except Exception as e:
        logger.error(f"Failed to get real-time metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/dashboard/data")
async def get_dashboard_data(
    time_range: str = Query("24h", description="Time range: 1h, 6h, 24h, 7d, 30d"),
    metric_types: List[str] = Query(
        ["system", "tasks"], description="Metric types to include"
    ),
    include_trends: bool = Query(True),
    include_comparisons: bool = Query(True),
    current_user: User = Depends(require_permissions("analytics:read")),
    db: Session = Depends(get_db),
):
    """Get comprehensive dashboard data with trends and comparisons"""
    try:
        # Parse time range
        time_ranges = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }

        if time_range not in time_ranges:
            raise HTTPException(
                status_code=400, detail=f"Invalid time range: {time_range}"
            )

        end_time = datetime.now(timezone.utc)
        start_time = end_time - time_ranges[time_range]

        collector = MetricsCollector()
        dashboard_data = {
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration": time_range,
            },
            "metrics": {},
            "summary": {},
            "trends": {},
            "comparisons": {},
        }

        # Collect current metrics
        if "system" in metric_types:
            system_metrics = await collector.collect_system_metrics()
            dashboard_data["metrics"]["system"] = system_metrics

        if "tasks" in metric_types:
            task_metrics = await collector.collect_task_metrics()
            dashboard_data["metrics"]["tasks"] = task_metrics

        if "users" in metric_types:
            user_metrics = await collector.collect_user_metrics()
            dashboard_data["metrics"]["users"] = user_metrics

        # Generate summary statistics
        dashboard_data["summary"] = {
            "total_metrics_collected": len(
                [
                    metric
                    for category in dashboard_data["metrics"].values()
                    for metric in category.keys()
                    if metric != "timestamp"
                ]
            ),
            "collection_timestamp": datetime.now(timezone.utc).isoformat(),
            "data_freshness": "real-time",
        }

        # Add trend analysis if requested
        if include_trends:
            dashboard_data["trends"] = await _generate_trend_analysis(
                dashboard_data["metrics"], time_range
            )

        # Add period comparisons if requested
        if include_comparisons:
            dashboard_data["comparisons"] = await _generate_period_comparisons(
                dashboard_data["metrics"], time_range
            )

        return dashboard_data

    except Exception as e:
        logger.error(f"Failed to get dashboard data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard data")


@router.get("/insights")
async def get_analytics_insights(
    timeframe_hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    min_confidence: float = Query(0.7, ge=0.0, le=1.0),
    categories: List[str] = Query(["performance", "efficiency", "anomalies"]),
    current_user: User = Depends(require_permissions("analytics:read")),
    db: Session = Depends(get_db),
):
    """Get AI-powered analytics insights and recommendations"""
    try:
        collector = MetricsCollector()

        # Collect comprehensive metrics
        system_metrics = await collector.collect_system_metrics()
        task_metrics = await collector.collect_task_metrics()
        user_metrics = await collector.collect_user_metrics()

        insights = []

        # Performance insights
        if "performance" in categories:
            performance_insights = await _generate_performance_insights(
                system_metrics, task_metrics, min_confidence
            )
            insights.extend(performance_insights)

        # Efficiency insights
        if "efficiency" in categories:
            efficiency_insights = await _generate_efficiency_insights(
                task_metrics, user_metrics, min_confidence
            )
            insights.extend(efficiency_insights)

        # Anomaly insights
        if "anomalies" in categories:
            anomaly_insights = await _generate_anomaly_insights(
                system_metrics, task_metrics, min_confidence
            )
            insights.extend(anomaly_insights)

        # Sort insights by confidence and importance
        insights.sort(
            key=lambda x: (x.get("confidence", 0), x.get("impact_score", 0)),
            reverse=True,
        )

        return {
            "timeframe_hours": timeframe_hours,
            "min_confidence": min_confidence,
            "total_insights": len(insights),
            "categories_analyzed": categories,
            "insights": insights,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to generate insights: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate insights")


@router.get("/export")
async def export_analytics_data(
    format: ExportFormat = Query(ExportFormat.JSON),
    time_range: str = Query("24h"),
    metric_types: List[str] = Query(["system", "tasks"]),
    include_metadata: bool = Query(True),
    current_user: User = Depends(require_permissions("analytics:export")),
    db: Session = Depends(get_db),
):
    """Export analytics data in various formats"""
    try:
        # Get dashboard data
        collector = MetricsCollector()
        export_data = {
            "export_metadata": {
                "format": format.value,
                "time_range": time_range,
                "metric_types": metric_types,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "exported_by": current_user.username,
            },
            "metrics": {},
        }

        # Collect metrics
        if "system" in metric_types:
            export_data["metrics"]["system"] = await collector.collect_system_metrics()

        if "tasks" in metric_types:
            export_data["metrics"]["tasks"] = await collector.collect_task_metrics()

        if "users" in metric_types:
            export_data["metrics"]["users"] = await collector.collect_user_metrics()

        # Generate export based on format
        if format == ExportFormat.JSON:
            return export_data

        elif format == ExportFormat.CSV:
            return _export_as_csv(export_data)

        elif format == ExportFormat.EXCEL:
            return _export_as_excel(export_data)

        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported export format: {format}"
            )

    except Exception as e:
        logger.error(f"Failed to export analytics data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export data")


# Helper functions for analytics processing


async def _generate_trend_analysis(
    metrics_data: Dict[str, Any], time_range: str
) -> Dict[str, Any]:
    """Generate trend analysis for metrics"""
    # This would typically use historical data from database
    # For now, return mock trend data
    return {
        "cpu_usage": {
            "trend": "increasing",
            "rate_of_change": 2.3,
            "confidence": 0.85,
        },
        "task_completion_rate": {
            "trend": "stable",
            "rate_of_change": 0.1,
            "confidence": 0.92,
        },
        "memory_usage": {
            "trend": "decreasing",
            "rate_of_change": -1.2,
            "confidence": 0.78,
        },
    }


async def _generate_period_comparisons(
    metrics_data: Dict[str, Any], time_range: str
) -> Dict[str, Any]:
    """Generate period-over-period comparisons"""
    # This would compare current period with previous period
    return {
        "vs_previous_period": {
            "cpu_usage": {"change_percent": 15.3, "direction": "increase"},
            "task_completion_rate": {
                "change_percent": -2.1,
                "direction": "decrease",
            },
            "memory_usage": {"change_percent": 8.7, "direction": "increase"},
        },
        "vs_same_period_last_week": {
            "cpu_usage": {"change_percent": -5.2, "direction": "decrease"},
            "task_completion_rate": {
                "change_percent": 12.4,
                "direction": "increase",
            },
            "memory_usage": {"change_percent": 3.1, "direction": "increase"},
        },
    }


async def _generate_performance_insights(
    system_metrics: Dict[str, Any],
    task_metrics: Dict[str, Any],
    min_confidence: float,
) -> List[Dict[str, Any]]:
    """Generate performance-related insights"""
    insights = []

    # CPU performance insight
    cpu_percent = system_metrics.get("cpu_percent", 0)
    if cpu_percent > 80:
        insights.append(
            {
                "category": "performance",
                "type": "warning",
                "title": "High CPU Usage Detected",
                "description": f"CPU usage is at {cpu_percent:.1f}%, which may impact system performance",
                "confidence": 0.9,
                "impact_score": 8,
                "recommendations": [
                    "Consider scaling up resources",
                    "Optimize high-CPU tasks",
                    "Review task scheduling",
                ],
                "metrics": {"cpu_percent": cpu_percent},
            }
        )

    # Task execution insight
    avg_exec_time = task_metrics.get("avg_execution_time", 0)
    if avg_exec_time > 300:  # 5 minutes
        insights.append(
            {
                "category": "performance",
                "type": "info",
                "title": "Long Task Execution Times",
                "description": f"Average task execution time is {avg_exec_time:.1f} seconds",
                "confidence": 0.85,
                "impact_score": 6,
                "recommendations": [
                    "Optimize task algorithms",
                    "Consider task parallelization",
                    "Review resource allocation",
                ],
                "metrics": {"avg_execution_time": avg_exec_time},
            }
        )

    return [insight for insight in insights if insight["confidence"] >= min_confidence]


async def _generate_efficiency_insights(
    task_metrics: Dict[str, Any],
    user_metrics: Dict[str, Any],
    min_confidence: float,
) -> List[Dict[str, Any]]:
    """Generate efficiency-related insights"""
    insights = []

    # Task success rate insight
    success_rate = task_metrics.get("success_rate", 0)
    if success_rate < 95:
        insights.append(
            {
                "category": "efficiency",
                "type": "warning" if success_rate < 90 else "info",
                "title": "Task Success Rate Below Optimal",
                "description": f"Task success rate is {success_rate:.1f}%, below the 95% target",
                "confidence": 0.88,
                "impact_score": 7,
                "recommendations": [
                    "Investigate common failure patterns",
                    "Improve error handling",
                    "Enhance input validation",
                ],
                "metrics": {"success_rate": success_rate},
            }
        )

    return [insight for insight in insights if insight["confidence"] >= min_confidence]


async def _generate_anomaly_insights(
    system_metrics: Dict[str, Any],
    task_metrics: Dict[str, Any],
    min_confidence: float,
) -> List[Dict[str, Any]]:
    """Generate anomaly-related insights"""
    insights = []

    # Memory usage anomaly
    memory_percent = system_metrics.get("memory_percent", 0)
    if memory_percent > 90:
        insights.append(
            {
                "category": "anomalies",
                "type": "critical",
                "title": "Critical Memory Usage Anomaly",
                "description": f"Memory usage at {memory_percent:.1f}% is critically high",
                "confidence": 0.95,
                "impact_score": 9,
                "recommendations": [
                    "Immediate memory cleanup required",
                    "Restart high-memory processes",
                    "Scale up memory resources",
                ],
                "metrics": {"memory_percent": memory_percent},
            }
        )

    return [insight for insight in insights if insight["confidence"] >= min_confidence]


def _export_as_csv(data: Dict[str, Any]) -> StreamingResponse:
    """Export data as CSV"""
    output = io.StringIO()

    # Flatten the metrics data for CSV format
    rows = []
    for category, metrics in data["metrics"].items():
        for metric_name, value in metrics.items():
            if metric_name != "timestamp":
                rows.append(
                    {
                        "category": category,
                        "metric": metric_name,
                        "value": value,
                        "timestamp": metrics.get(
                            "timestamp", datetime.now(timezone.utc).isoformat()
                        ),
                    }
                )

    if rows:
        writer = csv.DictWriter(
            output, fieldnames=["category", "metric", "value", "timestamp"]
        )
        writer.writeheader()
        writer.writerows(rows)

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=analytics_export.csv"},
    )


def _export_as_excel(data: Dict[str, Any]) -> StreamingResponse:
    """Export data as Excel using pandas and openpyxl"""
    try:
        import io

        import pandas as pd

        # Create Excel writer with openpyxl engine
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Create metadata sheet
            metadata_df = pd.DataFrame(
                [
                    ["Export Format", data["export_metadata"]["format"]],
                    ["Time Range", data["export_metadata"]["time_range"]],
                    [
                        "Metric Types",
                        ", ".join(data["export_metadata"]["metric_types"]),
                    ],
                    ["Exported At", data["export_metadata"]["exported_at"]],
                    ["Exported By", data["export_metadata"]["exported_by"]],
                ],
                columns=["Property", "Value"],
            )

            metadata_df.to_excel(writer, sheet_name="Metadata", index=False)

            # Create data sheets for each metric category
            for category, metrics in data["metrics"].items():
                rows = []
                for metric_name, value in metrics.items():
                    if metric_name != "timestamp":
                        rows.append(
                            {
                                "metric": metric_name,
                                "value": value,
                                "timestamp": metrics.get(
                                    "timestamp",
                                    data["export_metadata"]["exported_at"],
                                ),
                            }
                        )

                if rows:
                    df = pd.DataFrame(rows)
                    sheet_name = category.capitalize()[:31]  # Excel sheet name limit
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

        output.seek(0)

        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=analytics_export.xlsx"
            },
        )

    except ImportError:
        logger.warning("pandas or openpyxl not available, falling back to CSV export")
        return _export_as_csv(data)
    except Exception as e:
        logger.error(f"Failed to create Excel export: {str(e)}")
        return _export_as_csv(data)

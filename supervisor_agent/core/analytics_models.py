"""
Analytics Models

Data models for metrics collection, analytics processing, and dashboard configuration.
Follows SOLID principles with clear separation of concerns.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from supervisor_agent.db.database import Base


class MetricType(str, Enum):
    """Types of metrics that can be collected"""

    TASK_EXECUTION = "task_execution"
    SYSTEM_PERFORMANCE = "system_performance"
    USER_ACTIVITY = "user_activity"
    WORKFLOW_PERFORMANCE = "workflow_performance"
    COST_TRACKING = "cost_tracking"
    ERROR_RATE = "error_rate"


class TimeRange(str, Enum):
    """Time range options for analytics queries"""

    HOUR = "1h"
    DAY = "24h"
    WEEK = "7d"
    MONTH = "30d"
    QUARTER = "90d"
    YEAR = "365d"


class AggregationType(str, Enum):
    """Types of data aggregation"""

    SUM = "sum"
    AVERAGE = "average"
    COUNT = "count"
    MIN = "min"
    MAX = "max"
    PERCENTILE_95 = "p95"
    PERCENTILE_99 = "p99"


class ChartType(str, Enum):
    """Dashboard chart types"""

    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    AREA = "area"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    TABLE = "table"
    GAUGE = "gauge"


class ExportFormat(str, Enum):
    """Data export formats"""

    CSV = "csv"
    JSON = "json"
    PDF = "pdf"
    EXCEL = "excel"


# Pydantic Models for API


class MetricPoint(BaseModel):
    """Individual metric data point"""

    timestamp: datetime
    value: Union[float, int, str]
    labels: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskMetrics(BaseModel):
    """Metrics specific to task execution"""

    task_id: int
    task_type: str
    execution_time_ms: int
    success: bool
    queue_time_ms: int
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    error_message: Optional[str] = None
    cost_usd: Optional[str] = None


class SystemMetrics(BaseModel):
    """System-wide performance metrics"""

    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    active_tasks_count: int
    queue_depth: int
    response_time_ms: float


class UserMetrics(BaseModel):
    """User activity metrics"""

    user_id: str
    session_duration_ms: int
    actions_count: int
    features_used: List[str]
    last_activity: datetime


class WorkflowMetrics(BaseModel):
    """Workflow execution metrics"""

    workflow_id: str
    workflow_name: str
    total_execution_time_ms: int
    tasks_count: int
    success_rate: float
    parallel_efficiency: float
    resource_utilization: Dict[str, float]


class AnalyticsQuery(BaseModel):
    """Query configuration for analytics data"""

    metric_type: MetricType
    time_range: TimeRange
    aggregation: AggregationType
    filters: Dict[str, Any] = Field(default_factory=dict)
    group_by: List[str] = Field(default_factory=list)
    limit: Optional[int] = None


class ChartConfig(BaseModel):
    """Configuration for dashboard charts"""

    chart_id: str
    title: str
    chart_type: ChartType
    query: AnalyticsQuery
    refresh_interval_seconds: int = Field(default=30)
    height: int = Field(default=400)
    width: int = Field(default=600)
    options: Dict[str, Any] = Field(default_factory=dict)


class DashboardConfig(BaseModel):
    """Dashboard configuration"""

    dashboard_id: str
    name: str
    description: Optional[str] = None
    charts: List[ChartConfig]
    layout: Dict[str, Any] = Field(default_factory=dict)
    auto_refresh: bool = Field(default=True)
    is_public: bool = Field(default=False)


class AnalyticsResult(BaseModel):
    """Result of analytics processing"""

    query: AnalyticsQuery
    data: List[MetricPoint]
    total_points: int
    processing_time_ms: int
    cache_hit: bool = Field(default=False)


class TrendPrediction(BaseModel):
    """Trend prediction result"""

    metric_type: MetricType
    predicted_values: List[MetricPoint]
    confidence_score: float
    trend_direction: str  # "increasing", "decreasing", "stable"
    model_used: str
    prediction_accuracy: Optional[float] = None


class Insight(BaseModel):
    """Analytics insight"""

    title: str
    description: str
    severity: str  # "info", "warning", "critical"
    metric_type: MetricType
    value: Union[float, int, str]
    threshold: Optional[Union[float, int]] = None
    recommendation: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# SQLAlchemy Database Models


class MetricEntry(Base):
    """Database model for metric storage"""

    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    metric_type = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    value = Column(Float, nullable=False)
    string_value = Column(String, nullable=True)  # For non-numeric values
    labels = Column(JSON, nullable=False, default=dict)
    metric_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes for efficient querying
    __table_args__ = {"extend_existing": True, "mysql_engine": "InnoDB"}


class Dashboard(Base):
    """Database model for dashboard storage"""

    __tablename__ = "dashboards"

    id = Column(String, primary_key=True, index=True)  # UUID
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    config = Column(JSON, nullable=False)
    created_by = Column(String, nullable=True)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AnalyticsCache(Base):
    """Database model for analytics query caching"""

    __tablename__ = "analytics_cache"

    id = Column(Integer, primary_key=True, index=True)
    query_hash = Column(String, nullable=False, unique=True, index=True)
    query_config = Column(JSON, nullable=False)
    result_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    hit_count = Column(Integer, default=0)


class AlertRule(Base):
    """Database model for analytics alerts"""

    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    metric_type = Column(String, nullable=False)
    condition = Column(String, nullable=False)  # JSON condition
    threshold = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    notification_config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_triggered = Column(DateTime(timezone=True), nullable=True)


# Response Models for API


class MetricEntryResponse(BaseModel):
    """Response model for metric entries"""

    id: int
    metric_type: str
    timestamp: datetime
    value: float
    string_value: Optional[str]
    labels: Dict[str, str]
    metadata: Dict[str, Any]

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    """Response model for dashboards"""

    id: str
    name: str
    description: Optional[str]
    config: Dict[str, Any]
    created_by: Optional[str]
    is_public: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class AnalyticsSummary(BaseModel):
    """Summary analytics for overview"""

    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    average_execution_time_ms: float
    current_queue_depth: int
    system_health_score: float
    active_workflows: int
    cost_today_usd: str

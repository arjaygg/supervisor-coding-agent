# supervisor_agent/monitoring/real_time_monitor.py
import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import psutil

from supervisor_agent.models.task import Task


class MetricType(Enum):
    """Types of performance metrics."""

    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"
    TASK_THROUGHPUT = "task_throughput"
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    QUEUE_DEPTH = "queue_depth"


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class SLAStatus(Enum):
    """SLA compliance status."""

    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    VIOLATED = "violated"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    """Performance metric data point."""

    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceAlert:
    """Performance alert."""

    alert_id: str
    severity: AlertSeverity
    metric_type: MetricType
    message: str
    threshold_value: float
    actual_value: float
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class SLARequirement:
    """SLA requirement definition."""

    name: str
    metric_type: MetricType
    threshold: float
    comparison: str  # "<", ">", "<=", ">=", "=="
    time_window: int  # minutes
    description: str = ""


@dataclass
class SLAViolation:
    """SLA violation record."""

    sla_name: str
    metric_type: MetricType
    threshold: float
    actual_value: float
    violation_start: datetime
    violation_end: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    severity: AlertSeverity = AlertSeverity.WARNING


@dataclass
class WorkflowExecutionStatus:
    """Workflow execution status."""

    workflow_id: str
    status: str
    start_time: datetime
    current_time: datetime = field(default_factory=datetime.now)
    tasks_completed: int = 0
    tasks_total: int = 0
    average_task_time: float = 0.0
    estimated_completion: Optional[datetime] = None
    bottlenecks: List[str] = field(default_factory=list)
    performance_issues: List[str] = field(default_factory=list)


class RealTimeMonitor:
    """Advanced real-time performance monitoring system."""

    def __init__(self):
        self.metrics_history: Dict[MetricType, deque] = {
            metric_type: deque(maxlen=1000) for metric_type in MetricType
        }
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.sla_requirements: Dict[str, SLARequirement] = {}
        self.sla_violations: List[SLAViolation] = []
        self.workflow_statuses: Dict[str, WorkflowExecutionStatus] = {}
        self.alert_thresholds = {
            MetricType.CPU_USAGE: 80.0,
            MetricType.MEMORY_USAGE: 85.0,
            MetricType.RESPONSE_TIME: 5000.0,  # 5 seconds
            MetricType.ERROR_RATE: 5.0,  # 5%
            MetricType.QUEUE_DEPTH: 100,
        }
        self.monitoring_active = True

        # Set up default SLA requirements
        self._setup_default_slas()

    def _setup_default_slas(self):
        """Set up default SLA requirements."""
        self.sla_requirements = {
            "response_time_sla": SLARequirement(
                name="Response Time SLA",
                metric_type=MetricType.RESPONSE_TIME,
                threshold=3000.0,  # 3 seconds
                comparison="<",
                time_window=5,
                description="95% of requests must complete within 3 seconds",
            ),
            "availability_sla": SLARequirement(
                name="System Availability SLA",
                metric_type=MetricType.ERROR_RATE,
                threshold=1.0,  # 1%
                comparison="<",
                time_window=15,
                description="Error rate must stay below 1%",
            ),
            "throughput_sla": SLARequirement(
                name="Task Throughput SLA",
                metric_type=MetricType.TASK_THROUGHPUT,
                threshold=100.0,  # 100 tasks per hour
                comparison=">",
                time_window=60,
                description="System must process at least 100 tasks per hour",
            ),
        }

    async def start_monitoring(self):
        """Start continuous performance monitoring."""
        self.monitoring_active = True

        # Start monitoring tasks concurrently
        monitoring_tasks = [
            self._monitor_system_metrics(),
            self._monitor_application_metrics(),
            self._check_alert_conditions(),
            self._monitor_sla_compliance(),
        ]

        await asyncio.gather(*monitoring_tasks)

    async def _monitor_system_metrics(self):
        """Monitor system-level metrics."""
        while self.monitoring_active:
            try:
                # CPU Usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self._record_metric(MetricType.CPU_USAGE, cpu_percent)

                # Memory Usage
                memory = psutil.virtual_memory()
                self._record_metric(MetricType.MEMORY_USAGE, memory.percent)

                # Disk I/O
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    disk_usage = disk_io.read_bytes + disk_io.write_bytes
                    self._record_metric(MetricType.DISK_IO, disk_usage)

                # Network I/O
                network_io = psutil.net_io_counters()
                if network_io:
                    network_usage = network_io.bytes_sent + network_io.bytes_recv
                    self._record_metric(MetricType.NETWORK_IO, network_usage)

                await asyncio.sleep(5)  # Monitor every 5 seconds

            except Exception as e:
                print(f"Error monitoring system metrics: {e}")
                await asyncio.sleep(10)

    async def _monitor_application_metrics(self):
        """Monitor application-level metrics."""
        while self.monitoring_active:
            try:
                # Simulated application metrics
                # In a real implementation, these would come from the application

                # Task throughput (tasks per minute)
                import random

                throughput = 50 + random.randint(-10, 20)
                self._record_metric(MetricType.TASK_THROUGHPUT, throughput)

                # Response time (milliseconds)
                response_time = 1000 + random.randint(-200, 1000)
                self._record_metric(MetricType.RESPONSE_TIME, response_time)

                # Error rate (percentage)
                error_rate = max(0, random.gauss(0.5, 0.3))
                self._record_metric(MetricType.ERROR_RATE, error_rate)

                # Queue depth
                queue_depth = max(0, random.randint(0, 50))
                self._record_metric(MetricType.QUEUE_DEPTH, queue_depth)

                await asyncio.sleep(30)  # Monitor every 30 seconds

            except Exception as e:
                print(f"Error monitoring application metrics: {e}")
                await asyncio.sleep(60)

    def _record_metric(
        self,
        metric_type: MetricType,
        value: float,
        source: str = "system",
        tags: Dict[str, str] = None,
    ):
        """Record a performance metric."""
        metric = PerformanceMetric(
            metric_type=metric_type,
            value=value,
            source=source,
            tags=tags or {},
        )
        self.metrics_history[metric_type].append(metric)

    async def _check_alert_conditions(self):
        """Check for alert conditions and generate alerts."""
        while self.monitoring_active:
            try:
                for metric_type, threshold in self.alert_thresholds.items():
                    if (
                        metric_type in self.metrics_history
                        and self.metrics_history[metric_type]
                    ):
                        latest_metric = self.metrics_history[metric_type][-1]

                        # Check if threshold is exceeded
                        if self._should_trigger_alert(
                            metric_type, latest_metric.value, threshold
                        ):
                            alert = await self._create_alert(
                                metric_type, threshold, latest_metric.value
                            )
                            self.active_alerts[alert.alert_id] = alert

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                print(f"Error checking alert conditions: {e}")
                await asyncio.sleep(60)

    def _should_trigger_alert(
        self, metric_type: MetricType, value: float, threshold: float
    ) -> bool:
        """Determine if an alert should be triggered."""
        if metric_type in [
            MetricType.CPU_USAGE,
            MetricType.MEMORY_USAGE,
            MetricType.RESPONSE_TIME,
            MetricType.ERROR_RATE,
            MetricType.QUEUE_DEPTH,
        ]:
            return value > threshold
        elif metric_type == MetricType.TASK_THROUGHPUT:
            return value < threshold
        return False

    async def _create_alert(
        self, metric_type: MetricType, threshold: float, actual_value: float
    ) -> PerformanceAlert:
        """Create a performance alert."""
        severity = AlertSeverity.WARNING
        if actual_value > threshold * 1.5:
            severity = AlertSeverity.CRITICAL
        elif actual_value > threshold * 2.0:
            severity = AlertSeverity.EMERGENCY

        alert_id = f"{metric_type.value}_{int(time.time())}"

        message = f"{metric_type.value.replace('_', ' ').title()} exceeded threshold: {actual_value:.2f} > {threshold:.2f}"

        return PerformanceAlert(
            alert_id=alert_id,
            severity=severity,
            metric_type=metric_type,
            message=message,
            threshold_value=threshold,
            actual_value=actual_value,
            source="real_time_monitor",
        )

    async def _monitor_sla_compliance(self):
        """Monitor SLA compliance continuously."""
        while self.monitoring_active:
            try:
                for sla_name, sla_req in self.sla_requirements.items():
                    compliance_status = await self._check_sla_compliance(sla_req)

                    if compliance_status["status"] == SLAStatus.VIOLATED:
                        violation = SLAViolation(
                            sla_name=sla_name,
                            metric_type=sla_req.metric_type,
                            threshold=sla_req.threshold,
                            actual_value=compliance_status["actual_value"],
                            violation_start=datetime.now(),
                            severity=AlertSeverity.CRITICAL,
                        )
                        self.sla_violations.append(violation)

                await asyncio.sleep(300)  # Check every 5 minutes

            except Exception as e:
                print(f"Error monitoring SLA compliance: {e}")
                await asyncio.sleep(300)

    async def monitor_workflow_execution(self, workflow_id: str) -> Dict:
        """Monitor workflow execution in real-time."""
        if workflow_id not in self.workflow_statuses:
            self.workflow_statuses[workflow_id] = WorkflowExecutionStatus(
                workflow_id=workflow_id,
                status="running",
                start_time=datetime.now(),
            )

        status = self.workflow_statuses[workflow_id]

        # Update execution metrics (simplified simulation)
        import random

        status.tasks_completed = min(
            status.tasks_total or 10,
            status.tasks_completed + random.randint(0, 2),
        )
        status.tasks_total = status.tasks_total or 10

        if status.tasks_completed > 0:
            elapsed_time = (datetime.now() - status.start_time).total_seconds()
            status.average_task_time = elapsed_time / status.tasks_completed

            if status.tasks_completed < status.tasks_total:
                remaining_time = status.average_task_time * (
                    status.tasks_total - status.tasks_completed
                )
                status.estimated_completion = datetime.now() + timedelta(
                    seconds=remaining_time
                )

        # Detect potential bottlenecks
        bottlenecks = await self.detect_bottlenecks({"workflow_id": workflow_id})
        status.bottlenecks = [b["component"] for b in bottlenecks]

        return {
            "workflow_id": workflow_id,
            "status": status.status,
            "progress": {
                "completed": status.tasks_completed,
                "total": status.tasks_total,
                "percentage": (status.tasks_completed / max(1, status.tasks_total))
                * 100,
            },
            "timing": {
                "start_time": status.start_time.isoformat(),
                "current_time": status.current_time.isoformat(),
                "average_task_time": status.average_task_time,
                "estimated_completion": (
                    status.estimated_completion.isoformat()
                    if status.estimated_completion
                    else None
                ),
            },
            "issues": {
                "bottlenecks": status.bottlenecks,
                "performance_issues": status.performance_issues,
            },
        }

    async def detect_bottlenecks(self, execution_data: Dict) -> List[Dict]:
        """Detect performance bottlenecks in real-time."""
        bottlenecks = []

        # CPU bottleneck detection
        if MetricType.CPU_USAGE in self.metrics_history:
            recent_cpu = [
                m.value for m in list(self.metrics_history[MetricType.CPU_USAGE])[-5:]
            ]
            if recent_cpu and sum(recent_cpu) / len(recent_cpu) > 85.0:
                bottlenecks.append(
                    {
                        "type": "cpu_bottleneck",
                        "component": "system_cpu",
                        "severity": "high",
                        "description": f"High CPU usage: {sum(recent_cpu) / len(recent_cpu):.1f}%",
                        "recommendation": "Consider scaling up CPU resources or optimizing CPU-intensive tasks",
                    }
                )

        # Memory bottleneck detection
        if MetricType.MEMORY_USAGE in self.metrics_history:
            recent_memory = [
                m.value
                for m in list(self.metrics_history[MetricType.MEMORY_USAGE])[-5:]
            ]
            if recent_memory and sum(recent_memory) / len(recent_memory) > 90.0:
                bottlenecks.append(
                    {
                        "type": "memory_bottleneck",
                        "component": "system_memory",
                        "severity": "critical",
                        "description": f"High memory usage: {sum(recent_memory) / len(recent_memory):.1f}%",
                        "recommendation": "Scale up memory or optimize memory-intensive operations",
                    }
                )

        # Queue depth bottleneck
        if MetricType.QUEUE_DEPTH in self.metrics_history:
            recent_queue = [
                m.value for m in list(self.metrics_history[MetricType.QUEUE_DEPTH])[-3:]
            ]
            if recent_queue and sum(recent_queue) / len(recent_queue) > 75:
                bottlenecks.append(
                    {
                        "type": "queue_bottleneck",
                        "component": "task_queue",
                        "severity": "medium",
                        "description": f"High queue depth: {sum(recent_queue) / len(recent_queue):.0f} tasks",
                        "recommendation": "Increase worker capacity or optimize task processing",
                    }
                )

        # Response time bottleneck
        if MetricType.RESPONSE_TIME in self.metrics_history:
            recent_response = [
                m.value
                for m in list(self.metrics_history[MetricType.RESPONSE_TIME])[-5:]
            ]
            if (
                recent_response and sum(recent_response) / len(recent_response) > 4000
            ):  # 4 seconds
                bottlenecks.append(
                    {
                        "type": "response_time_bottleneck",
                        "component": "application_response",
                        "severity": "high",
                        "description": f"Slow response time: {sum(recent_response) / len(recent_response):.0f}ms",
                        "recommendation": "Optimize database queries, caching, or application logic",
                    }
                )

        return bottlenecks

    async def generate_performance_alerts(self, metrics: Dict) -> List[Dict]:
        """Generate performance alerts based on current metrics."""
        alerts = []

        # Convert active alerts to response format
        for alert in self.active_alerts.values():
            if not alert.acknowledged and not alert.resolved:
                alerts.append(
                    {
                        "alert_id": alert.alert_id,
                        "severity": alert.severity.value,
                        "metric": alert.metric_type.value,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                        "threshold": alert.threshold_value,
                        "actual_value": alert.actual_value,
                        "source": alert.source,
                    }
                )

        # Add SLA violation alerts
        for violation in self.sla_violations[-5:]:  # Last 5 violations
            if not violation.violation_end:  # Still ongoing
                alerts.append(
                    {
                        "alert_id": f"sla_violation_{violation.sla_name}_{int(violation.violation_start.timestamp())}",
                        "severity": violation.severity.value,
                        "metric": "sla_compliance",
                        "message": f"SLA violation: {violation.sla_name} - {violation.actual_value:.2f} vs {violation.threshold:.2f}",
                        "timestamp": violation.violation_start.isoformat(),
                        "threshold": violation.threshold,
                        "actual_value": violation.actual_value,
                        "source": "sla_monitor",
                    }
                )

        return alerts

    async def track_sla_compliance(self, sla_requirements: Dict) -> Dict:
        """Track SLA compliance with detailed analysis."""
        compliance_report = {
            "overall_compliance": "compliant",
            "compliance_percentage": 100.0,
            "sla_status": {},
            "violations": [],
            "at_risk": [],
        }

        compliant_count = 0
        total_slas = len(self.sla_requirements)

        for sla_name, sla_req in self.sla_requirements.items():
            status = await self._check_sla_compliance(sla_req)
            compliance_report["sla_status"][sla_name] = status

            if status["status"] == SLAStatus.COMPLIANT:
                compliant_count += 1
            elif status["status"] == SLAStatus.VIOLATED:
                compliance_report["violations"].append(
                    {
                        "sla_name": sla_name,
                        "metric": sla_req.metric_type.value,
                        "threshold": sla_req.threshold,
                        "actual": status["actual_value"],
                        "description": sla_req.description,
                    }
                )
            elif status["status"] == SLAStatus.AT_RISK:
                compliance_report["at_risk"].append(
                    {
                        "sla_name": sla_name,
                        "metric": sla_req.metric_type.value,
                        "risk_level": status.get("risk_level", "medium"),
                    }
                )

        # Calculate overall compliance
        if total_slas > 0:
            compliance_report["compliance_percentage"] = (
                compliant_count / total_slas
            ) * 100

            if compliance_report["compliance_percentage"] < 80:
                compliance_report["overall_compliance"] = "critical"
            elif compliance_report["compliance_percentage"] < 95:
                compliance_report["overall_compliance"] = "at_risk"
            else:
                compliance_report["overall_compliance"] = "compliant"

        return compliance_report

    async def _check_sla_compliance(self, sla_req: SLARequirement) -> Dict:
        """Check compliance for a specific SLA requirement."""
        if sla_req.metric_type not in self.metrics_history:
            return {
                "status": SLAStatus.COMPLIANT,
                "actual_value": 0.0,
                "message": "No data available",
            }

        # Get metrics from the specified time window
        cutoff_time = datetime.now() - timedelta(minutes=sla_req.time_window)
        recent_metrics = [
            m
            for m in self.metrics_history[sla_req.metric_type]
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {
                "status": SLAStatus.COMPLIANT,
                "actual_value": 0.0,
                "message": "No recent data",
            }

        # Calculate average value in time window
        avg_value = sum(m.value for m in recent_metrics) / len(recent_metrics)

        # Check compliance based on comparison operator
        is_compliant = self._evaluate_sla_condition(
            avg_value, sla_req.threshold, sla_req.comparison
        )

        if is_compliant:
            status = SLAStatus.COMPLIANT
        else:
            # Determine if at risk or violated
            if self._is_near_threshold(
                avg_value, sla_req.threshold, sla_req.comparison
            ):
                status = SLAStatus.AT_RISK
            else:
                status = SLAStatus.VIOLATED

        return {
            "status": status,
            "actual_value": avg_value,
            "threshold": sla_req.threshold,
            "comparison": sla_req.comparison,
            "sample_size": len(recent_metrics),
            "time_window": sla_req.time_window,
        }

    def _evaluate_sla_condition(
        self, actual: float, threshold: float, comparison: str
    ) -> bool:
        """Evaluate SLA condition based on comparison operator."""
        if comparison == "<":
            return actual < threshold
        elif comparison == ">":
            return actual > threshold
        elif comparison == "<=":
            return actual <= threshold
        elif comparison == ">=":
            return actual >= threshold
        elif comparison == "==":
            return abs(actual - threshold) < 0.01  # Small tolerance for floating point
        return False

    def _is_near_threshold(
        self,
        actual: float,
        threshold: float,
        comparison: str,
        tolerance: float = 0.1,
    ) -> bool:
        """Check if value is near the threshold (at risk)."""
        if comparison in ["<", "<="]:
            return actual > threshold * (1 - tolerance) and actual <= threshold
        elif comparison in [">", ">="]:
            return actual < threshold * (1 + tolerance) and actual >= threshold
        elif comparison == "==":
            return abs(actual - threshold) < threshold * tolerance
        return False

    async def get_performance_dashboard_data(self) -> Dict:
        """Get comprehensive performance dashboard data."""
        current_metrics = {}

        # Get latest metrics
        for metric_type in MetricType:
            if (
                metric_type in self.metrics_history
                and self.metrics_history[metric_type]
            ):
                latest = self.metrics_history[metric_type][-1]
                current_metrics[metric_type.value] = {
                    "value": latest.value,
                    "timestamp": latest.timestamp.isoformat(),
                    "trend": self._calculate_metric_trend(metric_type),
                }

        # Get active alerts
        active_alerts = await self.generate_performance_alerts({})

        # Get bottlenecks
        bottlenecks = await self.detect_bottlenecks({})

        # Get SLA compliance
        sla_compliance = await self.track_sla_compliance({})

        return {
            "timestamp": datetime.now().isoformat(),
            "system_health": self._calculate_system_health(),
            "current_metrics": current_metrics,
            "active_alerts": {
                "count": len(active_alerts),
                "critical_count": len(
                    [a for a in active_alerts if a["severity"] == "critical"]
                ),
                "alerts": active_alerts[:10],  # Latest 10 alerts
            },
            "bottlenecks": {
                "count": len(bottlenecks),
                "high_severity": len(
                    [b for b in bottlenecks if b["severity"] == "high"]
                ),
                "items": bottlenecks,
            },
            "sla_compliance": sla_compliance,
            "workflow_status": {
                "active_workflows": len(self.workflow_statuses),
                "workflows": list(self.workflow_statuses.values())[:5],  # Latest 5
            },
        }

    def _calculate_metric_trend(self, metric_type: MetricType) -> str:
        """Calculate trend for a metric (increasing, decreasing, stable)."""
        if (
            metric_type not in self.metrics_history
            or len(self.metrics_history[metric_type]) < 5
        ):
            return "stable"

        recent_values = [m.value for m in list(self.metrics_history[metric_type])[-5:]]

        # Simple trend calculation
        first_half = sum(recent_values[:2]) / 2
        second_half = sum(recent_values[-2:]) / 2

        change_percent = ((second_half - first_half) / max(0.1, first_half)) * 100

        if change_percent > 10:
            return "increasing"
        elif change_percent < -10:
            return "decreasing"
        else:
            return "stable"

    def _calculate_system_health(self) -> str:
        """Calculate overall system health score."""
        scores = []

        # CPU health
        if (
            MetricType.CPU_USAGE in self.metrics_history
            and self.metrics_history[MetricType.CPU_USAGE]
        ):
            cpu_usage = self.metrics_history[MetricType.CPU_USAGE][-1].value
            cpu_score = max(0, 100 - cpu_usage)
            scores.append(cpu_score)

        # Memory health
        if (
            MetricType.MEMORY_USAGE in self.metrics_history
            and self.metrics_history[MetricType.MEMORY_USAGE]
        ):
            memory_usage = self.metrics_history[MetricType.MEMORY_USAGE][-1].value
            memory_score = max(0, 100 - memory_usage)
            scores.append(memory_score)

        # Error rate health
        if (
            MetricType.ERROR_RATE in self.metrics_history
            and self.metrics_history[MetricType.ERROR_RATE]
        ):
            error_rate = self.metrics_history[MetricType.ERROR_RATE][-1].value
            error_score = max(0, 100 - error_rate * 10)  # Scale error rate
            scores.append(error_score)

        # Response time health
        if (
            MetricType.RESPONSE_TIME in self.metrics_history
            and self.metrics_history[MetricType.RESPONSE_TIME]
        ):
            response_time = self.metrics_history[MetricType.RESPONSE_TIME][-1].value
            response_score = max(0, 100 - (response_time / 50))  # Scale response time
            scores.append(response_score)

        if not scores:
            return "unknown"

        overall_score = sum(scores) / len(scores)

        if overall_score >= 90:
            return "excellent"
        elif overall_score >= 75:
            return "good"
        elif overall_score >= 60:
            return "fair"
        elif overall_score >= 40:
            return "poor"
        else:
            return "critical"

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an active alert."""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            return True
        return False

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert."""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].resolved = True
            return True
        return False

    async def stop_monitoring(self):
        """Stop the monitoring system."""
        self.monitoring_active = False

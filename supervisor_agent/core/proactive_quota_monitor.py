"""
Proactive Quota Monitoring System

Intelligent subscription monitoring with automated task scheduling:
- Real-time quota usage tracking with predictive alerts
- Automated task deferral when approaching quota limits
- Intelligent retry scheduling based on subscription refresh times
- Continuous work flow management without interruptions
- Multi-subscription monitoring and failover coordination
"""

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from celery import Celery
from sqlalchemy.orm import Session

from supervisor_agent.config import settings
from supervisor_agent.core.advanced_usage_predictor import (
    AdvancedUsagePredictor,
    QuotaExhaustionWarning,
    UsagePattern,
)
from supervisor_agent.core.quota import quota_manager
from supervisor_agent.db import crud
from supervisor_agent.db.database import get_db
from supervisor_agent.db.enums import TaskStatus
from supervisor_agent.db.models import Task
from supervisor_agent.queue.celery_app import celery_app
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class AlertLevel(str, Enum):
    """Alert severity levels"""

    INFO = "info"  # Normal operation
    WARNING = "warning"  # Approaching limits (60-80%)
    CRITICAL = "critical"  # Near limits (80-95%)
    EMERGENCY = "emergency"  # At or exceeding limits (95%+)


class MonitoringAction(str, Enum):
    """Actions the monitor can take"""

    CONTINUE = "continue"  # Normal processing
    THROTTLE = "throttle"  # Reduce processing rate
    DEFER_NON_CRITICAL = "defer_non_critical"  # Defer low priority tasks
    DEFER_ALL = "defer_all"  # Defer all new tasks
    EMERGENCY_STOP = "emergency_stop"  # Stop all processing


@dataclass
class QuotaAlert:
    """Quota monitoring alert"""

    provider_id: str
    agent_id: str
    alert_level: AlertLevel
    current_usage: int
    quota_limit: int
    usage_percentage: float
    predicted_exhaustion: Optional[datetime]
    recommended_action: MonitoringAction
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DeferredTaskGroup:
    """Group of deferred tasks waiting for quota refresh"""

    provider_id: str
    tasks: List[int]  # Task IDs
    priority_level: int  # 1=high, 2=medium, 3=low
    created_at: datetime
    retry_after: datetime
    reason: str


@dataclass
class SubscriptionStatus:
    """Status of a Claude subscription"""

    agent_id: str
    provider_id: str
    quota_used: int
    quota_limit: int
    quota_reset_time: datetime
    current_alert_level: AlertLevel
    consecutive_failures: int
    is_available: bool
    last_check_time: datetime
    usage_trend: UsagePattern


class ProactiveQuotaMonitor:
    """Intelligent quota monitoring with automated task management"""

    def __init__(
        self,
        check_interval_seconds: int = 60,  # Check every minute
        prediction_horizon_minutes: int = 120,  # 2 hour prediction
        alert_thresholds: Dict[AlertLevel, float] = None,
        max_deferred_tasks: int = 1000,
    ):
        self.check_interval_seconds = check_interval_seconds
        self.prediction_horizon_minutes = prediction_horizon_minutes
        self.max_deferred_tasks = max_deferred_tasks

        # Alert thresholds (percentage of quota)
        self.alert_thresholds = alert_thresholds or {
            AlertLevel.WARNING: 60.0,
            AlertLevel.CRITICAL: 80.0,
            AlertLevel.EMERGENCY: 95.0,
        }

        # Core components
        self.usage_predictor = AdvancedUsagePredictor()

        # Monitoring state
        self.subscription_status: Dict[str, SubscriptionStatus] = {}
        self.active_alerts: Dict[str, List[QuotaAlert]] = defaultdict(list)
        self.deferred_tasks: Dict[str, List[DeferredTaskGroup]] = defaultdict(list)

        # Task scheduling
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring: bool = False
        self.alert_callbacks: List[Callable[[QuotaAlert], None]] = []

        # Statistics
        self.alerts_sent: int = 0
        self.tasks_deferred: int = 0
        self.tasks_resumed: int = 0
        self.predictions_made: int = 0

        logger.info("Proactive quota monitor initialized")

    async def start_monitoring(self) -> None:
        """Start continuous quota monitoring"""
        if self.is_monitoring:
            logger.warning("Monitoring already started")
            return

        self.is_monitoring = True

        # Start monitoring loop
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        # Schedule periodic tasks
        self._schedule_periodic_tasks()

        logger.info("Started proactive quota monitoring")

    async def stop_monitoring(self) -> None:
        """Stop quota monitoring"""
        self.is_monitoring = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped proactive quota monitoring")

    def register_alert_callback(self, callback: Callable[[QuotaAlert], None]) -> None:
        """Register callback for quota alerts"""
        self.alert_callbacks.append(callback)

    async def check_quota_status(self, provider_id: str) -> SubscriptionStatus:
        """Check current quota status for a provider"""
        db = next(get_db())

        try:
            # Get agent for this provider (assuming 1:1 mapping for now)
            agent = quota_manager.get_available_agent(db)
            if not agent:
                # No available agent
                return SubscriptionStatus(
                    agent_id="none",
                    provider_id=provider_id,
                    quota_used=0,
                    quota_limit=0,
                    quota_reset_time=datetime.now(timezone.utc) + timedelta(hours=24),
                    current_alert_level=AlertLevel.EMERGENCY,
                    consecutive_failures=0,
                    is_available=False,
                    last_check_time=datetime.now(timezone.utc),
                    usage_trend=UsagePattern.STEADY,
                )

            # Calculate usage percentage
            usage_percentage = (
                (agent.quota_used / agent.quota_limit * 100)
                if agent.quota_limit > 0
                else 0
            )

            # Determine alert level
            alert_level = self._calculate_alert_level(usage_percentage)

            # Get usage pattern from predictor
            usage_pattern = await self.usage_predictor.analyze_usage_patterns(
                provider_id
            )

            status = SubscriptionStatus(
                agent_id=agent.id,
                provider_id=provider_id,
                quota_used=agent.quota_used,
                quota_limit=agent.quota_limit,
                quota_reset_time=agent.quota_reset_at,
                current_alert_level=alert_level,
                consecutive_failures=0,  # TODO: Track this
                is_available=agent.quota_used < agent.quota_limit,
                last_check_time=datetime.now(timezone.utc),
                usage_trend=usage_pattern.pattern_type,
            )

            self.subscription_status[provider_id] = status
            return status

        except Exception as e:
            logger.error(f"Error checking quota status for {provider_id}: {e}")
            # Return safe status
            return SubscriptionStatus(
                agent_id="error",
                provider_id=provider_id,
                quota_used=0,
                quota_limit=0,
                quota_reset_time=datetime.now(timezone.utc) + timedelta(hours=24),
                current_alert_level=AlertLevel.EMERGENCY,
                consecutive_failures=1,
                is_available=False,
                last_check_time=datetime.now(timezone.utc),
                usage_trend=UsagePattern.STEADY,
            )
        finally:
            db.close()

    async def should_defer_task(
        self, task: Task, provider_id: str
    ) -> Tuple[bool, Optional[str]]:
        """Determine if a task should be deferred based on quota status"""
        try:
            # Check current status
            status = await self.check_quota_status(provider_id)

            if not status.is_available:
                return True, f"Provider {provider_id} quota exhausted"

            # Get prediction for task completion
            try:
                prediction = await self.usage_predictor.predict_quota_exhaustion(
                    provider_id=provider_id,
                    current_usage=status.quota_used,
                    quota_limit=status.quota_limit,
                    quota_reset_time=status.quota_reset_time,
                )

                if prediction and prediction.severity in ["critical", "emergency"]:
                    # Estimate task token usage
                    estimated_tokens = quota_manager.estimate_messages_from_task(
                        task.type, len(str(task.payload))
                    )

                    # Check if this task would push us over
                    if status.quota_used + estimated_tokens > status.quota_limit:
                        return (
                            True,
                            f"Task would exceed quota limit (estimated {estimated_tokens} tokens)",
                        )

                    # Check if we're in high-risk zone
                    if status.current_alert_level in [
                        AlertLevel.CRITICAL,
                        AlertLevel.EMERGENCY,
                    ]:
                        # Only allow high priority tasks
                        priority = getattr(
                            task, "priority", 5
                        )  # Default medium priority
                        if priority > 2:  # Only high priority (1-2) allowed
                            return (
                                True,
                                f"Deferring non-critical task due to {status.current_alert_level} alert",
                            )

            except Exception as e:
                logger.warning(f"Prediction failed for task deferral decision: {e}")
                # Fall back to conservative approach
                if status.current_alert_level == AlertLevel.EMERGENCY:
                    return True, "Conservative deferral due to emergency alert level"

            return False, None

        except Exception as e:
            logger.error(f"Error in task deferral decision: {e}")
            # Conservative approach - defer on error
            return True, f"Deferred due to monitoring error: {e}"

    async def defer_task(
        self, task_id: int, provider_id: str, reason: str, priority_level: int = 3
    ) -> None:
        """Defer a task until quota is available"""
        db = next(get_db())

        try:
            # Update task status to deferred
            update_data = crud.schemas.TaskUpdate(
                status=TaskStatus.RETRY, error_message=f"Deferred: {reason}"
            )
            crud.TaskCRUD.update_task(db, task_id, update_data)

            # Calculate retry time based on quota reset
            status = self.subscription_status.get(provider_id)
            if status:
                retry_after = status.quota_reset_time
                # Add some jitter to spread out retries
                jitter = timedelta(minutes=priority_level * 5)  # 5, 10, 15 min jitter
                retry_after += jitter
            else:
                # Default retry in 1 hour
                retry_after = datetime.now(timezone.utc) + timedelta(hours=1)

            # Add to deferred tasks
            deferred_group = DeferredTaskGroup(
                provider_id=provider_id,
                tasks=[task_id],
                priority_level=priority_level,
                created_at=datetime.now(timezone.utc),
                retry_after=retry_after,
                reason=reason,
            )

            self.deferred_tasks[provider_id].append(deferred_group)
            self.tasks_deferred += 1

            # Schedule retry
            self._schedule_task_retry(task_id, retry_after)

            logger.info(
                f"Deferred task {task_id} for provider {provider_id}: {reason}. "
                f"Retry scheduled for {retry_after}"
            )

        except Exception as e:
            logger.error(f"Error deferring task {task_id}: {e}")
        finally:
            db.close()

    async def resume_deferred_tasks(self, provider_id: str) -> int:
        """Resume deferred tasks when quota becomes available"""
        if provider_id not in self.deferred_tasks:
            return 0

        # Check if provider is available
        status = await self.check_quota_status(provider_id)
        if not status.is_available:
            logger.debug(
                f"Provider {provider_id} still unavailable, cannot resume tasks"
            )
            return 0

        resumed_count = 0
        current_time = datetime.now(timezone.utc)

        # Sort deferred tasks by priority and creation time
        all_deferred = []
        for group in self.deferred_tasks[provider_id]:
            for task_id in group.tasks:
                all_deferred.append(
                    (task_id, group.priority_level, group.created_at, group.retry_after)
                )

        # Sort by priority (lower number = higher priority), then by creation time
        all_deferred.sort(key=lambda x: (x[1], x[2]))

        # Resume tasks based on available quota
        available_quota = status.quota_limit - status.quota_used

        for task_id, priority, created_at, retry_after in all_deferred:
            if current_time < retry_after:
                continue  # Not time yet

            if available_quota <= 0:
                break  # No more quota available

            try:
                # Estimate task resource usage
                db = next(get_db())
                task = crud.TaskCRUD.get_task(db, task_id)
                if task:
                    estimated_tokens = quota_manager.estimate_messages_from_task(
                        task.type, len(str(task.payload))
                    )

                    if estimated_tokens <= available_quota:
                        # Resume the task
                        await self._resume_task(task_id, provider_id)
                        available_quota -= estimated_tokens
                        resumed_count += 1
                        self.tasks_resumed += 1

                        logger.info(
                            f"Resumed deferred task {task_id} for provider {provider_id}"
                        )
                    else:
                        # Task too large for remaining quota
                        logger.debug(
                            f"Task {task_id} requires {estimated_tokens} tokens, "
                            f"but only {available_quota} available"
                        )
                db.close()

            except Exception as e:
                logger.error(f"Error resuming task {task_id}: {e}")

        # Clean up resumed tasks from deferred list
        self._cleanup_deferred_tasks(
            provider_id, [tid for tid, _, _, _ in all_deferred[:resumed_count]]
        )

        if resumed_count > 0:
            logger.info(
                f"Resumed {resumed_count} deferred tasks for provider {provider_id}"
            )

        return resumed_count

    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Get comprehensive monitoring status"""
        status = {
            "is_monitoring": self.is_monitoring,
            "check_interval_seconds": self.check_interval_seconds,
            "prediction_horizon_minutes": self.prediction_horizon_minutes,
            "statistics": {
                "alerts_sent": self.alerts_sent,
                "tasks_deferred": self.tasks_deferred,
                "tasks_resumed": self.tasks_resumed,
                "predictions_made": self.predictions_made,
            },
            "subscriptions": {},
            "active_alerts": {},
            "deferred_tasks_count": {},
        }

        # Subscription status
        for provider_id, sub_status in self.subscription_status.items():
            status["subscriptions"][provider_id] = {
                "agent_id": sub_status.agent_id,
                "quota_used": sub_status.quota_used,
                "quota_limit": sub_status.quota_limit,
                "usage_percentage": (
                    (sub_status.quota_used / sub_status.quota_limit * 100)
                    if sub_status.quota_limit > 0
                    else 0
                ),
                "quota_reset_time": sub_status.quota_reset_time.isoformat(),
                "alert_level": sub_status.current_alert_level,
                "is_available": sub_status.is_available,
                "usage_trend": sub_status.usage_trend,
                "last_check": sub_status.last_check_time.isoformat(),
            }

        # Active alerts
        for provider_id, alerts in self.active_alerts.items():
            status["active_alerts"][provider_id] = [
                {
                    "level": alert.alert_level,
                    "message": alert.message,
                    "action": alert.recommended_action,
                    "timestamp": alert.timestamp.isoformat(),
                }
                for alert in alerts[-5:]  # Last 5 alerts
            ]

        # Deferred tasks count
        for provider_id, groups in self.deferred_tasks.items():
            total_tasks = sum(len(group.tasks) for group in groups)
            status["deferred_tasks_count"][provider_id] = total_tasks

        return status

    # Private methods

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        logger.info("Started quota monitoring loop")

        while self.is_monitoring:
            try:
                # Get all providers to monitor
                providers_to_monitor = await self._get_providers_to_monitor()

                for provider_id in providers_to_monitor:
                    await self._monitor_provider(provider_id)

                # Resume deferred tasks where possible
                for provider_id in providers_to_monitor:
                    await self.resume_deferred_tasks(provider_id)

                # Cleanup old alerts and deferred tasks
                await self._cleanup_old_data()

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            # Wait for next check
            await asyncio.sleep(self.check_interval_seconds)

        logger.info("Exited quota monitoring loop")

    async def _get_providers_to_monitor(self) -> List[str]:
        """Get list of providers that need monitoring"""
        # For now, just monitor the primary Claude provider
        # This could be expanded to monitor multiple providers
        return ["claude-cli-primary"]

    async def _monitor_provider(self, provider_id: str) -> None:
        """Monitor a specific provider"""
        try:
            # Check current status
            status = await self.check_quota_status(provider_id)

            # Record usage data for predictions
            await self._record_usage_for_prediction(provider_id, status)

            # Generate predictions
            prediction = None
            try:
                prediction = await self.usage_predictor.predict_quota_exhaustion(
                    provider_id=provider_id,
                    current_usage=status.quota_used,
                    quota_limit=status.quota_limit,
                    quota_reset_time=status.quota_reset_time,
                )
                self.predictions_made += 1
            except Exception as e:
                logger.warning(f"Prediction failed for {provider_id}: {e}")

            # Check for alert conditions
            await self._check_alert_conditions(status, prediction)

        except Exception as e:
            logger.error(f"Error monitoring provider {provider_id}: {e}")

    async def _record_usage_for_prediction(
        self, provider_id: str, status: SubscriptionStatus
    ) -> None:
        """Record current usage data for ML predictions"""
        try:
            # Calculate tokens used since last check
            previous_status = self.subscription_status.get(provider_id)
            if previous_status:
                tokens_delta = status.quota_used - previous_status.quota_used
                if tokens_delta > 0:
                    # Record the usage increment
                    await self.usage_predictor.record_usage(
                        task_type="system_usage",
                        tokens_used=tokens_delta,
                        processing_time=self.check_interval_seconds,
                        provider_id=provider_id,
                        success=True,
                    )
        except Exception as e:
            logger.warning(f"Failed to record usage for prediction: {e}")

    async def _check_alert_conditions(
        self, status: SubscriptionStatus, prediction: Optional[QuotaExhaustionWarning]
    ) -> None:
        """Check if alert conditions are met"""
        provider_id = status.provider_id
        usage_percentage = (
            (status.quota_used / status.quota_limit * 100)
            if status.quota_limit > 0
            else 0
        )

        # Determine required action
        action = self._determine_monitoring_action(status, prediction)

        # Create alert if threshold crossed
        should_alert = False
        alert_message = ""

        if status.current_alert_level == AlertLevel.EMERGENCY:
            should_alert = True
            alert_message = (
                f"EMERGENCY: Provider {provider_id} quota at {usage_percentage:.1f}%"
            )
        elif status.current_alert_level == AlertLevel.CRITICAL:
            should_alert = True
            alert_message = (
                f"CRITICAL: Provider {provider_id} quota at {usage_percentage:.1f}%"
            )
            if prediction:
                hours_left = prediction.time_to_exhaustion_hours
                alert_message += f", predicted exhaustion in {hours_left:.1f} hours"
        elif status.current_alert_level == AlertLevel.WARNING:
            should_alert = True
            alert_message = (
                f"WARNING: Provider {provider_id} quota at {usage_percentage:.1f}%"
            )

        if should_alert:
            alert = QuotaAlert(
                provider_id=provider_id,
                agent_id=status.agent_id,
                alert_level=status.current_alert_level,
                current_usage=status.quota_used,
                quota_limit=status.quota_limit,
                usage_percentage=usage_percentage,
                predicted_exhaustion=(
                    prediction.predicted_exhaustion_time if prediction else None
                ),
                recommended_action=action,
                message=alert_message,
            )

            await self._send_alert(alert)

    def _determine_monitoring_action(
        self, status: SubscriptionStatus, prediction: Optional[QuotaExhaustionWarning]
    ) -> MonitoringAction:
        """Determine what action to take based on status"""
        if not status.is_available:
            return MonitoringAction.EMERGENCY_STOP

        if status.current_alert_level == AlertLevel.EMERGENCY:
            return MonitoringAction.DEFER_ALL
        elif status.current_alert_level == AlertLevel.CRITICAL:
            return MonitoringAction.DEFER_NON_CRITICAL
        elif status.current_alert_level == AlertLevel.WARNING:
            return MonitoringAction.THROTTLE
        else:
            return MonitoringAction.CONTINUE

    async def _send_alert(self, alert: QuotaAlert) -> None:
        """Send quota alert"""
        # Store alert
        self.active_alerts[alert.provider_id].append(alert)

        # Keep only recent alerts
        max_alerts = 50
        if len(self.active_alerts[alert.provider_id]) > max_alerts:
            self.active_alerts[alert.provider_id] = self.active_alerts[
                alert.provider_id
            ][-max_alerts:]

        # Call registered callbacks
        for callback in self.alert_callbacks:
            try:
                (
                    await callback(alert)
                    if asyncio.iscoroutinefunction(callback)
                    else callback(alert)
                )
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

        self.alerts_sent += 1

        logger.warning(f"QUOTA ALERT: {alert.message}")

    def _calculate_alert_level(self, usage_percentage: float) -> AlertLevel:
        """Calculate alert level based on usage percentage"""
        if usage_percentage >= self.alert_thresholds[AlertLevel.EMERGENCY]:
            return AlertLevel.EMERGENCY
        elif usage_percentage >= self.alert_thresholds[AlertLevel.CRITICAL]:
            return AlertLevel.CRITICAL
        elif usage_percentage >= self.alert_thresholds[AlertLevel.WARNING]:
            return AlertLevel.WARNING
        else:
            return AlertLevel.INFO

    def _schedule_periodic_tasks(self) -> None:
        """Schedule periodic Celery tasks"""
        # Schedule monitoring tasks
        from supervisor_agent.core.proactive_quota_monitor import (
            cleanup_old_monitoring_data,
            periodic_quota_check,
            resume_deferred_tasks_periodic,
        )

        # Schedule quota checks every minute
        periodic_quota_check.apply_async(countdown=60)

        # Schedule task resume checks every 5 minutes
        resume_deferred_tasks_periodic.apply_async(countdown=300)

        # Schedule cleanup every hour
        cleanup_old_monitoring_data.apply_async(countdown=3600)

    def _schedule_task_retry(self, task_id: int, retry_time: datetime) -> None:
        """Schedule a task for retry at specific time"""
        from supervisor_agent.queue.enhanced_tasks import process_single_task_enhanced

        # Calculate countdown in seconds
        countdown = max(
            0, int((retry_time - datetime.now(timezone.utc)).total_seconds())
        )

        # Schedule the retry
        process_single_task_enhanced.apply_async(args=[task_id], countdown=countdown)

        logger.debug(f"Scheduled task {task_id} retry in {countdown} seconds")

    async def _resume_task(self, task_id: int, provider_id: str) -> None:
        """Resume a specific deferred task"""
        db = next(get_db())

        try:
            # Update task status back to pending
            update_data = crud.schemas.TaskUpdate(
                status=TaskStatus.PENDING, error_message=None
            )
            crud.TaskCRUD.update_task(db, task_id, update_data)

            # Schedule immediate processing
            from supervisor_agent.queue.enhanced_tasks import (
                process_single_task_enhanced,
            )

            process_single_task_enhanced.delay(task_id)

        except Exception as e:
            logger.error(f"Error resuming task {task_id}: {e}")
        finally:
            db.close()

    def _cleanup_deferred_tasks(
        self, provider_id: str, completed_task_ids: List[int]
    ) -> None:
        """Remove completed tasks from deferred list"""
        if provider_id not in self.deferred_tasks:
            return

        # Remove completed tasks from deferred groups
        for group in self.deferred_tasks[provider_id]:
            group.tasks = [tid for tid in group.tasks if tid not in completed_task_ids]

        # Remove empty groups
        self.deferred_tasks[provider_id] = [
            group for group in self.deferred_tasks[provider_id] if group.tasks
        ]

    async def _cleanup_old_data(self) -> None:
        """Clean up old alerts and deferred tasks"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

        # Clean old alerts
        for provider_id in list(self.active_alerts.keys()):
            self.active_alerts[provider_id] = [
                alert
                for alert in self.active_alerts[provider_id]
                if alert.timestamp > cutoff_time
            ]

            if not self.active_alerts[provider_id]:
                del self.active_alerts[provider_id]

        # Clean old deferred tasks (but keep them if retry time hasn't passed)
        for provider_id in list(self.deferred_tasks.keys()):
            self.deferred_tasks[provider_id] = [
                group
                for group in self.deferred_tasks[provider_id]
                if group.retry_after > cutoff_time or group.created_at > cutoff_time
            ]

            if not self.deferred_tasks[provider_id]:
                del self.deferred_tasks[provider_id]


# Global monitor instance
quota_monitor = ProactiveQuotaMonitor()


# Celery tasks for periodic monitoring
@celery_app.task
def periodic_quota_check():
    """Periodic quota check task"""
    try:
        asyncio.run(quota_monitor._monitoring_loop())
    except Exception as e:
        logger.error(f"Periodic quota check failed: {e}")

    # Schedule next check
    periodic_quota_check.apply_async(countdown=quota_monitor.check_interval_seconds)


@celery_app.task
def resume_deferred_tasks_periodic():
    """Periodic task to resume deferred tasks"""
    try:

        async def resume_all():
            providers = await quota_monitor._get_providers_to_monitor()
            total_resumed = 0
            for provider_id in providers:
                resumed = await quota_monitor.resume_deferred_tasks(provider_id)
                total_resumed += resumed

            if total_resumed > 0:
                logger.info(f"Periodic resume: {total_resumed} tasks resumed")

        asyncio.run(resume_all())

    except Exception as e:
        logger.error(f"Periodic task resume failed: {e}")

    # Schedule next check
    resume_deferred_tasks_periodic.apply_async(countdown=300)  # Every 5 minutes


@celery_app.task
def cleanup_old_monitoring_data():
    """Periodic cleanup of old monitoring data"""
    try:
        asyncio.run(quota_monitor._cleanup_old_data())
    except Exception as e:
        logger.error(f"Monitoring data cleanup failed: {e}")

    # Schedule next cleanup
    cleanup_old_monitoring_data.apply_async(countdown=3600)  # Every hour

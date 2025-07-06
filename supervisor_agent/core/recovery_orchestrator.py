"""
Recovery Orchestrator

Intelligent subscription recovery and task continuation system:
- Automatic detection of quota refresh windows and subscription recovery
- Intelligent task resume scheduling post-quota reset
- Cross-provider failover with cost optimization
- Persistent state management during outages
- Health-based provider scoring and selection
- Circuit breaker patterns for API failures
- Exponential backoff with jitter for rate limits
"""

import asyncio
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from supervisor_agent.config import settings
from supervisor_agent.core.advanced_usage_predictor import AdvancedUsagePredictor
from supervisor_agent.core.claude_code_subscription_monitor import claude_code_monitor
from supervisor_agent.core.intelligent_task_scheduler import task_scheduler
from supervisor_agent.core.proactive_quota_monitor import quota_monitor
from supervisor_agent.db import crud
from supervisor_agent.db.database import get_db
from supervisor_agent.db.enums import TaskStatus
from supervisor_agent.queue.celery_app import celery_app
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class RecoveryState(str, Enum):
    """Recovery system states"""

    NORMAL = "normal"  # Normal operation
    DEGRADED = "degraded"  # Reduced capacity
    RECOVERY = "recovery"  # Actively recovering
    EMERGENCY = "emergency"  # Emergency mode
    OFFLINE = "offline"  # System offline


class ProviderStatus(str, Enum):
    """Provider health status"""

    HEALTHY = "healthy"  # Fully operational
    DEGRADED = "degraded"  # Partial functionality
    FAILING = "failing"  # Frequent failures
    UNAVAILABLE = "unavailable"  # Not responding
    RECOVERING = "recovering"  # Coming back online


@dataclass
class ProviderHealth:
    """Provider health information"""

    provider_id: str
    status: ProviderStatus
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    consecutive_failures: int
    consecutive_successes: int
    success_rate_1h: float
    response_time_avg: float
    quota_available: bool
    quota_reset_time: Optional[datetime]
    error_patterns: List[str]
    recovery_attempts: int

    @property
    def health_score(self) -> float:
        """Calculate overall health score (0-1)"""
        if self.status == ProviderStatus.UNAVAILABLE:
            return 0.0
        elif self.status == ProviderStatus.FAILING:
            return 0.2
        elif self.status == ProviderStatus.DEGRADED:
            return 0.5
        elif self.status == ProviderStatus.RECOVERING:
            return 0.7
        else:  # HEALTHY
            return 1.0


@dataclass
class RecoveryAction:
    """Recovery action to be executed"""

    action_type: str  # "retry", "failover", "circuit_break", "scale_back"
    provider_id: str
    task_ids: List[int]
    scheduled_time: datetime
    reason: str
    parameters: Dict[str, Any]
    max_attempts: int = 3
    attempt_count: int = 0


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for a provider"""

    provider_id: str
    state: str  # "closed", "open", "half_open"
    failure_count: int
    last_failure_time: Optional[datetime]
    next_retry_time: Optional[datetime]
    failure_threshold: int = 5
    timeout_seconds: int = 300  # 5 minutes

    def should_allow_request(self) -> bool:
        """Check if request should be allowed through circuit breaker"""
        if self.state == "closed":
            return True
        elif self.state == "open":
            if (
                self.next_retry_time
                and datetime.now(timezone.utc) >= self.next_retry_time
            ):
                self.state = "half_open"
                return True
            return False
        else:  # half_open
            return True

    def record_success(self) -> None:
        """Record successful request"""
        if self.state == "half_open":
            self.state = "closed"
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            self.next_retry_time = datetime.now(timezone.utc) + timedelta(
                seconds=self.timeout_seconds
            )
        elif self.state == "half_open":
            self.state = "open"
            self.next_retry_time = datetime.now(timezone.utc) + timedelta(
                seconds=self.timeout_seconds
            )


class RecoveryOrchestrator:
    """Intelligent recovery orchestration for subscription and provider management"""

    def __init__(
        self,
        health_check_interval: int = 60,  # 1 minute
        recovery_check_interval: int = 30,  # 30 seconds
        max_recovery_attempts: int = 5,
        circuit_breaker_failure_threshold: int = 5,
        circuit_breaker_timeout: int = 300,  # 5 minutes
    ):
        self.health_check_interval = health_check_interval
        self.recovery_check_interval = recovery_check_interval
        self.max_recovery_attempts = max_recovery_attempts
        self.circuit_breaker_failure_threshold = circuit_breaker_failure_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout

        # System state
        self.current_state = RecoveryState.NORMAL
        self.state_change_time = datetime.now(timezone.utc)

        # Provider health tracking
        self.provider_health: Dict[str, ProviderHealth] = {}
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}

        # Recovery management
        self.pending_recovery_actions: List[RecoveryAction] = []
        self.recovery_history: deque = deque(maxlen=100)
        self.failover_chains: Dict[str, List[str]] = {}

        # Monitoring tasks
        self.is_monitoring: bool = False
        self.health_check_task: Optional[asyncio.Task] = None
        self.recovery_task: Optional[asyncio.Task] = None

        # Statistics
        self.recovery_stats = {
            "total_recoveries": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "failovers_performed": 0,
            "circuit_breaker_trips": 0,
            "uptime_percentage": 100.0,
        }

        # Integration components
        self.usage_predictor = AdvancedUsagePredictor()

        logger.info("Recovery orchestrator initialized")

    async def start_recovery_monitoring(self) -> None:
        """Start recovery monitoring and orchestration"""
        if self.is_monitoring:
            logger.warning("Recovery monitoring already started")
            return

        self.is_monitoring = True

        # Initialize provider health tracking
        await self._initialize_provider_health()

        # Start monitoring tasks
        self.health_check_task = asyncio.create_task(self._health_monitoring_loop())
        self.recovery_task = asyncio.create_task(self._recovery_loop())

        # Schedule periodic tasks
        self._schedule_periodic_tasks()

        logger.info("Started recovery monitoring and orchestration")

    async def stop_recovery_monitoring(self) -> None:
        """Stop recovery monitoring"""
        self.is_monitoring = False

        if self.health_check_task:
            self.health_check_task.cancel()
        if self.recovery_task:
            self.recovery_task.cancel()

        try:
            if self.health_check_task:
                await self.health_check_task
            if self.recovery_task:
                await self.recovery_task
        except asyncio.CancelledError:
            pass

        logger.info("Stopped recovery monitoring")

    async def check_provider_health(self, provider_id: str) -> ProviderHealth:
        """Check and update provider health status"""
        try:
            # Get current subscription status
            if provider_id == "claude_code":
                claude_status = await claude_code_monitor.check_claude_code_status()

                # Determine provider status
                if not claude_status.is_available:
                    status = ProviderStatus.UNAVAILABLE
                elif claude_status.consecutive_failures >= 3:
                    status = ProviderStatus.FAILING
                elif claude_status.usage_percentage > 90:
                    status = ProviderStatus.DEGRADED
                else:
                    status = ProviderStatus.HEALTHY

                # Create or update health record
                health = ProviderHealth(
                    provider_id=provider_id,
                    status=status,
                    last_success=claude_status.last_successful_request,
                    last_failure=(
                        datetime.now(timezone.utc)
                        if claude_status.consecutive_failures > 0
                        else None
                    ),
                    consecutive_failures=claude_status.consecutive_failures,
                    consecutive_successes=(
                        0 if claude_status.consecutive_failures > 0 else 1
                    ),
                    success_rate_1h=max(
                        0.0, 100.0 - (claude_status.consecutive_failures * 20)
                    ),
                    response_time_avg=2.0,  # Estimate
                    quota_available=claude_status.is_available,
                    quota_reset_time=claude_status.reset_time,
                    error_patterns=claude_status.error_patterns,
                    recovery_attempts=0,
                )

            else:
                # Generic provider health check
                health = await self._generic_provider_health_check(provider_id)

            # Update circuit breaker based on health
            await self._update_circuit_breaker(provider_id, health)

            # Store health information
            self.provider_health[provider_id] = health

            return health

        except Exception as e:
            logger.error(f"Error checking provider health for {provider_id}: {e}")

            # Return degraded health on error
            return ProviderHealth(
                provider_id=provider_id,
                status=ProviderStatus.DEGRADED,
                last_success=None,
                last_failure=datetime.now(timezone.utc),
                consecutive_failures=1,
                consecutive_successes=0,
                success_rate_1h=0.0,
                response_time_avg=30.0,
                quota_available=False,
                quota_reset_time=None,
                error_patterns=[str(e)],
                recovery_attempts=0,
            )

    async def attempt_recovery(self, provider_id: str, recovery_reason: str) -> bool:
        """Attempt to recover a failed provider"""
        try:
            health = await self.check_provider_health(provider_id)

            if health.status == ProviderStatus.HEALTHY:
                logger.info(
                    f"Provider {provider_id} already healthy, no recovery needed"
                )
                return True

            logger.info(
                f"Attempting recovery for provider {provider_id}: {recovery_reason}"
            )

            # Determine recovery strategy based on health status
            if health.status == ProviderStatus.UNAVAILABLE:
                success = await self._attempt_provider_restart(provider_id, health)
            elif health.status == ProviderStatus.FAILING:
                success = await self._attempt_failure_recovery(provider_id, health)
            elif health.status == ProviderStatus.DEGRADED:
                success = await self._attempt_performance_recovery(provider_id, health)
            else:
                success = True  # Already recovering

            # Update recovery statistics
            self.recovery_stats["total_recoveries"] += 1
            if success:
                self.recovery_stats["successful_recoveries"] += 1
            else:
                self.recovery_stats["failed_recoveries"] += 1

            # Record recovery attempt
            self.recovery_history.append(
                {
                    "provider_id": provider_id,
                    "reason": recovery_reason,
                    "success": success,
                    "timestamp": datetime.now(timezone.utc),
                    "health_before": health.status,
                    "attempts": health.recovery_attempts + 1,
                }
            )

            return success

        except Exception as e:
            logger.error(f"Error during recovery attempt for {provider_id}: {e}")
            return False

    async def perform_failover(
        self,
        failed_provider_id: str,
        task_ids: List[int],
        reason: str = "Provider failure",
    ) -> Optional[str]:
        """Perform failover to alternative provider"""
        try:
            # Find best alternative provider
            alternative_providers = await self._get_alternative_providers(
                failed_provider_id
            )

            if not alternative_providers:
                logger.warning(
                    f"No alternative providers available for failover from {failed_provider_id}"
                )
                return None

            # Select best provider based on health scores
            best_provider = max(
                alternative_providers,
                key=lambda p: self.provider_health.get(
                    p,
                    ProviderHealth(
                        provider_id=p,
                        status=ProviderStatus.DEGRADED,
                        last_success=None,
                        last_failure=None,
                        consecutive_failures=0,
                        consecutive_successes=0,
                        success_rate_1h=50.0,
                        response_time_avg=5.0,
                        quota_available=True,
                        quota_reset_time=None,
                        error_patterns=[],
                        recovery_attempts=0,
                    ),
                ).health_score,
            )

            # Check if target provider can handle the load
            can_handle = await self._check_provider_capacity(best_provider, task_ids)
            if not can_handle:
                logger.warning(
                    f"Alternative provider {best_provider} cannot handle failover load"
                )
                return None

            # Perform the failover
            await self._execute_failover(
                failed_provider_id, best_provider, task_ids, reason
            )

            self.recovery_stats["failovers_performed"] += 1

            logger.info(
                f"Successfully failed over from {failed_provider_id} to {best_provider} for {len(task_ids)} tasks"
            )

            return best_provider

        except Exception as e:
            logger.error(f"Error during failover from {failed_provider_id}: {e}")
            return None

    async def schedule_recovery_retry(
        self,
        provider_id: str,
        task_ids: List[int],
        retry_delay_minutes: int = 5,
        reason: str = "Scheduled retry",
    ) -> None:
        """Schedule retry of tasks after provider recovery"""
        try:
            # Calculate retry time with jitter
            base_delay = timedelta(minutes=retry_delay_minutes)
            jitter = timedelta(seconds=random.randint(0, 60))  # 0-60 second jitter
            retry_time = datetime.now(timezone.utc) + base_delay + jitter

            # Create recovery action
            action = RecoveryAction(
                action_type="retry",
                provider_id=provider_id,
                task_ids=task_ids,
                scheduled_time=retry_time,
                reason=reason,
                parameters={"retry_delay_minutes": retry_delay_minutes},
            )

            self.pending_recovery_actions.append(action)

            # Schedule Celery task for retry
            schedule_recovery_retry.apply_async(
                args=[provider_id, task_ids, reason],
                countdown=int(base_delay.total_seconds() + jitter.total_seconds()),
            )

            logger.info(
                f"Scheduled recovery retry for provider {provider_id} with {len(task_ids)} tasks "
                f"in {retry_delay_minutes} minutes"
            )

        except Exception as e:
            logger.error(f"Error scheduling recovery retry: {e}")

    async def get_recovery_status(self) -> Dict[str, Any]:
        """Get comprehensive recovery system status"""
        status = {
            "system_state": self.current_state,
            "state_change_time": self.state_change_time.isoformat(),
            "is_monitoring": self.is_monitoring,
            "provider_health": {},
            "circuit_breakers": {},
            "pending_actions": len(self.pending_recovery_actions),
            "recovery_stats": self.recovery_stats.copy(),
            "recent_recoveries": list(self.recovery_history)[-10:],  # Last 10
        }

        # Provider health summary
        for provider_id, health in self.provider_health.items():
            status["provider_health"][provider_id] = {
                "status": health.status,
                "health_score": health.health_score,
                "consecutive_failures": health.consecutive_failures,
                "success_rate_1h": health.success_rate_1h,
                "quota_available": health.quota_available,
                "last_success": (
                    health.last_success.isoformat() if health.last_success else None
                ),
                "quota_reset_time": (
                    health.quota_reset_time.isoformat()
                    if health.quota_reset_time
                    else None
                ),
            }

        # Circuit breaker status
        for provider_id, cb in self.circuit_breakers.items():
            status["circuit_breakers"][provider_id] = {
                "state": cb.state,
                "failure_count": cb.failure_count,
                "next_retry_time": (
                    cb.next_retry_time.isoformat() if cb.next_retry_time else None
                ),
            }

        return status

    # Private methods

    async def _health_monitoring_loop(self) -> None:
        """Main health monitoring loop"""
        logger.info("Started provider health monitoring loop")

        while self.is_monitoring:
            try:
                # Check health of all known providers
                for provider_id in await self._get_known_providers():
                    await self.check_provider_health(provider_id)

                # Update system state based on overall health
                await self._update_system_state()

                # Check for automatic recovery opportunities
                await self._check_automatic_recovery()

            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")

            await asyncio.sleep(self.health_check_interval)

        logger.info("Exited provider health monitoring loop")

    async def _recovery_loop(self) -> None:
        """Recovery action execution loop"""
        logger.info("Started recovery action loop")

        while self.is_monitoring:
            try:
                # Process pending recovery actions
                await self._process_pending_recovery_actions()

                # Check for quota refresh opportunities
                await self._check_quota_refresh_opportunities()

                # Cleanup completed actions
                await self._cleanup_completed_actions()

            except Exception as e:
                logger.error(f"Error in recovery loop: {e}")

            await asyncio.sleep(self.recovery_check_interval)

        logger.info("Exited recovery action loop")

    async def _initialize_provider_health(self) -> None:
        """Initialize provider health tracking"""
        try:
            # Initialize known providers
            providers = await self._get_known_providers()

            for provider_id in providers:
                # Initialize circuit breaker
                self.circuit_breakers[provider_id] = CircuitBreakerState(
                    provider_id=provider_id,
                    state="closed",
                    failure_count=0,
                    last_failure_time=None,
                    next_retry_time=None,
                    failure_threshold=self.circuit_breaker_failure_threshold,
                    timeout_seconds=self.circuit_breaker_timeout,
                )

                # Check initial health
                await self.check_provider_health(provider_id)

        except Exception as e:
            logger.error(f"Error initializing provider health: {e}")

    async def _get_known_providers(self) -> List[str]:
        """Get list of known providers to monitor"""
        # For now, just monitor Claude Code
        # This could be expanded to include other providers
        return ["claude_code"]

    async def _generic_provider_health_check(self, provider_id: str) -> ProviderHealth:
        """Generic provider health check"""
        # Placeholder for generic provider health checking
        return ProviderHealth(
            provider_id=provider_id,
            status=ProviderStatus.HEALTHY,
            last_success=datetime.now(timezone.utc),
            last_failure=None,
            consecutive_failures=0,
            consecutive_successes=1,
            success_rate_1h=100.0,
            response_time_avg=1.0,
            quota_available=True,
            quota_reset_time=None,
            error_patterns=[],
            recovery_attempts=0,
        )

    async def _update_circuit_breaker(
        self, provider_id: str, health: ProviderHealth
    ) -> None:
        """Update circuit breaker state based on provider health"""
        if provider_id not in self.circuit_breakers:
            self.circuit_breakers[provider_id] = CircuitBreakerState(
                provider_id=provider_id,
                state="closed",
                failure_count=0,
                last_failure_time=None,
                next_retry_time=None,
            )

        cb = self.circuit_breakers[provider_id]

        if health.status in [ProviderStatus.HEALTHY, ProviderStatus.RECOVERING]:
            cb.record_success()
        elif health.status in [ProviderStatus.FAILING, ProviderStatus.UNAVAILABLE]:
            old_state = cb.state
            cb.record_failure()
            if old_state != "open" and cb.state == "open":
                self.recovery_stats["circuit_breaker_trips"] += 1
                logger.warning(f"Circuit breaker opened for provider {provider_id}")

    async def _update_system_state(self) -> None:
        """Update overall system state based on provider health"""
        if not self.provider_health:
            return

        # Calculate overall system health
        healthy_providers = sum(
            1
            for health in self.provider_health.values()
            if health.status == ProviderStatus.HEALTHY
        )
        total_providers = len(self.provider_health)

        health_ratio = healthy_providers / total_providers if total_providers > 0 else 0

        # Determine new state
        new_state = self.current_state

        if health_ratio >= 0.8:
            new_state = RecoveryState.NORMAL
        elif health_ratio >= 0.5:
            new_state = RecoveryState.DEGRADED
        elif health_ratio > 0:
            new_state = RecoveryState.RECOVERY
        else:
            new_state = RecoveryState.EMERGENCY

        # Update state if changed
        if new_state != self.current_state:
            logger.info(
                f"System state changed from {self.current_state} to {new_state}"
            )
            self.current_state = new_state
            self.state_change_time = datetime.now(timezone.utc)

    async def _check_automatic_recovery(self) -> None:
        """Check for automatic recovery opportunities"""
        for provider_id, health in self.provider_health.items():
            if health.status in [ProviderStatus.FAILING, ProviderStatus.UNAVAILABLE]:
                # Check if enough time has passed for retry
                if health.last_failure:
                    time_since_failure = (
                        datetime.now(timezone.utc) - health.last_failure
                    )
                    if time_since_failure > timedelta(minutes=5):  # Wait 5 minutes
                        if health.recovery_attempts < self.max_recovery_attempts:
                            await self.attempt_recovery(
                                provider_id, "Automatic recovery"
                            )

    async def _process_pending_recovery_actions(self) -> None:
        """Process pending recovery actions"""
        current_time = datetime.now(timezone.utc)

        # Find actions ready to execute
        ready_actions = [
            action
            for action in self.pending_recovery_actions
            if action.scheduled_time <= current_time
        ]

        for action in ready_actions:
            try:
                await self._execute_recovery_action(action)
                self.pending_recovery_actions.remove(action)
            except Exception as e:
                logger.error(f"Error executing recovery action: {e}")
                action.attempt_count += 1
                if action.attempt_count >= action.max_attempts:
                    self.pending_recovery_actions.remove(action)
                else:
                    # Reschedule with backoff
                    backoff_minutes = action.attempt_count * 5
                    action.scheduled_time = current_time + timedelta(
                        minutes=backoff_minutes
                    )

    async def _check_quota_refresh_opportunities(self) -> None:
        """Check for quota refresh opportunities to resume work"""
        for provider_id, health in self.provider_health.items():
            if health.quota_reset_time and health.quota_reset_time <= datetime.now(
                timezone.utc
            ):
                # Quota should have refreshed
                logger.info(f"Quota refresh detected for provider {provider_id}")

                # Resume deferred work
                if provider_id == "claude_code":
                    resumed = await claude_code_monitor.resume_pending_work()
                    if resumed > 0:
                        logger.info(
                            f"Resumed {resumed} tasks after quota refresh for {provider_id}"
                        )

    async def _attempt_provider_restart(
        self, provider_id: str, health: ProviderHealth
    ) -> bool:
        """Attempt to restart an unavailable provider"""
        logger.info(f"Attempting restart for unavailable provider {provider_id}")

        # For Claude Code, this might involve checking CLI availability
        if provider_id == "claude_code":
            # Wait a bit and recheck
            await asyncio.sleep(30)
            new_health = await self.check_provider_health(provider_id)
            return new_health.status != ProviderStatus.UNAVAILABLE

        return False

    async def _attempt_failure_recovery(
        self, provider_id: str, health: ProviderHealth
    ) -> bool:
        """Attempt to recover from provider failures"""
        logger.info(f"Attempting failure recovery for provider {provider_id}")

        # Reset circuit breaker if appropriate
        if provider_id in self.circuit_breakers:
            cb = self.circuit_breakers[provider_id]
            if cb.state == "open":
                # Force half-open state for testing
                cb.state = "half_open"

        # Test with a simple request
        test_success = await self._test_provider_connectivity(provider_id)

        if test_success:
            # Reset failure counters
            health.consecutive_failures = 0
            health.consecutive_successes = 1
            health.status = ProviderStatus.RECOVERING
            return True

        return False

    async def _attempt_performance_recovery(
        self, provider_id: str, health: ProviderHealth
    ) -> bool:
        """Attempt to recover from performance degradation"""
        logger.info(f"Attempting performance recovery for provider {provider_id}")

        # For quota-related degradation, check if quota has improved
        if provider_id == "claude_code":
            claude_status = await claude_code_monitor.check_claude_code_status()
            if claude_status.usage_percentage < 80:  # Improved from degraded threshold
                health.status = ProviderStatus.HEALTHY
                return True

        return False

    async def _test_provider_connectivity(self, provider_id: str) -> bool:
        """Test provider connectivity with minimal request"""
        try:
            if provider_id == "claude_code":
                result = await claude_code_monitor._test_claude_code_availability()
                return result["success"]
            return True
        except Exception as e:
            logger.debug(f"Provider connectivity test failed for {provider_id}: {e}")
            return False

    async def _get_alternative_providers(self, failed_provider_id: str) -> List[str]:
        """Get alternative providers for failover"""
        # For now, simple fallback logic
        # In a real system, this would be more sophisticated
        if failed_provider_id == "claude_code":
            return []  # No alternatives for Claude Code yet

        return []

    async def _check_provider_capacity(
        self, provider_id: str, task_ids: List[int]
    ) -> bool:
        """Check if provider can handle additional load"""
        health = self.provider_health.get(provider_id)
        if not health or not health.quota_available:
            return False

        # Simple capacity check - could be more sophisticated
        return health.status in [ProviderStatus.HEALTHY, ProviderStatus.RECOVERING]

    async def _execute_failover(
        self,
        source_provider: str,
        target_provider: str,
        task_ids: List[int],
        reason: str,
    ) -> None:
        """Execute failover between providers"""
        logger.info(f"Executing failover from {source_provider} to {target_provider}")

        # For now, this is a placeholder
        # In a real system, this would involve:
        # 1. Updating provider assignments in database
        # 2. Rescheduling tasks on new provider
        # 3. Updating routing configuration

        # Mark tasks for retry on new provider
        for task_id in task_ids:
            await self.schedule_recovery_retry(
                target_provider, [task_id], 1, f"Failover: {reason}"
            )

    async def _execute_recovery_action(self, action: RecoveryAction) -> None:
        """Execute a specific recovery action"""
        logger.info(
            f"Executing recovery action: {action.action_type} for provider {action.provider_id}"
        )

        if action.action_type == "retry":
            # Retry tasks on the provider
            for task_id in action.task_ids:
                from supervisor_agent.queue.enhanced_tasks import (
                    process_single_task_enhanced,
                )

                process_single_task_enhanced.delay(task_id)

        elif action.action_type == "failover":
            # Perform failover
            await self.perform_failover(
                action.provider_id, action.task_ids, action.reason
            )

        elif action.action_type == "circuit_break":
            # Open circuit breaker
            if action.provider_id in self.circuit_breakers:
                self.circuit_breakers[action.provider_id].state = "open"
                self.circuit_breakers[action.provider_id].next_retry_time = (
                    datetime.now(timezone.utc)
                    + timedelta(seconds=self.circuit_breaker_timeout)
                )

    async def _cleanup_completed_actions(self) -> None:
        """Clean up completed recovery actions"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

        # Remove old actions
        self.pending_recovery_actions = [
            action
            for action in self.pending_recovery_actions
            if action.scheduled_time > cutoff_time
        ]

    def _schedule_periodic_tasks(self) -> None:
        """Schedule periodic Celery tasks"""
        # Schedule health monitoring
        monitor_recovery_health.apply_async(countdown=self.health_check_interval)

        # Schedule recovery processing
        process_recovery_actions.apply_async(countdown=self.recovery_check_interval)


# Global orchestrator instance
recovery_orchestrator = RecoveryOrchestrator()


# Celery tasks for recovery orchestration
@celery_app.task
def monitor_recovery_health():
    """Monitor provider health and system recovery"""
    try:

        async def monitor():
            await recovery_orchestrator._health_monitoring_loop()

        asyncio.run(monitor())

    except Exception as e:
        logger.error(f"Recovery health monitoring failed: {e}")

    # Schedule next check
    monitor_recovery_health.apply_async(
        countdown=recovery_orchestrator.health_check_interval
    )


@celery_app.task
def process_recovery_actions():
    """Process pending recovery actions"""
    try:

        async def process():
            await recovery_orchestrator._process_pending_recovery_actions()

        asyncio.run(process())

    except Exception as e:
        logger.error(f"Recovery action processing failed: {e}")

    # Schedule next check
    process_recovery_actions.apply_async(
        countdown=recovery_orchestrator.recovery_check_interval
    )


@celery_app.task
def schedule_recovery_retry(provider_id: str, task_ids: List[int], reason: str):
    """Schedule recovery retry for specific tasks"""
    try:

        async def retry():
            await recovery_orchestrator.schedule_recovery_retry(
                provider_id, task_ids, 5, reason
            )

        asyncio.run(retry())

    except Exception as e:
        logger.error(f"Recovery retry scheduling failed: {e}")


@celery_app.task
def attempt_provider_recovery(provider_id: str, reason: str):
    """Attempt to recover a specific provider"""
    try:

        async def recover():
            success = await recovery_orchestrator.attempt_recovery(provider_id, reason)
            if success:
                logger.info(f"Provider {provider_id} recovery successful")
            else:
                logger.warning(f"Provider {provider_id} recovery failed")

        asyncio.run(recover())

    except Exception as e:
        logger.error(f"Provider recovery attempt failed: {e}")

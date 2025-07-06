"""
Claude Code Subscription Monitor

Monitors Claude Code CLI subscription usage and ensures work continuity:
- Tracks Claude Code subscription limits and usage patterns
- Detects when subscription limit will be hit soon  
- Automatically defers work when approaching/hitting limits
- Schedules work resumption when subscription refreshes
- Maintains persistent task queue for seamless continuity
- Intelligent retry scheduling based on subscription reset times
"""

import asyncio
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import deque

from celery import Celery
from sqlalchemy.orm import Session

from supervisor_agent.config import settings
from supervisor_agent.core.advanced_usage_predictor import AdvancedUsagePredictor
from supervisor_agent.db import crud
from supervisor_agent.db.database import get_db
from supervisor_agent.db.enums import TaskStatus
from supervisor_agent.queue.celery_app import celery_app
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeCodeLimitStatus(str, Enum):
    """Claude Code subscription limit status"""
    AVAILABLE = "available"        # Normal operation, plenty of quota
    APPROACHING = "approaching"    # Getting close to limits (70-85%)
    NEAR_LIMIT = "near_limit"     # Very close to limits (85-95%)
    LIMIT_HIT = "limit_hit"       # At or over limits (95%+)
    UNKNOWN = "unknown"           # Cannot determine status


@dataclass
class ClaudeCodeUsage:
    """Claude Code subscription usage information"""
    requests_made: int
    requests_limit: int
    usage_percentage: float
    reset_time: Optional[datetime]
    time_to_reset_hours: float
    last_successful_request: Optional[datetime]
    consecutive_failures: int
    error_patterns: List[str]
    
    @property
    def is_available(self) -> bool:
        return self.usage_percentage < 95.0 and self.consecutive_failures < 3


@dataclass
class PendingWork:
    """Work item waiting for subscription refresh"""
    work_id: str
    work_type: str
    payload: Dict[str, Any]
    priority: int  # 1=high, 2=medium, 3=low
    created_at: datetime
    retry_after: datetime
    max_retries: int
    retry_count: int
    reason_deferred: str


class ClaudeCodeSubscriptionMonitor:
    """Monitor Claude Code subscription and manage work continuity"""
    
    def __init__(
        self,
        check_interval_seconds: int = 300,  # Check every 5 minutes
        usage_tracking_window_hours: int = 24,  # Track usage over 24 hours
        emergency_threshold: float = 95.0,  # Emergency stop at 95%
        warning_threshold: float = 85.0,    # Warning at 85%
        max_pending_work_items: int = 500,
    ):
        self.check_interval_seconds = check_interval_seconds
        self.usage_tracking_window_hours = usage_tracking_window_hours
        self.emergency_threshold = emergency_threshold
        self.warning_threshold = warning_threshold
        self.max_pending_work_items = max_pending_work_items
        
        # Usage tracking
        self.usage_history: deque = deque(maxlen=1000)
        self.current_usage: Optional[ClaudeCodeUsage] = None
        self.usage_predictor = AdvancedUsagePredictor()
        
        # Work management
        self.pending_work: List[PendingWork] = []
        self.work_deferred_count: int = 0
        self.work_resumed_count: int = 0
        
        # Monitoring state
        self.is_monitoring: bool = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.last_limit_check: Optional[datetime] = None
        
        # Claude Code specific patterns
        self.known_limit_errors = [
            "rate limit exceeded",
            "quota exceeded", 
            "too many requests",
            "subscription limit",
            "monthly usage limit",
            "usage cap reached",
            "anthropic api rate limit",
            "billing limit reached"
        ]
        
        logger.info("Claude Code subscription monitor initialized")
    
    async def start_monitoring(self) -> None:
        """Start monitoring Claude Code subscription"""
        if self.is_monitoring:
            logger.warning("Claude Code monitoring already started")
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        # Start periodic tasks
        self._schedule_periodic_tasks()
        
        logger.info("Started Claude Code subscription monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop monitoring"""
        self.is_monitoring = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped Claude Code subscription monitoring")
    
    async def check_claude_code_status(self) -> ClaudeCodeUsage:
        """Check current Claude Code subscription status"""
        try:
            # Try a simple test command to check status
            result = await self._test_claude_code_availability()
            
            if result["success"]:
                # Successful request
                usage = ClaudeCodeUsage(
                    requests_made=self._estimate_requests_made(),
                    requests_limit=self._estimate_requests_limit(),
                    usage_percentage=self._calculate_usage_percentage(),
                    reset_time=self._estimate_reset_time(),
                    time_to_reset_hours=self._calculate_time_to_reset(),
                    last_successful_request=datetime.now(timezone.utc),
                    consecutive_failures=0,
                    error_patterns=[]
                )
            else:
                # Failed request - analyze error
                error_msg = result.get("error", "").lower()
                is_limit_error = any(pattern in error_msg for pattern in self.known_limit_errors)
                
                if is_limit_error:
                    # Subscription limit hit
                    usage = ClaudeCodeUsage(
                        requests_made=self._estimate_requests_made(),
                        requests_limit=self._estimate_requests_limit(),
                        usage_percentage=100.0,  # Assume at limit
                        reset_time=self._estimate_reset_time(),
                        time_to_reset_hours=self._calculate_time_to_reset(),
                        last_successful_request=self.current_usage.last_successful_request if self.current_usage else None,
                        consecutive_failures=(self.current_usage.consecutive_failures + 1) if self.current_usage else 1,
                        error_patterns=[error_msg] if error_msg else []
                    )
                else:
                    # Other error - assume temporary
                    usage = ClaudeCodeUsage(
                        requests_made=self._estimate_requests_made(),
                        requests_limit=self._estimate_requests_limit(),
                        usage_percentage=self.current_usage.usage_percentage if self.current_usage else 50.0,
                        reset_time=self._estimate_reset_time(),
                        time_to_reset_hours=self._calculate_time_to_reset(),
                        last_successful_request=self.current_usage.last_successful_request if self.current_usage else None,
                        consecutive_failures=(self.current_usage.consecutive_failures + 1) if self.current_usage else 1,
                        error_patterns=[error_msg] if error_msg else []
                    )
            
            self.current_usage = usage
            self.last_limit_check = datetime.now(timezone.utc)
            
            # Record usage for prediction
            await self.usage_predictor.record_usage(
                task_type="claude_code_status_check",
                tokens_used=1,  # Minimal usage for status check
                processing_time=1.0,
                provider_id="claude_code",
                success=result["success"]
            )
            
            return usage
            
        except Exception as e:
            logger.error(f"Error checking Claude Code status: {e}")
            
            # Return conservative status
            return ClaudeCodeUsage(
                requests_made=0,
                requests_limit=1000,  # Conservative estimate
                usage_percentage=90.0,  # Assume near limit on error
                reset_time=datetime.now(timezone.utc) + timedelta(hours=1),
                time_to_reset_hours=1.0,
                last_successful_request=None,
                consecutive_failures=10,
                error_patterns=[str(e)]
            )
    
    async def should_defer_work(self, work_type: str, priority: int = 3) -> Tuple[bool, str]:
        """Check if work should be deferred due to subscription limits"""
        if not self.current_usage:
            # No usage data - be conservative
            return True, "No subscription usage data available"
        
        # Check if limits are hit
        if not self.current_usage.is_available:
            return True, f"Claude Code subscription unavailable ({self.current_usage.usage_percentage:.1f}% used)"
        
        # Check usage level
        if self.current_usage.usage_percentage >= self.emergency_threshold:
            return True, f"Emergency threshold reached ({self.current_usage.usage_percentage:.1f}%)"
        
        # Check consecutive failures
        if self.current_usage.consecutive_failures >= 3:
            return True, f"Multiple consecutive failures ({self.current_usage.consecutive_failures})"
        
        # Check priority vs usage level
        if self.current_usage.usage_percentage >= self.warning_threshold:
            if priority > 2:  # Only high/medium priority allowed
                return True, f"Low priority work deferred at {self.current_usage.usage_percentage:.1f}% usage"
        
        # Predict if this work would push us over the limit
        try:
            prediction = await self.usage_predictor.predict_usage(
                provider_id="claude_code",
                horizon_minutes=60,  # 1 hour horizon
                task_type=work_type
            )
            
            estimated_usage_increase = prediction.predicted_value / 100  # Convert to percentage
            projected_usage = self.current_usage.usage_percentage + estimated_usage_increase
            
            if projected_usage >= self.emergency_threshold:
                return True, f"Work would push usage to {projected_usage:.1f}% (over {self.emergency_threshold}% threshold)"
        
        except Exception as e:
            logger.warning(f"Usage prediction failed: {e}")
            # Conservative approach on prediction failure
            if self.current_usage.usage_percentage >= 80.0:
                return True, "Conservative deferral due to prediction failure"
        
        return False, "Subscription available"
    
    async def defer_work(
        self,
        work_id: str,
        work_type: str,
        payload: Dict[str, Any],
        priority: int = 3,
        max_retries: int = 10
    ) -> bool:
        """Defer work until subscription is available"""
        try:
            # Check if we're already at max pending work
            if len(self.pending_work) >= self.max_pending_work_items:
                logger.warning(f"Max pending work items reached ({self.max_pending_work_items})")
                # Remove oldest low-priority items to make space
                self.pending_work = [w for w in self.pending_work if w.priority <= 2] + self.pending_work[-self.max_pending_work_items//2:]
            
            # Calculate retry time
            retry_after = self._calculate_retry_time(priority)
            
            # Create pending work item
            pending_work = PendingWork(
                work_id=work_id,
                work_type=work_type,
                payload=payload,
                priority=priority,
                created_at=datetime.now(timezone.utc),
                retry_after=retry_after,
                max_retries=max_retries,
                retry_count=0,
                reason_deferred=f"Claude Code usage at {self.current_usage.usage_percentage:.1f}%" if self.current_usage else "Subscription limit"
            )
            
            # Add to pending queue (maintain priority order)
            self.pending_work.append(pending_work)
            self.pending_work.sort(key=lambda w: (w.priority, w.created_at))
            
            self.work_deferred_count += 1
            
            logger.info(
                f"Deferred work {work_id} ({work_type}) until {retry_after}. "
                f"Reason: {pending_work.reason_deferred}"
            )
            
            # Schedule retry
            self._schedule_work_retry(work_id, retry_after)
            
            return True
            
        except Exception as e:
            logger.error(f"Error deferring work {work_id}: {e}")
            return False
    
    async def resume_pending_work(self) -> int:
        """Resume pending work when subscription becomes available"""
        if not self.pending_work:
            return 0
        
        # Check if subscription is available
        current_status = await self.check_claude_code_status()
        if not current_status.is_available:
            logger.debug("Claude Code subscription still unavailable")
            return 0
        
        resumed_count = 0
        current_time = datetime.now(timezone.utc)
        
        # Process work in priority order
        work_to_process = []
        for work in self.pending_work:
            if current_time >= work.retry_after:
                work_to_process.append(work)
        
        # Estimate available capacity
        available_capacity_pct = 100.0 - current_status.usage_percentage
        estimated_work_capacity = max(1, int(available_capacity_pct / 10))  # Conservative estimate
        
        # Resume high priority work first
        for work in work_to_process[:estimated_work_capacity]:
            try:
                success = await self._resume_work_item(work)
                if success:
                    self.pending_work.remove(work)
                    resumed_count += 1
                    self.work_resumed_count += 1
                else:
                    # Failed to resume - increment retry count
                    work.retry_count += 1
                    if work.retry_count >= work.max_retries:
                        logger.warning(f"Work {work.work_id} exceeded max retries, removing")
                        self.pending_work.remove(work)
                    else:
                        # Schedule next retry with backoff
                        work.retry_after = current_time + timedelta(minutes=work.retry_count * 10)
                        logger.info(f"Work {work.work_id} failed to resume, retry {work.retry_count}/{work.max_retries}")
                
            except Exception as e:
                logger.error(f"Error resuming work {work.work_id}: {e}")
        
        if resumed_count > 0:
            logger.info(f"Resumed {resumed_count} deferred work items")
        
        return resumed_count
    
    async def get_subscription_status(self) -> Dict[str, Any]:
        """Get comprehensive subscription status"""
        current_time = datetime.now(timezone.utc)
        
        status = {
            "is_monitoring": self.is_monitoring,
            "last_check": self.last_limit_check.isoformat() if self.last_limit_check else None,
            "check_interval_seconds": self.check_interval_seconds,
            "statistics": {
                "work_deferred_count": self.work_deferred_count,
                "work_resumed_count": self.work_resumed_count,
                "pending_work_items": len(self.pending_work),
            },
            "subscription_usage": None,
            "pending_work_summary": {},
            "predictions": None,
        }
        
        # Current usage
        if self.current_usage:
            status["subscription_usage"] = {
                "requests_made": self.current_usage.requests_made,
                "requests_limit": self.current_usage.requests_limit,
                "usage_percentage": self.current_usage.usage_percentage,
                "is_available": self.current_usage.is_available,
                "reset_time": self.current_usage.reset_time.isoformat() if self.current_usage.reset_time else None,
                "time_to_reset_hours": self.current_usage.time_to_reset_hours,
                "consecutive_failures": self.current_usage.consecutive_failures,
                "last_successful_request": self.current_usage.last_successful_request.isoformat() if self.current_usage.last_successful_request else None,
            }
        
        # Pending work summary
        if self.pending_work:
            by_priority = {}
            by_type = {}
            
            for work in self.pending_work:
                # Group by priority
                priority_key = f"priority_{work.priority}"
                by_priority[priority_key] = by_priority.get(priority_key, 0) + 1
                
                # Group by type
                by_type[work.work_type] = by_type.get(work.work_type, 0) + 1
            
            status["pending_work_summary"] = {
                "total_items": len(self.pending_work),
                "by_priority": by_priority,
                "by_type": by_type,
                "oldest_item": min(self.pending_work, key=lambda w: w.created_at).created_at.isoformat(),
                "next_retry": min(self.pending_work, key=lambda w: w.retry_after).retry_after.isoformat(),
            }
        
        # Usage predictions
        try:
            if self.current_usage and self.current_usage.is_available:
                prediction = await self.usage_predictor.predict_usage(
                    provider_id="claude_code",
                    horizon_minutes=120  # 2 hour prediction
                )
                
                status["predictions"] = {
                    "predicted_usage_2h": prediction.predicted_value,
                    "confidence_level": prediction.confidence_level,
                    "model_used": prediction.model_used,
                }
                
        except Exception as e:
            logger.debug(f"Could not generate predictions: {e}")
        
        return status
    
    # Private methods
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        logger.info("Started Claude Code subscription monitoring loop")
        
        while self.is_monitoring:
            try:
                # Check subscription status
                await self.check_claude_code_status()
                
                # Resume pending work if possible
                await self.resume_pending_work()
                
                # Cleanup old work items
                await self._cleanup_old_work()
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            # Wait for next check
            await asyncio.sleep(self.check_interval_seconds)
        
        logger.info("Exited Claude Code subscription monitoring loop")
    
    async def _test_claude_code_availability(self) -> Dict[str, Any]:
        """Test Claude Code availability with a minimal request"""
        try:
            # Use a simple command that uses minimal quota
            test_command = ["claude", "--help"]
            
            # Set timeout to prevent hanging
            process = await asyncio.create_subprocess_exec(
                *test_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=30  # 30 second timeout
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {"success": True, "output": stdout.decode()}
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                return {"success": False, "error": error_msg}
                
        except asyncio.TimeoutError:
            return {"success": False, "error": "Claude Code command timed out"}
        except FileNotFoundError:
            return {"success": False, "error": "Claude Code CLI not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _estimate_requests_made(self) -> int:
        """Estimate number of requests made in current period"""
        # This is a simplified estimation
        # In practice, you'd track actual API calls
        if self.current_usage:
            return self.current_usage.requests_made
        return 0
    
    def _estimate_requests_limit(self) -> int:
        """Estimate request limit for current subscription"""
        # This would need to be configured based on actual subscription
        # For now, use a conservative estimate
        return 1000  # Adjust based on actual Claude Code subscription limits
    
    def _calculate_usage_percentage(self) -> float:
        """Calculate current usage percentage"""
        requests_made = self._estimate_requests_made()
        requests_limit = self._estimate_requests_limit()
        
        if requests_limit <= 0:
            return 0.0
        
        return min(100.0, (requests_made / requests_limit) * 100.0)
    
    def _estimate_reset_time(self) -> datetime:
        """Estimate when subscription will reset"""
        # Most subscriptions reset daily or monthly
        # For now, assume daily reset at midnight UTC
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return tomorrow
    
    def _calculate_time_to_reset(self) -> float:
        """Calculate hours until subscription resets"""
        reset_time = self._estimate_reset_time()
        now = datetime.now(timezone.utc)
        return max(0.0, (reset_time - now).total_seconds() / 3600)
    
    def _calculate_retry_time(self, priority: int) -> datetime:
        """Calculate when to retry based on priority and reset time"""
        reset_time = self._estimate_reset_time()
        now = datetime.now(timezone.utc)
        
        # High priority work retries sooner after reset
        if priority == 1:  # High priority
            retry_delay = timedelta(minutes=5)
        elif priority == 2:  # Medium priority  
            retry_delay = timedelta(minutes=15)
        else:  # Low priority
            retry_delay = timedelta(minutes=30)
        
        return reset_time + retry_delay
    
    def _schedule_periodic_tasks(self) -> None:
        """Schedule periodic Celery tasks"""
        # Schedule monitoring
        monitor_claude_code_subscription.apply_async(countdown=self.check_interval_seconds)
        
        # Schedule work resumption checks
        resume_claude_code_work.apply_async(countdown=60)  # Check every minute
    
    def _schedule_work_retry(self, work_id: str, retry_time: datetime) -> None:
        """Schedule work retry at specific time"""
        countdown = max(0, int((retry_time - datetime.now(timezone.utc)).total_seconds()))
        
        # Schedule retry task
        retry_claude_code_work.apply_async(
            args=[work_id], 
            countdown=countdown
        )
        
        logger.debug(f"Scheduled work {work_id} retry in {countdown} seconds")
    
    async def _resume_work_item(self, work: PendingWork) -> bool:
        """Resume a specific work item"""
        try:
            # Check if subscription is still available
            should_defer, reason = await self.should_defer_work(work.work_type, work.priority)
            if should_defer:
                logger.debug(f"Work {work.work_id} still needs to be deferred: {reason}")
                return False
            
            # Execute the work based on type
            if work.work_type == "task_processing":
                # Resume task processing
                task_id = work.payload.get("task_id")
                if task_id:
                    from supervisor_agent.queue.enhanced_tasks import process_single_task_enhanced
                    process_single_task_enhanced.delay(task_id)
                    return True
            
            elif work.work_type == "batch_processing":
                # Resume batch processing  
                task_ids = work.payload.get("task_ids", [])
                if task_ids:
                    from supervisor_agent.queue.enhanced_tasks import process_task_batch_enhanced
                    process_task_batch_enhanced.delay(task_ids)
                    return True
            
            # Add other work types as needed
            
            logger.warning(f"Unknown work type: {work.work_type}")
            return False
            
        except Exception as e:
            logger.error(f"Error resuming work {work.work_id}: {e}")
            return False
    
    async def _cleanup_old_work(self) -> None:
        """Clean up old pending work items"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # Remove work items that are too old
        initial_count = len(self.pending_work)
        self.pending_work = [
            work for work in self.pending_work
            if work.created_at > cutoff_time
        ]
        
        removed_count = initial_count - len(self.pending_work)
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old pending work items")


# Global monitor instance
claude_code_monitor = ClaudeCodeSubscriptionMonitor()


# Celery tasks for Claude Code subscription monitoring
@celery_app.task
def monitor_claude_code_subscription():
    """Monitor Claude Code subscription status"""
    try:
        asyncio.run(claude_code_monitor._monitoring_loop())
    except Exception as e:
        logger.error(f"Claude Code subscription monitoring failed: {e}")
    
    # Schedule next check
    monitor_claude_code_subscription.apply_async(
        countdown=claude_code_monitor.check_interval_seconds
    )


@celery_app.task  
def resume_claude_code_work():
    """Resume deferred Claude Code work"""
    try:
        async def resume():
            resumed = await claude_code_monitor.resume_pending_work()
            if resumed > 0:
                logger.info(f"Claude Code: Resumed {resumed} work items")
        
        asyncio.run(resume())
        
    except Exception as e:
        logger.error(f"Claude Code work resumption failed: {e}")
    
    # Schedule next check
    resume_claude_code_work.apply_async(countdown=60)


@celery_app.task
def retry_claude_code_work(work_id: str):
    """Retry specific Claude Code work item"""
    try:
        async def retry():
            # Find the work item
            work_item = None
            for work in claude_code_monitor.pending_work:
                if work.work_id == work_id:
                    work_item = work
                    break
            
            if work_item:
                success = await claude_code_monitor._resume_work_item(work_item)
                if success:
                    claude_code_monitor.pending_work.remove(work_item)
                    logger.info(f"Successfully retried work {work_id}")
                else:
                    logger.debug(f"Work {work_id} retry deferred")
            else:
                logger.warning(f"Work {work_id} not found for retry")
        
        asyncio.run(retry())
        
    except Exception as e:
        logger.error(f"Claude Code work retry failed for {work_id}: {e}")
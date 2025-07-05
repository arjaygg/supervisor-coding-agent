"""
Workflow Scheduler

Implements cron-style scheduling for workflows with timezone support,
next run calculation, and schedule management capabilities.

Follows SOLID principles and integrates with workflow engine.
"""

import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import pytz
from croniter import croniter
from sqlalchemy import and_
from sqlalchemy.orm import Session

from supervisor_agent.core.workflow_engine import WorkflowEngine
from supervisor_agent.core.workflow_models import (
    ScheduleStatus,
    Workflow,
    WorkflowSchedule,
)
from supervisor_agent.db.database import SessionLocal
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class SchedulingError(Exception):
    """Raised when scheduling operations fail"""

    pass


class CronValidator:
    """Validates cron expressions and provides parsing utilities"""

    # Standard cron expression pattern (5 fields)
    CRON_PATTERN = re.compile(
        r"^(\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])|\*\/([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9]))\s+"  # minute
        r"(\*|([0-9]|1[0-9]|2[0-3])|\*\/([0-9]|1[0-9]|2[0-3]))\s+"  # hour
        r"(\*|([1-9]|1[0-9]|2[0-9]|3[0-1])|\*\/([1-9]|1[0-9]|2[0-9]|3[0-1]))\s+"  # day
        r"(\*|([1-9]|1[0-2])|\*\/([1-9]|1[0-2]))\s+"  # month
        r"(\*|([0-6])|\*\/[0-6])$"  # day of week
    )

    # Named expressions for common patterns
    NAMED_EXPRESSIONS = {
        "@yearly": "0 0 1 1 *",
        "@annually": "0 0 1 1 *",
        "@monthly": "0 0 1 * *",
        "@weekly": "0 0 * * 0",
        "@daily": "0 0 * * *",
        "@midnight": "0 0 * * *",
        "@hourly": "0 * * * *",
        "@reboot": None,  # Special case, not supported in standard cron
        "weekdays": "0 9 * * 1-5",
        "weekends": "0 9 * * 0,6",
        "month-end": "0 0 28-31 * *",
    }

    @classmethod
    def validate_expression(cls, expression: str) -> Tuple[bool, str]:
        """Validate cron expression format"""

        # Handle named expressions
        if expression.startswith("@") or expression in cls.NAMED_EXPRESSIONS:
            if expression == "@reboot":
                return False, "@reboot is not supported"

            canonical = cls.NAMED_EXPRESSIONS.get(expression, expression)
            if canonical is None:
                return False, f"Unsupported named expression: {expression}"

            expression = canonical

        # Validate using croniter
        try:
            croniter(expression)
            return True, ""
        except (ValueError, TypeError) as e:
            return False, f"Invalid cron expression: {str(e)}"

    @classmethod
    def get_next_run_time(
        cls,
        expression: str,
        from_time: datetime = None,
        timezone_str: str = "UTC",
    ) -> datetime:
        """Calculate next run time for cron expression"""

        # Convert named expressions
        if expression.startswith("@") or expression in cls.NAMED_EXPRESSIONS:
            expression = cls.NAMED_EXPRESSIONS.get(expression, expression)

        # Set timezone
        tz = pytz.timezone(timezone_str)

        # Use current time if not specified
        if from_time is None:
            from_time = datetime.now(tz)
        elif from_time.tzinfo is None:
            from_time = tz.localize(from_time)
        else:
            from_time = from_time.astimezone(tz)

        # Calculate next run
        cron = croniter(expression, from_time)
        next_run = cron.get_next(datetime)

        # Convert back to UTC for storage
        return next_run.astimezone(timezone.utc)

    @classmethod
    def get_description(cls, expression: str) -> str:
        """Get human-readable description of cron expression"""

        # Handle named expressions
        descriptions = {
            "@yearly": "Once a year (January 1st at midnight)",
            "@annually": "Once a year (January 1st at midnight)",
            "@monthly": "Once a month (1st day at midnight)",
            "@weekly": "Once a week (Sunday at midnight)",
            "@daily": "Once a day (at midnight)",
            "@midnight": "Once a day (at midnight)",
            "@hourly": "Once an hour (at the beginning of the hour)",
            "weekdays": "Weekdays at 9 AM",
            "weekends": "Weekends at 9 AM",
            "month-end": "End of month at midnight",
        }

        if expression in descriptions:
            return descriptions[expression]

        # For custom expressions, provide basic parsing
        # In a production system, you might want to use a library like cron-descriptor
        return f"Custom schedule: {expression}"


class WorkflowScheduler:
    """
    Manages workflow scheduling with cron-style expressions.

    Provides scheduling, execution management, and schedule lifecycle operations.
    """

    def __init__(self, workflow_engine: WorkflowEngine):
        self.workflow_engine = workflow_engine
        self._scheduler_running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._schedule_check_interval = 60  # Check every minute

    async def create_schedule(
        self,
        workflow_id: str,
        name: str,
        cron_expression: str,
        timezone_str: str = "UTC",
        created_by: str = None,
    ) -> str:
        """Create a new workflow schedule"""

        logger.info(f"Creating schedule '{name}' for workflow {workflow_id}")

        # Validate cron expression
        is_valid, error_msg = CronValidator.validate_expression(
            cron_expression
        )
        if not is_valid:
            raise SchedulingError(f"Invalid cron expression: {error_msg}")

        # Validate timezone
        try:
            pytz.timezone(timezone_str)
        except pytz.UnknownTimeZoneError:
            raise SchedulingError(f"Unknown timezone: {timezone_str}")

        # Check if workflow exists
        with SessionLocal() as db:
            workflow = (
                db.query(Workflow).filter(Workflow.id == workflow_id).first()
            )
            if not workflow:
                raise SchedulingError(f"Workflow not found: {workflow_id}")

            if not workflow.is_active:
                raise SchedulingError(
                    f"Cannot schedule inactive workflow: {workflow_id}"
                )

            # Calculate next run time
            next_run_at = CronValidator.get_next_run_time(
                cron_expression, None, timezone_str
            )

            # Create schedule record
            schedule_id = str(uuid.uuid4())
            schedule = WorkflowSchedule(
                id=schedule_id,
                workflow_id=workflow_id,
                name=name,
                cron_expression=cron_expression,
                timezone=timezone_str,
                next_run_at=next_run_at,
                status=ScheduleStatus.ACTIVE,
                created_by=created_by,
            )

            db.add(schedule)
            db.commit()

            logger.info(
                f"Schedule created: {schedule_id}, next run: {next_run_at}"
            )
            return schedule_id

    async def update_schedule(self, schedule_id: str, **updates) -> bool:
        """Update an existing schedule"""

        logger.info(f"Updating schedule: {schedule_id}")

        with SessionLocal() as db:
            schedule = (
                db.query(WorkflowSchedule)
                .filter(WorkflowSchedule.id == schedule_id)
                .first()
            )

            if not schedule:
                raise SchedulingError(f"Schedule not found: {schedule_id}")

            # Validate updates
            if "cron_expression" in updates:
                is_valid, error_msg = CronValidator.validate_expression(
                    updates["cron_expression"]
                )
                if not is_valid:
                    raise SchedulingError(
                        f"Invalid cron expression: {error_msg}"
                    )

            if "timezone" in updates:
                try:
                    pytz.timezone(updates["timezone"])
                except pytz.UnknownTimeZoneError:
                    raise SchedulingError(
                        f"Unknown timezone: {updates['timezone']}"
                    )

            # Apply updates
            for key, value in updates.items():
                if hasattr(schedule, key):
                    setattr(schedule, key, value)

            # Recalculate next run time if schedule details changed
            if "cron_expression" in updates or "timezone" in updates:
                schedule.next_run_at = CronValidator.get_next_run_time(
                    schedule.cron_expression, None, schedule.timezone
                )

            schedule.updated_at = datetime.now(timezone.utc)
            db.commit()

            logger.info(f"Schedule updated: {schedule_id}")
            return True

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule"""

        logger.info(f"Deleting schedule: {schedule_id}")

        with SessionLocal() as db:
            schedule = (
                db.query(WorkflowSchedule)
                .filter(WorkflowSchedule.id == schedule_id)
                .first()
            )

            if not schedule:
                return False

            db.delete(schedule)
            db.commit()

            logger.info(f"Schedule deleted: {schedule_id}")
            return True

    async def pause_schedule(self, schedule_id: str) -> bool:
        """Pause a schedule"""
        return await self.update_schedule(
            schedule_id, status=ScheduleStatus.PAUSED
        )

    async def resume_schedule(self, schedule_id: str) -> bool:
        """Resume a paused schedule"""
        return await self.update_schedule(
            schedule_id, status=ScheduleStatus.ACTIVE
        )

    async def get_schedule(self, schedule_id: str) -> Optional[Dict]:
        """Get schedule details"""

        with SessionLocal() as db:
            schedule = (
                db.query(WorkflowSchedule)
                .filter(WorkflowSchedule.id == schedule_id)
                .first()
            )

            if not schedule:
                return None

            return {
                "id": schedule.id,
                "workflow_id": schedule.workflow_id,
                "name": schedule.name,
                "cron_expression": schedule.cron_expression,
                "description": CronValidator.get_description(
                    schedule.cron_expression
                ),
                "timezone": schedule.timezone,
                "status": schedule.status.value,
                "next_run_at": (
                    schedule.next_run_at.isoformat()
                    if schedule.next_run_at
                    else None
                ),
                "last_run_at": (
                    schedule.last_run_at.isoformat()
                    if schedule.last_run_at
                    else None
                ),
                "created_by": schedule.created_by,
                "created_at": schedule.created_at.isoformat(),
                "updated_at": (
                    schedule.updated_at.isoformat()
                    if schedule.updated_at
                    else None
                ),
            }

    async def list_schedules(
        self, workflow_id: str = None, status: ScheduleStatus = None
    ) -> List[Dict]:
        """List schedules with optional filtering"""

        with SessionLocal() as db:
            query = db.query(WorkflowSchedule)

            if workflow_id:
                query = query.filter(
                    WorkflowSchedule.workflow_id == workflow_id
                )

            if status:
                query = query.filter(WorkflowSchedule.status == status)

            schedules = query.all()

            return [
                {
                    "id": schedule.id,
                    "workflow_id": schedule.workflow_id,
                    "name": schedule.name,
                    "cron_expression": schedule.cron_expression,
                    "description": CronValidator.get_description(
                        schedule.cron_expression
                    ),
                    "timezone": schedule.timezone,
                    "status": schedule.status.value,
                    "next_run_at": (
                        schedule.next_run_at.isoformat()
                        if schedule.next_run_at
                        else None
                    ),
                    "last_run_at": (
                        schedule.last_run_at.isoformat()
                        if schedule.last_run_at
                        else None
                    ),
                    "created_by": schedule.created_by,
                }
                for schedule in schedules
            ]

    async def start_scheduler(self):
        """Start the background scheduler"""

        if self._scheduler_running:
            logger.warning("Scheduler is already running")
            return

        logger.info("Starting workflow scheduler")
        self._scheduler_running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop_scheduler(self):
        """Stop the background scheduler"""

        if not self._scheduler_running:
            return

        logger.info("Stopping workflow scheduler")
        self._scheduler_running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None

    async def _scheduler_loop(self):
        """Main scheduler loop"""

        logger.info("Scheduler loop started")

        try:
            while self._scheduler_running:
                await self._check_and_execute_schedules()
                await asyncio.sleep(self._schedule_check_interval)
        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled")
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
        finally:
            logger.info("Scheduler loop stopped")

    async def _check_and_execute_schedules(self):
        """Check for due schedules and execute them"""

        current_time = datetime.now(timezone.utc)

        with SessionLocal() as db:
            # Get all active schedules that are due
            due_schedules = (
                db.query(WorkflowSchedule)
                .filter(
                    and_(
                        WorkflowSchedule.status == ScheduleStatus.ACTIVE,
                        WorkflowSchedule.next_run_at <= current_time,
                    )
                )
                .all()
            )

            for schedule in due_schedules:
                try:
                    await self._execute_scheduled_workflow(schedule, db)
                except Exception as e:
                    logger.error(
                        f"Failed to execute scheduled workflow {schedule.id}: {e}"
                    )

    async def _execute_scheduled_workflow(
        self, schedule: WorkflowSchedule, db: Session
    ):
        """Execute a scheduled workflow"""

        logger.info(
            f"Executing scheduled workflow: {schedule.workflow_id} (schedule: {schedule.id})"
        )

        try:
            # Execute workflow
            execution_id = await self.workflow_engine.execute_workflow(
                workflow_id=schedule.workflow_id,
                context={"triggered_by_schedule": schedule.id},
                triggered_by=f"schedule:{schedule.id}",
            )

            # Update schedule with last run time and calculate next run
            schedule.last_run_at = datetime.now(timezone.utc)
            schedule.next_run_at = CronValidator.get_next_run_time(
                schedule.cron_expression,
                schedule.last_run_at,
                schedule.timezone,
            )

            db.commit()

            logger.info(
                f"Scheduled workflow executed: {execution_id}, next run: {schedule.next_run_at}"
            )

        except Exception as e:
            logger.error(
                f"Failed to execute scheduled workflow {schedule.workflow_id}: {e}"
            )
            # Don't update schedule on failure - will retry next cycle
            raise

    async def force_schedule_execution(self, schedule_id: str) -> str:
        """Manually trigger a scheduled workflow"""

        logger.info(f"Manually triggering schedule: {schedule_id}")

        with SessionLocal() as db:
            schedule = (
                db.query(WorkflowSchedule)
                .filter(WorkflowSchedule.id == schedule_id)
                .first()
            )

            if not schedule:
                raise SchedulingError(f"Schedule not found: {schedule_id}")

            # Execute workflow
            execution_id = await self.workflow_engine.execute_workflow(
                workflow_id=schedule.workflow_id,
                context={
                    "triggered_by_schedule": schedule.id,
                    "manual_trigger": True,
                },
                triggered_by=f"manual_schedule:{schedule.id}",
            )

            logger.info(
                f"Manually triggered workflow execution: {execution_id}"
            )
            return execution_id

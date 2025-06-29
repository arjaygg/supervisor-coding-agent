from celery import Celery

from supervisor_agent.config import settings

# Create Celery app instance
celery_app = Celery(
    "supervisor_agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["supervisor_agent.queue.tasks"],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Periodic tasks configuration
celery_app.conf.beat_schedule = {
    "batch-tasks": {
        "task": "supervisor_agent.queue.tasks.batch_and_process_tasks",
        "schedule": settings.batch_interval_seconds,
    },
    "cleanup-expired-cache": {
        "task": "supervisor_agent.queue.tasks.cleanup_expired_cache",
        "schedule": 3600.0,  # Every hour
    },
    "health-check": {
        "task": "supervisor_agent.queue.tasks.health_check_task",
        "schedule": 300.0,  # Every 5 minutes
    },
}

if __name__ == "__main__":
    celery_app.start()

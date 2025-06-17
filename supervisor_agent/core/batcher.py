import json
import hashlib
from typing import List, Dict, Any, Set
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from supervisor_agent.db.models import Task, TaskStatus
from supervisor_agent.db.crud import TaskCRUD
from supervisor_agent.config import settings
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class TaskBatcher:
    def __init__(self):
        self.batch_size = settings.batch_size
        self.deduplication_window_hours = 24

    def get_batchable_tasks(self, db: Session) -> List[List[Task]]:
        pending_tasks = TaskCRUD.get_pending_tasks(db, limit=self.batch_size * 3)

        if not pending_tasks:
            return []

        # Group tasks by type and priority
        task_groups = self._group_tasks_by_type_and_priority(pending_tasks)

        # Create batches within each group
        batches = []
        for group_tasks in task_groups.values():
            group_batches = self._create_batches_from_group(db, group_tasks)
            batches.extend(group_batches)

        # Sort batches by priority (higher priority first)
        batches.sort(
            key=lambda batch: max(task.priority for task in batch), reverse=True
        )

        return batches

    def _group_tasks_by_type_and_priority(
        self, tasks: List[Task]
    ) -> Dict[str, List[Task]]:
        groups = {}

        for task in tasks:
            # Create a key based on task type and priority tier
            priority_tier = self._get_priority_tier(task.priority)
            group_key = f"{task.type}_{priority_tier}"

            if group_key not in groups:
                groups[group_key] = []

            groups[group_key].append(task)

        return groups

    def _get_priority_tier(self, priority: int) -> str:
        if priority >= 8:
            return "high"
        elif priority >= 5:
            return "medium"
        else:
            return "low"

    def _create_batches_from_group(
        self, db: Session, tasks: List[Task]
    ) -> List[List[Task]]:
        if not tasks:
            return []

        # Deduplicate tasks
        deduplicated_tasks = self._deduplicate_tasks(db, tasks)

        if not deduplicated_tasks:
            logger.info(f"All tasks in group were duplicates, skipping batch creation")
            return []

        # Create batches of appropriate size
        batches = []
        for i in range(0, len(deduplicated_tasks), self.batch_size):
            batch = deduplicated_tasks[i : i + self.batch_size]
            batches.append(batch)

        logger.info(
            f"Created {len(batches)} batches from {len(deduplicated_tasks)} tasks"
        )
        return batches

    def _deduplicate_tasks(self, db: Session, tasks: List[Task]) -> List[Task]:
        unique_tasks = []
        seen_hashes = set()

        for task in tasks:
            task_hash = self._calculate_task_hash(task)

            if task_hash in seen_hashes:
                logger.info(f"Task {task.id} is a duplicate based on hash, skipping")
                continue

            # Check if similar task was processed recently
            if self._is_recent_duplicate(db, task, task_hash):
                logger.info(f"Task {task.id} is a recent duplicate, skipping")
                continue

            seen_hashes.add(task_hash)
            unique_tasks.append(task)

        return unique_tasks

    def _calculate_task_hash(self, task: Task) -> str:
        # Create a hash based on task type and key payload elements
        hash_data = {
            "type": task.type,
            "payload": self._normalize_payload_for_hash(task.payload),
        }

        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.md5(hash_string.encode()).hexdigest()

    def _normalize_payload_for_hash(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Normalize payload by removing timestamps and other variable fields
        normalized = {}

        # List of fields to include in hash (task-type specific)
        important_fields = {
            "PR_REVIEW": ["repository", "pr_number", "title"],
            "ISSUE_SUMMARY": ["repository", "issue_number", "title"],
            "CODE_ANALYSIS": ["file_path", "code_hash"],
            "REFACTOR": ["target", "requirements"],
            "BUG_FIX": ["description", "error_message"],
            "FEATURE": ["description", "requirements"],
        }

        # Extract relevant fields for hashing
        for field in important_fields.get(payload.get("type", ""), []):
            if field in payload:
                normalized[field] = payload[field]

        return normalized

    def _is_recent_duplicate(self, db: Session, task: Task, task_hash: str) -> bool:
        # Check if a similar task was completed in the recent past
        cutoff_time = datetime.utcnow() - timedelta(
            hours=self.deduplication_window_hours
        )

        # This is a simplified check - in a real implementation,
        # you might store task hashes in a separate table or cache
        recent_tasks = TaskCRUD.get_similar_tasks(
            db, task.type, self.deduplication_window_hours
        )

        for recent_task in recent_tasks:
            if recent_task.status in [TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS]:
                recent_hash = self._calculate_task_hash(recent_task)
                if recent_hash == task_hash:
                    return True

        return False

    def mark_batch_as_queued(self, db: Session, batch: List[Task]):
        for task in batch:
            from supervisor_agent.db.schemas import TaskUpdate

            update_data = TaskUpdate(status=TaskStatus.QUEUED)
            TaskCRUD.update_task(db, task.id, update_data)

        task_ids = [task.id for task in batch]
        logger.info(f"Marked batch of {len(batch)} tasks as queued: {task_ids}")

    def can_batch_tasks(self, tasks: List[Task]) -> bool:
        if not tasks:
            return False

        # Check if all tasks are of the same type
        task_types = set(task.type for task in tasks)
        if len(task_types) > 1:
            return False

        # Check if tasks are within reasonable priority range
        priorities = [task.priority for task in tasks]
        priority_range = max(priorities) - min(priorities)
        if priority_range > 3:  # Don't batch tasks with very different priorities
            return False

        return True

    def optimize_batch_order(self, batch: List[Task]) -> List[Task]:
        # Sort tasks within batch for optimal processing
        # Higher priority first, then by creation time
        return sorted(batch, key=lambda t: (-t.priority, t.created_at))

    def estimate_batch_processing_time(self, batch: List[Task]) -> int:
        # Estimate processing time in seconds
        base_time_per_task = 30  # Base 30 seconds per task

        task_type_multipliers = {
            "PR_REVIEW": 2.0,
            "CODE_ANALYSIS": 1.5,
            "FEATURE": 3.0,
            "BUG_FIX": 2.5,
            "REFACTOR": 2.0,
            "ISSUE_SUMMARY": 1.0,
        }

        total_time = 0
        for task in batch:
            multiplier = task_type_multipliers.get(task.type, 1.0)
            total_time += base_time_per_task * multiplier

        return int(total_time)


task_batcher = TaskBatcher()

import json
import redis
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from supervisor_agent.config import settings
from supervisor_agent.db.models import Task, TaskSession
from supervisor_agent.db.crud import TaskCRUD, TaskSessionCRUD
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class SharedMemoryStore:
    def __init__(self):
        self.redis_client = redis.from_url(settings.redis_url)

    def get_task_context(self, task: Task) -> Dict[str, Any]:
        context = {}

        # Get similar tasks from the past
        similar_tasks = self._get_similar_task_history(task)
        if similar_tasks:
            context["similar_tasks"] = similar_tasks

        # Get project-specific context
        project_context = self._get_project_context(task)
        if project_context:
            context["project_context"] = project_context

        # Get cached results for similar payloads
        cached_results = self._get_cached_results(task)
        if cached_results:
            context["cached_results"] = cached_results

        return context

    def store_task_result(self, task: Task, result: Dict[str, Any]):
        try:
            # Store in Redis for quick access
            cache_key = self._generate_cache_key(task)
            cache_data = {
                "task_id": task.id,
                "task_type": task.type,
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Store with 7-day expiration
            self.redis_client.setex(
                cache_key, timedelta(days=7), json.dumps(cache_data)
            )

            logger.info(f"Stored result for task {task.id} in shared memory")

        except Exception as e:
            logger.error(f"Failed to store task result in shared memory: {str(e)}")

    def _get_similar_task_history(self, task: Task) -> List[Dict[str, Any]]:
        try:
            # Look for tasks of the same type in the past 7 days
            pattern = f"task:{task.type}:*"
            keys = self.redis_client.keys(pattern)

            similar_tasks = []
            for key in keys[-5:]:  # Limit to last 5 similar tasks
                try:
                    data = self.redis_client.get(key)
                    if data:
                        task_data = json.loads(data)
                        similar_tasks.append(
                            {
                                "task_id": task_data.get("task_id"),
                                "result_summary": self._summarize_result(
                                    task_data.get("result", {})
                                ),
                                "timestamp": task_data.get("timestamp"),
                            }
                        )
                except Exception as e:
                    logger.warning(f"Failed to parse cached task data: {str(e)}")

            return similar_tasks

        except Exception as e:
            logger.error(f"Failed to get similar task history: {str(e)}")
            return []

    def _get_project_context(self, task: Task) -> Dict[str, Any]:
        try:
            payload = task.payload

            # Extract project information from payload
            project_context = {}

            if "repository" in payload:
                repo_key = f"project:{payload['repository']}"
                cached_data = self.redis_client.get(repo_key)
                if cached_data:
                    project_context = json.loads(cached_data)

            return project_context

        except Exception as e:
            logger.error(f"Failed to get project context: {str(e)}")
            return {}

    def _get_cached_results(self, task: Task) -> Optional[Dict[str, Any]]:
        try:
            # Generate hash of task payload for deduplication
            payload_hash = self._hash_payload(task.payload)
            cache_key = f"result:{task.type}:{payload_hash}"

            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)

            return None

        except Exception as e:
            logger.error(f"Failed to get cached results: {str(e)}")
            return None

    def _generate_cache_key(self, task: Task) -> str:
        return f"task:{task.type}:{task.id}"

    def _hash_payload(self, payload: Dict[str, Any]) -> str:
        import hashlib

        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.md5(payload_str.encode()).hexdigest()

    def _summarize_result(self, result: Dict[str, Any]) -> str:
        if isinstance(result, dict):
            if "result" in result:
                content = str(result["result"])
                return content[:200] + "..." if len(content) > 200 else content
        return str(result)[:200]

    def update_project_context(self, repository: str, context: Dict[str, Any]):
        try:
            repo_key = f"project:{repository}"
            existing_data = self.redis_client.get(repo_key)

            if existing_data:
                existing_context = json.loads(existing_data)
                existing_context.update(context)
                context = existing_context

            # Store project context with 30-day expiration
            self.redis_client.setex(repo_key, timedelta(days=30), json.dumps(context))

            logger.info(f"Updated project context for {repository}")

        except Exception as e:
            logger.error(f"Failed to update project context: {str(e)}")

    def get_session_history(
        self, task_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        try:
            # This would be implemented to get session history from database
            # For now, return empty list as placeholder
            return []

        except Exception as e:
            logger.error(f"Failed to get session history: {str(e)}")
            return []

    def clear_expired_cache(self):
        try:
            # Redis handles expiration automatically, but we can clean up manually if needed
            logger.info("Cache cleanup completed")

        except Exception as e:
            logger.error(f"Failed to clear expired cache: {str(e)}")


shared_memory = SharedMemoryStore()

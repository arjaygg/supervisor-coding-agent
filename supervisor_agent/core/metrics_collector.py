"""
Metrics Collector

Collects various types of metrics from the system for analytics purposes.
Implements the MetricsCollector interface with SOLID principles.
"""

import asyncio
import psutil
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from supervisor_agent.db.database import SessionLocal
from supervisor_agent.db.models import Task, TaskStatus, Agent
from supervisor_agent.core.analytics_models import (
    MetricEntry, TaskMetrics, SystemMetrics, UserMetrics, WorkflowMetrics,
    MetricType, MetricPoint
)


class MetricsCollectorInterface(ABC):
    """Abstract interface for metrics collection"""
    
    @abstractmethod
    async def collect_task_metrics(self, task_id: int) -> TaskMetrics:
        """Collect metrics for a specific task"""
        pass
    
    @abstractmethod
    async def collect_system_metrics(self) -> SystemMetrics:
        """Collect system-wide performance metrics"""
        pass
    
    @abstractmethod
    async def collect_user_metrics(self, user_id: str) -> UserMetrics:
        """Collect user activity metrics"""
        pass
    
    @abstractmethod
    async def collect_workflow_metrics(self, workflow_id: str) -> WorkflowMetrics:
        """Collect workflow execution metrics"""
        pass
    
    @abstractmethod
    async def store_metric(self, metric_type: MetricType, value: Union[float, int, str], 
                          labels: Dict[str, str] = None, metadata: Dict[str, Any] = None) -> None:
        """Store a metric in the database"""
        pass


class MetricsCollector(MetricsCollectorInterface):
    """Concrete implementation of metrics collection"""
    
    def __init__(self):
        self.session_factory = SessionLocal
        self._system_stats_cache = {}
        self._cache_timeout = 30  # Cache system stats for 30 seconds
    
    async def collect_task_metrics(self, task_id: int) -> TaskMetrics:
        """Collect comprehensive metrics for a task"""
        async with self.session_factory() as session:
            task = session.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # Calculate execution time
            execution_time_ms = 0
            queue_time_ms = 0
            
            if task.updated_at and task.created_at:
                total_time = (task.updated_at - task.created_at).total_seconds() * 1000
                # Estimate queue time vs execution time based on status
                if task.status == TaskStatus.COMPLETED:
                    execution_time_ms = int(total_time * 0.8)  # 80% execution, 20% queue
                    queue_time_ms = int(total_time * 0.2)
                else:
                    queue_time_ms = int(total_time)
            
            # Get cost data if available
            cost_entry = session.query(text("""
                SELECT estimated_cost_usd FROM cost_tracking 
                WHERE task_id = :task_id 
                ORDER BY timestamp DESC LIMIT 1
            """)).params(task_id=task_id).first()
            
            cost_usd = cost_entry[0] if cost_entry else None
            
            return TaskMetrics(
                task_id=task.id,
                task_type=task.type.value,
                execution_time_ms=execution_time_ms,
                success=task.status == TaskStatus.COMPLETED,
                queue_time_ms=queue_time_ms,
                memory_usage_mb=None,  # Would need process-level monitoring
                cpu_usage_percent=None,  # Would need process-level monitoring
                error_message=task.error_message,
                cost_usd=cost_usd
            )
    
    async def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system performance metrics"""
        # Check cache first
        now = time.time()
        if (self._system_stats_cache.get('timestamp', 0) + self._cache_timeout > now):
            cached_data = self._system_stats_cache.get('data')
            if cached_data:
                return cached_data
        
        async with self.session_factory() as session:
            # Get system stats
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get task queue stats
            active_tasks = session.query(Task).filter(
                Task.status.in_([TaskStatus.IN_PROGRESS, TaskStatus.QUEUED])
            ).count()
            
            queue_depth = session.query(Task).filter(
                Task.status == TaskStatus.QUEUED
            ).count()
            
            # Calculate average response time (last 100 completed tasks)
            recent_tasks = session.query(Task).filter(
                Task.status == TaskStatus.COMPLETED,
                Task.updated_at.isnot(None),
                Task.created_at.isnot(None)
            ).order_by(Task.updated_at.desc()).limit(100).all()
            
            response_times = []
            for task in recent_tasks:
                if task.updated_at and task.created_at:
                    response_time = (task.updated_at - task.created_at).total_seconds() * 1000
                    response_times.append(response_time)
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            metrics = SystemMetrics(
                timestamp=datetime.now(timezone.utc),
                cpu_usage_percent=cpu_percent,
                memory_usage_percent=memory.percent,
                disk_usage_percent=(disk.used / disk.total) * 100,
                active_tasks_count=active_tasks,
                queue_depth=queue_depth,
                response_time_ms=avg_response_time
            )
            
            # Cache the result
            self._system_stats_cache = {
                'timestamp': now,
                'data': metrics
            }
            
            return metrics
    
    async def collect_user_metrics(self, user_id: str) -> UserMetrics:
        """Collect user activity metrics"""
        # This would typically integrate with session management
        # For now, we'll return basic metrics based on task creation
        async with self.session_factory() as session:
            # Get user's recent task activity
            user_tasks = session.query(Task).filter(
                Task.assigned_agent_id == user_id
            ).order_by(Task.created_at.desc()).limit(50).all()
            
            if not user_tasks:
                return UserMetrics(
                    user_id=user_id,
                    session_duration_ms=0,
                    actions_count=0,
                    features_used=[],
                    last_activity=datetime.now(timezone.utc)
                )
            
            # Calculate metrics from task data
            last_activity = user_tasks[0].created_at
            actions_count = len(user_tasks)
            
            # Estimate session duration from task spread
            first_task = user_tasks[-1]
            session_duration = (last_activity - first_task.created_at).total_seconds() * 1000
            
            # Determine features used based on task types
            features_used = list(set(task.type.value for task in user_tasks))
            
            return UserMetrics(
                user_id=user_id,
                session_duration_ms=int(session_duration),
                actions_count=actions_count,
                features_used=features_used,
                last_activity=last_activity
            )
    
    async def collect_workflow_metrics(self, workflow_id: str) -> WorkflowMetrics:
        """Collect workflow execution metrics"""
        async with self.session_factory() as session:
            # Get workflow data (would need to query workflow tables)
            # For now, we'll simulate based on tasks that might be part of workflow
            workflow_tasks = session.query(Task).filter(
                Task.payload.contains({'workflow_id': workflow_id})
            ).all()
            
            if not workflow_tasks:
                return WorkflowMetrics(
                    workflow_id=workflow_id,
                    workflow_name=f"Workflow {workflow_id}",
                    total_execution_time_ms=0,
                    tasks_count=0,
                    success_rate=0.0,
                    parallel_efficiency=0.0,
                    resource_utilization={}
                )
            
            # Calculate metrics
            total_execution_time = 0
            successful_tasks = 0
            
            for task in workflow_tasks:
                if task.updated_at and task.created_at:
                    exec_time = (task.updated_at - task.created_at).total_seconds() * 1000
                    total_execution_time += exec_time
                
                if task.status == TaskStatus.COMPLETED:
                    successful_tasks += 1
            
            success_rate = successful_tasks / len(workflow_tasks) if workflow_tasks else 0
            
            # Calculate parallel efficiency (simplified)
            # This would be more sophisticated in a real implementation
            parallel_efficiency = min(1.0, 1.0 / len(workflow_tasks) if workflow_tasks else 0)
            
            return WorkflowMetrics(
                workflow_id=workflow_id,
                workflow_name=f"Workflow {workflow_id}",
                total_execution_time_ms=int(total_execution_time),
                tasks_count=len(workflow_tasks),
                success_rate=success_rate,
                parallel_efficiency=parallel_efficiency,
                resource_utilization={
                    "cpu": 0.0,  # Would need more detailed monitoring
                    "memory": 0.0,
                    "io": 0.0
                }
            )
    
    async def store_metric(self, metric_type: MetricType, value: Union[float, int, str], 
                          labels: Dict[str, str] = None, metadata: Dict[str, Any] = None) -> None:
        """Store a metric entry in the database"""
        async with self.session_factory() as session:
            # Handle string values
            float_value = None
            string_value = None
            
            if isinstance(value, (int, float)):
                float_value = float(value)
            else:
                string_value = str(value)
                float_value = 0.0  # Default for non-numeric values
            
            metric_entry = MetricEntry(
                metric_type=metric_type.value,
                timestamp=datetime.now(timezone.utc),
                value=float_value,
                string_value=string_value,
                labels=labels or {},
                metadata=metadata or {}
            )
            
            session.add(metric_entry)
            await session.commit()
    
    async def collect_and_store_system_metrics(self) -> None:
        """Convenience method to collect and store system metrics"""
        try:
            metrics = await self.collect_system_metrics()
            
            # Store individual metric points
            await self.store_metric(
                MetricType.SYSTEM_PERFORMANCE, 
                metrics.cpu_usage_percent,
                labels={"component": "cpu"},
                metadata={"unit": "percent"}
            )
            
            await self.store_metric(
                MetricType.SYSTEM_PERFORMANCE, 
                metrics.memory_usage_percent,
                labels={"component": "memory"},
                metadata={"unit": "percent"}
            )
            
            await self.store_metric(
                MetricType.SYSTEM_PERFORMANCE, 
                metrics.disk_usage_percent,
                labels={"component": "disk"},
                metadata={"unit": "percent"}
            )
            
            await self.store_metric(
                MetricType.SYSTEM_PERFORMANCE, 
                metrics.active_tasks_count,
                labels={"component": "tasks"},
                metadata={"unit": "count"}
            )
            
            await self.store_metric(
                MetricType.SYSTEM_PERFORMANCE, 
                metrics.queue_depth,
                labels={"component": "queue"},
                metadata={"unit": "count"}
            )
            
            await self.store_metric(
                MetricType.SYSTEM_PERFORMANCE, 
                metrics.response_time_ms,
                labels={"component": "response_time"},
                metadata={"unit": "milliseconds"}
            )
            
        except Exception as e:
            # Log error but don't fail the application
            print(f"Error collecting system metrics: {e}")
    
    async def collect_and_store_task_metrics(self, task_id: int) -> None:
        """Convenience method to collect and store task metrics"""
        try:
            metrics = await self.collect_task_metrics(task_id)
            
            await self.store_metric(
                MetricType.TASK_EXECUTION,
                metrics.execution_time_ms,
                labels={
                    "task_id": str(task_id),
                    "task_type": metrics.task_type,
                    "success": str(metrics.success)
                },
                metadata={
                    "unit": "milliseconds",
                    "queue_time_ms": metrics.queue_time_ms,
                    "error_message": metrics.error_message
                }
            )
            
            if metrics.cost_usd:
                await self.store_metric(
                    MetricType.COST_TRACKING,
                    float(metrics.cost_usd),
                    labels={
                        "task_id": str(task_id),
                        "task_type": metrics.task_type
                    },
                    metadata={"unit": "usd"}
                )
                
        except Exception as e:
            print(f"Error collecting task metrics for task {task_id}: {e}")


class BackgroundMetricsCollector:
    """Background service for continuous metrics collection"""
    
    def __init__(self, collector: MetricsCollector, interval_seconds: int = 60):
        self.collector = collector
        self.interval_seconds = interval_seconds
        self._running = False
        self._task = None
    
    async def start(self):
        """Start background metrics collection"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._collect_loop())
    
    async def stop(self):
        """Stop background metrics collection"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _collect_loop(self):
        """Main collection loop"""
        while self._running:
            try:
                await self.collector.collect_and_store_system_metrics()
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(self.interval_seconds)
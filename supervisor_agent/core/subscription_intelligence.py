"""
Subscription Intelligence Module

Optimizes Claude API usage through:
- Request deduplication
- Intelligent batching
- Usage prediction
- Quota management

Follows Lean principles with continuous value delivery.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class RequestHash:
    """Utilities for generating consistent request hashes."""

    @staticmethod
    def generate(request_data: Dict[str, Any]) -> str:
        """Generate a consistent hash for request deduplication."""
        # Create a canonical JSON representation
        canonical_json = json.dumps(request_data, sort_keys=True, separators=(",", ":"))

        # Generate SHA-256 hash
        hash_object = hashlib.sha256(canonical_json.encode("utf-8"))
        return hash_object.hexdigest()


@dataclass
class CacheEntry:
    """Cache entry with result and timestamp."""

    result: Any
    timestamp: float
    hit_count: int = 0


@dataclass
class UsageRecord:
    """Record of API usage for prediction."""

    task_type: str
    tokens_used: int
    processing_time: float
    timestamp: datetime
    success: bool = True


class RequestDeduplicator:
    """Handles request deduplication with TTL-based cache."""

    def __init__(self, cache_ttl_seconds: int = 300):
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache: Dict[str, CacheEntry] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Cleanup every minute

    def is_duplicate(self, request: Dict[str, Any]) -> bool:
        """Check if request is a duplicate and cache it."""
        request_hash = RequestHash.generate(request)
        current_time = time.time()

        # Periodic cleanup
        if current_time - self._last_cleanup > self._cleanup_interval:
            self.cleanup_expired()

        # Check if request exists and is not expired
        if request_hash in self.cache:
            entry = self.cache[request_hash]
            if current_time - entry.timestamp < self.cache_ttl_seconds:
                entry.hit_count += 1
                logger.debug(f"Duplicate request detected: {request_hash[:8]}...")
                return True
            else:
                # Expired, remove from cache
                del self.cache[request_hash]

        # New request, cache it
        self.cache[request_hash] = CacheEntry(
            result=None, timestamp=current_time, hit_count=0
        )

        return False

    def get_cached_result(self, request: Dict[str, Any]) -> Optional[Any]:
        """Get cached result for a request."""
        request_hash = RequestHash.generate(request)

        if request_hash in self.cache:
            entry = self.cache[request_hash]
            if time.time() - entry.timestamp < self.cache_ttl_seconds:
                return entry.result

        return None

    def store_result(self, request: Dict[str, Any], result: Any):
        """Store result for a request."""
        request_hash = RequestHash.generate(request)

        if request_hash in self.cache:
            self.cache[request_hash].result = result
            logger.debug(f"Cached result for request: {request_hash[:8]}...")

    def cleanup_expired(self):
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = [
            key
            for key, entry in self.cache.items()
            if current_time - entry.timestamp >= self.cache_ttl_seconds
        ]

        for key in expired_keys:
            del self.cache[key]

        self._last_cleanup = current_time

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self.cache)
        total_hits = sum(entry.hit_count for entry in self.cache.values())

        return {
            "total_entries": total_entries,
            "total_hits": total_hits,
            "hit_rate": total_hits / max(total_entries, 1),
            "cache_size_mb": sum(
                len(str(entry.result))
                for entry in self.cache.values()
                if entry.result is not None
            )
            / (1024 * 1024),
        }


class BatchProcessor:
    """Handles intelligent batching of requests."""

    def __init__(self, batch_size: int = 5, batch_timeout_seconds: float = 2.0):
        self.batch_size = batch_size
        self.batch_timeout_seconds = batch_timeout_seconds
        self.current_batch: List[Dict[str, Any]] = []
        self.batch_start_time: Optional[float] = None
        self.process_callback: Optional[Callable] = None
        self._batch_lock = asyncio.Lock()
        self._timeout_task: Optional[asyncio.Task] = None

    async def add_request(self, request: Dict[str, Any]) -> bool:
        """Add request to batch. Returns True if batch was processed."""
        async with self._batch_lock:
            self.current_batch.append(request)

            # Set batch start time on first request
            if len(self.current_batch) == 1:
                self.batch_start_time = time.time()
                self._schedule_timeout()

            # Process batch if size threshold reached
            if len(self.current_batch) >= self.batch_size:
                await self._process_current_batch()
                return True

            return False

    async def force_process_batch(self):
        """Force process current batch regardless of size."""
        async with self._batch_lock:
            if self.current_batch:
                await self._process_current_batch()

    def _schedule_timeout(self):
        """Schedule timeout for current batch."""
        if self._timeout_task:
            self._timeout_task.cancel()

        self._timeout_task = asyncio.create_task(self._timeout_handler())

    async def _timeout_handler(self):
        """Handle batch timeout."""
        try:
            await asyncio.sleep(self.batch_timeout_seconds)
            async with self._batch_lock:
                if self.current_batch:
                    logger.debug(
                        f"Processing batch due to timeout: {len(self.current_batch)} requests"
                    )
                    await self._process_current_batch()
        except asyncio.CancelledError:
            pass

    async def _process_current_batch(self):
        """Process the current batch."""
        if not self.current_batch:
            return

        batch_to_process = self.current_batch.copy()
        self.current_batch.clear()
        self.batch_start_time = None

        if self._timeout_task:
            self._timeout_task.cancel()
            self._timeout_task = None

        if self.process_callback:
            logger.info(f"Processing batch of {len(batch_to_process)} requests")
            await self.process_callback(batch_to_process)

    def get_batch_stats(self) -> Dict[str, Any]:
        """Get batch processing statistics."""
        return {
            "current_batch_size": len(self.current_batch),
            "batch_age_seconds": (
                time.time() - self.batch_start_time if self.batch_start_time else 0
            ),
            "configured_batch_size": self.batch_size,
            "configured_timeout": self.batch_timeout_seconds,
        }


class UsagePredictor:
    """Predicts API usage patterns and costs."""

    def __init__(self, history_limit: int = 1000):
        self.history_limit = history_limit
        self.usage_history: List[UsageRecord] = []
        self.default_token_estimate = 2000  # Conservative estimate

    def record_usage(
        self,
        task_type: str,
        tokens_used: int,
        processing_time: float,
        timestamp: Optional[datetime] = None,
        success: bool = True,
    ):
        """Record API usage for prediction."""
        if timestamp is None:
            timestamp = datetime.now()

        record = UsageRecord(
            task_type=task_type,
            tokens_used=tokens_used,
            processing_time=processing_time,
            timestamp=timestamp,
            success=success,
        )

        self.usage_history.append(record)

        # Maintain history limit
        if len(self.usage_history) > self.history_limit:
            self.usage_history = self.usage_history[-self.history_limit :]

        logger.debug(
            f"Recorded usage: {task_type}, {tokens_used} tokens, {processing_time:.2f}s"
        )

    def predict_tokens(self, task_type: str) -> int:
        """Predict token usage for a task type."""
        # Filter recent history for this task type
        recent_records = [
            record
            for record in self.usage_history[-100:]  # Last 100 records
            if record.task_type == task_type and record.success
        ]

        if not recent_records:
            return self.default_token_estimate

        # Calculate average with outlier removal
        token_counts = [record.tokens_used for record in recent_records]
        token_counts.sort()

        # Remove outliers (top and bottom 10%)
        if len(token_counts) >= 10:
            trim_count = len(token_counts) // 10
            token_counts = token_counts[trim_count:-trim_count]

        average_tokens = sum(token_counts) // len(token_counts)
        return max(average_tokens, 100)  # Minimum 100 tokens

    def predict_daily_usage(self) -> float:
        """Predict daily token usage based on current patterns."""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get today's usage
        today_records = [
            record
            for record in self.usage_history
            if record.timestamp >= today_start and record.success
        ]

        if not today_records:
            return 0.0

        # Calculate tokens per hour so far today
        hours_elapsed = (now - today_start).total_seconds() / 3600
        total_tokens_today = sum(record.tokens_used for record in today_records)

        if hours_elapsed == 0:
            return float(total_tokens_today)

        tokens_per_hour = total_tokens_today / hours_elapsed

        # Predict for remaining hours (assuming similar usage pattern)
        remaining_hours = 24 - hours_elapsed
        predicted_remaining = tokens_per_hour * remaining_hours

        return float(total_tokens_today + predicted_remaining)

    def get_peak_hours(self, days_back: int = 7) -> List[int]:
        """Get peak usage hours based on historical data."""
        cutoff_date = datetime.now() - timedelta(days=days_back)

        # Filter recent records
        recent_records = [
            record
            for record in self.usage_history
            if record.timestamp >= cutoff_date and record.success
        ]

        # Count usage by hour
        hourly_usage = defaultdict(int)
        for record in recent_records:
            hour = record.timestamp.hour
            hourly_usage[hour] += record.tokens_used

        # Find top 3 peak hours
        sorted_hours = sorted(hourly_usage.items(), key=lambda x: x[1], reverse=True)

        return [hour for hour, _ in sorted_hours[:3]]

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics and predictions."""
        if not self.usage_history:
            return {
                "total_records": 0,
                "avg_tokens_per_request": 0,
                "success_rate": 0.0,
                "predicted_daily_usage": 0.0,
            }

        successful_records = [r for r in self.usage_history if r.success]

        return {
            "total_records": len(self.usage_history),
            "successful_records": len(successful_records),
            "avg_tokens_per_request": (
                sum(r.tokens_used for r in successful_records)
                // max(len(successful_records), 1)
            ),
            "success_rate": len(successful_records) / len(self.usage_history),
            "predicted_daily_usage": self.predict_daily_usage(),
            "peak_hours": self.get_peak_hours(),
        }


class SubscriptionIntelligence:
    """Main coordinator for subscription optimization."""

    def __init__(
        self,
        daily_limit: int = 50000,
        batch_size: int = 5,
        cache_ttl_seconds: int = 300,
        batch_timeout_seconds: float = 2.0,
    ):
        self.daily_limit = daily_limit
        self.current_usage = 0
        self.usage_reset_time = self._get_next_reset_time()

        # Components
        self.deduplicator = RequestDeduplicator(cache_ttl_seconds)
        self.batch_processor = BatchProcessor(batch_size, batch_timeout_seconds)
        self.usage_predictor = UsagePredictor()

        # Configuration
        self.batch_processor.process_callback = self._process_batch
        self._pending_batch_requests: Dict[str, asyncio.Future] = {}

        logger.info(
            f"Subscription Intelligence initialized: "
            f"daily_limit={daily_limit}, batch_size={batch_size}"
        )

    async def process_request(
        self, request: Dict[str, Any], processor: Callable
    ) -> Any:
        """Process a request with intelligent optimization."""
        # Check daily quota
        self._check_and_reset_quota()
        if self.current_usage >= self.daily_limit:
            raise Exception(
                f"Daily quota exceeded: {self.current_usage}/{self.daily_limit} tokens"
            )

        # Check for duplicate
        if self.deduplicator.is_duplicate(request):
            cached_result = self.deduplicator.get_cached_result(request)
            if cached_result is not None:
                logger.info("Returning cached result for duplicate request")
                return cached_result

        # Estimate token usage
        estimated_tokens = self.estimate_token_usage(request)

        # Check if we should batch this request
        if self.should_batch_request(request):
            return await self._process_batched_request(request, processor)
        else:
            return await self._process_individual_request(
                request, processor, estimated_tokens
            )

    async def _process_individual_request(
        self,
        request: Dict[str, Any],
        processor: Callable,
        estimated_tokens: int,
    ) -> Any:
        """Process a single request immediately."""
        start_time = time.time()

        try:
            result = await processor([request])

            # Extract single result if processor returns list
            if isinstance(result, list) and len(result) == 1:
                result = result[0]

            # Record usage
            processing_time = time.time() - start_time
            actual_tokens = self._extract_token_count(result, estimated_tokens)

            self.usage_predictor.record_usage(
                task_type=request.get("type", "unknown"),
                tokens_used=actual_tokens,
                processing_time=processing_time,
                success=True,
            )

            self.current_usage += actual_tokens

            # Cache result
            self.deduplicator.store_result(request, result)

            logger.info(
                f"Processed individual request: {actual_tokens} tokens, "
                f"{processing_time:.2f}s"
            )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            self.usage_predictor.record_usage(
                task_type=request.get("type", "unknown"),
                tokens_used=0,
                processing_time=processing_time,
                success=False,
            )
            raise

    async def _process_batched_request(
        self, request: Dict[str, Any], processor: Callable
    ) -> Any:
        """Process a request as part of a batch."""
        request_id = RequestHash.generate(request)

        # Create future for this request
        future = asyncio.Future()
        self._pending_batch_requests[request_id] = future

        # Add to batch
        await self.batch_processor.add_request(
            {**request, "_request_id": request_id, "_processor": processor}
        )

        # Wait for batch processing
        try:
            result = await future
            return result
        finally:
            # Cleanup
            self._pending_batch_requests.pop(request_id, None)

    async def _process_batch(self, batch_requests: List[Dict[str, Any]]):
        """Process a batch of requests."""
        if not batch_requests:
            return

        start_time = time.time()

        try:
            # Group requests by processor (in case of mixed batches)
            processor_groups = defaultdict(list)
            for request in batch_requests:
                processor = request.pop("_processor", None)
                request_id = request.pop("_request_id", None)

                if processor and request_id:
                    processor_groups[id(processor)].append(
                        (request, request_id, processor)
                    )

            # Process each group
            for group in processor_groups.values():
                requests = [item[0] for item in group]
                request_ids = [item[1] for item in group]
                processor = group[0][2]  # All have same processor

                try:
                    results = await processor(requests)

                    # Handle results
                    for i, (request, request_id) in enumerate(
                        zip(requests, request_ids)
                    ):
                        result = (
                            results[i]
                            if isinstance(results, list) and i < len(results)
                            else results
                        )

                        # Record usage
                        estimated_tokens = self.estimate_token_usage(request)
                        actual_tokens = self._extract_token_count(
                            result, estimated_tokens
                        )

                        self.usage_predictor.record_usage(
                            task_type=request.get("type", "unknown"),
                            tokens_used=actual_tokens,
                            processing_time=(time.time() - start_time) / len(requests),
                            success=True,
                        )

                        self.current_usage += actual_tokens

                        # Cache result
                        self.deduplicator.store_result(request, result)

                        # Resolve future
                        if request_id in self._pending_batch_requests:
                            self._pending_batch_requests[request_id].set_result(result)

                except Exception as e:
                    # Mark all requests in this group as failed
                    for request, request_id in zip(requests, request_ids):
                        self.usage_predictor.record_usage(
                            task_type=request.get("type", "unknown"),
                            tokens_used=0,
                            processing_time=(time.time() - start_time) / len(requests),
                            success=False,
                        )

                        if request_id in self._pending_batch_requests:
                            self._pending_batch_requests[request_id].set_exception(e)

            logger.info(f"Processed batch of {len(batch_requests)} requests")

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")

            # Fail all pending requests
            for request_id in [r.get("_request_id") for r in batch_requests]:
                if request_id and request_id in self._pending_batch_requests:
                    self._pending_batch_requests[request_id].set_exception(e)

    def should_batch_request(self, request: Dict[str, Any]) -> bool:
        """Determine if a request should be batched."""
        # Simple heuristic: batch smaller requests
        payload_size = len(str(request.get("payload", "")))

        # Don't batch large requests (>5KB)
        if payload_size > 5000:
            return False

        # Don't batch certain critical task types
        critical_types = {"CRITICAL_BUG_FIX", "SECURITY_ISSUE"}
        if request.get("type") in critical_types:
            return False

        # Don't batch high-priority requests
        priority = request.get("priority", 5)
        if priority <= 2:  # High priority (1-2)
            return False

        return True

    def estimate_token_usage(self, request: Dict[str, Any]) -> int:
        """Estimate token usage for a request."""
        task_type = request.get("type", "unknown")

        # Use prediction if available
        predicted = self.usage_predictor.predict_tokens(task_type)

        # Adjust based on payload size
        payload_size = len(str(request.get("payload", "")))
        size_multiplier = max(1.0, payload_size / 1000)  # 1 token per ~1000 chars

        estimated = int(predicted * size_multiplier)

        return max(estimated, 50)  # Minimum 50 tokens

    def _extract_token_count(self, result: Any, fallback: int) -> int:
        """Extract actual token count from result."""
        if isinstance(result, dict):
            # Try common token count fields
            for field in ["tokens_used", "token_count", "usage_tokens"]:
                if field in result:
                    return int(result[field])

            # Try nested usage objects
            if "usage" in result and isinstance(result["usage"], dict):
                usage = result["usage"]
                if "total_tokens" in usage:
                    return int(usage["total_tokens"])

        # Fallback to estimate
        return fallback

    def _check_and_reset_quota(self):
        """Check and reset daily quota if needed."""
        now = datetime.now()

        if now >= self.usage_reset_time:
            self.current_usage = 0
            self.usage_reset_time = self._get_next_reset_time()
            logger.info("Daily quota reset")

    def _get_next_reset_time(self) -> datetime:
        """Get next quota reset time (midnight)."""
        now = datetime.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        return tomorrow

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics."""
        self._check_and_reset_quota()

        usage_percentage = (self.current_usage / self.daily_limit) * 100
        time_until_reset = (self.usage_reset_time - datetime.now()).total_seconds()

        return {
            "current_usage": self.current_usage,
            "daily_limit": self.daily_limit,
            "usage_percentage": round(usage_percentage, 1),
            "remaining": self.daily_limit - self.current_usage,
            "time_until_reset_hours": round(time_until_reset / 3600, 1),
            "cache_stats": self.deduplicator.get_cache_stats(),
            "batch_stats": self.batch_processor.get_batch_stats(),
            "prediction_stats": self.usage_predictor.get_usage_stats(),
        }

    async def force_process_pending(self):
        """Force process any pending batches."""
        await self.batch_processor.force_process_batch()

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down Subscription Intelligence")
        await self.force_process_pending()

        # Cancel any pending timeouts
        if self.batch_processor._timeout_task:
            self.batch_processor._timeout_task.cancel()

        # Fail any remaining pending requests
        for future in self._pending_batch_requests.values():
            if not future.done():
                future.set_exception(Exception("System shutdown"))

        self._pending_batch_requests.clear()

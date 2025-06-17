import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import hashlib
import json

from supervisor_agent.core.subscription_intelligence import (
    SubscriptionIntelligence,
    RequestDeduplicator,
    BatchProcessor,
    UsagePredictor,
    RequestHash,
)


class TestRequestHash:
    """Test the request hashing functionality."""

    def test_generate_hash_same_content(self):
        """Test that same content generates same hash."""
        content1 = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}
        content2 = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}

        hash1 = RequestHash.generate(content1)
        hash2 = RequestHash.generate(content2)

        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 hex length

    def test_generate_hash_different_content(self):
        """Test that different content generates different hashes."""
        content1 = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}
        content2 = {"type": "PR_REVIEW", "payload": {"pr_number": 124}}

        hash1 = RequestHash.generate(content1)
        hash2 = RequestHash.generate(content2)

        assert hash1 != hash2

    def test_generate_hash_order_independent(self):
        """Test that key order doesn't affect hash."""
        content1 = {"type": "PR_REVIEW", "payload": {"pr_number": 123, "title": "test"}}
        content2 = {"payload": {"title": "test", "pr_number": 123}, "type": "PR_REVIEW"}

        hash1 = RequestHash.generate(content1)
        hash2 = RequestHash.generate(content2)

        assert hash1 == hash2


class TestRequestDeduplicator:
    """Test the request deduplication functionality."""

    @pytest.fixture
    def deduplicator(self):
        return RequestDeduplicator(cache_ttl_seconds=300)

    def test_is_duplicate_first_request(self, deduplicator):
        """Test that first request is not a duplicate."""
        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}

        is_duplicate = deduplicator.is_duplicate(request)

        assert not is_duplicate

    def test_is_duplicate_same_request(self, deduplicator):
        """Test that same request is marked as duplicate."""
        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}

        # First request
        deduplicator.is_duplicate(request)

        # Second identical request
        is_duplicate = deduplicator.is_duplicate(request)

        assert is_duplicate

    def test_get_cached_result(self, deduplicator):
        """Test retrieving cached result."""
        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}
        result = {"status": "completed", "analysis": "test"}

        # Mark as duplicate (caches the request)
        deduplicator.is_duplicate(request)
        # Store result
        deduplicator.store_result(request, result)

        cached_result = deduplicator.get_cached_result(request)

        assert cached_result == result

    def test_cache_expiry(self, deduplicator):
        """Test that cache expires after TTL."""
        deduplicator.cache_ttl_seconds = 0.1  # 100ms for testing
        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}

        # First request
        deduplicator.is_duplicate(request)

        # Wait for cache to expire
        import time

        time.sleep(0.2)

        # Should not be duplicate after expiry
        is_duplicate = deduplicator.is_duplicate(request)
        assert not is_duplicate

    def test_cleanup_expired(self, deduplicator):
        """Test cleanup of expired cache entries."""
        deduplicator.cache_ttl_seconds = 0.1
        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}

        deduplicator.is_duplicate(request)

        import time

        time.sleep(0.2)

        # Cleanup should remove expired entries
        deduplicator.cleanup_expired()

        assert len(deduplicator.cache) == 0


class TestBatchProcessor:
    """Test the batch processing functionality."""

    @pytest.fixture
    def batch_processor(self):
        return BatchProcessor(batch_size=3, batch_timeout_seconds=1.0)

    @pytest.mark.asyncio
    async def test_add_request_below_threshold(self, batch_processor):
        """Test adding requests below batch size threshold."""
        mock_callback = AsyncMock()
        batch_processor.process_callback = mock_callback

        request1 = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}
        request2 = {"type": "CODE_ANALYSIS", "payload": {"file": "test.py"}}

        await batch_processor.add_request(request1)
        await batch_processor.add_request(request2)

        # Should not process yet
        mock_callback.assert_not_called()
        assert len(batch_processor.current_batch) == 2

    @pytest.mark.asyncio
    async def test_add_request_at_threshold(self, batch_processor):
        """Test that batch is processed when size threshold is reached."""
        mock_callback = AsyncMock()
        batch_processor.process_callback = mock_callback

        requests = [
            {"type": "PR_REVIEW", "payload": {"pr_number": 123}},
            {"type": "CODE_ANALYSIS", "payload": {"file": "test.py"}},
            {"type": "BUG_FIX", "payload": {"issue": "memory leak"}},
        ]

        for request in requests:
            await batch_processor.add_request(request)

        # Should process batch when threshold is reached
        mock_callback.assert_called_once_with(requests)
        assert len(batch_processor.current_batch) == 0

    @pytest.mark.asyncio
    async def test_batch_timeout(self, batch_processor):
        """Test that batch is processed after timeout."""
        mock_callback = AsyncMock()
        batch_processor.process_callback = mock_callback
        batch_processor.batch_timeout_seconds = 0.1  # 100ms for testing

        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}
        await batch_processor.add_request(request)

        # Wait for timeout
        await asyncio.sleep(0.2)

        # Should process batch after timeout
        mock_callback.assert_called_once_with([request])

    @pytest.mark.asyncio
    async def test_force_process_batch(self, batch_processor):
        """Test force processing of current batch."""
        mock_callback = AsyncMock()
        batch_processor.process_callback = mock_callback

        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}
        await batch_processor.add_request(request)

        await batch_processor.force_process_batch()

        mock_callback.assert_called_once_with([request])
        assert len(batch_processor.current_batch) == 0


class TestUsagePredictor:
    """Test the usage prediction functionality."""

    @pytest.fixture
    def usage_predictor(self):
        return UsagePredictor()

    def test_record_usage(self, usage_predictor):
        """Test recording usage data."""
        usage_predictor.record_usage(
            task_type="PR_REVIEW",
            tokens_used=1500,
            processing_time=2.5,
            timestamp=datetime.now(),
        )

        assert len(usage_predictor.usage_history) == 1
        assert usage_predictor.usage_history[0].task_type == "PR_REVIEW"
        assert usage_predictor.usage_history[0].tokens_used == 1500

    def test_predict_tokens_no_history(self, usage_predictor):
        """Test token prediction with no history."""
        prediction = usage_predictor.predict_tokens("PR_REVIEW")

        assert prediction == usage_predictor.default_token_estimate

    def test_predict_tokens_with_history(self, usage_predictor):
        """Test token prediction with historical data."""
        # Add some historical data
        for i in range(5):
            usage_predictor.record_usage(
                task_type="PR_REVIEW",
                tokens_used=1000 + i * 100,  # 1000, 1100, 1200, 1300, 1400
                processing_time=2.0,
                timestamp=datetime.now() - timedelta(days=i),
            )

        prediction = usage_predictor.predict_tokens("PR_REVIEW")

        # Should be average: (1000 + 1100 + 1200 + 1300 + 1400) / 5 = 1200
        assert prediction == 1200

    def test_predict_daily_usage(self, usage_predictor):
        """Test daily usage prediction."""
        # Add usage data for different hours
        base_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

        for hour_offset in range(8):  # 9 AM to 5 PM
            usage_predictor.record_usage(
                task_type="PR_REVIEW",
                tokens_used=500,
                processing_time=1.0,
                timestamp=base_time + timedelta(hours=hour_offset),
            )

        prediction = usage_predictor.predict_daily_usage()

        # Should predict based on current usage pattern
        assert prediction > 0
        assert isinstance(prediction, float)

    def test_get_peak_hours(self, usage_predictor):
        """Test identification of peak usage hours."""
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Add more usage during "peak" hours (10 AM and 2 PM)
        peak_hours = [10, 14]
        for hour in range(24):
            usage_count = 5 if hour in peak_hours else 1
            for _ in range(usage_count):
                usage_predictor.record_usage(
                    task_type="PR_REVIEW",
                    tokens_used=500,
                    processing_time=1.0,
                    timestamp=base_time + timedelta(hours=hour),
                )

        peak_hours_result = usage_predictor.get_peak_hours()

        assert 10 in peak_hours_result
        assert 14 in peak_hours_result


class TestSubscriptionIntelligence:
    """Test the main subscription intelligence coordinator."""

    @pytest.fixture
    def subscription_intelligence(self):
        return SubscriptionIntelligence(
            daily_limit=10000, batch_size=5, cache_ttl_seconds=300
        )

    @pytest.mark.asyncio
    async def test_process_request_new(self, subscription_intelligence):
        """Test processing a new request."""
        mock_processor = AsyncMock(return_value={"status": "completed"})

        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}

        result = await subscription_intelligence.process_request(
            request, mock_processor
        )

        assert result["status"] == "completed"
        mock_processor.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_request_duplicate(self, subscription_intelligence):
        """Test processing a duplicate request returns cached result."""
        mock_processor = AsyncMock(return_value={"status": "completed"})

        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}

        # First request
        await subscription_intelligence.process_request(request, mock_processor)

        # Second identical request
        result = await subscription_intelligence.process_request(
            request, mock_processor
        )

        assert result["status"] == "completed"
        # Processor should only be called once (first time)
        mock_processor.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_request_quota_exceeded(self, subscription_intelligence):
        """Test behavior when daily quota is exceeded."""
        subscription_intelligence.daily_limit = 100  # Low limit for testing
        subscription_intelligence.current_usage = 150  # Already exceeded

        mock_processor = AsyncMock()
        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}

        with pytest.raises(Exception) as exc_info:
            await subscription_intelligence.process_request(request, mock_processor)

        assert "quota exceeded" in str(exc_info.value).lower()
        mock_processor.assert_not_called()

    def test_should_batch_request(self, subscription_intelligence):
        """Test batching decision logic."""
        # Simple requests should be batched
        simple_request = {"type": "CODE_ANALYSIS", "payload": {"file": "small.py"}}
        assert subscription_intelligence.should_batch_request(simple_request)

        # Complex requests should not be batched
        complex_request = {
            "type": "PR_REVIEW",
            "payload": {"pr_number": 123, "large_diff": "x" * 10000},
        }
        assert not subscription_intelligence.should_batch_request(complex_request)

    def test_estimate_token_usage(self, subscription_intelligence):
        """Test token usage estimation."""
        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}

        estimate = subscription_intelligence.estimate_token_usage(request)

        assert isinstance(estimate, int)
        assert estimate > 0

    def test_get_usage_stats(self, subscription_intelligence):
        """Test usage statistics retrieval."""
        subscription_intelligence.current_usage = 5000
        subscription_intelligence.daily_limit = 10000

        stats = subscription_intelligence.get_usage_stats()

        assert stats["current_usage"] == 5000
        assert stats["daily_limit"] == 10000
        assert stats["usage_percentage"] == 50.0
        assert stats["remaining"] == 5000


class TestSubscriptionIntelligenceIntegration:
    """Integration tests for subscription intelligence."""

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test complete workflow from request to response."""
        si = SubscriptionIntelligence(
            daily_limit=10000, batch_size=2, cache_ttl_seconds=300
        )

        # Mock processor
        async def mock_processor(requests):
            return [
                {"status": "completed", "request_id": i} for i in range(len(requests))
            ]

        # Process multiple requests
        requests = [
            {"type": "PR_REVIEW", "payload": {"pr_number": 123}},
            {"type": "PR_REVIEW", "payload": {"pr_number": 124}},
            {"type": "CODE_ANALYSIS", "payload": {"file": "test.py"}},
        ]

        results = []
        for request in requests:
            result = await si.process_request(request, mock_processor)
            results.append(result)

        assert len(results) == 3
        assert all(result["status"] == "completed" for result in results)

    @pytest.mark.asyncio
    async def test_deduplication_with_batching(self):
        """Test that deduplication works with batching."""
        si = SubscriptionIntelligence(
            daily_limit=10000, batch_size=3, cache_ttl_seconds=300
        )

        call_count = 0

        async def counting_processor(requests):
            nonlocal call_count
            call_count += 1
            return [{"status": "completed", "call": call_count} for _ in requests]

        # Same request multiple times
        request = {"type": "PR_REVIEW", "payload": {"pr_number": 123}}

        # First batch of requests
        results = []
        for _ in range(3):
            result = await si.process_request(request, counting_processor)
            results.append(result)

        # All should have same result from cache (after first call)
        assert call_count == 1  # Only called once due to deduplication
        assert all(result["call"] == 1 for result in results)

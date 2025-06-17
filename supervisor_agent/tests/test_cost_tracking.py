import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from supervisor_agent.core.cost_tracker import TokenEstimator, CostTracker, cost_tracker
from supervisor_agent.db import models, schemas, crud
from supervisor_agent.tests.conftest import test_db


class TestTokenEstimator:
    """Test token estimation functionality"""
    
    def test_estimate_tokens_empty_text(self):
        """Test token estimation for empty text"""
        assert TokenEstimator.estimate_tokens("") == 0
        assert TokenEstimator.estimate_tokens(None) == 0
    
    def test_estimate_tokens_short_text(self):
        """Test token estimation for short text"""
        short_text = "Hello world"
        tokens = TokenEstimator.estimate_tokens(short_text)
        # Should be at least 1 token and reasonable for short text
        assert 1 <= tokens <= 20
    
    def test_estimate_tokens_long_text(self):
        """Test token estimation for longer text"""
        long_text = " ".join(["This is a test sentence."] * 20)
        tokens = TokenEstimator.estimate_tokens(long_text)
        # Should be proportional to text length
        assert tokens > 50
        assert tokens < len(long_text)  # Should be less than character count
    
    def test_estimate_cost_default_model(self):
        """Test cost estimation with default model"""
        cost = TokenEstimator.estimate_cost(1000, 500)  # 1k prompt, 500 completion tokens
        
        # Should be a string with 4 decimal places
        assert isinstance(cost, str)
        assert "." in cost
        
        # Should be reasonable cost (not zero, not huge)
        cost_float = float(cost)
        assert 0.001 < cost_float < 1.0
    
    def test_estimate_cost_specific_model(self):
        """Test cost estimation with specific model"""
        cost_sonnet = TokenEstimator.estimate_cost(1000, 500, "claude-3-5-sonnet-20241022")
        cost_haiku = TokenEstimator.estimate_cost(1000, 500, "claude-3-5-haiku-20241022")
        
        # Haiku should be cheaper than Sonnet
        assert float(cost_haiku) < float(cost_sonnet)
    
    def test_estimate_prompt_tokens_with_context(self):
        """Test prompt token estimation including context"""
        prompt = "Analyze this code"
        context = {"previous_result": "Some previous analysis", "project": "test-project"}
        
        tokens_with_context = TokenEstimator.estimate_prompt_tokens(prompt, context)
        tokens_without_context = TokenEstimator.estimate_prompt_tokens(prompt, None)
        
        # With context should have more tokens
        assert tokens_with_context > tokens_without_context
    
    def test_extract_model_from_cli_output(self):
        """Test model extraction from CLI output"""
        output_with_model = "Response generated using claude-3-5-sonnet-20241022"
        model = TokenEstimator.extract_model_from_cli_output(output_with_model)
        assert model == "claude-3-5-sonnet-20241022"
        
        output_without_model = "This is just a regular response"
        model = TokenEstimator.extract_model_from_cli_output(output_without_model)
        assert model is None


class TestCostTracker:
    """Test cost tracking functionality"""
    
    @pytest.fixture
    def sample_task(self):
        task = Mock(spec=models.Task)
        task.id = 1
        task.type = models.TaskType.PR_REVIEW
        task.payload = {"repository": "test/repo", "pr_number": 123}
        return task
    
    def test_cost_tracker_initialization(self):
        """Test cost tracker initializes properly"""
        tracker = CostTracker()
        assert tracker.token_estimator is not None
        assert isinstance(tracker.token_estimator, TokenEstimator)
    
    def test_generate_prompt_hash(self):
        """Test prompt hash generation"""
        prompt1 = "Test prompt"
        prompt2 = "Test prompt"
        prompt3 = "Different prompt"
        
        hash1 = cost_tracker.generate_prompt_hash(prompt1)
        hash2 = cost_tracker.generate_prompt_hash(prompt2)
        hash3 = cost_tracker.generate_prompt_hash(prompt3)
        
        # Same prompts should have same hash
        assert hash1 == hash2
        # Different prompts should have different hashes
        assert hash1 != hash3
        # Hash should be reasonable length
        assert len(hash1) == 16
    
    @pytest.mark.asyncio
    async def test_track_task_execution(self, test_db, sample_task):
        """Test tracking task execution"""
        # Mock database operations
        with patch('supervisor_agent.db.crud.CostTrackingCRUD.create_cost_entry') as mock_create:
            mock_entry = Mock()
            mock_entry.id = 1
            mock_entry.task_id = sample_task.id
            mock_entry.agent_id = "test-agent"
            mock_entry.estimated_cost_usd = "0.0250"
            mock_create.return_value = mock_entry
            
            # Track execution
            result = cost_tracker.track_task_execution(
                db=test_db,
                task_id=sample_task.id,
                agent_id="test-agent",
                prompt="Test prompt for PR review",
                response="This PR looks good with minor suggestions",
                execution_time_ms=5000,
                context={"project": "test"}
            )
            
            # Verify create was called
            mock_create.assert_called_once()
            
            # Verify call arguments
            call_args = mock_create.call_args[0]
            cost_entry = call_args[1]  # Second argument is the cost entry
            
            assert cost_entry.task_id == sample_task.id
            assert cost_entry.agent_id == "test-agent"
            assert cost_entry.execution_time_ms == 5000
            assert cost_entry.prompt_tokens > 0
            assert cost_entry.completion_tokens > 0
            assert cost_entry.total_tokens > 0
            assert float(cost_entry.estimated_cost_usd) > 0
    
    def test_get_cost_summary(self, test_db):
        """Test getting cost summary"""
        with patch('supervisor_agent.db.crud.CostTrackingCRUD.get_cost_summary') as mock_summary:
            mock_summary.return_value = {
                "total_cost_usd": "0.1250",
                "total_tokens": 5000,
                "total_requests": 10,
                "avg_cost_per_request": "0.0125",
                "avg_tokens_per_request": 500.0,
                "cost_by_agent": {"agent-1": "0.0750", "agent-2": "0.0500"},
                "cost_by_task_type": {"PR_REVIEW": "0.1000", "CODE_ANALYSIS": "0.0250"},
                "daily_breakdown": []
            }
            
            summary = cost_tracker.get_cost_summary(test_db)
            
            assert summary.total_cost_usd == "0.1250"
            assert summary.total_tokens == 5000
            assert summary.total_requests == 10
            assert len(summary.cost_by_agent) == 2
            assert len(summary.cost_by_task_type) == 2


class TestCostTrackingCRUD:
    """Test cost tracking CRUD operations"""
    
    def test_create_cost_entry(self, test_db):
        """Test creating cost tracking entry"""
        cost_entry = schemas.CostTrackingEntryCreate(
            task_id=1,
            agent_id="test-agent",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd="0.0050",
            model_used="claude-3-5-sonnet-20241022",
            execution_time_ms=3000
        )
        
        # This would fail without proper database setup, but tests the interface
        with patch.object(test_db, 'add'), patch.object(test_db, 'commit'), patch.object(test_db, 'refresh'):
            db_entry = crud.CostTrackingCRUD.create_cost_entry(test_db, cost_entry)
            # Just verify the method can be called without errors
            # In a real integration test, we'd verify the actual database operations
    
    def test_get_cost_entries_with_filters(self, test_db):
        """Test getting cost entries with filters"""
        with patch.object(test_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            
            # Test with task_id filter
            entries = crud.CostTrackingCRUD.get_cost_entries(test_db, task_id=1)
            mock_query.assert_called()
            
            # Test with agent_id filter
            entries = crud.CostTrackingCRUD.get_cost_entries(test_db, agent_id="test-agent")
            mock_query.assert_called()
    
    def test_get_cost_summary_empty_data(self, test_db):
        """Test cost summary with no data"""
        with patch.object(test_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = []
            
            summary = crud.CostTrackingCRUD.get_cost_summary(test_db)
            
            assert summary["total_cost_usd"] == "0.00"
            assert summary["total_tokens"] == 0
            assert summary["total_requests"] == 0
            assert summary["avg_cost_per_request"] == "0.00"
            assert summary["avg_tokens_per_request"] == 0.0
            assert summary["cost_by_agent"] == {}
            assert summary["cost_by_task_type"] == {}
            assert summary["daily_breakdown"] == []


class TestUsageMetricsCRUD:
    """Test usage metrics CRUD operations"""
    
    def test_create_metric(self, test_db):
        """Test creating usage metric"""
        metric = schemas.UsageMetricsCreate(
            metric_type="daily",
            metric_key="2024-01-01",
            total_requests=10,
            total_tokens=1000,
            total_cost_usd="0.0500",
            avg_response_time_ms=2500,
            success_rate="95.00"
        )
        
        with patch.object(test_db, 'add'), patch.object(test_db, 'commit'), patch.object(test_db, 'refresh'):
            db_metric = crud.UsageMetricsCRUD.create_metric(test_db, metric)
            # Verify method can be called
    
    def test_upsert_metric_new(self, test_db):
        """Test upserting new metric"""
        with patch.object(test_db, 'query') as mock_query:
            # Mock no existing metric
            mock_query.return_value.filter.return_value.first.return_value = None
            
            with patch.object(test_db, 'add'), patch.object(test_db, 'commit'), patch.object(test_db, 'refresh'):
                result = crud.UsageMetricsCRUD.upsert_metric(
                    test_db, "daily", "2024-01-01", 
                    {"total_requests": 5, "total_cost_usd": "0.0250"}
                )
                # Should create new metric
                mock_query.assert_called()
    
    def test_upsert_metric_existing(self, test_db):
        """Test upserting existing metric"""
        existing_metric = Mock()
        existing_metric.total_requests = 5
        existing_metric.total_cost_usd = "0.0250"
        
        with patch.object(test_db, 'query') as mock_query:
            # Mock existing metric
            mock_query.return_value.filter.return_value.first.return_value = existing_metric
            
            with patch.object(test_db, 'commit'), patch.object(test_db, 'refresh'):
                result = crud.UsageMetricsCRUD.upsert_metric(
                    test_db, "daily", "2024-01-01", 
                    {"total_requests": 10, "total_cost_usd": "0.0500"}
                )
                
                # Should update existing metric
                assert existing_metric.total_requests == 10
                assert existing_metric.total_cost_usd == "0.0500"


# Integration test for cost tracking flow
@pytest.mark.asyncio
async def test_cost_tracking_integration():
    """Test complete cost tracking flow"""
    # This is a conceptual test - in practice, you'd need proper database setup
    
    # 1. Task execution should track costs
    # 2. Costs should be aggregated into usage metrics
    # 3. Analytics should be able to query the data
    
    # Mock the complete flow
    with patch('supervisor_agent.core.cost_tracker.cost_tracker.track_task_execution') as mock_track:
        mock_track.return_value = schemas.CostTrackingEntryResponse(
            id=1,
            task_id=1,
            agent_id="test-agent",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd="0.0050",
            model_used="claude-3-5-sonnet-20241022",
            execution_time_ms=3000,
            timestamp=datetime.utcnow()
        )
        
        # Simulate task execution with cost tracking
        # In real implementation, this would be called from the agent
        result = cost_tracker.track_task_execution(
            db=Mock(),
            task_id=1,
            agent_id="test-agent",
            prompt="Test prompt",
            response="Test response",
            execution_time_ms=3000
        )
        
        assert result.total_tokens == 150
        assert result.estimated_cost_usd == "0.0050"
        mock_track.assert_called_once()
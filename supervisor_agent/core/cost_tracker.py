"""
Cost tracking and token estimation for Claude API usage
"""

import hashlib
import re
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from supervisor_agent.db import crud, schemas
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class TokenEstimator:
    """Estimates token usage for Claude API calls"""
    
    # Claude pricing (as of 2024) - these should be updated based on current pricing
    CLAUDE_PRICING = {
        "claude-3-5-sonnet-20241022": {
            "input": 0.003,   # per 1K tokens
            "output": 0.015   # per 1K tokens
        },
        "claude-3-5-haiku-20241022": {
            "input": 0.001,   # per 1K tokens
            "output": 0.005   # per 1K tokens
        },
        "claude-3-opus-20240229": {
            "input": 0.015,   # per 1K tokens
            "output": 0.075   # per 1K tokens
        },
        # Default fallback pricing
        "default": {
            "input": 0.003,
            "output": 0.015
        }
    }
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count for text.
        This is a rough approximation - actual tokenization may differ.
        """
        if not text:
            return 0
            
        # Rough estimation: 1 token ≈ 4 characters for English text
        # This includes punctuation, spaces, etc.
        # Claude uses a different tokenizer, but this gives a reasonable estimate
        
        # Count words and characters
        word_count = len(text.split())
        char_count = len(text)
        
        # Use a hybrid approach:
        # - For short text, use character-based estimation
        # - For longer text, use word-based estimation with adjustments
        
        if char_count < 100:
            # Short text: roughly 4 chars per token
            estimated_tokens = char_count // 4
        else:
            # Longer text: roughly 0.75 tokens per word, with character adjustment
            word_based = int(word_count * 0.75)
            char_based = char_count // 4
            # Take average of both approaches
            estimated_tokens = (word_based + char_based) // 2
        
        # Add overhead for special tokens, formatting, etc.
        overhead = max(10, estimated_tokens // 20)  # 5% overhead, minimum 10 tokens
        
        return max(1, estimated_tokens + overhead)
    
    @staticmethod
    def estimate_cost(prompt_tokens: int, completion_tokens: int, 
                     model: str = "default") -> str:
        """
        Estimate cost in USD for token usage.
        Returns cost as string to maintain precision.
        """
        pricing = TokenEstimator.CLAUDE_PRICING.get(model, 
                                                   TokenEstimator.CLAUDE_PRICING["default"])
        
        # Calculate cost per 1K tokens
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        
        total_cost = input_cost + output_cost
        
        # Return as string with 4 decimal places for precision
        return f"{total_cost:.4f}"
    
    @staticmethod
    def estimate_prompt_tokens(prompt: str, context: Optional[Dict[str, Any]] = None) -> int:
        """
        Estimate tokens for a prompt including context and system messages.
        """
        base_tokens = TokenEstimator.estimate_tokens(prompt)
        
        # Add tokens for context/shared memory
        context_tokens = 0
        if context:
            context_str = str(context)
            context_tokens = TokenEstimator.estimate_tokens(context_str)
        
        # Add tokens for system message overhead (Claude has system prompts)
        system_overhead = 50  # Estimated system prompt tokens
        
        return base_tokens + context_tokens + system_overhead
    
    @staticmethod
    def extract_model_from_cli_output(output: str) -> Optional[str]:
        """
        Try to extract the model name from Claude CLI output.
        This is a best-effort attempt.
        """
        # Look for common model patterns in output
        model_patterns = [
            r"claude-3-5-sonnet-\d+",
            r"claude-3-5-haiku-\d+", 
            r"claude-3-opus-\d+",
            r"claude-3-sonnet-\d+",
            r"claude-3-haiku-\d+"
        ]
        
        for pattern in model_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(0).lower()
        
        return None


class CostTracker:
    """Main cost tracking service"""
    
    def __init__(self):
        self.token_estimator = TokenEstimator()
        
    def track_task_execution(self, db: Session, task_id: int, agent_id: str,
                           prompt: str, response: str, execution_time_ms: int,
                           context: Optional[Dict[str, Any]] = None) -> schemas.CostTrackingEntryResponse:
        """
        Track cost and usage for a task execution.
        """
        try:
            # Estimate tokens
            prompt_tokens = self.token_estimator.estimate_prompt_tokens(prompt, context)
            completion_tokens = self.token_estimator.estimate_tokens(response)
            total_tokens = prompt_tokens + completion_tokens
            
            # Try to extract model from response (best effort)
            model_used = self.token_estimator.extract_model_from_cli_output(response)
            if not model_used:
                model_used = "claude-3-5-sonnet-20241022"  # Default assumption
            
            # Estimate cost
            estimated_cost = self.token_estimator.estimate_cost(
                prompt_tokens, completion_tokens, model_used
            )
            
            # Create cost tracking entry
            cost_entry = schemas.CostTrackingEntryCreate(
                task_id=task_id,
                agent_id=agent_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
                model_used=model_used,
                execution_time_ms=execution_time_ms
            )
            
            # Save to database
            db_entry = crud.CostTrackingCRUD.create_cost_entry(db, cost_entry)
            
            # Update usage metrics
            self._update_usage_metrics(db, agent_id, total_tokens, float(estimated_cost), 
                                     execution_time_ms, success=True)
            
            logger.info(f"Tracked cost for task {task_id}: ${estimated_cost} "
                       f"({total_tokens} tokens, {execution_time_ms}ms)")
            
            return schemas.CostTrackingEntryResponse.model_validate(db_entry)
            
        except Exception as e:
            logger.error(f"Failed to track cost for task {task_id}: {str(e)}")
            # Still update metrics for failed requests
            self._update_usage_metrics(db, agent_id, 0, 0.0, execution_time_ms, success=False)
            raise
    
    def _update_usage_metrics(self, db: Session, agent_id: str, tokens: int, 
                            cost: float, execution_time_ms: int, success: bool):
        """Update aggregated usage metrics"""
        try:
            now = datetime.utcnow()
            date_key = now.strftime("%Y-%m-%d")
            hour_key = now.strftime("%Y-%m-%d-%H")
            
            # Update daily metrics
            daily_metrics = self._get_or_create_metrics(db, "daily", date_key)
            self._increment_metrics(db, daily_metrics, tokens, cost, execution_time_ms, success)
            
            # Update hourly metrics
            hourly_metrics = self._get_or_create_metrics(db, "hourly", hour_key)
            self._increment_metrics(db, hourly_metrics, tokens, cost, execution_time_ms, success)
            
            # Update agent metrics
            agent_metrics = self._get_or_create_metrics(db, "agent", agent_id)
            self._increment_metrics(db, agent_metrics, tokens, cost, execution_time_ms, success)
            
        except Exception as e:
            logger.error(f"Failed to update usage metrics: {str(e)}")
    
    def _get_or_create_metrics(self, db: Session, metric_type: str, metric_key: str) -> schemas.UsageMetricsResponse:
        """Get existing metrics or create new ones"""
        existing = db.query(crud.models.UsageMetrics).filter(
            crud.models.UsageMetrics.metric_type == metric_type,
            crud.models.UsageMetrics.metric_key == metric_key
        ).first()
        
        if existing:
            return schemas.UsageMetricsResponse.model_validate(existing)
        else:
            # Create new metrics entry
            new_metrics = schemas.UsageMetricsCreate(
                metric_type=metric_type,
                metric_key=metric_key,
                total_requests=0,
                total_tokens=0,
                total_cost_usd="0.0000",
                avg_response_time_ms=0,
                success_rate="100.00"
            )
            db_metrics = crud.UsageMetricsCRUD.create_metric(db, new_metrics)
            return schemas.UsageMetricsResponse.model_validate(db_metrics)
    
    def _increment_metrics(self, db: Session, metrics: schemas.UsageMetricsResponse, 
                          tokens: int, cost: float, execution_time_ms: int, success: bool):
        """Increment usage metrics with new data"""
        # Calculate new values
        new_requests = metrics.total_requests + 1
        new_tokens = metrics.total_tokens + tokens
        new_cost = float(metrics.total_cost_usd) + cost
        
        # Calculate new average response time
        old_total_time = metrics.avg_response_time_ms * metrics.total_requests
        new_avg_time = (old_total_time + execution_time_ms) // new_requests
        
        # Calculate new success rate
        old_successes = (float(metrics.success_rate) / 100) * metrics.total_requests
        new_successes = old_successes + (1 if success else 0)
        new_success_rate = (new_successes / new_requests) * 100
        
        # Update metrics
        update_data = {
            "total_requests": new_requests,
            "total_tokens": new_tokens,
            "total_cost_usd": f"{new_cost:.4f}",
            "avg_response_time_ms": new_avg_time,
            "success_rate": f"{new_success_rate:.2f}"
        }
        
        crud.UsageMetricsCRUD.upsert_metric(
            db, metrics.metric_type, metrics.metric_key, update_data
        )
    
    def get_cost_summary(self, db: Session, start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> schemas.CostSummaryResponse:
        """Get cost summary for a time period"""
        summary_data = crud.CostTrackingCRUD.get_cost_summary(db, start_date, end_date)
        return schemas.CostSummaryResponse(**summary_data)
    
    def generate_prompt_hash(self, prompt: str) -> str:
        """Generate a hash for prompt deduplication and analysis"""
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]


# Global instance
cost_tracker = CostTracker()
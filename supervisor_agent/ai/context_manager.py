"""
Smart Context Manager for dynamic context window handling and optimization.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from supervisor_agent.ai.providers import AIMessage, ModelInfo
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ContextMetrics(BaseModel):
    """Metrics for context window usage"""
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    context_window_used: float = 0.0  # Percentage of context window used
    truncated_messages: int = 0
    summarized_chunks: int = 0


class ContextChunk(BaseModel):
    """A chunk of conversation context"""
    messages: List[AIMessage]
    token_count: int
    importance_score: float
    created_at: datetime
    chunk_type: str = "conversation"  # conversation, summary, system
    metadata: Dict[str, Any] = {}


class ContextStrategy(BaseModel):
    """Strategy for context management"""
    max_context_ratio: float = 0.85  # Use max 85% of context window
    preserve_recent_messages: int = 10  # Always keep last 10 messages
    importance_threshold: float = 0.6  # Keep messages above this importance
    enable_summarization: bool = True
    summary_ratio: float = 0.3  # Summarize to 30% of original length
    enable_compression: bool = True


class SmartContextManager:
    """
    Manages conversation context with intelligent pruning and optimization.
    """
    
    def __init__(self, strategy: Optional[ContextStrategy] = None):
        self.strategy = strategy or ContextStrategy()
        self.metrics = ContextMetrics()
        self._token_estimator = TokenEstimator()
        
    def optimize_context(
        self,
        messages: List[AIMessage],
        model_info: ModelInfo,
        target_max_tokens: Optional[int] = None
    ) -> Tuple[List[AIMessage], ContextMetrics]:
        """
        Optimize conversation context for the given model's context window.
        
        Args:
            messages: List of conversation messages
            model_info: Information about the target model
            target_max_tokens: Override for max tokens (for completion space)
            
        Returns:
            Tuple of optimized messages and context metrics
        """
        logger.info(f"Optimizing context for model {model_info.id} with {len(messages)} messages")
        
        # Calculate available context window
        max_context_tokens = int(model_info.context_window * self.strategy.max_context_ratio)
        if target_max_tokens:
            max_context_tokens = min(max_context_tokens, target_max_tokens)
        
        # Estimate current token usage
        total_tokens = sum(self._token_estimator.estimate_tokens(msg.content) for msg in messages)
        
        # If we're within limits, return as-is
        if total_tokens <= max_context_tokens:
            self.metrics = ContextMetrics(
                total_tokens=total_tokens,
                prompt_tokens=total_tokens,
                context_window_used=total_tokens / model_info.context_window
            )
            logger.info(f"Context within limits: {total_tokens}/{max_context_tokens} tokens")
            return messages, self.metrics
        
        # Need to optimize - apply context management strategies
        optimized_messages = self._apply_context_strategies(
            messages, max_context_tokens, model_info
        )
        
        # Calculate final metrics
        final_tokens = sum(self._token_estimator.estimate_tokens(msg.content) for msg in optimized_messages)
        self.metrics = ContextMetrics(
            total_tokens=final_tokens,
            prompt_tokens=final_tokens,
            context_window_used=final_tokens / model_info.context_window,
            truncated_messages=len(messages) - len(optimized_messages),
            summarized_chunks=getattr(self, '_summarized_chunks', 0)
        )
        
        logger.info(f"Context optimized: {len(messages)} -> {len(optimized_messages)} messages, "
                   f"{total_tokens} -> {final_tokens} tokens")
        
        return optimized_messages, self.metrics
    
    def _apply_context_strategies(
        self,
        messages: List[AIMessage],
        max_tokens: int,
        model_info: ModelInfo
    ) -> List[AIMessage]:
        """Apply context optimization strategies"""
        
        # Step 1: Separate system messages and preserve recent messages
        system_messages = [msg for msg in messages if msg.role == "system"]
        conversation_messages = [msg for msg in messages if msg.role != "system"]
        
        # Always preserve the most recent messages
        recent_messages = conversation_messages[-self.strategy.preserve_recent_messages:]
        older_messages = conversation_messages[:-self.strategy.preserve_recent_messages]
        
        # Step 2: Calculate token budget
        system_tokens = sum(self._token_estimator.estimate_tokens(msg.content) for msg in system_messages)
        recent_tokens = sum(self._token_estimator.estimate_tokens(msg.content) for msg in recent_messages)
        
        available_tokens = max_tokens - system_tokens - recent_tokens
        
        if available_tokens <= 0:
            # Even recent messages exceed limit - truncate recent messages
            logger.warning("Even recent messages exceed context limit - applying aggressive truncation")
            return system_messages + self._truncate_recent_messages(recent_messages, max_tokens - system_tokens)
        
        # Step 3: Process older messages with available token budget
        processed_older = self._process_older_messages(older_messages, available_tokens, model_info)
        
        # Step 4: Combine all parts
        result_messages = system_messages + processed_older + recent_messages
        
        return result_messages
    
    def _process_older_messages(
        self,
        messages: List[AIMessage],
        token_budget: int,
        model_info: ModelInfo
    ) -> List[AIMessage]:
        """Process older messages with importance scoring and summarization"""
        
        if not messages or token_budget <= 0:
            return []
        
        # Step 1: Score messages by importance
        scored_messages = []
        for i, msg in enumerate(messages):
            importance = self._calculate_importance_score(msg, i, len(messages))
            token_count = self._token_estimator.estimate_tokens(msg.content)
            scored_messages.append((msg, importance, token_count))
        
        # Step 2: Sort by importance (descending)
        scored_messages.sort(key=lambda x: x[1], reverse=True)
        
        # Step 3: Select messages within budget, prioritizing by importance
        selected_messages = []
        used_tokens = 0
        
        for msg, importance, tokens in scored_messages:
            if used_tokens + tokens <= token_budget and importance >= self.strategy.importance_threshold:
                selected_messages.append(msg)
                used_tokens += tokens
            elif self.strategy.enable_summarization and tokens > token_budget * 0.1:
                # Try to summarize large messages
                summary = self._summarize_message(msg, int(tokens * self.strategy.summary_ratio))
                summary_tokens = self._token_estimator.estimate_tokens(summary.content)
                if used_tokens + summary_tokens <= token_budget:
                    selected_messages.append(summary)
                    used_tokens += summary_tokens
                    self._summarized_chunks = getattr(self, '_summarized_chunks', 0) + 1
        
        # Step 4: Restore chronological order
        original_indices = {id(msg): i for i, msg in enumerate(messages)}
        selected_messages.sort(key=lambda msg: original_indices.get(id(msg), 0))
        
        return selected_messages
    
    def _calculate_importance_score(self, message: AIMessage, index: int, total: int) -> float:
        """Calculate importance score for a message (0.0 to 1.0)"""
        
        # Base score from recency (newer = more important)
        recency_score = (index + 1) / total
        
        # Content-based scoring
        content_score = 0.5  # Base score
        content = message.content.lower()
        
        # Boost for certain keywords/patterns
        important_keywords = [
            'error', 'exception', 'bug', 'issue', 'problem',
            'task', 'todo', 'action', 'next steps',
            'decision', 'conclusion', 'summary', 'result'
        ]
        
        keyword_boost = sum(0.1 for keyword in important_keywords if keyword in content)
        content_score = min(1.0, content_score + keyword_boost)
        
        # Boost for longer, detailed messages (up to a point)
        length_score = min(0.2, len(message.content) / 1000)
        
        # Role-based scoring
        role_scores = {
            'system': 0.9,  # System messages are usually important
            'user': 0.7,    # User messages drive conversation
            'assistant': 0.6  # Assistant responses
        }
        role_score = role_scores.get(message.role, 0.5)
        
        # Combine scores with weights
        final_score = (
            recency_score * 0.3 +
            content_score * 0.3 +
            length_score * 0.1 +
            role_score * 0.3
        )
        
        return min(1.0, final_score)
    
    def _summarize_message(self, message: AIMessage, target_tokens: int) -> AIMessage:
        """Create a summarized version of a message"""
        
        content = message.content
        
        # Simple extractive summarization - take first and last parts
        if len(content) <= target_tokens:
            return message
        
        # Estimate how much text we can keep
        chars_per_token = len(content) / self._token_estimator.estimate_tokens(content)
        target_chars = int(target_tokens * chars_per_token * 0.8)  # Leave some buffer
        
        if target_chars < 100:  # Too small to summarize meaningfully
            return AIMessage(
                role=message.role,
                content=f"[Summarized: {len(content)} chars -> truncated]"
            )
        
        # Take first 60% and last 40% of target length
        first_part_chars = int(target_chars * 0.6)
        last_part_chars = target_chars - first_part_chars
        
        first_part = content[:first_part_chars]
        last_part = content[-last_part_chars:] if last_part_chars > 0 else ""
        
        summarized_content = f"{first_part}...[truncated]...{last_part}" if last_part else f"{first_part}...[truncated]"
        
        return AIMessage(
            role=message.role,
            content=summarized_content
        )
    
    def _truncate_recent_messages(self, messages: List[AIMessage], max_tokens: int) -> List[AIMessage]:
        """Truncate recent messages to fit within token limit"""
        
        result = []
        used_tokens = 0
        
        # Process from most recent backwards
        for msg in reversed(messages):
            msg_tokens = self._token_estimator.estimate_tokens(msg.content)
            if used_tokens + msg_tokens <= max_tokens:
                result.insert(0, msg)
                used_tokens += msg_tokens
            else:
                # Try to fit a truncated version
                remaining_tokens = max_tokens - used_tokens
                if remaining_tokens > 50:  # Only if we have reasonable space
                    truncated = self._summarize_message(msg, remaining_tokens)
                    result.insert(0, truncated)
                break
        
        return result
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        return self._token_estimator.estimate_tokens(text)
    
    def get_metrics(self) -> ContextMetrics:
        """Get current context metrics"""
        return self.metrics


class TokenEstimator:
    """
    Estimates token count for text content.
    """
    
    def __init__(self):
        # Rough estimates based on common tokenization patterns
        self.chars_per_token = 4  # Conservative estimate
        
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        This is a simplified estimator. In production, you might want to use
        tiktoken or similar libraries for more accurate estimates.
        """
        
        if not text:
            return 0
            
        # Basic estimation based on character count
        base_tokens = len(text) / self.chars_per_token
        
        # Adjust for whitespace and punctuation
        word_count = len(text.split())
        
        # Code content tends to have more tokens per character
        if self._looks_like_code(text):
            base_tokens *= 1.3
        
        # JSON content is also more token-dense
        if self._looks_like_json(text):
            base_tokens *= 1.2
        
        return max(1, int(base_tokens))
    
    def _looks_like_code(self, text: str) -> bool:
        """Heuristic to detect if text looks like code"""
        code_indicators = ['{', '}', '()', '=>', 'function', 'class', 'def ', 'import ', 'const ', 'let ']
        return sum(1 for indicator in code_indicators if indicator in text) >= 2
    
    def _looks_like_json(self, text: str) -> bool:
        """Heuristic to detect if text looks like JSON"""
        try:
            json.loads(text.strip())
            return True
        except (json.JSONDecodeError, ValueError):
            return False


# Example usage and configuration
DEFAULT_CONTEXT_STRATEGY = ContextStrategy(
    max_context_ratio=0.85,
    preserve_recent_messages=8,
    importance_threshold=0.5,
    enable_summarization=True,
    summary_ratio=0.4,
    enable_compression=True
)

AGGRESSIVE_CONTEXT_STRATEGY = ContextStrategy(
    max_context_ratio=0.75,
    preserve_recent_messages=5,
    importance_threshold=0.7,
    enable_summarization=True,
    summary_ratio=0.3,
    enable_compression=True
)

CONSERVATIVE_CONTEXT_STRATEGY = ContextStrategy(
    max_context_ratio=0.9,
    preserve_recent_messages=15,
    importance_threshold=0.3,
    enable_summarization=False,
    summary_ratio=0.5,
    enable_compression=False
)
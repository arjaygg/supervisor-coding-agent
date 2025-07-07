"""
AI Manager for provider selection, fallback handling, and cost optimization.
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from pydantic import BaseModel

from supervisor_agent.ai.providers import (
    AIMessage,
    AIProvider,
    AIResponse,
    AnthropicProvider,
    LocalProvider,
    ModelCapability,
    ModelInfo,
    ModelTier,
    OpenAIProvider,
    StreamingChunk,
)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ProviderConfig(BaseModel):
    """Configuration for an AI provider"""
    name: str
    provider_class: str
    api_key: str
    base_url: Optional[str] = None
    enabled: bool = True
    priority: int = 0  # Lower number = higher priority
    rate_limit_per_minute: int = 1000
    cost_multiplier: float = 1.0  # For custom pricing adjustments


class AIManagerConfig(BaseModel):
    """Configuration for the AI Manager"""
    providers: List[ProviderConfig]
    default_model_preferences: Dict[str, str] = {}  # capability -> model_id
    cost_optimization: bool = True
    fallback_enabled: bool = True
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    request_timeout_seconds: float = 60.0


class RequestContext(BaseModel):
    """Context for an AI request"""
    user_id: Optional[str] = None
    thread_id: Optional[str] = None
    task_type: Optional[str] = None
    priority: str = "normal"  # low, normal, high, urgent
    budget_limit: Optional[float] = None
    preferred_providers: List[str] = []
    required_capabilities: List[ModelCapability] = []
    max_response_time_ms: Optional[int] = None


class UsageStats(BaseModel):
    """Usage statistics for tracking"""
    provider: str
    model: str
    requests_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    avg_response_time_ms: float = 0.0
    success_rate: float = 1.0
    last_used: Optional[datetime] = None


class AIManager:
    """
    Central AI manager that handles multiple providers, fallbacks, and optimization.
    """
    
    def __init__(self, config: AIManagerConfig):
        self.config = config
        self.providers: Dict[str, AIProvider] = {}
        self.usage_stats: Dict[str, UsageStats] = {}
        self.rate_limits: Dict[str, List[datetime]] = {}
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize all configured providers"""
        if self._initialized:
            return
            
        provider_classes = {
            "anthropic": AnthropicProvider,
            "openai": OpenAIProvider,
            "local": LocalProvider,
        }
        
        for provider_config in self.config.providers:
            if not provider_config.enabled:
                continue
                
            provider_class = provider_classes.get(provider_config.provider_class)
            if not provider_class:
                logger.warning(f"Unknown provider class: {provider_config.provider_class}")
                continue
                
            try:
                provider = provider_class(
                    api_key=provider_config.api_key,
                    base_url=provider_config.base_url
                )
                await provider.initialize()
                self.providers[provider_config.name] = provider
                
                # Initialize rate limiting
                self.rate_limits[provider_config.name] = []
                
                logger.info(f"Initialized AI provider: {provider_config.name}")
                
            except Exception as e:
                logger.error(f"Failed to initialize provider {provider_config.name}: {str(e)}")
                
        self._initialized = True
        logger.info(f"AI Manager initialized with {len(self.providers)} providers")
    
    async def generate_response(
        self,
        messages: List[AIMessage],
        context: RequestContext,
        model_preference: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        """
        Generate a response using the best available provider/model combination.
        """
        if not self._initialized:
            await self.initialize()
            
        # Select the best provider and model
        provider, model = await self._select_provider_and_model(
            context, model_preference, kwargs.get("stream", False)
        )
        
        if not provider or not model:
            raise RuntimeError("No suitable provider/model available")
        
        # Track rate limiting
        await self._check_rate_limit(provider.provider_name)
        
        attempt = 0
        last_error = None
        
        while attempt < self.config.max_retry_attempts:
            try:
                logger.info(f"Generating response with {provider.provider_name}:{model.id} (attempt {attempt + 1})")
                
                response = await provider.generate_response(
                    messages=messages,
                    model=model.id,
                    **kwargs
                )
                
                # Update usage statistics
                await self._update_usage_stats(provider.provider_name, model.id, response, success=True)
                
                return response
                
            except Exception as e:
                last_error = e
                attempt += 1
                logger.warning(f"Provider {provider.provider_name} failed (attempt {attempt}): {str(e)}")
                
                # Update failure stats
                await self._update_usage_stats(provider.provider_name, model.id, None, success=False)
                
                if attempt < self.config.max_retry_attempts:
                    if self.config.fallback_enabled:
                        # Try next best provider
                        provider, model = await self._select_provider_and_model(
                            context, model_preference, kwargs.get("stream", False),
                            exclude_providers=[provider.provider_name]
                        )
                        if not provider:
                            break
                    
                    # Wait before retry
                    await asyncio.sleep(self.config.retry_delay_seconds)
        
        raise RuntimeError(f"All providers failed. Last error: {str(last_error)}")
    
    async def stream_response(
        self,
        messages: List[AIMessage],
        context: RequestContext,
        model_preference: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[StreamingChunk]:
        """
        Stream a response using the best available provider/model combination.
        """
        if not self._initialized:
            await self.initialize()
            
        # Select the best provider and model for streaming
        provider, model = await self._select_provider_and_model(
            context, model_preference, stream_required=True
        )
        
        if not provider or not model:
            raise RuntimeError("No suitable streaming provider/model available")
        
        # Track rate limiting
        await self._check_rate_limit(provider.provider_name)
        
        try:
            logger.info(f"Streaming response with {provider.provider_name}:{model.id}")
            
            async for chunk in provider.stream_response(
                messages=messages,
                model=model.id,
                **kwargs
            ):
                yield chunk
            
            # Update usage statistics (approximate for streaming)
            await self._update_usage_stats(provider.provider_name, model.id, None, success=True)
            
        except Exception as e:
            logger.error(f"Streaming failed with {provider.provider_name}: {str(e)}")
            await self._update_usage_stats(provider.provider_name, model.id, None, success=False)
            raise
    
    async def _select_provider_and_model(
        self,
        context: RequestContext,
        model_preference: Optional[str] = None,
        stream_required: bool = False,
        exclude_providers: List[str] = None
    ) -> Tuple[Optional[AIProvider], Optional[ModelInfo]]:
        """
        Select the best provider and model based on context and optimization criteria.
        """
        exclude_providers = exclude_providers or []
        candidates = []
        
        # Collect all available model candidates
        for provider_name, provider in self.providers.items():
            if provider_name in exclude_providers:
                continue
                
            models = provider.get_available_models()
            
            for model_id, model_info in models.items():
                # Check if specific model requested
                if model_preference and model_id != model_preference:
                    continue
                
                # Check streaming requirement
                if stream_required and not model_info.supports_streaming:
                    continue
                
                # Check required capabilities
                if context.required_capabilities:
                    if not all(cap in model_info.capabilities for cap in context.required_capabilities):
                        continue
                
                # Check rate limiting
                if not await self._is_within_rate_limit(provider_name):
                    continue
                
                score = await self._calculate_model_score(
                    provider_name, model_info, context
                )
                
                candidates.append((score, provider, model_info))
        
        if not candidates:
            return None, None
        
        # Sort by score (higher is better)
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Return the best candidate
        _, best_provider, best_model = candidates[0]
        return best_provider, best_model
    
    async def _calculate_model_score(
        self,
        provider_name: str,
        model_info: ModelInfo,
        context: RequestContext
    ) -> float:
        """
        Calculate a score for model selection based on various factors.
        """
        score = 0.0
        
        # Base score from provider priority
        provider_config = next(
            (p for p in self.config.providers if p.name == provider_name),
            None
        )
        if provider_config:
            score += (10 - provider_config.priority) * 10  # Higher priority = higher score
        
        # Performance tier scoring
        tier_scores = {
            ModelTier.FAST: 30,
            ModelTier.BALANCED: 50,
            ModelTier.PREMIUM: 70
        }
        score += tier_scores.get(model_info.tier, 0)
        
        # Cost optimization
        if self.config.cost_optimization:
            # Prefer lower cost models (inverse relationship)
            total_cost_per_1k = model_info.cost_per_input_token + model_info.cost_per_output_token
            if total_cost_per_1k > 0:
                cost_score = max(0, 100 - (total_cost_per_1k * 5))  # Adjust multiplier as needed
                score += cost_score
            else:
                score += 100  # Free models get max cost score
        
        # Context window consideration
        if model_info.context_window >= 32000:
            score += 20
        elif model_info.context_window >= 16000:
            score += 10
        
        # Historical performance
        stats_key = f"{provider_name}:{model_info.id}"
        if stats_key in self.usage_stats:
            stats = self.usage_stats[stats_key]
            score += stats.success_rate * 30  # Up to 30 points for reliability
            
            # Response time bonus (faster is better)
            if stats.avg_response_time_ms < 2000:
                score += 10
            elif stats.avg_response_time_ms < 5000:
                score += 5
        
        # Priority-based adjustments
        if context.priority == "urgent":
            # Prefer faster models for urgent requests
            if ModelCapability.FAST_RESPONSE in model_info.capabilities:
                score += 30
        elif context.priority == "low":
            # Prefer cheaper models for low priority
            if model_info.tier == ModelTier.FAST:
                score += 20
        
        # Budget constraints
        if context.budget_limit:
            estimated_cost = (model_info.cost_per_input_token + model_info.cost_per_output_token) / 1000
            if estimated_cost <= context.budget_limit:
                score += 15
            elif estimated_cost > context.budget_limit * 2:
                score -= 50  # Heavy penalty for exceeding budget
        
        # Preferred providers
        if context.preferred_providers and provider_name in context.preferred_providers:
            score += 25
        
        return score
    
    async def _check_rate_limit(self, provider_name: str) -> None:
        """Check and enforce rate limiting"""
        provider_config = next(
            (p for p in self.config.providers if p.name == provider_name),
            None
        )
        if not provider_config:
            return
        
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old requests
        recent_requests = [
            req_time for req_time in self.rate_limits[provider_name]
            if req_time > minute_ago
        ]
        self.rate_limits[provider_name] = recent_requests
        
        # Check if we're within limits
        if len(recent_requests) >= provider_config.rate_limit_per_minute:
            sleep_time = 60 - (now - recent_requests[0]).total_seconds()
            if sleep_time > 0:
                logger.warning(f"Rate limit reached for {provider_name}, waiting {sleep_time:.1f}s")
                await asyncio.sleep(sleep_time)
        
        # Record this request
        self.rate_limits[provider_name].append(now)
    
    async def _is_within_rate_limit(self, provider_name: str) -> bool:
        """Check if provider is within rate limits without enforcing"""
        provider_config = next(
            (p for p in self.config.providers if p.name == provider_name),
            None
        )
        if not provider_config:
            return True
        
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        recent_requests = [
            req_time for req_time in self.rate_limits[provider_name]
            if req_time > minute_ago
        ]
        
        return len(recent_requests) < provider_config.rate_limit_per_minute
    
    async def _update_usage_stats(
        self,
        provider_name: str,
        model_id: str,
        response: Optional[AIResponse],
        success: bool
    ) -> None:
        """Update usage statistics for analytics"""
        stats_key = f"{provider_name}:{model_id}"
        
        if stats_key not in self.usage_stats:
            self.usage_stats[stats_key] = UsageStats(
                provider=provider_name,
                model=model_id
            )
        
        stats = self.usage_stats[stats_key]
        stats.requests_count += 1
        stats.last_used = datetime.utcnow()
        
        if response:
            usage = response.usage
            stats.total_input_tokens += usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
            stats.total_output_tokens += usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
            stats.total_cost += response.cost_estimate
            
            # Update average response time
            if stats.avg_response_time_ms == 0:
                stats.avg_response_time_ms = response.response_time_ms
            else:
                stats.avg_response_time_ms = (
                    (stats.avg_response_time_ms * (stats.requests_count - 1) + response.response_time_ms)
                    / stats.requests_count
                )
        
        # Update success rate
        if success:
            current_successes = stats.success_rate * (stats.requests_count - 1)
            stats.success_rate = (current_successes + 1) / stats.requests_count
        else:
            current_successes = stats.success_rate * (stats.requests_count - 1)
            stats.success_rate = current_successes / stats.requests_count
    
    async def get_usage_statistics(self) -> Dict[str, UsageStats]:
        """Get current usage statistics"""
        return self.usage_stats.copy()
    
    async def get_available_models(self) -> Dict[str, List[ModelInfo]]:
        """Get all available models grouped by provider"""
        models_by_provider = {}
        
        for provider_name, provider in self.providers.items():
            models_by_provider[provider_name] = list(provider.get_available_models().values())
        
        return models_by_provider
    
    async def cleanup(self) -> None:
        """Cleanup all providers"""
        for provider in self.providers.values():
            try:
                await provider.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up provider: {str(e)}")
        
        self.providers.clear()
        self._initialized = False
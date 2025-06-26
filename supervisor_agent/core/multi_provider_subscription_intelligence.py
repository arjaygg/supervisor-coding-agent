"""
Multi-Provider Subscription Intelligence Module

Enhanced subscription intelligence for managing multiple Claude subscriptions and AI providers.
Extends the existing subscription intelligence with:
- Cross-provider quota tracking
- Intelligent subscription switching
- Usage analytics across providers
- Cost optimization recommendations
- Automatic quota reset handling
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import logging
from enum import Enum

from supervisor_agent.core.subscription_intelligence import (
    RequestHash, CacheEntry, SubscriptionIntelligence
)
from supervisor_agent.providers.provider_registry import ProviderRegistry
from supervisor_agent.providers.base_provider import AIProvider, CostEstimate, ProviderError
from supervisor_agent.db.models import Provider, ProviderUsage
from supervisor_agent.db.crud import ProviderCRUD, ProviderUsageCRUD

logger = logging.getLogger(__name__)


class QuotaStatus(str, Enum):
    """Quota status for providers"""
    AVAILABLE = "available"
    WARNING = "warning"          # 80% used
    CRITICAL = "critical"        # 95% used
    EXHAUSTED = "exhausted"      # 100% used
    UNKNOWN = "unknown"


@dataclass
class ProviderQuotaInfo:
    """Quota information for a specific provider"""
    provider_id: str
    provider_name: str
    daily_limit: int
    current_usage: int
    reset_time: datetime
    status: QuotaStatus
    estimated_remaining_hours: float
    cost_per_request: float
    success_rate: float = 1.0
    
    @property
    def usage_percentage(self) -> float:
        """Calculate usage percentage"""
        if self.daily_limit <= 0:
            return 0.0
        return (self.current_usage / self.daily_limit) * 100.0
        
    @property
    def requests_remaining(self) -> int:
        """Calculate requests remaining"""
        return max(0, self.daily_limit - self.current_usage)
        
    @property
    def is_available(self) -> bool:
        """Check if provider is available for new requests"""
        return self.status in [QuotaStatus.AVAILABLE, QuotaStatus.WARNING]


@dataclass
class CrossProviderAnalytics:
    """Analytics across all providers"""
    total_requests_today: int
    total_cost_today: float
    average_response_time: float
    success_rate: float
    provider_count: int
    most_used_provider: str
    most_cost_effective_provider: str
    quota_utilization: Dict[str, float]
    recommendations: List[str]


class MultiProviderSubscriptionIntelligence:
    """Enhanced subscription intelligence for multi-provider environments"""
    
    def __init__(
        self, 
        provider_registry: ProviderRegistry,
        cache_ttl: int = 300,  # 5 minutes
        quota_check_interval: int = 60  # 1 minute
    ):
        self.provider_registry = provider_registry
        self.cache_ttl = cache_ttl
        self.quota_check_interval = quota_check_interval
        
        # Provider quota tracking
        self.provider_quotas: Dict[str, ProviderQuotaInfo] = {}
        self.last_quota_check = datetime.utcnow() - timedelta(hours=1)
        
        # Enhanced caching with cross-provider deduplication
        self._cache: Dict[str, CacheEntry] = {}
        self._provider_cache_hits: Dict[str, int] = defaultdict(int)
        
        # Usage analytics
        self._daily_usage: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._cost_tracking: Dict[str, List[Tuple[datetime, float]]] = defaultdict(list)
        self._response_times: Dict[str, List[float]] = defaultdict(list)
        
        # Quota management
        self._quota_warnings_sent: Set[str] = set()
        self._auto_switch_enabled = True
        
        logger.info("Multi-Provider Subscription Intelligence initialized")
        
    async def get_optimal_provider(
        self, 
        request_data: Dict[str, Any], 
        exclude_providers: Optional[List[str]] = None,
        cost_priority: float = 0.3,  # 0.0 = speed priority, 1.0 = cost priority
        max_cost_usd: Optional[float] = None
    ) -> Optional[str]:
        """
        Select the optimal provider for a request based on quotas, cost, and performance
        
        Args:
            request_data: The request data to process
            exclude_providers: Providers to exclude from selection
            cost_priority: Weight for cost vs performance (0.0-1.0)
            max_cost_usd: Maximum acceptable cost
            
        Returns:
            Provider ID of optimal provider, or None if none available
        """
        try:
            # Update quota information
            await self._update_quota_information()
            
            # Get available providers
            available_providers = await self._get_available_providers(exclude_providers)
            if not available_providers:
                logger.warning("No available providers for request")
                return None
                
            # Check cache first for deduplication opportunity
            request_hash = RequestHash.generate(request_data)
            cached_result = self._get_cached_result(request_hash)
            if cached_result:
                logger.info("Request cache hit - skipping provider selection")
                return "cache"  # Special indicator for cached result
                
            # Score providers based on multiple factors
            provider_scores = {}
            
            for provider_id in available_providers:
                score = await self._calculate_provider_score(
                    provider_id, request_data, cost_priority, max_cost_usd
                )
                if score > 0:
                    provider_scores[provider_id] = score
                    
            if not provider_scores:
                logger.warning("No providers meet the selection criteria")
                return None
                
            # Select provider with highest score
            optimal_provider = max(provider_scores.items(), key=lambda x: x[1])[0]
            
            logger.info(f"Selected optimal provider: {optimal_provider} (score: {provider_scores[optimal_provider]:.3f})")
            return optimal_provider
            
        except Exception as e:
            logger.error(f"Error selecting optimal provider: {str(e)}")
            return None
            
    async def track_request(
        self, 
        provider_id: str, 
        request_data: Dict[str, Any], 
        response: Any,
        execution_time: float,
        cost_usd: float,
        success: bool
    ) -> None:
        """Track a request for analytics and quota management"""
        try:
            now = datetime.utcnow()
            today = now.date().isoformat()
            
            # Update usage tracking
            self._daily_usage[today][provider_id] += 1
            
            # Track cost
            self._cost_tracking[provider_id].append((now, cost_usd))
            
            # Track response time
            if success:
                self._response_times[provider_id].append(execution_time)
                
            # Update cache if successful
            if success and response:
                request_hash = RequestHash.generate(request_data)
                self._cache[request_hash] = CacheEntry(
                    result=response,
                    timestamp=time.time(),
                    hit_count=0
                )
                
            # Update quota information
            if provider_id in self.provider_quotas:
                self.provider_quotas[provider_id].current_usage += 1
                self._update_quota_status(provider_id)
                
            # Store in database for persistence
            await self._persist_usage_data(provider_id, request_data, cost_usd, execution_time, success)
            
            logger.debug(f"Tracked request for provider {provider_id}: cost=${cost_usd:.4f}, time={execution_time:.2f}s, success={success}")
            
        except Exception as e:
            logger.error(f"Error tracking request: {str(e)}")
            
    async def get_quota_status(self, provider_id: Optional[str] = None) -> Dict[str, ProviderQuotaInfo]:
        """Get quota status for one or all providers"""
        await self._update_quota_information()
        
        if provider_id:
            return {provider_id: self.provider_quotas.get(provider_id)} if provider_id in self.provider_quotas else {}
        
        return self.provider_quotas.copy()
        
    async def get_cross_provider_analytics(self) -> CrossProviderAnalytics:
        """Get comprehensive analytics across all providers"""
        try:
            today = datetime.utcnow().date().isoformat()
            
            # Calculate totals
            total_requests = sum(self._daily_usage[today].values())
            total_cost = sum(
                sum(cost for _, cost in costs if _.date().isoformat() == today)
                for costs in self._cost_tracking.values()
            )
            
            # Calculate average response time
            all_response_times = []
            for times in self._response_times.values():
                all_response_times.extend(times[-100:])  # Last 100 requests per provider
            avg_response_time = sum(all_response_times) / len(all_response_times) if all_response_times else 0.0
            
            # Calculate success rate
            total_successes = sum(
                len(times) for times in self._response_times.values()
            )
            success_rate = total_successes / total_requests if total_requests > 0 else 1.0
            
            # Find most used and most cost-effective providers
            most_used = max(self._daily_usage[today].items(), key=lambda x: x[1])[0] if self._daily_usage[today] else "none"
            
            # Calculate cost effectiveness (requests per dollar)
            cost_effectiveness = {}
            for provider_id, costs in self._cost_tracking.items():
                today_costs = [cost for _, cost in costs if _.date().isoformat() == today]
                today_requests = self._daily_usage[today][provider_id]
                if today_costs and today_requests > 0:
                    cost_per_request = sum(today_costs) / today_requests
                    cost_effectiveness[provider_id] = 1.0 / cost_per_request if cost_per_request > 0 else 0.0
                    
            most_cost_effective = max(cost_effectiveness.items(), key=lambda x: x[1])[0] if cost_effectiveness else "none"
            
            # Quota utilization
            quota_util = {
                pid: info.usage_percentage 
                for pid, info in self.provider_quotas.items()
            }
            
            # Generate recommendations
            recommendations = await self._generate_recommendations()
            
            return CrossProviderAnalytics(
                total_requests_today=total_requests,
                total_cost_today=total_cost,
                average_response_time=avg_response_time,
                success_rate=success_rate,
                provider_count=len(self.provider_registry.providers),
                most_used_provider=most_used,
                most_cost_effective_provider=most_cost_effective,
                quota_utilization=quota_util,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error generating cross-provider analytics: {str(e)}")
            return CrossProviderAnalytics(
                total_requests_today=0,
                total_cost_today=0.0,
                average_response_time=0.0,
                success_rate=0.0,
                provider_count=0,
                most_used_provider="unknown",
                most_cost_effective_provider="unknown",
                quota_utilization={},
                recommendations=["Error generating analytics"]
            )
            
    async def predict_quota_exhaustion(self, provider_id: str) -> Optional[datetime]:
        """Predict when a provider's quota will be exhausted"""
        if provider_id not in self.provider_quotas:
            return None
            
        quota_info = self.provider_quotas[provider_id]
        if quota_info.requests_remaining <= 0:
            return datetime.utcnow()  # Already exhausted
            
        # Calculate usage rate over the last few hours
        recent_usage = self._calculate_recent_usage_rate(provider_id, hours=4)
        if recent_usage <= 0:
            return None  # No recent usage to predict from
            
        # Estimate time to exhaustion
        hours_to_exhaustion = quota_info.requests_remaining / recent_usage
        exhaustion_time = datetime.utcnow() + timedelta(hours=hours_to_exhaustion)
        
        # Don't predict beyond the quota reset time
        if exhaustion_time > quota_info.reset_time:
            return None
            
        return exhaustion_time
        
    async def suggest_provider_switch(self, current_provider_id: str) -> Optional[str]:
        """Suggest an alternative provider if current one is suboptimal"""
        if current_provider_id not in self.provider_quotas:
            return None
            
        current_quota = self.provider_quotas[current_provider_id]
        
        # Switch if current provider is in critical or exhausted state
        if current_quota.status in [QuotaStatus.CRITICAL, QuotaStatus.EXHAUSTED]:
            available_providers = await self._get_available_providers(exclude_providers=[current_provider_id])
            if available_providers:
                # Return the provider with most capacity
                best_provider = min(
                    available_providers,
                    key=lambda pid: self.provider_quotas[pid].usage_percentage
                )
                return best_provider
                
        return None
        
    async def _update_quota_information(self) -> None:
        """Update quota information for all providers"""
        now = datetime.utcnow()
        
        # Only update if enough time has passed
        if now - self.last_quota_check < timedelta(seconds=self.quota_check_interval):
            return
            
        try:
            for provider_id, provider in self.provider_registry.providers.items():
                await self._update_provider_quota(provider_id, provider)
                
            self.last_quota_check = now
            
        except Exception as e:
            logger.error(f"Error updating quota information: {str(e)}")
            
    async def _update_provider_quota(self, provider_id: str, provider: AIProvider) -> None:
        """Update quota information for a specific provider"""
        try:
            # Get health status which should include quota information
            health = await provider.get_health_status()
            
            # Extract quota information from health metrics
            daily_limit = health.metrics.get("daily_quota", 1000)  # Default quota
            current_usage = health.metrics.get("quota_used", 0)
            
            # Calculate reset time (assume daily reset at midnight UTC)
            tomorrow = datetime.utcnow().date() + timedelta(days=1)
            reset_time = datetime.combine(tomorrow, datetime.min.time())
            
            # Determine status
            usage_pct = (current_usage / daily_limit) * 100 if daily_limit > 0 else 0
            if usage_pct >= 100:
                status = QuotaStatus.EXHAUSTED
            elif usage_pct >= 95:
                status = QuotaStatus.CRITICAL
            elif usage_pct >= 80:
                status = QuotaStatus.WARNING
            else:
                status = QuotaStatus.AVAILABLE
                
            # Estimate remaining hours at current usage rate
            remaining_requests = daily_limit - current_usage
            usage_rate = self._calculate_recent_usage_rate(provider_id, hours=1)
            estimated_hours = remaining_requests / usage_rate if usage_rate > 0 else 24.0
            
            # Get cost per request (provider-specific)
            cost_per_request = health.metrics.get("cost_per_request", 0.01)
            
            # Calculate success rate
            success_rate = health.metrics.get("success_rate", health.score)
            
            self.provider_quotas[provider_id] = ProviderQuotaInfo(
                provider_id=provider_id,
                provider_name=provider.name,
                daily_limit=daily_limit,
                current_usage=current_usage,
                reset_time=reset_time,
                status=status,
                estimated_remaining_hours=min(estimated_hours, 24.0),
                cost_per_request=cost_per_request,
                success_rate=success_rate
            )
            
        except Exception as e:
            logger.warning(f"Could not update quota for provider {provider_id}: {str(e)}")
            
    def _update_quota_status(self, provider_id: str) -> None:
        """Update quota status after a request"""
        if provider_id not in self.provider_quotas:
            return
            
        quota_info = self.provider_quotas[provider_id]
        usage_pct = quota_info.usage_percentage
        
        # Update status
        if usage_pct >= 100:
            quota_info.status = QuotaStatus.EXHAUSTED
        elif usage_pct >= 95:
            quota_info.status = QuotaStatus.CRITICAL
        elif usage_pct >= 80:
            quota_info.status = QuotaStatus.WARNING
        else:
            quota_info.status = QuotaStatus.AVAILABLE
            
        # Send warnings if needed
        if quota_info.status in [QuotaStatus.WARNING, QuotaStatus.CRITICAL] and provider_id not in self._quota_warnings_sent:
            logger.warning(f"Provider {provider_id} quota at {usage_pct:.1f}% - status: {quota_info.status}")
            self._quota_warnings_sent.add(provider_id)
            
    async def _get_available_providers(self, exclude_providers: Optional[List[str]] = None) -> List[str]:
        """Get list of available providers"""
        exclude_providers = exclude_providers or []
        available = []
        
        for provider_id in self.provider_registry.providers.keys():
            if provider_id in exclude_providers:
                continue
                
            quota_info = self.provider_quotas.get(provider_id)
            if quota_info and quota_info.is_available:
                available.append(provider_id)
            elif provider_id not in self.provider_quotas:
                # Provider without quota info - assume available
                available.append(provider_id)
                
        return available
        
    async def _calculate_provider_score(
        self, 
        provider_id: str, 
        request_data: Dict[str, Any],
        cost_priority: float,
        max_cost_usd: Optional[float]
    ) -> float:
        """Calculate a score for provider selection"""
        try:
            provider = self.provider_registry.get_provider(provider_id)
            if not provider:
                return 0.0
                
            quota_info = self.provider_quotas.get(provider_id)
            if not quota_info or not quota_info.is_available:
                return 0.0
                
            # Get cost estimate
            # For this implementation, we'll create a mock task to estimate cost
            from supervisor_agent.db.models import Task
            from supervisor_agent.db.enums import TaskType
            mock_task = Task(
                type=TaskType.FEATURE,  # Default task type
                payload=request_data,
                status="pending"
            )
            cost_estimate = provider.estimate_cost(mock_task)
            
            # Check cost constraint
            if max_cost_usd and float(cost_estimate.total_cost_usd) > max_cost_usd:
                return 0.0
                
            # Calculate score components
            quota_score = 1.0 - (quota_info.usage_percentage / 100.0)  # More available quota = higher score
            cost_score = 1.0 - min(1.0, float(cost_estimate.total_cost_usd) / 1.0)  # Lower cost = higher score
            performance_score = quota_info.success_rate  # Higher success rate = higher score
            
            # Average response time score
            recent_times = self._response_times[provider_id][-10:]  # Last 10 requests
            if recent_times:
                avg_time = sum(recent_times) / len(recent_times)
                time_score = max(0.0, 1.0 - (avg_time / 30.0))  # 30s = 0 score, 0s = 1.0 score
            else:
                time_score = 0.5  # Neutral score for new providers
                
            # Weighted combination
            final_score = (
                quota_score * 0.3 +
                cost_score * cost_priority +
                performance_score * 0.3 +
                time_score * (1.0 - cost_priority) * 0.4
            )
            
            return max(0.0, min(1.0, final_score))
            
        except Exception as e:
            logger.error(f"Error calculating provider score for {provider_id}: {str(e)}")
            return 0.0
            
    def _calculate_recent_usage_rate(self, provider_id: str, hours: float) -> float:
        """Calculate usage rate (requests per hour) for recent period"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Count recent requests from cost tracking (as a proxy for request count)
        recent_requests = 0
        for timestamp, _ in self._cost_tracking[provider_id]:
            if timestamp >= cutoff_time:
                recent_requests += 1
                
        return recent_requests / hours if hours > 0 else 0.0
        
    def _get_cached_result(self, request_hash: str) -> Optional[Any]:
        """Get cached result if available and fresh"""
        if request_hash not in self._cache:
            return None
            
        entry = self._cache[request_hash]
        if time.time() - entry.timestamp > self.cache_ttl:
            del self._cache[request_hash]
            return None
            
        entry.hit_count += 1
        return entry.result
        
    async def _persist_usage_data(
        self, 
        provider_id: str, 
        request_data: Dict[str, Any],
        cost_usd: float,
        execution_time: float,
        success: bool
    ) -> None:
        """Persist usage data to database"""
        try:
            # This would integrate with the database layer
            # For now, just log the data
            logger.debug(f"Persisting usage data: provider={provider_id}, cost={cost_usd}, time={execution_time}, success={success}")
            
        except Exception as e:
            logger.error(f"Error persisting usage data: {str(e)}")
            
    async def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        try:
            # Check for underutilized providers
            for provider_id, quota_info in self.provider_quotas.items():
                if quota_info.usage_percentage < 20:
                    recommendations.append(f"Provider {provider_id} is underutilized ({quota_info.usage_percentage:.1f}% used)")
                    
            # Check for cost optimization opportunities
            total_cost_today = sum(
                sum(cost for _, cost in costs if _.date() == datetime.utcnow().date())
                for costs in self._cost_tracking.values()
            )
            
            if total_cost_today > 10.0:  # Arbitrary threshold
                recommendations.append(f"Daily cost is high (${total_cost_today:.2f}) - consider optimizing provider selection")
                
            # Check for performance issues
            for provider_id, times in self._response_times.items():
                if times and len(times) >= 5:
                    avg_time = sum(times[-10:]) / min(10, len(times))
                    if avg_time > 15.0:  # 15 seconds threshold
                        recommendations.append(f"Provider {provider_id} has slow response times ({avg_time:.1f}s average)")
                        
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            recommendations.append("Error generating recommendations")
            
        return recommendations[:5]  # Limit to top 5 recommendations
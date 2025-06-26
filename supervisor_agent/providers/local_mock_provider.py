"""
Local Mock Provider Implementation

This provider provides deterministic mock responses for testing and offline scenarios,
implementing the AIProvider interface without external dependencies.
"""

import asyncio
import hashlib
import json
import random
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .base_provider import (
    ProviderCapabilities,
    ProviderHealth,
    ProviderResponse,
    CostEstimate,
    ProviderStatus,
    Task,
    TaskCapability,
)
from .provider_interfaces import MockProvider
from .base_provider_impl import BaseProviderImpl, TaskExecutionHelper

from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class LocalMockProvider(BaseProviderImpl, MockProvider, TaskExecutionHelper):
    """
    Local mock provider for testing and offline scenarios.
    
    Provides deterministic responses based on request patterns without
    making any external API calls. Useful for development, testing,
    and offline operation.
    """
    
    def __init__(self, provider_id: str, config: Dict[str, Any]):
        BaseProviderImpl.__init__(self, provider_id, config)
        
        # Configuration
        self.response_delay_min: float = config.get("response_delay_min", 0.5)
        self.response_delay_max: float = config.get("response_delay_max", 2.0)
        self.failure_rate: float = config.get("failure_rate", 0.05)  # 5% failure rate
        self.deterministic: bool = config.get("deterministic", True)
        self.custom_responses: Dict[str, str] = config.get("custom_responses", {})
        
        # State tracking
        self._request_count: int = 0
        self._failure_count: int = 0
        self._total_response_time: float = 0.0
        
        # Deterministic failure patterns
        self._failure_pattern: List[int] = config.get("failure_pattern", [])
        self._pattern_index: int = 0
    
    async def initialize(self) -> None:
        """Initialize the local mock provider."""
        self._initialized = True
        logger.info(f"Local mock provider {self.provider_id} initialized")
        
        if not self.deterministic:
            logger.info("Mock provider running in non-deterministic mode")
    
    async def execute_task(self, task: Task, context: Dict[str, Any] = None) -> ProviderResponse:
        """Execute a task with mock response."""
        start_time = datetime.now(timezone.utc)
        
        # Simulate processing delay
        delay = await self._get_response_delay()
        await asyncio.sleep(delay)
        
        execution_time_ms = int(delay * 1000)
        self._request_count += 1
        
        # Determine if this request should fail
        should_fail = self._should_fail()
        
        if should_fail:
            self._failure_count += 1
            error_message = self._generate_error_message(task)
            
            return ProviderResponse(
                success=False,
                result=None,
                provider_id=self.provider_id,
                execution_time_ms=execution_time_ms,
                tokens_used=0,
                cost_usd=0.0,
                error_message=error_message,
                metadata={
                    "mock_provider": True,
                    "task_type": task.type,
                    "request_count": self._request_count,
                    "simulated_failure": True
                }
            )
        
        # Generate successful response
        result = await self._generate_response(task, context or {})
        tokens_used = self._estimate_tokens_for_task(task, result)
        
        self._total_response_time += delay
        
        return ProviderResponse(
            success=True,
            result=result,
            provider_id=self.provider_id,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
            cost_usd=0.0,  # Mock provider has no cost
            model_used="mock-model-v1",
            metadata={
                "mock_provider": True,
                "task_type": task.type,
                "request_count": self._request_count,
                "deterministic": self.deterministic,
                "response_hash": self._get_response_hash(task)
            }
        )
    
    async def execute_batch(self, tasks: List[Task], context: Dict[str, Any] = None) -> List[ProviderResponse]:
        """Execute multiple tasks as a batch."""
        responses = []
        
        # Simulate batch processing with a longer delay
        batch_delay = await self._get_response_delay() * len(tasks) * 0.7  # Batch efficiency
        await asyncio.sleep(batch_delay)
        
        for task in tasks:
            # For batch processing, we don't add individual delays
            response = await self._execute_task_without_delay(task, context)
            responses.append(response)
        
        logger.info(f"Mock provider processed batch of {len(tasks)} tasks")
        return responses
    
    def get_capabilities(self) -> ProviderCapabilities:
        """Get the capabilities of this mock provider."""
        return ProviderCapabilities(
            supported_tasks=[
                TaskCapability.CODE_REVIEW,
                TaskCapability.BUG_FIX,
                TaskCapability.FEATURE_DEVELOPMENT,
                TaskCapability.CODE_ANALYSIS,
                TaskCapability.REFACTORING,
                TaskCapability.DOCUMENTATION,
                TaskCapability.TESTING,
                TaskCapability.SECURITY_ANALYSIS,
                TaskCapability.PERFORMANCE_OPTIMIZATION,
                TaskCapability.GENERAL_CODING,
            ],
            max_tokens_per_request=8000,  # Mock provider can handle large requests
            supports_batching=True,
            supports_streaming=False,
            supports_function_calling=False,
            max_concurrent_requests=100,  # Very high concurrency for testing
            rate_limit_per_minute=1000,
            rate_limit_per_hour=60000,
            rate_limit_per_day=1000000,
        )
    
    async def get_health_status(self, use_cache: bool = True) -> ProviderHealth:
        """Get the current health status of the provider."""
        if use_cache and self._should_cache_health():
            return self._health_cache
        
        # Calculate metrics
        success_rate = 100.0
        if self._request_count > 0:
            success_rate = ((self._request_count - self._failure_count) / self._request_count) * 100
        
        avg_response_time = 0.0
        if self._request_count > 0:
            avg_response_time = (self._total_response_time / self._request_count) * 1000  # Convert to ms
        
        health = ProviderHealth(
            status=ProviderStatus.ACTIVE,  # Mock provider is always active
            response_time_ms=avg_response_time,
            success_rate=success_rate,
            error_count=self._failure_count,
            last_error=None,
            last_check_time=datetime.now(timezone.utc),
            quota_remaining=999999,  # Unlimited quota for mock provider
            quota_reset_time=None,
        )
        
        self._cache_health(health)
        return health
    
    def estimate_cost(self, task: Task) -> CostEstimate:
        """Estimate the cost of executing a task (always $0 for mock)."""
        estimated_tokens = self._estimate_tokens_for_task(task, "")
        
        return CostEstimate(
            estimated_tokens=estimated_tokens,
            cost_per_token=0.0,
            estimated_cost_usd=0.0,
            currency="USD",
            model_used="mock-model-v1"
        )
    
    # Private methods
    
    async def _execute_task_without_delay(self, task: Task, context: Dict[str, Any] = None) -> ProviderResponse:
        """Execute task without delay (for batch processing)."""
        start_time = datetime.now(timezone.utc)
        
        self._request_count += 1
        
        # Determine if this request should fail
        should_fail = self._should_fail()
        
        if should_fail:
            self._failure_count += 1
            error_message = self._generate_error_message(task)
            
            return ProviderResponse(
                success=False,
                result=None,
                provider_id=self.provider_id,
                execution_time_ms=100,  # Minimal time for batch
                tokens_used=0,
                cost_usd=0.0,
                error_message=error_message,
                metadata={
                    "mock_provider": True,
                    "task_type": task.type,
                    "batch_execution": True,
                    "simulated_failure": True
                }
            )
        
        # Generate successful response
        result = await self._generate_response(task, context or {})
        tokens_used = self._estimate_tokens_for_task(task, result)
        
        return ProviderResponse(
            success=True,
            result=result,
            provider_id=self.provider_id,
            execution_time_ms=100,
            tokens_used=tokens_used,
            cost_usd=0.0,
            model_used="mock-model-v1",
            metadata={
                "mock_provider": True,
                "task_type": task.type,
                "batch_execution": True,
                "response_hash": self._get_response_hash(task)
            }
        )
    
    async def _get_response_delay(self) -> float:
        """Get response delay based on configuration."""
        if self.deterministic:
            # Use hash-based delay for deterministic responses
            task_hash = abs(hash(str(self._request_count))) % 1000
            delay_range = self.response_delay_max - self.response_delay_min
            return self.response_delay_min + (task_hash / 1000.0) * delay_range
        else:
            # Random delay
            return random.uniform(self.response_delay_min, self.response_delay_max)
    
    def _should_fail(self) -> bool:
        """Determine if this request should fail."""
        if self.failure_rate <= 0:
            return False
        
        if self._failure_pattern:
            # Use predefined failure pattern
            should_fail = self._request_count in self._failure_pattern
            return should_fail
        
        if self.deterministic:
            # Deterministic failure based on request count and failure rate
            return (self._request_count % int(1 / self.failure_rate)) == 0
        else:
            # Random failure
            return random.random() < self.failure_rate
    
    def _generate_error_message(self, task: Task) -> str:
        """Generate a realistic error message."""
        error_types = [
            "Simulated network timeout",
            "Mock rate limit exceeded",
            "Simulated service unavailable",
            "Mock authentication failure",
            "Simulated parsing error",
        ]
        
        if self.deterministic:
            # Use hash to select consistent error type
            error_index = abs(hash(f"{task.id}_{task.type}")) % len(error_types)
            return f"{error_types[error_index]} for task {task.id}"
        else:
            return f"{random.choice(error_types)} for task {task.id}"
    
    async def _generate_response(self, task: Task, context: Dict[str, Any]) -> str:
        """Generate a mock response for the task."""
        # Check for custom responses first
        task_key = f"{task.type}_{self._get_response_hash(task)[:8]}"
        if task_key in self.custom_responses:
            return self.custom_responses[task_key]
        
        # Generate response based on task type
        if task.type == "PR_REVIEW":
            return self._generate_pr_review_response(task)
        elif task.type == "ISSUE_SUMMARY":
            return self._generate_issue_summary_response(task)
        elif task.type == "CODE_ANALYSIS":
            return self._generate_code_analysis_response(task)
        elif task.type == "REFACTOR":
            return self._generate_refactor_response(task)
        elif task.type == "BUG_FIX":
            return self._generate_bug_fix_response(task)
        elif task.type == "FEATURE":
            return self._generate_feature_response(task)
        else:
            return self._generate_generic_response(task)
    
    def _generate_pr_review_response(self, task: Task) -> str:
        """Generate a mock PR review response."""
        response_hash = self._get_response_hash(task)[:8]
        
        return f"""## Mock Code Review Analysis

**Overall Assessment**: The code changes look good with minor suggestions for improvement.

**Potential Issues**:
- Consider adding error handling for edge cases in function `processData()`
- Variable naming could be more descriptive in some functions
- Missing null checks on lines 42-45

**Suggestions**:
1. Add comprehensive test coverage for new functionality
2. Consider performance implications of the new algorithm O(n²)
3. Update documentation to reflect API changes
4. Add input validation for user-provided data

**Security Considerations**: 
- Ensure proper sanitization of user inputs
- Review authentication flow changes

**Performance**: Changes should have minimal performance impact.

**Test Coverage**: Current coverage appears adequate but could be improved in edge cases.

*Mock response generated - Request ID: {response_hash}*
*Generated by Local Mock Provider: {self.provider_id}*"""
    
    def _generate_issue_summary_response(self, task: Task) -> str:
        """Generate a mock issue summary response."""
        response_hash = self._get_response_hash(task)[:8]
        
        return f"""## Mock Issue Analysis

**Summary**: Well-defined issue with clear reproduction steps and expected behavior.

**Root Cause**: Likely related to async operation timing or state management.

**Proposed Solution**:
1. Implement proper error boundary handling
2. Add retry logic with exponential backoff
3. Improve state synchronization

**Complexity**: Medium (estimated 2-3 days)

**Priority**: High - affects user experience

**Dependencies**: 
- Frontend state management refactor
- API endpoint modifications
- Database schema updates

**Testing Requirements**:
- Unit tests for error scenarios
- Integration tests for full user flow
- Load testing under concurrent access

*Mock response generated - Request ID: {response_hash}*
*Generated by Local Mock Provider: {self.provider_id}*"""
    
    def _generate_code_analysis_response(self, task: Task) -> str:
        """Generate a mock code analysis response."""
        response_hash = self._get_response_hash(task)[:8]
        
        return f"""## Mock Code Analysis Report

**Code Quality Score**: 7.5/10

**Issues Found**:
- **Critical**: Potential memory leak in event handler cleanup
- **Major**: Inefficient database query in loop (lines 120-135)
- **Minor**: Inconsistent naming conventions
- **Minor**: Missing JSDoc comments for public methods

**Security Concerns**:
- SQL injection vulnerability in dynamic query building
- Missing input validation for user-provided parameters

**Performance Optimizations**:
1. Implement query batching for database operations
2. Add memoization for expensive calculations
3. Use lazy loading for large datasets

**Maintainability**:
- Consider extracting utility functions
- Reduce cyclomatic complexity in main processing function
- Add error handling patterns

**Best Practices**:
- Follow established coding standards
- Add comprehensive error logging
- Implement proper separation of concerns

*Mock response generated - Request ID: {response_hash}*
*Generated by Local Mock Provider: {self.provider_id}*"""
    
    def _generate_bug_fix_response(self, task: Task) -> str:
        """Generate a mock bug fix response."""
        response_hash = self._get_response_hash(task)[:8]
        
        return f"""## Mock Bug Fix Analysis

**Root Cause**: Race condition in concurrent data access leading to inconsistent state.

**Proposed Solution**:
```python
# Add proper synchronization
import threading
from contextlib import contextmanager

@contextmanager
def data_lock():
    lock = threading.RLock()
    lock.acquire()
    try:
        yield
    finally:
        lock.release()

# Usage in problematic code
def update_shared_data(data):
    with data_lock():
        # Critical section - safe concurrent access
        shared_state.update(data)
        validate_consistency()
```

**Additional Changes Needed**:
1. Add timeout handling for lock acquisition
2. Implement deadlock detection
3. Add comprehensive logging for debugging
4. Create monitoring for lock contention

**Testing Strategy**:
- Unit tests for edge cases and error conditions
- Stress tests with high concurrency
- Integration tests with realistic load patterns
- Performance regression testing

**Rollback Plan**:
- Feature flag to enable/disable fix
- Monitoring alerts for performance degradation
- Quick revert mechanism if issues arise

*Mock response generated - Request ID: {response_hash}*
*Generated by Local Mock Provider: {self.provider_id}*"""
    
    def _generate_feature_response(self, task: Task) -> str:
        """Generate a mock feature response."""
        response_hash = self._get_response_hash(task)[:8]
        
        return f"""## Mock Feature Implementation Plan

**Architecture Approach**: Microservices pattern with event-driven communication.

**Implementation Strategy**:

### Phase 1: Foundation (Days 1-2)
1. Design API contracts and data schemas
2. Set up service infrastructure and deployment pipeline
3. Implement core business logic layer
4. Create database migrations and seed data

### Phase 2: Core Features (Days 3-5)
1. Build REST API endpoints with validation
2. Implement frontend components and user interface
3. Add real-time notifications via WebSocket
4. Integrate with existing authentication system

### Phase 3: Testing & Polish (Days 6-7)
1. Comprehensive test suite (unit, integration, E2E)
2. Performance optimization and load testing
3. Security review and penetration testing
4. Documentation and deployment guides

**Technical Stack**:
- Backend: FastAPI with async/await patterns
- Frontend: React with TypeScript
- Database: PostgreSQL with proper indexing
- Caching: Redis for session and API response caching
- Monitoring: Prometheus metrics with Grafana dashboards

**Estimated Effort**: 7-10 days for full implementation

**Risks & Mitigation**:
- **Risk**: Integration complexity with legacy systems
  **Mitigation**: Adapter pattern and gradual migration
- **Risk**: Performance under load
  **Mitigation**: Caching strategy and horizontal scaling

*Mock response generated - Request ID: {response_hash}*
*Generated by Local Mock Provider: {self.provider_id}*"""
    
    def _generate_refactor_response(self, task: Task) -> str:
        """Generate a mock refactor response."""
        response_hash = self._get_response_hash(task)[:8]
        
        return f"""## Mock Refactoring Plan

**Current Issues Analysis**:
- High cyclomatic complexity (>15 in main functions)
- Tight coupling between modules
- Inconsistent error handling patterns
- Lack of proper abstraction layers

**Refactoring Strategy**:

### 1. Extract Service Layer
```python
# Before: Tightly coupled controller logic
class UserController:
    def create_user(self, data):
        # validation, business logic, persistence all mixed
        
# After: Separated concerns
class UserService:
    def __init__(self, repository, validator):
        self.repository = repository
        self.validator = validator
    
    def create_user(self, data):
        validated_data = self.validator.validate(data)
        return self.repository.save(validated_data)
```

### 2. Implement Repository Pattern
- Abstract data access layer
- Enable easier testing with mocks
- Support multiple data sources

### 3. Add Proper Error Handling
- Consistent exception hierarchy
- Centralized error logging
- User-friendly error messages

**Benefits**:
✅ Improved testability (mocking individual components)
✅ Better maintainability (single responsibility principle)
✅ Enhanced reusability (modular design)
✅ Reduced technical debt

**Migration Plan**:
1. Create new structure alongside existing code
2. Gradually move functionality to new architecture
3. Update tests to use new interfaces
4. Remove legacy code once migration complete

*Mock response generated - Request ID: {response_hash}*
*Generated by Local Mock Provider: {self.provider_id}*"""
    
    def _generate_generic_response(self, task: Task) -> str:
        """Generate a generic mock response."""
        response_hash = self._get_response_hash(task)[:8]
        
        return f"""## Mock Task Analysis

**Task Type**: {task.type}
**Priority**: {task.priority}

**Analysis Results**:
I've successfully analyzed your request and generated the following recommendations:

**Key Findings**:
1. Implementation approach looks technically sound
2. Consider adding proper error handling and validation
3. Test coverage should be comprehensive
4. Documentation needs to be updated

**Recommendations**:
- Follow established patterns and conventions
- Add monitoring and logging for production deployment
- Consider performance implications under load
- Implement proper security measures

**Next Steps**:
1. Review and validate the proposed approach
2. Create detailed technical specifications
3. Implement with appropriate test coverage
4. Deploy to staging environment for validation

**Estimated Effort**: 2-4 days depending on complexity

*Mock response generated - Request ID: {response_hash}*
*Generated by Local Mock Provider: {self.provider_id}*"""
    
    def _get_response_hash(self, task: Task) -> str:
        """Generate a deterministic hash for the task."""
        task_data = f"{task.type}_{task.payload}_{task.priority}"
        return hashlib.md5(task_data.encode()).hexdigest()
    
    def _estimate_tokens_for_task(self, task: Task, response: str) -> int:
        """Estimate token count for a task and response."""
        prompt_length = len(str(task.payload))
        response_length = len(response)
        
        # Rough approximation: 1 token per 4 characters
        return max((prompt_length + response_length) // 4, 50)
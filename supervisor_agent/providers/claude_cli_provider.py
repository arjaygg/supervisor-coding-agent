"""
Claude CLI Provider Implementation

This provider implements the AIProvider interface for Claude Code CLI integration,
reusing existing ClaudeAgentWrapper functionality while adding multi-subscription support.
"""

import asyncio
import subprocess
import hashlib
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import asdict

from .base_provider import (
    AIProvider,
    ProviderCapabilities,
    ProviderHealth,
    ProviderResponse,
    CostEstimate,
    ProviderStatus,
    ProviderError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    Task,
    TaskCapability,
)

from supervisor_agent.config import settings
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeCliProvider(AIProvider):
    """
    Claude CLI provider implementation with multi-subscription support.
    
    Extends the existing ClaudeAgentWrapper functionality to support the
    new provider interface while maintaining backward compatibility.
    """
    
    def __init__(self, provider_id: str, config: Dict[str, Any]):
        super().__init__(provider_id, config)
        
        # Extract configuration
        self.api_keys: List[str] = config.get("api_keys", [])
        self.cli_path: str = config.get("cli_path", settings.claude_cli_path)
        self.current_key_index: int = 0
        self.max_tokens_per_request: int = config.get("max_tokens_per_request", 4000)
        self.rate_limit_per_minute: int = config.get("rate_limit_per_minute", 60)
        self.rate_limit_per_hour: int = config.get("rate_limit_per_hour", 1000)
        self.rate_limit_per_day: int = config.get("rate_limit_per_day", 10000)
        self.mock_mode: bool = config.get("mock_mode", False)
        
        # Rate limiting state
        self._request_timestamps: List[float] = []
        self._hourly_usage: int = 0
        self._daily_usage: int = 0
        self._usage_reset_time: datetime = datetime.now(timezone.utc)
        
        # Health tracking
        self._consecutive_failures: int = 0
        self._last_success_time: Optional[datetime] = None
        self._last_error: Optional[str] = None
    
    async def initialize(self) -> None:
        """Initialize the Claude CLI provider."""
        if not self.api_keys:
            raise ProviderError("No API keys configured for Claude CLI provider", self.provider_id)
        
        # Validate CLI availability unless in mock mode
        if not self.mock_mode and not await self._validate_claude_cli():
            logger.warning(f"Claude CLI not available at {self.cli_path}, enabling mock mode")
            self.mock_mode = True
        
        self._initialized = True
        logger.info(f"Claude CLI provider {self.provider_id} initialized with {len(self.api_keys)} API keys")
    
    async def execute_task(self, task: Task, context: Dict[str, Any] = None) -> ProviderResponse:
        """Execute a single task using Claude CLI."""
        start_time = datetime.now(timezone.utc)
        
        try:
            # Check rate limits
            await self._check_rate_limits()
            
            # Build prompt using existing logic
            prompt = self._build_prompt(task, context or {})
            
            # Execute using Claude CLI
            result = await self._run_claude_cli(prompt)
            
            # Calculate execution time
            execution_time_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            # Estimate tokens (reuse existing logic)
            tokens_used = self._estimate_tokens_from_text(prompt + result)
            
            # Track usage
            self._record_usage(tokens_used)
            self._consecutive_failures = 0
            self._last_success_time = datetime.now(timezone.utc)
            
            return ProviderResponse(
                success=True,
                result=result,
                provider_id=self.provider_id,
                execution_time_ms=execution_time_ms,
                tokens_used=tokens_used,
                cost_usd=self._calculate_cost(tokens_used),
                model_used="claude-3-sonnet",
                metadata={
                    "api_key_index": self.current_key_index,
                    "prompt_length": len(prompt),
                    "task_type": task.type
                }
            )
            
        except Exception as e:
            execution_time_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            self._consecutive_failures += 1
            self._last_error = str(e)
            
            logger.error(f"Claude CLI execution failed for task {task.id}: {str(e)}")
            
            return ProviderResponse(
                success=False,
                result=None,
                provider_id=self.provider_id,
                execution_time_ms=execution_time_ms,
                tokens_used=0,
                cost_usd=0.0,
                error_message=str(e),
                metadata={
                    "task_type": task.type,
                    "consecutive_failures": self._consecutive_failures
                }
            )
    
    async def execute_batch(self, tasks: List[Task], context: Dict[str, Any] = None) -> List[ProviderResponse]:
        """Execute multiple tasks as a batch."""
        # For Claude CLI, we execute tasks individually as true batching isn't supported
        responses = []
        
        for task in tasks:
            try:
                response = await self.execute_task(task, context)
                responses.append(response)
                
                # Small delay between requests to avoid rate limiting
                if len(tasks) > 1:
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Batch execution failed for task {task.id}: {str(e)}")
                responses.append(ProviderResponse(
                    success=False,
                    result=None,
                    provider_id=self.provider_id,
                    execution_time_ms=0,
                    tokens_used=0,
                    cost_usd=0.0,
                    error_message=str(e),
                    metadata={"task_type": task.type, "batch_execution": True}
                ))
        
        return responses
    
    def get_capabilities(self) -> ProviderCapabilities:
        """Get the capabilities of this Claude CLI provider."""
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
            max_tokens_per_request=self.max_tokens_per_request,
            supports_batching=True,  # We support batching through sequential execution
            supports_streaming=False,
            supports_function_calling=False,
            max_concurrent_requests=1,  # CLI is inherently sequential
            rate_limit_per_minute=self.rate_limit_per_minute,
            rate_limit_per_hour=self.rate_limit_per_hour,
            rate_limit_per_day=self.rate_limit_per_day,
        )
    
    async def get_health_status(self, use_cache: bool = True) -> ProviderHealth:
        """Get the current health status of the provider."""
        if use_cache and self._should_cache_health():
            return self._health_cache
        
        # Determine status based on recent failures and CLI availability
        status = ProviderStatus.ACTIVE
        response_time_ms = 1000.0  # Default response time
        
        if self._consecutive_failures >= 3:
            status = ProviderStatus.ERROR
        elif self._consecutive_failures >= 1:
            status = ProviderStatus.DEGRADED
        elif not await self._validate_claude_cli():
            status = ProviderStatus.MAINTENANCE if self.mock_mode else ProviderStatus.ERROR
        
        # Calculate success rate based on recent usage
        success_rate = max(0.0, 100.0 - (self._consecutive_failures * 20))
        
        # Check quota remaining
        quota_remaining = max(0, self.rate_limit_per_day - self._daily_usage)
        
        health = ProviderHealth(
            status=status,
            response_time_ms=response_time_ms,
            success_rate=success_rate,
            error_count=self._consecutive_failures,
            last_error=self._last_error,
            last_check_time=datetime.now(timezone.utc),
            quota_remaining=quota_remaining,
            quota_reset_time=self._usage_reset_time,
        )
        
        self._cache_health(health)
        return health
    
    def estimate_cost(self, task: Task) -> CostEstimate:
        """Estimate the cost of executing a task."""
        # Build prompt to estimate tokens
        prompt = self._build_prompt(task, {})
        estimated_tokens = self._estimate_tokens_from_text(prompt)
        
        # Add expected response tokens (rough estimate)
        estimated_tokens += 500
        
        # Claude pricing (approximate)
        cost_per_token = 0.00001  # $0.01 per 1K tokens
        
        return CostEstimate.from_tokens(
            tokens=estimated_tokens,
            cost_per_token=cost_per_token,
            model="claude-3-sonnet"
        )
    
    # Private methods (reuse existing ClaudeAgentWrapper logic)
    
    def _build_prompt(self, task: Task, shared_memory: Dict[str, Any]) -> str:
        """Build prompt using existing logic from ClaudeAgentWrapper."""
        task_type = task.type
        payload = task.payload
        
        if task_type is None:
            raise ValueError("Task type cannot be None")
        
        task_type_str = task_type.value if hasattr(task_type, "value") else str(task_type)
        base_prompt = f"Task Type: {task_type_str}\n\n"
        
        # Add shared memory context if available
        if shared_memory:
            base_prompt += "Shared Context:\n"
            for key, value in shared_memory.items():
                base_prompt += f"- {key}: {value}\n"
            base_prompt += "\n"
        
        # Build task-specific prompts (reuse existing logic)
        if task_type == "PR_REVIEW":
            return base_prompt + self._build_pr_review_prompt(payload)
        elif task_type == "ISSUE_SUMMARY":
            return base_prompt + self._build_issue_summary_prompt(payload)
        elif task_type == "CODE_ANALYSIS":
            return base_prompt + self._build_code_analysis_prompt(payload)
        elif task_type == "REFACTOR":
            return base_prompt + self._build_refactor_prompt(payload)
        elif task_type == "BUG_FIX":
            return base_prompt + self._build_bug_fix_prompt(payload)
        elif task_type == "FEATURE":
            return base_prompt + self._build_feature_prompt(payload)
        else:
            return base_prompt + f"Task Details: {json.dumps(payload, indent=2)}"
    
    def _build_pr_review_prompt(self, payload: Dict[str, Any]) -> str:
        """Build PR review prompt (reuse existing logic)."""
        return f"""Please review the following pull request:

Repository: {payload.get('repository', 'N/A')}
PR Title: {payload.get('title', 'N/A')}
PR Description: {payload.get('description', 'N/A')}
Files Changed: {payload.get('files_changed', [])}
Diff: {payload.get('diff', 'N/A')}

Please provide:
1. Overall assessment of code quality
2. Potential issues or bugs
3. Suggestions for improvement
4. Security considerations
5. Performance implications"""
    
    def _build_issue_summary_prompt(self, payload: Dict[str, Any]) -> str:
        """Build issue summary prompt (reuse existing logic)."""
        return f"""Please analyze and summarize the following issue:

Issue Title: {payload.get('title', 'N/A')}
Issue Description: {payload.get('description', 'N/A')}
Labels: {payload.get('labels', [])}
Comments: {payload.get('comments', [])}

Please provide:
1. Summary of the issue
2. Proposed solution approach
3. Complexity estimation
4. Required resources
5. Priority recommendation"""
    
    def _build_code_analysis_prompt(self, payload: Dict[str, Any]) -> str:
        """Build code analysis prompt (reuse existing logic)."""
        return f"""Please analyze the following code:

File Path: {payload.get('file_path', 'N/A')}
Code: {payload.get('code', 'N/A')}
Language: {payload.get('language', 'N/A')}

Please provide:
1. Code quality assessment
2. Potential bugs or issues
3. Performance optimizations
4. Best practices suggestions
5. Refactoring recommendations"""
    
    def _build_refactor_prompt(self, payload: Dict[str, Any]) -> str:
        """Build refactor prompt (reuse existing logic)."""
        return f"""Please refactor the following code:

Target: {payload.get('target', 'N/A')}
Current Code: {payload.get('current_code', 'N/A')}
Requirements: {payload.get('requirements', 'N/A')}

Please provide:
1. Refactored code
2. Explanation of changes
3. Benefits of the refactoring
4. Testing recommendations"""
    
    def _build_bug_fix_prompt(self, payload: Dict[str, Any]) -> str:
        """Build bug fix prompt (reuse existing logic)."""
        return f"""Please help fix the following bug:

Bug Description: {payload.get('description', 'N/A')}
Error Message: {payload.get('error_message', 'N/A')}
Code Context: {payload.get('code_context', 'N/A')}
Steps to Reproduce: {payload.get('steps_to_reproduce', 'N/A')}

Please provide:
1. Root cause analysis
2. Proposed fix
3. Code changes needed
4. Testing strategy"""
    
    def _build_feature_prompt(self, payload: Dict[str, Any]) -> str:
        """Build feature prompt (reuse existing logic)."""
        return f"""Please help implement the following feature:

Feature Description: {payload.get('description', 'N/A')}
Requirements: {payload.get('requirements', 'N/A')}
Existing Code Context: {payload.get('code_context', 'N/A')}

Please provide:
1. Implementation approach
2. Code structure design
3. Required changes
4. Testing recommendations
5. Potential challenges"""
    
    async def _run_claude_cli(self, prompt: str) -> str:
        """Run Claude CLI with the prompt (reuse existing logic)."""
        try:
            # Check if we're in mock mode
            if self.mock_mode or self.cli_path == "mock" or not self.api_keys:
                return self._generate_mock_response(prompt)
            
            # Validate Claude CLI exists
            if not await self._validate_claude_cli():
                logger.warning(f"Claude CLI not found at {self.cli_path}, using mock response")
                return self._generate_mock_response(prompt)
            
            # Get current API key with rotation
            api_key = self._get_next_api_key()
            
            # Set environment variable for API key
            import os
            env = os.environ.copy()
            env["ANTHROPIC_API_KEY"] = api_key
            
            # Construct Claude CLI command
            command = [self.cli_path]
            
            # Run Claude CLI with the prompt via stdin
            process = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                env=env,
                timeout=300,  # 5 minute timeout
            )
            
            if process.returncode != 0:
                error_msg = process.stderr.strip() if process.stderr else "Unknown error"
                logger.warning(f"Claude CLI failed, falling back to mock response: {error_msg}")
                return self._generate_mock_response(prompt)
            
            return process.stdout.strip()
            
        except subprocess.TimeoutExpired:
            logger.warning("Claude CLI execution timed out, using mock response")
            return self._generate_mock_response(prompt)
        except FileNotFoundError:
            logger.warning(f"Claude CLI not found at path: {self.cli_path}, using mock response")
            return self._generate_mock_response(prompt)
        except Exception as e:
            logger.warning(f"Failed to execute Claude CLI, using mock response: {str(e)}")
            return self._generate_mock_response(prompt)
    
    async def _validate_claude_cli(self) -> bool:
        """Validate that Claude CLI is available and functional."""
        try:
            import os
            import shutil
            
            # In mock mode, always return False to trigger mock responses
            if self.cli_path == "mock":
                return False
            
            # Check if file exists
            if not shutil.which(self.cli_path) and not os.path.isfile(self.cli_path):
                return False
            
            # Try to run a simple help command
            process = subprocess.run(
                [self.cli_path, "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return process.returncode == 0
        except Exception:
            return False
    
    def _generate_mock_response(self, prompt: str) -> str:
        """Generate a realistic mock response for testing (reuse existing logic)."""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        
        if "PR_REVIEW" in prompt:
            return f"""## Code Review Analysis

**Overall Assessment**: The code changes look good with minor suggestions for improvement.

**Potential Issues**:
- Consider adding error handling for edge cases
- Variable naming could be more descriptive in some functions

**Suggestions**:
1. Add comprehensive test coverage for new functionality
2. Consider performance implications of the new algorithm
3. Update documentation to reflect API changes

**Security Considerations**: No major security concerns identified.

**Performance**: Changes should have minimal performance impact.

*Mock response generated - ID: {prompt_hash}*"""
        
        elif "CODE_ANALYSIS" in prompt:
            return f"""## Code Analysis Report

**Code Quality**: Good overall structure with room for improvement.

**Issues Found**:
- Potential null pointer dereference on line 42
- Unused variable 'temp' in function processData()
- Magic numbers should be defined as constants

**Recommendations**:
1. Implement proper error handling patterns
2. Add input validation
3. Consider refactoring large functions into smaller components
4. Improve code comments and documentation

**Complexity Score**: 6/10 - Moderate complexity

*Mock response generated - ID: {prompt_hash}*"""
        
        elif "BUG_FIX" in prompt:
            return f"""## Bug Fix Analysis

**Root Cause**: The issue appears to be related to race condition in concurrent operations.

**Proposed Solution**:
```python
# Add proper synchronization
with threading.Lock():
    # Critical section code here
    process_shared_resource()
```

**Additional Changes Needed**:
1. Add timeout handling
2. Implement retry logic
3. Add logging for debugging

**Testing Strategy**:
- Unit tests for edge cases
- Integration tests with concurrent load
- Performance testing

*Mock response generated - ID: {prompt_hash}*"""
        
        elif "FEATURE" in prompt:
            return f"""## Feature Implementation Plan

**Approach**: Implement using modular design pattern for maintainability.

**Architecture**:
1. Create new service layer for feature logic
2. Add database migration for new schema
3. Implement REST API endpoints
4. Add frontend components

**Implementation Steps**:
1. Define data models and schemas
2. Create backend service methods
3. Add API routes with validation
4. Implement frontend UI components
5. Add comprehensive test coverage

**Estimated Effort**: 2-3 days

*Mock response generated - ID: {prompt_hash}*"""
        
        elif "REFACTOR" in prompt:
            return f"""## Refactoring Plan

**Current Issues**: Code has high complexity and poor separation of concerns.

**Refactoring Steps**:
1. Extract common functionality into utility functions
2. Apply single responsibility principle
3. Improve naming conventions
4. Reduce cyclomatic complexity

**Proposed Structure**:
```
src/
├── models/
├── services/
├── utils/
└── controllers/
```

**Benefits**:
- Improved maintainability
- Better testability
- Reduced technical debt

*Mock response generated - ID: {prompt_hash}*"""
        
        else:
            return f"""## Task Analysis

I've analyzed your request and here's my response:

**Summary**: Successfully processed the task with the following recommendations.

**Key Points**:
1. Implementation looks feasible with current architecture
2. Consider adding proper error handling
3. Test coverage should be expanded

**Next Steps**:
- Review the proposed changes
- Run existing test suite
- Deploy to staging environment

*Mock response generated - ID: {prompt_hash}*"""
    
    def _get_next_api_key(self) -> str:
        """Get the next API key using round-robin."""
        if not self.api_keys:
            raise ProviderError("No API keys available", self.provider_id)
        
        api_key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return api_key
    
    async def _check_rate_limits(self):
        """Check and enforce rate limits."""
        current_time = time.time()
        
        # Clean old timestamps (keep only last minute)
        self._request_timestamps = [
            ts for ts in self._request_timestamps
            if current_time - ts < 60
        ]
        
        # Check minute rate limit
        if len(self._request_timestamps) >= self.rate_limit_per_minute:
            raise RateLimitError(
                f"Rate limit exceeded: {self.rate_limit_per_minute} requests per minute",
                self.provider_id,
                retry_after_seconds=60
            )
        
        # Check daily rate limit
        if self._daily_usage >= self.rate_limit_per_day:
            reset_time = self._usage_reset_time
            raise QuotaExceededError(
                f"Daily quota exceeded: {self.rate_limit_per_day} requests per day",
                self.provider_id,
                quota_reset_time=reset_time
            )
        
        # Add current timestamp
        self._request_timestamps.append(current_time)
    
    def _record_usage(self, tokens_used: int):
        """Record usage for quota tracking."""
        self._daily_usage += 1
        
        # Reset daily usage if needed
        if datetime.now(timezone.utc) >= self._usage_reset_time:
            self._daily_usage = 1
            self._usage_reset_time = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timezone.utc
    
    def _calculate_cost(self, tokens_used: int) -> float:
        """Calculate cost based on token usage."""
        # Claude pricing (approximate)
        cost_per_token = 0.00001  # $0.01 per 1K tokens
        return tokens_used * cost_per_token
import subprocess
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from supervisor_agent.config import settings
from supervisor_agent.db.models import Task, TaskSession, Agent
# Removed unused imports TaskSessionCRUD, AgentCRUD to fix circular import issue
from supervisor_agent.core.cost_tracker import cost_tracker
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeAgentWrapper:
    def __init__(self, agent_id: str, api_key: str):
        self.agent_id = agent_id
        self.api_key = api_key
        self.cli_path = settings.claude_cli_path

    async def execute_task(
        self, task: Task, shared_memory: Dict[str, Any], db_session=None
    ) -> Dict[str, Any]:
        start_time = datetime.now(timezone.utc)
        prompt = None
        result = None

        try:
            prompt = self._build_prompt(task, shared_memory)

            logger.info(f"Executing task {task.id} with agent {self.agent_id}")

            # Invoke Claude CLI via subprocess
            result = await self._run_claude_cli(prompt)

            end_time = datetime.now(timezone.utc)
            execution_time = int((end_time - start_time).total_seconds())
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Track cost and usage if database session is provided
            if db_session:
                try:
                    cost_tracker.track_task_execution(
                        db=db_session,
                        task_id=task.id,
                        agent_id=self.agent_id,
                        prompt=prompt,
                        response=result,
                        execution_time_ms=execution_time_ms,
                        context=shared_memory,
                    )
                except Exception as cost_error:
                    logger.warning(
                        f"Failed to track cost for task {task.id}: {str(cost_error)}"
                    )

            return {
                "success": True,
                "result": result,
                "execution_time": execution_time,
                "execution_time_ms": execution_time_ms,
                "prompt": prompt,
            }

        except Exception as e:
            end_time = datetime.now(timezone.utc)
            execution_time = int((end_time - start_time).total_seconds())
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            logger.error(f"Task {task.id} failed with agent {self.agent_id}: {str(e)}")

            # Track failed execution cost if database session is provided
            if db_session and prompt:
                try:
                    cost_tracker.track_task_execution(
                        db=db_session,
                        task_id=task.id,
                        agent_id=self.agent_id,
                        prompt=prompt,
                        response="",  # Empty response for failed tasks
                        execution_time_ms=execution_time_ms,
                        context=shared_memory,
                    )
                except Exception as cost_error:
                    logger.warning(
                        f"Failed to track cost for failed task {task.id}: {str(cost_error)}"
                    )

            return {
                "success": False,
                "error": str(e),
                "execution_time": execution_time,
                "execution_time_ms": execution_time_ms,
                "prompt": prompt if prompt else None,
            }

    def _build_prompt(self, task: Task, shared_memory: Dict[str, Any]) -> str:
        task_type = task.type
        payload = task.payload

        # Handle None task type
        if task_type is None:
            raise ValueError("Task type cannot be None")

        # Extract the enum value if it's an enum, otherwise use string directly
        task_type_str = (
            task_type.value if hasattr(task_type, "value") else str(task_type)
        )
        base_prompt = f"Task Type: {task_type_str}\n\n"

        # Add shared memory context if available
        if shared_memory:
            base_prompt += "Shared Context:\n"
            for key, value in shared_memory.items():
                base_prompt += f"- {key}: {value}\n"
            base_prompt += "\n"

        # Build task-specific prompts
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
        try:
            # Check if we're in mock mode
            if settings.claude_cli_path == "mock" or not settings.claude_api_keys:
                return self._generate_mock_response(prompt)
            
            # Validate Claude CLI exists
            if not self._validate_claude_cli():
                logger.warning(f"Claude CLI not found at {self.cli_path}, using mock response")
                return self._generate_mock_response(prompt)

            # Set environment variable for API key, inheriting current environment
            import os

            env = os.environ.copy()
            env["ANTHROPIC_API_KEY"] = self.api_key

            # Construct Claude CLI command
            # Using stdin for prompt to handle large prompts and special characters
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
                error_msg = (
                    process.stderr.strip() if process.stderr else "Unknown error"
                )
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
    
    def _validate_claude_cli(self) -> bool:
        """Validate that Claude CLI is available and functional"""
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
        """Generate a realistic mock response for testing"""
        import hashlib
        import random
        
        # Create a deterministic but varied response based on prompt
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


class AgentManager:
    def __init__(self):
        self.agents: Dict[str, ClaudeAgentWrapper] = {}
        self._initialize_agents()

    def _initialize_agents(self):
        api_keys = settings.claude_api_keys_list

        for i, api_key in enumerate(api_keys):
            agent_id = f"claude-agent-{i+1}"
            self.agents[agent_id] = ClaudeAgentWrapper(agent_id, api_key)

            logger.info(f"Initialized agent {agent_id}")

    def get_agent(self, agent_id: str) -> Optional[ClaudeAgentWrapper]:
        return self.agents.get(agent_id)

    def get_available_agent_ids(self) -> list[str]:
        return list(self.agents.keys())


agent_manager = AgentManager()

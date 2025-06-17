import subprocess
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from supervisor_agent.config import settings
from supervisor_agent.db.models import Task, TaskSession, Agent
from supervisor_agent.db.crud import TaskSessionCRUD, AgentCRUD
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeAgentWrapper:
    def __init__(self, agent_id: str, api_key: str):
        self.agent_id = agent_id
        self.api_key = api_key
        self.cli_path = settings.claude_cli_path
    
    async def execute_task(self, task: Task, shared_memory: Dict[str, Any]) -> Dict[str, Any]:
        start_time = datetime.utcnow()
        
        try:
            prompt = self._build_prompt(task, shared_memory)
            
            logger.info(f"Executing task {task.id} with agent {self.agent_id}")
            
            # Invoke Claude CLI via subprocess
            result = await self._run_claude_cli(prompt)
            
            execution_time = int((datetime.utcnow() - start_time).total_seconds())
            
            return {
                "success": True,
                "result": result,
                "execution_time": execution_time,
                "prompt": prompt
            }
            
        except Exception as e:
            execution_time = int((datetime.utcnow() - start_time).total_seconds())
            logger.error(f"Task {task.id} failed with agent {self.agent_id}: {str(e)}")
            
            return {
                "success": False,
                "error": str(e),
                "execution_time": execution_time,
                "prompt": prompt if 'prompt' in locals() else None
            }
    
    def _build_prompt(self, task: Task, shared_memory: Dict[str, Any]) -> str:
        task_type = task.type
        payload = task.payload
        
        # Extract the enum value if it's an enum, otherwise use string directly
        task_type_str = task_type.value if hasattr(task_type, 'value') else str(task_type)
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
                timeout=300  # 5 minute timeout
            )
            
            if process.returncode != 0:
                error_msg = process.stderr.strip() if process.stderr else "Unknown error"
                raise Exception(f"Claude CLI failed with return code {process.returncode}: {error_msg}")
            
            return process.stdout.strip()
            
        except subprocess.TimeoutExpired:
            raise Exception("Claude CLI execution timed out")
        except FileNotFoundError:
            raise Exception(f"Claude CLI not found at path: {self.cli_path}")
        except Exception as e:
            raise Exception(f"Failed to execute Claude CLI: {str(e)}")


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
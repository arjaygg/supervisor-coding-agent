"""
Prompt building utilities for different task types.
Separates prompt construction logic from task execution.
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple


@dataclass
class PromptTemplate:
    """Template for building task-specific prompts."""
    header: str
    fields: List[Tuple[str, str]]  # (field_name, display_name)
    sections: List[str]


class PromptStrategy(ABC):
    """Abstract base class for prompt building strategies."""
    
    @abstractmethod
    def build_prompt(self, payload: Dict[str, Any]) -> str:
        pass


class TemplatePromptStrategy(PromptStrategy):
    """Template-based prompt building strategy."""
    
    def __init__(self, template: PromptTemplate):
        self.template = template
    
    def build_prompt(self, payload: Dict[str, Any]) -> str:
        lines = [self.template.header, ""]
        
        # Render fields
        for field_name, display_name in self.template.fields:
            value = payload.get(field_name, 'N/A')
            lines.append(f"{display_name}: {value}")
        
        lines.extend(["", "Please provide:"])
        
        # Render sections
        for i, section in enumerate(self.template.sections, 1):
            lines.append(f"{i}. {section}")
            
        return "\n".join(lines)


class GenericPromptStrategy(PromptStrategy):
    """Generic fallback strategy for unknown task types."""
    
    def build_prompt(self, payload: Dict[str, Any]) -> str:
        return f"Task Details: {json.dumps(payload, indent=2)}"


class PromptBuilder:
    """Main prompt builder using strategy pattern."""
    
    TEMPLATES = {
        "PR_REVIEW": PromptTemplate(
            header="Please review the following pull request:",
            fields=[
                ("repository", "Repository"),
                ("title", "PR Title"),
                ("description", "PR Description"),
                ("files_changed", "Files Changed"),
                ("diff", "Diff")
            ],
            sections=[
                "Overall assessment of code quality",
                "Potential issues or bugs",
                "Suggestions for improvement",
                "Security considerations",
                "Performance implications"
            ]
        ),
        "ISSUE_SUMMARY": PromptTemplate(
            header="Please analyze and summarize the following issue:",
            fields=[
                ("title", "Issue Title"),
                ("description", "Issue Description"),
                ("labels", "Labels"),
                ("comments", "Comments")
            ],
            sections=[
                "Summary of the issue",
                "Proposed solution approach",
                "Complexity estimation",
                "Required resources",
                "Priority recommendation"
            ]
        ),
        "CODE_ANALYSIS": PromptTemplate(
            header="Please analyze the following code:",
            fields=[
                ("file_path", "File Path"),
                ("code", "Code"),
                ("language", "Language")
            ],
            sections=[
                "Code quality assessment",
                "Potential bugs or issues",
                "Performance optimizations",
                "Best practices suggestions",
                "Refactoring recommendations"
            ]
        ),
        "REFACTOR": PromptTemplate(
            header="Please refactor the following code:",
            fields=[
                ("target", "Target"),
                ("current_code", "Current Code"),
                ("requirements", "Requirements")
            ],
            sections=[
                "Refactored code",
                "Explanation of changes",
                "Benefits of the refactoring",
                "Testing recommendations"
            ]
        ),
        "BUG_FIX": PromptTemplate(
            header="Please help fix the following bug:",
            fields=[
                ("description", "Bug Description"),
                ("error_message", "Error Message"),
                ("code_context", "Code Context"),
                ("steps_to_reproduce", "Steps to Reproduce")
            ],
            sections=[
                "Root cause analysis",
                "Proposed fix",
                "Code changes needed",
                "Testing strategy"
            ]
        ),
        "FEATURE": PromptTemplate(
            header="Please help implement the following feature:",
            fields=[
                ("description", "Feature Description"),
                ("requirements", "Requirements"),
                ("code_context", "Existing Code Context")
            ],
            sections=[
                "Implementation approach",
                "Code structure design",
                "Required changes",
                "Testing recommendations",
                "Potential challenges"
            ]
        )
    }
    
    def __init__(self):
        self._strategies = {}
        self._generic_strategy = GenericPromptStrategy()
        self._initialize_strategies()
    
    def _initialize_strategies(self):
        """Initialize template-based strategies."""
        for task_type, template in self.TEMPLATES.items():
            self._strategies[task_type] = TemplatePromptStrategy(template)
    
    def build_prompt(self, task_type: str, payload: Dict[str, Any], 
                    shared_memory: Dict[str, Any] = None) -> str:
        """Build a prompt for the given task type and payload."""
        # Build base prompt with task type
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
        
        # Get strategy for task type
        strategy = self._strategies.get(task_type, self._generic_strategy)
        
        # Build task-specific prompt
        task_prompt = strategy.build_prompt(payload)
        
        return base_prompt + task_prompt
    
    def register_strategy(self, task_type: str, strategy: PromptStrategy):
        """Register a custom strategy for a task type."""
        self._strategies[task_type] = strategy
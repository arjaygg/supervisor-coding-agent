"""
Mock response generator for testing and fallback scenarios.
Separates mock response logic from task execution.
"""
import hashlib
from typing import Dict, Any


class MockResponseGenerator:
    """Generates realistic mock responses for different task types."""
    
    RESPONSE_TEMPLATES = {
        "PR_REVIEW": {
            "title": "Code Review Analysis",
            "assessment": "The code changes look good with minor suggestions for improvement.",
            "issues": [
                "Consider adding error handling for edge cases",
                "Variable naming could be more descriptive in some functions"
            ],
            "suggestions": [
                "Add comprehensive test coverage for new functionality",
                "Consider performance implications of the new algorithm",
                "Update documentation to reflect API changes"
            ],
            "security": "No major security concerns identified.",
            "performance": "Changes should have minimal performance impact."
        },
        "CODE_ANALYSIS": {
            "title": "Code Analysis Report",
            "quality": "Good overall structure with room for improvement.",
            "issues": [
                "Potential null pointer dereference on line 42",
                "Unused variable 'temp' in function processData()",
                "Magic numbers should be defined as constants"
            ],
            "recommendations": [
                "Implement proper error handling patterns",
                "Add input validation",
                "Consider refactoring large functions into smaller components",
                "Improve code comments and documentation"
            ],
            "complexity": "6/10 - Moderate complexity"
        },
        "BUG_FIX": {
            "title": "Bug Fix Analysis",
            "root_cause": "The issue appears to be related to race condition in concurrent operations.",
            "solution": """# Add proper synchronization
with threading.Lock():
    # Critical section code here
    process_shared_resource()""",
            "changes": [
                "Add timeout handling",
                "Implement retry logic",
                "Add logging for debugging"
            ],
            "testing": [
                "Unit tests for edge cases",
                "Integration tests with concurrent load",
                "Performance testing"
            ]
        },
        "FEATURE": {
            "title": "Feature Implementation Plan",
            "approach": "Implement using modular design pattern for maintainability.",
            "architecture": [
                "Create new service layer for feature logic",
                "Add database migration for new schema",
                "Implement REST API endpoints",
                "Add frontend components"
            ],
            "steps": [
                "Define data models and schemas",
                "Create backend service methods",
                "Add API routes with validation",
                "Implement frontend UI components",
                "Add comprehensive test coverage"
            ],
            "effort": "2-3 days"
        },
        "REFACTOR": {
            "title": "Refactoring Plan",
            "issues": "Code has high complexity and poor separation of concerns.",
            "steps": [
                "Extract common functionality into utility functions",
                "Apply single responsibility principle",
                "Improve naming conventions",
                "Reduce cyclomatic complexity"
            ],
            "structure": """src/
├── models/
├── services/
├── utils/
└── controllers/""",
            "benefits": [
                "Improved maintainability",
                "Better testability",
                "Reduced technical debt"
            ]
        },
        "ISSUE_SUMMARY": {
            "title": "Issue Analysis",
            "summary": "This issue requires implementing a new feature with moderate complexity.",
            "approach": "Break down into smaller tasks and implement incrementally.",
            "complexity": "Medium - estimated 3-5 days",
            "resources": "1 developer, QA testing required",
            "priority": "Medium - should be completed in next sprint"
        }
    }
    
    def generate_response(self, prompt: str) -> str:
        """Generate a mock response based on the prompt content."""
        prompt_hash = self._generate_hash(prompt)
        task_type = self._detect_task_type(prompt)
        
        template = self.RESPONSE_TEMPLATES.get(task_type)
        if template:
            return self._render_response_template(template, prompt_hash)
        else:
            return self._generate_generic_response(prompt_hash)
    
    def _generate_hash(self, prompt: str) -> str:
        """Generate a deterministic hash for the prompt."""
        return hashlib.md5(prompt.encode()).hexdigest()[:8]
    
    def _detect_task_type(self, prompt: str) -> str:
        """Detect task type from prompt content."""
        prompt_upper = prompt.upper()
        
        if "PR_REVIEW" in prompt_upper:
            return "PR_REVIEW"
        elif "CODE_ANALYSIS" in prompt_upper:
            return "CODE_ANALYSIS"
        elif "BUG_FIX" in prompt_upper:
            return "BUG_FIX"
        elif "FEATURE" in prompt_upper:
            return "FEATURE"
        elif "REFACTOR" in prompt_upper:
            return "REFACTOR"
        elif "ISSUE_SUMMARY" in prompt_upper:
            return "ISSUE_SUMMARY"
        else:
            return "GENERIC"
    
    def _render_response_template(self, template: Dict[str, Any], prompt_hash: str) -> str:
        """Render a response template into formatted text."""
        lines = [f"## {template['title']}", ""]
        
        if "assessment" in template:
            lines.extend([f"**Overall Assessment**: {template['assessment']}", ""])
        
        if "quality" in template:
            lines.extend([f"**Code Quality**: {template['quality']}", ""])
        
        if "root_cause" in template:
            lines.extend([f"**Root Cause**: {template['root_cause']}", ""])
        
        if "approach" in template:
            lines.extend([f"**Approach**: {template['approach']}", ""])
        
        if "summary" in template:
            lines.extend([f"**Summary**: {template['summary']}", ""])
        
        if "issues" in template:
            lines.extend(["**Potential Issues**:"])
            for issue in template["issues"]:
                lines.append(f"- {issue}")
            lines.append("")
        
        if "suggestions" in template:
            lines.extend(["**Suggestions**:"])
            for i, suggestion in enumerate(template["suggestions"], 1):
                lines.append(f"{i}. {suggestion}")
            lines.append("")
        
        if "recommendations" in template:
            lines.extend(["**Recommendations**:"])
            for i, rec in enumerate(template["recommendations"], 1):
                lines.append(f"{i}. {rec}")
            lines.append("")
        
        if "solution" in template:
            lines.extend(["**Proposed Solution**:", "```python", template["solution"], "```", ""])
        
        if "changes" in template:
            lines.extend(["**Additional Changes Needed**:"])
            for i, change in enumerate(template["changes"], 1):
                lines.append(f"{i}. {change}")
            lines.append("")
        
        if "steps" in template:
            lines.extend(["**Implementation Steps**:"])
            for i, step in enumerate(template["steps"], 1):
                lines.append(f"{i}. {step}")
            lines.append("")
        
        if "architecture" in template:
            lines.extend(["**Architecture**:"])
            for i, item in enumerate(template["architecture"], 1):
                lines.append(f"{i}. {item}")
            lines.append("")
        
        if "structure" in template:
            lines.extend(["**Proposed Structure**:", "```", template["structure"], "```", ""])
        
        if "benefits" in template:
            lines.extend(["**Benefits**:"])
            for benefit in template["benefits"]:
                lines.append(f"- {benefit}")
            lines.append("")
        
        if "testing" in template:
            lines.extend(["**Testing Strategy**:"])
            for test in template["testing"]:
                lines.append(f"- {test}")
            lines.append("")
        
        if "security" in template:
            lines.extend([f"**Security Considerations**: {template['security']}", ""])
        
        if "performance" in template:
            lines.extend([f"**Performance**: {template['performance']}", ""])
        
        if "complexity" in template:
            lines.extend([f"**Complexity Score**: {template['complexity']}", ""])
        
        if "effort" in template:
            lines.extend([f"**Estimated Effort**: {template['effort']}", ""])
        
        lines.extend(["", f"*Mock response generated - ID: {prompt_hash}*"])
        
        return "\n".join(lines)
    
    def _generate_generic_response(self, prompt_hash: str) -> str:
        """Generate a generic response for unknown task types."""
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
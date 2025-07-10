"""
Code Analysis Task Processor Plugin

Specialized task processor for code analysis operations including
static analysis, security scanning, complexity metrics, and
code quality assessment as specified in Epic 3.2.

Features:
- Multi-language code analysis support
- Integration with existing analysis tools (flake8, pylint, mypy, etc.)
- Security vulnerability detection
- Code complexity and maintainability metrics
- Custom analysis pipeline configuration
- Report generation and formatting
"""

import ast
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from supervisor_agent.plugins.plugin_interface import (
    PluginMetadata,
    PluginResult,
    PluginType,
    TaskProcessorInterface,
)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class CodeAnalysisProcessor(TaskProcessorInterface):
    """Task processor for code analysis operations"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.analysis_stats = {
            "total_analyses": 0,
            "successful_analyses": 0,
            "failed_analyses": 0,
            "languages_analyzed": set(),
        }
        
        # Configure analysis tools
        self.analysis_tools = {
            "python": {
                "syntax": self._check_python_syntax,
                "style": self._run_flake8,
                "quality": self._run_pylint,
                "types": self._run_mypy,
                "security": self._run_bandit,
                "complexity": self._calculate_complexity,
            },
            "javascript": {
                "syntax": self._check_js_syntax,
                "style": self._run_eslint,
            },
            "typescript": {
                "syntax": self._check_ts_syntax,
                "style": self._run_eslint,
                "types": self._run_tsc,
            },
        }

    @property
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        return PluginMetadata(
            name="code_analysis_processor",
            version="1.0.0",
            description="Process code analysis tasks with multi-language support",
            author="Supervisor Agent Team",
            plugin_type=PluginType.TASK_PROCESSOR,
            dependencies=[],
            min_api_version="1.0.0",
            max_api_version="2.0.0",
            configuration_schema={
                "supported_languages": {
                    "type": "array",
                    "description": "List of supported programming languages",
                    "required": False,
                    "default": ["python", "javascript", "typescript"],
                },
                "analysis_timeout": {
                    "type": "integer",
                    "description": "Analysis timeout in seconds",
                    "required": False,
                    "default": 300,
                },
                "enable_security_scan": {
                    "type": "boolean",
                    "description": "Enable security vulnerability scanning",
                    "required": False,
                    "default": True,
                },
                "max_file_size_mb": {
                    "type": "integer",
                    "description": "Maximum file size to analyze in MB",
                    "required": False,
                    "default": 10,
                },
            },
            permissions=["file:read", "process:execute", "network:http"],
            tags=["code-analysis", "static-analysis", "security", "quality"],
        )

    async def initialize(self) -> bool:
        """Initialize the plugin"""
        try:
            # Check available analysis tools
            available_tools = self._check_available_tools()
            logger.info(f"Code analysis processor initialized with tools: {available_tools}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize code analysis processor: {str(e)}")
            return False

    async def activate(self) -> bool:
        """Activate the plugin"""
        try:
            logger.info("Code analysis processor activated successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to activate code analysis processor: {str(e)}")
            return False

    async def deactivate(self) -> bool:
        """Deactivate the plugin"""
        try:
            logger.info("Code analysis processor deactivated")
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate code analysis processor: {str(e)}")
            return False

    async def cleanup(self) -> bool:
        """Clean up plugin resources"""
        try:
            logger.info("Code analysis processor cleaned up successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup code analysis processor: {str(e)}")
            return False

    async def health_check(self) -> PluginResult:
        """Check plugin health status"""
        try:
            available_tools = self._check_available_tools()
            
            health_data = {
                "status": "healthy",
                "available_tools": available_tools,
                "analysis_stats": {
                    **self.analysis_stats,
                    "languages_analyzed": list(self.analysis_stats["languages_analyzed"])
                },
                "supported_languages": self.get_configuration_value("supported_languages", []),
            }

            return PluginResult(success=True, data=health_data)
        except Exception as e:
            return PluginResult(success=False, error=str(e))

    async def process_task(self, task_data: Dict[str, Any]) -> PluginResult:
        """Process a code analysis task"""
        try:
            start_time = datetime.now(timezone.utc)
            
            # Extract task parameters
            analysis_type = task_data.get("analysis_type", "full")
            code_content = task_data.get("code_content")
            language = task_data.get("language", "python")
            file_path = task_data.get("file_path")
            options = task_data.get("options", {})
            
            if not code_content and not file_path:
                return PluginResult(
                    success=False,
                    error="Either code_content or file_path must be provided"
                )

            # Validate language support
            supported_languages = self.get_configuration_value("supported_languages", [])
            if language not in supported_languages:
                return PluginResult(
                    success=False,
                    error=f"Language {language} not supported. Supported: {supported_languages}"
                )

            # Get code content
            if code_content:
                # Use provided code content
                code = code_content
                temp_file = None
            else:
                # Read from file
                if not os.path.exists(file_path):
                    return PluginResult(
                        success=False,
                        error=f"File not found: {file_path}"
                    )
                
                # Check file size
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                max_size = self.get_configuration_value("max_file_size_mb", 10)
                if file_size_mb > max_size:
                    return PluginResult(
                        success=False,
                        error=f"File too large: {file_size_mb:.1f}MB > {max_size}MB"
                    )
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                temp_file = None

            # Create temporary file if needed for analysis tools
            if not file_path:
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix=f'.{self._get_file_extension(language)}',
                    delete=False
                )
                temp_file.write(code)
                temp_file.close()
                analysis_file_path = temp_file.name
            else:
                analysis_file_path = file_path

            try:
                # Perform analysis
                analysis_results = await self._analyze_code(
                    code, analysis_file_path, language, analysis_type, options
                )

                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                
                # Update stats
                self.analysis_stats["total_analyses"] += 1
                self.analysis_stats["successful_analyses"] += 1
                self.analysis_stats["languages_analyzed"].add(language)

                return PluginResult(
                    success=True,
                    data={
                        "analysis_type": analysis_type,
                        "language": language,
                        "results": analysis_results,
                        "execution_time": execution_time,
                        "file_info": {
                            "lines": len(code.splitlines()),
                            "characters": len(code),
                            "size_kb": len(code.encode('utf-8')) / 1024,
                        }
                    },
                    execution_time=execution_time
                )

            finally:
                # Clean up temporary file
                if temp_file and os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)

        except Exception as e:
            self.analysis_stats["total_analyses"] += 1
            self.analysis_stats["failed_analyses"] += 1
            logger.error(f"Code analysis failed: {str(e)}")
            return PluginResult(success=False, error=str(e))

    def can_handle_task(self, task_type: str) -> bool:
        """Determine if this plugin can handle the given task type"""
        return task_type in [
            "code_analysis",
            "static_analysis", 
            "security_scan",
            "quality_check",
            "syntax_check",
            "style_check",
            "complexity_analysis"
        ]

    def get_supported_task_types(self) -> List[str]:
        """Return list of supported task types"""
        return [
            "code_analysis",
            "static_analysis",
            "security_scan", 
            "quality_check",
            "syntax_check",
            "style_check",
            "complexity_analysis"
        ]

    async def _analyze_code(
        self,
        code: str,
        file_path: str,
        language: str,
        analysis_type: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform code analysis based on type and language"""
        results = {
            "summary": {
                "language": language,
                "analysis_type": analysis_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "findings": {},
            "metrics": {},
            "errors": []
        }

        analysis_tools = self.analysis_tools.get(language, {})

        try:
            if analysis_type == "syntax" or analysis_type == "full":
                if "syntax" in analysis_tools:
                    syntax_result = analysis_tools["syntax"](code, file_path)
                    results["findings"]["syntax"] = syntax_result

            if analysis_type == "style" or analysis_type == "full":
                if "style" in analysis_tools:
                    style_result = analysis_tools["style"](file_path)
                    results["findings"]["style"] = style_result

            if analysis_type == "quality" or analysis_type == "full":
                if "quality" in analysis_tools:
                    quality_result = analysis_tools["quality"](file_path)
                    results["findings"]["quality"] = quality_result

            if analysis_type == "types" or analysis_type == "full":
                if "types" in analysis_tools:
                    types_result = analysis_tools["types"](file_path)
                    results["findings"]["types"] = types_result

            if analysis_type == "security" or analysis_type == "full":
                if "security" in analysis_tools and self.get_configuration_value("enable_security_scan", True):
                    security_result = analysis_tools["security"](file_path)
                    results["findings"]["security"] = security_result

            if analysis_type == "complexity" or analysis_type == "full":
                if "complexity" in analysis_tools:
                    complexity_result = analysis_tools["complexity"](code, file_path)
                    results["metrics"]["complexity"] = complexity_result

            # Generate summary
            results["summary"]["total_issues"] = sum(
                len(finding.get("issues", [])) for finding in results["findings"].values()
                if isinstance(finding, dict)
            )
            
            results["summary"]["severity_counts"] = self._count_severities(results["findings"])

        except Exception as e:
            results["errors"].append(f"Analysis error: {str(e)}")
            logger.error(f"Code analysis error: {str(e)}")

        return results

    def _check_available_tools(self) -> List[str]:
        """Check which analysis tools are available"""
        tools = []
        
        # Check Python tools
        for tool in ["flake8", "pylint", "mypy", "bandit"]:
            if self._is_tool_available(tool):
                tools.append(tool)
        
        # Check JavaScript/TypeScript tools
        for tool in ["eslint", "tsc"]:
            if self._is_tool_available(tool):
                tools.append(tool)
                
        return tools

    def _is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available in the system"""
        try:
            result = subprocess.run(
                [tool_name, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False

    def _get_file_extension(self, language: str) -> str:
        """Get file extension for language"""
        extensions = {
            "python": "py",
            "javascript": "js",
            "typescript": "ts",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
        }
        return extensions.get(language, "txt")

    # Python analysis methods
    def _check_python_syntax(self, code: str, file_path: str) -> Dict[str, Any]:
        """Check Python syntax"""
        issues = []
        try:
            ast.parse(code)
            return {"status": "valid", "issues": []}
        except SyntaxError as e:
            issues.append({
                "type": "syntax_error",
                "line": e.lineno,
                "column": e.offset,
                "message": e.msg,
                "severity": "error"
            })
            return {"status": "invalid", "issues": issues}

    def _run_flake8(self, file_path: str) -> Dict[str, Any]:
        """Run flake8 style checking"""
        if not self._is_tool_available("flake8"):
            return {"status": "tool_not_available", "issues": []}
        
        try:
            result = subprocess.run(
                ["flake8", file_path, "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            issues = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(': ', 2)
                    if len(parts) >= 3:
                        location = parts[0].split(':')
                        if len(location) >= 3:
                            issues.append({
                                "type": "style",
                                "line": int(location[1]),
                                "column": int(location[2]),
                                "code": parts[1],
                                "message": parts[2],
                                "severity": "warning"
                            })
            
            return {"status": "completed", "issues": issues}
        except Exception as e:
            return {"status": "error", "error": str(e), "issues": []}

    def _run_pylint(self, file_path: str) -> Dict[str, Any]:
        """Run pylint quality checking"""
        if not self._is_tool_available("pylint"):
            return {"status": "tool_not_available", "issues": []}
        
        try:
            result = subprocess.run(
                ["pylint", file_path, "--output-format=json"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            issues = []
            if result.stdout:
                import json
                pylint_results = json.loads(result.stdout)
                for item in pylint_results:
                    issues.append({
                        "type": "quality",
                        "line": item.get("line", 0),
                        "column": item.get("column", 0),
                        "code": item.get("message-id", ""),
                        "message": item.get("message", ""),
                        "severity": item.get("type", "info")
                    })
            
            return {"status": "completed", "issues": issues}
        except Exception as e:
            return {"status": "error", "error": str(e), "issues": []}

    def _run_mypy(self, file_path: str) -> Dict[str, Any]:
        """Run mypy type checking"""
        if not self._is_tool_available("mypy"):
            return {"status": "tool_not_available", "issues": []}
        
        try:
            result = subprocess.run(
                ["mypy", file_path, "--show-column-numbers"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            issues = []
            for line in result.stdout.strip().split('\n'):
                if ':' in line and 'error:' in line:
                    parts = line.split(':', 3)
                    if len(parts) >= 4:
                        issues.append({
                            "type": "type_error",
                            "line": int(parts[1]) if parts[1].isdigit() else 0,
                            "column": int(parts[2]) if parts[2].isdigit() else 0,
                            "message": parts[3].strip(),
                            "severity": "error"
                        })
            
            return {"status": "completed", "issues": issues}
        except Exception as e:
            return {"status": "error", "error": str(e), "issues": []}

    def _run_bandit(self, file_path: str) -> Dict[str, Any]:
        """Run bandit security scanning"""
        if not self._is_tool_available("bandit"):
            return {"status": "tool_not_available", "issues": []}
        
        try:
            result = subprocess.run(
                ["bandit", "-f", "json", file_path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            issues = []
            if result.stdout:
                import json
                bandit_results = json.loads(result.stdout)
                for item in bandit_results.get("results", []):
                    issues.append({
                        "type": "security",
                        "line": item.get("line_number", 0),
                        "column": 0,
                        "code": item.get("test_id", ""),
                        "message": item.get("issue_text", ""),
                        "severity": item.get("issue_severity", "info").lower(),
                        "confidence": item.get("issue_confidence", "").lower()
                    })
            
            return {"status": "completed", "issues": issues}
        except Exception as e:
            return {"status": "error", "error": str(e), "issues": []}

    def _calculate_complexity(self, code: str, file_path: str) -> Dict[str, Any]:
        """Calculate code complexity metrics"""
        try:
            tree = ast.parse(code)
            
            metrics = {
                "lines_of_code": len(code.splitlines()),
                "functions": 0,
                "classes": 0,
                "complexity_score": 0,
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    metrics["functions"] += 1
                elif isinstance(node, ast.ClassDef):
                    metrics["classes"] += 1
                elif isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
                    metrics["complexity_score"] += 1
            
            return {"status": "completed", "metrics": metrics}
        except Exception as e:
            return {"status": "error", "error": str(e), "metrics": {}}

    # JavaScript/TypeScript analysis methods
    def _check_js_syntax(self, code: str, file_path: str) -> Dict[str, Any]:
        """Check JavaScript syntax using Node.js"""
        try:
            # Basic syntax check using Node.js
            result = subprocess.run(
                ["node", "-c", file_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return {"status": "valid", "issues": []}
            else:
                return {
                    "status": "invalid",
                    "issues": [{
                        "type": "syntax_error",
                        "message": result.stderr,
                        "severity": "error"
                    }]
                }
        except Exception as e:
            return {"status": "error", "error": str(e), "issues": []}

    def _check_ts_syntax(self, code: str, file_path: str) -> Dict[str, Any]:
        """Check TypeScript syntax"""
        return self._run_tsc(file_path)

    def _run_eslint(self, file_path: str) -> Dict[str, Any]:
        """Run ESLint for JavaScript/TypeScript"""
        if not self._is_tool_available("eslint"):
            return {"status": "tool_not_available", "issues": []}
        
        try:
            result = subprocess.run(
                ["eslint", file_path, "--format=json"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            issues = []
            if result.stdout:
                import json
                eslint_results = json.loads(result.stdout)
                for file_result in eslint_results:
                    for message in file_result.get("messages", []):
                        issues.append({
                            "type": "style",
                            "line": message.get("line", 0),
                            "column": message.get("column", 0),
                            "code": message.get("ruleId", ""),
                            "message": message.get("message", ""),
                            "severity": message.get("severity", 1) == 2 and "error" or "warning"
                        })
            
            return {"status": "completed", "issues": issues}
        except Exception as e:
            return {"status": "error", "error": str(e), "issues": []}

    def _run_tsc(self, file_path: str) -> Dict[str, Any]:
        """Run TypeScript compiler for type checking"""
        if not self._is_tool_available("tsc"):
            return {"status": "tool_not_available", "issues": []}
        
        try:
            result = subprocess.run(
                ["tsc", "--noEmit", file_path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            issues = []
            for line in result.stderr.strip().split('\n'):
                if '(' in line and ')' in line and ':' in line:
                    # Parse TypeScript error format
                    issues.append({
                        "type": "type_error",
                        "message": line,
                        "severity": "error"
                    })
            
            return {"status": "completed", "issues": issues}
        except Exception as e:
            return {"status": "error", "error": str(e), "issues": []}

    def _count_severities(self, findings: Dict[str, Any]) -> Dict[str, int]:
        """Count issues by severity level"""
        counts = {"error": 0, "warning": 0, "info": 0}
        
        for finding in findings.values():
            if isinstance(finding, dict) and "issues" in finding:
                for issue in finding["issues"]:
                    severity = issue.get("severity", "info")
                    if severity in counts:
                        counts[severity] += 1
        
        return counts
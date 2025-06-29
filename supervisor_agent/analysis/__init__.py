"""
Static Analysis Module

Provides comprehensive code analysis capabilities using SCC and Semgrep.
Designed for AI model consumption with structured insights and recommendations.

Main components:
- SCC Analyzer: Code metrics, complexity, and language analysis
- Semgrep Analyzer: Security and code quality analysis
- Static Analysis Pipeline: Unified analysis with AI-ready outputs

Key features:
- Parallel execution for performance
- AI model integration with structured data
- SARIF output for CI/CD integration
- Focused on Python, TypeScript, and SvelteKit projects
"""

from .scc_analyzer import AnalysisResult as SCCAnalysisResult
from .scc_analyzer import (CodeMetrics, FileMetrics, SCCAnalyzer,
                           analyze_repository_quick, get_code_quality_score)
from .semgrep_analyzer import AnalysisResult as SemgrepAnalysisResult
from .semgrep_analyzer import (Finding, FindingCategory, SemgrepAnalyzer,
                               SeverityLevel, analyze_repository_security,
                               get_vulnerability_summary)
from .static_analysis_pipeline import (PipelineMetrics, PipelineResult,
                                       StaticAnalysisPipeline, UnifiedInsights,
                                       get_ai_analysis_context,
                                       quick_repository_analysis)

__all__ = [
    # SCC Analyzer
    "SCCAnalyzer",
    "CodeMetrics",
    "FileMetrics",
    "SCCAnalysisResult",
    "analyze_repository_quick",
    "get_code_quality_score",
    # Semgrep Analyzer
    "SemgrepAnalyzer",
    "Finding",
    "SeverityLevel",
    "FindingCategory",
    "SemgrepAnalysisResult",
    "analyze_repository_security",
    "get_vulnerability_summary",
    # Pipeline
    "StaticAnalysisPipeline",
    "PipelineResult",
    "UnifiedInsights",
    "PipelineMetrics",
    "quick_repository_analysis",
    "get_ai_analysis_context",
]

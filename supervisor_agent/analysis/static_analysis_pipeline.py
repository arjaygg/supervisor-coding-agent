"""
Static Analysis Pipeline

Combines SCC and Semgrep analysis into a unified pipeline that feeds AI models
with comprehensive code insights. Designed for Python, TypeScript, and SvelteKit.

Key features:
- Parallel execution of SCC and Semgrep analysis
- Unified reporting and insights generation
- AI model integration with structured data
- Performance metrics and caching
- CI/CD ready with SARIF and JSON outputs

Following Lean principles with fast, actionable results for AI consumption.
"""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

from supervisor_agent.analysis.scc_analyzer import SCCAnalyzer, AnalysisResult as SCCResult
from supervisor_agent.analysis.semgrep_analyzer import SemgrepAnalyzer, AnalysisResult as SemgrepResult
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineMetrics:
    """Performance metrics for the analysis pipeline."""
    total_execution_time: float
    scc_execution_time: float
    semgrep_execution_time: float
    parallel_efficiency: float  # Time saved by parallel execution
    files_analyzed: int
    total_findings: int
    pipeline_timestamp: datetime


@dataclass
class UnifiedInsights:
    """Unified insights combining SCC and Semgrep analysis."""
    code_quality_score: int  # 0-100
    security_score: int      # 0-100
    maintainability_score: int  # 0-100
    technical_debt_indicators: List[str]
    priority_recommendations: List[Dict[str, Any]]
    ai_model_context: Dict[str, Any]  # Structured data for AI consumption
    risk_profile: str  # LOW, MEDIUM, HIGH, CRITICAL


@dataclass
class PipelineResult:
    """Complete static analysis pipeline result."""
    scc_result: SCCResult
    semgrep_result: SemgrepResult
    unified_insights: UnifiedInsights
    pipeline_metrics: PipelineMetrics
    repository_path: str
    analysis_timestamp: datetime


class StaticAnalysisPipeline:
    """
    Unified static analysis pipeline combining SCC and Semgrep.
    
    Designed for AI model consumption with:
    - Parallel execution for performance
    - Structured insights for AI processing
    - Comprehensive scoring and recommendations
    - Integration-ready outputs
    """
    
    def __init__(
        self,
        scc_binary_path: str = "scc",
        semgrep_binary_path: str = "semgrep",
        max_workers: int = 2
    ):
        """
        Initialize static analysis pipeline.
        
        Args:
            scc_binary_path: Path to SCC binary
            semgrep_binary_path: Path to Semgrep binary  
            max_workers: Maximum number of parallel workers
        """
        self.scc_analyzer = SCCAnalyzer(scc_binary_path)
        self.semgrep_analyzer = SemgrepAnalyzer(semgrep_binary_path)
        self.max_workers = max_workers
        
        logger.info("Static Analysis Pipeline initialized")
    
    def analyze_repository(
        self,
        repo_path: str,
        include_file_details: bool = True,
        semgrep_timeout: int = 300,
        enable_parallel: bool = True
    ) -> PipelineResult:
        """
        Run complete static analysis pipeline on repository.
        
        Args:
            repo_path: Path to repository root
            include_file_details: Include detailed file metrics
            semgrep_timeout: Semgrep analysis timeout in seconds
            enable_parallel: Run SCC and Semgrep in parallel
            
        Returns:
            Complete pipeline analysis result
        """
        start_time = datetime.now()
        
        try:
            repo_path = Path(repo_path).resolve()
            if not repo_path.exists():
                raise ValueError(f"Repository path does not exist: {repo_path}")
            
            logger.info(f"Starting static analysis pipeline for {repo_path}")
            
            if enable_parallel:
                scc_result, semgrep_result = self._run_parallel_analysis(
                    repo_path, include_file_details, semgrep_timeout
                )
            else:
                scc_result = self._run_scc_analysis(repo_path, include_file_details)
                semgrep_result = self._run_semgrep_analysis(repo_path, semgrep_timeout)
            
            # Generate unified insights
            unified_insights = self._generate_unified_insights(scc_result, semgrep_result)
            
            # Calculate pipeline metrics
            total_execution_time = (datetime.now() - start_time).total_seconds()
            pipeline_metrics = PipelineMetrics(
                total_execution_time=total_execution_time,
                scc_execution_time=scc_result.execution_time_seconds,
                semgrep_execution_time=semgrep_result.execution_time_seconds,
                parallel_efficiency=self._calculate_parallel_efficiency(
                    total_execution_time,
                    scc_result.execution_time_seconds,
                    semgrep_result.execution_time_seconds,
                    enable_parallel
                ),
                files_analyzed=scc_result.total_metrics.files,
                total_findings=semgrep_result.summary["total_findings"],
                pipeline_timestamp=start_time
            )
            
            result = PipelineResult(
                scc_result=scc_result,
                semgrep_result=semgrep_result,
                unified_insights=unified_insights,
                pipeline_metrics=pipeline_metrics,
                repository_path=str(repo_path),
                analysis_timestamp=start_time
            )
            
            logger.info(
                f"Pipeline completed in {total_execution_time:.2f}s: "
                f"Quality Score: {unified_insights.code_quality_score}, "
                f"Security Score: {unified_insights.security_score}, "
                f"Risk: {unified_insights.risk_profile}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Pipeline analysis error: {str(e)}")
            raise
    
    def analyze_files(
        self,
        file_paths: List[str],
        base_path: Optional[str] = None,
        enable_parallel: bool = True
    ) -> PipelineResult:
        """
        Analyze specific files with the pipeline.
        
        Args:
            file_paths: List of file paths to analyze
            base_path: Base path for relative file paths
            enable_parallel: Run analyses in parallel
            
        Returns:
            Pipeline analysis result for specified files
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Analyzing {len(file_paths)} files with pipeline")
            
            if enable_parallel:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit both analyses
                    scc_future = executor.submit(
                        self.scc_analyzer.analyze_files, 
                        file_paths, 
                        base_path
                    )
                    semgrep_future = executor.submit(
                        self.semgrep_analyzer.analyze_files,
                        file_paths,
                        None,  # rulesets - let it auto-detect
                        base_path
                    )
                    
                    # Wait for completion
                    scc_result = scc_future.result()
                    semgrep_result = semgrep_future.result()
            else:
                scc_result = self.scc_analyzer.analyze_files(file_paths, base_path)
                semgrep_result = self.semgrep_analyzer.analyze_files(
                    file_paths, None, base_path
                )
            
            # Generate unified insights
            unified_insights = self._generate_unified_insights(scc_result, semgrep_result)
            
            # Calculate metrics
            total_execution_time = (datetime.now() - start_time).total_seconds()
            pipeline_metrics = PipelineMetrics(
                total_execution_time=total_execution_time,
                scc_execution_time=scc_result.execution_time_seconds,
                semgrep_execution_time=semgrep_result.execution_time_seconds,
                parallel_efficiency=self._calculate_parallel_efficiency(
                    total_execution_time,
                    scc_result.execution_time_seconds,
                    semgrep_result.execution_time_seconds,
                    enable_parallel
                ),
                files_analyzed=scc_result.total_metrics.files,
                total_findings=semgrep_result.summary["total_findings"],
                pipeline_timestamp=start_time
            )
            
            result = PipelineResult(
                scc_result=scc_result,
                semgrep_result=semgrep_result,
                unified_insights=unified_insights,
                pipeline_metrics=pipeline_metrics,
                repository_path=base_path or "file_analysis",
                analysis_timestamp=start_time
            )
            
            return result
            
        except Exception as e:
            logger.error(f"File analysis pipeline error: {str(e)}")
            raise
    
    def _run_parallel_analysis(
        self,
        repo_path: Path,
        include_file_details: bool,
        semgrep_timeout: int
    ) -> Tuple[SCCResult, SemgrepResult]:
        """Run SCC and Semgrep analysis in parallel."""
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit both analyses
                scc_future = executor.submit(
                    self._run_scc_analysis, 
                    repo_path, 
                    include_file_details
                )
                semgrep_future = executor.submit(
                    self._run_semgrep_analysis,
                    repo_path,
                    semgrep_timeout
                )
                
                # Collect results as they complete
                scc_result = None
                semgrep_result = None
                
                for future in as_completed([scc_future, semgrep_future]):
                    try:
                        if future == scc_future:
                            scc_result = future.result()
                            logger.info("SCC analysis completed")
                        elif future == semgrep_future:
                            semgrep_result = future.result()
                            logger.info("Semgrep analysis completed")
                    except Exception as e:
                        logger.error(f"Analysis future failed: {e}")
                        raise
                
                if scc_result is None or semgrep_result is None:
                    raise RuntimeError("One or more analyses failed to complete")
                
                return scc_result, semgrep_result
                
        except Exception as e:
            logger.error(f"Parallel analysis error: {e}")
            raise
    
    def _run_scc_analysis(
        self, 
        repo_path: Path, 
        include_file_details: bool
    ) -> SCCResult:
        """Run SCC analysis."""
        try:
            return self.scc_analyzer.analyze_repository(
                str(repo_path),
                include_files=include_file_details
            )
        except Exception as e:
            logger.error(f"SCC analysis failed: {e}")
            raise
    
    def _run_semgrep_analysis(
        self, 
        repo_path: Path, 
        timeout: int
    ) -> SemgrepResult:
        """Run Semgrep analysis."""
        try:
            return self.semgrep_analyzer.analyze_repository(
                str(repo_path),
                timeout_seconds=timeout
            )
        except Exception as e:
            logger.error(f"Semgrep analysis failed: {e}")
            raise
    
    def _generate_unified_insights(
        self,
        scc_result: SCCResult,
        semgrep_result: SemgrepResult
    ) -> UnifiedInsights:
        """Generate unified insights from both analyses."""
        try:
            # Get individual insights
            scc_insights = self.scc_analyzer.get_language_insights(scc_result)
            semgrep_insights = self.semgrep_analyzer.get_security_insights(semgrep_result)
            
            # Calculate composite scores
            code_quality_score = self._calculate_code_quality_score(scc_result, scc_insights)
            security_score = semgrep_insights.get("security_score", 100)
            maintainability_score = scc_insights.get("maintainability_score", 50)
            
            # Identify technical debt indicators
            technical_debt = self._identify_technical_debt(scc_result, semgrep_result)
            
            # Generate priority recommendations
            recommendations = self._generate_priority_recommendations(
                scc_result, semgrep_result, scc_insights, semgrep_insights
            )
            
            # Create AI model context
            ai_context = self._create_ai_model_context(
                scc_result, semgrep_result, scc_insights, semgrep_insights
            )
            
            # Determine risk profile
            risk_profile = self._calculate_risk_profile(
                code_quality_score, security_score, maintainability_score,
                len(technical_debt), semgrep_result.summary["by_severity"]["ERROR"]
            )
            
            return UnifiedInsights(
                code_quality_score=code_quality_score,
                security_score=security_score,
                maintainability_score=maintainability_score,
                technical_debt_indicators=technical_debt,
                priority_recommendations=recommendations,
                ai_model_context=ai_context,
                risk_profile=risk_profile
            )
            
        except Exception as e:
            logger.error(f"Error generating unified insights: {e}")
            raise
    
    def _calculate_code_quality_score(
        self, 
        scc_result: SCCResult, 
        scc_insights: Dict[str, Any]
    ) -> int:
        """Calculate overall code quality score (0-100)."""
        try:
            score = 100
            
            # Factor in maintainability from SCC
            maintainability = scc_insights.get("maintainability_score", 50)
            score = int(score * 0.4 + maintainability * 0.6)
            
            # Factor in language diversity (too many languages can be problematic)
            diversity = scc_insights.get("language_diversity", 1)
            if diversity > 5:
                score -= min(15, (diversity - 5) * 3)
            
            # Factor in complexity distribution
            complexity_dist = scc_insights.get("complexity_distribution", {})
            high_complexity_langs = [
                lang for lang, data in complexity_dist.items()
                if data.get("complexity_per_line", 0) > 0.2
            ]
            if high_complexity_langs:
                score -= min(20, len(high_complexity_langs) * 5)
            
            return max(0, min(100, score))
            
        except Exception as e:
            logger.error(f"Error calculating code quality score: {e}")
            return 50  # Default neutral score
    
    def _identify_technical_debt(
        self, 
        scc_result: SCCResult, 
        semgrep_result: SemgrepResult
    ) -> List[str]:
        """Identify technical debt indicators."""
        debt_indicators = []
        
        try:
            # Large files
            if scc_result.file_details:
                large_files = [
                    f for f in scc_result.file_details if f.lines > 500
                ]
                if large_files:
                    debt_indicators.append(
                        f"{len(large_files)} files exceed 500 lines (largest: "
                        f"{max(f.lines for f in large_files)} lines)"
                    )
            
            # High complexity
            if scc_result.total_metrics.files > 0:
                avg_complexity = (
                    scc_result.total_metrics.complexity / 
                    scc_result.total_metrics.files
                )
                if avg_complexity > 15:
                    debt_indicators.append(
                        f"High average complexity per file: {avg_complexity:.1f}"
                    )
            
            # Low comment ratio
            if scc_result.total_metrics.lines > 0:
                comment_ratio = (
                    scc_result.total_metrics.comments / 
                    scc_result.total_metrics.lines
                )
                if comment_ratio < 0.05:
                    debt_indicators.append(
                        f"Low documentation: {comment_ratio:.1%} comments"
                    )
            
            # Security debt
            critical_security = semgrep_result.summary["by_severity"]["ERROR"]
            if critical_security > 0:
                debt_indicators.append(f"{critical_security} critical security issues")
            
            # Code quality debt from Semgrep
            quality_issues = semgrep_result.summary["by_category"].get("correctness", 0)
            if quality_issues > 10:
                debt_indicators.append(f"{quality_issues} code correctness issues")
            
            return debt_indicators[:5]  # Limit to top 5 indicators
            
        except Exception as e:
            logger.error(f"Error identifying technical debt: {e}")
            return ["Unable to assess technical debt"]
    
    def _generate_priority_recommendations(
        self,
        scc_result: SCCResult,
        semgrep_result: SemgrepResult,
        scc_insights: Dict[str, Any],
        semgrep_insights: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate prioritized recommendations for improvement."""
        recommendations = []
        
        try:
            # Security recommendations (highest priority)
            if semgrep_insights.get("risk_assessment") in ["HIGH", "CRITICAL"]:
                recommendations.append({
                    "priority": "CRITICAL",
                    "category": "security",
                    "title": "Address Critical Security Issues",
                    "description": f"Found {semgrep_result.summary['by_severity']['ERROR']} critical security vulnerabilities",
                    "impact": "HIGH",
                    "effort": "MEDIUM",
                    "action_items": [
                        f"Review and fix: {issue['rule_id']}" 
                        for issue in semgrep_insights.get("critical_issues", [])[:3]
                    ]
                })
            
            # Code quality recommendations
            code_quality_score = scc_insights.get("maintainability_score", 50)
            if code_quality_score < 70:
                recommendations.append({
                    "priority": "HIGH",
                    "category": "maintainability",
                    "title": "Improve Code Maintainability",
                    "description": f"Maintainability score: {code_quality_score}/100",
                    "impact": "MEDIUM",
                    "effort": "HIGH",
                    "action_items": scc_insights.get("recommendations", [])[:3]
                })
            
            # Performance recommendations from Semgrep
            perf_issues = semgrep_result.summary["by_category"].get("performance", 0)
            if perf_issues > 0:
                recommendations.append({
                    "priority": "MEDIUM",
                    "category": "performance",
                    "title": "Address Performance Issues",
                    "description": f"Found {perf_issues} performance-related issues",
                    "impact": "MEDIUM",
                    "effort": "LOW",
                    "action_items": [
                        "Review performance-related findings in Semgrep report"
                    ]
                })
            
            # Documentation recommendations
            if scc_result.total_metrics.lines > 0:
                comment_ratio = (
                    scc_result.total_metrics.comments / 
                    scc_result.total_metrics.lines
                )
                if comment_ratio < 0.1:
                    recommendations.append({
                        "priority": "LOW",
                        "category": "documentation",
                        "title": "Improve Code Documentation",
                        "description": f"Comment ratio: {comment_ratio:.1%} (recommended: >10%)",
                        "impact": "LOW",
                        "effort": "MEDIUM",
                        "action_items": [
                            "Add docstrings to functions and classes",
                            "Document complex algorithms and business logic",
                            "Add README files for modules"
                        ]
                    })
            
            return recommendations[:5]  # Top 5 recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return [{"error": "Unable to generate recommendations"}]
    
    def _create_ai_model_context(
        self,
        scc_result: SCCResult,
        semgrep_result: SemgrepResult,
        scc_insights: Dict[str, Any],
        semgrep_insights: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create structured context for AI model consumption."""
        try:
            return {
                "codebase_summary": {
                    "total_files": scc_result.total_metrics.files,
                    "total_lines": scc_result.total_metrics.lines,
                    "primary_languages": scc_result.repository_summary["primary_languages"],
                    "complexity_score": scc_result.total_metrics.complexity,
                    "dominant_language": scc_insights.get("dominant_language")
                },
                "security_context": {
                    "vulnerability_count": semgrep_result.summary["total_findings"],
                    "critical_vulnerabilities": semgrep_result.summary["by_severity"]["ERROR"],
                    "security_score": semgrep_insights.get("security_score", 100),
                    "risk_level": semgrep_insights.get("risk_assessment", "LOW"),
                    "top_vulnerability_types": list(
                        semgrep_result.summary["by_category"].keys()
                    )[:3]
                },
                "quality_metrics": {
                    "maintainability_score": scc_insights.get("maintainability_score", 50),
                    "comment_ratio": (
                        scc_result.total_metrics.comments / 
                        max(scc_result.total_metrics.lines, 1)
                    ),
                    "average_file_size": (
                        scc_result.total_metrics.lines / 
                        max(scc_result.total_metrics.files, 1)
                    ),
                    "complexity_per_line": (
                        scc_result.total_metrics.complexity /
                        max(scc_result.total_metrics.lines, 1)
                    )
                },
                "project_characteristics": {
                    "is_web_project": any(
                        lang in ["TypeScript", "JavaScript", "Svelte"]
                        for lang in scc_result.repository_summary["primary_languages"]
                    ),
                    "is_python_project": "Python" in scc_result.repository_summary["primary_languages"],
                    "language_diversity": scc_insights.get("language_diversity", 1),
                    "estimated_project_age": "unknown",  # Could be enhanced with git analysis
                    "estimated_team_size": min(
                        max(1, scc_result.total_metrics.files // 100), 20
                    )  # Rough heuristic
                },
                "actionable_insights": {
                    "immediate_actions": len([
                        r for r in self._generate_priority_recommendations(
                            scc_result, semgrep_result, scc_insights, semgrep_insights
                        ) if r.get("priority") in ["CRITICAL", "HIGH"]
                    ]),
                    "technical_debt_level": len(
                        self._identify_technical_debt(scc_result, semgrep_result)
                    ),
                    "refactoring_candidates": len([
                        f for f in scc_result.file_details 
                        if f.lines > 500 or f.complexity > 50
                    ]) if scc_result.file_details else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating AI model context: {e}")
            return {"error": "Unable to create AI context"}
    
    def _calculate_risk_profile(
        self,
        code_quality_score: int,
        security_score: int,
        maintainability_score: int,
        technical_debt_count: int,
        critical_security_issues: int
    ) -> str:
        """Calculate overall risk profile."""
        try:
            # Critical risk conditions
            if critical_security_issues > 10 or security_score < 30:
                return "CRITICAL"
            
            # High risk conditions
            if (
                critical_security_issues > 0 or
                security_score < 60 or
                code_quality_score < 40 or
                technical_debt_count > 5
            ):
                return "HIGH"
            
            # Medium risk conditions
            if (
                security_score < 80 or
                code_quality_score < 70 or
                maintainability_score < 60 or
                technical_debt_count > 2
            ):
                return "MEDIUM"
            
            return "LOW"
            
        except Exception as e:
            logger.error(f"Error calculating risk profile: {e}")
            return "MEDIUM"  # Default to medium risk
    
    def _calculate_parallel_efficiency(
        self,
        total_time: float,
        scc_time: float,
        semgrep_time: float,
        was_parallel: bool
    ) -> float:
        """Calculate efficiency gained from parallel execution."""
        if not was_parallel:
            return 0.0
        
        try:
            sequential_time = scc_time + semgrep_time
            if sequential_time == 0:
                return 0.0
            
            time_saved = sequential_time - total_time
            efficiency = (time_saved / sequential_time) * 100
            
            return max(0.0, min(100.0, efficiency))
            
        except Exception as e:
            logger.error(f"Error calculating parallel efficiency: {e}")
            return 0.0
    
    def export_unified_json(self, pipeline_result: PipelineResult) -> str:
        """Export complete pipeline result as JSON."""
        try:
            # Create exportable dictionary
            export_data = {
                "analysis_timestamp": pipeline_result.analysis_timestamp.isoformat(),
                "repository_path": pipeline_result.repository_path,
                "pipeline_metrics": asdict(pipeline_result.pipeline_metrics),
                "unified_insights": asdict(pipeline_result.unified_insights),
                "scc_summary": {
                    "total_metrics": asdict(pipeline_result.scc_result.total_metrics),
                    "language_breakdown": [
                        asdict(lang) for lang in pipeline_result.scc_result.language_breakdown
                    ],
                    "repository_summary": pipeline_result.scc_result.repository_summary
                },
                "semgrep_summary": pipeline_result.semgrep_result.summary,
                "ai_ready_context": pipeline_result.unified_insights.ai_model_context
            }
            
            return json.dumps(export_data, indent=2, default=str)
            
        except Exception as e:
            logger.error(f"Error exporting unified JSON: {e}")
            raise
    
    def export_sarif(self, pipeline_result: PipelineResult) -> str:
        """Export Semgrep results as SARIF for CI/CD integration."""
        return self.semgrep_analyzer.export_sarif(pipeline_result.semgrep_result)


# Convenience functions for integration
def quick_repository_analysis(repo_path: str) -> Dict[str, Any]:
    """Quick repository analysis for dashboard/API consumption."""
    pipeline = StaticAnalysisPipeline()
    result = pipeline.analyze_repository(repo_path, include_file_details=False)
    
    return {
        "quality_score": result.unified_insights.code_quality_score,
        "security_score": result.unified_insights.security_score,
        "risk_profile": result.unified_insights.risk_profile,
        "total_files": result.scc_result.total_metrics.files,
        "total_findings": result.semgrep_result.summary["total_findings"],
        "execution_time": result.pipeline_metrics.total_execution_time,
        "top_recommendations": result.unified_insights.priority_recommendations[:3]
    }


def get_ai_analysis_context(repo_path: str) -> Dict[str, Any]:
    """Get structured context optimized for AI model consumption."""
    pipeline = StaticAnalysisPipeline()
    result = pipeline.analyze_repository(repo_path, include_file_details=True)
    
    return result.unified_insights.ai_model_context
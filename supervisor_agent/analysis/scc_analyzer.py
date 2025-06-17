"""
SCC (Source Code Counter) Analyzer

Provides comprehensive code metrics and analysis using SCC tool.
Focus on Python, TypeScript, and SvelteKit projects.

Key metrics:
- Lines of code, complexity, SLOC
- Language distribution
- File-level metrics
- Repository health indicators

Following Lean principles with fast, accurate analysis.
"""

import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CodeMetrics:
    """Code metrics from SCC analysis."""

    language: str
    files: int
    lines: int
    blanks: int
    comments: int
    complexity: int
    bytes: int


@dataclass
class FileMetrics:
    """Individual file metrics."""

    filename: str
    language: str
    lines: int
    blanks: int
    comments: int
    complexity: int
    bytes: int


@dataclass
class AnalysisResult:
    """Complete SCC analysis result."""

    total_metrics: CodeMetrics
    language_breakdown: List[CodeMetrics]
    file_details: List[FileMetrics]
    repository_summary: Dict[str, Any]
    analysis_timestamp: datetime
    execution_time_seconds: float


class SCCAnalyzer:
    """
    Source Code Counter analyzer for comprehensive code metrics.

    Optimized for Python, TypeScript, and SvelteKit projects with focus on:
    - Performance (sub-second analysis for most repos)
    - Accuracy (language-specific counting)
    - Rich metrics (complexity, maintainability indicators)
    """

    def __init__(self, scc_binary_path: str = "scc"):
        """
        Initialize SCC analyzer.

        Args:
            scc_binary_path: Path to SCC binary (default: assumes in PATH)
        """
        self.scc_binary_path = scc_binary_path
        self.supported_languages = {
            "Python",
            "TypeScript",
            "JavaScript",
            "Svelte",
            "JSON",
            "YAML",
            "HTML",
            "CSS",
            "Markdown",
            "Shell",
        }

        # Verify SCC is available
        self._verify_scc_installation()

    def _verify_scc_installation(self):
        """Verify SCC is installed and accessible."""
        try:
            result = subprocess.run(
                [self.scc_binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(f"SCC not accessible: {result.stderr}")

            logger.info(f"SCC version: {result.stdout.strip()}")

        except FileNotFoundError:
            raise RuntimeError(
                f"SCC not found at {self.scc_binary_path}. "
                "Install with: go install github.com/boyter/scc/v3@latest"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("SCC installation check timed out")

    def analyze_repository(
        self,
        repo_path: str,
        include_files: bool = True,
        exclude_patterns: Optional[List[str]] = None,
    ) -> AnalysisResult:
        """
        Analyze a complete repository with SCC.

        Args:
            repo_path: Path to repository root
            include_files: Whether to include per-file analysis
            exclude_patterns: Patterns to exclude (e.g., ['node_modules', '.git'])

        Returns:
            Complete analysis result with metrics and file details
        """
        start_time = datetime.now()

        try:
            repo_path = Path(repo_path).resolve()
            if not repo_path.exists():
                raise ValueError(f"Repository path does not exist: {repo_path}")

            logger.info(f"Starting SCC analysis of {repo_path}")

            # Build SCC command
            cmd = [
                self.scc_binary_path,
                "--format",
                "json",
                "--by-file" if include_files else "--no-by-file",
                "--count-as",
                "py:Python,ts:TypeScript,js:JavaScript,svelte:Svelte",
            ]

            # Add exclusions
            default_excludes = [
                "node_modules",
                ".git",
                "__pycache__",
                ".pytest_cache",
                "dist",
                "build",
                ".svelte-kit",
                ".vscode",
                ".idea",
                "*.pyc",
                "*.pyo",
                "*.pyd",
                ".DS_Store",
            ]

            if exclude_patterns:
                default_excludes.extend(exclude_patterns)

            for pattern in default_excludes:
                cmd.extend(["--exclude-dir", pattern])

            cmd.append(str(repo_path))

            # Execute SCC
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=repo_path,
            )

            if result.returncode != 0:
                raise RuntimeError(f"SCC analysis failed: {result.stderr}")

            # Parse JSON output
            scc_data = json.loads(result.stdout)

            # Process results
            analysis_result = self._process_scc_output(
                scc_data, repo_path, start_time, include_files
            )

            execution_time = (datetime.now() - start_time).total_seconds()
            analysis_result.execution_time_seconds = execution_time

            logger.info(
                f"SCC analysis completed in {execution_time:.2f}s: "
                f"{analysis_result.total_metrics.files} files, "
                f"{analysis_result.total_metrics.lines} total lines"
            )

            return analysis_result

        except subprocess.TimeoutExpired:
            raise RuntimeError("SCC analysis timed out after 5 minutes")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse SCC output: {e}")
        except Exception as e:
            logger.error(f"SCC analysis error: {str(e)}")
            raise

    def analyze_files(
        self, file_paths: List[str], base_path: Optional[str] = None
    ) -> AnalysisResult:
        """
        Analyze specific files with SCC.

        Args:
            file_paths: List of file paths to analyze
            base_path: Base path for relative file paths

        Returns:
            Analysis result for specified files
        """
        try:
            # Create temporary directory with files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Copy files to temp directory maintaining structure
                for file_path in file_paths:
                    source_path = Path(file_path)
                    if not source_path.is_absolute() and base_path:
                        source_path = Path(base_path) / source_path

                    if not source_path.exists():
                        logger.warning(f"File not found: {source_path}")
                        continue

                    # Create relative path in temp dir
                    if base_path:
                        try:
                            rel_path = source_path.relative_to(Path(base_path))
                        except ValueError:
                            rel_path = source_path.name
                    else:
                        rel_path = source_path.name

                    dest_path = temp_path / rel_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, dest_path)

                # Analyze temp directory
                return self.analyze_repository(
                    str(temp_path), include_files=True, exclude_patterns=[]
                )

        except Exception as e:
            logger.error(f"File analysis error: {str(e)}")
            raise

    def get_language_insights(self, analysis_result: AnalysisResult) -> Dict[str, Any]:
        """
        Extract language-specific insights from analysis.

        Args:
            analysis_result: SCC analysis result

        Returns:
            Dictionary with language insights and recommendations
        """
        try:
            insights = {
                "dominant_language": None,
                "language_diversity": 0,
                "complexity_distribution": {},
                "maintainability_score": 0,
                "recommendations": [],
            }

            if not analysis_result.language_breakdown:
                return insights

            # Find dominant language
            dominant = max(analysis_result.language_breakdown, key=lambda x: x.lines)
            insights["dominant_language"] = dominant.language

            # Calculate language diversity (number of languages with >5% of total lines)
            total_lines = analysis_result.total_metrics.lines
            if total_lines > 0:
                significant_languages = [
                    lang
                    for lang in analysis_result.language_breakdown
                    if (lang.lines / total_lines) > 0.05
                ]
                insights["language_diversity"] = len(significant_languages)

            # Complexity analysis
            for lang_metrics in analysis_result.language_breakdown:
                if lang_metrics.lines > 0:
                    complexity_ratio = lang_metrics.complexity / lang_metrics.lines
                    insights["complexity_distribution"][lang_metrics.language] = {
                        "total_complexity": lang_metrics.complexity,
                        "complexity_per_line": round(complexity_ratio, 3),
                        "lines": lang_metrics.lines,
                    }

            # Calculate maintainability score (0-100)
            insights["maintainability_score"] = self._calculate_maintainability_score(
                analysis_result
            )

            # Generate recommendations
            insights["recommendations"] = self._generate_recommendations(
                analysis_result, insights
            )

            return insights

        except Exception as e:
            logger.error(f"Error generating language insights: {str(e)}")
            return {"error": str(e)}

    def _process_scc_output(
        self,
        scc_data: Dict[str, Any],
        repo_path: Path,
        start_time: datetime,
        include_files: bool,
    ) -> AnalysisResult:
        """Process SCC JSON output into structured result."""
        try:
            # Extract language breakdown
            language_breakdown = []
            for lang_data in scc_data.get("Languages", []):
                metrics = CodeMetrics(
                    language=lang_data["Name"],
                    files=lang_data["Count"],
                    lines=lang_data["Lines"],
                    blanks=lang_data["Blank"],
                    comments=lang_data["Comment"],
                    complexity=lang_data["Complexity"],
                    bytes=lang_data["Bytes"],
                )
                language_breakdown.append(metrics)

            # Calculate total metrics
            total_metrics = CodeMetrics(
                language="Total",
                files=sum(lang.files for lang in language_breakdown),
                lines=sum(lang.lines for lang in language_breakdown),
                blanks=sum(lang.blanks for lang in language_breakdown),
                comments=sum(lang.comments for lang in language_breakdown),
                complexity=sum(lang.complexity for lang in language_breakdown),
                bytes=sum(lang.bytes for lang in language_breakdown),
            )

            # Extract file details if requested
            file_details = []
            if include_files and "Files" in scc_data:
                for file_data in scc_data["Files"]:
                    file_metrics = FileMetrics(
                        filename=file_data["Filename"],
                        language=file_data["Language"],
                        lines=file_data["Lines"],
                        blanks=file_data["Blank"],
                        comments=file_data["Comment"],
                        complexity=file_data["Complexity"],
                        bytes=file_data["Bytes"],
                    )
                    file_details.append(file_metrics)

            # Create repository summary
            repository_summary = {
                "path": str(repo_path),
                "total_files": total_metrics.files,
                "total_lines": total_metrics.lines,
                "languages_detected": len(language_breakdown),
                "primary_languages": [
                    lang.language
                    for lang in sorted(
                        language_breakdown, key=lambda x: x.lines, reverse=True
                    )[:3]
                ],
                "code_to_comment_ratio": (
                    (
                        (total_metrics.lines - total_metrics.comments)
                        / max(total_metrics.comments, 1)
                    )
                    if total_metrics.comments > 0
                    else float("inf")
                ),
                "average_complexity_per_file": (
                    total_metrics.complexity / max(total_metrics.files, 1)
                ),
            }

            return AnalysisResult(
                total_metrics=total_metrics,
                language_breakdown=language_breakdown,
                file_details=file_details,
                repository_summary=repository_summary,
                analysis_timestamp=start_time,
                execution_time_seconds=0,  # Will be set by caller
            )

        except Exception as e:
            logger.error(f"Error processing SCC output: {str(e)}")
            raise

    def _calculate_maintainability_score(self, analysis_result: AnalysisResult) -> int:
        """Calculate maintainability score (0-100)."""
        try:
            score = 100

            # Penalize high complexity
            if analysis_result.total_metrics.lines > 0:
                complexity_ratio = (
                    analysis_result.total_metrics.complexity
                    / analysis_result.total_metrics.lines
                )
                if complexity_ratio > 0.3:  # High complexity threshold
                    score -= min(30, int((complexity_ratio - 0.3) * 100))

            # Reward good comments
            if analysis_result.total_metrics.lines > 0:
                comment_ratio = (
                    analysis_result.total_metrics.comments
                    / analysis_result.total_metrics.lines
                )
                if comment_ratio < 0.1:  # Low comment threshold
                    score -= min(20, int((0.1 - comment_ratio) * 200))

            # Penalize very large files
            if analysis_result.file_details:
                large_files = [f for f in analysis_result.file_details if f.lines > 500]
                if large_files:
                    score -= min(15, len(large_files) * 3)

            # Reward language consistency
            if len(analysis_result.language_breakdown) > 5:
                score -= min(10, (len(analysis_result.language_breakdown) - 5) * 2)

            return max(0, score)

        except Exception as e:
            logger.error(f"Error calculating maintainability score: {str(e)}")
            return 50  # Default neutral score

    def _generate_recommendations(
        self, analysis_result: AnalysisResult, insights: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        try:
            # Comment ratio recommendations
            total_lines = analysis_result.total_metrics.lines
            comment_lines = analysis_result.total_metrics.comments

            if total_lines > 0:
                comment_ratio = comment_lines / total_lines
                if comment_ratio < 0.1:
                    recommendations.append(
                        f"Consider adding more documentation. Current comment ratio: "
                        f"{comment_ratio:.1%} (recommended: >10%)"
                    )

            # Complexity recommendations
            if analysis_result.total_metrics.files > 0:
                avg_complexity = (
                    analysis_result.total_metrics.complexity
                    / analysis_result.total_metrics.files
                )
                if avg_complexity > 10:
                    recommendations.append(
                        f"High average complexity per file ({avg_complexity:.1f}). "
                        "Consider refactoring complex functions."
                    )

            # Large file recommendations
            if analysis_result.file_details:
                large_files = [f for f in analysis_result.file_details if f.lines > 500]
                if large_files:
                    recommendations.append(
                        f"Found {len(large_files)} large files (>500 lines). "
                        "Consider breaking them into smaller modules."
                    )

            # Language-specific recommendations
            dominant_lang = insights.get("dominant_language")
            if dominant_lang == "JavaScript":
                ts_files = sum(
                    1
                    for lang in analysis_result.language_breakdown
                    if lang.language == "TypeScript"
                )
                if ts_files == 0:
                    recommendations.append(
                        "Consider migrating to TypeScript for better type safety."
                    )

            # Maintainability recommendations
            maintainability = insights.get("maintainability_score", 50)
            if maintainability < 70:
                recommendations.append(
                    f"Maintainability score is {maintainability}/100. "
                    "Focus on reducing complexity and improving documentation."
                )

            return recommendations[:5]  # Limit to top 5 recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return ["Unable to generate recommendations due to analysis error."]

    def export_metrics_json(self, analysis_result: AnalysisResult) -> str:
        """Export analysis result as JSON string."""
        try:
            # Convert to dictionary with proper serialization
            result_dict = {
                "total_metrics": asdict(analysis_result.total_metrics),
                "language_breakdown": [
                    asdict(lang) for lang in analysis_result.language_breakdown
                ],
                "file_details": [asdict(file) for file in analysis_result.file_details],
                "repository_summary": analysis_result.repository_summary,
                "analysis_timestamp": analysis_result.analysis_timestamp.isoformat(),
                "execution_time_seconds": analysis_result.execution_time_seconds,
            }

            return json.dumps(result_dict, indent=2)

        except Exception as e:
            logger.error(f"Error exporting metrics: {str(e)}")
            raise


# Convenience functions for integration
def analyze_repository_quick(repo_path: str) -> Dict[str, Any]:
    """Quick repository analysis with basic metrics."""
    analyzer = SCCAnalyzer()
    result = analyzer.analyze_repository(repo_path, include_files=False)
    insights = analyzer.get_language_insights(result)

    return {
        "summary": asdict(result.total_metrics),
        "languages": [asdict(lang) for lang in result.language_breakdown],
        "insights": insights,
        "execution_time": result.execution_time_seconds,
    }


def get_code_quality_score(repo_path: str) -> Dict[str, Any]:
    """Get code quality score and key metrics."""
    analyzer = SCCAnalyzer()
    result = analyzer.analyze_repository(repo_path, include_files=True)
    insights = analyzer.get_language_insights(result)

    return {
        "maintainability_score": insights["maintainability_score"],
        "total_lines": result.total_metrics.lines,
        "total_files": result.total_metrics.files,
        "complexity": result.total_metrics.complexity,
        "recommendations": insights["recommendations"],
    }

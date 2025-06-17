"""
Semgrep Security and Code Quality Analyzer

Provides comprehensive security and code quality analysis using Semgrep.
Focus on Python, TypeScript, and JavaScript with custom rules for SvelteKit.

Key features:
- Security vulnerability detection
- Code quality and anti-pattern detection
- Performance issue identification
- Custom rules for modern frameworks
- SARIF output for CI/CD integration

Following Lean principles with actionable, false-positive-minimized results.
"""

import json
import subprocess
import tempfile
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class SeverityLevel(Enum):
    """Semgrep finding severity levels."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class FindingCategory(Enum):
    """Categories of security/quality findings."""

    SECURITY = "security"
    CORRECTNESS = "correctness"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    BEST_PRACTICES = "best-practices"


@dataclass
class Finding:
    """Individual Semgrep finding."""

    rule_id: str
    severity: SeverityLevel
    category: FindingCategory
    message: str
    file_path: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    code_snippet: str
    fix_suggestion: Optional[str] = None


@dataclass
class RulesetStats:
    """Statistics for a specific ruleset."""

    ruleset_name: str
    total_rules: int
    findings_count: int
    error_count: int
    warning_count: int
    info_count: int


@dataclass
class AnalysisResult:
    """Complete Semgrep analysis result."""

    findings: List[Finding]
    ruleset_stats: List[RulesetStats]
    summary: Dict[str, Any]
    analysis_timestamp: datetime
    execution_time_seconds: float
    repository_path: str
    total_files_scanned: int


class SemgrepAnalyzer:
    """
    Semgrep analyzer for security and code quality analysis.

    Optimized for Python, TypeScript, JavaScript, and SvelteKit with:
    - Performance-focused rulesets to minimize false positives
    - Custom rules for modern web development patterns
    - Integration-ready SARIF output
    - Actionable security recommendations
    """

    def __init__(self, semgrep_binary_path: str = "semgrep"):
        """
        Initialize Semgrep analyzer.

        Args:
            semgrep_binary_path: Path to Semgrep binary (default: assumes in PATH)
        """
        self.semgrep_binary_path = semgrep_binary_path

        # Language-specific rulesets optimized for accuracy
        self.default_rulesets = {
            "python": ["p/python", "p/flask", "p/django", "p/security-audit"],
            "typescript": ["p/typescript", "p/react", "p/javascript", "p/nodejs"],
            "javascript": ["p/javascript", "p/react", "p/nodejs", "p/express"],
            "svelte": [
                "p/javascript",
                "p/typescript",
                "p/react",  # Some patterns are similar
            ],
        }

        # Custom rules for SvelteKit and modern patterns
        self.custom_rules_dir = Path(__file__).parent / "semgrep_rules"

        # Verify Semgrep installation
        self._verify_semgrep_installation()
        self._setup_custom_rules()

    def _verify_semgrep_installation(self):
        """Verify Semgrep is installed and accessible."""
        try:
            result = subprocess.run(
                [self.semgrep_binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Semgrep not accessible: {result.stderr}")

            logger.info(f"Semgrep version: {result.stdout.strip()}")

        except FileNotFoundError:
            raise RuntimeError(
                f"Semgrep not found at {self.semgrep_binary_path}. "
                "Install with: pip install semgrep"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Semgrep installation check timed out")

    def _setup_custom_rules(self):
        """Set up custom Semgrep rules for SvelteKit and modern patterns."""
        try:
            self.custom_rules_dir.mkdir(exist_ok=True)

            # Create custom rules for SvelteKit
            sveltekit_rules = {
                "rules": [
                    {
                        "id": "sveltekit-missing-csrf-protection",
                        "message": "SvelteKit form action missing CSRF protection",
                        "severity": "WARNING",
                        "languages": ["typescript", "javascript"],
                        "pattern-either": [
                            {
                                "pattern": "export async function POST({ request }) { ... }"
                            },
                            {"pattern": "export const actions = { ... }"},
                        ],
                        "pattern-not-inside": {
                            "pattern-either": [
                                {"pattern": "... csrf.verify(...) ..."},
                                {"pattern": "... verifyCSRF(...) ..."},
                            ]
                        },
                        "metadata": {
                            "category": "security",
                            "technology": ["sveltekit"],
                            "cwe": "CWE-352: Cross-Site Request Forgery (CSRF)",
                        },
                    },
                    {
                        "id": "sveltekit-unvalidated-form-data",
                        "message": "Form data used without validation in SvelteKit action",
                        "severity": "ERROR",
                        "languages": ["typescript", "javascript"],
                        "pattern": "const data = await request.formData(); ... $DATA",
                        "metavariable-pattern": {
                            "metavariable": "$DATA",
                            "pattern-not": "... validate($DATA) ...",
                        },
                        "metadata": {
                            "category": "security",
                            "technology": ["sveltekit"],
                        },
                    },
                    {
                        "id": "typescript-any-usage",
                        "message": "Usage of 'any' type reduces type safety",
                        "severity": "WARNING",
                        "languages": ["typescript"],
                        "pattern-either": [{"pattern": ": any"}, {"pattern": "as any"}],
                        "metadata": {
                            "category": "best-practices",
                            "technology": ["typescript"],
                        },
                    },
                    {
                        "id": "console-log-in-production",
                        "message": "Console.log statements should be removed in production",
                        "severity": "INFO",
                        "languages": ["javascript", "typescript"],
                        "pattern-either": [
                            {"pattern": "console.log(...)"},
                            {"pattern": "console.debug(...)"},
                        ],
                        "metadata": {
                            "category": "maintainability",
                            "technology": ["javascript", "typescript"],
                        },
                    },
                ]
            }

            # Write custom rules file
            custom_rules_file = self.custom_rules_dir / "sveltekit-security.yaml"
            with open(custom_rules_file, "w") as f:
                yaml.dump(sveltekit_rules, f, default_flow_style=False)

            logger.info(f"Custom Semgrep rules created at {custom_rules_file}")

        except Exception as e:
            logger.warning(f"Could not set up custom rules: {e}")

    def analyze_repository(
        self,
        repo_path: str,
        rulesets: Optional[List[str]] = None,
        include_custom_rules: bool = True,
        max_target_bytes: int = 1000000,  # 1MB per file limit
        timeout_seconds: int = 300,
    ) -> AnalysisResult:
        """
        Analyze repository with Semgrep rules.

        Args:
            repo_path: Path to repository root
            rulesets: Custom rulesets to use (auto-detected if None)
            include_custom_rules: Whether to include custom SvelteKit rules
            max_target_bytes: Maximum file size to analyze
            timeout_seconds: Analysis timeout

        Returns:
            Complete analysis result with findings and statistics
        """
        start_time = datetime.now()

        try:
            repo_path = Path(repo_path).resolve()
            if not repo_path.exists():
                raise ValueError(f"Repository path does not exist: {repo_path}")

            logger.info(f"Starting Semgrep analysis of {repo_path}")

            # Auto-detect languages and select appropriate rulesets
            if rulesets is None:
                rulesets = self._detect_and_select_rulesets(repo_path)

            # Build Semgrep command
            cmd = [
                self.semgrep_binary_path,
                "--json",
                "--no-git-ignore",  # We'll handle exclusions manually
                f"--max-target-bytes={max_target_bytes}",
                "--timeout",
                str(timeout_seconds),
                "--disable-version-check",
            ]

            # Add rulesets
            for ruleset in rulesets:
                cmd.extend(["--config", ruleset])

            # Add custom rules if requested
            if include_custom_rules and self.custom_rules_dir.exists():
                custom_rule_files = list(self.custom_rules_dir.glob("*.yaml"))
                for rule_file in custom_rule_files:
                    cmd.extend(["--config", str(rule_file)])

            # Add exclusions for performance
            exclusions = [
                "node_modules",
                ".git",
                "__pycache__",
                ".pytest_cache",
                "dist",
                "build",
                ".svelte-kit",
                "coverage",
                ".nyc_output",
                "*.min.js",
                "*.bundle.js",
                "*.d.ts",
            ]

            for exclusion in exclusions:
                cmd.extend(["--exclude", exclusion])

            # Add target directory
            cmd.append(str(repo_path))

            # Execute Semgrep
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds + 30,  # Extra buffer
                cwd=repo_path,
            )

            # Semgrep returns non-zero when findings are found, which is expected
            if result.returncode not in [0, 1]:
                raise RuntimeError(f"Semgrep analysis failed: {result.stderr}")

            # Parse JSON output
            if result.stdout.strip():
                semgrep_data = json.loads(result.stdout)
            else:
                semgrep_data = {"results": []}

            # Process results
            analysis_result = self._process_semgrep_output(
                semgrep_data, repo_path, rulesets, start_time
            )

            execution_time = (datetime.now() - start_time).total_seconds()
            analysis_result.execution_time_seconds = execution_time

            logger.info(
                f"Semgrep analysis completed in {execution_time:.2f}s: "
                f"{len(analysis_result.findings)} findings across "
                f"{analysis_result.total_files_scanned} files"
            )

            return analysis_result

        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Semgrep analysis timed out after {timeout_seconds} seconds"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Semgrep output: {result.stdout}")
            raise RuntimeError(f"Failed to parse Semgrep output: {e}")
        except Exception as e:
            logger.error(f"Semgrep analysis error: {str(e)}")
            raise

    def analyze_files(
        self,
        file_paths: List[str],
        rulesets: Optional[List[str]] = None,
        base_path: Optional[str] = None,
    ) -> AnalysisResult:
        """
        Analyze specific files with Semgrep.

        Args:
            file_paths: List of file paths to analyze
            rulesets: Rulesets to use
            base_path: Base path for relative file paths

        Returns:
            Analysis result for specified files
        """
        try:
            # Create temporary directory with files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Copy files to temp directory
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

                    # Copy file
                    import shutil

                    shutil.copy2(source_path, dest_path)

                # Analyze temp directory
                return self.analyze_repository(
                    str(temp_path), rulesets=rulesets, include_custom_rules=True
                )

        except Exception as e:
            logger.error(f"File analysis error: {str(e)}")
            raise

    def _detect_and_select_rulesets(self, repo_path: Path) -> List[str]:
        """Auto-detect languages and select appropriate rulesets."""
        try:
            detected_languages = set()

            # Sample files to detect languages
            for ext in [".py", ".ts", ".js", ".svelte"]:
                if list(repo_path.rglob(f"*{ext}")):
                    if ext == ".py":
                        detected_languages.add("python")
                    elif ext == ".ts":
                        detected_languages.add("typescript")
                    elif ext == ".js":
                        detected_languages.add("javascript")
                    elif ext == ".svelte":
                        detected_languages.add("svelte")

            # Select rulesets based on detected languages
            selected_rulesets = []
            for lang in detected_languages:
                if lang in self.default_rulesets:
                    selected_rulesets.extend(self.default_rulesets[lang])

            # Remove duplicates while preserving order
            unique_rulesets = []
            seen = set()
            for ruleset in selected_rulesets:
                if ruleset not in seen:
                    unique_rulesets.append(ruleset)
                    seen.add(ruleset)

            # Always include generic security rules
            if "p/security-audit" not in unique_rulesets:
                unique_rulesets.append("p/security-audit")

            logger.info(f"Detected languages: {detected_languages}")
            logger.info(f"Selected rulesets: {unique_rulesets}")

            return unique_rulesets

        except Exception as e:
            logger.warning(f"Language detection failed: {e}, using default rulesets")
            return ["p/security-audit", "p/javascript", "p/python"]

    def _process_semgrep_output(
        self,
        semgrep_data: Dict[str, Any],
        repo_path: Path,
        rulesets: List[str],
        start_time: datetime,
    ) -> AnalysisResult:
        """Process Semgrep JSON output into structured result."""
        try:
            findings = []
            scanned_files = set()

            # Process results
            for result in semgrep_data.get("results", []):
                try:
                    # Extract finding details
                    severity = SeverityLevel(result["extra"]["severity"])

                    # Determine category from metadata
                    metadata = result["extra"].get("metadata", {})
                    category_str = metadata.get("category", "security")

                    try:
                        category = FindingCategory(category_str)
                    except ValueError:
                        category = FindingCategory.SECURITY  # Default

                    # Extract location info
                    start_pos = result["start"]
                    end_pos = result["end"]

                    # Get code snippet
                    lines = result.get("extra", {}).get("lines", "")

                    # Create finding
                    finding = Finding(
                        rule_id=result["check_id"],
                        severity=severity,
                        category=category,
                        message=result["extra"]["message"],
                        file_path=result["path"],
                        start_line=start_pos["line"],
                        end_line=end_pos["line"],
                        start_col=start_pos["col"],
                        end_col=end_pos["col"],
                        code_snippet=lines,
                        fix_suggestion=result["extra"].get("fix", None),
                    )

                    findings.append(finding)
                    scanned_files.add(result["path"])

                except Exception as e:
                    logger.warning(f"Error processing finding: {e}")
                    continue

            # Calculate statistics
            ruleset_stats = self._calculate_ruleset_stats(findings, rulesets)

            # Create summary
            summary = {
                "total_findings": len(findings),
                "by_severity": {
                    "ERROR": len(
                        [f for f in findings if f.severity == SeverityLevel.ERROR]
                    ),
                    "WARNING": len(
                        [f for f in findings if f.severity == SeverityLevel.WARNING]
                    ),
                    "INFO": len(
                        [f for f in findings if f.severity == SeverityLevel.INFO]
                    ),
                },
                "by_category": {
                    category.value: len([f for f in findings if f.category == category])
                    for category in FindingCategory
                },
                "unique_rules_triggered": len(set(f.rule_id for f in findings)),
                "files_with_issues": len(set(f.file_path for f in findings)),
                "rulesets_used": rulesets,
            }

            return AnalysisResult(
                findings=findings,
                ruleset_stats=ruleset_stats,
                summary=summary,
                analysis_timestamp=start_time,
                execution_time_seconds=0,  # Will be set by caller
                repository_path=str(repo_path),
                total_files_scanned=len(scanned_files),
            )

        except Exception as e:
            logger.error(f"Error processing Semgrep output: {str(e)}")
            raise

    def _calculate_ruleset_stats(
        self, findings: List[Finding], rulesets: List[str]
    ) -> List[RulesetStats]:
        """Calculate statistics for each ruleset."""
        try:
            stats = []

            for ruleset in rulesets:
                # For simplicity, we'll aggregate all findings
                # In a more sophisticated implementation, we'd track which
                # rules belong to which rulesets

                ruleset_findings = findings  # Simplified

                stat = RulesetStats(
                    ruleset_name=ruleset,
                    total_rules=0,  # Would need to query Semgrep for this
                    findings_count=len(ruleset_findings),
                    error_count=len(
                        [
                            f
                            for f in ruleset_findings
                            if f.severity == SeverityLevel.ERROR
                        ]
                    ),
                    warning_count=len(
                        [
                            f
                            for f in ruleset_findings
                            if f.severity == SeverityLevel.WARNING
                        ]
                    ),
                    info_count=len(
                        [
                            f
                            for f in ruleset_findings
                            if f.severity == SeverityLevel.INFO
                        ]
                    ),
                )

                stats.append(stat)

            return stats

        except Exception as e:
            logger.error(f"Error calculating ruleset stats: {e}")
            return []

    def get_security_insights(self, analysis_result: AnalysisResult) -> Dict[str, Any]:
        """
        Extract security-focused insights from analysis.

        Args:
            analysis_result: Semgrep analysis result

        Returns:
            Dictionary with security insights and recommendations
        """
        try:
            insights = {
                "security_score": 0,
                "critical_issues": [],
                "vulnerability_categories": {},
                "risk_assessment": "LOW",
                "remediation_priority": [],
                "compliance_notes": [],
            }

            if not analysis_result.findings:
                insights["security_score"] = 100
                insights["risk_assessment"] = "MINIMAL"
                return insights

            # Calculate security score (0-100)
            security_score = 100
            error_count = analysis_result.summary["by_severity"]["ERROR"]
            warning_count = analysis_result.summary["by_severity"]["WARNING"]

            # Penalties for findings
            security_score -= error_count * 10  # 10 points per error
            security_score -= warning_count * 3  # 3 points per warning

            insights["security_score"] = max(0, security_score)

            # Risk assessment
            if error_count > 5 or security_score < 50:
                insights["risk_assessment"] = "HIGH"
            elif error_count > 0 or warning_count > 10 or security_score < 80:
                insights["risk_assessment"] = "MEDIUM"
            else:
                insights["risk_assessment"] = "LOW"

            # Identify critical issues (ERROR severity)
            critical_findings = [
                f for f in analysis_result.findings if f.severity == SeverityLevel.ERROR
            ]

            insights["critical_issues"] = [
                {
                    "rule_id": f.rule_id,
                    "message": f.message,
                    "file": f.file_path,
                    "line": f.start_line,
                }
                for f in critical_findings[:10]  # Top 10 critical issues
            ]

            # Categorize vulnerabilities
            category_counts = {}
            for finding in analysis_result.findings:
                if finding.category not in category_counts:
                    category_counts[finding.category] = 0
                category_counts[finding.category] += 1

            insights["vulnerability_categories"] = {
                category.value: count for category, count in category_counts.items()
            }

            # Prioritize remediation
            priority_rules = []
            rule_counts = {}

            for finding in analysis_result.findings:
                if finding.rule_id not in rule_counts:
                    rule_counts[finding.rule_id] = {
                        "count": 0,
                        "severity": finding.severity,
                        "message": finding.message,
                    }
                rule_counts[finding.rule_id]["count"] += 1

            # Sort by severity and frequency
            for rule_id, info in rule_counts.items():
                priority_score = info["count"]
                if info["severity"] == SeverityLevel.ERROR:
                    priority_score *= 10
                elif info["severity"] == SeverityLevel.WARNING:
                    priority_score *= 3

                priority_rules.append(
                    {
                        "rule_id": rule_id,
                        "message": info["message"],
                        "count": info["count"],
                        "severity": info["severity"].value,
                        "priority_score": priority_score,
                    }
                )

            priority_rules.sort(key=lambda x: x["priority_score"], reverse=True)
            insights["remediation_priority"] = priority_rules[:5]

            return insights

        except Exception as e:
            logger.error(f"Error generating security insights: {str(e)}")
            return {"error": str(e)}

    def export_sarif(self, analysis_result: AnalysisResult) -> str:
        """Export analysis result as SARIF format for CI/CD integration."""
        try:
            sarif_output = {
                "version": "2.1.0",
                "$schema": "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0.json",
                "runs": [
                    {
                        "tool": {
                            "driver": {
                                "name": "semgrep",
                                "version": "1.0.0",
                                "informationUri": "https://semgrep.dev/",
                            }
                        },
                        "results": [],
                    }
                ],
            }

            # Convert findings to SARIF format
            for finding in analysis_result.findings:
                sarif_result = {
                    "ruleId": finding.rule_id,
                    "message": {"text": finding.message},
                    "level": finding.severity.value.lower(),
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": finding.file_path},
                                "region": {
                                    "startLine": finding.start_line,
                                    "endLine": finding.end_line,
                                    "startColumn": finding.start_col,
                                    "endColumn": finding.end_col,
                                },
                            }
                        }
                    ],
                }

                if finding.fix_suggestion:
                    sarif_result["fixes"] = [
                        {
                            "description": {"text": "Suggested fix"},
                            "artifactChanges": [
                                {
                                    "artifactLocation": {"uri": finding.file_path},
                                    "replacements": [
                                        {
                                            "deletedRegion": {
                                                "startLine": finding.start_line,
                                                "endLine": finding.end_line,
                                            },
                                            "insertedContent": {
                                                "text": finding.fix_suggestion
                                            },
                                        }
                                    ],
                                }
                            ],
                        }
                    ]

                sarif_output["runs"][0]["results"].append(sarif_result)

            return json.dumps(sarif_output, indent=2)

        except Exception as e:
            logger.error(f"Error exporting SARIF: {str(e)}")
            raise


# Convenience functions for integration
def analyze_repository_security(repo_path: str) -> Dict[str, Any]:
    """Quick security analysis of repository."""
    analyzer = SemgrepAnalyzer()
    result = analyzer.analyze_repository(repo_path)
    insights = analyzer.get_security_insights(result)

    return {
        "security_score": insights["security_score"],
        "risk_assessment": insights["risk_assessment"],
        "total_findings": result.summary["total_findings"],
        "critical_issues": len(insights["critical_issues"]),
        "execution_time": result.execution_time_seconds,
        "top_issues": insights["remediation_priority"][:3],
    }


def get_vulnerability_summary(repo_path: str) -> Dict[str, Any]:
    """Get vulnerability summary for dashboard."""
    analyzer = SemgrepAnalyzer()
    result = analyzer.analyze_repository(repo_path)

    return {
        "total_vulnerabilities": result.summary["total_findings"],
        "by_severity": result.summary["by_severity"],
        "by_category": result.summary["by_category"],
        "files_affected": result.summary["files_with_issues"],
        "analysis_time": result.execution_time_seconds,
    }

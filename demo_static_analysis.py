#!/usr/bin/env python3
"""
Static Analysis Pipeline Demo

Demonstrates the SCC + Semgrep pipeline implementation without full dependencies.
Shows the data structures, processing logic, and AI-ready outputs.
"""

import json
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Any, Optional


# Minimal re-implementation for demo
class SeverityLevel(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class FindingCategory(Enum):
    SECURITY = "security"
    CORRECTNESS = "correctness"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"


@dataclass
class CodeMetrics:
    language: str
    files: int
    lines: int
    blanks: int
    comments: int
    complexity: int
    bytes: int


@dataclass
class Finding:
    rule_id: str
    severity: SeverityLevel
    category: FindingCategory
    message: str
    file_path: str
    start_line: int
    end_line: int
    code_snippet: str


@dataclass
class UnifiedInsights:
    code_quality_score: int
    security_score: int
    maintainability_score: int
    technical_debt_indicators: List[str]
    priority_recommendations: List[Dict[str, Any]]
    ai_model_context: Dict[str, Any]
    risk_profile: str


def demo_scc_analysis():
    """Demo SCC analysis with sample data."""
    print("🔍 SCC Code Metrics Analysis Demo")
    print("=" * 50)
    
    # Sample SCC metrics (would come from actual SCC analysis)
    scc_data = {
        "Languages": [
            {
                "Name": "Python",
                "Count": 15,
                "Lines": 2500,
                "Blank": 300,
                "Comment": 400,
                "Complexity": 125,
                "Bytes": 75000
            },
            {
                "Name": "TypeScript", 
                "Count": 8,
                "Lines": 1200,
                "Blank": 150,
                "Comment": 180,
                "Complexity": 60,
                "Bytes": 35000
            },
            {
                "Name": "Svelte",
                "Count": 5,
                "Lines": 800,
                "Blank": 80,
                "Comment": 100,
                "Complexity": 40,
                "Bytes": 22000
            }
        ]
    }
    
    # Process SCC data
    language_breakdown = []
    for lang_data in scc_data["Languages"]:
        metrics = CodeMetrics(
            language=lang_data["Name"],
            files=lang_data["Count"],
            lines=lang_data["Lines"],
            blanks=lang_data["Blank"],
            comments=lang_data["Comment"],
            complexity=lang_data["Complexity"],
            bytes=lang_data["Bytes"]
        )
        language_breakdown.append(metrics)
    
    # Calculate totals
    total_metrics = CodeMetrics(
        language="Total",
        files=sum(lang.files for lang in language_breakdown),
        lines=sum(lang.lines for lang in language_breakdown),
        blanks=sum(lang.blanks for lang in language_breakdown),
        comments=sum(lang.comments for lang in language_breakdown),
        complexity=sum(lang.complexity for lang in language_breakdown),
        bytes=sum(lang.bytes for lang in language_breakdown)
    )
    
    print(f"📊 Total Files: {total_metrics.files}")
    print(f"📏 Total Lines: {total_metrics.lines}")
    print(f"🔄 Total Complexity: {total_metrics.complexity}")
    print(f"📝 Comment Ratio: {(total_metrics.comments / total_metrics.lines * 100):.1f}%")
    print(f"🧠 Complexity per Line: {(total_metrics.complexity / total_metrics.lines):.3f}")
    
    print("\n📋 Language Breakdown:")
    for lang in language_breakdown:
        percentage = (lang.lines / total_metrics.lines) * 100
        print(f"  {lang.language}: {lang.lines} lines ({percentage:.1f}%)")
    
    return language_breakdown, total_metrics


def demo_semgrep_analysis():
    """Demo Semgrep analysis with sample findings."""
    print("\n🔒 Semgrep Security Analysis Demo")
    print("=" * 50)
    
    # Sample Semgrep findings (would come from actual Semgrep analysis)
    sample_findings = [
        {
            "rule_id": "python.django.security.injection.sql-injection-raw-query",
            "severity": "ERROR",
            "category": "security",
            "message": "Potential SQL injection vulnerability",
            "file_path": "app/models.py",
            "start_line": 45,
            "end_line": 45,
            "code_snippet": "cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")"
        },
        {
            "rule_id": "typescript.react.security.audit.react-dangerouslysetinnerhtml",
            "severity": "WARNING", 
            "category": "security",
            "message": "Dangerous use of dangerouslySetInnerHTML",
            "file_path": "src/components/Content.tsx",
            "start_line": 23,
            "end_line": 23,
            "code_snippet": "<div dangerouslySetInnerHTML={{__html: userContent}} />"
        },
        {
            "rule_id": "javascript.express.security.audit.express-fileupload-no-size-limit",
            "severity": "WARNING",
            "category": "security", 
            "message": "File upload without size limit",
            "file_path": "server/upload.js",
            "start_line": 12,
            "end_line": 12,
            "code_snippet": "app.use(fileUpload());"
        },
        {
            "rule_id": "python.lang.correctness.useless-comparison",
            "severity": "INFO",
            "category": "correctness",
            "message": "Useless comparison, result is always False",
            "file_path": "utils/helpers.py", 
            "start_line": 78,
            "end_line": 78,
            "code_snippet": "if x < x:"
        },
        {
            "rule_id": "typescript.lang.best-practice.no-any",
            "severity": "INFO",
            "category": "maintainability",
            "message": "Use of 'any' type reduces type safety",
            "file_path": "src/types/api.ts",
            "start_line": 15,
            "end_line": 15,
            "code_snippet": "data: any"
        }
    ]
    
    # Process findings
    findings = []
    for finding_data in sample_findings:
        finding = Finding(
            rule_id=finding_data["rule_id"],
            severity=SeverityLevel(finding_data["severity"]),
            category=FindingCategory(finding_data["category"]),
            message=finding_data["message"],
            file_path=finding_data["file_path"],
            start_line=finding_data["start_line"],
            end_line=finding_data["end_line"],
            code_snippet=finding_data["code_snippet"]
        )
        findings.append(finding)
    
    # Calculate summary statistics
    summary = {
        "total_findings": len(findings),
        "by_severity": {
            "ERROR": len([f for f in findings if f.severity == SeverityLevel.ERROR]),
            "WARNING": len([f for f in findings if f.severity == SeverityLevel.WARNING]),
            "INFO": len([f for f in findings if f.severity == SeverityLevel.INFO])
        },
        "by_category": {}
    }
    
    for category in FindingCategory:
        summary["by_category"][category.value] = len([
            f for f in findings if f.category == category
        ])
    
    print(f"🚨 Total Findings: {summary['total_findings']}")
    print(f"❌ Critical (ERROR): {summary['by_severity']['ERROR']}")
    print(f"⚠️  Warning: {summary['by_severity']['WARNING']}")
    print(f"ℹ️  Info: {summary['by_severity']['INFO']}")
    
    print("\n📂 Findings by Category:")
    for category, count in summary["by_category"].items():
        if count > 0:
            print(f"  {category}: {count}")
    
    print("\n🔍 Sample Critical Issues:")
    critical_findings = [f for f in findings if f.severity == SeverityLevel.ERROR]
    for finding in critical_findings[:3]:
        print(f"  • {finding.rule_id}")
        print(f"    File: {finding.file_path}:{finding.start_line}")
        print(f"    Issue: {finding.message}")
    
    return findings, summary


def generate_unified_insights(language_breakdown, total_metrics, findings, summary):
    """Generate unified insights combining SCC and Semgrep analysis."""
    print("\n🧠 AI-Ready Unified Insights")
    print("=" * 50)
    
    # Calculate code quality score
    code_quality_score = 100
    
    # Penalize based on complexity
    if total_metrics.lines > 0:
        complexity_ratio = total_metrics.complexity / total_metrics.lines
        if complexity_ratio > 0.1:  # High complexity threshold
            code_quality_score -= min(30, int((complexity_ratio - 0.1) * 300))
    
    # Penalize low comment ratio
    if total_metrics.lines > 0:
        comment_ratio = total_metrics.comments / total_metrics.lines
        if comment_ratio < 0.1:  # Low comment threshold
            code_quality_score -= min(20, int((0.1 - comment_ratio) * 200))
    
    code_quality_score = max(0, code_quality_score)
    
    # Calculate security score
    security_score = 100
    error_count = summary["by_severity"]["ERROR"] 
    warning_count = summary["by_severity"]["WARNING"]
    
    security_score -= error_count * 15  # 15 points per critical issue
    security_score -= warning_count * 5   # 5 points per warning
    security_score = max(0, security_score)
    
    # Calculate maintainability score (simplified)
    maintainability_score = code_quality_score
    
    # Identify technical debt
    technical_debt = []
    
    if total_metrics.lines > 0:
        complexity_per_line = total_metrics.complexity / total_metrics.lines
        if complexity_per_line > 0.08:
            technical_debt.append(f"High complexity ratio: {complexity_per_line:.3f}")
    
    if total_metrics.lines > 0:
        comment_ratio = total_metrics.comments / total_metrics.lines
        if comment_ratio < 0.1:
            technical_debt.append(f"Low documentation: {comment_ratio:.1%} comments")
    
    if error_count > 0:
        technical_debt.append(f"{error_count} critical security issues")
    
    if warning_count > 10:
        technical_debt.append(f"{warning_count} security warnings need attention")
    
    # Generate priority recommendations
    recommendations = []
    
    if error_count > 0:
        recommendations.append({
            "priority": "CRITICAL",
            "category": "security",
            "title": "Fix Critical Security Vulnerabilities",
            "description": f"Address {error_count} critical security issues immediately",
            "impact": "HIGH",
            "effort": "MEDIUM"
        })
    
    if code_quality_score < 70:
        recommendations.append({
            "priority": "HIGH",
            "category": "quality",
            "title": "Improve Code Quality",
            "description": f"Code quality score is {code_quality_score}/100",
            "impact": "MEDIUM",
            "effort": "HIGH"
        })
    
    if warning_count > 5:
        recommendations.append({
            "priority": "MEDIUM",
            "category": "security",
            "title": "Address Security Warnings",
            "description": f"Review and fix {warning_count} security warnings",
            "impact": "MEDIUM", 
            "effort": "LOW"
        })
    
    # Determine risk profile
    if error_count > 5 or security_score < 30:
        risk_profile = "CRITICAL"
    elif error_count > 0 or security_score < 60 or code_quality_score < 40:
        risk_profile = "HIGH"
    elif security_score < 80 or code_quality_score < 70 or len(technical_debt) > 2:
        risk_profile = "MEDIUM"
    else:
        risk_profile = "LOW"
    
    # Create AI model context
    ai_context = {
        "codebase_summary": {
            "total_files": total_metrics.files,
            "total_lines": total_metrics.lines,
            "primary_languages": [lang.language for lang in language_breakdown],
            "complexity_score": total_metrics.complexity,
            "dominant_language": max(language_breakdown, key=lambda x: x.lines).language
        },
        "security_context": {
            "vulnerability_count": summary["total_findings"],
            "critical_vulnerabilities": summary["by_severity"]["ERROR"],
            "security_score": security_score,
            "risk_level": risk_profile,
            "vulnerability_categories": list(summary["by_category"].keys())
        },
        "quality_metrics": {
            "maintainability_score": maintainability_score,
            "comment_ratio": total_metrics.comments / max(total_metrics.lines, 1),
            "average_file_size": total_metrics.lines / max(total_metrics.files, 1),
            "complexity_per_line": total_metrics.complexity / max(total_metrics.lines, 1)
        },
        "project_characteristics": {
            "is_web_project": any(lang.language in ["TypeScript", "JavaScript", "Svelte"] 
                                for lang in language_breakdown),
            "is_python_project": any(lang.language == "Python" for lang in language_breakdown),
            "language_diversity": len(language_breakdown),
            "estimated_team_size": min(max(1, total_metrics.files // 100), 20)
        },
        "actionable_insights": {
            "immediate_actions": len([r for r in recommendations 
                                   if r.get("priority") in ["CRITICAL", "HIGH"]]),
            "technical_debt_level": len(technical_debt),
            "refactoring_priority": "HIGH" if code_quality_score < 60 else "MEDIUM" if code_quality_score < 80 else "LOW"
        }
    }
    
    insights = UnifiedInsights(
        code_quality_score=code_quality_score,
        security_score=security_score,
        maintainability_score=maintainability_score,
        technical_debt_indicators=technical_debt,
        priority_recommendations=recommendations,
        ai_model_context=ai_context,
        risk_profile=risk_profile
    )
    
    # Display results
    print(f"📊 Code Quality Score: {code_quality_score}/100")
    print(f"🔒 Security Score: {security_score}/100")
    print(f"🔧 Maintainability Score: {maintainability_score}/100")
    print(f"⚠️  Risk Profile: {risk_profile}")
    
    print(f"\n🔧 Technical Debt Indicators ({len(technical_debt)}):")
    for debt in technical_debt:
        print(f"  • {debt}")
    
    print(f"\n📋 Priority Recommendations ({len(recommendations)}):")
    for rec in recommendations:
        print(f"  • [{rec['priority']}] {rec['title']}")
        print(f"    {rec['description']}")
    
    print("\n🤖 AI Model Context Preview:")
    print(f"  • Project Type: {'Web' if ai_context['project_characteristics']['is_web_project'] else 'Backend'}")
    print(f"  • Dominant Language: {ai_context['codebase_summary']['dominant_language']}")
    print(f"  • Team Size Estimate: {ai_context['project_characteristics']['estimated_team_size']} developers")
    print(f"  • Immediate Actions Needed: {ai_context['actionable_insights']['immediate_actions']}")
    
    return insights


def export_results(insights):
    """Export results in various formats."""
    print("\n📤 Export Formats Demo")
    print("=" * 50)
    
    # JSON export for AI consumption
    ai_ready_data = {
        "analysis_timestamp": datetime.now().isoformat(),
        "quality_scores": {
            "code_quality": insights.code_quality_score,
            "security": insights.security_score,
            "maintainability": insights.maintainability_score
        },
        "risk_assessment": {
            "profile": insights.risk_profile,
            "technical_debt_count": len(insights.technical_debt_indicators),
            "priority_actions": len([r for r in insights.priority_recommendations 
                                   if r.get("priority") in ["CRITICAL", "HIGH"]])
        },
        "ai_context": insights.ai_model_context
    }
    
    print("📄 AI-Ready JSON Preview:")
    print(json.dumps(ai_ready_data, indent=2)[:500] + "...")
    
    # Dashboard summary
    dashboard_summary = {
        "overall_health": "HEALTHY" if insights.code_quality_score > 80 and insights.security_score > 80 else
                         "NEEDS_ATTENTION" if insights.code_quality_score > 60 and insights.security_score > 60 else
                         "CRITICAL",
        "quality_score": insights.code_quality_score,
        "security_score": insights.security_score,
        "risk_profile": insights.risk_profile,
        "top_priorities": insights.priority_recommendations[:3]
    }
    
    print(f"\n📊 Dashboard Summary:")
    print(f"  Overall Health: {dashboard_summary['overall_health']}")
    print(f"  Quality: {dashboard_summary['quality_score']}/100")
    print(f"  Security: {dashboard_summary['security_score']}/100")
    print(f"  Risk: {dashboard_summary['risk_profile']}")
    
    return ai_ready_data, dashboard_summary


def main():
    """Run the complete static analysis pipeline demo."""
    print("🚀 Static Analysis Pipeline Demo")
    print("Demonstrating SCC + Semgrep integration for AI model consumption")
    print("=" * 70)
    
    # Step 1: SCC Analysis
    language_breakdown, total_metrics = demo_scc_analysis()
    
    # Step 2: Semgrep Analysis
    findings, summary = demo_semgrep_analysis()
    
    # Step 3: Unified Insights
    insights = generate_unified_insights(language_breakdown, total_metrics, findings, summary)
    
    # Step 4: Export Results
    ai_data, dashboard_data = export_results(insights)
    
    print("\n" + "=" * 70)
    print("✅ Static Analysis Pipeline Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("  ✓ SCC code metrics analysis")
    print("  ✓ Semgrep security and quality findings")
    print("  ✓ Unified scoring and risk assessment")
    print("  ✓ AI-ready context generation")
    print("  ✓ Technical debt identification")
    print("  ✓ Priority recommendations")
    print("  ✓ Multiple export formats")
    
    print(f"\n📈 Pipeline Performance:")
    print(f"  • Analysis would run in parallel for optimal speed")
    print(f"  • Results optimized for AI model consumption")
    print(f"  • Integration-ready with SARIF and JSON outputs")
    print(f"  • Focused on Python, TypeScript, and SvelteKit projects")


if __name__ == "__main__":
    main()
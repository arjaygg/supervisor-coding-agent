#!/usr/bin/env python3
"""
Basic test for static analysis implementation without dependencies.
Tests core logic and data structures.
"""

import json
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch


def test_scc_analyzer_basic():
    """Test SCC analyzer basic functionality."""
    try:
        # Import the module
        sys.path.insert(0, '.')
        from supervisor_agent.analysis.scc_analyzer import (
            CodeMetrics, FileMetrics, AnalysisResult, SCCAnalyzer
        )
        
        # Test data structures
        metrics = CodeMetrics("Python", 10, 1000, 100, 200, 50, 25000)
        assert metrics.language == "Python"
        assert metrics.files == 10
        assert metrics.lines == 1000
        
        file_metrics = FileMetrics("test.py", "Python", 100, 10, 20, 5, 2500)
        assert file_metrics.filename == "test.py"
        assert file_metrics.language == "Python"
        
        print("✓ SCC data structures work correctly")
        
        # Test analyzer initialization (mocked)
        with patch.object(SCCAnalyzer, '_verify_scc_installation'):
            analyzer = SCCAnalyzer()
            assert analyzer.scc_binary_path == "scc"
            print("✓ SCC analyzer initialization works")
        
        # Test analysis result creation
        lang_breakdown = [metrics]
        result = AnalysisResult(
            total_metrics=metrics,
            language_breakdown=lang_breakdown,
            file_details=[file_metrics],
            repository_summary={"total_files": 10},
            analysis_timestamp=datetime.now(),
            execution_time_seconds=1.5
        )
        
        assert result.total_metrics.files == 10
        assert len(result.language_breakdown) == 1
        print("✓ SCC analysis result structure works")
        
        return True
        
    except Exception as e:
        print(f"✗ SCC analyzer test failed: {e}")
        return False


def test_semgrep_analyzer_basic():
    """Test Semgrep analyzer basic functionality."""
    try:
        from supervisor_agent.analysis.semgrep_analyzer import (
            Finding, SeverityLevel, FindingCategory, AnalysisResult, SemgrepAnalyzer
        )
        
        # Test data structures
        finding = Finding(
            rule_id="test-rule",
            severity=SeverityLevel.WARNING,
            category=FindingCategory.SECURITY,
            message="Test finding",
            file_path="test.py",
            start_line=10,
            end_line=10,
            start_col=5,
            end_col=20,
            code_snippet="test code"
        )
        
        assert finding.rule_id == "test-rule"
        assert finding.severity == SeverityLevel.WARNING
        assert finding.category == FindingCategory.SECURITY
        
        print("✓ Semgrep data structures work correctly")
        
        # Test analyzer initialization (mocked)
        with patch.object(SemgrepAnalyzer, '_verify_semgrep_installation'), \
             patch.object(SemgrepAnalyzer, '_setup_custom_rules'):
            analyzer = SemgrepAnalyzer()
            assert analyzer.semgrep_binary_path == "semgrep"
            print("✓ Semgrep analyzer initialization works")
        
        # Test analysis result
        result = AnalysisResult(
            findings=[finding],
            ruleset_stats=[],
            summary={
                "total_findings": 1,
                "by_severity": {"ERROR": 0, "WARNING": 1, "INFO": 0},
                "by_category": {"security": 1}
            },
            analysis_timestamp=datetime.now(),
            execution_time_seconds=2.0,
            repository_path="/test",
            total_files_scanned=5
        )
        
        assert len(result.findings) == 1
        assert result.summary["total_findings"] == 1
        print("✓ Semgrep analysis result structure works")
        
        return True
        
    except Exception as e:
        print(f"✗ Semgrep analyzer test failed: {e}")
        return False


def test_pipeline_basic():
    """Test static analysis pipeline basic functionality."""
    try:
        from supervisor_agent.analysis.static_analysis_pipeline import (
            StaticAnalysisPipeline, UnifiedInsights, PipelineMetrics, PipelineResult
        )
        from supervisor_agent.analysis.scc_analyzer import CodeMetrics, AnalysisResult as SCCResult
        from supervisor_agent.analysis.semgrep_analyzer import AnalysisResult as SemgrepResult
        
        # Test unified insights
        insights = UnifiedInsights(
            code_quality_score=85,
            security_score=90,
            maintainability_score=75,
            technical_debt_indicators=["High complexity files"],
            priority_recommendations=[{"priority": "HIGH", "title": "Test"}],
            ai_model_context={"total_files": 10},
            risk_profile="LOW"
        )
        
        assert insights.code_quality_score == 85
        assert insights.security_score == 90
        assert insights.risk_profile == "LOW"
        
        print("✓ Pipeline unified insights work correctly")
        
        # Test pipeline metrics
        metrics = PipelineMetrics(
            total_execution_time=5.0,
            scc_execution_time=2.0,
            semgrep_execution_time=3.0,
            parallel_efficiency=20.0,
            files_analyzed=10,
            total_findings=5,
            pipeline_timestamp=datetime.now()
        )
        
        assert metrics.total_execution_time == 5.0
        assert metrics.parallel_efficiency == 20.0
        
        print("✓ Pipeline metrics work correctly")
        
        # Test pipeline initialization (mocked)
        with patch('supervisor_agent.analysis.static_analysis_pipeline.SCCAnalyzer'), \
             patch('supervisor_agent.analysis.static_analysis_pipeline.SemgrepAnalyzer'):
            pipeline = StaticAnalysisPipeline()
            assert pipeline.max_workers == 2  # default
            print("✓ Pipeline initialization works")
        
        return True
        
    except Exception as e:
        print(f"✗ Pipeline test failed: {e}")
        return False


def test_convenience_functions():
    """Test convenience functions with mocking."""
    try:
        # Mock the pipeline class and its methods
        mock_result = Mock()
        mock_result.unified_insights.code_quality_score = 85
        mock_result.unified_insights.security_score = 90
        mock_result.unified_insights.risk_profile = "LOW"
        mock_result.scc_result.total_metrics.files = 50
        mock_result.semgrep_result.summary = {"total_findings": 3}
        mock_result.pipeline_metrics.total_execution_time = 10.5
        mock_result.unified_insights.priority_recommendations = [
            {"title": "Test recommendation"}
        ]
        mock_result.unified_insights.ai_model_context = {
            "codebase_summary": {"total_files": 50}
        }
        
        with patch('supervisor_agent.analysis.static_analysis_pipeline.StaticAnalysisPipeline') as mock_pipeline_class:
            mock_pipeline = Mock()
            mock_pipeline_class.return_value = mock_pipeline
            mock_pipeline.analyze_repository.return_value = mock_result
            
            # Test quick analysis
            from supervisor_agent.analysis.static_analysis_pipeline import quick_repository_analysis
            result = quick_repository_analysis("/test/path")
            
            assert result["quality_score"] == 85
            assert result["security_score"] == 90
            assert result["risk_profile"] == "LOW"
            
            print("✓ Quick repository analysis function works")
            
            # Test AI context
            from supervisor_agent.analysis.static_analysis_pipeline import get_ai_analysis_context
            context = get_ai_analysis_context("/test/path")
            
            assert "codebase_summary" in context
            
            print("✓ AI analysis context function works")
        
        return True
        
    except Exception as e:
        print(f"✗ Convenience functions test failed: {e}")
        return False


def test_json_export():
    """Test JSON export functionality."""
    try:
        from supervisor_agent.analysis.scc_analyzer import CodeMetrics
        from supervisor_agent.analysis.semgrep_analyzer import Finding, SeverityLevel, FindingCategory
        
        # Test code metrics JSON serialization
        metrics = CodeMetrics("Python", 10, 1000, 100, 200, 50, 25000)
        from dataclasses import asdict
        metrics_dict = asdict(metrics)
        
        json_str = json.dumps(metrics_dict)
        parsed = json.loads(json_str)
        
        assert parsed["language"] == "Python"
        assert parsed["files"] == 10
        
        print("✓ SCC metrics JSON export works")
        
        # Test finding JSON serialization
        finding = Finding(
            rule_id="test-rule",
            severity=SeverityLevel.WARNING,
            category=FindingCategory.SECURITY,
            message="Test finding",
            file_path="test.py",
            start_line=10,
            end_line=10,
            start_col=5,
            end_col=20,
            code_snippet="test code"
        )
        
        finding_dict = asdict(finding)
        # Convert enums to strings for JSON
        finding_dict["severity"] = finding.severity.value
        finding_dict["category"] = finding.category.value
        
        json_str = json.dumps(finding_dict)
        parsed = json.loads(json_str)
        
        assert parsed["rule_id"] == "test-rule"
        assert parsed["severity"] == "WARNING"
        
        print("✓ Semgrep finding JSON export works")
        
        return True
        
    except Exception as e:
        print(f"✗ JSON export test failed: {e}")
        return False


def main():
    """Run all basic tests."""
    print("Running basic static analysis tests...\n")
    
    tests = [
        test_scc_analyzer_basic,
        test_semgrep_analyzer_basic, 
        test_pipeline_basic,
        test_convenience_functions,
        test_json_export
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        if test():
            passed += 1
        
    print(f"\n" + "="*50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All static analysis tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
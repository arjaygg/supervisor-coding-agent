"""
Tests for Static Analysis Pipeline

Tests SCC, Semgrep, and unified pipeline functionality.
Follows TDD principles with comprehensive test coverage.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from supervisor_agent.analysis.scc_analyzer import (
    SCCAnalyzer, CodeMetrics, FileMetrics, AnalysisResult as SCCResult
)
from supervisor_agent.analysis.semgrep_analyzer import (
    SemgrepAnalyzer, Finding, SeverityLevel, FindingCategory, 
    AnalysisResult as SemgrepResult
)
from supervisor_agent.analysis.static_analysis_pipeline import (
    StaticAnalysisPipeline, PipelineResult, UnifiedInsights
)


class TestSCCAnalyzer:
    """Test SCC analyzer functionality."""
    
    @pytest.fixture
    def mock_scc_output(self):
        """Mock SCC JSON output."""
        return {
            "Languages": [
                {
                    "Name": "Python",
                    "Count": 10,
                    "Lines": 1000,
                    "Blank": 100,
                    "Comment": 200,
                    "Complexity": 50,
                    "Bytes": 25000
                },
                {
                    "Name": "TypeScript", 
                    "Count": 5,
                    "Lines": 500,
                    "Blank": 50,
                    "Comment": 75,
                    "Complexity": 25,
                    "Bytes": 12500
                }
            ],
            "Files": [
                {
                    "Filename": "test.py",
                    "Language": "Python",
                    "Lines": 100,
                    "Blank": 10,
                    "Comment": 20,
                    "Complexity": 5,
                    "Bytes": 2500
                }
            ]
        }
    
    @pytest.fixture
    def scc_analyzer(self):
        """Create SCC analyzer with mocked binary check."""
        with patch.object(SCCAnalyzer, '_verify_scc_installation'):
            return SCCAnalyzer()
    
    def test_scc_analyzer_initialization(self):
        """Test SCC analyzer initialization."""
        with patch.object(SCCAnalyzer, '_verify_scc_installation') as mock_verify:
            analyzer = SCCAnalyzer("custom_scc_path")
            assert analyzer.scc_binary_path == "custom_scc_path"
            mock_verify.assert_called_once()
    
    @patch('subprocess.run')
    def test_analyze_repository_success(self, mock_run, scc_analyzer, mock_scc_output):
        """Test successful repository analysis."""
        # Mock subprocess result
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_scc_output)
        mock_run.return_value = mock_result
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = scc_analyzer.analyze_repository(temp_dir)
            
            assert isinstance(result, SCCResult)
            assert result.total_metrics.files == 15
            assert result.total_metrics.lines == 1500
            assert len(result.language_breakdown) == 2
            assert len(result.file_details) == 1
    
    @patch('subprocess.run')
    def test_analyze_repository_failure(self, mock_run, scc_analyzer):
        """Test repository analysis failure handling."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "SCC error"
        mock_run.return_value = mock_result
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(RuntimeError, match="SCC analysis failed"):
                scc_analyzer.analyze_repository(temp_dir)
    
    def test_get_language_insights(self, scc_analyzer, mock_scc_output):
        """Test language insights generation."""
        # Create mock analysis result
        lang_breakdown = [
            CodeMetrics("Python", 10, 1000, 100, 200, 50, 25000),
            CodeMetrics("TypeScript", 5, 500, 50, 75, 25, 12500)
        ]
        
        total_metrics = CodeMetrics("Total", 15, 1500, 150, 275, 75, 37500)
        
        result = SCCResult(
            total_metrics=total_metrics,
            language_breakdown=lang_breakdown,
            file_details=[],
            repository_summary={},
            analysis_timestamp=datetime.now(),
            execution_time_seconds=1.0
        )
        
        insights = scc_analyzer.get_language_insights(result)
        
        assert insights["dominant_language"] == "Python"
        assert "maintainability_score" in insights
        assert "recommendations" in insights
        assert isinstance(insights["recommendations"], list)
    
    def test_maintainability_score_calculation(self, scc_analyzer):
        """Test maintainability score calculation logic."""
        # High complexity, low comments scenario
        lang_breakdown = [
            CodeMetrics("Python", 1, 100, 10, 5, 50, 2500)  # High complexity
        ]
        
        total_metrics = CodeMetrics("Total", 1, 100, 10, 5, 50, 2500)
        file_details = [
            FileMetrics("large_file.py", "Python", 600, 60, 30, 100, 15000)  # Large file
        ]
        
        result = SCCResult(
            total_metrics=total_metrics,
            language_breakdown=lang_breakdown,
            file_details=file_details,
            repository_summary={},
            analysis_timestamp=datetime.now(),
            execution_time_seconds=1.0
        )
        
        score = scc_analyzer._calculate_maintainability_score(result)
        assert 0 <= score <= 100
        assert score < 80  # Should be penalized for high complexity and large files


class TestSemgrepAnalyzer:
    """Test Semgrep analyzer functionality."""
    
    @pytest.fixture
    def mock_semgrep_output(self):
        """Mock Semgrep JSON output."""
        return {
            "results": [
                {
                    "check_id": "python.security.sql-injection",
                    "path": "app.py",
                    "start": {"line": 10, "col": 5},
                    "end": {"line": 10, "col": 20},
                    "extra": {
                        "severity": "ERROR",
                        "message": "SQL injection vulnerability",
                        "metadata": {"category": "security"},
                        "lines": "cursor.execute(query)"
                    }
                },
                {
                    "check_id": "typescript.correctness.no-any",
                    "path": "types.ts", 
                    "start": {"line": 5, "col": 10},
                    "end": {"line": 5, "col": 15},
                    "extra": {
                        "severity": "WARNING",
                        "message": "Usage of any type",
                        "metadata": {"category": "correctness"},
                        "lines": "param: any"
                    }
                }
            ]
        }
    
    @pytest.fixture 
    def semgrep_analyzer(self):
        """Create Semgrep analyzer with mocked checks."""
        with patch.object(SemgrepAnalyzer, '_verify_semgrep_installation'), \
             patch.object(SemgrepAnalyzer, '_setup_custom_rules'):
            return SemgrepAnalyzer()
    
    @patch('subprocess.run')
    def test_analyze_repository_success(self, mock_run, semgrep_analyzer, mock_semgrep_output):
        """Test successful repository analysis."""
        mock_result = Mock()
        mock_result.returncode = 1  # Semgrep returns 1 when findings exist
        mock_result.stdout = json.dumps(mock_semgrep_output)
        mock_run.return_value = mock_result
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = semgrep_analyzer.analyze_repository(temp_dir)
            
            assert isinstance(result, SemgrepResult)
            assert len(result.findings) == 2
            assert result.summary["total_findings"] == 2
            assert result.summary["by_severity"]["ERROR"] == 1
            assert result.summary["by_severity"]["WARNING"] == 1
    
    def test_get_security_insights(self, semgrep_analyzer):
        """Test security insights generation."""
        # Create mock findings
        findings = [
            Finding(
                rule_id="sql-injection",
                severity=SeverityLevel.ERROR,
                category=FindingCategory.SECURITY,
                message="SQL injection",
                file_path="app.py",
                start_line=10,
                end_line=10,
                start_col=5,
                end_col=20,
                code_snippet="cursor.execute(query)"
            ),
            Finding(
                rule_id="xss-vulnerability", 
                severity=SeverityLevel.WARNING,
                category=FindingCategory.SECURITY,
                message="XSS vulnerability",
                file_path="views.py",
                start_line=25,
                end_line=25,
                start_col=10,
                end_col=30,
                code_snippet="render_template_string(user_input)"
            )
        ]
        
        result = SemgrepResult(
            findings=findings,
            ruleset_stats=[],
            summary={
                "total_findings": 2,
                "by_severity": {"ERROR": 1, "WARNING": 1, "INFO": 0},
                "by_category": {"security": 2}
            },
            analysis_timestamp=datetime.now(),
            execution_time_seconds=5.0,
            repository_path="/test",
            total_files_scanned=10
        )
        
        insights = semgrep_analyzer.get_security_insights(result)
        
        assert insights["security_score"] < 100
        assert insights["risk_assessment"] in ["LOW", "MEDIUM", "HIGH"]
        assert len(insights["critical_issues"]) == 1  # One ERROR
        assert "remediation_priority" in insights
    
    def test_custom_rules_setup(self):
        """Test custom rules directory creation."""
        with patch.object(SemgrepAnalyzer, '_verify_semgrep_installation'), \
             patch('pathlib.Path.mkdir') as mock_mkdir, \
             patch('builtins.open', mock=Mock()) as mock_open:
            
            analyzer = SemgrepAnalyzer()
            mock_mkdir.assert_called()  # Rules directory should be created
    
    @patch('subprocess.run')  
    def test_analyze_repository_timeout(self, mock_run, semgrep_analyzer):
        """Test repository analysis timeout handling."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("semgrep", 300)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(RuntimeError, match="timed out"):
                semgrep_analyzer.analyze_repository(temp_dir)


class TestStaticAnalysisPipeline:
    """Test unified static analysis pipeline."""
    
    @pytest.fixture
    def mock_scc_result(self):
        """Mock SCC analysis result."""
        return SCCResult(
            total_metrics=CodeMetrics("Total", 20, 2000, 200, 300, 100, 50000),
            language_breakdown=[
                CodeMetrics("Python", 15, 1500, 150, 250, 75, 37500),
                CodeMetrics("TypeScript", 5, 500, 50, 50, 25, 12500)
            ],
            file_details=[],
            repository_summary={
                "path": "/test",
                "total_files": 20,
                "primary_languages": ["Python", "TypeScript"]
            },
            analysis_timestamp=datetime.now(),
            execution_time_seconds=2.0
        )
    
    @pytest.fixture
    def mock_semgrep_result(self):
        """Mock Semgrep analysis result."""
        return SemgrepResult(
            findings=[
                Finding(
                    rule_id="test-rule",
                    severity=SeverityLevel.WARNING, 
                    category=FindingCategory.SECURITY,
                    message="Test finding",
                    file_path="test.py",
                    start_line=1,
                    end_line=1,
                    start_col=1,
                    end_col=10,
                    code_snippet="test code"
                )
            ],
            ruleset_stats=[],
            summary={
                "total_findings": 1,
                "by_severity": {"ERROR": 0, "WARNING": 1, "INFO": 0},
                "by_category": {"security": 1}
            },
            analysis_timestamp=datetime.now(),
            execution_time_seconds=3.0,
            repository_path="/test",
            total_files_scanned=20
        )
    
    @pytest.fixture
    def pipeline(self):
        """Create pipeline with mocked analyzers."""
        with patch.object(SCCAnalyzer, '_verify_scc_installation'), \
             patch.object(SemgrepAnalyzer, '_verify_semgrep_installation'), \
             patch.object(SemgrepAnalyzer, '_setup_custom_rules'):
            return StaticAnalysisPipeline()
    
    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        with patch.object(SCCAnalyzer, '_verify_scc_installation'), \
             patch.object(SemgrepAnalyzer, '_verify_semgrep_installation'), \
             patch.object(SemgrepAnalyzer, '_setup_custom_rules'):
            
            pipeline = StaticAnalysisPipeline("custom_scc", "custom_semgrep", 4)
            assert pipeline.scc_analyzer.scc_binary_path == "custom_scc"
            assert pipeline.semgrep_analyzer.semgrep_binary_path == "custom_semgrep"
            assert pipeline.max_workers == 4
    
    def test_analyze_repository_sequential(self, pipeline, mock_scc_result, mock_semgrep_result):
        """Test sequential repository analysis."""
        with patch.object(pipeline, '_run_scc_analysis', return_value=mock_scc_result), \
             patch.object(pipeline, '_run_semgrep_analysis', return_value=mock_semgrep_result):
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = pipeline.analyze_repository(temp_dir, enable_parallel=False)
                
                assert isinstance(result, PipelineResult)
                assert result.scc_result == mock_scc_result
                assert result.semgrep_result == mock_semgrep_result
                assert isinstance(result.unified_insights, UnifiedInsights)
                assert result.pipeline_metrics.parallel_efficiency == 0.0  # No parallelism
    
    def test_analyze_repository_parallel(self, pipeline, mock_scc_result, mock_semgrep_result):
        """Test parallel repository analysis."""
        with patch.object(pipeline, '_run_parallel_analysis', 
                         return_value=(mock_scc_result, mock_semgrep_result)):
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = pipeline.analyze_repository(temp_dir, enable_parallel=True)
                
                assert isinstance(result, PipelineResult)
                assert result.pipeline_metrics.parallel_efficiency >= 0.0
    
    def test_unified_insights_generation(self, pipeline, mock_scc_result, mock_semgrep_result):
        """Test unified insights generation."""
        with patch.object(pipeline.scc_analyzer, 'get_language_insights',
                         return_value={"maintainability_score": 80, "dominant_language": "Python"}), \
             patch.object(pipeline.semgrep_analyzer, 'get_security_insights',
                         return_value={"security_score": 90, "risk_assessment": "LOW"}):
            
            insights = pipeline._generate_unified_insights(mock_scc_result, mock_semgrep_result)
            
            assert isinstance(insights, UnifiedInsights)
            assert 0 <= insights.code_quality_score <= 100
            assert 0 <= insights.security_score <= 100
            assert insights.risk_profile in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            assert isinstance(insights.technical_debt_indicators, list)
            assert isinstance(insights.priority_recommendations, list)
            assert isinstance(insights.ai_model_context, dict)
    
    def test_technical_debt_identification(self, pipeline, mock_scc_result, mock_semgrep_result):
        """Test technical debt identification."""
        # Add large file to mock result
        mock_scc_result.file_details = [
            FileMetrics("large_file.py", "Python", 800, 80, 40, 150, 20000)
        ]
        
        debt_indicators = pipeline._identify_technical_debt(mock_scc_result, mock_semgrep_result)
        
        assert isinstance(debt_indicators, list)
        assert any("files exceed 500 lines" in indicator for indicator in debt_indicators)
    
    def test_risk_profile_calculation(self, pipeline):
        """Test risk profile calculation logic."""
        # Test critical risk
        critical_risk = pipeline._calculate_risk_profile(50, 20, 50, 3, 15)
        assert critical_risk == "CRITICAL"
        
        # Test high risk
        high_risk = pipeline._calculate_risk_profile(80, 50, 80, 2, 3)
        assert high_risk == "HIGH"
        
        # Test medium risk  
        medium_risk = pipeline._calculate_risk_profile(70, 75, 55, 3, 0)
        assert medium_risk == "MEDIUM"
        
        # Test low risk
        low_risk = pipeline._calculate_risk_profile(90, 95, 85, 1, 0)
        assert low_risk == "LOW"
    
    def test_ai_model_context_creation(self, pipeline, mock_scc_result, mock_semgrep_result):
        """Test AI model context creation."""
        with patch.object(pipeline.scc_analyzer, 'get_language_insights',
                         return_value={"maintainability_score": 75, "dominant_language": "Python"}), \
             patch.object(pipeline.semgrep_analyzer, 'get_security_insights',
                         return_value={"security_score": 85, "risk_assessment": "LOW"}):
            
            context = pipeline._create_ai_model_context(
                mock_scc_result, mock_semgrep_result, {}, {}
            )
            
            assert "codebase_summary" in context
            assert "security_context" in context
            assert "quality_metrics" in context
            assert "project_characteristics" in context
            assert "actionable_insights" in context
            
            # Verify specific fields
            assert context["codebase_summary"]["total_files"] == 20
            assert context["security_context"]["vulnerability_count"] == 1
            assert "is_python_project" in context["project_characteristics"]
    
    def test_export_unified_json(self, pipeline, mock_scc_result, mock_semgrep_result):
        """Test unified JSON export."""
        with patch.object(pipeline, '_generate_unified_insights') as mock_insights:
            mock_insights.return_value = UnifiedInsights(
                code_quality_score=80,
                security_score=90,
                maintainability_score=75,
                technical_debt_indicators=[],
                priority_recommendations=[],
                ai_model_context={},
                risk_profile="LOW"
            )
            
            # Create mock pipeline result
            from supervisor_agent.analysis.static_analysis_pipeline import PipelineMetrics
            
            pipeline_metrics = PipelineMetrics(
                total_execution_time=5.0,
                scc_execution_time=2.0,
                semgrep_execution_time=3.0,
                parallel_efficiency=0.0,
                files_analyzed=20,
                total_findings=1,
                pipeline_timestamp=datetime.now()
            )
            
            result = PipelineResult(
                scc_result=mock_scc_result,
                semgrep_result=mock_semgrep_result,
                unified_insights=mock_insights.return_value,
                pipeline_metrics=pipeline_metrics,
                repository_path="/test",
                analysis_timestamp=datetime.now()
            )
            
            json_output = pipeline.export_unified_json(result)
            parsed = json.loads(json_output)
            
            assert "analysis_timestamp" in parsed
            assert "unified_insights" in parsed
            assert "scc_summary" in parsed
            assert "semgrep_summary" in parsed
            assert "ai_ready_context" in parsed
    
    def test_parallel_efficiency_calculation(self, pipeline):
        """Test parallel efficiency calculation."""
        # Test with parallel execution
        efficiency = pipeline._calculate_parallel_efficiency(3.0, 2.0, 2.5, True)
        assert efficiency > 0  # Should save time
        
        # Test without parallel execution
        efficiency_seq = pipeline._calculate_parallel_efficiency(5.0, 2.0, 3.0, False)
        assert efficiency_seq == 0.0  # No parallel benefit
        
        # Test edge case
        efficiency_zero = pipeline._calculate_parallel_efficiency(0.0, 0.0, 0.0, True)
        assert efficiency_zero == 0.0


class TestIntegrationFunctions:
    """Test convenience functions for integration."""
    
    @patch('supervisor_agent.analysis.static_analysis_pipeline.StaticAnalysisPipeline')
    def test_quick_repository_analysis(self, mock_pipeline_class):
        """Test quick repository analysis function."""
        # Mock pipeline and result
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
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
        
        mock_pipeline.analyze_repository.return_value = mock_result
        
        from supervisor_agent.analysis.static_analysis_pipeline import quick_repository_analysis
        
        result = quick_repository_analysis("/test/path")
        
        assert result["quality_score"] == 85
        assert result["security_score"] == 90
        assert result["risk_profile"] == "LOW"
        assert result["total_files"] == 50
        assert result["total_findings"] == 3
        assert result["execution_time"] == 10.5
        assert len(result["top_recommendations"]) == 1
    
    @patch('supervisor_agent.analysis.static_analysis_pipeline.StaticAnalysisPipeline')
    def test_get_ai_analysis_context(self, mock_pipeline_class):
        """Test AI analysis context function."""
        # Mock pipeline and result
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        mock_context = {
            "codebase_summary": {"total_files": 100},
            "security_context": {"vulnerability_count": 5},
            "quality_metrics": {"maintainability_score": 80}
        }
        
        mock_result = Mock()
        mock_result.unified_insights.ai_model_context = mock_context
        mock_pipeline.analyze_repository.return_value = mock_result
        
        from supervisor_agent.analysis.static_analysis_pipeline import get_ai_analysis_context
        
        result = get_ai_analysis_context("/test/path")
        
        assert result == mock_context
        assert "codebase_summary" in result
        assert "security_context" in result
        assert "quality_metrics" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
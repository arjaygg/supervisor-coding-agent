# supervisor_agent/tests/test_performance_monitoring.py
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from supervisor_agent.core.performance_optimizer import (
    OptimizationAction,
    OptimizationPlan,
    OptimizationTarget,
    OptimizationTechnique,
    PerformanceLevel,
    PerformanceMetric,
    PerformanceOptimizer,
)
from supervisor_agent.models.task import Task
from supervisor_agent.monitoring.bottleneck_detector import (
    BottleneckAnalysis,
    BottleneckDetector,
    BottleneckType,
    ComponentMetrics,
    ComponentType,
    OptimizationRecommendation,
    OptimizationStrategy,
)
from supervisor_agent.monitoring.real_time_monitor import (
    AlertSeverity,
    MetricType,
    PerformanceAlert,
    PerformanceMetric,
    RealTimeMonitor,
    SLARequirement,
    SLAStatus,
)


class TestRealTimeMonitor:
    """Test suite for RealTimeMonitor."""

    @pytest.fixture
    def monitor(self):
        """Create a RealTimeMonitor instance."""
        return RealTimeMonitor()

    @pytest.fixture
    def sample_metrics(self):
        """Create sample performance metrics."""
        return {
            "cpu_usage": 75.0,
            "memory_usage": 80.0,
            "response_time": 1500.0,
            "throughput": 150.0,
            "error_rate": 2.0,
            "queue_depth": 25,
        }

    def test_monitor_initialization(self, monitor):
        """Test monitor initialization with default SLAs."""
        assert len(monitor.sla_requirements) == 3
        assert "response_time_sla" in monitor.sla_requirements
        assert "availability_sla" in monitor.sla_requirements
        assert "throughput_sla" in monitor.sla_requirements

        assert monitor.monitoring_active is True
        assert len(monitor.alert_thresholds) == 5

    @pytest.mark.asyncio
    async def test_record_metric(self, monitor):
        """Test metric recording functionality."""
        monitor._record_metric(MetricType.CPU_USAGE, 85.0, "test_source")

        assert MetricType.CPU_USAGE in monitor.metrics_history
        assert len(monitor.metrics_history[MetricType.CPU_USAGE]) == 1

        metric = monitor.metrics_history[MetricType.CPU_USAGE][0]
        assert metric.value == 85.0
        assert metric.source == "test_source"

    @pytest.mark.asyncio
    async def test_monitor_workflow_execution(self, monitor):
        """Test workflow execution monitoring."""
        workflow_id = "test_workflow_001"

        result = await monitor.monitor_workflow_execution(workflow_id)

        assert result["workflow_id"] == workflow_id
        assert result["status"] == "running"
        assert "progress" in result
        assert "timing" in result
        assert "issues" in result

        # Test workflow status tracking
        assert workflow_id in monitor.workflow_statuses
        status = monitor.workflow_statuses[workflow_id]
        assert status.workflow_id == workflow_id

    @pytest.mark.asyncio
    async def test_detect_bottlenecks(self, monitor):
        """Test bottleneck detection."""
        # Simulate high CPU usage
        for i in range(5):
            monitor._record_metric(MetricType.CPU_USAGE, 90.0 + i)

        bottlenecks = await monitor.detect_bottlenecks({"workflow_id": "test"})

        assert len(bottlenecks) > 0
        cpu_bottleneck = next(
            (b for b in bottlenecks if b["type"] == "cpu_bottleneck"), None
        )
        assert cpu_bottleneck is not None
        assert cpu_bottleneck["severity"] in ["warning", "critical"]

    @pytest.mark.asyncio
    async def test_generate_performance_alerts(self, monitor):
        """Test performance alert generation."""
        # Create a test alert
        alert = PerformanceAlert(
            alert_id="test_alert_001",
            severity=AlertSeverity.CRITICAL,
            metric_type=MetricType.RESPONSE_TIME,
            message="High response time detected",
            threshold_value=3000.0,
            actual_value=4500.0,
        )
        monitor.active_alerts[alert.alert_id] = alert

        alerts = await monitor.generate_performance_alerts({})

        assert len(alerts) == 1
        generated_alert = alerts[0]
        assert generated_alert["alert_id"] == "test_alert_001"
        assert generated_alert["severity"] == "critical"
        assert generated_alert["metric"] == "response_time"

    @pytest.mark.asyncio
    async def test_sla_compliance_tracking(self, monitor):
        """Test SLA compliance tracking."""
        # Add some metrics that violate SLA
        for i in range(10):
            monitor._record_metric(
                MetricType.RESPONSE_TIME, 4000.0
            )  # Above 3s threshold

        compliance_report = await monitor.track_sla_compliance({})

        assert "overall_compliance" in compliance_report
        assert "sla_status" in compliance_report
        assert "violations" in compliance_report

        # Should detect response time SLA violation
        assert len(compliance_report["violations"]) > 0
        violation = compliance_report["violations"][0]
        assert violation["sla_name"] == "response_time_sla"

    @pytest.mark.asyncio
    async def test_check_sla_compliance(self, monitor):
        """Test individual SLA compliance checking."""
        sla_req = SLARequirement(
            name="test_sla",
            metric_type=MetricType.RESPONSE_TIME,
            threshold=3000.0,
            comparison="<",
            time_window=5,
            description="Test SLA",
        )

        # Add metrics within SLA
        for i in range(5):
            monitor._record_metric(MetricType.RESPONSE_TIME, 2000.0)

        result = await monitor._check_sla_compliance(sla_req)

        assert result["status"] == SLAStatus.COMPLIANT
        assert result["actual_value"] == 2000.0

        # Add metrics that violate SLA
        for i in range(5):
            monitor._record_metric(MetricType.RESPONSE_TIME, 5000.0)

        result = await monitor._check_sla_compliance(sla_req)

        assert result["status"] in [SLAStatus.VIOLATED, SLAStatus.AT_RISK]

    @pytest.mark.asyncio
    async def test_alert_acknowledgment(self, monitor):
        """Test alert acknowledgment functionality."""
        alert = PerformanceAlert(
            alert_id="ack_test_001",
            severity=AlertSeverity.WARNING,
            metric_type=MetricType.CPU_USAGE,
            message="Test alert",
            threshold_value=80.0,
            actual_value=85.0,
        )
        monitor.active_alerts[alert.alert_id] = alert

        # Test acknowledgment
        result = await monitor.acknowledge_alert("ack_test_001")
        assert result is True
        assert monitor.active_alerts["ack_test_001"].acknowledged is True

        # Test non-existent alert
        result = await monitor.acknowledge_alert("non_existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_performance_dashboard_data(self, monitor):
        """Test performance dashboard data generation."""
        # Add some sample metrics
        monitor._record_metric(MetricType.CPU_USAGE, 75.0)
        monitor._record_metric(MetricType.MEMORY_USAGE, 60.0)
        monitor._record_metric(MetricType.RESPONSE_TIME, 1200.0)

        dashboard_data = await monitor.get_performance_dashboard_data()

        assert "timestamp" in dashboard_data
        assert "system_health" in dashboard_data
        assert "current_metrics" in dashboard_data
        assert "active_alerts" in dashboard_data
        assert "bottlenecks" in dashboard_data
        assert "sla_compliance" in dashboard_data
        assert "workflow_status" in dashboard_data

        # Test system health calculation
        health = dashboard_data["system_health"]
        assert health in [
            "excellent",
            "good",
            "fair",
            "poor",
            "critical",
            "unknown",
        ]

    def test_metric_trend_calculation(self, monitor):
        """Test metric trend calculation."""
        # Add increasing trend
        for i in range(10):
            monitor._record_metric(MetricType.CPU_USAGE, 50.0 + i * 5)

        trend = monitor._calculate_metric_trend(MetricType.CPU_USAGE)
        assert trend == "increasing"

        # Add decreasing trend
        monitor.metrics_history[MetricType.MEMORY_USAGE].clear()
        for i in range(10):
            monitor._record_metric(MetricType.MEMORY_USAGE, 90.0 - i * 5)

        trend = monitor._calculate_metric_trend(MetricType.MEMORY_USAGE)
        assert trend == "decreasing"


class TestBottleneckDetector:
    """Test suite for BottleneckDetector."""

    @pytest.fixture
    def detector(self):
        """Create a BottleneckDetector instance."""
        return BottleneckDetector()

    @pytest.fixture
    def sample_pipeline(self):
        """Create a sample pipeline for testing."""
        return {
            "pipeline_id": "test_pipeline_001",
            "stages": [
                {
                    "name": "data_ingestion",
                    "type": "task_processor",
                    "execution_time": 2000.0,
                    "throughput": 100.0,
                    "dependencies": [],
                    "parallel_capacity": 2,
                    "current_load": 0.9,
                },
                {
                    "name": "data_processing",
                    "type": "task_processor",
                    "execution_time": 5000.0,
                    "throughput": 50.0,
                    "dependencies": ["data_ingestion"],
                    "parallel_capacity": 1,
                    "current_load": 0.95,
                },
                {
                    "name": "data_output",
                    "type": "task_processor",
                    "execution_time": 1000.0,
                    "throughput": 80.0,
                    "dependencies": ["data_processing"],
                    "parallel_capacity": 3,
                    "current_load": 0.4,
                },
            ],
        }

    @pytest.fixture
    def sample_component_metrics(self):
        """Create sample component metrics."""
        return {
            "api_gateway": {
                "type": "external_api",
                "response_times": [3200, 3500, 3800, 4100, 3400],  # Above 3000ms threshold
                "throughput": 800.0,
                "error_rate": 3.5,
                "cpu_usage": 85.0,
                "memory_usage": 78.0,
            },
            "database_pool": {
                "type": "database_connection",
                "response_times": [300, 350, 400, 450, 380],
                "throughput": 1200.0,
                "error_rate": 0.8,
                "cpu_usage": 45.0,
                "memory_usage": 92.0,
            },
            "worker_queue": {
                "type": "message_queue",
                "response_times": [50, 60, 70, 80, 65],
                "throughput": 2000.0,
                "error_rate": 0.1,
                "cpu_usage": 25.0,
                "memory_usage": 40.0,
                "queue_depth": 150,
            },
        }

    def test_detector_initialization(self, detector):
        """Test detector initialization."""
        assert len(detector.thresholds) == 6
        assert len(detector.analysis_rules) == 5
        assert detector.monitoring_active is True

    @pytest.mark.asyncio
    async def test_analyze_execution_pipeline(self, detector, sample_pipeline):
        """Test pipeline execution analysis."""
        analysis = await detector.analyze_execution_pipeline(sample_pipeline)

        assert analysis["pipeline_id"] == "test_pipeline_001"
        assert analysis["total_stages"] == 3
        assert "critical_path" in analysis
        assert "bottleneck_stages" in analysis
        assert "parallelization_opportunities" in analysis
        assert "resource_utilization" in analysis
        assert "performance_metrics" in analysis

        # Test bottleneck stage detection
        bottleneck_stages = analysis["bottleneck_stages"]
        assert len(bottleneck_stages) > 0

        # data_processing should be identified as bottleneck (95% utilization)
        processing_bottleneck = next(
            (b for b in bottleneck_stages if b["stage_name"] == "data_processing"),
            None,
        )
        assert processing_bottleneck is not None
        assert processing_bottleneck["severity"] == "high"

    @pytest.mark.asyncio
    async def test_identify_slow_components(self, detector, sample_component_metrics):
        """Test slow component identification."""
        slow_components = await detector.identify_slow_components(
            sample_component_metrics
        )

        assert len(slow_components) > 0

        # API gateway should be identified as slow (high response times, CPU usage)
        api_component = next(
            (c for c in slow_components if c["component_name"] == "api_gateway"),
            None,
        )
        assert api_component is not None
        assert len(api_component["issues"]) > 0

        # Check for high response time issue
        response_issue = next(
            (i for i in api_component["issues"] if i["type"] == "slow_response"),
            None,
        )
        assert response_issue is not None

        # Database should be identified for memory issues
        db_component = next(
            (c for c in slow_components if c["component_name"] == "database_pool"),
            None,
        )
        assert db_component is not None

        memory_issue = next(
            (i for i in db_component["issues"] if i["type"] == "high_memory_usage"),
            None,
        )
        assert memory_issue is not None

    @pytest.mark.asyncio
    async def test_suggest_optimization_strategies(self, detector):
        """Test optimization strategy suggestions."""
        bottlenecks = [
            {
                "type": "cpu_bottleneck",
                "component": "api_gateway",
                "severity": "warning",
                "description": "High CPU usage detected",
            },
            {
                "type": "memory_bottleneck",
                "component": "database_pool",
                "severity": "critical",
                "description": "Memory usage exceeding limits",
            },
            {
                "type": "queue_bottleneck",
                "component": "worker_queue",
                "severity": "warning",
                "description": "Queue depth increasing",
            },
        ]

        recommendations = await detector.suggest_optimization_strategies(bottlenecks)

        assert len(recommendations) > 0

        # Should have recommendations for each bottleneck type
        cpu_recommendations = [
            r for r in recommendations if "cpu" in r.description.lower()
        ]
        memory_recommendations = [
            r for r in recommendations if "memory" in r.description.lower()
        ]
        queue_recommendations = [
            r for r in recommendations if "queue" in r.description.lower()
        ]

        assert len(cpu_recommendations) > 0
        assert len(memory_recommendations) > 0
        assert len(queue_recommendations) > 0

        # Test recommendation priorities
        for rec in recommendations:
            assert 1 <= rec.priority <= 10
            assert rec.estimated_cost >= 0
            assert rec.implementation_effort in ["low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_parallelization_opportunities(self, detector, sample_pipeline):
        """Test parallelization opportunity identification."""
        analysis = await detector.analyze_execution_pipeline(sample_pipeline)
        opportunities = analysis["parallelization_opportunities"]

        # Should identify opportunities where stages can run in parallel
        if opportunities:
            for opp in opportunities:
                assert "level" in opp
                assert "stages" in opp
                assert "time_savings" in opp
                assert opp["time_savings"] > 0

    @pytest.mark.asyncio
    async def test_performance_score_calculation(self, detector):
        """Test performance score calculation."""
        metrics = ComponentMetrics(
            component_name="test_component",
            component_type=ComponentType.TASK_PROCESSOR,
            response_times=[1000, 1100, 1200],
            throughput=500.0,
            error_rate=1.0,
            cpu_usage=70.0,
            memory_usage=65.0,
        )

        score = detector._calculate_performance_score(metrics)

        assert 0 <= score <= 100

        # Test with poor performance metrics
        poor_metrics = ComponentMetrics(
            component_name="poor_component",
            component_type=ComponentType.TASK_PROCESSOR,
            response_times=[5000, 6000, 7000],
            throughput=10.0,
            error_rate=15.0,
            cpu_usage=95.0,
            memory_usage=98.0,
        )

        poor_score = detector._calculate_performance_score(poor_metrics)
        assert poor_score < score  # Poor metrics should have lower score

    @pytest.mark.asyncio
    async def test_optimization_report_generation(
        self, detector, sample_component_metrics
    ):
        """Test comprehensive optimization report generation."""
        # Update component metrics
        for name, metrics_data in sample_component_metrics.items():
            await detector.update_component_metrics(name, metrics_data)

        report = await detector.get_optimization_report()

        assert "timestamp" in report
        assert "summary" in report
        assert "slow_components" in report
        assert "optimization_recommendations" in report
        assert "performance_trends" in report
        assert "system_health_score" in report

        summary = report["summary"]
        assert summary["total_components_analyzed"] == 3
        assert summary["slow_components_detected"] >= 0
        assert summary["optimization_recommendations"] >= 0


class TestPerformanceOptimizer:
    """Test suite for PerformanceOptimizer."""

    @pytest.fixture
    def optimizer(self):
        """Create a PerformanceOptimizer instance."""
        return PerformanceOptimizer()

    @pytest.fixture
    def sample_metrics_data(self):
        """Create sample metrics data for analysis."""
        return {
            "response_time": 3500.0,  # Above 3000ms threshold
            "throughput": 80.0,
            "cpu_usage": 88.0,
            "memory_usage": 75.0,
            "error_rate": 3.5,
            "queue_depth": 45,
        }

    @pytest.fixture
    def sample_time_window(self):
        """Create sample time window for analysis."""
        now = datetime.now()
        return {
            "start": (now - timedelta(hours=24)).isoformat(),
            "end": now.isoformat(),
        }

    def test_optimizer_initialization(self, optimizer):
        """Test optimizer initialization."""
        assert len(optimizer.optimization_rules) == 5
        assert len(optimizer.performance_targets) == 6
        assert optimizer.learning_enabled is True

    @pytest.mark.asyncio
    async def test_analyze_performance_bottlenecks(
        self, optimizer, sample_metrics_data
    ):
        """Test performance bottleneck analysis."""
        bottlenecks = await optimizer.analyze_performance_bottlenecks(
            sample_metrics_data
        )

        # Should detect high CPU and response time bottlenecks
        assert len(bottlenecks) > 0

        cpu_bottleneck = next(
            (b for b in bottlenecks if b["type"] == "high_resource_usage"),
            None,
        )
        assert cpu_bottleneck is not None
        assert cpu_bottleneck["severity"] == "warning"

        response_bottleneck = next(
            (b for b in bottlenecks if b["type"] == "high_response_time"), None
        )
        assert response_bottleneck is not None

    @pytest.mark.asyncio
    async def test_generate_optimization_recommendations(
        self, optimizer, sample_metrics_data
    ):
        """Test optimization recommendation generation."""
        analysis = {"current_metrics": sample_metrics_data}
        recommendations = await optimizer.generate_optimization_recommendations(
            analysis
        )

        assert len(recommendations) > 0

        # Should have recommendations for detected bottlenecks
        caching_rec = next(
            (
                r
                for r in recommendations
                if r.technique == OptimizationTechnique.CACHING
            ),
            None,
        )
        assert caching_rec is not None
        assert caching_rec.target in [
            OptimizationTarget.RESPONSE_TIME,
            OptimizationTarget.RESOURCE_UTILIZATION,
        ]

        # Test recommendation structure
        for rec in recommendations:
            assert rec.action_id is not None
            assert rec.description is not None
            assert rec.estimated_impact is not None
            assert len(rec.implementation_steps) > 0
            assert rec.estimated_effort in ["low", "medium", "high"]
            assert rec.estimated_cost >= 0
            assert 1 <= rec.priority <= 10

    @pytest.mark.asyncio
    async def test_analyze_performance_patterns(self, optimizer, sample_time_window):
        """Test performance pattern analysis."""
        # Add some historical metrics
        for i in range(24):  # 24 hours of data
            for j in range(5):  # 5 metrics per hour
                timestamp = datetime.now() - timedelta(hours=23 - i, minutes=j * 10)

                # Simulate business hours pattern
                hour = timestamp.hour
                load_multiplier = 1.5 if 9 <= hour <= 17 else 1.0

                optimizer.performance_metrics["cpu_usage"].append(
                    PerformanceMetric(
                        name="cpu_usage",
                        value=50.0 * load_multiplier + (i % 5) * 2,
                        unit="percent",
                        timestamp=timestamp,
                    )
                )

        patterns = await optimizer.analyze_performance_patterns(sample_time_window)

        assert "analysis_period" in patterns
        assert "patterns" in patterns
        assert "insights" in patterns
        assert "recommendations" in patterns

        # Test time-based patterns
        time_patterns = patterns["patterns"]["time_based_patterns"]
        assert "hourly_patterns" in time_patterns
        assert "business_hours_impact" in time_patterns

        business_impact = time_patterns["business_hours_impact"]
        assert (
            business_impact["business_hours_multiplier"] > 1.0
        )  # Should detect higher load during business hours

    @pytest.mark.asyncio
    async def test_detect_performance_regressions(self, optimizer):
        """Test performance regression detection."""
        baseline = {
            "response_time": 1000.0,
            "throughput": 1000.0,
            "error_rate": 0.5,
            "cpu_usage": 60.0,
        }

        # Add current metrics that show regression
        optimizer.performance_metrics["response_time"].append(
            PerformanceMetric(
                name="response_time", value=1500.0, unit="ms"
            )  # 50% worse
        )
        optimizer.performance_metrics["throughput"].append(
            PerformanceMetric(
                name="throughput", value=750.0, unit="rps"
            )  # 25% worse
        )
        optimizer.performance_metrics["error_rate"].append(
            PerformanceMetric(
                name="error_rate", value=2.0, unit="percent"
            )  # 300% worse
        )

        regressions = await optimizer.detect_performance_regressions(baseline)

        assert len(regressions) > 0

        # Should detect response time regression
        response_regression = next(
            (r for r in regressions if r["metric"] == "response_time"), None
        )
        assert response_regression is not None
        assert response_regression["regression_percent"] > 10  # Significant regression
        assert response_regression["severity"] in [
            "medium",
            "high",
            "critical",
        ]

    @pytest.mark.asyncio
    async def test_optimize_provider_selection(self, optimizer):
        """Test provider selection optimization."""
        task = {
            "requirements": {
                "priority": "high",
                "throughput": 1200,
                "max_cost_per_request": 0.01,
                "cpu_intensive": True,
            }
        }

        result = await optimizer.optimize_provider_selection(task)

        assert "selected_provider" in result
        assert "selection_score" in result
        assert "provider_metrics" in result
        assert "all_scores" in result
        assert "selection_reasoning" in result

        # Test that selection reasoning is provided
        reasoning = result["selection_reasoning"]
        assert len(reasoning) > 0

        # Test that provider metrics are realistic
        provider_metrics = result["provider_metrics"]
        assert provider_metrics["response_time"] > 0
        assert provider_metrics["throughput"] > 0
        assert provider_metrics["reliability"] > 90  # Should be high reliability

    @pytest.mark.asyncio
    async def test_implement_automatic_adjustments(self, optimizer):
        """Test automatic performance adjustments."""
        # Create low-risk recommendations
        recommendations = [
            OptimizationAction(
                action_id="auto_test_001",
                technique=OptimizationTechnique.CONNECTION_POOLING,
                target=OptimizationTarget.RESOURCE_UTILIZATION,
                description="Optimize connection pooling",
                estimated_impact="20% efficiency improvement",
                implementation_steps=["Configure pool", "Monitor"],
                estimated_effort="low",
                estimated_cost=25.0,
                priority=3,
                risks=[],  # No risks for auto-implementation
            )
        ]

        adjustments = await optimizer.implement_automatic_adjustments(recommendations)

        assert len(adjustments) == 1
        adjustment = adjustments[0]
        assert adjustment["action_id"] == "auto_test_001"
        assert adjustment["status"] in ["implemented", "failed"]

    def test_correlation_analysis(self, optimizer):
        """Test correlation analysis between metrics."""
        # Add correlated metrics
        for i in range(50):
            cpu_value = 50.0 + i
            response_value = 1000.0 + i * 10  # Correlated with CPU

            optimizer.performance_metrics["cpu_usage"].append(
                PerformanceMetric(
                    name="cpu_usage", value=cpu_value, unit="percent"
                )
            )
            optimizer.performance_metrics["response_time"].append(
                PerformanceMetric(
                    name="response_time", value=response_value, unit="ms"
                )
            )

        correlation = optimizer._calculate_correlation("cpu_usage", "response_time")

        # Should detect strong positive correlation
        assert correlation > 0.8

    def test_trend_calculation(self, optimizer):
        """Test trend calculation in time series."""
        # Create increasing trend
        increasing_values = [10.0 + i * 2 for i in range(20)]
        trend = optimizer._calculate_trend(increasing_values)
        assert trend > 0  # Positive trend

        # Create decreasing trend
        decreasing_values = [100.0 - i * 3 for i in range(20)]
        trend = optimizer._calculate_trend(decreasing_values)
        assert trend < 0  # Negative trend

        # Create stable trend
        stable_values = [50.0] * 20
        trend = optimizer._calculate_trend(stable_values)
        assert abs(trend) < 0.1  # Near zero trend

    @pytest.mark.asyncio
    async def test_optimization_plan_creation(self, optimizer):
        """Test optimization plan creation."""
        recommendations = [
            OptimizationAction(
                action_id="plan_test_001",
                technique=OptimizationTechnique.CACHING,
                target=OptimizationTarget.RESPONSE_TIME,
                description="Implement caching layer",
                estimated_impact="50% response time improvement",
                implementation_steps=["Setup cache", "Configure", "Monitor"],
                estimated_effort="medium",
                estimated_cost=100.0,
                priority=1,
            ),
            OptimizationAction(
                action_id="plan_test_002",
                technique=OptimizationTechnique.LOAD_BALANCING,
                target=OptimizationTarget.THROUGHPUT,
                description="Add load balancing",
                estimated_impact="100% throughput increase",
                implementation_steps=["Setup LB", "Configure", "Test"],
                estimated_effort="high",
                estimated_cost=200.0,
                priority=2,
            ),
        ]

        constraints = {
            "max_cost": 250.0,
            "max_effort": "high",
            "target_system": "test_system",
        }

        plan = await optimizer.create_optimization_plan(recommendations, constraints)

        assert plan.plan_id is not None
        assert plan.target_system == "test_system"
        assert len(plan.actions) == 2
        assert plan.estimated_total_cost == 300.0
        assert len(plan.implementation_phases) > 0

        # Test phase grouping
        phases = plan.implementation_phases
        phase_1 = next((p for p in phases if p["phase"] == 1), None)
        assert phase_1 is not None
        assert phase_1["name"] == "Quick Wins"

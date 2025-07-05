# supervisor_agent/tests/test_predictive_analytics.py
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from supervisor_agent.core.predictive_analytics import (
    OptimizationOpportunity,
    PredictionModel,
    PredictionResult,
    PredictiveAnalyticsEngine,
    RiskAssessment,
    RiskLevel,
    TrendAnalysis,
    TrendDirection,
)


class TestPredictiveAnalyticsEngine:
    """Test suite for PredictiveAnalyticsEngine."""

    @pytest.fixture
    def analytics_engine(self):
        """Create a PredictiveAnalyticsEngine instance."""
        return PredictiveAnalyticsEngine()

    @pytest.fixture
    def sample_workflow_data(self):
        """Create sample workflow data for testing."""
        return {
            "workflow_id": "test_workflow_001",
            "cpu_usage": 75.0,
            "memory_usage": 80.0,
            "disk_usage": 60.0,
            "network_usage": 45.0,
            "avg_response_time": 2500.0,
            "throughput": 150.0,
            "error_rate": 2.5,
            "queue_depth": 25,
            "task_count": 50,
            "active_users": 100,
            "dependencies": ["service_a", "service_b", "database"],
            "historical_failures": 3,
            "last_failure": (datetime.now() - timedelta(days=2)).isoformat(),
        }

    @pytest.fixture
    def sample_resource_demand_data(self):
        """Create sample resource demand data."""
        return {
            "cpu_demand": [70, 75, 80, 85, 90, 85, 80],
            "memory_demand": [60, 65, 70, 75, 80, 75, 70],
            "storage_demand": [40, 42, 45, 48, 50, 48, 45],
            "network_demand": [30, 35, 40, 45, 50, 45, 40],
            "forecast_horizon": 7,
            "time_unit": "days",
        }

    @pytest.fixture
    def sample_historical_metrics(self):
        """Create sample historical metrics for trend analysis."""
        base_time = datetime.now() - timedelta(days=7)
        metrics = []

        for i in range(168):  # 7 days * 24 hours
            timestamp = base_time + timedelta(hours=i)

            # Simulate business hours pattern
            hour = timestamp.hour
            business_multiplier = 1.5 if 9 <= hour <= 17 else 1.0

            # Add some seasonality and noise
            seasonal = 10 * (1 + 0.3 * (i % 24) / 24)
            noise = (-5 + (i % 13)) / 2

            metrics.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "response_time": 1000
                    + (seasonal * business_multiplier)
                    + noise,
                    "throughput": 100
                    + (seasonal * business_multiplier)
                    + noise,
                    "cpu_usage": 50 + (seasonal * business_multiplier) + noise,
                    "error_rate": 1.0 + (seasonal * 0.1) + (noise * 0.1),
                }
            )

        return metrics

    def test_engine_initialization(self, analytics_engine):
        """Test analytics engine initialization."""
        assert len(analytics_engine.failure_indicators) == 5
        assert analytics_engine.trend_analysis_window == 24
        assert analytics_engine.seasonal_period == 168
        assert "cpu_usage_threshold" in analytics_engine.failure_indicators
        assert "memory_usage_threshold" in analytics_engine.failure_indicators

    @pytest.mark.asyncio
    async def test_predict_workflow_failures(
        self, analytics_engine, sample_workflow_data
    ):
        """Test workflow failure prediction functionality."""
        prediction = await analytics_engine.predict_workflow_failures(
            sample_workflow_data
        )

        assert prediction["workflow_id"] == "test_workflow_001"
        assert "overall_risk" in prediction
        assert "specific_risks" in prediction
        assert "recommendations" in prediction
        assert "features_analyzed" in prediction
        assert "prediction_timestamp" in prediction

        # Test overall risk structure
        overall_risk = prediction["overall_risk"]
        assert "level" in overall_risk
        assert "probability" in overall_risk
        assert "confidence" in overall_risk
        assert overall_risk["level"] in [
            "very_low",
            "low",
            "medium",
            "high",
            "critical",
        ]
        assert 0 <= overall_risk["probability"] <= 1
        assert 0 <= overall_risk["confidence"] <= 1

        # Test specific risks
        specific_risks = prediction["specific_risks"]
        expected_risk_types = [
            "resource_exhaustion",
            "performance_degradation",
            "dependency_failure",
            "cascade_failure",
        ]

        for risk_type in expected_risk_types:
            assert risk_type in specific_risks
            risk_data = specific_risks[risk_type]
            assert "level" in risk_data
            assert "probability" in risk_data
            assert "factors" in risk_data
            assert "mitigation" in risk_data
            assert isinstance(risk_data["factors"], list)
            assert isinstance(risk_data["mitigation"], list)

    @pytest.mark.asyncio
    async def test_high_risk_workflow_prediction(self, analytics_engine):
        """Test prediction for high-risk workflow."""
        high_risk_data = {
            "workflow_id": "high_risk_workflow",
            "cpu_usage": 95.0,  # Above threshold
            "memory_usage": 98.0,  # Above threshold
            "error_rate": 8.0,  # Above threshold
            "avg_response_time": 8000.0,  # Above threshold
            "queue_depth": 150,  # Above threshold
            "throughput": 10.0,  # Low throughput
            "dependencies": ["unstable_service"] * 5,  # Many dependencies
        }

        prediction = await analytics_engine.predict_workflow_failures(
            high_risk_data
        )

        # Should predict high or critical risk
        risk_level = prediction["overall_risk"]["level"]
        assert risk_level in ["high", "critical"]

        # Should have high probability
        assert prediction["overall_risk"]["probability"] > 0.7

        # Should have multiple recommendations
        assert len(prediction["recommendations"]) > 3

    @pytest.mark.asyncio
    async def test_predict_resource_demand(
        self, analytics_engine, sample_resource_demand_data
    ):
        """Test resource demand forecasting."""
        forecast = await analytics_engine.predict_resource_demand(
            sample_resource_demand_data
        )

        assert "forecast_horizon" in forecast
        assert "predictions" in forecast
        assert "model_accuracy" in forecast
        assert "confidence_intervals" in forecast
        assert "trend_analysis" in forecast

        # Test predictions structure
        predictions = forecast["predictions"]
        resource_types = [
            "cpu_demand",
            "memory_demand",
            "storage_demand",
            "network_demand",
        ]

        for resource_type in resource_types:
            assert resource_type in predictions
            resource_forecast = predictions[resource_type]
            assert "values" in resource_forecast
            assert "model_used" in resource_forecast
            assert "confidence" in resource_forecast
            assert len(resource_forecast["values"]) == 7  # forecast_horizon

    @pytest.mark.asyncio
    async def test_analyze_performance_trends(
        self, analytics_engine, sample_historical_metrics
    ):
        """Test performance trend analysis."""
        trends = await analytics_engine.analyze_performance_trends(
            sample_historical_metrics
        )

        assert "analysis_period" in trends
        assert "metrics_analyzed" in trends
        assert "trend_results" in trends
        assert "insights" in trends
        assert "anomalies_detected" in trends

        # Test trend results
        trend_results = trends["trend_results"]
        expected_metrics = [
            "response_time",
            "throughput",
            "cpu_usage",
            "error_rate",
        ]

        for metric in expected_metrics:
            if metric in trend_results:
                trend_data = trend_results[metric]
                assert "direction" in trend_data
                assert "strength" in trend_data
                assert "rate_of_change" in trend_data
                assert "projection_24h" in trend_data
                assert "projection_7d" in trend_data
                assert trend_data["direction"] in [
                    "strongly_increasing",
                    "increasing",
                    "stable",
                    "decreasing",
                    "strongly_decreasing",
                    "volatile",
                ]
                assert 0 <= trend_data["strength"] <= 1

    @pytest.mark.asyncio
    async def test_seasonal_pattern_detection(
        self, analytics_engine, sample_historical_metrics
    ):
        """Test seasonal pattern detection in trends."""
        trends = await analytics_engine.analyze_performance_trends(
            sample_historical_metrics
        )

        # Should detect business hours patterns
        insights = trends["insights"]
        business_hours_insights = [
            insight
            for insight in insights
            if "business" in insight.lower() or "hour" in insight.lower()
        ]

        # Should have at least one business hours insight
        assert len(business_hours_insights) > 0

    @pytest.mark.asyncio
    async def test_identify_optimization_opportunities(self, analytics_engine):
        """Test optimization opportunity identification."""
        system_state = {
            "cpu_usage": 85.0,
            "memory_usage": 78.0,
            "response_time": 3500.0,
            "throughput": 80.0,
            "error_rate": 3.0,
            "cost_per_hour": 50.0,
            "task_count": 150,
        }

        opportunities = (
            await analytics_engine.identify_optimization_opportunities(
                system_state
            )
        )

        assert len(opportunities) > 0

        # Test opportunity structure
        for opportunity in opportunities:
            assert hasattr(opportunity, "opportunity_id")
            assert hasattr(opportunity, "opportunity_type")
            assert hasattr(opportunity, "description")
            assert hasattr(opportunity, "potential_improvement")
            assert hasattr(opportunity, "implementation_effort")
            assert hasattr(opportunity, "estimated_roi")
            assert hasattr(opportunity, "priority_score")

            # Validate effort levels
            assert opportunity.implementation_effort in [
                "low",
                "medium",
                "high",
            ]

            # Validate priority score
            assert 1 <= opportunity.priority_score <= 100

            # Validate ROI
            assert 0 <= opportunity.estimated_roi <= 1

    @pytest.mark.asyncio
    async def test_optimization_opportunity_types(self, analytics_engine):
        """Test different types of optimization opportunities."""
        # High resource usage scenario
        high_resource_state = {
            "cpu_usage": 90.0,
            "memory_usage": 88.0,
            "response_time": 4000.0,
            "cost_per_hour": 100.0,
        }

        opportunities = (
            await analytics_engine.identify_optimization_opportunities(
                high_resource_state
            )
        )

        # Should identify resource and performance optimizations
        opportunity_types = [opp.opportunity_type for opp in opportunities]
        assert "resource_optimization" in opportunity_types
        assert "performance_optimization" in opportunity_types

        # Test cost optimization scenario
        high_cost_state = {
            "cost_per_hour": 200.0,
            "cpu_usage": 40.0,  # Low utilization
            "throughput": 50.0,
        }

        cost_opportunities = (
            await analytics_engine.identify_optimization_opportunities(
                high_cost_state
            )
        )
        cost_types = [opp.opportunity_type for opp in cost_opportunities]
        assert "cost_optimization" in cost_types

    @pytest.mark.asyncio
    async def test_error_handling_workflow_prediction(self, analytics_engine):
        """Test error handling in workflow prediction."""
        # Test with invalid data
        invalid_data = {
            "workflow_id": "error_test",
            "invalid_field": "should_cause_error",
        }

        prediction = await analytics_engine.predict_workflow_failures(
            invalid_data
        )

        # Should handle gracefully
        assert "workflow_id" in prediction
        assert prediction["workflow_id"] == "error_test"

        # Should still provide some prediction or error info
        assert "overall_risk" in prediction or "error" in prediction

    @pytest.mark.asyncio
    async def test_time_series_forecasting_models(self, analytics_engine):
        """Test different time series forecasting models."""
        # Create time series data
        time_series_data = [10, 12, 14, 13, 15, 17, 16, 18, 20, 19]

        # Test linear regression
        linear_forecast = analytics_engine._forecast_linear_regression(
            time_series_data, 3
        )
        assert len(linear_forecast) == 3
        assert all(isinstance(val, (int, float)) for val in linear_forecast)

        # Test exponential smoothing
        exp_forecast = analytics_engine._forecast_exponential_smoothing(
            time_series_data, 3
        )
        assert len(exp_forecast) == 3
        assert all(isinstance(val, (int, float)) for val in exp_forecast)

        # Test moving average
        ma_forecast = analytics_engine._forecast_moving_average(
            time_series_data, 3
        )
        assert len(ma_forecast) == 3
        assert all(isinstance(val, (int, float)) for val in ma_forecast)

    @pytest.mark.asyncio
    async def test_risk_assessment_calculation(
        self, analytics_engine, sample_workflow_data
    ):
        """Test risk assessment calculation methods."""
        features = analytics_engine._extract_workflow_features(
            sample_workflow_data
        )

        # Test resource exhaustion risk
        resource_risk = (
            await analytics_engine._assess_resource_exhaustion_risk(features)
        )
        assert isinstance(resource_risk, RiskAssessment)
        assert resource_risk.risk_level in [level for level in RiskLevel]
        assert 0 <= resource_risk.probability <= 1
        assert 0 <= resource_risk.confidence <= 1
        assert isinstance(resource_risk.risk_factors, list)
        assert isinstance(resource_risk.mitigation_strategies, list)

        # Test performance degradation risk
        perf_risk = (
            await analytics_engine._assess_performance_degradation_risk(
                features
            )
        )
        assert isinstance(perf_risk, RiskAssessment)
        assert perf_risk.risk_level in [level for level in RiskLevel]

        # Test dependency failure risk
        dep_risk = await analytics_engine._assess_dependency_failure_risk(
            features
        )
        assert isinstance(dep_risk, RiskAssessment)
        assert dep_risk.risk_level in [level for level in RiskLevel]

    def test_feature_extraction(self, analytics_engine, sample_workflow_data):
        """Test workflow feature extraction."""
        features = analytics_engine._extract_workflow_features(
            sample_workflow_data
        )

        # Test basic features
        expected_features = [
            "cpu_usage",
            "memory_usage",
            "disk_usage",
            "network_usage",
            "avg_response_time",
            "throughput",
            "error_rate",
            "queue_depth",
        ]

        for feature in expected_features:
            assert feature in features
            assert isinstance(features[feature], (int, float))

        # Test derived features
        derived_features = analytics_engine._calculate_derived_features(
            features, sample_workflow_data
        )

        assert "resource_pressure" in derived_features
        assert "performance_score" in derived_features
        assert "stability_index" in derived_features
        assert "complexity_score" in derived_features

    @pytest.mark.asyncio
    async def test_trend_strength_calculation(self, analytics_engine):
        """Test trend strength calculation."""
        # Strong increasing trend
        increasing_data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        trend_strength = analytics_engine._calculate_trend_strength(
            increasing_data
        )
        assert trend_strength > 0.8  # Should detect strong trend

        # No trend (stable)
        stable_data = [5, 5, 5, 5, 5, 5, 5, 5, 5, 5]
        stable_strength = analytics_engine._calculate_trend_strength(
            stable_data
        )
        assert stable_strength < 0.2  # Should detect weak/no trend

        # Volatile data
        volatile_data = [1, 5, 2, 8, 3, 7, 4, 6, 1, 9]
        volatile_strength = analytics_engine._calculate_trend_strength(
            volatile_data
        )
        assert (
            volatile_strength < 0.5
        )  # Should detect weak trend due to volatility

    @pytest.mark.asyncio
    async def test_autocorrelation_analysis(
        self, analytics_engine, sample_historical_metrics
    ):
        """Test autocorrelation analysis for seasonality detection."""
        # Extract response time values
        response_times = [
            float(metric["response_time"])
            for metric in sample_historical_metrics
        ]

        # Test different lag periods
        lag_1h = analytics_engine._calculate_autocorrelation(response_times, 1)
        lag_24h = analytics_engine._calculate_autocorrelation(
            response_times, 24
        )
        lag_168h = analytics_engine._calculate_autocorrelation(
            response_times, 168
        )

        # All should be valid correlation values
        assert -1 <= lag_1h <= 1
        assert -1 <= lag_24h <= 1

        # 24-hour lag should show strong correlation due to daily pattern
        assert lag_24h > 0.3

    @pytest.mark.asyncio
    async def test_anomaly_detection(self, analytics_engine):
        """Test anomaly detection in trend analysis."""
        # Normal data with anomalies
        normal_data = [10] * 20  # Normal baseline
        anomaly_data = normal_data + [50, 60, 70]  # Clear anomalies

        anomalies = analytics_engine._detect_anomalies(anomaly_data)

        # Should detect the anomalous values
        assert len(anomalies) >= 2  # Should detect the anomalous points

        for anomaly in anomalies:
            assert "index" in anomaly
            assert "value" in anomaly
            assert "severity" in anomaly
            assert "z_score" in anomaly

    @pytest.mark.asyncio
    async def test_model_ensemble_forecasting(
        self, analytics_engine, sample_resource_demand_data
    ):
        """Test ensemble forecasting with multiple models."""
        forecast = await analytics_engine.predict_resource_demand(
            sample_resource_demand_data
        )

        # Should use ensemble of models
        cpu_prediction = forecast["predictions"]["cpu_demand"]
        assert cpu_prediction["model_used"] in [
            model.value for model in PredictionModel
        ]

        # Should have confidence scores
        assert 0 <= cpu_prediction["confidence"] <= 1

        # Should have model accuracy metrics
        assert "model_accuracy" in forecast
        accuracy = forecast["model_accuracy"]
        assert "mae" in accuracy  # Mean Absolute Error
        assert "rmse" in accuracy  # Root Mean Square Error
        assert "mape" in accuracy  # Mean Absolute Percentage Error

    @pytest.mark.asyncio
    async def test_recommendation_generation(
        self, analytics_engine, sample_workflow_data
    ):
        """Test failure prevention recommendation generation."""
        prediction = await analytics_engine.predict_workflow_failures(
            sample_workflow_data
        )
        recommendations = prediction["recommendations"]

        assert len(recommendations) > 0

        for rec in recommendations:
            assert "type" in rec
            assert "priority" in rec
            assert "description" in rec
            assert "implementation_effort" in rec
            assert "expected_impact" in rec

            # Validate priority
            assert rec["priority"] in ["low", "medium", "high", "critical"]

            # Validate effort
            assert rec["implementation_effort"] in ["low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_prediction_caching(
        self, analytics_engine, sample_workflow_data
    ):
        """Test prediction result caching."""
        # First prediction
        prediction1 = await analytics_engine.predict_workflow_failures(
            sample_workflow_data
        )

        # Check if results are cached
        workflow_id = sample_workflow_data["workflow_id"]
        cache_key = f"workflow_prediction_{workflow_id}"

        # Make second prediction with same data
        prediction2 = await analytics_engine.predict_workflow_failures(
            sample_workflow_data
        )

        # Results should be consistent
        assert prediction1["workflow_id"] == prediction2["workflow_id"]
        assert (
            prediction1["overall_risk"]["level"]
            == prediction2["overall_risk"]["level"]
        )

    @pytest.mark.asyncio
    async def test_confidence_interval_calculation(
        self, analytics_engine, sample_resource_demand_data
    ):
        """Test confidence interval calculation for predictions."""
        forecast = await analytics_engine.predict_resource_demand(
            sample_resource_demand_data
        )

        confidence_intervals = forecast["confidence_intervals"]

        for resource_type in ["cpu_demand", "memory_demand"]:
            if resource_type in confidence_intervals:
                intervals = confidence_intervals[resource_type]
                assert "lower_bound" in intervals
                assert "upper_bound" in intervals
                assert isinstance(intervals["lower_bound"], list)
                assert isinstance(intervals["upper_bound"], list)
                assert (
                    len(intervals["lower_bound"])
                    == sample_resource_demand_data["forecast_horizon"]
                )
                assert (
                    len(intervals["upper_bound"])
                    == sample_resource_demand_data["forecast_horizon"]
                )

    def test_performance_metrics_calculation(self, analytics_engine):
        """Test model performance metrics calculation."""
        # Mock actual vs predicted values
        actual = [10, 15, 20, 25, 30]
        predicted = [12, 14, 22, 24, 28]

        mae = analytics_engine._calculate_mae(actual, predicted)
        rmse = analytics_engine._calculate_rmse(actual, predicted)
        mape = analytics_engine._calculate_mape(actual, predicted)

        assert mae > 0
        assert rmse > 0
        assert mape > 0

        # MAE should be less than RMSE for this data
        assert mae <= rmse

        # MAPE should be reasonable percentage
        assert 0 <= mape <= 100

    @pytest.mark.asyncio
    async def test_complex_workflow_scenario(self, analytics_engine):
        """Test prediction for complex multi-factor workflow."""
        complex_workflow = {
            "workflow_id": "complex_workflow_001",
            "cpu_usage": 82.0,
            "memory_usage": 75.0,
            "disk_usage": 90.0,  # High disk usage
            "network_usage": 60.0,
            "avg_response_time": 3200.0,
            "throughput": 95.0,
            "error_rate": 4.2,
            "queue_depth": 85,
            "task_count": 200,
            "active_users": 500,
            "dependencies": [
                "service_a",
                "service_b",
                "service_c",
                "database",
                "cache",
            ],
            "historical_failures": 5,
            "last_failure": (datetime.now() - timedelta(hours=6)).isoformat(),
            "complexity_factors": {
                "nested_workflows": 3,
                "external_apis": 7,
                "data_transformations": 12,
            },
        }

        prediction = await analytics_engine.predict_workflow_failures(
            complex_workflow
        )

        # Should identify multiple risk factors
        assert len(prediction["specific_risks"]) == 4

        # Should have detailed recommendations
        assert len(prediction["recommendations"]) >= 3

        # Should analyze complexity factors
        assert len(prediction["features_analyzed"]) >= 8

    @pytest.mark.asyncio
    async def test_seasonal_decomposition(
        self, analytics_engine, sample_historical_metrics
    ):
        """Test seasonal decomposition functionality."""
        response_times = [
            float(metric["response_time"])
            for metric in sample_historical_metrics
        ]

        decomposition = analytics_engine._seasonal_decomposition(
            response_times, 24
        )  # 24-hour period

        assert "trend" in decomposition
        assert "seasonal" in decomposition
        assert "residual" in decomposition

        # Components should have same length as original data
        assert len(decomposition["trend"]) == len(response_times)
        assert len(decomposition["seasonal"]) == len(response_times)
        assert len(decomposition["residual"]) == len(response_times)

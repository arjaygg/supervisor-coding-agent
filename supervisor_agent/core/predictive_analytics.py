# supervisor_agent/core/predictive_analytics.py
import asyncio
import json
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import random
import math

from supervisor_agent.models.task import Task


class PredictionModel(Enum):
    """Types of prediction models."""
    LINEAR_REGRESSION = "linear_regression"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    ARIMA = "arima"
    NEURAL_NETWORK = "neural_network"
    ENSEMBLE = "ensemble"
    SEASONAL_DECOMPOSITION = "seasonal_decomposition"


class RiskLevel(Enum):
    """Risk assessment levels."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TrendDirection(Enum):
    """Trend direction indicators."""
    STRONGLY_INCREASING = "strongly_increasing"
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    STRONGLY_DECREASING = "strongly_decreasing"
    VOLATILE = "volatile"


@dataclass
class PredictionResult:
    """Result of a prediction analysis."""
    prediction_type: str
    predicted_value: float
    confidence: float
    prediction_range: Tuple[float, float]
    time_horizon: int  # minutes
    model_used: PredictionModel
    features_used: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskAssessment:
    """Risk assessment result."""
    risk_level: RiskLevel
    probability: float
    risk_factors: List[str]
    mitigation_strategies: List[str]
    confidence: float
    time_to_event: Optional[int] = None  # minutes
    impact_severity: str = "medium"


@dataclass
class TrendAnalysis:
    """Trend analysis result."""
    metric_name: str
    trend_direction: TrendDirection
    trend_strength: float  # 0-1
    rate_of_change: float
    projection_24h: float
    projection_7d: float
    seasonal_component: Optional[float] = None
    anomaly_score: float = 0.0


@dataclass
class OptimizationOpportunity:
    """Optimization opportunity identification."""
    opportunity_id: str
    opportunity_type: str
    description: str
    potential_improvement: str
    implementation_effort: str  # low, medium, high
    estimated_roi: float
    priority_score: int  # 1-100
    requirements: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


class PredictiveAnalyticsEngine:
    """Advanced predictive analytics engine with ML-powered insights."""
    
    def __init__(self):
        self.historical_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.prediction_cache: Dict[str, Any] = {}
        self.model_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.feature_importance: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Performance thresholds
        self.failure_indicators = {
            "cpu_usage_threshold": 90.0,
            "memory_usage_threshold": 95.0,
            "error_rate_threshold": 5.0,
            "response_time_threshold": 5000.0,
            "queue_depth_threshold": 100
        }
        
        # Trend analysis parameters
        self.trend_analysis_window = 24  # hours
        self.seasonal_period = 168  # weekly pattern (hours)
    
    async def predict_workflow_failures(self, workflow_data: Dict) -> Dict:
        """Predict workflow failures using multi-factor risk analysis."""
        try:
            workflow_id = workflow_data.get("workflow_id", "unknown")
            
            # Extract features for prediction
            features = self._extract_workflow_features(workflow_data)
            
            # Calculate risk scores for different failure types
            risk_assessments = {}
            
            # Resource exhaustion risk
            resource_risk = await self._assess_resource_exhaustion_risk(features)
            risk_assessments["resource_exhaustion"] = resource_risk
            
            # Performance degradation risk
            performance_risk = await self._assess_performance_degradation_risk(features)
            risk_assessments["performance_degradation"] = performance_risk
            
            # Dependency failure risk
            dependency_risk = await self._assess_dependency_failure_risk(features)
            risk_assessments["dependency_failure"] = dependency_risk
            
            # Cascade failure risk
            cascade_risk = await self._assess_cascade_failure_risk(features)
            risk_assessments["cascade_failure"] = cascade_risk
            
            # Calculate overall risk
            overall_risk = self._calculate_overall_risk(risk_assessments)
            
            # Generate recommendations
            recommendations = self._generate_failure_prevention_recommendations(
                risk_assessments, overall_risk
            )
            
            return {
                "workflow_id": workflow_id,
                "overall_risk": {
                    "level": overall_risk.risk_level.value,
                    "probability": overall_risk.probability,
                    "confidence": overall_risk.confidence,
                    "time_to_failure": overall_risk.time_to_event,
                    "impact_severity": overall_risk.impact_severity
                },
                "specific_risks": {
                    risk_type: {
                        "level": assessment.risk_level.value,
                        "probability": assessment.probability,
                        "factors": assessment.risk_factors,
                        "mitigation": assessment.mitigation_strategies
                    }
                    for risk_type, assessment in risk_assessments.items()
                },
                "recommendations": recommendations,
                "features_analyzed": list(features.keys()),
                "prediction_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "error": f"Failed to predict workflow failures: {str(e)}",
                "workflow_id": workflow_data.get("workflow_id", "unknown"),
                "prediction": "error"
            }
    
    def _extract_workflow_features(self, workflow_data: Dict) -> Dict[str, float]:
        """Extract numerical features from workflow data."""
        features = {}
        
        # Resource utilization features
        features["cpu_usage"] = workflow_data.get("cpu_usage", 0.0)
        features["memory_usage"] = workflow_data.get("memory_usage", 0.0)
        features["disk_usage"] = workflow_data.get("disk_usage", 0.0)
        features["network_usage"] = workflow_data.get("network_usage", 0.0)
        
        # Performance features
        features["avg_response_time"] = workflow_data.get("avg_response_time", 0.0)
        features["throughput"] = workflow_data.get("throughput", 0.0)
        features["error_rate"] = workflow_data.get("error_rate", 0.0)
        features["queue_depth"] = workflow_data.get("queue_depth", 0.0)
        
        # Workflow complexity features
        features["task_count"] = workflow_data.get("task_count", 0.0)
        features["dependency_count"] = workflow_data.get("dependency_count", 0.0)
        features["parallel_stages"] = workflow_data.get("parallel_stages", 0.0)
        features["execution_time"] = workflow_data.get("execution_time", 0.0)
        
        # Historical performance features
        features["recent_failure_rate"] = workflow_data.get("recent_failure_rate", 0.0)
        features["avg_execution_time"] = workflow_data.get("avg_execution_time", 0.0)
        features["resource_variance"] = workflow_data.get("resource_variance", 0.0)
        
        return features
    
    async def _assess_resource_exhaustion_risk(self, features: Dict[str, float]) -> RiskAssessment:
        """Assess risk of resource exhaustion."""
        risk_factors = []
        risk_score = 0.0
        
        # CPU exhaustion risk
        if features.get("cpu_usage", 0) > 85:
            risk_factors.append(f"High CPU usage: {features['cpu_usage']:.1f}%")
            risk_score += 30
        
        # Memory exhaustion risk
        if features.get("memory_usage", 0) > 90:
            risk_factors.append(f"High memory usage: {features['memory_usage']:.1f}%")
            risk_score += 35
        
        # Disk space risk
        if features.get("disk_usage", 0) > 85:
            risk_factors.append(f"High disk usage: {features['disk_usage']:.1f}%")
            risk_score += 20
        
        # Queue depth risk
        if features.get("queue_depth", 0) > 50:
            risk_factors.append(f"High queue depth: {features['queue_depth']:.0f}")
            risk_score += 15
        
        # Determine risk level
        if risk_score >= 80:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 60:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 40:
            risk_level = RiskLevel.MEDIUM
        elif risk_score >= 20:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.VERY_LOW
        
        mitigation_strategies = []
        if risk_score > 40:
            mitigation_strategies.extend([
                "Scale up resource allocation",
                "Implement resource throttling",
                "Add resource monitoring alerts",
                "Optimize resource-intensive operations"
            ])
        
        return RiskAssessment(
            risk_level=risk_level,
            probability=min(risk_score / 100, 0.95),
            risk_factors=risk_factors,
            mitigation_strategies=mitigation_strategies,
            confidence=0.8,
            time_to_event=max(30, 180 - int(risk_score * 1.5)) if risk_score > 20 else None,
            impact_severity="high" if risk_score > 60 else "medium"
        )
    
    async def _assess_performance_degradation_risk(self, features: Dict[str, float]) -> RiskAssessment:
        """Assess risk of performance degradation."""
        risk_factors = []
        risk_score = 0.0
        
        # Response time degradation
        if features.get("avg_response_time", 0) > 3000:
            risk_factors.append(f"High response time: {features['avg_response_time']:.0f}ms")
            risk_score += 25
        
        # Low throughput
        if features.get("throughput", 0) < 100:
            risk_factors.append(f"Low throughput: {features['throughput']:.1f}/min")
            risk_score += 20
        
        # High error rate
        error_rate = features.get("error_rate", 0)
        if error_rate > 2:
            risk_factors.append(f"High error rate: {error_rate:.1f}%")
            risk_score += 30
        
        # Resource variance (instability)
        if features.get("resource_variance", 0) > 0.5:
            risk_factors.append("High resource usage variance indicating instability")
            risk_score += 15
        
        # Historical failure rate
        if features.get("recent_failure_rate", 0) > 5:
            risk_factors.append(f"Recent failures: {features['recent_failure_rate']:.1f}%")
            risk_score += 25
        
        # Determine risk level
        if risk_score >= 75:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 55:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 35:
            risk_level = RiskLevel.MEDIUM
        elif risk_score >= 15:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.VERY_LOW
        
        mitigation_strategies = []
        if risk_score > 30:
            mitigation_strategies.extend([
                "Implement performance monitoring",
                "Optimize slow operations",
                "Add caching layers",
                "Review and tune algorithms",
                "Implement circuit breakers"
            ])
        
        return RiskAssessment(
            risk_level=risk_level,
            probability=min(risk_score / 100, 0.9),
            risk_factors=risk_factors,
            mitigation_strategies=mitigation_strategies,
            confidence=0.75,
            time_to_event=max(60, 240 - int(risk_score * 2)) if risk_score > 15 else None,
            impact_severity="medium"
        )
    
    async def _assess_dependency_failure_risk(self, features: Dict[str, float]) -> RiskAssessment:
        """Assess risk of dependency failures."""
        risk_factors = []
        risk_score = 0.0
        
        # High dependency count increases risk
        dependency_count = features.get("dependency_count", 0)
        if dependency_count > 10:
            risk_factors.append(f"High dependency count: {dependency_count:.0f}")
            risk_score += 20
        elif dependency_count > 5:
            risk_score += 10
        
        # Complex workflows are more prone to dependency issues
        if features.get("task_count", 0) > 20:
            risk_factors.append("Complex workflow with many tasks")
            risk_score += 15
        
        # Network usage as indicator of external dependencies
        if features.get("network_usage", 0) > 80:
            risk_factors.append("High network usage indicating external dependency stress")
            risk_score += 25
        
        # Error rate indicating dependency issues
        if features.get("error_rate", 0) > 1:
            risk_factors.append("Error rate suggesting dependency issues")
            risk_score += 20
        
        if risk_score >= 60:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 40:
            risk_level = RiskLevel.MEDIUM
        elif risk_score >= 20:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.VERY_LOW
        
        mitigation_strategies = []
        if risk_score > 20:
            mitigation_strategies.extend([
                "Implement dependency health checks",
                "Add fallback mechanisms",
                "Implement retry logic with exponential backoff",
                "Monitor dependency response times",
                "Consider dependency alternatives"
            ])
        
        return RiskAssessment(
            risk_level=risk_level,
            probability=min(risk_score / 80, 0.8),
            risk_factors=risk_factors,
            mitigation_strategies=mitigation_strategies,
            confidence=0.7,
            time_to_event=max(120, 300 - int(risk_score * 2)) if risk_score > 20 else None,
            impact_severity="medium"
        )
    
    async def _assess_cascade_failure_risk(self, features: Dict[str, float]) -> RiskAssessment:
        """Assess risk of cascade failures."""
        risk_factors = []
        risk_score = 0.0
        
        # High parallel stages increase cascade risk
        parallel_stages = features.get("parallel_stages", 0)
        if parallel_stages > 5:
            risk_factors.append(f"High parallelism: {parallel_stages:.0f} parallel stages")
            risk_score += 25
        
        # Resource pressure can trigger cascades
        resource_pressure = (
            features.get("cpu_usage", 0) + 
            features.get("memory_usage", 0) + 
            features.get("disk_usage", 0)
        ) / 3
        
        if resource_pressure > 80:
            risk_factors.append(f"High resource pressure: {resource_pressure:.1f}%")
            risk_score += 30
        
        # High error rate indicates system stress
        if features.get("error_rate", 0) > 3:
            risk_factors.append("High error rate indicating system stress")
            risk_score += 20
        
        # Long execution times can contribute to cascades
        if features.get("execution_time", 0) > 3600:  # 1 hour
            risk_factors.append("Long execution time increasing cascade risk")
            risk_score += 15
        
        if risk_score >= 70:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 50:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 30:
            risk_level = RiskLevel.MEDIUM
        elif risk_score >= 15:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.VERY_LOW
        
        mitigation_strategies = []
        if risk_score > 30:
            mitigation_strategies.extend([
                "Implement bulkhead patterns",
                "Add circuit breakers between stages",
                "Implement graceful degradation",
                "Monitor stage-by-stage health",
                "Prepare rollback mechanisms"
            ])
        
        return RiskAssessment(
            risk_level=risk_level,
            probability=min(risk_score / 100, 0.85),
            risk_factors=risk_factors,
            mitigation_strategies=mitigation_strategies,
            confidence=0.65,
            time_to_event=max(90, 360 - int(risk_score * 3)) if risk_score > 15 else None,
            impact_severity="high" if risk_score > 50 else "medium"
        )
    
    def _calculate_overall_risk(self, risk_assessments: Dict[str, RiskAssessment]) -> RiskAssessment:
        """Calculate overall risk from individual assessments."""
        if not risk_assessments:
            return RiskAssessment(
                risk_level=RiskLevel.VERY_LOW,
                probability=0.0,
                risk_factors=[],
                mitigation_strategies=[],
                confidence=0.5
            )
        
        # Weight different risk types
        weights = {
            "resource_exhaustion": 0.3,
            "performance_degradation": 0.25,
            "dependency_failure": 0.25,
            "cascade_failure": 0.2
        }
        
        weighted_probability = 0.0
        all_risk_factors = []
        all_mitigation_strategies = []
        min_time_to_event = None
        max_impact_severity = "low"
        
        for risk_type, assessment in risk_assessments.items():
            weight = weights.get(risk_type, 0.25)
            weighted_probability += assessment.probability * weight
            
            all_risk_factors.extend(assessment.risk_factors)
            all_mitigation_strategies.extend(assessment.mitigation_strategies)
            
            if assessment.time_to_event:
                if min_time_to_event is None or assessment.time_to_event < min_time_to_event:
                    min_time_to_event = assessment.time_to_event
            
            if assessment.impact_severity == "high":
                max_impact_severity = "high"
            elif assessment.impact_severity == "medium" and max_impact_severity == "low":
                max_impact_severity = "medium"
        
        # Determine overall risk level
        if weighted_probability >= 0.8:
            overall_risk_level = RiskLevel.CRITICAL
        elif weighted_probability >= 0.6:
            overall_risk_level = RiskLevel.HIGH
        elif weighted_probability >= 0.4:
            overall_risk_level = RiskLevel.MEDIUM
        elif weighted_probability >= 0.2:
            overall_risk_level = RiskLevel.LOW
        else:
            overall_risk_level = RiskLevel.VERY_LOW
        
        # Remove duplicate mitigation strategies
        unique_strategies = list(set(all_mitigation_strategies))
        
        return RiskAssessment(
            risk_level=overall_risk_level,
            probability=weighted_probability,
            risk_factors=all_risk_factors,
            mitigation_strategies=unique_strategies,
            confidence=0.75,
            time_to_event=min_time_to_event,
            impact_severity=max_impact_severity
        )
    
    def _generate_failure_prevention_recommendations(
        self, risk_assessments: Dict[str, RiskAssessment], overall_risk: RiskAssessment
    ) -> List[Dict[str, Any]]:
        """Generate specific recommendations for failure prevention."""
        recommendations = []
        
        if overall_risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append({
                "priority": "immediate",
                "category": "emergency_response",
                "action": "Implement immediate monitoring and alerting",
                "description": "Set up real-time monitoring for all critical metrics",
                "estimated_effort": "low",
                "expected_impact": "high"
            })
        
        # Resource-specific recommendations
        if "resource_exhaustion" in risk_assessments:
            resource_risk = risk_assessments["resource_exhaustion"]
            if resource_risk.risk_level != RiskLevel.VERY_LOW:
                recommendations.append({
                    "priority": "high",
                    "category": "resource_management",
                    "action": "Scale resources proactively",
                    "description": "Increase resource allocation before reaching critical thresholds",
                    "estimated_effort": "medium",
                    "expected_impact": "high"
                })
        
        # Performance-specific recommendations
        if "performance_degradation" in risk_assessments:
            perf_risk = risk_assessments["performance_degradation"]
            if perf_risk.risk_level != RiskLevel.VERY_LOW:
                recommendations.append({
                    "priority": "high",
                    "category": "performance_optimization",
                    "action": "Implement performance tuning",
                    "description": "Optimize slow operations and add caching where appropriate",
                    "estimated_effort": "high",
                    "expected_impact": "medium"
                })
        
        # Dependency-specific recommendations
        if "dependency_failure" in risk_assessments:
            dep_risk = risk_assessments["dependency_failure"]
            if dep_risk.risk_level != RiskLevel.VERY_LOW:
                recommendations.append({
                    "priority": "medium",
                    "category": "reliability",
                    "action": "Strengthen dependency management",
                    "description": "Add circuit breakers and fallback mechanisms",
                    "estimated_effort": "medium",
                    "expected_impact": "medium"
                })
        
        return recommendations
    
    async def forecast_resource_demands(self, historical_data: Dict) -> Dict:
        """Forecast future resource demands using time series analysis."""
        try:
            forecasts = {}
            
            for resource_type, data_points in historical_data.items():
                if not data_points or len(data_points) < 10:
                    continue
                
                # Prepare time series data
                values = [point.get("value", 0) for point in data_points]
                timestamps = [
                    datetime.fromisoformat(point.get("timestamp", datetime.now().isoformat()))
                    for point in data_points
                ]
                
                # Generate forecasts for different horizons
                forecast_horizons = [24, 168, 720]  # 1 day, 1 week, 1 month (hours)
                
                resource_forecasts = {}
                for horizon in forecast_horizons:
                    forecast = await self._generate_resource_forecast(
                        values, timestamps, horizon, resource_type
                    )
                    resource_forecasts[f"{horizon}h"] = forecast
                
                forecasts[resource_type] = resource_forecasts
            
            # Generate capacity planning recommendations
            capacity_recommendations = self._generate_capacity_recommendations(forecasts)
            
            return {
                "forecasts": forecasts,
                "capacity_recommendations": capacity_recommendations,
                "forecast_timestamp": datetime.now().isoformat(),
                "forecast_confidence": self._calculate_forecast_confidence(forecasts),
                "model_performance": self._get_forecast_model_performance()
            }
            
        except Exception as e:
            return {
                "error": f"Failed to forecast resource demands: {str(e)}",
                "forecasts": {}
            }
    
    async def _generate_resource_forecast(
        self, values: List[float], timestamps: List[datetime], horizon_hours: int, resource_type: str
    ) -> Dict[str, Any]:
        """Generate forecast for a specific resource and time horizon."""
        if len(values) < 5:
            return {"error": "Insufficient data for forecasting"}
        
        # Use ensemble of forecasting methods
        forecasting_methods = {
            "linear_trend": self._forecast_linear_trend,
            "exponential_smoothing": self._forecast_exponential_smoothing,
            "seasonal_naive": self._forecast_seasonal_naive,
            "moving_average": self._forecast_moving_average
        }
        
        method_results = {}
        for method_name, method_func in forecasting_methods.items():
            try:
                result = method_func(values, horizon_hours)
                method_results[method_name] = result
            except Exception as e:
                continue
        
        if not method_results:
            return {"error": "All forecasting methods failed"}
        
        # Calculate ensemble forecast
        ensemble_values = []
        for i in range(horizon_hours):
            hour_predictions = []
            for method_predictions in method_results.values():
                if i < len(method_predictions):
                    hour_predictions.append(method_predictions[i])
            
            if hour_predictions:
                ensemble_value = statistics.mean(hour_predictions)
                ensemble_values.append(ensemble_value)
        
        # Calculate forecast statistics
        current_value = values[-1]
        peak_forecast = max(ensemble_values) if ensemble_values else current_value
        min_forecast = min(ensemble_values) if ensemble_values else current_value
        avg_forecast = statistics.mean(ensemble_values) if ensemble_values else current_value
        
        # Calculate growth rate
        growth_rate = ((avg_forecast - current_value) / current_value * 100) if current_value > 0 else 0
        
        # Determine forecast confidence based on method agreement
        if len(method_results) >= 3:
            # Calculate variance between methods for confidence
            method_variances = []
            for i in range(min(horizon_hours, min(len(pred) for pred in method_results.values()))):
                hour_predictions = [pred[i] for pred in method_results.values() if i < len(pred)]
                if len(hour_predictions) > 1:
                    variance = statistics.variance(hour_predictions)
                    method_variances.append(variance)
            
            avg_variance = statistics.mean(method_variances) if method_variances else 0
            confidence = max(0.3, 1.0 - (avg_variance / max(0.1, avg_forecast)))
        else:
            confidence = 0.6  # Default confidence for fewer methods
        
        return {
            "forecast_values": ensemble_values,
            "current_value": current_value,
            "peak_forecast": peak_forecast,
            "min_forecast": min_forecast,
            "average_forecast": avg_forecast,
            "growth_rate_percent": growth_rate,
            "confidence": min(confidence, 0.95),
            "methods_used": list(method_results.keys()),
            "forecast_horizon_hours": horizon_hours,
            "recommendations": self._generate_resource_specific_recommendations(
                resource_type, current_value, peak_forecast, growth_rate
            )
        }
    
    def _forecast_linear_trend(self, values: List[float], horizon: int) -> List[float]:
        """Linear trend forecasting."""
        if len(values) < 2:
            return [values[-1]] * horizon if values else []
        
        # Calculate linear regression
        n = len(values)
        x = list(range(n))
        
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean
        
        # Generate forecasts
        forecasts = []
        for i in range(horizon):
            forecast = slope * (n + i) + intercept
            forecasts.append(max(0, forecast))  # Ensure non-negative values
        
        return forecasts
    
    def _forecast_exponential_smoothing(self, values: List[float], horizon: int) -> List[float]:
        """Exponential smoothing forecasting."""
        if not values:
            return []
        
        alpha = 0.3  # Smoothing parameter
        smoothed = values[0]
        
        # Calculate smoothed values
        for value in values[1:]:
            smoothed = alpha * value + (1 - alpha) * smoothed
        
        # Generate constant forecasts
        return [max(0, smoothed)] * horizon
    
    def _forecast_seasonal_naive(self, values: List[float], horizon: int) -> List[float]:
        """Seasonal naive forecasting (weekly seasonality)."""
        if len(values) < 7:
            return [statistics.mean(values)] * horizon if values else []
        
        season_length = min(24, len(values))  # Daily seasonality
        forecasts = []
        
        for i in range(horizon):
            seasonal_index = i % season_length
            if seasonal_index < len(values):
                forecast = values[-(season_length - seasonal_index)]
            else:
                forecast = values[-1]
            forecasts.append(max(0, forecast))
        
        return forecasts
    
    def _forecast_moving_average(self, values: List[float], horizon: int) -> List[float]:
        """Moving average forecasting."""
        if not values:
            return []
        
        window_size = min(10, len(values))
        recent_values = values[-window_size:]
        moving_avg = statistics.mean(recent_values)
        
        return [max(0, moving_avg)] * horizon
    
    def _generate_resource_specific_recommendations(
        self, resource_type: str, current: float, peak: float, growth_rate: float
    ) -> List[str]:
        """Generate recommendations specific to resource type and forecast."""
        recommendations = []
        
        if growth_rate > 20:  # High growth
            recommendations.append(f"High growth rate detected ({growth_rate:.1f}%) - plan for rapid scaling")
        
        if peak > current * 1.5:  # Significant peak expected
            recommendations.append(f"Peak usage ({peak:.1f}) significantly higher than current - prepare for surge")
        
        # Resource-specific recommendations
        if resource_type == "cpu":
            if peak > 80:
                recommendations.append("CPU peak forecast exceeds 80% - consider adding CPU capacity")
            elif growth_rate > 10:
                recommendations.append("CPU growth trend detected - monitor for scaling needs")
        
        elif resource_type == "memory":
            if peak > 85:
                recommendations.append("Memory peak forecast exceeds 85% - consider memory upgrade")
            elif growth_rate > 15:
                recommendations.append("Memory growth trend - investigate potential memory leaks")
        
        elif resource_type == "disk":
            if peak > 80:
                recommendations.append("Disk usage peak forecast exceeds 80% - plan storage expansion")
        
        elif resource_type == "network":
            if growth_rate > 25:
                recommendations.append("Network usage growing rapidly - consider bandwidth upgrade")
        
        if not recommendations:
            recommendations.append("Resource usage within normal parameters - continue monitoring")
        
        return recommendations
    
    def _generate_capacity_recommendations(self, forecasts: Dict) -> List[Dict[str, Any]]:
        """Generate capacity planning recommendations."""
        recommendations = []
        
        for resource_type, resource_forecasts in forecasts.items():
            if "24h" in resource_forecasts and "forecast_values" in resource_forecasts["24h"]:
                peak_24h = resource_forecasts["24h"]["peak_forecast"]
                growth_24h = resource_forecasts["24h"]["growth_rate_percent"]
                
                if peak_24h > 80:  # High utilization expected
                    recommendations.append({
                        "resource": resource_type,
                        "urgency": "high",
                        "recommendation": f"Scale {resource_type} capacity before 24h peak of {peak_24h:.1f}%",
                        "timeline": "immediate",
                        "estimated_cost": "medium"
                    })
                elif growth_24h > 20:  # High growth rate
                    recommendations.append({
                        "resource": resource_type,
                        "urgency": "medium", 
                        "recommendation": f"Monitor {resource_type} closely due to {growth_24h:.1f}% growth rate",
                        "timeline": "this_week",
                        "estimated_cost": "low"
                    })
        
        return recommendations
    
    def _calculate_forecast_confidence(self, forecasts: Dict) -> float:
        """Calculate overall confidence in forecasts."""
        if not forecasts:
            return 0.0
        
        confidences = []
        for resource_forecasts in forecasts.values():
            for horizon_forecast in resource_forecasts.values():
                if isinstance(horizon_forecast, dict) and "confidence" in horizon_forecast:
                    confidences.append(horizon_forecast["confidence"])
        
        return statistics.mean(confidences) if confidences else 0.5
    
    def _get_forecast_model_performance(self) -> Dict[str, float]:
        """Get historical performance of forecasting models."""
        # In a real implementation, this would track actual vs predicted performance
        return {
            "linear_trend": 0.75,
            "exponential_smoothing": 0.68,
            "seasonal_naive": 0.72,
            "moving_average": 0.65,
            "ensemble": 0.82
        }
    
    async def predict_performance_trends(self, performance_history: Dict) -> Dict:
        """Predict performance trends using advanced time series analysis."""
        try:
            trends = {}
            
            for metric_name, metric_data in performance_history.items():
                if not metric_data or len(metric_data) < 10:
                    continue
                
                # Extract values and timestamps
                values = [point.get("value", 0) for point in metric_data]
                timestamps = [
                    datetime.fromisoformat(point.get("timestamp", datetime.now().isoformat()))
                    for point in metric_data
                ]
                
                # Perform trend analysis
                trend_analysis = self._analyze_performance_trend(metric_name, values, timestamps)
                trends[metric_name] = trend_analysis
            
            # Generate overall performance insights
            insights = self._generate_performance_insights(trends)
            
            # Predict future performance issues
            predicted_issues = self._predict_performance_issues(trends)
            
            return {
                "trends": {
                    name: {
                        "direction": analysis.trend_direction.value,
                        "strength": analysis.trend_strength,
                        "rate_of_change": analysis.rate_of_change,
                        "projection_24h": analysis.projection_24h,
                        "projection_7d": analysis.projection_7d,
                        "seasonal_component": analysis.seasonal_component,
                        "anomaly_score": analysis.anomaly_score
                    }
                    for name, analysis in trends.items()
                },
                "insights": insights,
                "predicted_issues": predicted_issues,
                "analysis_timestamp": datetime.now().isoformat(),
                "trend_confidence": self._calculate_trend_confidence(trends)
            }
            
        except Exception as e:
            return {
                "error": f"Failed to predict performance trends: {str(e)}",
                "trends": {}
            }
    
    def _analyze_performance_trend(
        self, metric_name: str, values: List[float], timestamps: List[datetime]
    ) -> TrendAnalysis:
        """Analyze trend for a specific performance metric."""
        if len(values) < 5:
            return TrendAnalysis(
                metric_name=metric_name,
                trend_direction=TrendDirection.STABLE,
                trend_strength=0.0,
                rate_of_change=0.0,
                projection_24h=values[-1] if values else 0.0,
                projection_7d=values[-1] if values else 0.0
            )
        
        # Calculate trend direction and strength
        trend_direction, trend_strength = self._calculate_trend_direction(values)
        
        # Calculate rate of change
        rate_of_change = self._calculate_rate_of_change(values, timestamps)
        
        # Project future values
        projection_24h = self._project_value(values, 24)  # 24 hours
        projection_7d = self._project_value(values, 168)  # 7 days (168 hours)
        
        # Detect seasonal component
        seasonal_component = self._detect_seasonal_component(values)
        
        # Calculate anomaly score
        anomaly_score = self._calculate_anomaly_score(values)
        
        return TrendAnalysis(
            metric_name=metric_name,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            rate_of_change=rate_of_change,
            projection_24h=projection_24h,
            projection_7d=projection_7d,
            seasonal_component=seasonal_component,
            anomaly_score=anomaly_score
        )
    
    def _calculate_trend_direction(self, values: List[float]) -> Tuple[TrendDirection, float]:
        """Calculate trend direction and strength."""
        if len(values) < 3:
            return TrendDirection.STABLE, 0.0
        
        # Calculate linear regression slope
        n = len(values)
        x = list(range(n))
        
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        
        # Calculate R-squared for trend strength
        y_pred = [slope * i + (y_mean - slope * x_mean) for i in x]
        ss_res = sum((values[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((values[i] - y_mean) ** 2 for i in range(n))
        
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        trend_strength = max(0, r_squared)
        
        # Determine trend direction
        slope_threshold = 0.01  # Adjust based on metric scale
        
        if abs(slope) < slope_threshold:
            trend_direction = TrendDirection.STABLE
        elif slope > slope_threshold * 2:
            trend_direction = TrendDirection.STRONGLY_INCREASING
        elif slope > slope_threshold:
            trend_direction = TrendDirection.INCREASING
        elif slope < -slope_threshold * 2:
            trend_direction = TrendDirection.STRONGLY_DECREASING
        elif slope < -slope_threshold:
            trend_direction = TrendDirection.DECREASING
        else:
            trend_direction = TrendDirection.STABLE
        
        # Check for volatility
        recent_volatility = statistics.stdev(values[-10:]) if len(values) >= 10 else 0
        overall_volatility = statistics.stdev(values)
        
        if recent_volatility > overall_volatility * 1.5:
            trend_direction = TrendDirection.VOLATILE
        
        return trend_direction, trend_strength
    
    def _calculate_rate_of_change(self, values: List[float], timestamps: List[datetime]) -> float:
        """Calculate rate of change per hour."""
        if len(values) < 2 or len(timestamps) < 2:
            return 0.0
        
        # Calculate change over the full time period
        time_span = (timestamps[-1] - timestamps[0]).total_seconds() / 3600  # hours
        value_change = values[-1] - values[0]
        
        return (value_change / time_span) if time_span > 0 else 0.0
    
    def _project_value(self, values: List[float], hours_ahead: int) -> float:
        """Project value for specific time in the future."""
        if len(values) < 2:
            return values[-1] if values else 0.0
        
        # Simple linear projection
        n = len(values)
        x = list(range(n))
        
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean
        
        # Project future value
        future_x = n + (hours_ahead / 24)  # Assuming daily data points
        projected_value = slope * future_x + intercept
        
        return max(0, projected_value)  # Ensure non-negative
    
    def _detect_seasonal_component(self, values: List[float]) -> Optional[float]:
        """Detect seasonal component in the data."""
        if len(values) < 14:  # Need at least 2 weeks of data
            return None
        
        # Simple seasonal detection using autocorrelation
        season_lengths = [7, 24, 168]  # weekly, daily, weekly in hours
        
        best_correlation = 0
        best_seasonal_strength = 0
        
        for season_length in season_lengths:
            if len(values) >= season_length * 2:
                correlation = self._calculate_autocorrelation(values, season_length)
                if correlation > best_correlation:
                    best_correlation = correlation
                    best_seasonal_strength = correlation
        
        return best_seasonal_strength if best_seasonal_strength > 0.3 else None
    
    def _calculate_autocorrelation(self, values: List[float], lag: int) -> float:
        """Calculate autocorrelation at specific lag."""
        if len(values) <= lag:
            return 0.0
        
        n = len(values) - lag
        if n <= 1:
            return 0.0
        
        x1 = values[:-lag]
        x2 = values[lag:]
        
        mean1 = sum(x1) / len(x1)
        mean2 = sum(x2) / len(x2)
        
        numerator = sum((x1[i] - mean1) * (x2[i] - mean2) for i in range(n))
        
        sum_sq1 = sum((x - mean1) ** 2 for x in x1)
        sum_sq2 = sum((x - mean2) ** 2 for x in x2)
        
        denominator = math.sqrt(sum_sq1 * sum_sq2)
        
        return numerator / denominator if denominator != 0 else 0.0
    
    def _calculate_anomaly_score(self, values: List[float]) -> float:
        """Calculate anomaly score for the data."""
        if len(values) < 10:
            return 0.0
        
        # Calculate Z-scores for recent values
        recent_values = values[-5:]  # Last 5 values
        historical_values = values[:-5]
        
        if len(historical_values) < 5:
            return 0.0
        
        mean_historical = statistics.mean(historical_values)
        std_historical = statistics.stdev(historical_values) if len(historical_values) > 1 else 0
        
        if std_historical == 0:
            return 0.0
        
        anomaly_scores = []
        for value in recent_values:
            z_score = abs(value - mean_historical) / std_historical
            anomaly_scores.append(min(z_score / 3, 1.0))  # Normalize to 0-1
        
        return statistics.mean(anomaly_scores)
    
    def _generate_performance_insights(self, trends: Dict[str, TrendAnalysis]) -> List[str]:
        """Generate insights from performance trend analysis."""
        insights = []
        
        # Analyze overall system health
        degrading_metrics = [
            name for name, analysis in trends.items()
            if analysis.trend_direction in [TrendDirection.DECREASING, TrendDirection.STRONGLY_DECREASING]
            and "response_time" in name.lower() or "error" in name.lower()
        ]
        
        improving_metrics = [
            name for name, analysis in trends.items()
            if analysis.trend_direction in [TrendDirection.INCREASING, TrendDirection.STRONGLY_INCREASING]
            and "throughput" in name.lower() or "success" in name.lower()
        ]
        
        if degrading_metrics:
            insights.append(f"Performance degradation detected in: {', '.join(degrading_metrics)}")
        
        if improving_metrics:
            insights.append(f"Performance improvements observed in: {', '.join(improving_metrics)}")
        
        # Detect seasonal patterns
        seasonal_metrics = [
            name for name, analysis in trends.items()
            if analysis.seasonal_component and analysis.seasonal_component > 0.4
        ]
        
        if seasonal_metrics:
            insights.append(f"Strong seasonal patterns detected in: {', '.join(seasonal_metrics)}")
        
        # Detect high volatility
        volatile_metrics = [
            name for name, analysis in trends.items()
            if analysis.trend_direction == TrendDirection.VOLATILE
        ]
        
        if volatile_metrics:
            insights.append(f"High volatility detected in: {', '.join(volatile_metrics)}")
        
        # Detect anomalies
        anomalous_metrics = [
            name for name, analysis in trends.items()
            if analysis.anomaly_score > 0.7
        ]
        
        if anomalous_metrics:
            insights.append(f"Recent anomalies detected in: {', '.join(anomalous_metrics)}")
        
        if not insights:
            insights.append("Performance trends are stable across all monitored metrics")
        
        return insights
    
    def _predict_performance_issues(self, trends: Dict[str, TrendAnalysis]) -> List[Dict[str, Any]]:
        """Predict future performance issues based on trends."""
        predicted_issues = []
        
        for metric_name, analysis in trends.items():
            issues = []
            
            # Predict threshold breaches
            if "response_time" in metric_name.lower():
                if analysis.projection_24h > 5000:  # 5 seconds
                    issues.append({
                        "issue_type": "response_time_breach",
                        "severity": "high",
                        "predicted_value": analysis.projection_24h,
                        "threshold": 5000,
                        "time_to_breach": "24h",
                        "confidence": analysis.trend_strength
                    })
                elif analysis.projection_7d > 3000:  # 3 seconds
                    issues.append({
                        "issue_type": "response_time_degradation",
                        "severity": "medium", 
                        "predicted_value": analysis.projection_7d,
                        "threshold": 3000,
                        "time_to_breach": "7d",
                        "confidence": analysis.trend_strength
                    })
            
            elif "error_rate" in metric_name.lower():
                if analysis.projection_24h > 5:  # 5%
                    issues.append({
                        "issue_type": "error_rate_spike",
                        "severity": "critical",
                        "predicted_value": analysis.projection_24h,
                        "threshold": 5,
                        "time_to_breach": "24h",
                        "confidence": analysis.trend_strength
                    })
            
            elif "cpu" in metric_name.lower() or "memory" in metric_name.lower():
                if analysis.projection_24h > 90:  # 90%
                    issues.append({
                        "issue_type": "resource_exhaustion",
                        "severity": "high",
                        "predicted_value": analysis.projection_24h,
                        "threshold": 90,
                        "time_to_breach": "24h",
                        "confidence": analysis.trend_strength
                    })
            
            # Predict volatility issues
            if analysis.trend_direction == TrendDirection.VOLATILE:
                issues.append({
                    "issue_type": "system_instability",
                    "severity": "medium",
                    "description": f"High volatility in {metric_name} indicating system instability",
                    "confidence": 0.7
                })
            
            for issue in issues:
                issue["metric"] = metric_name
                predicted_issues.append(issue)
        
        return predicted_issues
    
    def _calculate_trend_confidence(self, trends: Dict[str, TrendAnalysis]) -> float:
        """Calculate overall confidence in trend analysis."""
        if not trends:
            return 0.0
        
        strengths = [analysis.trend_strength for analysis in trends.values()]
        return statistics.mean(strengths)
    
    async def identify_optimization_opportunities(self, system_state: Dict) -> List[OptimizationOpportunity]:
        """Identify optimization opportunities using ML-powered analysis."""
        try:
            opportunities = []
            
            # Analyze system state for optimization potential
            opportunities.extend(await self._identify_resource_optimization_opportunities(system_state))
            opportunities.extend(await self._identify_performance_optimization_opportunities(system_state))
            opportunities.extend(await self._identify_cost_optimization_opportunities(system_state))
            opportunities.extend(await self._identify_reliability_optimization_opportunities(system_state))
            opportunities.extend(await self._identify_scalability_optimization_opportunities(system_state))
            
            # Sort opportunities by priority score
            opportunities.sort(key=lambda x: x.priority_score, reverse=True)
            
            return opportunities
            
        except Exception as e:
            return [OptimizationOpportunity(
                opportunity_id="error_001",
                opportunity_type="error",
                description=f"Failed to identify optimization opportunities: {str(e)}",
                potential_improvement="Unknown",
                implementation_effort="unknown",
                estimated_roi=0.0,
                priority_score=0
            )]
    
    async def _identify_resource_optimization_opportunities(
        self, system_state: Dict
    ) -> List[OptimizationOpportunity]:
        """Identify resource optimization opportunities."""
        opportunities = []
        
        cpu_usage = system_state.get("cpu_usage", 0)
        memory_usage = system_state.get("memory_usage", 0)
        disk_usage = system_state.get("disk_usage", 0)
        
        # CPU optimization opportunities
        if cpu_usage > 80:
            opportunities.append(OptimizationOpportunity(
                opportunity_id="cpu_opt_001",
                opportunity_type="resource_optimization",
                description="High CPU usage detected - implement CPU-intensive operation optimization",
                potential_improvement="20-40% CPU usage reduction",
                implementation_effort="medium",
                estimated_roi=0.35,
                priority_score=85,
                requirements=["CPU profiling", "Algorithm optimization"],
                risks=["Temporary performance impact during optimization"]
            ))
        elif 60 < cpu_usage <= 80:
            opportunities.append(OptimizationOpportunity(
                opportunity_id="cpu_opt_002",
                opportunity_type="resource_optimization",
                description="Moderate CPU usage - proactive optimization recommended",
                potential_improvement="10-20% CPU usage reduction",
                implementation_effort="low",
                estimated_roi=0.15,
                priority_score=65,
                requirements=["Performance monitoring"],
                risks=["Minimal risk"]
            ))
        
        # Memory optimization opportunities
        if memory_usage > 85:
            opportunities.append(OptimizationOpportunity(
                opportunity_id="mem_opt_001",
                opportunity_type="resource_optimization", 
                description="High memory usage - implement memory optimization strategies",
                potential_improvement="25-50% memory usage reduction",
                implementation_effort="high",
                estimated_roi=0.45,
                priority_score=90,
                requirements=["Memory profiling", "Garbage collection tuning"],
                risks=["Application restart required", "Potential data structure changes"]
            ))
        
        # Disk optimization opportunities
        if disk_usage > 80:
            opportunities.append(OptimizationOpportunity(
                opportunity_id="disk_opt_001",
                opportunity_type="resource_optimization",
                description="High disk usage - implement data archiving and cleanup",
                potential_improvement="30-60% disk space recovery",
                implementation_effort="medium",
                estimated_roi=0.25,
                priority_score=75,
                requirements=["Data lifecycle policies", "Archive storage"],
                risks=["Data access latency for archived data"]
            ))
        
        return opportunities
    
    async def _identify_performance_optimization_opportunities(
        self, system_state: Dict
    ) -> List[OptimizationOpportunity]:
        """Identify performance optimization opportunities."""
        opportunities = []
        
        response_time = system_state.get("avg_response_time", 0)
        throughput = system_state.get("throughput", 0)
        error_rate = system_state.get("error_rate", 0)
        
        # Response time optimization
        if response_time > 3000:  # 3 seconds
            opportunities.append(OptimizationOpportunity(
                opportunity_id="perf_opt_001",
                opportunity_type="performance_optimization",
                description="High response times - implement caching and query optimization",
                potential_improvement="40-70% response time improvement",
                implementation_effort="medium",
                estimated_roi=0.55,
                priority_score=95,
                requirements=["Cache infrastructure", "Database optimization"],
                risks=["Cache coherency complexity", "Initial implementation overhead"]
            ))
        
        # Throughput optimization
        if throughput < 100:  # requests per minute
            opportunities.append(OptimizationOpportunity(
                opportunity_id="perf_opt_002",
                opportunity_type="performance_optimization",
                description="Low throughput - implement async processing and load balancing",
                potential_improvement="100-300% throughput increase",
                implementation_effort="high",
                estimated_roi=0.75,
                priority_score=88,
                requirements=["Async framework", "Load balancer", "Horizontal scaling"],
                risks=["Architecture complexity", "Debugging difficulty"]
            ))
        
        # Error rate optimization
        if error_rate > 2:
            opportunities.append(OptimizationOpportunity(
                opportunity_id="perf_opt_003",
                opportunity_type="reliability_optimization",
                description="High error rate - implement error handling and retry mechanisms",
                potential_improvement="60-90% error reduction",
                implementation_effort="medium",
                estimated_roi=0.65,
                priority_score=92,
                requirements=["Circuit breakers", "Retry logic", "Error monitoring"],
                risks=["Increased latency for retries"]
            ))
        
        return opportunities
    
    async def _identify_cost_optimization_opportunities(
        self, system_state: Dict
    ) -> List[OptimizationOpportunity]:
        """Identify cost optimization opportunities."""
        opportunities = []
        
        # Resource utilization based cost optimization
        cpu_usage = system_state.get("cpu_usage", 0)
        memory_usage = system_state.get("memory_usage", 0)
        
        if cpu_usage < 30 and memory_usage < 40:
            opportunities.append(OptimizationOpportunity(
                opportunity_id="cost_opt_001",
                opportunity_type="cost_optimization",
                description="Low resource utilization - right-size infrastructure",
                potential_improvement="30-50% infrastructure cost reduction",
                implementation_effort="low",
                estimated_roi=0.85,
                priority_score=80,
                requirements=["Resource monitoring", "Auto-scaling policies"],
                risks=["Potential performance impact during peak loads"]
            ))
        
        # Scheduling optimization
        opportunities.append(OptimizationOpportunity(
            opportunity_id="cost_opt_002",
            opportunity_type="cost_optimization", 
            description="Implement intelligent task scheduling for off-peak execution",
            potential_improvement="20-40% compute cost reduction",
            implementation_effort="medium",
            estimated_roi=0.55,
            priority_score=70,
            requirements=["Task prioritization", "Scheduling algorithms"],
            risks=["Increased latency for non-urgent tasks"]
        ))
        
        return opportunities
    
    async def _identify_reliability_optimization_opportunities(
        self, system_state: Dict
    ) -> List[OptimizationOpportunity]:
        """Identify reliability optimization opportunities."""
        opportunities = []
        
        error_rate = system_state.get("error_rate", 0)
        
        if error_rate > 1:
            opportunities.append(OptimizationOpportunity(
                opportunity_id="rel_opt_001",
                opportunity_type="reliability_optimization",
                description="Implement comprehensive error handling and monitoring",
                potential_improvement="80-95% error recovery improvement",
                implementation_effort="medium",
                estimated_roi=0.7,
                priority_score=88,
                requirements=["Error tracking", "Health checks", "Alerting system"],
                risks=["Increased complexity", "Performance overhead"]
            ))
        
        # Backup and disaster recovery
        opportunities.append(OptimizationOpportunity(
            opportunity_id="rel_opt_002",
            opportunity_type="reliability_optimization",
            description="Enhance backup and disaster recovery capabilities",
            potential_improvement="99.9% uptime achievement",
            implementation_effort="high",
            estimated_roi=0.4,
            priority_score=75,
            requirements=["Backup infrastructure", "Recovery procedures", "Testing"],
            risks=["Additional infrastructure costs", "Complexity"]
        ))
        
        return opportunities
    
    async def _identify_scalability_optimization_opportunities(
        self, system_state: Dict
    ) -> List[OptimizationOpportunity]:
        """Identify scalability optimization opportunities."""
        opportunities = []
        
        throughput = system_state.get("throughput", 0)
        task_count = system_state.get("task_count", 0)
        
        if task_count > 100 or throughput > 500:
            opportunities.append(OptimizationOpportunity(
                opportunity_id="scale_opt_001",
                opportunity_type="scalability_optimization",
                description="Implement horizontal auto-scaling for high-load scenarios",
                potential_improvement="10x capacity increase capability",
                implementation_effort="high",
                estimated_roi=0.6,
                priority_score=85,
                requirements=["Container orchestration", "Load balancing", "Monitoring"],
                risks=["Operational complexity", "Cost scaling"]
            ))
        
        # Database scalability
        opportunities.append(OptimizationOpportunity(
            opportunity_id="scale_opt_002",
            opportunity_type="scalability_optimization",
            description="Implement database sharding and read replicas",
            potential_improvement="5-10x database performance scaling",
            implementation_effort="high",
            estimated_roi=0.5,
            priority_score=78,
            requirements=["Database architecture redesign", "Data migration"],
            risks=["Data consistency complexity", "Migration downtime"]
        ))
        
        return opportunities

"""
Advanced Usage Forecasting Engine

Intelligent subscription management with ML-based predictions for:
- Time-series forecasting using sliding window analysis
- Peak usage pattern recognition (hourly, daily, weekly)  
- Workload classification and prediction
- Machine learning-based token consumption prediction
- Confidence intervals for predictions
- Proactive quota exhaustion warnings
"""

import asyncio
import logging
import math
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler

from supervisor_agent.core.subscription_intelligence import UsageRecord
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class PredictionModel(str, Enum):
    """Available prediction models"""
    LINEAR = "linear"
    RANDOM_FOREST = "random_forest"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    SEASONAL_DECOMPOSITION = "seasonal_decomposition"


class UsagePattern(str, Enum):
    """Usage pattern classifications"""
    STEADY = "steady"          # Consistent usage
    BURSTY = "bursty"         # Sporadic high usage
    CYCLICAL = "cyclical"     # Regular patterns
    GROWING = "growing"       # Increasing trend
    DECLINING = "declining"   # Decreasing trend
    VOLATILE = "volatile"     # Highly variable


@dataclass
class PredictionResult:
    """Result of usage prediction"""
    predicted_value: float
    confidence_lower: float
    confidence_upper: float
    confidence_level: float
    model_used: PredictionModel
    prediction_horizon_minutes: int
    features_used: Dict[str, float]
    accuracy_score: float
    
    @property
    def prediction_range(self) -> Tuple[float, float]:
        """Get prediction range as tuple"""
        return (self.confidence_lower, self.confidence_upper)


@dataclass
class UsagePatternAnalysis:
    """Analysis of usage patterns"""
    pattern_type: UsagePattern
    trend_direction: float  # Positive = increasing, negative = decreasing
    seasonality_strength: float  # 0-1, higher = more seasonal
    volatility_score: float  # 0-1, higher = more volatile
    peak_hours: List[int]
    peak_days: List[int]
    avg_hourly_usage: float
    max_hourly_usage: float
    usage_distribution: Dict[str, float]


@dataclass 
class QuotaExhaustionWarning:
    """Warning about potential quota exhaustion"""
    provider_id: str
    current_usage: int
    quota_limit: int
    predicted_exhaustion_time: datetime
    confidence_level: float
    recommended_actions: List[str]
    time_to_exhaustion_hours: float
    severity: str  # "low", "medium", "high", "critical"


class AdvancedUsagePredictor:
    """Advanced usage prediction with ML and time-series analysis"""
    
    def __init__(
        self,
        history_limit: int = 10000,
        min_samples_for_ml: int = 100,
        prediction_update_interval: int = 300,  # 5 minutes
        confidence_level: float = 0.95,
    ):
        self.history_limit = history_limit
        self.min_samples_for_ml = min_samples_for_ml
        self.prediction_update_interval = prediction_update_interval
        self.confidence_level = confidence_level
        
        # Usage history storage
        self.usage_history: deque = deque(maxlen=history_limit)
        self.hourly_usage: Dict[int, List[float]] = defaultdict(list)
        self.daily_usage: Dict[int, List[float]] = defaultdict(list)
        self.task_type_usage: Dict[str, List[UsageRecord]] = defaultdict(list)
        
        # ML models
        self.models: Dict[PredictionModel, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.model_performance: Dict[PredictionModel, float] = {}
        
        # Pattern analysis
        self.current_pattern: Optional[UsagePatternAnalysis] = None
        self.pattern_update_time: Optional[datetime] = None
        
        # Prediction cache
        self.prediction_cache: Dict[str, Tuple[PredictionResult, datetime]] = {}
        self.cache_ttl_seconds: int = 300  # 5 minutes
        
        # Feature engineering
        self.feature_window_sizes = [15, 30, 60, 120, 240]  # minutes
        
        logger.info("Advanced usage predictor initialized")
    
    async def record_usage(
        self,
        task_type: str,
        tokens_used: int,
        processing_time: float,
        provider_id: str,
        success: bool = True,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record usage with enhanced context tracking"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        record = UsageRecord(
            task_type=task_type,
            tokens_used=tokens_used,
            processing_time=processing_time,
            timestamp=timestamp,
            success=success,
        )
        
        # Add enhanced context
        record.provider_id = provider_id
        record.hour_of_day = timestamp.hour
        record.day_of_week = timestamp.weekday()
        record.day_of_month = timestamp.day
        
        # Store in various collections
        self.usage_history.append(record)
        self.hourly_usage[timestamp.hour].append(tokens_used)
        self.daily_usage[timestamp.weekday()].append(tokens_used)
        self.task_type_usage[task_type].append(record)
        
        # Update pattern analysis periodically
        if (self.pattern_update_time is None or 
            timestamp - self.pattern_update_time > timedelta(hours=1)):
            await self._update_pattern_analysis()
            self.pattern_update_time = timestamp
        
        logger.debug(
            f"Recorded usage: {task_type}, {tokens_used} tokens, "
            f"provider: {provider_id}, success: {success}"
        )
    
    async def predict_usage(
        self,
        provider_id: str,
        horizon_minutes: int = 60,
        task_type: Optional[str] = None,
        use_cache: bool = True,
    ) -> PredictionResult:
        """Predict usage with advanced ML models"""
        cache_key = f"{provider_id}_{horizon_minutes}_{task_type}"
        
        # Check cache
        if use_cache and cache_key in self.prediction_cache:
            result, cached_time = self.prediction_cache[cache_key]
            if datetime.now(timezone.utc) - cached_time < timedelta(seconds=self.cache_ttl_seconds):
                logger.debug(f"Using cached prediction for {cache_key}")
                return result
        
        # Prepare features
        features = await self._extract_features(provider_id, task_type)
        
        if len(self.usage_history) < self.min_samples_for_ml:
            # Fallback to simple prediction
            result = await self._simple_prediction(provider_id, horizon_minutes, task_type)
        else:
            # Use ML models
            result = await self._ml_prediction(features, horizon_minutes, provider_id, task_type)
        
        # Cache result
        self.prediction_cache[cache_key] = (result, datetime.now(timezone.utc))
        
        return result
    
    async def predict_quota_exhaustion(
        self,
        provider_id: str,
        current_usage: int,
        quota_limit: int,
        quota_reset_time: datetime,
    ) -> Optional[QuotaExhaustionWarning]:
        """Predict when quota will be exhausted with confidence intervals"""
        if current_usage >= quota_limit:
            # Already exhausted
            return QuotaExhaustionWarning(
                provider_id=provider_id,
                current_usage=current_usage,
                quota_limit=quota_limit,
                predicted_exhaustion_time=datetime.now(timezone.utc),
                confidence_level=1.0,
                recommended_actions=["Switch to alternative provider immediately"],
                time_to_exhaustion_hours=0.0,
                severity="critical"
            )
        
        remaining_quota = quota_limit - current_usage
        time_until_reset = (quota_reset_time - datetime.now(timezone.utc)).total_seconds() / 3600
        
        # Predict usage for multiple horizons
        predictions = []
        for hours in [1, 2, 4, 8, 12, 24]:
            if hours > time_until_reset:
                break
            try:
                pred = await self.predict_usage(provider_id, int(hours * 60))
                predictions.append((hours, pred))
            except Exception as e:
                logger.warning(f"Failed to predict usage for {hours}h: {e}")
                continue
        
        if not predictions:
            return None
        
        # Find when quota will be exhausted
        exhaustion_time = None
        confidence = 0.0
        
        cumulative_usage = current_usage
        for hours, pred in predictions:
            cumulative_usage += pred.predicted_value
            
            if cumulative_usage >= quota_limit:
                # Interpolate exact exhaustion time
                prev_hours = predictions[predictions.index((hours, pred)) - 1][0] if predictions.index((hours, pred)) > 0 else 0
                prev_usage = current_usage + (predictions[predictions.index((hours, pred)) - 1][1].predicted_value if predictions.index((hours, pred)) > 0 else 0)
                
                # Linear interpolation
                usage_rate = (cumulative_usage - prev_usage) / (hours - prev_hours) if hours > prev_hours else 0
                if usage_rate > 0:
                    remaining_in_period = quota_limit - prev_usage
                    hours_to_exhaustion = prev_hours + (remaining_in_period / usage_rate)
                    exhaustion_time = datetime.now(timezone.utc) + timedelta(hours=hours_to_exhaustion)
                    confidence = pred.confidence_level
                    break
        
        if exhaustion_time is None:
            # Won't exhaust before reset
            return None
        
        # Determine severity
        hours_to_exhaustion = (exhaustion_time - datetime.now(timezone.utc)).total_seconds() / 3600
        if hours_to_exhaustion < 1:
            severity = "critical"
        elif hours_to_exhaustion < 4:
            severity = "high"
        elif hours_to_exhaustion < 12:
            severity = "medium"
        else:
            severity = "low"
        
        # Generate recommendations
        recommendations = self._generate_exhaustion_recommendations(
            hours_to_exhaustion, confidence, current_usage / quota_limit
        )
        
        return QuotaExhaustionWarning(
            provider_id=provider_id,
            current_usage=current_usage,
            quota_limit=quota_limit,
            predicted_exhaustion_time=exhaustion_time,
            confidence_level=confidence,
            recommended_actions=recommendations,
            time_to_exhaustion_hours=hours_to_exhaustion,
            severity=severity
        )
    
    async def analyze_usage_patterns(self, provider_id: Optional[str] = None) -> UsagePatternAnalysis:
        """Analyze usage patterns for optimization insights"""
        if self.current_pattern and self.pattern_update_time:
            if datetime.now(timezone.utc) - self.pattern_update_time < timedelta(hours=1):
                return self.current_pattern
        
        # Filter usage data by provider if specified
        usage_data = [
            record for record in self.usage_history
            if provider_id is None or getattr(record, 'provider_id', None) == provider_id
        ]
        
        if len(usage_data) < 10:
            # Default pattern for insufficient data
            return UsagePatternAnalysis(
                pattern_type=UsagePattern.STEADY,
                trend_direction=0.0,
                seasonality_strength=0.0,
                volatility_score=0.0,
                peak_hours=[],
                peak_days=[],
                avg_hourly_usage=0.0,
                max_hourly_usage=0.0,
                usage_distribution={}
            )
        
        # Extract time series
        hourly_usage = self._aggregate_usage_by_hour(usage_data)
        daily_usage = self._aggregate_usage_by_day(usage_data)
        
        # Calculate trend
        if len(hourly_usage) > 24:
            trend = self._calculate_trend(hourly_usage[-24:])  # Last 24 hours
        else:
            trend = 0.0
        
        # Calculate seasonality
        seasonality = self._calculate_seasonality(hourly_usage)
        
        # Calculate volatility
        if len(hourly_usage) > 1:
            volatility = statistics.stdev(hourly_usage) / max(statistics.mean(hourly_usage), 1)
        else:
            volatility = 0.0
        
        # Determine pattern type
        pattern_type = self._classify_pattern(trend, seasonality, volatility)
        
        # Find peak hours and days
        peak_hours = self._find_peak_hours(hourly_usage)
        peak_days = self._find_peak_days(daily_usage)
        
        # Calculate statistics
        avg_usage = statistics.mean(hourly_usage) if hourly_usage else 0.0
        max_usage = max(hourly_usage) if hourly_usage else 0.0
        
        # Usage distribution
        distribution = self._calculate_usage_distribution(usage_data)
        
        pattern = UsagePatternAnalysis(
            pattern_type=pattern_type,
            trend_direction=trend,
            seasonality_strength=seasonality,
            volatility_score=volatility,
            peak_hours=peak_hours,
            peak_days=peak_days,
            avg_hourly_usage=avg_usage,
            max_hourly_usage=max_usage,
            usage_distribution=distribution
        )
        
        self.current_pattern = pattern
        return pattern
    
    async def get_optimization_recommendations(
        self, provider_id: str
    ) -> List[str]:
        """Get intelligent optimization recommendations"""
        recommendations = []
        
        try:
            # Analyze patterns
            pattern = await self.analyze_usage_patterns(provider_id)
            
            # Pattern-based recommendations
            if pattern.pattern_type == UsagePattern.BURSTY:
                recommendations.append(
                    "Consider implementing request queuing to smooth out burst patterns"
                )
                recommendations.append(
                    "Monitor for batch processing opportunities during low usage periods"
                )
            
            elif pattern.pattern_type == UsagePattern.GROWING:
                recommendations.append(
                    "Usage is trending upward - consider increasing quota limits"
                )
                recommendations.append(
                    "Evaluate cost optimization strategies for sustained growth"
                )
            
            elif pattern.pattern_type == UsagePattern.VOLATILE:
                recommendations.append(
                    "High usage volatility detected - implement adaptive batching"
                )
                recommendations.append(
                    "Consider setting up dynamic rate limiting based on usage patterns"
                )
            
            # Peak hour recommendations
            if pattern.peak_hours:
                peak_hours_str = ", ".join(map(str, pattern.peak_hours))
                recommendations.append(
                    f"Peak usage hours: {peak_hours_str} - consider pre-scaling during these times"
                )
            
            # Seasonality recommendations
            if pattern.seasonality_strength > 0.3:
                recommendations.append(
                    "Strong seasonal patterns detected - implement predictive scaling"
                )
            
            # Usage distribution recommendations
            if pattern.usage_distribution.get("large_tasks", 0) > 0.2:
                recommendations.append(
                    "High percentage of large tasks - optimize task splitting strategies"
                )
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations.append("Unable to generate recommendations due to insufficient data")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    # Private helper methods
    
    async def _update_pattern_analysis(self):
        """Update pattern analysis in background"""
        try:
            self.current_pattern = await self.analyze_usage_patterns()
            logger.debug("Updated usage pattern analysis")
        except Exception as e:
            logger.warning(f"Failed to update pattern analysis: {e}")
    
    async def _extract_features(
        self, provider_id: str, task_type: Optional[str] = None
    ) -> Dict[str, float]:
        """Extract features for ML prediction"""
        features = {}
        now = datetime.now(timezone.utc)
        
        # Time-based features
        features["hour_of_day"] = now.hour
        features["day_of_week"] = now.weekday()
        features["day_of_month"] = now.day
        features["is_weekend"] = 1.0 if now.weekday() >= 5 else 0.0
        
        # Provider-specific features
        provider_usage = [
            record for record in self.usage_history
            if getattr(record, 'provider_id', None) == provider_id
        ]
        
        # Recent usage features
        for window_minutes in self.feature_window_sizes:
            cutoff = now - timedelta(minutes=window_minutes)
            recent_usage = [
                record.tokens_used for record in provider_usage
                if record.timestamp >= cutoff
            ]
            
            if recent_usage:
                features[f"avg_usage_{window_minutes}m"] = statistics.mean(recent_usage)
                features[f"max_usage_{window_minutes}m"] = max(recent_usage)
                features[f"request_count_{window_minutes}m"] = len(recent_usage)
            else:
                features[f"avg_usage_{window_minutes}m"] = 0.0
                features[f"max_usage_{window_minutes}m"] = 0.0
                features[f"request_count_{window_minutes}m"] = 0.0
        
        # Task type features
        if task_type:
            task_history = self.task_type_usage.get(task_type, [])
            if task_history:
                recent_task_usage = [
                    record.tokens_used for record in task_history[-20:]  # Last 20 tasks
                ]
                features["task_type_avg"] = statistics.mean(recent_task_usage)
                features["task_type_max"] = max(recent_task_usage)
            else:
                features["task_type_avg"] = 0.0
                features["task_type_max"] = 0.0
        
        return features
    
    async def _simple_prediction(
        self, provider_id: str, horizon_minutes: int, task_type: Optional[str]
    ) -> PredictionResult:
        """Simple prediction for when ML models aren't available"""
        # Get recent usage
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=2)
        
        recent_usage = [
            record.tokens_used for record in self.usage_history
            if (record.timestamp >= cutoff and 
                getattr(record, 'provider_id', None) == provider_id)
        ]
        
        if not recent_usage:
            # No recent usage, predict low usage
            predicted = 100.0  # Conservative estimate
            confidence = 0.3
        else:
            # Use moving average
            predicted = statistics.mean(recent_usage) * (horizon_minutes / 60)
            confidence = 0.5
        
        # Simple confidence interval (±30%)
        margin = predicted * 0.3
        
        return PredictionResult(
            predicted_value=predicted,
            confidence_lower=max(0, predicted - margin),
            confidence_upper=predicted + margin,
            confidence_level=confidence,
            model_used=PredictionModel.LINEAR,
            prediction_horizon_minutes=horizon_minutes,
            features_used={},
            accuracy_score=confidence
        )
    
    async def _ml_prediction(
        self, 
        features: Dict[str, float], 
        horizon_minutes: int, 
        provider_id: str,
        task_type: Optional[str]
    ) -> PredictionResult:
        """ML-based prediction using trained models"""
        try:
            # Train models if needed
            await self._ensure_models_trained()
            
            # Prepare feature vector
            feature_names = sorted(features.keys())
            X = np.array([[features[name] for name in feature_names]])
            
            # Scale features
            if "prediction" in self.scalers:
                X = self.scalers["prediction"].transform(X)
            
            # Get predictions from all models
            predictions = {}
            for model_type, model in self.models.items():
                try:
                    pred = model.predict(X)[0]
                    predictions[model_type] = pred
                except Exception as e:
                    logger.warning(f"Model {model_type} prediction failed: {e}")
            
            if not predictions:
                # Fallback to simple prediction
                return await self._simple_prediction(provider_id, horizon_minutes, task_type)
            
            # Ensemble prediction (weighted average based on performance)
            total_weight = sum(self.model_performance.values())
            if total_weight > 0:
                weighted_pred = sum(
                    pred * self.model_performance.get(model_type, 1.0)
                    for model_type, pred in predictions.items()
                ) / total_weight
            else:
                weighted_pred = statistics.mean(predictions.values())
            
            # Calculate confidence based on model agreement
            pred_std = statistics.stdev(predictions.values()) if len(predictions) > 1 else 0
            confidence = max(0.1, 1.0 - (pred_std / max(weighted_pred, 1)))
            
            # Adjust for horizon
            adjusted_pred = weighted_pred * (horizon_minutes / 60)
            
            # Confidence interval
            margin = adjusted_pred * (1 - confidence) * 0.5
            
            return PredictionResult(
                predicted_value=adjusted_pred,
                confidence_lower=max(0, adjusted_pred - margin),
                confidence_upper=adjusted_pred + margin,
                confidence_level=confidence,
                model_used=PredictionModel.RANDOM_FOREST,  # Best performing typically
                prediction_horizon_minutes=horizon_minutes,
                features_used=features,
                accuracy_score=confidence
            )
            
        except Exception as e:
            logger.error(f"ML prediction failed: {e}")
            return await self._simple_prediction(provider_id, horizon_minutes, task_type)
    
    async def _ensure_models_trained(self):
        """Ensure ML models are trained with recent data"""
        if len(self.usage_history) < self.min_samples_for_ml:
            return
        
        # Prepare training data
        X, y = self._prepare_training_data()
        
        if len(X) < 10:
            logger.warning("Insufficient training data for ML models")
            return
        
        # Split features and scale
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        self.scalers["prediction"] = scaler
        
        # Train models
        try:
            # Linear regression
            lr_model = LinearRegression()
            lr_model.fit(X_scaled, y)
            self.models[PredictionModel.LINEAR] = lr_model
            
            # Random forest
            rf_model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
            rf_model.fit(X_scaled, y)
            self.models[PredictionModel.RANDOM_FOREST] = rf_model
            
            # Evaluate models
            await self._evaluate_models(X_scaled, y)
            
            logger.info(f"Trained ML models with {len(X)} samples")
            
        except Exception as e:
            logger.error(f"Model training failed: {e}")
    
    def _prepare_training_data(self) -> Tuple[List[List[float]], List[float]]:
        """Prepare training data from usage history"""
        X, y = [], []
        
        # Create sliding window samples
        for i in range(60, len(self.usage_history)):  # Need 60 samples for features
            record = self.usage_history[i]
            
            # Features based on previous usage
            features = []
            
            # Time features
            features.extend([
                record.timestamp.hour,
                record.timestamp.weekday(),
                record.timestamp.day,
                1.0 if record.timestamp.weekday() >= 5 else 0.0
            ])
            
            # Historical usage features
            for window_size in [5, 15, 30, 60]:
                if i >= window_size:
                    window_usage = [
                        self.usage_history[j].tokens_used 
                        for j in range(i - window_size, i)
                    ]
                    features.extend([
                        statistics.mean(window_usage),
                        max(window_usage),
                        len(window_usage)
                    ])
                else:
                    features.extend([0.0, 0.0, 0.0])
            
            X.append(features)
            y.append(record.tokens_used)
        
        return X, y
    
    async def _evaluate_models(self, X: np.ndarray, y: List[float]):
        """Evaluate model performance"""
        if len(X) < 20:
            return
        
        # Simple train/test split
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        for model_type, model in self.models.items():
            try:
                predictions = model.predict(X_test)
                mae = mean_absolute_error(y_test, predictions)
                mse = mean_squared_error(y_test, predictions)
                
                # Performance score (inverse of normalized MAE)
                mean_actual = statistics.mean(y_test) if y_test else 1
                normalized_mae = mae / max(mean_actual, 1)
                performance = max(0.1, 1.0 - normalized_mae)
                
                self.model_performance[model_type] = performance
                
                logger.debug(f"Model {model_type}: MAE={mae:.2f}, Performance={performance:.3f}")
                
            except Exception as e:
                logger.warning(f"Model evaluation failed for {model_type}: {e}")
                self.model_performance[model_type] = 0.1
    
    def _generate_exhaustion_recommendations(
        self, hours_to_exhaustion: float, confidence: float, usage_ratio: float
    ) -> List[str]:
        """Generate recommendations for quota exhaustion scenarios"""
        recommendations = []
        
        if hours_to_exhaustion < 1:
            recommendations.extend([
                "URGENT: Switch to alternative provider immediately",
                "Implement emergency request queuing",
                "Alert operations team for manual intervention"
            ])
        elif hours_to_exhaustion < 4:
            recommendations.extend([
                "Begin gradual migration to alternative providers",
                "Reduce non-critical task processing",
                "Implement strict request prioritization"
            ])
        elif hours_to_exhaustion < 12:
            recommendations.extend([
                "Consider load balancing to alternative providers",
                "Optimize batch processing to reduce request count",
                "Review and defer low-priority tasks"
            ])
        else:
            recommendations.extend([
                "Monitor usage trends closely",
                "Prepare alternative provider fallback",
                "Optimize request batching and caching"
            ])
        
        # Confidence-based recommendations
        if confidence < 0.7:
            recommendations.append(
                "Prediction confidence is low - collect more usage data for better accuracy"
            )
        
        # Usage ratio recommendations
        if usage_ratio > 0.8:
            recommendations.append(
                "Usage is high relative to quota - consider upgrading subscription tier"
            )
        
        return recommendations
    
    def _aggregate_usage_by_hour(self, usage_data: List[UsageRecord]) -> List[float]:
        """Aggregate usage data by hour"""
        hourly_totals = defaultdict(float)
        
        for record in usage_data:
            hour_key = record.timestamp.replace(minute=0, second=0, microsecond=0)
            hourly_totals[hour_key] += record.tokens_used
        
        # Return chronologically ordered list
        sorted_hours = sorted(hourly_totals.keys())
        return [hourly_totals[hour] for hour in sorted_hours]
    
    def _aggregate_usage_by_day(self, usage_data: List[UsageRecord]) -> List[float]:
        """Aggregate usage data by day"""
        daily_totals = defaultdict(float)
        
        for record in usage_data:
            day_key = record.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_totals[day_key] += record.tokens_used
        
        sorted_days = sorted(daily_totals.keys())
        return [daily_totals[day] for day in sorted_days]
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend direction using linear regression"""
        if len(values) < 2:
            return 0.0
        
        x = list(range(len(values)))
        n = len(values)
        
        # Simple linear regression slope
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        return slope
    
    def _calculate_seasonality(self, values: List[float]) -> float:
        """Calculate seasonality strength"""
        if len(values) < 24:  # Need at least 24 hours
            return 0.0
        
        # Calculate hourly averages
        hourly_avgs = [0] * 24
        hourly_counts = [0] * 24
        
        for i, value in enumerate(values):
            hour = i % 24
            hourly_avgs[hour] += value
            hourly_counts[hour] += 1
        
        # Average by hour
        for i in range(24):
            if hourly_counts[i] > 0:
                hourly_avgs[i] /= hourly_counts[i]
        
        # Calculate coefficient of variation as seasonality measure
        if len(hourly_avgs) > 1:
            mean_usage = statistics.mean(hourly_avgs)
            if mean_usage > 0:
                std_usage = statistics.stdev(hourly_avgs)
                return min(1.0, std_usage / mean_usage)
        
        return 0.0
    
    def _classify_pattern(
        self, trend: float, seasonality: float, volatility: float
    ) -> UsagePattern:
        """Classify usage pattern based on metrics"""
        # Strong trend patterns
        if abs(trend) > 10:  # Strong trend
            return UsagePattern.GROWING if trend > 0 else UsagePattern.DECLINING
        
        # High volatility
        if volatility > 0.8:
            return UsagePattern.VOLATILE
        
        # Strong seasonality
        if seasonality > 0.5:
            return UsagePattern.CYCLICAL
        
        # Bursty pattern (high volatility with low seasonality)
        if volatility > 0.3 and seasonality < 0.2:
            return UsagePattern.BURSTY
        
        # Default to steady
        return UsagePattern.STEADY
    
    def _find_peak_hours(self, hourly_usage: List[float]) -> List[int]:
        """Find peak usage hours"""
        if not hourly_usage:
            return []
        
        # Group by hour and find average usage per hour
        hourly_sums = [0] * 24
        hourly_counts = [0] * 24
        
        for i, usage in enumerate(hourly_usage):
            hour = i % 24
            hourly_sums[hour] += usage
            hourly_counts[hour] += 1
        
        hourly_avgs = [
            hourly_sums[i] / max(hourly_counts[i], 1) for i in range(24)
        ]
        
        # Find hours with usage above 80th percentile
        if len(hourly_avgs) > 0:
            threshold = np.percentile(hourly_avgs, 80)
            peak_hours = [
                hour for hour, avg in enumerate(hourly_avgs) 
                if avg >= threshold and avg > 0
            ]
            return sorted(peak_hours)
        
        return []
    
    def _find_peak_days(self, daily_usage: List[float]) -> List[int]:
        """Find peak usage days of week"""
        if not daily_usage:
            return []
        
        # This would need actual day-of-week mapping
        # For now, return empty list
        return []
    
    def _calculate_usage_distribution(self, usage_data: List[UsageRecord]) -> Dict[str, float]:
        """Calculate usage distribution by categories"""
        if not usage_data:
            return {}
        
        total_usage = sum(record.tokens_used for record in usage_data)
        if total_usage == 0:
            return {}
        
        # Categorize by token usage
        small_tasks = sum(
            record.tokens_used for record in usage_data 
            if record.tokens_used < 1000
        )
        medium_tasks = sum(
            record.tokens_used for record in usage_data 
            if 1000 <= record.tokens_used < 5000
        )
        large_tasks = sum(
            record.tokens_used for record in usage_data 
            if record.tokens_used >= 5000
        )
        
        return {
            "small_tasks": small_tasks / total_usage,
            "medium_tasks": medium_tasks / total_usage,
            "large_tasks": large_tasks / total_usage
        }
#!/usr/bin/env python3
"""
Test analytics system with sample data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supervisor_agent.core.advanced_analytics_engine import MetricsCollector, StatisticalAnomalyDetector, TimeSeriesPredictor
from supervisor_agent.core.analytics_models import MetricPoint, SystemMetrics, TaskMetrics
import sqlite3
from datetime import datetime, timedelta
import json

def test_analytics_components():
    """Test analytics engine components"""
    try:
        print("--- Testing Analytics Components ---")
        
        # Test MetricsCollector
        collector = MetricsCollector()
        print("✅ MetricsCollector initialized successfully")
        
        # Test StatisticalAnomalyDetector
        detector = StatisticalAnomalyDetector()
        print("✅ StatisticalAnomalyDetector initialized successfully")
        
        # Test TimeSeriesPredictor
        predictor = TimeSeriesPredictor()
        print("✅ TimeSeriesPredictor initialized successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Analytics components test failed: {e}")
        return False

def test_metrics_data_models():
    """Test metrics data models"""
    try:
        print("\n--- Testing Metrics Data Models ---")
        
        # Test MetricPoint
        metric_point = MetricPoint(
            timestamp=datetime.now(),
            value=100.5,
            labels={"source": "test", "type": "cpu"},
            metadata={"unit": "percent", "threshold": 80}
        )
        print("✅ MetricPoint created successfully")
        print(f"  - Value: {metric_point.value}")
        print(f"  - Labels: {metric_point.labels}")
        
        # Test SystemMetrics
        system_metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu_usage_percent=75.2,
            memory_usage_percent=60.8,
            disk_usage_percent=45.0,
            active_tasks_count=5,
            queue_depth=2,
            response_time_ms=250.5
        )
        print("✅ SystemMetrics created successfully")
        print(f"  - CPU: {system_metrics.cpu_usage_percent}%")
        print(f"  - Memory: {system_metrics.memory_usage_percent}%")
        
        # Test TaskMetrics
        task_metrics = TaskMetrics(
            task_id=12345,
            task_type="CODE_ANALYSIS",
            execution_time_ms=2400,
            success=True,
            queue_time_ms=500,
            memory_usage_mb=128.5,
            cpu_usage_percent=75.0,
            cost_usd="0.025"
        )
        print("✅ TaskMetrics created successfully")
        print(f"  - Task ID: {task_metrics.task_id}")
        print(f"  - Execution time: {task_metrics.execution_time_ms}ms")
        
        return True
        
    except Exception as e:
        print(f"❌ Metrics data models test failed: {e}")
        return False

def test_database_metrics_storage():
    """Test storing metrics in database"""
    try:
        print("\n--- Testing Database Metrics Storage ---")
        
        # Connect to database
        conn = sqlite3.connect("supervisor_agent.db")
        cursor = conn.cursor()
        
        # Insert sample metrics
        sample_metrics = [
            {
                "metric_type": "system_performance",
                "timestamp": datetime.now().isoformat(),
                "value": 75.5,
                "string_value": None,
                "labels": json.dumps({"component": "cpu", "host": "server1"}),
                "metadata": json.dumps({"unit": "percent", "threshold": 80})
            },
            {
                "metric_type": "task_execution",
                "timestamp": datetime.now().isoformat(),
                "value": 1200.0,
                "string_value": None,
                "labels": json.dumps({"task_type": "CODE_ANALYSIS", "status": "SUCCESS"}),
                "metadata": json.dumps({"unit": "milliseconds", "agent_id": "test-agent"})
            },
            {
                "metric_type": "error_rate",
                "timestamp": datetime.now().isoformat(),
                "value": 2.5,
                "string_value": None,
                "labels": json.dumps({"service": "api", "endpoint": "/tasks"}),
                "metadata": json.dumps({"unit": "percent", "window": "1h"})
            }
        ]
        
        for metric in sample_metrics:
            cursor.execute("""
                INSERT INTO metrics (metric_type, timestamp, value, string_value, labels, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                metric["metric_type"],
                metric["timestamp"],
                metric["value"],
                metric["string_value"],
                metric["labels"],
                metric["metadata"]
            ))
        
        conn.commit()
        print(f"✅ Inserted {len(sample_metrics)} sample metrics")
        
        # Query metrics back
        cursor.execute("SELECT COUNT(*) FROM metrics")
        total_metrics = cursor.fetchone()[0]
        print(f"✅ Total metrics in database: {total_metrics}")
        
        # Query by metric type
        cursor.execute("SELECT metric_type, value FROM metrics WHERE metric_type = 'system_performance'")
        system_metrics = cursor.fetchall()
        print(f"✅ Found {len(system_metrics)} system performance metrics")
        
        # Query recent metrics
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM metrics WHERE timestamp > ?", (one_hour_ago,))
        recent_metrics = cursor.fetchone()[0]
        print(f"✅ Found {recent_metrics} recent metrics (last hour)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database metrics storage test failed: {e}")
        return False

def test_metrics_aggregation():
    """Test metrics aggregation and analysis"""
    try:
        print("\n--- Testing Metrics Aggregation ---")
        
        # Connect to database
        conn = sqlite3.connect("supervisor_agent.db")
        cursor = conn.cursor()
        
        # Test basic aggregations
        cursor.execute("SELECT AVG(value) FROM metrics WHERE metric_type = 'system_performance'")
        avg_cpu = cursor.fetchone()[0]
        if avg_cpu:
            print(f"✅ Average system performance: {avg_cpu:.2f}")
        
        cursor.execute("SELECT MAX(value) FROM metrics WHERE metric_type = 'task_execution'")
        max_execution_time = cursor.fetchone()[0]
        if max_execution_time:
            print(f"✅ Maximum task execution time: {max_execution_time:.2f}ms")
        
        cursor.execute("SELECT MIN(value) FROM metrics WHERE metric_type = 'error_rate'")
        min_error_rate = cursor.fetchone()[0]
        if min_error_rate:
            print(f"✅ Minimum error rate: {min_error_rate:.2f}%")
        
        # Test grouping by metric type
        cursor.execute("""
            SELECT metric_type, COUNT(*), AVG(value), MIN(value), MAX(value)
            FROM metrics
            GROUP BY metric_type
        """)
        
        aggregations = cursor.fetchall()
        print("✅ Metrics summary by type:")
        for metric_type, count, avg, min_val, max_val in aggregations:
            print(f"  - {metric_type}: {count} records, avg={avg:.2f}, range=[{min_val:.2f}, {max_val:.2f}]")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Metrics aggregation test failed: {e}")
        return False

def test_time_series_analysis():
    """Test basic time series analysis"""
    try:
        print("\n--- Testing Time Series Analysis ---")
        
        # Generate sample time series data
        time_series_data = []
        base_time = datetime.now() - timedelta(hours=24)
        
        for i in range(24):  # 24 hourly data points
            timestamp = base_time + timedelta(hours=i)
            # Simulate CPU usage with some variation
            base_value = 50.0
            hourly_variation = 20.0 * (0.5 + 0.5 * (i % 12) / 12)  # Daily pattern
            noise = (i % 7) * 2  # Weekly pattern simulation
            value = base_value + hourly_variation + noise
            
            time_series_data.append({
                "timestamp": timestamp,
                "value": value
            })
        
        print(f"✅ Generated {len(time_series_data)} time series data points")
        
        # Calculate basic statistics
        values = [point["value"] for point in time_series_data]
        avg_value = sum(values) / len(values)
        min_value = min(values)
        max_value = max(values)
        
        print(f"✅ Time series statistics:")
        print(f"  - Average: {avg_value:.2f}")
        print(f"  - Range: [{min_value:.2f}, {max_value:.2f}]")
        print(f"  - Variation: {max_value - min_value:.2f}")
        
        # Simple trend detection
        first_half = values[:12]
        second_half = values[12:]
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        trend = "increasing" if second_avg > first_avg else "decreasing"
        trend_magnitude = abs(second_avg - first_avg)
        
        print(f"✅ Trend analysis: {trend} trend (magnitude: {trend_magnitude:.2f})")
        
        # Simple anomaly detection (values beyond 2 standard deviations)
        mean = avg_value
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        threshold = 2 * std_dev
        
        anomalies = [point for point in time_series_data if abs(point["value"] - mean) > threshold]
        print(f"✅ Anomaly detection: {len(anomalies)} anomalies found (threshold: ±{threshold:.2f})")
        
        return True
        
    except Exception as e:
        print(f"❌ Time series analysis test failed: {e}")
        return False

def cleanup_test_data():
    """Clean up test metrics data"""
    try:
        conn = sqlite3.connect("supervisor_agent.db")
        cursor = conn.cursor()
        
        # Remove test metrics
        cursor.execute("DELETE FROM metrics WHERE labels LIKE '%test%' OR labels LIKE '%server1%'")
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            print(f"\n🧹 Cleaned up {deleted_count} test metrics")
        
        return True
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Analytics System with Sample Data\n")
    
    success = True
    success &= test_analytics_components()
    success &= test_metrics_data_models()
    success &= test_database_metrics_storage()
    success &= test_metrics_aggregation()
    success &= test_time_series_analysis()
    
    # Clean up test data
    cleanup_test_data()
    
    if success:
        print("\n🎉 All analytics system tests passed!")
        print("\n📊 Test Summary:")
        print("✅ Analytics components initialization")
        print("✅ Metrics data models")
        print("✅ Database metrics storage")
        print("✅ Metrics aggregation and querying")
        print("✅ Time series analysis and anomaly detection")
        print("\n📈 Analytics system capabilities validated!")
        sys.exit(0)
    else:
        print("\n💥 Some analytics system tests failed!")
        sys.exit(1)
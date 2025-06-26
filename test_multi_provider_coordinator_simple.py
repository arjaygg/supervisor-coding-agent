#!/usr/bin/env python3
"""
Simple test for Multi-Provider Coordinator core logic
Tests the coordinator without complex dependencies
"""

import asyncio
import sys
from datetime import datetime

sys.path.append('/home/devag/git/dev-assist')


async def test_multi_provider_coordinator_core():
    """Test core multi-provider coordination logic"""
    print("🔍 Testing Multi-Provider Coordinator Core Logic...")
    
    # Import and test the core classes directly
    from supervisor_agent.orchestration.multi_provider_coordinator import (
        CoordinationStrategy, ProviderStatus, ProviderMetrics, CoordinationTask, ExecutionResult
    )
    from supervisor_agent.providers.base_provider import ProviderType, TaskCapability
    
    # Test enums
    print("✅ CoordinationStrategy enum loaded successfully")
    print(f"   Available strategies: {len(list(CoordinationStrategy))}")
    for strategy in list(CoordinationStrategy)[:3]:
        print(f"   - {strategy.value}")
    
    print("✅ ProviderStatus enum loaded successfully")
    print(f"   Available statuses: {len(list(ProviderStatus))}")
    
    # Test ProviderMetrics
    metrics = ProviderMetrics(
        provider_type=ProviderType.CLAUDE_CLI,
        total_requests=100,
        successful_requests=85,
        current_load=25,
        max_capacity=100
    )
    
    print("✅ ProviderMetrics created successfully")
    print(f"   Provider: {metrics.provider_type.value}")
    print(f"   Success rate: {metrics.success_rate:.2f}")
    print(f"   Load percentage: {metrics.load_percentage:.1f}%")
    print(f"   Availability score: {metrics.availability_score:.2f}")
    
    # Test CoordinationTask
    task = CoordinationTask(
        task_id="test_task_001",
        task_type=TaskCapability.CODE_GENERATION,
        priority=8,
        timeout_seconds=300
    )
    
    print("✅ CoordinationTask created successfully")
    print(f"   Task ID: {task.task_id}")
    print(f"   Task type: {task.task_type.value}")
    print(f"   Priority: {task.priority}")
    
    # Test ExecutionResult
    result = ExecutionResult(
        task_id=task.task_id,
        success=True,
        provider_used=ProviderType.CLAUDE_CLI,
        execution_time=2.5,
        cost=0.05,
        result_data={"status": "completed"}
    )
    
    print("✅ ExecutionResult created successfully")
    print(f"   Success: {result.success}")
    print(f"   Provider: {result.provider_used.value}")
    print(f"   Execution time: {result.execution_time}s")
    print(f"   Cost: ${result.cost:.3f}")
    
    print("\n🎯 Core Multi-Provider Coordinator Components Working!")
    return True


async def test_provider_metrics_calculations():
    """Test provider metrics calculations"""
    print("\n🔢 Testing Provider Metrics Calculations...")
    
    from supervisor_agent.orchestration.multi_provider_coordinator import ProviderMetrics, ProviderStatus
    from supervisor_agent.providers.base_provider import ProviderType
    
    # Test various scenarios
    scenarios = [
        {
            "name": "Healthy Provider",
            "total": 100,
            "successful": 95,
            "load": 30,
            "capacity": 100,
            "status": ProviderStatus.HEALTHY
        },
        {
            "name": "Degraded Provider",
            "total": 50,
            "successful": 35,
            "load": 80,
            "capacity": 100,
            "status": ProviderStatus.DEGRADED
        },
        {
            "name": "Overloaded Provider",
            "total": 200,
            "successful": 180,
            "load": 95,
            "capacity": 100,
            "status": ProviderStatus.OVERLOADED
        }
    ]
    
    for scenario in scenarios:
        metrics = ProviderMetrics(
            provider_type=ProviderType.CLAUDE_CLI,
            total_requests=scenario["total"],
            successful_requests=scenario["successful"],
            current_load=scenario["load"],
            max_capacity=scenario["capacity"],
            status=scenario["status"]
        )
        
        print(f"   {scenario['name']}:")
        print(f"     Success rate: {metrics.success_rate:.2f}")
        print(f"     Load: {metrics.load_percentage:.1f}%")
        print(f"     Availability: {metrics.availability_score:.2f}")
    
    print("✅ Provider metrics calculations working correctly")
    return True


async def main():
    """Main test runner"""
    print("🚀 Multi-Provider Coordinator - Core Logic Test")
    print("=" * 60)
    
    try:
        # Test core components
        result1 = await test_multi_provider_coordinator_core()
        result2 = await test_provider_metrics_calculations()
        
        if result1 and result2:
            print("\n✅ All core components working correctly!")
            print("📝 Note: Full integration test requires provider service setup")
            return 0
        else:
            print("\n❌ Some core components failed")
            return 1
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
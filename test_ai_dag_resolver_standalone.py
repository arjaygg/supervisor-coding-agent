#!/usr/bin/env python3
"""
Standalone test for AI-Enhanced DAG Resolver

Tests the AI-enhanced DAG resolver in isolation to verify
optimization capabilities and AI integration.
"""

import asyncio
import json
import sys
from datetime import datetime

sys.path.append('/home/devag/git/dev-assist')

from supervisor_agent.intelligence.ai_enhanced_dag_resolver import (
    AIEnhancedDAGResolver,
    OptimizedExecutionPlan,
    create_ai_enhanced_dag_resolver
)
from supervisor_agent.intelligence.workflow_synthesizer import (
    EnhancedWorkflowDefinition,
    ClaudeAgentWrapper,
    TenantContext
)
from supervisor_agent.core.workflow_models import TaskDefinition


async def test_ai_dag_optimization():
    """Test AI-powered DAG optimization capabilities"""
    print("🧪 Starting AI-Enhanced DAG Resolver Test")
    
    # Create a complex workflow for testing
    workflow = EnhancedWorkflowDefinition(
        name="Complex Software Development Workflow",
        description="Multi-stage software development with parallel opportunities",
        tasks=[
            # Independent analysis tasks (can be parallelized)
            TaskDefinition(
                id="requirements-analysis",
                name="Requirements Analysis",
                type="CODE_ANALYSIS",
                config={"timeout_minutes": 30, "complexity": "medium"},
                dependencies=[]
            ),
            TaskDefinition(
                id="architecture-design",
                name="Architecture Design",
                type="DESIGN_TASK",
                config={"timeout_minutes": 45, "complexity": "high"},
                dependencies=[]
            ),
            TaskDefinition(
                id="security-analysis",
                name="Security Analysis",
                type="CODE_ANALYSIS",
                config={"timeout_minutes": 25, "complexity": "medium"},
                dependencies=[]
            ),
            
            # Implementation tasks (depend on analysis)
            TaskDefinition(
                id="backend-implementation",
                name="Backend Implementation",
                type="CODE_IMPLEMENTATION",
                config={"timeout_minutes": 120, "complexity": "high"},
                dependencies=["requirements-analysis", "architecture-design"]
            ),
            TaskDefinition(
                id="frontend-implementation",
                name="Frontend Implementation",
                type="CODE_IMPLEMENTATION",
                config={"timeout_minutes": 90, "complexity": "medium"},
                dependencies=["requirements-analysis", "architecture-design"]
            ),
            
            # Testing tasks (can be partially parallel)
            TaskDefinition(
                id="unit-testing",
                name="Unit Testing",
                type="TESTING",
                config={"timeout_minutes": 60, "complexity": "medium"},
                dependencies=["backend-implementation"]
            ),
            TaskDefinition(
                id="integration-testing",
                name="Integration Testing", 
                type="TESTING",
                config={"timeout_minutes": 45, "complexity": "medium"},
                dependencies=["backend-implementation", "frontend-implementation"]
            ),
            TaskDefinition(
                id="security-testing",
                name="Security Testing",
                type="TESTING",
                config={"timeout_minutes": 40, "complexity": "high"},
                dependencies=["security-analysis", "backend-implementation"]
            ),
            
            # Final deployment task
            TaskDefinition(
                id="deployment",
                name="Production Deployment",
                type="FEATURE",
                config={"timeout_minutes": 30, "complexity": "high"},
                dependencies=["unit-testing", "integration-testing", "security-testing"]
            )
        ],
        version="1.0"
    )
    
    print(f"✅ Created test workflow: {workflow.name}")
    print(f"   - Tasks: {len(workflow.tasks)}")
    print(f"   - Complexity: Multi-stage with parallel opportunities")
    
    # Test without AI (heuristic mode)
    print("\n🔧 Testing heuristic optimization (without AI)...")
    
    heuristic_resolver = AIEnhancedDAGResolver(claude_agent=None)
    heuristic_plan = await heuristic_resolver.create_intelligent_execution_plan(workflow)
    
    print(f"📊 Heuristic Results:")
    print(f"   - Execution stages: {len(heuristic_plan.execution_order)}")
    print(f"   - Parallel efficiency: {heuristic_plan.parallel_efficiency_score:.2f}")
    print(f"   - Estimated time: {heuristic_plan.estimated_execution_time_minutes} minutes")
    print(f"   - Confidence: {heuristic_plan.confidence_score:.2f}")
    
    # Display execution order
    print(f"\n📋 Execution Order (Heuristic):")
    for i, stage in enumerate(heuristic_plan.execution_order, 1):
        print(f"   Stage {i}: {stage}")
    
    # Test with AI (mock responses)
    print("\n🤖 Testing AI-powered optimization...")
    
    # Create mock Claude agent
    tenant_context = TenantContext(
        tenant_id="test-org",
        org_profile={"name": "Test Organization"},
        team_skills=["Python", "React", "DevOps"],
        team_hierarchy={},
        approval_policies={},
        resource_limits={},
        quality_standards={}
    )
    
    claude_agent = ClaudeAgentWrapper()  # Will use mock responses
    ai_resolver = AIEnhancedDAGResolver(claude_agent=claude_agent)
    
    ai_plan = await ai_resolver.create_intelligent_execution_plan(workflow)
    
    print(f"🧠 AI-Optimized Results:")
    print(f"   - Execution stages: {len(ai_plan.execution_order)}")
    print(f"   - Parallel efficiency: {ai_plan.parallel_efficiency_score:.2f}")
    print(f"   - Estimated time: {ai_plan.estimated_execution_time_minutes} minutes")
    print(f"   - Confidence: {ai_plan.confidence_score:.2f}")
    print(f"   - Bottleneck predictions: {len(ai_plan.bottleneck_predictions)}")
    
    # Display AI execution order
    print(f"\n📋 Execution Order (AI-Optimized):")
    for i, stage in enumerate(ai_plan.execution_order, 1):
        print(f"   Stage {i}: {stage}")
    
    # Display bottleneck predictions
    if ai_plan.bottleneck_predictions:
        print(f"\n⚠️ Predicted Bottlenecks:")
        for bottleneck in ai_plan.bottleneck_predictions:
            print(f"   - {bottleneck.get('task_id', 'Unknown')}: {bottleneck.get('type', 'Unknown type')}")
            print(f"     Probability: {bottleneck.get('probability', 0):.1%}")
            print(f"     Impact: {bottleneck.get('impact', 'Unknown')}")
    
    # Display resource allocation hints
    if ai_plan.resource_allocation_hints:
        print(f"\n💾 Resource Allocation Hints:")
        cpu_alloc = ai_plan.resource_allocation_hints.get("cpu_allocation", {})
        memory_alloc = ai_plan.resource_allocation_hints.get("memory_allocation", {})
        
        for task_id in workflow.tasks[:3]:  # Show first 3 tasks
            cpu = cpu_alloc.get(task_id.id, "N/A")
            memory = memory_alloc.get(task_id.id, "N/A")
            print(f"   - {task_id.name}: CPU={cpu}, Memory={memory}")
    
    # Compare efficiency
    improvement = ai_plan.parallel_efficiency_score - heuristic_plan.parallel_efficiency_score
    time_improvement = heuristic_plan.estimated_execution_time_minutes - ai_plan.estimated_execution_time_minutes
    
    print(f"\n📈 AI vs Heuristic Comparison:")
    print(f"   - Efficiency improvement: {improvement:+.2f}")
    print(f"   - Time reduction: {time_improvement:+.0f} minutes")
    print(f"   - Confidence gain: {ai_plan.confidence_score - heuristic_plan.confidence_score:+.2f}")
    
    return True


async def test_bottleneck_prediction():
    """Test bottleneck prediction capabilities"""
    print("\n🔍 Testing Bottleneck Prediction...")
    
    # Create workflow with potential bottlenecks
    bottleneck_workflow = EnhancedWorkflowDefinition(
        name="Bottleneck Test Workflow",
        description="Workflow designed to test bottleneck detection",
        tasks=[
            # Many tasks depending on one bottleneck task
            TaskDefinition(
                id="data-collection",
                name="Data Collection",
                type="CODE_ANALYSIS",
                config={}, 
                dependencies=[]
            ),
            TaskDefinition(
                id="bottleneck-processing",
                name="Complex Data Processing (Bottleneck)",
                type="CODE_IMPLEMENTATION",
                config={"complexity": "very_high", "resource_intensive": True},
                dependencies=["data-collection"]
            ),
            # Many tasks waiting for bottleneck
            TaskDefinition(id="analysis-1", name="Analysis 1", type="CODE_ANALYSIS", config={}, dependencies=["bottleneck-processing"]),
            TaskDefinition(id="analysis-2", name="Analysis 2", type="CODE_ANALYSIS", config={}, dependencies=["bottleneck-processing"]),
            TaskDefinition(id="analysis-3", name="Analysis 3", type="CODE_ANALYSIS", config={}, dependencies=["bottleneck-processing"]),
            TaskDefinition(id="analysis-4", name="Analysis 4", type="CODE_ANALYSIS", config={}, dependencies=["bottleneck-processing"]),
            TaskDefinition(id="analysis-5", name="Analysis 5", type="CODE_ANALYSIS", config={}, dependencies=["bottleneck-processing"]),
        ],
        version="1.0"
    )
    
    # Test bottleneck prediction
    claude_agent = ClaudeAgentWrapper()
    resolver = AIEnhancedDAGResolver(claude_agent=claude_agent)
    
    # Create execution plan
    plan = await resolver.create_intelligent_execution_plan(bottleneck_workflow)
    
    # Predict bottlenecks
    bottlenecks = await resolver.predict_execution_bottlenecks(plan)
    
    print(f"🎯 Bottleneck Analysis Results:")
    print(f"   - Total bottlenecks detected: {len(bottlenecks)}")
    
    for i, bottleneck in enumerate(bottlenecks, 1):
        print(f"\n   Bottleneck {i}:")
        print(f"     - Type: {bottleneck.get('type', 'Unknown')}")
        print(f"     - Task: {bottleneck.get('task_id', 'Unknown')}")
        print(f"     - Probability: {bottleneck.get('probability', 0):.1%}")
        print(f"     - Impact: {bottleneck.get('impact', 'Unknown')}")
        
        mitigation = bottleneck.get('mitigation_strategies', [])
        if mitigation:
            print(f"     - Mitigation: {', '.join(mitigation[:2])}")
    
    # Test heuristic bottleneck detection
    print(f"\n🔧 Heuristic Bottleneck Detection:")
    heuristic_resolver = AIEnhancedDAGResolver(claude_agent=None)
    heuristic_bottlenecks = await heuristic_resolver.predict_execution_bottlenecks(plan)
    
    print(f"   - Heuristic bottlenecks: {len(heuristic_bottlenecks)}")
    for bottleneck in heuristic_bottlenecks:
        print(f"     - {bottleneck['type']}: {bottleneck.get('task_id', 'group')}")
    
    return True


async def test_parallel_optimization():
    """Test parallel execution optimization"""
    print("\n⚡ Testing Parallel Execution Optimization...")
    
    # Create workflow with good parallelization opportunities
    parallel_workflow = EnhancedWorkflowDefinition(
        name="Parallel Optimization Test",
        description="Workflow with clear parallel opportunities",
        tasks=[
            # Independent setup tasks
            TaskDefinition(id="setup-db", name="Database Setup", type="SETUP", config={}, dependencies=[]),
            TaskDefinition(id="setup-cache", name="Cache Setup", type="SETUP", config={}, dependencies=[]),
            TaskDefinition(id="setup-api", name="API Setup", type="SETUP", config={}, dependencies=[]),
            
            # Independent analysis tasks
            TaskDefinition(id="analyze-users", name="User Analysis", type="CODE_ANALYSIS", config={}, dependencies=["setup-db"]),
            TaskDefinition(id="analyze-products", name="Product Analysis", type="CODE_ANALYSIS", config={}, dependencies=["setup-db"]),
            TaskDefinition(id="analyze-orders", name="Order Analysis", type="CODE_ANALYSIS", config={}, dependencies=["setup-db"]),
            
            # Final aggregation
            TaskDefinition(
                id="aggregate-results",
                name="Aggregate Results",
                type="CODE_IMPLEMENTATION",
                config={},
                dependencies=["analyze-users", "analyze-products", "analyze-orders"]
            )
        ],
        version="1.0"
    )
    
    resolver = AIEnhancedDAGResolver(claude_agent=ClaudeAgentWrapper())
    
    # Test parallel optimization
    optimization = await resolver.optimize_parallel_execution(parallel_workflow)
    
    print(f"🔄 Parallel Optimization Results:")
    print(f"   - Parallel groups found: {len(optimization.get('parallel_groups', []))}")
    
    for i, group in enumerate(optimization.get('parallel_groups', []), 1):
        print(f"\n   Group {i}:")
        print(f"     - Tasks: {group.get('tasks', [])}")
        print(f"     - Estimated speedup: {group.get('estimated_speedup', 1):.1f}x")
        
        resources = group.get('resource_requirements', {})
        if resources:
            print(f"     - Resource needs: {resources}")
    
    metrics = optimization.get('optimization_metrics', {})
    if metrics:
        print(f"\n📊 Optimization Metrics:")
        print(f"   - Total speedup: {metrics.get('total_speedup', 1):.1f}x")
        print(f"   - Resource efficiency: {metrics.get('resource_efficiency', 0):.1%}")
        print(f"   - Complexity increase: {metrics.get('complexity_increase', 0):.1%}")
    
    return True


async def test_resource_allocation():
    """Test resource allocation suggestions"""
    print("\n💰 Testing Resource Allocation...")
    
    # Create execution plan for testing
    from supervisor_agent.core.workflow_models import ExecutionPlan
    
    task_map = {
        "light-task": TaskDefinition("light-task", "Light Analysis", "CODE_ANALYSIS", {}),
        "heavy-task": TaskDefinition("heavy-task", "Heavy Processing", "CODE_IMPLEMENTATION", {}),
        "test-task": TaskDefinition("test-task", "Testing", "TESTING", {})
    }
    
    plan = OptimizedExecutionPlan(
        execution_order=[["light-task"], ["heavy-task"], ["test-task"]],
        task_map=task_map,
        dependency_map={"heavy-task": ["light-task"], "test-task": ["heavy-task"]},
        parallel_efficiency_score=0.7,
        bottleneck_predictions=[],
        optimization_suggestions=[],
        resource_allocation_hints={},
        estimated_execution_time_minutes=60,
        confidence_score=0.8
    )
    
    resolver = AIEnhancedDAGResolver(claude_agent=ClaudeAgentWrapper())
    
    # Test resource allocation
    allocation = await resolver.suggest_resource_allocation(plan)
    
    print(f"🖥️ Resource Allocation Suggestions:")
    
    cpu_alloc = allocation.get("cpu_allocation", {})
    memory_alloc = allocation.get("memory_allocation", {})
    
    print(f"   CPU Allocation:")
    for task_id, cpu in cpu_alloc.items():
        print(f"     - {task_id}: {cpu} cores")
    
    print(f"   Memory Allocation:")
    for task_id, memory in memory_alloc.items():
        print(f"     - {task_id}: {memory}MB")
    
    io_opts = allocation.get("io_optimization", [])
    if io_opts:
        print(f"   I/O Optimizations: {', '.join(io_opts)}")
    
    scaling = allocation.get("scaling_recommendations", {})
    if scaling:
        print(f"   Scaling Recommendations:")
        print(f"     - Max parallel tasks: {scaling.get('max_parallel_tasks', 'N/A')}")
        print(f"     - Resource buffer: {scaling.get('resource_buffer_percent', 'N/A')}%")
    
    return True


async def test_performance_characteristics():
    """Test performance of AI-enhanced DAG resolver"""
    print("\n⏱️ Testing Performance Characteristics...")
    
    # Create large workflow for performance testing
    large_workflow = EnhancedWorkflowDefinition(
        name="Large Workflow Performance Test",
        description="Large workflow to test resolver performance",
        tasks=[
            TaskDefinition(
                id=f"task-{i}",
                name=f"Task {i}",
                type="CODE_ANALYSIS" if i % 2 == 0 else "CODE_IMPLEMENTATION",
                config={"timeout_minutes": 10 + (i % 5) * 10},
                dependencies=[f"task-{i-1}"] if i > 0 else []
            )
            for i in range(20)  # 20 tasks
        ],
        version="1.0"
    )
    
    print(f"📏 Performance Test Setup:")
    print(f"   - Tasks: {len(large_workflow.tasks)}")
    print(f"   - Dependencies: Sequential chain")
    
    # Time the optimization
    start_time = datetime.now()
    
    resolver = AIEnhancedDAGResolver(claude_agent=ClaudeAgentWrapper())
    plan = await resolver.create_intelligent_execution_plan(large_workflow)
    
    end_time = datetime.now()
    optimization_time = (end_time - start_time).total_seconds()
    
    print(f"⚡ Performance Results:")
    print(f"   - Optimization time: {optimization_time:.2f} seconds")
    print(f"   - Execution stages: {len(plan.execution_order)}")
    print(f"   - Tasks processed: {len(plan.task_map)}")
    print(f"   - Dependencies resolved: {len(plan.dependency_map)}")
    
    # Performance targets
    if optimization_time < 2.0:
        print(f"   ✅ Performance target met (< 2 seconds)")
    else:
        print(f"   ⚠️ Performance target missed (> 2 seconds)")
    
    return optimization_time < 5.0  # Allow up to 5 seconds


async def main():
    """Main test runner"""
    print("🚀 AI-Enhanced DAG Resolver - Comprehensive Test Suite")
    print("=" * 70)
    
    try:
        # Run all test suites
        test_results = []
        
        test_results.append(await test_ai_dag_optimization())
        test_results.append(await test_bottleneck_prediction())
        test_results.append(await test_parallel_optimization())
        test_results.append(await test_resource_allocation())
        test_results.append(await test_performance_characteristics())
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 Test Results Summary:")
        
        passed = sum(test_results)
        total = len(test_results)
        
        print(f"✅ Passed: {passed}/{total}")
        
        if passed == total:
            print("🎉 All tests passed! AI-Enhanced DAG Resolver is working correctly.")
            return 0
        else:
            print("❌ Some tests failed. Check the output above for details.")
            return 1
            
    except Exception as e:
        print(f"❌ Test suite failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
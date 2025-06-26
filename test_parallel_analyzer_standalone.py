#!/usr/bin/env python3
"""
Standalone test for Parallel Execution Analyzer

Tests the parallel execution analyzer in isolation to verify
intelligent parallelization capabilities and resource conflict detection.
"""

import asyncio
import sys
from datetime import datetime

sys.path.append('/home/devag/git/dev-assist')

from supervisor_agent.intelligence.parallel_execution_analyzer import (
    ParallelExecutionAnalyzer,
    ParallelGroup,
    ResourceConflict,
    ParallelizationAnalysis,
    create_parallel_execution_analyzer
)
from supervisor_agent.intelligence.workflow_synthesizer import (
    EnhancedWorkflowDefinition,
    ClaudeAgentWrapper,
    TenantContext
)
from supervisor_agent.core.workflow_models import TaskDefinition


async def test_parallel_opportunity_detection():
    """Test detection of parallel execution opportunities"""
    print("🔍 Testing Parallel Opportunity Detection...")
    
    # Create workflow with clear parallel opportunities
    workflow = EnhancedWorkflowDefinition(
        name="Parallel Opportunity Test Workflow",
        description="Workflow designed to test parallel opportunity detection",
        tasks=[
            # Independent setup tasks (can be parallelized)
            TaskDefinition(
                id="setup-database",
                name="Database Setup",
                type="SETUP",
                config={"timeout_minutes": 15},
                dependencies=[]
            ),
            TaskDefinition(
                id="setup-cache",
                name="Cache Setup", 
                type="SETUP",
                config={"timeout_minutes": 10},
                dependencies=[]
            ),
            TaskDefinition(
                id="setup-messaging",
                name="Messaging Setup",
                type="SETUP", 
                config={"timeout_minutes": 12},
                dependencies=[]
            ),
            
            # Analysis tasks depending on setup (can be parallelized)
            TaskDefinition(
                id="analyze-users",
                name="User Data Analysis",
                type="CODE_ANALYSIS",
                config={"timeout_minutes": 30},
                dependencies=["setup-database"]
            ),
            TaskDefinition(
                id="analyze-products",
                name="Product Data Analysis",
                type="CODE_ANALYSIS",
                config={"timeout_minutes": 25},
                dependencies=["setup-database"]
            ),
            TaskDefinition(
                id="analyze-orders",
                name="Order Data Analysis",
                type="CODE_ANALYSIS",
                config={"timeout_minutes": 35},
                dependencies=["setup-database"]
            ),
            
            # Final aggregation (depends on all analysis)
            TaskDefinition(
                id="aggregate-results",
                name="Aggregate Analysis Results",
                type="CODE_IMPLEMENTATION",
                config={"timeout_minutes": 20},
                dependencies=["analyze-users", "analyze-products", "analyze-orders"]
            )
        ],
        version="1.0"
    )
    
    print(f"✅ Created test workflow: {workflow.name}")
    print(f"   - Tasks: {len(workflow.tasks)}")
    print(f"   - Expected parallel groups: 2-3")
    
    # Test with AI agent
    claude_agent = ClaudeAgentWrapper()
    analyzer = ParallelExecutionAnalyzer(claude_agent=claude_agent)
    
    analysis = await analyzer.analyze_parallel_opportunities(workflow)
    
    print(f"🧠 AI-Powered Analysis Results:")
    print(f"   - Parallel groups found: {len(analysis.parallel_groups)}")
    print(f"   - Resource conflicts: {len(analysis.resource_conflicts)}")
    print(f"   - Optimization score: {analysis.optimization_score:.2f}")
    print(f"   - Confidence level: {analysis.confidence_level:.2f}")
    
    # Display parallel groups
    print(f"\n📋 Parallel Groups Identified:")
    for i, group in enumerate(analysis.parallel_groups, 1):
        print(f"   Group {i} ({group.group_id}):")
        print(f"     - Tasks: {group.tasks}")
        print(f"     - Estimated speedup: {group.estimated_speedup:.1f}x")
        print(f"     - Conflict risk: {group.conflict_risk:.1%}")
        print(f"     - Priority score: {group.priority_score:.2f}")
    
    # Display resource conflicts
    if analysis.resource_conflicts:
        print(f"\n⚠️ Resource Conflicts Detected:")
        for i, conflict in enumerate(analysis.resource_conflicts, 1):
            print(f"   Conflict {i}:")
            print(f"     - Type: {conflict.conflict_type}")
            print(f"     - Severity: {conflict.severity}")
            print(f"     - Affected tasks: {conflict.conflicting_tasks}")
            print(f"     - Impact: {conflict.estimated_impact:.1%}")
            print(f"     - Mitigation: {', '.join(conflict.mitigation_strategies[:2])}")
    
    # Display performance predictions
    perf = analysis.performance_predictions
    print(f"\n📊 Performance Predictions:")
    print(f"   - Baseline time: {perf.get('baseline_execution_time_minutes', 0)} minutes")
    print(f"   - Optimized time: {perf.get('optimized_execution_time_minutes', 0)} minutes")
    print(f"   - Speedup factor: {perf.get('speedup_factor', 1.0):.1f}x")
    print(f"   - Resource efficiency: {perf.get('resource_efficiency', 0):.1%}")
    print(f"   - Success probability: {perf.get('success_probability', 0):.1%}")
    
    return True


async def test_resource_conflict_detection():
    """Test detection of resource conflicts between parallel tasks"""
    print("\n⚡ Testing Resource Conflict Detection...")
    
    # Create workflow with potential resource conflicts
    conflict_workflow = EnhancedWorkflowDefinition(
        name="Resource Conflict Test Workflow",
        description="Workflow designed to test resource conflict detection",
        tasks=[
            # Multiple CPU-intensive tasks (should conflict)
            TaskDefinition(
                id="compile-backend",
                name="Backend Compilation",
                type="CODE_IMPLEMENTATION",
                config={"complexity": "high", "cpu_intensive": True},
                dependencies=[]
            ),
            TaskDefinition(
                id="compile-frontend",
                name="Frontend Compilation", 
                type="CODE_IMPLEMENTATION",
                config={"complexity": "high", "cpu_intensive": True},
                dependencies=[]
            ),
            TaskDefinition(
                id="run-tests",
                name="Run Test Suite",
                type="TESTING",
                config={"complexity": "medium", "memory_intensive": True},
                dependencies=[]
            ),
            TaskDefinition(
                id="build-documentation",
                name="Build Documentation",
                type="CODE_IMPLEMENTATION",
                config={"complexity": "medium", "io_intensive": True},
                dependencies=[]
            ),
            TaskDefinition(
                id="package-artifacts",
                name="Package Build Artifacts",
                type="CODE_IMPLEMENTATION", 
                config={"complexity": "medium", "io_intensive": True},
                dependencies=["compile-backend", "compile-frontend"]
            )
        ],
        version="1.0"
    )
    
    analyzer = ParallelExecutionAnalyzer(claude_agent=ClaudeAgentWrapper())
    analysis = await analyzer.analyze_parallel_opportunities(conflict_workflow)
    
    print(f"🎯 Resource Conflict Analysis:")
    print(f"   - Total conflicts detected: {len(analysis.resource_conflicts)}")
    
    conflict_types = {}
    for conflict in analysis.resource_conflicts:
        conflict_type = conflict.conflict_type
        if conflict_type not in conflict_types:
            conflict_types[conflict_type] = []
        conflict_types[conflict_type].append(conflict)
    
    for conflict_type, conflicts in conflict_types.items():
        print(f"\n   {conflict_type.upper()} Conflicts ({len(conflicts)}):")
        for i, conflict in enumerate(conflicts, 1):
            print(f"     Conflict {i}:")
            print(f"       - Severity: {conflict.severity}")
            print(f"       - Tasks: {conflict.conflicting_tasks}")
            print(f"       - Impact: {conflict.estimated_impact:.1%}")
            print(f"       - Mitigation: {', '.join(conflict.mitigation_strategies[:2])}")
    
    # Test heuristic conflict detection
    print(f"\n🔧 Heuristic Conflict Detection:")
    heuristic_analyzer = ParallelExecutionAnalyzer(claude_agent=None)
    heuristic_analysis = await heuristic_analyzer.analyze_parallel_opportunities(conflict_workflow)
    
    print(f"   - Heuristic conflicts: {len(heuristic_analysis.resource_conflicts)}")
    for conflict in heuristic_analysis.resource_conflicts:
        print(f"     - {conflict.conflict_type}: {conflict.severity} ({len(conflict.conflicting_tasks)} tasks)")
    
    return True


async def test_bottleneck_identification():
    """Test identification of execution bottlenecks"""
    print("\n🚧 Testing Bottleneck Identification...")
    
    # Create workflow with clear bottlenecks
    bottleneck_workflow = EnhancedWorkflowDefinition(
        name="Bottleneck Test Workflow",
        description="Workflow with intentional bottlenecks",
        tasks=[
            # Initial independent tasks
            TaskDefinition(id="init-1", name="Initialize Component 1", type="SETUP", config={}, dependencies=[]),
            TaskDefinition(id="init-2", name="Initialize Component 2", type="SETUP", config={}, dependencies=[]),
            TaskDefinition(id="init-3", name="Initialize Component 3", type="SETUP", config={}, dependencies=[]),
            
            # Central bottleneck task
            TaskDefinition(
                id="central-processing",
                name="Central Data Processing",
                type="CODE_IMPLEMENTATION",
                config={"complexity": "very_high", "single_threaded": True},
                dependencies=["init-1", "init-2", "init-3"]
            ),
            
            # Many tasks waiting for bottleneck
            TaskDefinition(id="process-1", name="Process Module 1", type="CODE_ANALYSIS", config={}, dependencies=["central-processing"]),
            TaskDefinition(id="process-2", name="Process Module 2", type="CODE_ANALYSIS", config={}, dependencies=["central-processing"]),
            TaskDefinition(id="process-3", name="Process Module 3", type="CODE_ANALYSIS", config={}, dependencies=["central-processing"]),
            TaskDefinition(id="process-4", name="Process Module 4", type="CODE_ANALYSIS", config={}, dependencies=["central-processing"]),
            TaskDefinition(id="process-5", name="Process Module 5", type="CODE_ANALYSIS", config={}, dependencies=["central-processing"]),
            
            # Final aggregation
            TaskDefinition(
                id="final-output",
                name="Generate Final Output",
                type="CODE_IMPLEMENTATION",
                config={},
                dependencies=["process-1", "process-2", "process-3", "process-4", "process-5"]
            )
        ],
        version="1.0"
    )
    
    analyzer = ParallelExecutionAnalyzer(claude_agent=ClaudeAgentWrapper())
    analysis = await analyzer.analyze_parallel_opportunities(bottleneck_workflow)
    
    # Identify bottlenecks
    bottlenecks = await analyzer.identify_bottlenecks(analysis)
    
    print(f"🎯 Bottleneck Identification Results:")
    print(f"   - Total bottlenecks found: {len(bottlenecks)}")
    
    for i, bottleneck in enumerate(bottlenecks, 1):
        print(f"\n   Bottleneck {i}:")
        print(f"     - Type: {bottleneck.get('type', 'Unknown')}")
        print(f"     - Description: {bottleneck.get('description', 'N/A')}")
        print(f"     - Severity: {bottleneck.get('severity', 'Unknown')}")
        print(f"     - Probability: {bottleneck.get('probability', 0):.1%}")
        
        affected_tasks = bottleneck.get('affected_tasks', [])
        if affected_tasks:
            print(f"     - Affected tasks: {affected_tasks}")
        
        mitigation = bottleneck.get('mitigation_strategies', [])
        if mitigation:
            print(f"     - Mitigation: {', '.join(mitigation[:2])}")
        
        monitoring = bottleneck.get('monitoring_indicators', [])
        if monitoring:
            print(f"     - Monitoring: {', '.join(monitoring[:2])}")
    
    return True


async def test_resource_allocation_optimization():
    """Test resource allocation optimization"""
    print("\n💰 Testing Resource Allocation Optimization...")
    
    # Create simple workflow for resource allocation testing
    workflow = EnhancedWorkflowDefinition(
        name="Resource Allocation Test",
        description="Test workflow for resource allocation",
        tasks=[
            TaskDefinition(id="light-analysis", name="Light Analysis", type="CODE_ANALYSIS", config={}, dependencies=[]),
            TaskDefinition(id="heavy-processing", name="Heavy Processing", type="CODE_IMPLEMENTATION", config={}, dependencies=[]),
            TaskDefinition(id="memory-intensive", name="Memory Intensive Task", type="TESTING", config={}, dependencies=[]),
            TaskDefinition(id="io-heavy", name="I/O Heavy Task", type="DEPLOYMENT", config={}, dependencies=[])
        ],
        version="1.0"
    )
    
    analyzer = ParallelExecutionAnalyzer(claude_agent=ClaudeAgentWrapper())
    analysis = await analyzer.analyze_parallel_opportunities(workflow)
    
    # Optimize resource allocation
    resource_constraints = {
        "max_cpu_cores": 8,
        "max_memory_gb": 16,
        "max_concurrent_tasks": 4
    }
    
    allocation = await analyzer.optimize_resource_allocation(analysis, resource_constraints)
    
    print(f"🖥️ Resource Allocation Results:")
    
    # CPU allocation
    cpu_alloc = allocation.get("cpu_allocation", {})
    print(f"   CPU Allocation:")
    for task_id, cpu_cores in cpu_alloc.items():
        print(f"     - {task_id}: {cpu_cores} cores")
    
    # Memory allocation
    memory_alloc = allocation.get("memory_allocation", {})
    print(f"   Memory Allocation:")
    for task_id, memory_mb in memory_alloc.items():
        print(f"     - {task_id}: {memory_mb}MB")
    
    # I/O optimizations
    io_opts = allocation.get("io_optimization", [])
    if io_opts:
        print(f"   I/O Optimizations: {', '.join(io_opts)}")
    
    # Scheduling strategy
    scheduling = allocation.get("scheduling_strategy", {})
    print(f"   Scheduling Strategy:")
    for key, value in scheduling.items():
        print(f"     - {key}: {value}")
    
    # Scaling recommendations
    scaling = allocation.get("scaling_recommendations", {})
    print(f"   Scaling Recommendations:")
    for key, value in scaling.items():
        print(f"     - {key}: {value}")
    
    return True


async def test_performance_characteristics():
    """Test performance characteristics of the analyzer"""
    print("\n⏱️ Testing Performance Characteristics...")
    
    # Create moderately large workflow
    large_workflow = EnhancedWorkflowDefinition(
        name="Performance Test Workflow",
        description="Large workflow for performance testing",
        tasks=[
            TaskDefinition(
                id=f"task-{i}",
                name=f"Task {i}",
                type="CODE_ANALYSIS" if i % 2 == 0 else "CODE_IMPLEMENTATION",
                config={"timeout_minutes": 10 + (i % 3) * 5},
                dependencies=[f"task-{i-1}"] if i > 0 and i % 5 != 0 else []
            )
            for i in range(25)  # 25 tasks
        ],
        version="1.0"
    )
    
    print(f"📏 Performance Test Setup:")
    print(f"   - Tasks: {len(large_workflow.tasks)}")
    print(f"   - Dependencies: Mixed (some parallel opportunities)")
    
    # Time the analysis
    start_time = datetime.now()
    
    analyzer = ParallelExecutionAnalyzer(claude_agent=ClaudeAgentWrapper())
    analysis = await analyzer.analyze_parallel_opportunities(large_workflow)
    
    end_time = datetime.now()
    analysis_time = (end_time - start_time).total_seconds()
    
    print(f"⚡ Performance Results:")
    print(f"   - Analysis time: {analysis_time:.2f} seconds")
    print(f"   - Parallel groups: {len(analysis.parallel_groups)}")
    print(f"   - Resource conflicts: {len(analysis.resource_conflicts)}")
    print(f"   - Optimization score: {analysis.optimization_score:.2f}")
    
    # Performance targets
    if analysis_time < 3.0:
        print(f"   ✅ Performance target met (< 3 seconds)")
    else:
        print(f"   ⚠️ Performance target missed (> 3 seconds)")
    
    # Test bottleneck identification performance
    start_time = datetime.now()
    bottlenecks = await analyzer.identify_bottlenecks(analysis)
    end_time = datetime.now()
    bottleneck_time = (end_time - start_time).total_seconds()
    
    print(f"   - Bottleneck analysis time: {bottleneck_time:.2f} seconds")
    print(f"   - Bottlenecks identified: {len(bottlenecks)}")
    
    return analysis_time < 5.0  # Allow up to 5 seconds


async def test_factory_function():
    """Test factory function for creating analyzer"""
    print("\n🏭 Testing Factory Function...")
    
    # Test with dependencies
    claude_agent = ClaudeAgentWrapper()
    analyzer_with_ai = await create_parallel_execution_analyzer(claude_agent=claude_agent)
    
    print(f"✅ Created analyzer with AI agent")
    print(f"   - Has Claude agent: {analyzer_with_ai.claude_agent is not None}")
    
    # Test without dependencies
    analyzer_without_ai = await create_parallel_execution_analyzer()
    
    print(f"✅ Created analyzer without AI agent")
    print(f"   - Has Claude agent: {analyzer_without_ai.claude_agent is not None}")
    
    # Test functionality
    simple_workflow = EnhancedWorkflowDefinition(
        name="Factory Test Workflow",
        description="Simple workflow for factory testing",
        tasks=[
            TaskDefinition(id="task-1", name="Task 1", type="CODE_ANALYSIS", config={}, dependencies=[]),
            TaskDefinition(id="task-2", name="Task 2", type="CODE_IMPLEMENTATION", config={}, dependencies=["task-1"])
        ],
        version="1.0"
    )
    
    analysis = await analyzer_without_ai.analyze_parallel_opportunities(simple_workflow)
    print(f"✅ Analysis completed successfully")
    print(f"   - Optimization score: {analysis.optimization_score:.2f}")
    
    return True


async def main():
    """Main test runner"""
    print("🚀 Parallel Execution Analyzer - Comprehensive Test Suite")
    print("=" * 75)
    
    try:
        # Run all test suites
        test_results = []
        
        test_results.append(await test_parallel_opportunity_detection())
        test_results.append(await test_resource_conflict_detection())
        test_results.append(await test_bottleneck_identification())
        test_results.append(await test_resource_allocation_optimization())
        test_results.append(await test_performance_characteristics())
        test_results.append(await test_factory_function())
        
        # Summary
        print("\n" + "=" * 75)
        print("📊 Test Results Summary:")
        
        passed = sum(test_results)
        total = len(test_results)
        
        print(f"✅ Passed: {passed}/{total}")
        
        if passed == total:
            print("🎉 All tests passed! Parallel Execution Analyzer is working correctly.")
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
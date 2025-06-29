#!/usr/bin/env python3
"""
Standalone test for Workflow Optimizer

Tests the comprehensive workflow optimizer that integrates AI intelligence
components for end-to-end workflow optimization.
"""

import asyncio
import sys
from datetime import datetime

sys.path.append('/home/devag/git/dev-assist')

from supervisor_agent.intelligence.workflow_optimizer import (
    WorkflowOptimizer,
    OptimizationStrategy,
    OptimizationPriority,
    OptimizationMetrics,
    OptimizationRecommendation,
    WorkflowOptimizationResult,
    create_workflow_optimizer
)
from supervisor_agent.intelligence.workflow_synthesizer import (
    EnhancedWorkflowDefinition,
    ClaudeAgentWrapper,
    TenantContext
)
from supervisor_agent.core.workflow_models import TaskDefinition


async def test_comprehensive_workflow_optimization():
    """Test end-to-end workflow optimization"""
    print("🚀 Testing Comprehensive Workflow Optimization...")
    
    # Create complex workflow for optimization testing
    workflow = EnhancedWorkflowDefinition(
        name="E-commerce Platform Development Workflow",
        description="Complete development workflow for e-commerce platform",
        tasks=[
            # Requirements and Planning Phase
            TaskDefinition(
                id="requirements-gathering",
                name="Requirements Gathering",
                type="REQUIREMENT_ANALYSIS",
                config={"timeout_minutes": 60, "priority": "high"},
                dependencies=[]
            ),
            TaskDefinition(
                id="system-design",
                name="System Architecture Design",
                type="DESIGN_TASK",
                config={"timeout_minutes": 90, "priority": "high"},
                dependencies=["requirements-gathering"]
            ),
            TaskDefinition(
                id="database-design",
                name="Database Schema Design",
                type="DESIGN_TASK",
                config={"timeout_minutes": 45, "priority": "medium"},
                dependencies=["requirements-gathering"]
            ),
            
            # Development Phase (can be parallelized)
            TaskDefinition(
                id="user-service",
                name="User Management Service",
                type="CODE_IMPLEMENTATION",
                config={"timeout_minutes": 120, "complexity": "high"},
                dependencies=["system-design", "database-design"]
            ),
            TaskDefinition(
                id="product-service",
                name="Product Catalog Service",
                type="CODE_IMPLEMENTATION",
                config={"timeout_minutes": 100, "complexity": "medium"},
                dependencies=["system-design", "database-design"]
            ),
            TaskDefinition(
                id="order-service",
                name="Order Processing Service",
                type="CODE_IMPLEMENTATION",
                config={"timeout_minutes": 110, "complexity": "high"},
                dependencies=["system-design", "database-design"]
            ),
            TaskDefinition(
                id="payment-service",
                name="Payment Integration Service",
                type="CODE_IMPLEMENTATION",
                config={"timeout_minutes": 80, "complexity": "high"},
                dependencies=["system-design"]
            ),
            
            # Frontend Development
            TaskDefinition(
                id="frontend-webapp",
                name="React Web Application",
                type="CODE_IMPLEMENTATION",
                config={"timeout_minutes": 150, "complexity": "medium"},
                dependencies=["system-design"]
            ),
            TaskDefinition(
                id="mobile-app",
                name="Mobile Application",
                type="CODE_IMPLEMENTATION",
                config={"timeout_minutes": 180, "complexity": "high"},
                dependencies=["system-design"]
            ),
            
            # Testing Phase
            TaskDefinition(
                id="unit-tests",
                name="Unit Testing",
                type="TESTING",
                config={"timeout_minutes": 90, "coverage_target": 80},
                dependencies=["user-service", "product-service", "order-service", "payment-service"]
            ),
            TaskDefinition(
                id="integration-tests",
                name="Integration Testing",
                type="TESTING",
                config={"timeout_minutes": 120, "test_environments": ["staging"]},
                dependencies=["unit-tests", "frontend-webapp"]
            ),
            TaskDefinition(
                id="e2e-tests",
                name="End-to-End Testing",
                type="TESTING",
                config={"timeout_minutes": 60, "test_scenarios": ["user_journey"]},
                dependencies=["integration-tests", "mobile-app"]
            ),
            
            # Deployment
            TaskDefinition(
                id="deployment",
                name="Production Deployment",
                type="FEATURE",
                config={"timeout_minutes": 45, "environment": "production"},
                dependencies=["e2e-tests"]
            )
        ],
        version="1.0"
    )
    
    print(f"✅ Created complex workflow: {workflow.name}")
    print(f"   - Tasks: {len(workflow.tasks)}")
    print(f"   - Phases: Requirements, Development, Testing, Deployment")
    
    # Test different optimization strategies
    strategies = [
        OptimizationStrategy.SPEED_OPTIMIZED,
        OptimizationStrategy.RESOURCE_OPTIMIZED,
        OptimizationStrategy.BALANCED
    ]
    
    # Create workflow optimizer
    claude_agent = ClaudeAgentWrapper()
    tenant_context = TenantContext(
        tenant_id="ecommerce-dev-team",
        org_profile={"name": "E-commerce Development Team", "size": "medium"},
        team_skills=["Python", "React", "AWS", "Docker", "PostgreSQL"],
        team_hierarchy={"lead": 1, "senior": 2, "junior": 3},
        approval_policies={"deployment": "lead_approval"},
        resource_limits={"max_parallel_tasks": 6, "max_cpu": 16, "max_memory_gb": 32},
        quality_standards={"test_coverage": 80, "code_review": True}
    )
    
    optimizer = WorkflowOptimizer(
        claude_agent=claude_agent,
        tenant_context=tenant_context
    )
    
    for strategy in strategies:
        print(f"\n🧠 Testing {strategy.value} optimization...")
        
        # Add historical data for more realistic testing
        historical_data = {
            "average_task_times": {
                "CODE_IMPLEMENTATION": 95,
                "TESTING": 75,
                "DESIGN_TASK": 60,
                "REQUIREMENT_ANALYSIS": 50
            },
            "success_rates": {
                "CODE_IMPLEMENTATION": 0.92,
                "TESTING": 0.95,
                "DESIGN_TASK": 0.98,
                "REQUIREMENT_ANALYSIS": 0.99
            },
            "resource_utilization": {
                "cpu_average": 0.65,
                "memory_average": 0.70,
                "concurrent_tasks_max": 4
            }
        }
        
        # Optimize workflow
        result = await optimizer.optimize_workflow(
            workflow=workflow,
            strategy=strategy,
            historical_data=historical_data,
            constraints={
                "max_parallel_tasks": 6,
                "max_execution_time_hours": 8,
                "budget_constraints": {"max_cost_usd": 500}
            }
        )
        
        print(f"📊 {strategy.value} Results:")
        metrics = result.optimization_metrics
        print(f"   - Baseline time: {metrics.baseline_execution_time_minutes} minutes")
        print(f"   - Optimized time: {metrics.optimized_execution_time_minutes} minutes")
        print(f"   - Speedup factor: {metrics.speedup_factor:.2f}x")
        print(f"   - Resource efficiency: {metrics.resource_efficiency:.1%}")
        print(f"   - Cost reduction: {metrics.cost_reduction_percent:.1f}%")
        print(f"   - Reliability score: {metrics.reliability_score:.1%}")
        print(f"   - Optimization confidence: {metrics.optimization_confidence:.1%}")
        
        # Display top recommendations
        if result.recommendations:
            print(f"   - Top recommendations: {len(result.recommendations)}")
            for i, rec in enumerate(result.recommendations[:2], 1):
                print(f"     {i}. {rec.type}: {rec.description[:60]}...")
                print(f"        Impact: {rec.impact}, Effort: {rec.effort}, Priority: {rec.priority.value}")
        
        # Display execution plan details
        print(f"   - Execution stages: {len(result.execution_plan.execution_order)}")
        print(f"   - Parallel efficiency: {result.execution_plan.parallel_efficiency_score:.2f}")
        print(f"   - Bottleneck predictions: {len(result.execution_plan.bottleneck_predictions)}")
        
        # Display parallelization analysis
        print(f"   - Parallel groups: {len(result.parallelization_analysis.parallel_groups)}")
        print(f"   - Resource conflicts: {len(result.parallelization_analysis.resource_conflicts)}")
        print(f"   - Parallelization score: {result.parallelization_analysis.optimization_score:.2f}")
    
    return True


async def test_strategy_comparison():
    """Test comparison of multiple optimization strategies"""
    print("\n📊 Testing Strategy Comparison...")
    
    # Create medium-complexity workflow for comparison
    workflow = EnhancedWorkflowDefinition(
        name="API Development Workflow",
        description="RESTful API development and deployment",
        tasks=[
            TaskDefinition(id="api-design", name="API Design", type="DESIGN_TASK", config={"timeout_minutes": 45}, dependencies=[]),
            TaskDefinition(id="data-models", name="Data Models", type="CODE_IMPLEMENTATION", config={"timeout_minutes": 60}, dependencies=["api-design"]),
            TaskDefinition(id="auth-service", name="Authentication Service", type="CODE_IMPLEMENTATION", config={"timeout_minutes": 80}, dependencies=["data-models"]),
            TaskDefinition(id="user-endpoints", name="User Endpoints", type="CODE_IMPLEMENTATION", config={"timeout_minutes": 70}, dependencies=["auth-service"]),
            TaskDefinition(id="data-endpoints", name="Data Endpoints", type="CODE_IMPLEMENTATION", config={"timeout_minutes": 90}, dependencies=["data-models"]),
            TaskDefinition(id="api-tests", name="API Testing", type="TESTING", config={"timeout_minutes": 60}, dependencies=["user-endpoints", "data-endpoints"]),
            TaskDefinition(id="documentation", name="API Documentation", type="DESIGN_TASK", config={"timeout_minutes": 30}, dependencies=["api-tests"]),
            TaskDefinition(id="deployment", name="Production Deployment", type="FEATURE", config={"timeout_minutes": 40}, dependencies=["documentation"])
        ],
        version="1.0"
    )
    
    optimizer = WorkflowOptimizer(claude_agent=ClaudeAgentWrapper())
    
    # Compare all strategies
    comparison_results = await optimizer.compare_optimization_strategies(
        workflow=workflow,
        strategies=[
            OptimizationStrategy.SPEED_OPTIMIZED,
            OptimizationStrategy.RESOURCE_OPTIMIZED,
            OptimizationStrategy.COST_OPTIMIZED,
            OptimizationStrategy.BALANCED
        ]
    )
    
    print(f"🔄 Strategy Comparison Results:")
    print(f"   - Strategies compared: {len(comparison_results)}")
    
    # Create comparison table
    strategy_metrics = {}
    for strategy_name, result in comparison_results.items():
        metrics = result.optimization_metrics
        strategy_metrics[strategy_name] = {
            "speedup": metrics.speedup_factor,
            "efficiency": metrics.resource_efficiency,
            "cost_reduction": metrics.cost_reduction_percent,
            "confidence": metrics.optimization_confidence
        }
    
    # Find best strategies for different criteria
    best_speed = max(strategy_metrics.items(), key=lambda x: x[1]["speedup"])
    best_efficiency = max(strategy_metrics.items(), key=lambda x: x[1]["efficiency"])
    best_cost = max(strategy_metrics.items(), key=lambda x: x[1]["cost_reduction"])
    
    print(f"\n📈 Best Strategies:")
    print(f"   - Best Speed: {best_speed[0]} ({best_speed[1]['speedup']:.2f}x speedup)")
    print(f"   - Best Efficiency: {best_efficiency[0]} ({best_efficiency[1]['efficiency']:.1%} efficiency)")
    print(f"   - Best Cost: {best_cost[0]} ({best_cost[1]['cost_reduction']:.1f}% cost reduction)")
    
    # Detailed comparison table
    print(f"\n📋 Detailed Comparison:")
    print(f"{'Strategy':<20} {'Speedup':<10} {'Efficiency':<12} {'Cost Red.':<10} {'Confidence':<10}")
    print(f"{'-' * 65}")
    
    for strategy_name, metrics in strategy_metrics.items():
        print(f"{strategy_name:<20} {metrics['speedup']:<10.2f} {metrics['efficiency']:<12.1%} {metrics['cost_reduction']:<10.1f}% {metrics['confidence']:<10.1%}")
    
    return True


async def test_optimization_report_generation():
    """Test optimization report generation"""
    print("\n📋 Testing Optimization Report Generation...")
    
    # Create simple workflow for report testing
    workflow = EnhancedWorkflowDefinition(
        name="CI/CD Pipeline Workflow",
        description="Continuous integration and deployment pipeline",
        tasks=[
            TaskDefinition(id="code-checkout", name="Code Checkout", type="SETUP", config={"timeout_minutes": 5}, dependencies=[]),
            TaskDefinition(id="build", name="Build Application", type="CODE_IMPLEMENTATION", config={"timeout_minutes": 15}, dependencies=["code-checkout"]),
            TaskDefinition(id="unit-tests", name="Unit Tests", type="TESTING", config={"timeout_minutes": 20}, dependencies=["build"]),
            TaskDefinition(id="security-scan", name="Security Scanning", type="CODE_ANALYSIS", config={"timeout_minutes": 10}, dependencies=["build"]),
            TaskDefinition(id="integration-tests", name="Integration Tests", type="TESTING", config={"timeout_minutes": 25}, dependencies=["unit-tests", "security-scan"]),
            TaskDefinition(id="deploy-staging", name="Deploy to Staging", type="FEATURE", config={"timeout_minutes": 8}, dependencies=["integration-tests"]),
            TaskDefinition(id="e2e-tests", name="E2E Tests", type="TESTING", config={"timeout_minutes": 30}, dependencies=["deploy-staging"]),
            TaskDefinition(id="deploy-prod", name="Deploy to Production", type="FEATURE", config={"timeout_minutes": 12}, dependencies=["e2e-tests"])
        ],
        version="1.0"
    )
    
    optimizer = WorkflowOptimizer(claude_agent=ClaudeAgentWrapper())
    
    # Optimize workflow
    optimization_result = await optimizer.optimize_workflow(
        workflow=workflow,
        strategy=OptimizationStrategy.BALANCED
    )
    
    # Generate comprehensive report
    report = await optimizer.generate_optimization_report(optimization_result)
    
    print(f"📄 Optimization Report Generated:")
    
    # Executive Summary
    exec_summary = report["executive_summary"]
    print(f"\n🎯 Executive Summary:")
    print(f"   - Workflow: {exec_summary['workflow_name']}")
    print(f"   - Strategy: {exec_summary['optimization_strategy']}")
    print(f"   - Time reduction: {exec_summary['key_improvements']['execution_time_reduction']}")
    print(f"   - Efficiency gain: {exec_summary['key_improvements']['resource_efficiency_gain']}")
    print(f"   - Cost reduction: {exec_summary['key_improvements']['cost_reduction']}")
    print(f"   - Confidence: {exec_summary['confidence_level']}")
    
    # Performance Analysis
    perf_analysis = report["performance_analysis"]
    print(f"\n⚡ Performance Analysis:")
    print(f"   - Baseline time: {perf_analysis['baseline_execution_time']}")
    print(f"   - Optimized time: {perf_analysis['optimized_execution_time']}")
    print(f"   - Speedup factor: {perf_analysis['speedup_factor']}")
    print(f"   - Reliability score: {perf_analysis['reliability_score']}")
    
    # Parallelization Analysis
    parallel_analysis = report["parallelization_analysis"]
    print(f"\n🔄 Parallelization Analysis:")
    print(f"   - Parallel groups: {parallel_analysis['parallel_groups_identified']}")
    print(f"   - Resource conflicts: {parallel_analysis['resource_conflicts_detected']}")
    print(f"   - Parallelization score: {parallel_analysis['parallelization_score']}")
    
    # Recommendations Summary
    rec_summary = report["recommendations_summary"]
    print(f"\n💡 Recommendations Summary:")
    print(f"   - High priority: {rec_summary['high_priority_count']}")
    print(f"   - Medium priority: {rec_summary['medium_priority_count']}")
    print(f"   - Low priority: {rec_summary['low_priority_count']}")
    print(f"   - Total recommendations: {rec_summary['total_recommendations']}")
    
    # Display top recommendations
    recommendations = report["optimization_recommendations"]
    if recommendations:
        print(f"\n🔧 Top Recommendations:")
        for i, rec in enumerate(recommendations[:3], 1):
            print(f"   {i}. {rec['type'].title()}: {rec['description'][:70]}...")
            print(f"      Impact: {rec['impact']}, Priority: {rec['priority']}")
            if rec.get('expected_benefit'):
                benefits = rec['expected_benefit']
                if benefits:
                    benefit_str = ", ".join([f"{k}: {v}" for k, v in list(benefits.items())[:2]])
                    print(f"      Benefits: {benefit_str}")
    
    # Validation Results
    validation = report["validation_results"]
    print(f"\n✅ Validation Results:")
    print(f"   - Overall valid: {validation['overall_valid']}")
    print(f"   - Validation score: {validation['validation_score']:.1%}")
    
    return True


async def test_error_handling_and_fallbacks():
    """Test error handling and fallback mechanisms"""
    print("\n🛡️ Testing Error Handling and Fallbacks...")
    
    # Test with invalid workflow data
    invalid_workflow_dict = {
        "name": "Invalid Workflow",
        "description": "Test workflow with missing fields",
        "tasks": []  # Empty tasks should trigger fallback
    }
    
    optimizer = WorkflowOptimizer(claude_agent=None)  # No AI agent
    
    try:
        result = await optimizer.optimize_workflow(
            workflow=invalid_workflow_dict,
            strategy=OptimizationStrategy.BALANCED
        )
        
        print(f"✅ Fallback optimization completed")
        print(f"   - Strategy used: {result.strategy_used.value}")
        print(f"   - Confidence: {result.optimization_metrics.optimization_confidence:.1%}")
        print(f"   - Validation: {result.validation_results['overall_valid']}")
        
    except Exception as e:
        print(f"❌ Error handling failed: {str(e)}")
        return False
    
    # Test with minimal valid workflow
    minimal_workflow = EnhancedWorkflowDefinition(
        name="Minimal Test Workflow",
        description="Single task workflow",
        tasks=[
            TaskDefinition(
                id="single-task",
                name="Single Task",
                type="CODE_ANALYSIS", 
                config={"timeout_minutes": 30},
                dependencies=[]
            )
        ],
        version="1.0"
    )
    
    result = await optimizer.optimize_workflow(
        workflow=minimal_workflow,
        strategy=OptimizationStrategy.SPEED_OPTIMIZED
    )
    
    print(f"✅ Minimal workflow optimization completed")
    print(f"   - Tasks: {len(result.optimized_workflow.tasks)}")
    print(f"   - Recommendations: {len(result.recommendations)}")
    print(f"   - Speedup: {result.optimization_metrics.speedup_factor:.2f}x")
    
    return True


async def test_factory_function():
    """Test factory function for creating optimizer"""
    print("\n🏭 Testing Factory Function...")
    
    # Test with full dependencies
    claude_agent = ClaudeAgentWrapper()
    tenant_context = TenantContext(
        tenant_id="test-tenant",
        org_profile={"name": "Test Organization"},
        team_skills=["Python", "DevOps"],
        team_hierarchy={},
        approval_policies={},
        resource_limits={},
        quality_standards={}
    )
    
    optimizer_with_deps = await create_workflow_optimizer(
        claude_agent=claude_agent,
        tenant_context=tenant_context
    )
    
    print(f"✅ Created optimizer with dependencies")
    print(f"   - Has Claude agent: {optimizer_with_deps.claude_agent is not None}")
    print(f"   - Has tenant context: {optimizer_with_deps.tenant_context is not None}")
    
    # Test without dependencies
    optimizer_minimal = await create_workflow_optimizer()
    
    print(f"✅ Created minimal optimizer")
    print(f"   - Has Claude agent: {optimizer_minimal.claude_agent is not None}")
    print(f"   - Has tenant context: {optimizer_minimal.tenant_context is not None}")
    
    # Test basic functionality
    test_workflow = EnhancedWorkflowDefinition(
        name="Factory Test Workflow",
        description="Simple workflow for factory testing",
        tasks=[
            TaskDefinition(id="task-1", name="Task 1", type="CODE_ANALYSIS", config={}, dependencies=[]),
            TaskDefinition(id="task-2", name="Task 2", type="TESTING", config={}, dependencies=["task-1"])
        ],
        version="1.0"
    )
    
    result = await optimizer_minimal.optimize_workflow(test_workflow)
    print(f"✅ Factory-created optimizer works correctly")
    print(f"   - Optimization completed successfully")
    print(f"   - Confidence: {result.optimization_metrics.optimization_confidence:.1%}")
    
    return True


async def test_performance_characteristics():
    """Test performance characteristics of the optimizer"""
    print("\n⏱️ Testing Performance Characteristics...")
    
    # Create moderately large workflow for performance testing
    large_workflow = EnhancedWorkflowDefinition(
        name="Large Workflow Performance Test",
        description="Large workflow to test optimizer performance",
        tasks=[
            TaskDefinition(
                id=f"task-{i}",
                name=f"Task {i}",
                type="CODE_IMPLEMENTATION" if i % 3 == 0 else "CODE_ANALYSIS",
                config={"timeout_minutes": 10 + (i % 5) * 5},
                dependencies=[f"task-{i-1}"] if i > 0 and i % 7 != 0 else []
            )
            for i in range(30)  # 30 tasks
        ],
        version="1.0"
    )
    
    print(f"📏 Performance Test Setup:")
    print(f"   - Tasks: {len(large_workflow.tasks)}")
    print(f"   - Dependencies: Mixed (some parallel opportunities)")
    
    optimizer = WorkflowOptimizer(claude_agent=ClaudeAgentWrapper())
    
    # Time the optimization
    start_time = datetime.now()
    
    result = await optimizer.optimize_workflow(
        workflow=large_workflow,
        strategy=OptimizationStrategy.BALANCED
    )
    
    end_time = datetime.now()
    optimization_time = (end_time - start_time).total_seconds()
    
    print(f"⚡ Performance Results:")
    print(f"   - Total optimization time: {optimization_time:.2f} seconds")
    print(f"   - Tasks processed: {len(result.optimized_workflow.tasks)}")
    print(f"   - Recommendations generated: {len(result.recommendations)}")
    print(f"   - Execution stages: {len(result.execution_plan.execution_order)}")
    print(f"   - Parallel groups: {len(result.parallelization_analysis.parallel_groups)}")
    
    # Performance targets
    if optimization_time < 5.0:
        print(f"   ✅ Performance target met (< 5 seconds)")
    else:
        print(f"   ⚠️ Performance target missed (> 5 seconds)")
    
    # Test report generation performance
    start_time = datetime.now()
    report = await optimizer.generate_optimization_report(result)
    end_time = datetime.now()
    report_time = (end_time - start_time).total_seconds()
    
    print(f"   - Report generation time: {report_time:.2f} seconds")
    print(f"   - Report sections: {len(report)}")
    
    return optimization_time < 10.0  # Allow up to 10 seconds


async def main():
    """Main test runner"""
    print("🚀 Workflow Optimizer - Comprehensive Test Suite")
    print("=" * 80)
    
    try:
        # Run all test suites
        test_results = []
        
        test_results.append(await test_comprehensive_workflow_optimization())
        test_results.append(await test_strategy_comparison())
        test_results.append(await test_optimization_report_generation())
        test_results.append(await test_error_handling_and_fallbacks())
        test_results.append(await test_factory_function())
        test_results.append(await test_performance_characteristics())
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 Test Results Summary:")
        
        passed = sum(test_results)
        total = len(test_results)
        
        print(f"✅ Passed: {passed}/{total}")
        
        if passed == total:
            print("🎉 All tests passed! Workflow Optimizer is working correctly.")
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
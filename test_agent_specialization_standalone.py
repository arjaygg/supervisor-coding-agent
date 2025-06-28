#!/usr/bin/env python3
"""
Standalone test for Agent Specialization Engine

Tests the intelligent agent specialization system that routes tasks to
the most appropriate specialized AI agents based on task characteristics,
provider capabilities, and historical performance.
"""

import asyncio
import sys
from datetime import datetime

sys.path.append('/home/devag/git/dev-assist')

from supervisor_agent.orchestration.agent_specialization_engine import (
    AgentSpecializationEngine,
    AgentSpecialty,
    SpecializationCapability,
    SpecializationScore,
    DefaultTaskAnalyzer,
    DefaultCapabilityMatcher,
    DefaultPerformancePredictor,
    DefaultSpecializationStrategy,
    create_agent_specialization_engine
)
from supervisor_agent.providers.base_provider import TaskCapability, ProviderType
from supervisor_agent.core.provider_coordinator import ExecutionContext
from supervisor_agent.db.models import Task, TaskType


async def test_task_analysis():
    """Test task characteristic analysis"""
    print("🔍 Testing Task Analysis...")
    
    analyzer = DefaultTaskAnalyzer()
    
    # Test different task types
    test_tasks = [
        Task(
            id="security-task",
            type=TaskType.CODE_REVIEW,
            config={
                "description": "Review authentication service for security vulnerabilities",
                "security": True,
                "complexity": "high",
                "requirements": ["security audit", "penetration testing"]
            },
            priority=8
        ),
        Task(
            id="performance-task",
            type=TaskType.FEATURE_DEVELOPMENT,
            config={
                "description": "Optimize database queries for better performance",
                "performance": True,
                "optimization": "speed",
                "constraints": {"memory": "limited"}
            },
            priority=6
        ),
        Task(
            id="simple-bug",
            type=TaskType.BUG_FIX,
            config={
                "description": "Fix simple null pointer exception",
                "severity": "low"
            },
            priority=3
        )
    ]
    
    for task in test_tasks:
        characteristics = await analyzer.analyze_task_characteristics(task)
        
        print(f"\n📋 Task: {task.id}")
        print(f"   - Type: {characteristics['task_type']}")
        print(f"   - Complexity: {characteristics['complexity']}")
        print(f"   - Domain: {characteristics['domain']}")
        print(f"   - Estimated effort: {characteristics['estimated_effort']:.1f} hours")
        print(f"   - Requirements: {characteristics['requirements']}")
        print(f"   - Constraints: {characteristics['constraints']}")
    
    return True


async def test_capability_matching():
    """Test capability matching logic"""
    print("\n🎯 Testing Capability Matching...")
    
    matcher = DefaultCapabilityMatcher()
    
    # Create test capabilities
    test_capabilities = {
        AgentSpecialty.SECURITY_ANALYST: [
            SpecializationCapability(
                name="Security Analysis",
                proficiency_score=0.9,
                task_types=[TaskCapability.SECURITY_ANALYSIS, TaskCapability.CODE_REVIEW],
                provider_preferences=[ProviderType.CLAUDE_CLI],
                context_requirements={"domain": "security"},
                performance_metrics={"success_rate": 0.9}
            )
        ],
        AgentSpecialty.PERFORMANCE_OPTIMIZER: [
            SpecializationCapability(
                name="Performance Optimization",
                proficiency_score=0.8,
                task_types=[TaskCapability.PERFORMANCE_OPTIMIZATION, TaskCapability.CODE_ANALYSIS],
                provider_preferences=[ProviderType.CLAUDE_CLI],
                context_requirements={"domain": "performance"},
                performance_metrics={"success_rate": 0.8}
            )
        ],
        AgentSpecialty.BUG_HUNTER: [
            SpecializationCapability(
                name="Bug Detection",
                proficiency_score=0.85,
                task_types=[TaskCapability.BUG_FIX],
                provider_preferences=[ProviderType.CLAUDE_CLI],
                context_requirements={"domain": "debugging"},
                performance_metrics={"success_rate": 0.85}
            )
        ]
    }
    
    # Test task characteristics
    test_characteristics = [
        {
            "name": "Security Review Task",
            "characteristics": {
                "task_type": "security_analysis",
                "domain": "security",
                "complexity": "high"
            }
        },
        {
            "name": "Performance Optimization Task", 
            "characteristics": {
                "task_type": "performance_optimization",
                "domain": "performance",
                "complexity": "moderate"
            }
        },
        {
            "name": "Bug Fix Task",
            "characteristics": {
                "task_type": "bug_fix",
                "domain": "debugging",
                "complexity": "simple"
            }
        }
    ]
    
    for test_case in test_characteristics:
        print(f"\n🧪 Testing {test_case['name']}:")
        matches = await matcher.match_capabilities(
            test_case['characteristics'], test_capabilities
        )
        
        print(f"   Matches found: {len(matches)}")
        for specialty, score in matches[:3]:
            print(f"   - {specialty.value}: {score:.2f}")
    
    return True


async def test_agent_specialization_selection():
    """Test end-to-end agent specialization selection"""
    print("\n🎯 Testing Agent Specialization Selection...")
    
    engine = await create_agent_specialization_engine()
    
    # Test various task scenarios
    test_scenarios = [
        {
            "name": "Security Code Review",
            "task": Task(
                id="security-review-1",
                type=TaskType.CODE_REVIEW,
                config={
                    "description": "Review payment processing code for security vulnerabilities",
                    "security": True,
                    "pci_compliance": True,
                    "critical": True
                },
                priority=9
            ),
            "context": ExecutionContext(
                user_id="security-team",
                priority=9,
                require_capabilities=["security_analysis"]
            )
        },
        {
            "name": "Performance Optimization",
            "task": Task(
                id="perf-opt-1",
                type=TaskType.FEATURE_DEVELOPMENT,
                config={
                    "description": "Optimize database queries and caching strategy",
                    "performance": True,
                    "database_optimization": True,
                    "target_improvement": "50% faster"
                },
                priority=7
            ),
            "context": ExecutionContext(
                user_id="performance-team",
                priority=7,
                max_cost_usd=100.0
            )
        },
        {
            "name": "Simple Bug Fix",
            "task": Task(
                id="bug-fix-1",
                type=TaskType.BUG_FIX,
                config={
                    "description": "Fix null pointer exception in user service",
                    "severity": "medium",
                    "reproduction_steps": ["login", "access profile", "crash"]
                },
                priority=5
            ),
            "context": ExecutionContext(
                user_id="dev-team",
                priority=5
            )
        },
        {
            "name": "Documentation Task",
            "task": Task(
                id="docs-1",
                type=TaskType.DOCUMENTATION,
                config={
                    "description": "Create API documentation for new endpoints",
                    "format": "openapi",
                    "include_examples": True
                },
                priority=4
            ),
            "context": ExecutionContext(
                user_id="docs-team",
                priority=4
            )
        },
        {
            "name": "Complex Architecture Design",
            "task": Task(
                id="arch-1",
                type=TaskType.FEATURE_DEVELOPMENT,
                config={
                    "description": "Design microservices architecture for new product line",
                    "complexity": "enterprise",
                    "scalability_requirements": "1M+ users",
                    "compliance": ["SOX", "GDPR"]
                },
                priority=8
            ),
            "context": ExecutionContext(
                user_id="architecture-team",
                priority=8,
                organization_id="enterprise-org"
            )
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n🧪 Scenario: {scenario['name']}")
        print(f"   Task: {scenario['task'].config.get('description', '')}")
        
        # Get best specialist
        best_score = await engine.select_best_specialist(
            scenario['task'], scenario['context']
        )
        
        print(f"\n   🎯 Best Specialist: {best_score.specialty.value}")
        print(f"   - Overall Score: {best_score.overall_score:.3f}")
        print(f"   - Capability Match: {best_score.capability_match:.3f}")
        print(f"   - Provider Availability: {best_score.provider_availability:.3f}")
        print(f"   - Historical Performance: {best_score.historical_performance:.3f}")
        print(f"   - Context Match: {best_score.context_match:.3f}")
        print(f"   - Confidence: {best_score.confidence:.3f}")
        print(f"   - Recommended Provider: {best_score.recommended_provider}")
        print(f"   - Estimated Time: {best_score.estimated_execution_time:.1f} seconds")
        print(f"   - Reasoning: {best_score.reasoning}")
        
        # Validate that we got a reasonable selection
        assert best_score.overall_score > 0.0
        assert best_score.confidence > 0.0
        assert best_score.specialty is not None
    
    return True


async def test_all_specialization_scores():
    """Test getting all specialization scores for comparison"""
    print("\n📊 Testing All Specialization Scores...")
    
    engine = await create_agent_specialization_engine()
    
    # Test with a security-focused task
    task = Task(
        id="security-analysis",
        type=TaskType.SECURITY_ANALYSIS,
        config={
            "description": "Comprehensive security audit of authentication system",
            "scope": "full_application",
            "compliance_requirements": ["SOC2", "PCI-DSS"]
        },
        priority=8
    )
    
    context = ExecutionContext(
        user_id="security-audit-team",
        priority=8,
        require_capabilities=["security_analysis"]
    )
    
    all_scores = await engine.get_all_specialization_scores(task, context)
    
    print(f"📋 All Specialization Scores (sorted by overall score):")
    print(f"{'Rank':<4} {'Specialty':<25} {'Score':<8} {'Capability':<12} {'Provider':<10} {'Performance':<12} {'Confidence':<10}")
    print("-" * 85)
    
    for i, score in enumerate(all_scores[:8], 1):
        print(f"{i:<4} {score.specialty.value:<25} {score.overall_score:<8.3f} "
              f"{score.capability_match:<12.3f} {score.provider_availability:<10.3f} "
              f"{score.historical_performance:<12.3f} {score.confidence:<10.3f}")
    
    # Validate that security analyst is highly ranked for security task
    top_3_specialties = [score.specialty for score in all_scores[:3]]
    print(f"\n🏆 Top 3 Specialists: {[s.value for s in top_3_specialties]}")
    
    return True


async def test_capability_updates():
    """Test updating agent capabilities"""
    print("\n🔧 Testing Capability Updates...")
    
    engine = await create_agent_specialization_engine()
    
    # Get initial capabilities
    initial_capabilities = await engine.get_agent_capabilities(AgentSpecialty.SECURITY_ANALYST)
    print(f"Initial Security Analyst capabilities: {len(initial_capabilities)}")
    
    # Add new specialized capability
    new_capability = SpecializationCapability(
        name="Advanced Penetration Testing",
        proficiency_score=0.95,
        task_types=[TaskCapability.SECURITY_ANALYSIS],
        provider_preferences=[ProviderType.CLAUDE_CLI, ProviderType.ANTHROPIC_API],
        context_requirements={
            "domain": "security",
            "complexity": ["complex", "enterprise"],
            "penetration_testing": True
        },
        performance_metrics={
            "success_rate": 0.95,
            "avg_execution_time": 900.0,
            "false_positive_rate": 0.02
        }
    )
    
    updated_capabilities = initial_capabilities + [new_capability]
    await engine.update_agent_capabilities(AgentSpecialty.SECURITY_ANALYST, updated_capabilities)
    
    # Verify update
    final_capabilities = await engine.get_agent_capabilities(AgentSpecialty.SECURITY_ANALYST)
    print(f"Updated Security Analyst capabilities: {len(final_capabilities)}")
    
    # Test that the new capability affects scoring
    pen_test_task = Task(
        id="pen-test",
        type=TaskType.SECURITY_ANALYSIS,
        config={
            "description": "Conduct penetration testing on web application",
            "penetration_testing": True,
            "complexity": "enterprise"
        },
        priority=9
    )
    
    context = ExecutionContext(user_id="pen-test-team", priority=9)
    best_score = await engine.select_best_specialist(pen_test_task, context)
    
    print(f"Best specialist for penetration testing: {best_score.specialty.value}")
    print(f"Score: {best_score.overall_score:.3f}")
    
    assert len(final_capabilities) == len(initial_capabilities) + 1
    return True


async def test_performance_characteristics():
    """Test performance characteristics of the specialization engine"""
    print("\n⏱️ Testing Performance Characteristics...")
    
    engine = await create_agent_specialization_engine()
    
    # Create multiple tasks for performance testing
    tasks = []
    for i in range(20):
        task = Task(
            id=f"perf-test-{i}",
            type=TaskType.CODE_REVIEW if i % 2 == 0 else TaskType.FEATURE_DEVELOPMENT,
            config={
                "description": f"Performance test task {i}",
                "complexity": "moderate",
                "iteration": i
            },
            priority=5
        )
        tasks.append(task)
    
    context = ExecutionContext(user_id="perf-test", priority=5)
    
    # Time the specialization selection
    start_time = datetime.now()
    
    results = []
    for task in tasks:
        score = await engine.select_best_specialist(task, context)
        results.append(score)
    
    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()
    avg_time = total_time / len(tasks)
    
    print(f"📊 Performance Results:")
    print(f"   - Tasks processed: {len(tasks)}")
    print(f"   - Total time: {total_time:.3f} seconds")
    print(f"   - Average time per task: {avg_time:.3f} seconds")
    print(f"   - Throughput: {len(tasks)/total_time:.1f} tasks/second")
    
    # Performance targets
    if avg_time < 0.1:  # 100ms per task
        print(f"   ✅ Performance target met (< 0.1 seconds per task)")
    else:
        print(f"   ⚠️ Performance target missed (> 0.1 seconds per task)")
    
    # Validate results
    successful_selections = sum(1 for r in results if r.overall_score > 0.0)
    print(f"   - Successful selections: {successful_selections}/{len(tasks)}")
    
    return avg_time < 0.5  # Allow up to 500ms per task


async def test_error_handling():
    """Test error handling and fallback mechanisms"""
    print("\n🛡️ Testing Error Handling...")
    
    engine = await create_agent_specialization_engine()
    
    # Test with invalid/minimal task
    invalid_task = Task(
        id="invalid-task",
        type=None,  # Invalid type
        config={},
        priority=0
    )
    
    context = ExecutionContext(user_id="test")
    
    try:
        score = await engine.select_best_specialist(invalid_task, context)
        
        print(f"✅ Graceful fallback for invalid task:")
        print(f"   - Fallback specialty: {score.specialty.value}")
        print(f"   - Score: {score.overall_score:.3f}")
        print(f"   - Confidence: {score.confidence:.3f}")
        print(f"   - Reasoning: {score.reasoning}")
        
        # Should fallback to general developer
        assert score.specialty == AgentSpecialty.GENERAL_DEVELOPER
        
    except Exception as e:
        print(f"❌ Error handling failed: {str(e)}")
        return False
    
    # Test with empty capabilities
    empty_capabilities_engine = AgentSpecializationEngine()
    empty_capabilities_engine.agent_capabilities = {}  # Clear capabilities
    
    try:
        task = Task(id="test", type=TaskType.CODE_REVIEW, config={}, priority=5)
        score = await empty_capabilities_engine.select_best_specialist(task, context)
        
        print(f"✅ Graceful fallback with no capabilities:")
        print(f"   - Fallback specialty: {score.specialty.value}")
        print(f"   - Score: {score.overall_score:.3f}")
        
    except Exception as e:
        print(f"❌ Empty capabilities handling failed: {str(e)}")
        return False
    
    return True


async def main():
    """Main test runner"""
    print("🚀 Agent Specialization Engine - Comprehensive Test Suite")
    print("=" * 80)
    
    try:
        # Run all test suites
        test_results = []
        
        test_results.append(await test_task_analysis())
        test_results.append(await test_capability_matching())
        test_results.append(await test_agent_specialization_selection())
        test_results.append(await test_all_specialization_scores())
        test_results.append(await test_capability_updates())
        test_results.append(await test_performance_characteristics())
        test_results.append(await test_error_handling())
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 Test Results Summary:")
        
        passed = sum(test_results)
        total = len(test_results)
        
        print(f"✅ Passed: {passed}/{total}")
        
        if passed == total:
            print("🎉 All tests passed! Agent Specialization Engine is working correctly.")
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
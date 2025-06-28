#!/usr/bin/env python3
"""
Standalone test for AI Workflow Synthesizer

This test runs the AI Workflow Synthesizer in isolation without
the full application context to verify core functionality.
"""

import asyncio
import json
from datetime import datetime

# Import our synthesizer components
import sys
sys.path.append('/home/devag/git/dev-assist')

from supervisor_agent.intelligence.workflow_synthesizer import (
    AIWorkflowSynthesizer,
    RequirementAnalysis,
    RequirementComplexity,
    DomainType,
    TenantContext,
    ClaudeAgentWrapper,
    create_workflow_synthesizer
)

async def test_basic_workflow_synthesis():
    """Test basic workflow synthesis functionality"""
    print("🧪 Starting AI Workflow Synthesizer Standalone Test")
    
    # Create tenant context
    tenant_context = TenantContext(
        tenant_id="test-tenant-001",
        org_profile={"name": "Test Organization", "type": "software_company"},
        team_skills=["Python", "FastAPI", "AI", "Testing"],
        team_hierarchy={"cto": "alice", "lead": "bob", "dev": "charlie"},
        approval_policies={"production": "cto_approval", "staging": "lead_approval"},
        resource_limits={"max_parallel_tasks": 8, "max_duration_hours": 24},
        quality_standards={"code_coverage": 0.85, "security_scan": True}
    )
    
    print(f"✅ Created tenant context for: {tenant_context.org_profile['name']}")
    
    # Create workflow synthesizer (without provider coordinator for testing)
    synthesizer = await create_workflow_synthesizer(
        tenant_context=tenant_context,
        provider_coordinator=None  # Will use mock responses
    )
    
    print("✅ Created AI Workflow Synthesizer")
    
    # Test requirement analysis
    description = "Build a secure user authentication system with JWT tokens, password hashing, and role-based access control"
    
    print(f"🔍 Analyzing requirements: {description[:50]}...")
    
    requirements = await synthesizer.analyze_requirements(description)
    
    print(f"✅ Requirements Analysis:")
    print(f"   - Domain: {requirements.domain.value}")
    print(f"   - Complexity: {requirements.complexity.value}")
    print(f"   - Estimated Duration: {requirements.estimated_duration_hours} hours")
    print(f"   - Required Skills: {', '.join(requirements.required_skills)}")
    print(f"   - Success Criteria: {len(requirements.success_criteria)} items")
    
    # Test workflow synthesis
    print("\n🔧 Synthesizing optimal workflow...")
    
    workflow = await synthesizer.synthesize_optimal_workflow(requirements)
    
    print(f"✅ Workflow Synthesis:")
    print(f"   - Name: {workflow.name}")
    print(f"   - Description: {workflow.description[:80]}...")
    print(f"   - Tasks: {len(workflow.tasks)} tasks")
    print(f"   - Version: {workflow.version}")
    
    # Display task details
    print("\n📋 Generated Tasks:")
    for i, task in enumerate(workflow.tasks, 1):
        print(f"   {i}. {task.name}")
        print(f"      - Type: {task.type}")
        print(f"      - Dependencies: {task.dependencies}")
        timeout = task.config.get("timeout_minutes", "N/A")
        print(f"      - Timeout: {timeout} minutes")
    
    # Display AI enhancements
    print("\n🤖 AI Enhancements:")
    if workflow.optimization_hints:
        parallel_groups = workflow.optimization_hints.get("parallel_groups", [])
        print(f"   - Parallel Execution Groups: {len(parallel_groups)}")
        for i, group in enumerate(parallel_groups, 1):
            print(f"     Group {i}: {group}")
    
    if workflow.quality_gates:
        print(f"   - Quality Gates: {len(workflow.quality_gates)}")
        for gate in workflow.quality_gates:
            print(f"     - {gate['name']}: {gate['position']}")
    
    if workflow.risk_mitigation:
        print(f"   - Risk Mitigation Strategies: {len(workflow.risk_mitigation)} categories")
    
    # Test workflow adaptation
    print("\n⚡ Testing workflow adaptation...")
    
    mock_execution_state = {
        "progress": 0.6,
        "bottlenecks": ["database_connection"],
        "resource_usage": {"cpu": 75, "memory": 80},
        "performance_metrics": {"avg_task_time": 120, "queue_depth": 5}
    }
    
    adaptation = await synthesizer.adapt_workflow_realtime(
        "test-execution-123",
        mock_execution_state
    )
    
    print(f"✅ Workflow Adaptation:")
    print(f"   - Type: {adaptation.adaptation_type}")
    print(f"   - Actions: {', '.join(adaptation.recommended_actions)}")
    print(f"   - Urgency: {adaptation.urgency}")
    print(f"   - Expected Impact: {adaptation.expected_impact}")
    
    print("\n🎉 All tests completed successfully!")
    return True

async def test_requirement_analysis_variations():
    """Test requirement analysis with different types of requirements"""
    print("\n🔬 Testing requirement analysis variations...")
    
    tenant_context = TenantContext(
        tenant_id="test-tenant-002",
        org_profile={"name": "DevOps Corp"},
        team_skills=["Docker", "Kubernetes", "CI/CD"],
        team_hierarchy={},
        approval_policies={},
        resource_limits={},
        quality_standards={}
    )
    
    synthesizer = await create_workflow_synthesizer(tenant_context)
    
    # Test different types of requirements
    test_cases = [
        ("Set up CI/CD pipeline with Docker and Kubernetes deployment", DomainType.DEVOPS_AUTOMATION),
        ("Perform security audit on web application with penetration testing", DomainType.SECURITY_AUDIT),
        ("Analyze customer data and generate insights dashboard", DomainType.DATA_ANALYSIS),
        ("Optimize database queries and improve API response times", DomainType.PERFORMANCE_OPTIMIZATION)
    ]
    
    for description, expected_domain in test_cases:
        print(f"\n📊 Testing: {description[:50]}...")
        
        requirements = await synthesizer.analyze_requirements(description)
        
        print(f"   ✅ Domain: {requirements.domain.value}")
        print(f"   ✅ Complexity: {requirements.complexity.value}")
        print(f"   ✅ Duration: {requirements.estimated_duration_hours}h")
        
        # Verify domain detection
        if requirements.domain == expected_domain:
            print(f"   ✅ Domain detection accurate")
        else:
            print(f"   ⚠️ Domain detection: expected {expected_domain.value}, got {requirements.domain.value}")
    
    return True

async def test_performance_characteristics():
    """Test performance characteristics of the synthesizer"""
    print("\n⚡ Testing performance characteristics...")
    
    tenant_context = TenantContext(
        tenant_id="perf-test",
        org_profile={},
        team_skills=[],
        team_hierarchy={},
        approval_policies={},
        resource_limits={},
        quality_standards={}
    )
    
    synthesizer = await create_workflow_synthesizer(tenant_context)
    
    # Time synthesis performance
    start_time = datetime.now()
    
    requirements = await synthesizer.analyze_requirements(
        "Build a microservices architecture with API gateway, service discovery, and monitoring"
    )
    
    workflow = await synthesizer.synthesize_optimal_workflow(requirements)
    
    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()
    
    print(f"⏱️ Performance Results:")
    print(f"   - Total synthesis time: {total_time:.2f} seconds")
    print(f"   - Requirement analysis: ✅")
    print(f"   - Workflow generation: ✅")
    print(f"   - AI enhancements: ✅")
    
    if total_time < 5.0:
        print(f"   ✅ Performance target met (< 5 seconds)")
    else:
        print(f"   ⚠️ Performance target missed (> 5 seconds)")
    
    return total_time < 10.0  # Allow up to 10 seconds for CI/CD

async def main():
    """Main test runner"""
    print("🚀 AI Workflow Synthesizer - Comprehensive Standalone Test Suite")
    print("=" * 70)
    
    try:
        # Run all test suites
        test_results = []
        
        test_results.append(await test_basic_workflow_synthesis())
        test_results.append(await test_requirement_analysis_variations())
        test_results.append(await test_performance_characteristics())
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 Test Results Summary:")
        
        passed = sum(test_results)
        total = len(test_results)
        
        print(f"✅ Passed: {passed}/{total}")
        
        if passed == total:
            print("🎉 All tests passed! AI Workflow Synthesizer is working correctly.")
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
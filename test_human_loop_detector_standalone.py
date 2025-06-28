#!/usr/bin/env python3
"""
Standalone test for Human-Loop Intelligence Detector

Tests the human loop detector in isolation to verify intelligent detection
of when human intervention is needed in workflows.
"""

import asyncio
import sys
from datetime import datetime

sys.path.append('/home/devag/git/dev-assist')

from supervisor_agent.intelligence.human_loop_detector import (
    HumanLoopIntelligenceDetector,
    HumanInvolvementAnalysis,
    HumanInvolvementPoint,
    ApprovalWorkflow,
    RiskLevel,
    ApprovalUrgency,
    HumanInvolvementType,
    create_human_loop_detector
)
from supervisor_agent.intelligence.workflow_synthesizer import (
    RequirementAnalysis,
    TenantContext,
    ClaudeAgentWrapper,
    RequirementComplexity,
    DomainType
)


async def test_human_involvement_analysis():
    """Test human involvement need analysis"""
    print("🔍 Testing Human Involvement Analysis...")
    
    # Create test requirement analysis
    requirements = RequirementAnalysis(
        description="Implement secure payment processing system with PCI compliance",
        complexity=RequirementComplexity.COMPLEX,
        domain=DomainType.SOFTWARE_DEVELOPMENT,
        estimated_duration_hours=120,
        dependencies=["payment_gateway_api", "security_framework", "database_encryption"],
        required_skills=["payment_processing", "security", "compliance", "backend_development"],
        constraints={"deadline": "strict"},
        success_criteria=["PCI compliance", "security audit pass", "performance benchmarks"]
    )
    
    # Create tenant context with approval policies
    tenant_context = TenantContext(
        tenant_id="financial-services-team",
        org_profile={"name": "Financial Services Division", "size": "large", "industry": "fintech"},
        team_skills=["python", "security", "payments", "compliance"],
        team_hierarchy={"cto": 1, "security_lead": 1, "senior_dev": 3, "dev": 5},
        approval_policies={
            "security_review": {
                "triggers": ["security", "pci", "payment"],
                "approvers": ["security_lead", "compliance_officer"],
                "threshold": 2
            },
            "production_deployment": {
                "triggers": ["deployment", "production"],
                "approvers": ["cto", "devops_lead"],
                "threshold": 1
            }
        },
        resource_limits={"max_budget": 50000, "max_duration_hours": 160},
        quality_standards={"security_review": True, "code_coverage": 0.9, "compliance_check": True}
    )
    
    print(f"✅ Created test requirements: {requirements.description[:60]}...")
    print(f"   - Complexity: {requirements.complexity.value}")
    print(f"   - Domain: {requirements.domain.value}")
    print(f"   - Duration: {requirements.estimated_duration_hours} hours")
    print(f"   - Dependencies: {len(requirements.dependencies)}")
    
    # Test human loop detector
    detector = await create_human_loop_detector()
    
    analysis = await detector.analyze_human_involvement_need(requirements, tenant_context)
    
    print(f"🧠 Human Involvement Analysis Results:")
    print(f"   - Analysis ID: {analysis.analysis_id}")
    print(f"   - Risk factors: {len(analysis.risk_assessment)}")
    print(f"   - Involvement points: {len(analysis.involvement_points)}")
    print(f"   - Confidence score: {analysis.confidence_score:.2f}")
    
    # Display risk assessment
    if analysis.risk_assessment:
        print(f"\n⚠️ Risk Assessment:")
        for i, risk in enumerate(analysis.risk_assessment[:3], 1):
            print(f"   {i}. {risk.factor_name} - {risk.risk_level.value}")
            print(f"      Description: {risk.description}")
            print(f"      Human expertise required: {risk.human_expertise_required}")
            print(f"      Confidence: {risk.confidence_score:.2f}")
    
    # Display involvement points
    if analysis.involvement_points:
        print(f"\n👥 Human Involvement Points:")
        for i, point in enumerate(analysis.involvement_points, 1):
            print(f"   {i}. {point.involvement_type.value.title()} - {point.urgency.value}")
            print(f"      Required roles: {', '.join(point.required_roles)}")
            print(f"      Estimated time: {point.estimated_time_hours:.1f} hours")
            print(f"      Can be parallelized: {point.can_be_parallelized}")
            print(f"      Confidence: {point.confidence_score:.2f}")
    
    # Display autonomous capabilities
    if analysis.autonomous_capabilities:
        print(f"\n🤖 Autonomous Capabilities:")
        for capability, details in analysis.autonomous_capabilities.items():
            print(f"   - {capability}: {details}")
    
    # Display recommendations
    if analysis.recommendations:
        print(f"\n💡 Recommendations:")
        for rec_type, rec_details in analysis.recommendations.items():
            print(f"   - {rec_type}: {rec_details}")
    
    return True


async def test_dynamic_approval_workflow():
    """Test dynamic approval workflow generation"""
    print("\n🔄 Testing Dynamic Approval Workflow Generation...")
    
    # Create a mock human involvement analysis
    requirements = RequirementAnalysis(
        description="Deploy new authentication service to production",
        complexity=RequirementComplexity.MODERATE,
        domain=DomainType.DEVOPS_AUTOMATION,
        estimated_duration_hours=40,
        dependencies=["auth_service", "database", "load_balancer"],
        required_skills=["devops", "security", "monitoring"],
        constraints={"deadline": "flexible"},
        success_criteria=["zero downtime deployment", "security checks pass"]
    )
    
    tenant_context = TenantContext(
        tenant_id="platform-team",
        org_profile={"name": "Platform Engineering", "size": "medium"},
        team_skills=["kubernetes", "terraform", "monitoring"],
        team_hierarchy={"platform_lead": 1, "senior_sre": 2, "sre": 4},
        approval_policies={
            "production_deployment": {
                "triggers": ["production", "deploy"],
                "approvers": ["platform_lead", "security_team"],
                "threshold": 1
            }
        },
        resource_limits={},
        quality_standards={"deployment_checklist": True}
    )
    
    detector = await create_human_loop_detector()
    
    # First get human involvement analysis
    involvement_analysis = await detector.analyze_human_involvement_need(requirements, tenant_context)
    
    print(f"✅ Got involvement analysis with {len(involvement_analysis.involvement_points)} points")
    
    # Generate dynamic approval workflow
    workflow = await detector.generate_dynamic_approval_workflow(involvement_analysis)
    
    print(f"🎯 Dynamic Approval Workflow Generated:")
    print(f"   - Workflow ID: {workflow.workflow_id}")
    print(f"   - Name: {workflow.name}")
    print(f"   - Description: {workflow.description}")
    print(f"   - Steps: {len(workflow.steps)}")
    print(f"   - Estimated time: {workflow.total_estimated_time_hours:.1f} hours")
    
    # Display workflow steps
    if workflow.steps:
        print(f"\n📋 Workflow Steps:")
        for i, step in enumerate(workflow.steps, 1):
            print(f"   {i}. {step.step_name}")
            print(f"      Required roles: {', '.join(step.required_roles)}")
            print(f"      Timeout: {step.timeout_hours:.1f} hours")
            print(f"      Parallel with: {', '.join(step.parallel_with) if step.parallel_with else 'None'}")
            print(f"      Depends on: {', '.join(step.depends_on) if step.depends_on else 'None'}")
            if step.auto_approve_conditions:
                print(f"      Auto-approve conditions: {step.auto_approve_conditions}")
    
    # Display parallel groups
    if workflow.parallel_groups:
        print(f"\n🔄 Parallel Groups:")
        for i, group in enumerate(workflow.parallel_groups, 1):
            print(f"   Group {i}: {', '.join(group)}")
    
    # Display bypass conditions
    if workflow.bypass_conditions:
        print(f"\n⚡ Bypass Conditions:")
        for condition, value in workflow.bypass_conditions.items():
            print(f"   - {condition}: {value}")
    
    # Display emergency override
    if workflow.emergency_override:
        print(f"\n🚨 Emergency Override:")
        for override_type, details in workflow.emergency_override.items():
            print(f"   - {override_type}: {details}")
    
    return True


async def test_bypass_condition_evaluation():
    """Test bypass condition evaluation"""
    print("\n⚡ Testing Bypass Condition Evaluation...")
    
    # Create mock involvement analysis with bypass conditions
    requirements = RequirementAnalysis(
        description="Update configuration settings",
        complexity=RequirementComplexity.SIMPLE,
        domain=DomainType.SYSTEM_INTEGRATION,
        estimated_duration_hours=8,
        dependencies=[],
        required_skills=["configuration"],
        constraints={},
        success_criteria=["configuration validated", "no service interruption"]
    )
    
    tenant_context = TenantContext(
        tenant_id="config-team",
        org_profile={"name": "Configuration Team"},
        team_skills=["configuration", "yaml"],
        team_hierarchy={"config_lead": 1, "config_dev": 2},
        approval_policies={},
        resource_limits={},
        quality_standards={}
    )
    
    detector = await create_human_loop_detector()
    analysis = await detector.analyze_human_involvement_need(requirements, tenant_context)
    
    print(f"✅ Created analysis with {len(analysis.involvement_points)} involvement points")
    
    # Test various execution contexts
    test_contexts = [
        {
            "name": "High Quality Context",
            "context": {
                "quality_score_above": 0.95,
                "automated_tests_pass": True,
                "low_risk_assessment": 0.2,
                "code_review_approved": True
            }
        },
        {
            "name": "Medium Quality Context",
            "context": {
                "quality_score_above": 0.75,
                "automated_tests_pass": True,
                "low_risk_assessment": 0.5,
                "code_review_approved": False
            }
        },
        {
            "name": "Low Quality Context", 
            "context": {
                "quality_score_above": 0.60,
                "automated_tests_pass": False,
                "low_risk_assessment": 0.8,
                "code_review_approved": False
            }
        }
    ]
    
    for test_case in test_contexts:
        print(f"\n🧪 Testing {test_case['name']}:")
        
        bypass_results = await detector.evaluate_bypass_conditions(
            analysis, test_case['context']
        )
        
        print(f"   - Context: {test_case['context']}")
        print(f"   - Bypass results: {bypass_results}")
        
        can_bypass_all = all(bypass_results.values()) if bypass_results else False
        print(f"   - Can bypass all checkpoints: {can_bypass_all}")
    
    return True


async def test_escalation_trigger_detection():
    """Test escalation trigger detection"""
    print("\n🚨 Testing Escalation Trigger Detection...")
    
    detector = await create_human_loop_detector()
    
    # Test various execution contexts that should trigger escalations
    escalation_scenarios = [
        {
            "name": "Repeated Failures",
            "context": {
                "failure_count": 5,
                "execution_time_ratio": 1.2,
                "error_rate": 0.1
            }
        },
        {
            "name": "Timeline Overrun",
            "context": {
                "failure_count": 1,
                "execution_time_ratio": 3.5,
                "error_rate": 0.05
            }
        },
        {
            "name": "High Error Rate",
            "context": {
                "failure_count": 2,
                "execution_time_ratio": 1.5,
                "error_rate": 0.45
            }
        },
        {
            "name": "Multiple Issues",
            "context": {
                "failure_count": 4,
                "execution_time_ratio": 2.8,
                "error_rate": 0.35
            }
        },
        {
            "name": "Normal Execution",
            "context": {
                "failure_count": 0,
                "execution_time_ratio": 0.95,
                "error_rate": 0.02
            }
        }
    ]
    
    for scenario in escalation_scenarios:
        print(f"\n🎯 Testing {scenario['name']}:")
        print(f"   - Context: {scenario['context']}")
        
        triggers = await detector.detect_escalation_triggers(scenario['context'])
        
        print(f"   - Escalation triggers detected: {len(triggers)}")
        
        for i, trigger in enumerate(triggers, 1):
            print(f"     {i}. {trigger['type']} - {trigger['urgency']}")
            print(f"        Description: {trigger['description']}")
    
    return True


async def test_risk_analysis():
    """Test comprehensive risk analysis"""
    print("\n📊 Testing Risk Analysis...")
    
    # Test different types of requirements
    risk_scenarios = [
        {
            "name": "High-Risk Security Project",
            "requirements": RequirementAnalysis(
                description="Implement encryption for sensitive customer financial data with PCI DSS compliance",
                complexity=RequirementComplexity.ENTERPRISE,
                domain=DomainType.SECURITY_AUDIT,
                estimated_duration_hours=200,
                dependencies=["hsm_integration", "audit_logging", "key_management"],
                required_skills=["cryptography", "pci_compliance", "security_architecture"],
                constraints={"deadline": "strict"},
                success_criteria=["PCI DSS compliance", "encryption standards met", "audit trail complete"]
            )
        },
        {
            "name": "Medium-Risk Feature Development",
            "requirements": RequirementAnalysis(
                description="Add user dashboard with analytics and reporting features",
                complexity=RequirementComplexity.MODERATE,
                domain=DomainType.SOFTWARE_DEVELOPMENT,
                estimated_duration_hours=80,
                dependencies=["analytics_api", "charting_library"],
                required_skills=["react", "data_visualization", "api_integration"],
                constraints={"deadline": "flexible"},
                success_criteria=["user acceptance", "performance benchmarks", "accessibility compliance"]
            )
        },
        {
            "name": "Low-Risk Configuration Update",
            "requirements": RequirementAnalysis(
                description="Update logging configuration and monitoring thresholds",
                complexity=RequirementComplexity.SIMPLE,
                domain=DomainType.SYSTEM_INTEGRATION,
                estimated_duration_hours=16,
                dependencies=[],
                required_skills=["configuration_management"],
                constraints={},
                success_criteria=["configuration validated", "monitoring operational"]
            )
        }
    ]
    
    detector = await create_human_loop_detector()
    
    for scenario in risk_scenarios:
        print(f"\n🎯 Analyzing {scenario['name']}:")
        print(f"   - Description: {scenario['requirements'].description[:60]}...")
        print(f"   - Complexity: {scenario['requirements'].complexity.value}")
        print(f"   - Duration: {scenario['requirements'].estimated_duration_hours} hours")
        
        # Get risk assessment
        risk_assessment = await detector.risk_analyzer.assess_risks(scenario['requirements'])
        
        print(f"\n   📋 Risk Assessment Results:")
        for risk_type, risk_data in risk_assessment.items():
            if isinstance(risk_data, dict):
                score = risk_data.get("score", 0)
                level = risk_data.get("level", "unknown")
                description = risk_data.get("description", "")
                print(f"     - {risk_type}: {score:.2f} ({level}) - {description}")
    
    return True


async def test_error_handling():
    """Test error handling and fallback mechanisms"""
    print("\n🛡️ Testing Error Handling...")
    
    # Test with invalid/minimal data
    minimal_requirements = RequirementAnalysis(
        description="",
        complexity=RequirementComplexity.SIMPLE,
        domain=DomainType.SYSTEM_INTEGRATION,
        estimated_duration_hours=1,
        dependencies=[],
        required_skills=[],
        constraints={},
        success_criteria=[]
    )
    
    minimal_context = TenantContext(
        tenant_id="test",
        org_profile={},
        team_skills=[],
        team_hierarchy={},
        approval_policies={},
        resource_limits={},
        quality_standards={}
    )
    
    # Test without Claude agent (should use fallback)
    detector_no_claude = HumanLoopIntelligenceDetector(claude_agent=None)
    
    try:
        analysis = await detector_no_claude.analyze_human_involvement_need(
            minimal_requirements, minimal_context
        )
        
        print(f"✅ Fallback analysis created:")
        print(f"   - Analysis ID: {analysis.analysis_id}")
        print(f"   - Involvement points: {len(analysis.involvement_points)}")
        print(f"   - Confidence: {analysis.confidence_score:.2f}")
        
        if analysis.recommendations.get("error"):
            print(f"   - Fallback reason: {analysis.recommendations['error']}")
        
    except Exception as e:
        print(f"❌ Error handling failed: {str(e)}")
        return False
    
    # Test workflow generation with fallback
    try:
        workflow = await detector_no_claude.generate_dynamic_approval_workflow(analysis)
        
        print(f"✅ Fallback workflow created:")
        print(f"   - Workflow ID: {workflow.workflow_id}")
        print(f"   - Steps: {len(workflow.steps)}")
        print(f"   - Name: {workflow.name}")
        
    except Exception as e:
        print(f"❌ Workflow fallback failed: {str(e)}")
        return False
    
    return True


async def test_performance_characteristics():
    """Test performance characteristics"""
    print("\n⏱️ Testing Performance Characteristics...")
    
    # Create complex scenario for performance testing
    complex_requirements = RequirementAnalysis(
        description="Large-scale microservices migration with security updates and compliance requirements",
        complexity=RequirementComplexity.ENTERPRISE,
        domain=DomainType.SOFTWARE_DEVELOPMENT,
        estimated_duration_hours=500,
        dependencies=["service_mesh", "security_framework", "monitoring", "ci_cd", "database_migration"],
        required_skills=["microservices", "kubernetes", "security", "compliance", "devops", "database"],
        constraints={"deadline": "strict"},
        success_criteria=["zero_downtime_migration", "security_compliance", "performance_benchmarks"]
    )
    
    complex_context = TenantContext(
        tenant_id="enterprise-team",
        org_profile={"name": "Enterprise Platform", "size": "large"},
        team_skills=["microservices", "security", "compliance"],
        team_hierarchy={"cto": 1, "arch": 2, "leads": 5, "seniors": 10, "devs": 20},
        approval_policies={
            "architecture_review": {"triggers": ["microservices"], "approvers": ["architect"]},
            "security_review": {"triggers": ["security"], "approvers": ["security_team"]},
            "compliance_review": {"triggers": ["compliance"], "approvers": ["compliance_team"]},
            "deployment_approval": {"triggers": ["production"], "approvers": ["cto", "platform_lead"]}
        },
        resource_limits={"max_budget": 500000},
        quality_standards={"security_scan": True, "compliance_check": True}
    )
    
    print(f"📏 Performance Test Setup:")
    print(f"   - Requirements complexity: {complex_requirements.complexity.value}")
    print(f"   - Dependencies: {len(complex_requirements.dependencies)}")
    print(f"   - Required skills: {len(complex_requirements.required_skills)}")
    print(f"   - Approval policies: {len(complex_context.approval_policies)}")
    
    detector = await create_human_loop_detector()
    
    # Time the analysis
    start_time = datetime.now()
    
    analysis = await detector.analyze_human_involvement_need(complex_requirements, complex_context)
    
    end_time = datetime.now()
    analysis_time = (end_time - start_time).total_seconds()
    
    print(f"⚡ Performance Results:")
    print(f"   - Analysis time: {analysis_time:.2f} seconds")
    print(f"   - Risk factors identified: {len(analysis.risk_assessment)}")
    print(f"   - Involvement points: {len(analysis.involvement_points)}")
    print(f"   - Confidence score: {analysis.confidence_score:.2f}")
    
    # Performance targets
    if analysis_time < 3.0:
        print(f"   ✅ Performance target met (< 3 seconds)")
    else:
        print(f"   ⚠️ Performance target missed (> 3 seconds)")
    
    # Test workflow generation performance
    start_time = datetime.now()
    workflow = await detector.generate_dynamic_approval_workflow(analysis)
    end_time = datetime.now()
    workflow_time = (end_time - start_time).total_seconds()
    
    print(f"   - Workflow generation time: {workflow_time:.2f} seconds")
    print(f"   - Workflow steps: {len(workflow.steps)}")
    
    return analysis_time < 5.0  # Allow up to 5 seconds


async def main():
    """Main test runner"""
    print("🚀 Human-Loop Intelligence Detector - Comprehensive Test Suite")
    print("=" * 80)
    
    try:
        # Run all test suites
        test_results = []
        
        test_results.append(await test_human_involvement_analysis())
        test_results.append(await test_dynamic_approval_workflow())
        test_results.append(await test_bypass_condition_evaluation())
        test_results.append(await test_escalation_trigger_detection())
        test_results.append(await test_risk_analysis())
        test_results.append(await test_error_handling())
        test_results.append(await test_performance_characteristics())
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 Test Results Summary:")
        
        passed = sum(test_results)
        total = len(test_results)
        
        print(f"✅ Passed: {passed}/{total}")
        
        if passed == total:
            print("🎉 All tests passed! Human-Loop Intelligence Detector is working correctly.")
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
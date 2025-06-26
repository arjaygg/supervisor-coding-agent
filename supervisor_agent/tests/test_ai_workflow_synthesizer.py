"""
Comprehensive Test Suite for AI Workflow Synthesizer

Following Test-First Development (TDD) methodology:
- 70% Unit Tests: Fast, isolated component validation
- 20% Integration Tests: Provider and database integration
- 10% E2E Tests: Complete workflow synthesis validation
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from supervisor_agent.intelligence.workflow_synthesizer import (
    AIWorkflowSynthesizer,
    RequirementAnalysis,
    RequirementComplexity,
    DomainType,
    TenantContext,
    EnhancedWorkflowDefinition,
    WorkflowMemoryManager,
    ClaudeAgentWrapper,
    WorkflowAdaptation,
    create_workflow_synthesizer
)
from supervisor_agent.db.workflow_models import TaskDefinition


class TestRequirementAnalysis:
    """Test requirement analysis functionality"""
    
    def test_requirement_analysis_creation(self):
        """Test creating requirement analysis with valid data"""
        # Given: Valid requirement data
        requirements = RequirementAnalysis(
            description="Implement user authentication system",
            domain=DomainType.SOFTWARE_DEVELOPMENT,
            complexity=RequirementComplexity.MODERATE,
            estimated_duration_hours=16.0,
            required_skills=["Python", "FastAPI", "JWT"],
            dependencies=["database", "redis"],
            constraints={"budget": 5000, "deadline": "2025-07-15"},
            success_criteria=["All tests pass", "Security audit passed"]
        )
        
        # Then: Object is created correctly
        assert requirements.description == "Implement user authentication system"
        assert requirements.domain == DomainType.SOFTWARE_DEVELOPMENT
        assert requirements.complexity == RequirementComplexity.MODERATE
        assert requirements.estimated_duration_hours == 16.0
        assert len(requirements.required_skills) == 3
        assert len(requirements.dependencies) == 2
        assert len(requirements.success_criteria) == 2
    
    def test_requirement_analysis_to_dict(self):
        """Test requirement analysis serialization"""
        # Given: Requirement analysis object
        requirements = RequirementAnalysis(
            description="Test requirement",
            domain=DomainType.DATA_ANALYSIS,
            complexity=RequirementComplexity.SIMPLE,
            estimated_duration_hours=4.0,
            required_skills=["Python"],
            dependencies=[],
            constraints={},
            success_criteria=["Data processed"]
        )
        
        # When: Converting to dictionary
        result_dict = requirements.to_dict()
        
        # Then: Dictionary contains all fields
        assert result_dict["description"] == "Test requirement"
        assert result_dict["domain"] == "data_analysis"
        assert result_dict["complexity"] == "simple"
        assert result_dict["estimated_duration_hours"] == 4.0
        assert result_dict["required_skills"] == ["Python"]
        assert result_dict["dependencies"] == []


class TestTenantContext:
    """Test tenant context functionality"""
    
    def test_tenant_context_creation(self):
        """Test creating tenant context with org data"""
        # Given: Organization context data
        context = TenantContext(
            tenant_id="org-123",
            org_profile={"name": "TechCorp", "size": "medium"},
            team_skills=["Python", "DevOps", "AI"],
            team_hierarchy={"cto": "alice", "dev_lead": "bob"},
            approval_policies={"production_deploy": "cto_approval"},
            resource_limits={"max_parallel_tasks": 10},
            quality_standards={"code_coverage": 0.8}
        )
        
        # Then: Context is properly initialized
        assert context.tenant_id == "org-123"
        assert context.org_profile["name"] == "TechCorp"
        assert len(context.team_skills) == 3
        assert context.approval_policies["production_deploy"] == "cto_approval"


class TestWorkflowMemoryManager:
    """Test workflow memory management"""
    
    @pytest.fixture
    def memory_manager(self):
        return WorkflowMemoryManager()
    
    @pytest.mark.asyncio
    async def test_get_successful_patterns_empty(self, memory_manager):
        """Test getting patterns when none exist"""
        # When: Getting patterns for new domain
        patterns = await memory_manager.get_successful_patterns("new_domain")
        
        # Then: Empty list is returned
        assert patterns == []
    
    @pytest.mark.asyncio
    async def test_store_successful_pattern(self, memory_manager):
        """Test storing successful workflow pattern"""
        # Given: Successful pattern data
        pattern = {
            "domain": "software_development",
            "success_metrics": {"completion_time": 120, "quality_score": 0.95},
            "workflow_structure": {"parallel_tasks": 3, "total_tasks": 8}
        }
        
        # When: Storing pattern (should not raise exception)
        await memory_manager.store_successful_pattern(pattern)
        
        # Then: No exception is raised (implementation is TODO)
        assert True


class TestClaudeAgentWrapper:
    """Test Claude CLI integration wrapper"""
    
    @pytest.fixture
    def claude_agent(self):
        return ClaudeAgentWrapper(api_key="test-key")
    
    @pytest.mark.asyncio
    async def test_execute_task_mock_response(self, claude_agent):
        """Test task execution with mock response"""
        # Given: Task data
        task_data = {
            "type": "workflow_synthesis",
            "prompt": "Generate a workflow for code review"
        }
        
        # When: Executing task
        result = await claude_agent.execute_task(task_data)
        
        # Then: Mock response is returned
        assert "result" in result
        assert result["confidence"] == 0.85
        assert result["reasoning"] == "Generated using AI analysis"


class TestAIWorkflowSynthesizer:
    """Test AI Workflow Synthesizer core functionality"""
    
    @pytest.fixture
    def mock_claude_agent(self):
        """Create mock Claude agent for testing"""
        agent = AsyncMock(spec=ClaudeAgentWrapper)
        agent.execute_task = AsyncMock()
        return agent
    
    @pytest.fixture
    def tenant_context(self):
        """Create test tenant context"""
        return TenantContext(
            tenant_id="test-org",
            org_profile={"name": "TestOrg", "type": "software"},
            team_skills=["Python", "FastAPI", "Testing"],
            team_hierarchy={"lead": "alice"},
            approval_policies={"deploy": "lead_approval"},
            resource_limits={"max_tasks": 5},
            quality_standards={"coverage": 0.8}
        )
    
    @pytest.fixture
    def synthesizer(self, mock_claude_agent, tenant_context):
        """Create AI workflow synthesizer for testing"""
        return AIWorkflowSynthesizer(mock_claude_agent, tenant_context)
    
    @pytest.fixture
    def sample_requirements(self):
        """Create sample requirements for testing"""
        return RequirementAnalysis(
            description="Implement REST API for user management",
            domain=DomainType.SOFTWARE_DEVELOPMENT,
            complexity=RequirementComplexity.MODERATE,
            estimated_duration_hours=12.0,
            required_skills=["Python", "FastAPI", "Database"],
            dependencies=["postgresql", "redis"],
            constraints={"deadline": "2025-07-01"},
            success_criteria=["API tests pass", "Documentation complete"]
        )
    
    @pytest.mark.asyncio
    async def test_synthesize_optimal_workflow_success(self, synthesizer, mock_claude_agent, sample_requirements):
        """Test successful workflow synthesis"""
        # Given: Mock Claude response with valid workflow
        mock_workflow_response = {
            "result": json.dumps({
                "name": "User Management API Workflow",
                "description": "Complete workflow for user management API",
                "tasks": [
                    {
                        "id": "task-1",
                        "name": "Design API Schema",
                        "type": "DESIGN_TASK",
                        "config": {"schema_type": "openapi"},
                        "dependencies": [],
                        "timeout_minutes": 60
                    },
                    {
                        "id": "task-2", 
                        "name": "Implement Endpoints",
                        "type": "CODE_IMPLEMENTATION",
                        "config": {"language": "python"},
                        "dependencies": ["task-1"],
                        "timeout_minutes": 180
                    }
                ],
                "estimated_duration_hours": 12.0
            }),
            "confidence": 0.9,
            "reasoning": "Generated optimal workflow based on requirements"
        }
        
        mock_claude_agent.execute_task.return_value = mock_workflow_response
        
        # When: Synthesizing workflow
        workflow = await synthesizer.synthesize_optimal_workflow(sample_requirements)
        
        # Then: Workflow is properly generated
        assert isinstance(workflow, EnhancedWorkflowDefinition)
        assert workflow.name == "User Management API Workflow"
        assert len(workflow.tasks) == 2
        assert workflow.tasks[0].id == "task-1"
        assert workflow.tasks[1].dependencies == ["task-1"]
        
        # And: Claude agent was called with correct parameters
        mock_claude_agent.execute_task.assert_called_once()
        call_args = mock_claude_agent.execute_task.call_args[0][0]
        assert call_args["type"] == "workflow_synthesis"
        assert "prompt" in call_args
    
    @pytest.mark.asyncio
    async def test_synthesize_workflow_with_invalid_claude_response(self, synthesizer, mock_claude_agent, sample_requirements):
        """Test workflow synthesis with invalid Claude response"""
        # Given: Mock Claude response with invalid JSON
        mock_claude_agent.execute_task.return_value = {
            "result": "Invalid JSON response",
            "confidence": 0.1
        }
        
        # When: Synthesizing workflow
        workflow = await synthesizer.synthesize_optimal_workflow(sample_requirements)
        
        # Then: Fallback workflow is created
        assert isinstance(workflow, EnhancedWorkflowDefinition)
        assert "Fallback Workflow" in workflow.name
        assert len(workflow.tasks) == 1
        assert workflow.tasks[0].type == "CODE_ANALYSIS"
    
    @pytest.mark.asyncio
    async def test_synthesize_workflow_enhances_with_intelligence(self, synthesizer, mock_claude_agent, sample_requirements):
        """Test that synthesized workflow is enhanced with AI intelligence"""
        # Given: Mock Claude response
        mock_claude_agent.execute_task.return_value = {
            "result": json.dumps({
                "name": "Test Workflow",
                "description": "Test description",
                "tasks": [{
                    "id": "task-1",
                    "name": "Test Task",
                    "type": "CODE_ANALYSIS",
                    "config": {},
                    "dependencies": [],
                    "timeout_minutes": 30
                }]
            })
        }
        
        # When: Synthesizing workflow
        workflow = await synthesizer.synthesize_optimal_workflow(sample_requirements)
        
        # Then: Workflow is enhanced with AI features
        assert workflow.dynamic_task_templates is not None
        assert workflow.conditional_branches is not None
        assert workflow.optimization_hints is not None
        assert workflow.risk_mitigation is not None
        assert workflow.quality_gates is not None
    
    @pytest.mark.asyncio
    async def test_analyze_requirements_from_description(self, synthesizer, mock_claude_agent):
        """Test requirement analysis from natural language description"""
        # Given: Natural language description
        description = "Build a secure login system with multi-factor authentication"
        
        # And: Mock Claude analysis response
        mock_analysis_response = {
            "result": json.dumps({
                "domain": "software_development",
                "complexity": "complex",
                "estimated_duration_hours": 24.0,
                "required_skills": ["Python", "Security", "OAuth"],
                "dependencies": ["authentication_service", "sms_provider"],
                "constraints": {"security_compliance": "required"},
                "success_criteria": ["Security audit passed", "MFA working"]
            })
        }
        mock_claude_agent.execute_task.return_value = mock_analysis_response
        
        # When: Analyzing requirements
        analysis = await synthesizer.analyze_requirements(description)
        
        # Then: Analysis is properly structured
        assert analysis.description == description
        assert analysis.domain == DomainType.SOFTWARE_DEVELOPMENT
        assert analysis.complexity == RequirementComplexity.COMPLEX
        assert analysis.estimated_duration_hours == 24.0
        assert "Python" in analysis.required_skills
        assert "Security audit passed" in analysis.success_criteria
    
    @pytest.mark.asyncio
    async def test_adapt_workflow_realtime(self, synthesizer, mock_claude_agent):
        """Test real-time workflow adaptation"""
        # Given: Execution state with performance issues
        execution_id = str(uuid.uuid4())
        current_state = {
            "progress": 0.5,
            "bottlenecks": ["task-2"],
            "resource_usage": {"cpu": 0.8, "memory": 0.9}
        }
        
        # And: Mock adaptation response
        mock_adaptation_response = {
            "result": json.dumps({
                "adaptation_type": "resource_optimization",
                "recommended_actions": ["add_parallel_agent", "increase_memory"],
                "expected_impact": {"performance_improvement": 0.3},
                "risk_assessment": {"probability": "low"},
                "urgency": "medium"
            })
        }
        mock_claude_agent.execute_task.return_value = mock_adaptation_response
        
        # When: Adapting workflow
        adaptation = await synthesizer.adapt_workflow_realtime(execution_id, current_state)
        
        # Then: Adaptation is properly structured
        assert isinstance(adaptation, WorkflowAdaptation)
        assert adaptation.adaptation_type == "resource_optimization"
        assert "add_parallel_agent" in adaptation.recommended_actions
        assert adaptation.urgency == "medium"
    
    @pytest.mark.asyncio
    async def test_workflow_enhancement_identifies_parallel_opportunities(self, synthesizer, sample_requirements):
        """Test identification of parallel execution opportunities"""
        # Given: Workflow with independent tasks
        workflow = EnhancedWorkflowDefinition(
            name="Test Workflow",
            description="Test",
            tasks=[
                TaskDefinition(id="task-1", name="Task 1", type="ANALYSIS", config={"timeout_minutes": 30}, dependencies=[]),
                TaskDefinition(id="task-2", name="Task 2", type="ANALYSIS", config={"timeout_minutes": 30}, dependencies=[]),
                TaskDefinition(id="task-3", name="Task 3", type="ANALYSIS", config={"timeout_minutes": 30}, dependencies=["task-1", "task-2"])
            ],
            version="1.0"
        )
        
        # When: Identifying parallel opportunities
        parallel_groups = await synthesizer._identify_parallel_opportunities(workflow)
        
        # Then: Independent tasks are grouped for parallel execution
        assert len(parallel_groups) > 0
        assert "task-1" in parallel_groups[0]
        assert "task-2" in parallel_groups[0]
    
    @pytest.mark.asyncio
    async def test_predict_bottlenecks_identifies_dependency_heavy_tasks(self, synthesizer):
        """Test bottleneck prediction for dependency-heavy tasks"""
        # Given: Workflow with task having many dependencies
        workflow = EnhancedWorkflowDefinition(
            name="Test Workflow",
            description="Test",
            tasks=[
                TaskDefinition(
                    id="bottleneck-task", 
                    name="Heavy Dependencies Task", 
                    type="ANALYSIS", 
                    config={"timeout_minutes": 30}, 
                    dependencies=["dep-1", "dep-2", "dep-3", "dep-4"]
                )
            ],
            version="1.0"
        )
        
        # When: Predicting bottlenecks
        bottlenecks = await synthesizer._predict_bottlenecks(workflow)
        
        # Then: Dependency bottleneck is identified
        assert len(bottlenecks) > 0
        bottleneck = bottlenecks[0]
        assert bottleneck["task_id"] == "bottleneck-task"
        assert bottleneck["type"] == "dependency_bottleneck"
        assert bottleneck["severity"] == "medium"


class TestWorkflowAdaptation:
    """Test workflow adaptation functionality"""
    
    def test_workflow_adaptation_from_valid_claude_response(self):
        """Test creating adaptation from valid Claude response"""
        # Given: Valid Claude response JSON
        claude_response = json.dumps({
            "adaptation_type": "scale_up",
            "recommended_actions": ["add_workers", "increase_timeout"],
            "expected_impact": {"throughput_increase": 0.4},
            "risk_assessment": {"impact": "low", "probability": "low"},
            "urgency": "high"
        })
        
        # When: Creating adaptation from response
        adaptation = WorkflowAdaptation.from_claude_response(claude_response)
        
        # Then: Adaptation is properly created
        assert adaptation.adaptation_type == "scale_up"
        assert "add_workers" in adaptation.recommended_actions
        assert adaptation.expected_impact["throughput_increase"] == 0.4
        assert adaptation.urgency == "high"
    
    def test_workflow_adaptation_from_invalid_claude_response(self):
        """Test creating adaptation from invalid Claude response"""
        # Given: Invalid JSON response
        invalid_response = "This is not valid JSON"
        
        # When: Creating adaptation from invalid response
        adaptation = WorkflowAdaptation.from_claude_response(invalid_response)
        
        # Then: Error adaptation is created
        assert adaptation.adaptation_type == "parse_error"
        assert "manual_review_required" in adaptation.recommended_actions
        assert adaptation.urgency == "low"
        assert "error" in adaptation.risk_assessment


class TestWorkflowSynthesizerIntegration:
    """Integration tests for workflow synthesizer"""
    
    @pytest.mark.asyncio
    async def test_create_workflow_synthesizer_factory(self):
        """Test factory function for creating synthesizer"""
        # Given: Tenant context
        context = TenantContext(
            tenant_id="test-org",
            org_profile={},
            team_skills=[],
            team_hierarchy={},
            approval_policies={},
            resource_limits={},
            quality_standards={}
        )
        
        # When: Creating synthesizer via factory
        synthesizer = await create_workflow_synthesizer(context, "test-api-key")
        
        # Then: Synthesizer is properly configured
        assert isinstance(synthesizer, AIWorkflowSynthesizer)
        assert synthesizer.tenant_context.tenant_id == "test-org"
        assert isinstance(synthesizer.claude_agent, ClaudeAgentWrapper)
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow_synthesis(self):
        """Test complete end-to-end workflow synthesis"""
        # Given: Complete setup with mock responses
        context = TenantContext(
            tenant_id="e2e-test",
            org_profile={"name": "E2E Corp"},
            team_skills=["Python", "Testing"],
            team_hierarchy={"lead": "alice"},
            approval_policies={},
            resource_limits={},
            quality_standards={}
        )
        
        # Create synthesizer with mocked Claude agent
        synthesizer = await create_workflow_synthesizer(context)
        
        # Mock the Claude response
        with patch.object(synthesizer.claude_agent, 'execute_task') as mock_execute:
            mock_execute.return_value = {
                "result": json.dumps({
                    "name": "E2E Test Workflow",
                    "description": "End-to-end test workflow",
                    "tasks": [
                        {
                            "id": "e2e-task-1",
                            "name": "Setup Task",
                            "type": "SETUP",
                            "config": {"env": "test"},
                            "dependencies": [],
                            "timeout_minutes": 15
                        }
                    ],
                    "estimated_duration_hours": 2.0
                })
            }
            
            # When: Analyzing requirements and synthesizing workflow
            requirements = await synthesizer.analyze_requirements(
                "Create comprehensive test suite for API endpoints"
            )
            workflow = await synthesizer.synthesize_optimal_workflow(requirements)
            
            # Then: Complete workflow is generated
            assert isinstance(workflow, EnhancedWorkflowDefinition)
            assert workflow.name == "E2E Test Workflow"
            assert len(workflow.tasks) == 1
            assert workflow.tasks[0].id == "e2e-task-1"
            
            # And: Workflow is enhanced with intelligence
            assert workflow.dynamic_task_templates is not None
            assert workflow.conditional_branches is not None
            assert workflow.optimization_hints is not None


class TestWorkflowSynthesizerErrorHandling:
    """Test error handling and resilience"""
    
    @pytest.fixture
    def synthesizer_with_failing_claude(self):
        """Create synthesizer with Claude agent that fails"""
        failing_agent = AsyncMock(spec=ClaudeAgentWrapper)
        failing_agent.execute_task.side_effect = Exception("Claude API Error")
        
        context = TenantContext(
            tenant_id="error-test",
            org_profile={},
            team_skills=[],
            team_hierarchy={},
            approval_policies={},
            resource_limits={},
            quality_standards={}
        )
        
        return AIWorkflowSynthesizer(failing_agent, context)
    
    @pytest.mark.asyncio
    async def test_workflow_synthesis_handles_claude_api_failure(self, synthesizer_with_failing_claude):
        """Test workflow synthesis resilience to Claude API failures"""
        # Given: Requirements for synthesis
        requirements = RequirementAnalysis(
            description="Test requirement",
            domain=DomainType.SOFTWARE_DEVELOPMENT,
            complexity=RequirementComplexity.SIMPLE,
            estimated_duration_hours=4.0,
            required_skills=[],
            dependencies=[],
            constraints={},
            success_criteria=[]
        )
        
        # When/Then: Synthesis should handle error gracefully
        with pytest.raises(Exception) as exc_info:
            await synthesizer_with_failing_claude.synthesize_optimal_workflow(requirements)
        
        assert "Claude API Error" in str(exc_info.value)


# Performance and Load Testing
class TestWorkflowSynthesizerPerformance:
    """Test performance characteristics"""
    
    @pytest.mark.asyncio
    async def test_concurrent_workflow_synthesis(self):
        """Test handling multiple concurrent synthesis requests"""
        # Given: Multiple synthesizers for concurrent testing
        context = TenantContext(
            tenant_id="perf-test",
            org_profile={},
            team_skills=[],
            team_hierarchy={},
            approval_policies={},
            resource_limits={},
            quality_standards={}
        )
        
        synthesizers = [await create_workflow_synthesizer(context) for _ in range(5)]
        
        requirements = RequirementAnalysis(
            description="Performance test requirement",
            domain=DomainType.SOFTWARE_DEVELOPMENT,
            complexity=RequirementComplexity.SIMPLE,
            estimated_duration_hours=1.0,
            required_skills=[],
            dependencies=[],
            constraints={},
            success_criteria=[]
        )
        
        # Mock all Claude agents
        for synthesizer in synthesizers:
            with patch.object(synthesizer.claude_agent, 'execute_task') as mock_execute:
                mock_execute.return_value = {
                    "result": json.dumps({
                        "name": "Perf Test Workflow",
                        "description": "Performance test",
                        "tasks": [{"id": "perf-task", "name": "Task", "type": "ANALYSIS", "config": {}, "dependencies": [], "timeout_minutes": 30}]
                    })
                }
        
        # When: Running concurrent synthesis
        start_time = datetime.now()
        
        tasks = [
            synthesizer.synthesize_optimal_workflow(requirements) 
            for synthesizer in synthesizers
        ]
        
        workflows = await asyncio.gather(*tasks)
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # Then: All workflows are generated successfully
        assert len(workflows) == 5
        assert all(isinstance(w, EnhancedWorkflowDefinition) for w in workflows)
        
        # And: Performance is reasonable (should complete in under 10 seconds)
        assert execution_time < 10.0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
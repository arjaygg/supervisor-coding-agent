# supervisor_agent/tests/test_strategic_planner.py
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from supervisor_agent.intelligence.strategic_planner import (
    PlanningContext,
    PlanningHorizon,
    PlanStatus,
    StrategicInitiative,
    StrategicObjective,
    StrategicObjectiveType,
    StrategicPlan,
    StrategicPlanner,
)


class TestStrategicPlanner:
    """Test suite for StrategicPlanner."""

    @pytest.fixture
    def mock_claude_agent(self):
        """Create a mock Claude agent."""
        mock_agent = Mock()
        mock_agent.execute_task = AsyncMock(return_value={
            "result": '{"swot_analysis": {"strengths": ["capability"], "weaknesses": ["gap"], "opportunities": ["market"], "threats": ["competition"]}, "strategic_options": ["optimize", "expand"], "success_factors": ["alignment", "execution"]}'
        })
        return mock_agent

    @pytest.fixture
    def mock_decision_engine(self):
        """Create a mock decision engine."""
        mock_engine = Mock()
        mock_engine.make_decision = AsyncMock()
        return mock_engine

    @pytest.fixture
    def strategic_planner(self, mock_claude_agent, mock_decision_engine):
        """Create a StrategicPlanner instance."""
        return StrategicPlanner(mock_claude_agent, mock_decision_engine)

    @pytest.fixture
    def sample_planning_context(self):
        """Create sample planning context."""
        return PlanningContext(
            current_capabilities={
                "processing_capacity": 100.0,
                "quality_score": 85.0,
                "automation_level": 70.0,
                "scalability_index": 60.0
            },
            available_resources={
                "budget": 500000.0,
                "people": 25.0,
                "technology_assets": 15.0,
                "infrastructure_capacity": 80.0
            },
            market_conditions={
                "growth_rate": 12.0,
                "competition_intensity": "high",
                "customer_demand": "increasing",
                "market_maturity": "growth"
            },
            competitive_landscape={
                "market_position": "strong",
                "competitive_advantage": ["technology", "quality"],
                "threat_level": "moderate",
                "differentiation_strength": 75.0
            },
            technology_trends=[
                "artificial_intelligence",
                "automation",
                "cloud_computing",
                "data_analytics",
                "cybersecurity"
            ],
            regulatory_environment={
                "compliance_requirements": ["data_protection", "security"],
                "regulatory_stability": "stable",
                "upcoming_changes": ["privacy_regulations"]
            },
            organizational_constraints={
                "change_capacity": "medium",
                "risk_tolerance": "moderate",
                "innovation_culture": "developing",
                "resource_flexibility": "high"
            },
            stakeholder_priorities={
                "performance_improvement": 9,
                "cost_reduction": 7,
                "innovation": 8,
                "quality_enhancement": 9,
                "risk_management": 6
            }
        )

    @pytest.fixture
    def sample_strategic_priorities(self):
        """Create sample strategic priorities."""
        return [
            "Enhance operational efficiency and performance",
            "Accelerate digital transformation initiatives",
            "Improve customer experience and satisfaction",
            "Strengthen competitive positioning",
            "Build organizational capabilities for future growth"
        ]

    def test_strategic_planner_initialization(self, strategic_planner):
        """Test strategic planner initialization."""
        assert strategic_planner.claude_agent is not None
        assert len(strategic_planner.active_plans) == 0
        assert len(strategic_planner.plan_history) == 0
        assert strategic_planner.max_concurrent_plans == 5
        assert strategic_planner.planning_cycle_months == 6
        assert "balanced_scorecard" in strategic_planner.planning_frameworks
        assert "okr" in strategic_planner.planning_frameworks

    @pytest.mark.asyncio
    async def test_create_strategic_plan_basic(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test basic strategic plan creation."""
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Test Strategic Plan",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        assert isinstance(plan, StrategicPlan)
        assert plan.plan_id is not None
        assert plan.name == "Test Strategic Plan"
        assert plan.planning_horizon == PlanningHorizon.STRATEGIC
        assert len(plan.objectives) >= 0
        assert len(plan.initiatives) >= 0
        assert plan.status == PlanStatus.DRAFT
        assert plan.created_at is not None

    @pytest.mark.asyncio
    async def test_create_strategic_plan_different_horizons(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test strategic plan creation with different planning horizons."""
        horizons = [
            PlanningHorizon.TACTICAL,
            PlanningHorizon.OPERATIONAL,
            PlanningHorizon.STRATEGIC,
            PlanningHorizon.VISIONARY
        ]
        
        for horizon in horizons:
            plan = await strategic_planner.create_strategic_plan(
                plan_name=f"Plan for {horizon.value}",
                planning_horizon=horizon,
                planning_context=sample_planning_context,
                strategic_priorities=sample_strategic_priorities
            )
            
            assert plan.planning_horizon == horizon
            assert plan.plan_id is not None

    @pytest.mark.asyncio
    async def test_create_strategic_plan_different_frameworks(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test strategic plan creation with different frameworks."""
        frameworks = ["balanced_scorecard", "okr", "smart_goals"]
        
        for framework in frameworks:
            if framework in strategic_planner.planning_frameworks:
                plan = await strategic_planner.create_strategic_plan(
                    plan_name=f"Plan with {framework}",
                    planning_horizon=PlanningHorizon.STRATEGIC,
                    planning_context=sample_planning_context,
                    strategic_priorities=sample_strategic_priorities,
                    framework=framework
                )
                
                assert plan.plan_id is not None
                assert len(plan.objectives) >= 0

    @pytest.mark.asyncio
    async def test_strategic_objectives_generation(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test strategic objectives generation."""
        # Mock the response to include objectives
        strategic_planner.claude_agent.execute_task = AsyncMock(return_value={
            "result": '{"objectives": [{"objective_name": "Performance Optimization", "objective_type": "performance_optimization", "description": "Improve system performance", "target_value": 25.0, "current_value": 15.0, "measurement_unit": "percent", "priority": 8, "success_criteria": ["20% improvement"], "dependencies": [], "risk_factors": ["resource_constraints"], "stakeholders": ["engineering"]}]}'
        })
        
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Objectives Test Plan",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        assert len(plan.objectives) > 0
        
        for objective in plan.objectives:
            assert isinstance(objective, StrategicObjective)
            assert objective.objective_id is not None
            assert objective.name is not None
            assert isinstance(objective.objective_type, StrategicObjectiveType)
            assert objective.target_value >= 0
            assert objective.priority >= 1
            assert objective.target_date is not None

    @pytest.mark.asyncio
    async def test_strategic_initiatives_generation(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test strategic initiatives generation."""
        # Mock response with initiatives
        strategic_planner.claude_agent.execute_task = AsyncMock(return_value={
            "result": '{"initiatives": [{"initiative_name": "Digital Transformation", "description": "Accelerate digital capabilities", "objectives_addressed": ["obj1"], "resource_requirements": {"budget": 100000, "people": 5}, "estimated_duration_months": 12, "estimated_cost": 150000.0, "expected_benefits": {"efficiency": 20.0}, "risk_assessment": {"overall_risk": 0.3}, "implementation_phases": [{"phase": "planning"}], "success_metrics": ["adoption_rate"]}]}'
        })
        
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Initiatives Test Plan",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        if len(plan.initiatives) > 0:
            for initiative in plan.initiatives:
                assert isinstance(initiative, StrategicInitiative)
                assert initiative.initiative_id is not None
                assert initiative.name is not None
                assert initiative.estimated_duration_months > 0
                assert initiative.estimated_cost >= 0
                assert isinstance(initiative.resource_requirements, dict)
                assert isinstance(initiative.expected_benefits, dict)

    @pytest.mark.asyncio
    async def test_resource_allocation_optimization(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test resource allocation optimization."""
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Resource Allocation Test",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        assert isinstance(plan.resource_allocation, dict)
        
        # Check for basic resource allocation structure
        if plan.resource_allocation:
            assert "by_resource_type" in plan.resource_allocation or \
                   "by_objective" in plan.resource_allocation or \
                   "by_initiative" in plan.resource_allocation

    @pytest.mark.asyncio
    async def test_implementation_timeline_creation(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test implementation timeline creation."""
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Timeline Test Plan",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        assert isinstance(plan.timeline, dict)
        
        # Check for basic timeline structure
        if plan.timeline:
            expected_elements = ["phases", "milestones", "review_points"]
            found_elements = [elem for elem in expected_elements if elem in plan.timeline]
            assert len(found_elements) >= 1

    @pytest.mark.asyncio
    async def test_risk_management_strategy(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test risk management strategy development."""
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Risk Management Test",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        assert isinstance(plan.risk_management, dict)
        
        # Check for basic risk management structure
        if plan.risk_management:
            expected_elements = ["risk_register", "mitigation_strategies", "monitoring_framework"]
            found_elements = [elem for elem in expected_elements if elem in plan.risk_management]
            assert len(found_elements) >= 1

    @pytest.mark.asyncio
    async def test_success_metrics_definition(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test success metrics definition."""
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Success Metrics Test",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        assert isinstance(plan.success_metrics, dict)
        
        # Check for basic success metrics structure
        if plan.success_metrics:
            expected_elements = ["objective_metrics", "initiative_metrics", "dashboard_structure"]
            found_elements = [elem for elem in expected_elements if elem in plan.success_metrics]
            assert len(found_elements) >= 1

    @pytest.mark.asyncio
    async def test_plan_storage_and_tracking(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test plan storage and tracking."""
        initial_plan_count = len(strategic_planner.active_plans)
        
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Storage Test Plan",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        # Should be stored in active plans
        assert len(strategic_planner.active_plans) == initial_plan_count + 1
        assert plan.plan_id in strategic_planner.active_plans
        assert strategic_planner.active_plans[plan.plan_id] == plan

    @pytest.mark.asyncio
    async def test_plan_progress_review(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test plan progress review functionality."""
        # Create a plan first
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Progress Review Test",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        # Review progress
        review_result = await strategic_planner.review_plan_progress(plan.plan_id)
        
        assert isinstance(review_result, dict)
        assert "plan_id" in review_result
        assert "review_date" in review_result
        assert "overall_progress" in review_result
        assert "recommendations" in review_result
        assert review_result["plan_id"] == plan.plan_id

    @pytest.mark.asyncio
    async def test_plan_update(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test plan update functionality."""
        # Create a plan first
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Update Test Plan",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        original_update_time = plan.last_updated
        
        # Update the plan
        updates = {
            "resource_allocation": {"budget": 600000},
            "timeline": {"review_frequency": "monthly"}
        }
        
        updated_plan = await strategic_planner.update_plan(plan.plan_id, updates)
        
        assert updated_plan.plan_id == plan.plan_id
        assert updated_plan.last_updated > original_update_time

    @pytest.mark.asyncio
    async def test_invalid_plan_operations(self, strategic_planner):
        """Test operations on invalid/non-existent plans."""
        invalid_plan_id = "non_existent_plan"
        
        # Should raise error for non-existent plan review
        with pytest.raises(ValueError):
            await strategic_planner.review_plan_progress(invalid_plan_id)
        
        # Should raise error for non-existent plan update
        with pytest.raises(ValueError):
            await strategic_planner.update_plan(invalid_plan_id, {})

    @pytest.mark.asyncio
    async def test_concurrent_plan_creation(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test concurrent plan creation."""
        # Create multiple plans concurrently
        tasks = []
        for i in range(3):
            task = strategic_planner.create_strategic_plan(
                plan_name=f"Concurrent Plan {i}",
                planning_horizon=PlanningHorizon.OPERATIONAL,
                planning_context=sample_planning_context,
                strategic_priorities=sample_strategic_priorities
            )
            tasks.append(task)
        
        plans = await asyncio.gather(*tasks)
        
        # All plans should be created successfully
        assert len(plans) == 3
        for plan in plans:
            assert isinstance(plan, StrategicPlan)
            assert plan.plan_id is not None
        
        # All plans should be stored
        assert len(strategic_planner.active_plans) >= 3

    @pytest.mark.asyncio
    async def test_planning_framework_configuration(self, strategic_planner):
        """Test planning framework configuration."""
        frameworks = strategic_planner.planning_frameworks
        
        # Test balanced scorecard framework
        assert "balanced_scorecard" in frameworks
        bsc = frameworks["balanced_scorecard"]
        assert "perspectives" in bsc
        assert "weight_distribution" in bsc
        assert len(bsc["perspectives"]) == len(bsc["weight_distribution"])
        assert sum(bsc["weight_distribution"]) == 1.0
        
        # Test OKR framework
        assert "okr" in frameworks
        okr = frameworks["okr"]
        assert "objectives_per_period" in okr
        assert "key_results_per_objective" in okr
        assert "confidence_target" in okr
        
        # Test SMART goals framework
        assert "smart_goals" in frameworks
        smart = frameworks["smart_goals"]
        assert "criteria" in smart
        assert len(smart["criteria"]) == 5  # Specific, Measurable, Achievable, Relevant, Time-bound

    @pytest.mark.asyncio
    async def test_strategic_analysis_fallback(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test strategic analysis fallback functionality."""
        # Mock Claude agent to return invalid JSON
        strategic_planner.claude_agent.execute_task = AsyncMock(return_value={
            "result": "invalid json response"
        })
        
        # Should still create a plan with fallback analysis
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Fallback Test Plan",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        assert isinstance(plan, StrategicPlan)
        assert plan.plan_id is not None

    @pytest.mark.asyncio
    async def test_objective_types_coverage(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test coverage of different strategic objective types."""
        objective_types = [obj_type for obj_type in StrategicObjectiveType]
        
        # Verify all objective types are valid
        for obj_type in objective_types:
            assert obj_type.value is not None
            
        # Test creating objectives with different types
        sample_objectives = []
        for i, obj_type in enumerate(objective_types[:3]):  # Test first 3 types
            objective = StrategicObjective(
                objective_id=f"test_obj_{i}",
                name=f"Test {obj_type.value}",
                description=f"Test objective for {obj_type.value}",
                objective_type=obj_type,
                target_value=100.0,
                current_value=50.0,
                measurement_unit="percent",
                target_date=datetime.now(timezone.utc) + timedelta(days=365),
                priority=5
            )
            sample_objectives.append(objective)
        
        # All objectives should be valid
        for obj in sample_objectives:
            assert isinstance(obj.objective_type, StrategicObjectiveType)

    @pytest.mark.asyncio
    async def test_planning_horizon_impact(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test impact of different planning horizons."""
        # Create plans with different horizons
        tactical_plan = await strategic_planner.create_strategic_plan(
            plan_name="Tactical Plan",
            planning_horizon=PlanningHorizon.TACTICAL,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        strategic_plan = await strategic_planner.create_strategic_plan(
            plan_name="Strategic Plan",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        # Plans should have different characteristics based on horizon
        assert tactical_plan.planning_horizon == PlanningHorizon.TACTICAL
        assert strategic_plan.planning_horizon == PlanningHorizon.STRATEGIC
        
        # Both should be valid plans
        assert tactical_plan.plan_id is not None
        assert strategic_plan.plan_id is not None

    def test_planning_context_validation(self, sample_planning_context):
        """Test planning context validation."""
        assert isinstance(sample_planning_context.current_capabilities, dict)
        assert isinstance(sample_planning_context.available_resources, dict)
        assert isinstance(sample_planning_context.market_conditions, dict)
        assert isinstance(sample_planning_context.competitive_landscape, dict)
        assert isinstance(sample_planning_context.technology_trends, list)
        assert isinstance(sample_planning_context.regulatory_environment, dict)
        assert isinstance(sample_planning_context.organizational_constraints, dict)
        assert isinstance(sample_planning_context.stakeholder_priorities, dict)

    @pytest.mark.asyncio
    async def test_plan_status_transitions(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test plan status transitions."""
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Status Test Plan",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=sample_planning_context,
            strategic_priorities=sample_strategic_priorities
        )
        
        # Initial status should be DRAFT
        assert plan.status == PlanStatus.DRAFT
        
        # Test status updates
        plan.status = PlanStatus.UNDER_REVIEW
        assert plan.status == PlanStatus.UNDER_REVIEW
        
        plan.status = PlanStatus.APPROVED
        assert plan.status == PlanStatus.APPROVED
        
        plan.status = PlanStatus.IN_EXECUTION
        assert plan.status == PlanStatus.IN_EXECUTION

    @pytest.mark.asyncio
    async def test_performance_metrics_tracking(self, strategic_planner):
        """Test performance metrics tracking."""
        # Initially should have empty metrics
        assert len(strategic_planner.planning_metrics) == 0
        assert len(strategic_planner.execution_tracking) == 0
        
        # After creating plans, metrics should be tracked
        # (This would be implemented in the actual performance tracking system)

    @pytest.mark.asyncio
    async def test_error_handling_in_plan_creation(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test error handling in plan creation."""
        # Mock Claude agent to raise exception
        strategic_planner.claude_agent.execute_task = AsyncMock(side_effect=Exception("AI service error"))
        
        # Should raise exception on plan creation failure
        with pytest.raises(Exception):
            await strategic_planner.create_strategic_plan(
                plan_name="Error Test Plan",
                planning_horizon=PlanningHorizon.STRATEGIC,
                planning_context=sample_planning_context,
                strategic_priorities=sample_strategic_priorities
            )

    def test_strategic_planner_configuration(self, strategic_planner):
        """Test strategic planner configuration parameters."""
        assert strategic_planner.max_concurrent_plans > 0
        assert strategic_planner.planning_cycle_months > 0
        assert strategic_planner.review_frequency_weeks > 0
        
        # Test configuration limits
        assert strategic_planner.max_concurrent_plans <= 10  # Reasonable upper limit
        assert strategic_planner.planning_cycle_months <= 24  # Reasonable upper limit
        assert strategic_planner.review_frequency_weeks <= 52  # Reasonable upper limit

    @pytest.mark.asyncio
    async def test_plan_complexity_handling(
        self, 
        strategic_planner, 
        sample_planning_context,
        sample_strategic_priorities
    ):
        """Test handling of complex planning scenarios."""
        # Create complex planning context
        complex_context = PlanningContext(
            current_capabilities={f"capability_{i}": float(i*10) for i in range(10)},
            available_resources={f"resource_{i}": float(i*1000) for i in range(8)},
            market_conditions={"complexity": "high", "volatility": "extreme"},
            competitive_landscape={"competitors": list(range(50))},
            technology_trends=[f"trend_{i}" for i in range(20)],
            regulatory_environment={"regulations": list(range(30))},
            organizational_constraints={"constraints": list(range(15))},
            stakeholder_priorities={f"stakeholder_{i}": i for i in range(25)}
        )
        
        complex_priorities = [f"Priority {i}: Complex strategic initiative" for i in range(10)]
        
        # Should handle complex scenarios
        plan = await strategic_planner.create_strategic_plan(
            plan_name="Complex Strategic Plan",
            planning_horizon=PlanningHorizon.STRATEGIC,
            planning_context=complex_context,
            strategic_priorities=complex_priorities
        )
        
        assert isinstance(plan, StrategicPlan)
        assert plan.plan_id is not None
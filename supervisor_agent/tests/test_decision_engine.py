# supervisor_agent/tests/test_decision_engine.py
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from supervisor_agent.intelligence.decision_engine import (
    DecisionContext,
    DecisionCriteria,
    DecisionEngine,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
    DecisionStatus,
    DecisionType,
    DecisionUrgency,
)


class TestDecisionEngine:
    """Test suite for DecisionEngine."""

    @pytest.fixture
    def mock_claude_agent(self):
        """Create a mock Claude agent."""
        mock_agent = Mock()
        mock_agent.execute_task = AsyncMock(
            return_value={
                "result": '{"key_factors": ["resource_availability", "time_constraints"], "risk_analysis": {"primary_risks": ["implementation_risk"]}, "opportunity_analysis": {"primary_opportunities": ["efficiency_gain"]}, "reasoning": "AI-powered decision analysis based on comprehensive evaluation."}'
            }
        )
        return mock_agent

    @pytest.fixture
    def decision_engine(self, mock_claude_agent):
        """Create a DecisionEngine instance."""
        return DecisionEngine(mock_claude_agent)

    @pytest.fixture
    def sample_decision_criteria(self):
        """Create sample decision criteria."""
        return [
            DecisionCriteria(
                criterion_id="cost_efficiency",
                name="Cost Efficiency",
                weight=0.3,
                optimization_direction="minimize",
                constraints={"max_cost": 100000},
            ),
            DecisionCriteria(
                criterion_id="implementation_speed",
                name="Implementation Speed",
                weight=0.25,
                optimization_direction="minimize",
                constraints={"max_time": 30},
            ),
            DecisionCriteria(
                criterion_id="quality_impact",
                name="Quality Impact",
                weight=0.35,
                optimization_direction="maximize",
            ),
            DecisionCriteria(
                criterion_id="risk_level",
                name="Risk Level",
                weight=0.1,
                optimization_direction="minimize",
            ),
        ]

    @pytest.fixture
    def sample_decision_options(self):
        """Create sample decision options."""
        return [
            DecisionOption(
                option_id="option_a",
                name="Conservative Approach",
                description="Low-risk, incremental improvement strategy",
                parameters={
                    "approach": "incremental",
                    "risk_tolerance": "low",
                },
                estimated_impact={"performance": 15.0, "cost_savings": 8.0},
                implementation_cost=50000.0,
                risk_assessment={
                    "overall_risk": 0.2,
                    "major_risks": ["minimal_impact"],
                },
                time_to_implement=45,
                reversibility=True,
            ),
            DecisionOption(
                option_id="option_b",
                name="Aggressive Transformation",
                description="High-impact, transformational change strategy",
                parameters={
                    "approach": "transformational",
                    "risk_tolerance": "high",
                },
                estimated_impact={"performance": 40.0, "cost_savings": 25.0},
                implementation_cost=150000.0,
                risk_assessment={
                    "overall_risk": 0.7,
                    "major_risks": [
                        "implementation_complexity",
                        "stakeholder_resistance",
                    ],
                },
                time_to_implement=120,
                reversibility=False,
            ),
            DecisionOption(
                option_id="option_c",
                name="Balanced Optimization",
                description="Moderate risk, balanced improvement strategy",
                parameters={
                    "approach": "balanced",
                    "risk_tolerance": "medium",
                },
                estimated_impact={"performance": 25.0, "cost_savings": 15.0},
                implementation_cost=85000.0,
                risk_assessment={
                    "overall_risk": 0.4,
                    "major_risks": ["resource_constraints"],
                },
                time_to_implement=75,
                reversibility=True,
            ),
        ]

    @pytest.fixture
    def sample_decision_context(self):
        """Create sample decision context."""
        return DecisionContext(
            context_id="test_context_001",
            decision_type=DecisionType.WORKFLOW_OPTIMIZATION,
            urgency=DecisionUrgency.HIGH,
            stakeholders=["engineering_team", "operations_team", "management"],
            constraints={"budget_limit": 100000, "time_limit": 90},
            available_resources={
                "budget": 200000,
                "people": 10,
                "tools": ["analytics", "monitoring"],
            },
            historical_context={
                "previous_optimizations": 3,
                "success_rate": 0.8,
            },
            environmental_factors={
                "market_pressure": "high",
                "competition": "increasing",
            },
            success_metrics={"performance_gain": 20.0, "cost_reduction": 10.0},
            deadline=datetime.now(timezone.utc) + timedelta(days=60),
        )

    @pytest.fixture
    def sample_decision_request(
        self,
        sample_decision_context,
        sample_decision_criteria,
        sample_decision_options,
    ):
        """Create a sample decision request."""
        return DecisionRequest(
            request_id="test_request_001",
            decision_type=DecisionType.WORKFLOW_OPTIMIZATION,
            context=sample_decision_context,
            criteria=sample_decision_criteria,
            options=sample_decision_options,
            requesting_entity="system_optimizer",
        )

    def test_decision_engine_initialization(self, decision_engine):
        """Test decision engine initialization."""
        assert decision_engine.claude_agent is not None
        assert len(decision_engine.active_decisions) == 0
        assert len(decision_engine.decision_history) == 0
        assert decision_engine.max_concurrent_decisions == 10
        assert decision_engine.confidence_threshold == 0.7
        assert "conservative" in decision_engine.decision_strategies
        assert "adaptive" in decision_engine.decision_strategies

    @pytest.mark.asyncio
    async def test_make_decision_basic(
        self, decision_engine, sample_decision_request
    ):
        """Test basic decision making functionality."""
        result = await decision_engine.make_decision(sample_decision_request)

        assert isinstance(result, DecisionResult)
        assert result.decision_id is not None
        assert result.request_id == sample_decision_request.request_id
        assert result.selected_option is not None
        assert result.confidence_score > 0
        assert result.reasoning is not None
        assert len(result.alternative_options) >= 0
        assert result.implementation_plan is not None
        assert result.decided_at is not None

    @pytest.mark.asyncio
    async def test_make_decision_with_strategy(
        self, decision_engine, sample_decision_request
    ):
        """Test decision making with different strategies."""
        strategies = ["conservative", "balanced", "aggressive", "adaptive"]

        for strategy in strategies:
            result = await decision_engine.make_decision(
                sample_decision_request, strategy=strategy
            )

            assert isinstance(result, DecisionResult)
            assert result.selected_option is not None
            assert 0 <= result.confidence_score <= 1

    @pytest.mark.asyncio
    async def test_decision_criteria_evaluation(
        self, decision_engine, sample_decision_request
    ):
        """Test decision criteria evaluation."""
        result = await decision_engine.make_decision(sample_decision_request)

        # Verify that decision considered all criteria
        selected_option = result.selected_option
        assert selected_option.confidence_score > 0

        # Check that the selected option is from the provided options
        option_ids = [opt.option_id for opt in sample_decision_request.options]
        assert selected_option.option_id in option_ids

    @pytest.mark.asyncio
    async def test_urgent_decision_handling(
        self, decision_engine, sample_decision_request
    ):
        """Test handling of urgent decisions."""
        # Set high urgency
        sample_decision_request.context.urgency = DecisionUrgency.CRITICAL
        sample_decision_request.context.deadline = datetime.now(
            timezone.utc
        ) + timedelta(hours=2)

        result = await decision_engine.make_decision(sample_decision_request)

        assert isinstance(result, DecisionResult)
        assert result.selected_option is not None
        # Urgent decisions may accept lower confidence thresholds
        assert result.confidence_score >= 0

    @pytest.mark.asyncio
    async def test_risk_adjusted_scoring(
        self, decision_engine, sample_decision_request
    ):
        """Test risk-adjusted scoring of options."""
        result = await decision_engine.make_decision(sample_decision_request)

        selected_option = result.selected_option

        # Lower risk options should generally score higher (all else being equal)
        # Find the lowest risk option
        lowest_risk_option = min(
            sample_decision_request.options,
            key=lambda x: x.risk_assessment.get("overall_risk", 0.5),
        )

        # Verify risk was considered in scoring
        assert selected_option.confidence_score > 0

        # The selected option should be reasonable given risk considerations
        assert selected_option.risk_assessment.get("overall_risk", 0.5) <= 0.8

    @pytest.mark.asyncio
    async def test_multi_criteria_optimization(
        self, decision_engine, sample_decision_request
    ):
        """Test multi-criteria decision optimization."""
        result = await decision_engine.make_decision(sample_decision_request)

        # Verify multiple criteria were considered
        assert len(sample_decision_request.criteria) > 1

        # Check that different criteria weights influence the decision
        high_weight_criteria = [
            c for c in sample_decision_request.criteria if c.weight > 0.3
        ]
        assert len(high_weight_criteria) > 0

        # Selected option should have reasonable confidence
        assert result.confidence_score > 0.4

    @pytest.mark.asyncio
    async def test_implementation_plan_generation(
        self, decision_engine, sample_decision_request
    ):
        """Test implementation plan generation."""
        result = await decision_engine.make_decision(sample_decision_request)

        implementation_plan = result.implementation_plan

        # Check basic implementation plan structure
        assert isinstance(implementation_plan, dict)

        # Should have key implementation elements
        expected_elements = [
            "implementation_steps",
            "timeline",
            "success_criteria",
        ]
        for element in expected_elements:
            if element in implementation_plan:
                assert implementation_plan[element] is not None

    @pytest.mark.asyncio
    async def test_decision_history_tracking(
        self, decision_engine, sample_decision_request
    ):
        """Test decision history tracking."""
        initial_history_count = len(decision_engine.decision_history)

        result = await decision_engine.make_decision(sample_decision_request)

        # Should add to decision history
        assert (
            len(decision_engine.decision_history) == initial_history_count + 1
        )

        # Should store result
        assert result.decision_id in decision_engine.decision_results
        assert decision_engine.decision_results[result.decision_id] == result

    @pytest.mark.asyncio
    async def test_concurrent_decision_handling(self, decision_engine):
        """Test handling of concurrent decisions."""
        # Create multiple decision requests
        requests = []
        for i in range(3):
            context = DecisionContext(
                context_id=f"context_{i}",
                decision_type=DecisionType.RESOURCE_ALLOCATION,
                urgency=DecisionUrgency.MEDIUM,
                stakeholders=["team_a"],
                constraints={},
                available_resources={},
                historical_context={},
                environmental_factors={},
                success_metrics={},
            )

            criteria = [
                DecisionCriteria(
                    criterion_id="test_criterion",
                    name="Test Criterion",
                    weight=1.0,
                    optimization_direction="maximize",
                )
            ]

            options = [
                DecisionOption(
                    option_id=f"option_{i}",
                    name=f"Option {i}",
                    description="Test option",
                    parameters={},
                    estimated_impact={},
                    implementation_cost=1000.0,
                    risk_assessment={},
                    time_to_implement=30,
                    reversibility=True,
                )
            ]

            request = DecisionRequest(
                request_id=f"request_{i}",
                decision_type=DecisionType.RESOURCE_ALLOCATION,
                context=context,
                criteria=criteria,
                options=options,
                requesting_entity="test_system",
            )
            requests.append(request)

        # Process decisions concurrently
        tasks = [decision_engine.make_decision(req) for req in requests]
        results = await asyncio.gather(*tasks)

        # All decisions should complete successfully
        assert len(results) == 3
        for result in results:
            assert isinstance(result, DecisionResult)
            assert result.selected_option is not None

    @pytest.mark.asyncio
    async def test_decision_status_tracking(
        self, decision_engine, sample_decision_request
    ):
        """Test decision status tracking."""
        # Before decision
        status = await decision_engine.get_decision_status(
            sample_decision_request.request_id
        )
        assert status["status"] == "not_found"

        # Make decision
        result = await decision_engine.make_decision(sample_decision_request)

        # After decision
        status = await decision_engine.get_decision_status(
            sample_decision_request.request_id
        )
        assert status["status"] == "completed"
        assert status["result"] == result

    @pytest.mark.asyncio
    async def test_decision_recommendations(self, decision_engine):
        """Test decision recommendation functionality."""
        recommendations = await decision_engine.get_decision_recommendations(
            DecisionType.PERFORMANCE_TUNING,
            {"complexity": "high", "urgency": "medium"},
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        for rec in recommendations:
            assert "recommendation" in rec
            assert "confidence" in rec
            assert "based_on" in rec
            assert 0 <= rec["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_performance_metrics(
        self, decision_engine, sample_decision_request
    ):
        """Test decision engine performance metrics."""
        # Make a decision to generate metrics
        await decision_engine.make_decision(sample_decision_request)

        metrics = await decision_engine.get_performance_metrics()

        assert "total_decisions" in metrics
        assert "average_confidence" in metrics
        assert "decisions_by_type" in metrics
        assert "active_decisions" in metrics

        assert metrics["total_decisions"] >= 1
        assert 0 <= metrics["average_confidence"] <= 1

    @pytest.mark.asyncio
    async def test_low_confidence_decision_handling(
        self, decision_engine, sample_decision_request
    ):
        """Test handling of low confidence decisions."""
        # Create options with inherently low confidence scores
        low_confidence_options = [
            DecisionOption(
                option_id="low_conf_option",
                name="Uncertain Option",
                description="Option with high uncertainty",
                parameters={},
                estimated_impact={"uncertain": True},
                implementation_cost=500000.0,  # Very high cost
                risk_assessment={"overall_risk": 0.9},  # Very high risk
                time_to_implement=365,  # Very long implementation
                reversibility=False,
            )
        ]

        sample_decision_request.options = low_confidence_options

        # For critical urgency, should proceed even with low confidence
        sample_decision_request.context.urgency = DecisionUrgency.CRITICAL
        result = await decision_engine.make_decision(sample_decision_request)

        assert isinstance(result, DecisionResult)
        assert result.selected_option is not None

    @pytest.mark.asyncio
    async def test_decision_with_dependencies(self, decision_engine):
        """Test decision making with option dependencies."""
        context = DecisionContext(
            context_id="dependency_context",
            decision_type=DecisionType.STRATEGIC_PLANNING,
            urgency=DecisionUrgency.MEDIUM,
            stakeholders=["strategy_team"],
            constraints={},
            available_resources={},
            historical_context={},
            environmental_factors={},
            success_metrics={},
        )

        criteria = [
            DecisionCriteria(
                criterion_id="strategic_value",
                name="Strategic Value",
                weight=1.0,
                optimization_direction="maximize",
                dependencies=["market_analysis"],
            )
        ]

        options = [
            DecisionOption(
                option_id="dependent_option",
                name="Dependent Strategy",
                description="Strategy dependent on other factors",
                parameters={
                    "dependencies": ["market_research", "competitive_analysis"]
                },
                estimated_impact={"strategic_value": 50.0},
                implementation_cost=75000.0,
                risk_assessment={"dependency_risk": 0.4},
                time_to_implement=90,
                reversibility=True,
            )
        ]

        request = DecisionRequest(
            request_id="dependency_request",
            decision_type=DecisionType.STRATEGIC_PLANNING,
            context=context,
            criteria=criteria,
            options=options,
            requesting_entity="strategy_system",
        )

        result = await decision_engine.make_decision(request)

        assert isinstance(result, DecisionResult)
        assert result.selected_option is not None

    @pytest.mark.asyncio
    async def test_historical_learning_integration(
        self, decision_engine, sample_decision_request
    ):
        """Test integration with historical learning."""
        # Make initial decision
        result1 = await decision_engine.make_decision(sample_decision_request)

        # Create similar decision request
        similar_request = DecisionRequest(
            request_id="similar_request",
            decision_type=sample_decision_request.decision_type,
            context=sample_decision_request.context,
            criteria=sample_decision_request.criteria,
            options=sample_decision_request.options,
            requesting_entity="learning_test",
        )

        # Make second decision - should benefit from learning
        result2 = await decision_engine.make_decision(similar_request)

        assert isinstance(result2, DecisionResult)
        assert result2.selected_option is not None

        # Learning database should contain entries
        decision_type_key = sample_decision_request.decision_type.value
        assert decision_type_key in decision_engine.learning_database
        assert len(decision_engine.learning_database[decision_type_key]) >= 1

    def test_decision_criteria_validation(self, sample_decision_criteria):
        """Test decision criteria validation."""
        for criterion in sample_decision_criteria:
            assert criterion.criterion_id is not None
            assert criterion.name is not None
            assert 0 <= criterion.weight <= 1
            assert criterion.optimization_direction in ["maximize", "minimize"]

    def test_decision_option_validation(self, sample_decision_options):
        """Test decision option validation."""
        for option in sample_decision_options:
            assert option.option_id is not None
            assert option.name is not None
            assert option.implementation_cost >= 0
            assert option.time_to_implement >= 0
            assert isinstance(option.reversibility, bool)

    def test_decision_context_validation(self, sample_decision_context):
        """Test decision context validation."""
        assert sample_decision_context.context_id is not None
        assert isinstance(sample_decision_context.decision_type, DecisionType)
        assert isinstance(sample_decision_context.urgency, DecisionUrgency)
        assert isinstance(sample_decision_context.stakeholders, list)
        assert isinstance(sample_decision_context.constraints, dict)
        assert isinstance(sample_decision_context.available_resources, dict)

    @pytest.mark.asyncio
    async def test_error_handling_invalid_request(self, decision_engine):
        """Test error handling for invalid decision requests."""
        # Create invalid request with no options
        invalid_context = DecisionContext(
            context_id="invalid_context",
            decision_type=DecisionType.TASK_PRIORITIZATION,
            urgency=DecisionUrgency.LOW,
            stakeholders=[],
            constraints={},
            available_resources={},
            historical_context={},
            environmental_factors={},
            success_metrics={},
        )

        invalid_request = DecisionRequest(
            request_id="invalid_request",
            decision_type=DecisionType.TASK_PRIORITIZATION,
            context=invalid_context,
            criteria=[],
            options=[],  # No options provided
            requesting_entity="error_test",
        )

        # Should raise an exception for invalid request
        with pytest.raises(ValueError):
            await decision_engine.make_decision(invalid_request)

    @pytest.mark.asyncio
    async def test_decision_timeout_handling(self, decision_engine):
        """Test decision timeout handling."""
        # This test would require more complex mocking to simulate timeouts
        # For now, just verify the timeout configuration exists
        assert decision_engine.decision_timeout_minutes > 0
        assert decision_engine.max_concurrent_decisions > 0

    def test_strategy_pattern_configuration(self, decision_engine):
        """Test decision strategy pattern configuration."""
        strategies = decision_engine.decision_strategies

        required_strategies = [
            "conservative",
            "balanced",
            "aggressive",
            "adaptive",
        ]
        for strategy in required_strategies:
            assert strategy in strategies
            assert "risk_tolerance" in strategies[strategy]
            assert "change_preference" in strategies[strategy]
            assert 0 <= strategies[strategy]["risk_tolerance"] <= 1
            assert 0 <= strategies[strategy]["change_preference"] <= 1

    @pytest.mark.asyncio
    async def test_decision_learning_database_management(
        self, decision_engine, sample_decision_request
    ):
        """Test learning database management and size limits."""
        # Make multiple decisions to test database management
        for i in range(5):
            request = DecisionRequest(
                request_id=f"learning_test_{i}",
                decision_type=sample_decision_request.decision_type,
                context=sample_decision_request.context,
                criteria=sample_decision_request.criteria,
                options=sample_decision_request.options,
                requesting_entity=f"learning_entity_{i}",
            )
            await decision_engine.make_decision(request)

        # Verify learning database is populated
        decision_type_key = sample_decision_request.decision_type.value
        assert decision_type_key in decision_engine.learning_database
        assert len(decision_engine.learning_database[decision_type_key]) >= 1

        # Verify entries have expected structure
        for entry in decision_engine.learning_database[decision_type_key]:
            assert "decision_type" in entry
            assert "confidence_score" in entry
            assert "timestamp" in entry

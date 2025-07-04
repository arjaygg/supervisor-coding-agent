# supervisor_agent/tests/test_coordination_systems.py
import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock

from supervisor_agent.coordination.swarm_coordinator import (
    IntelligentSwarmCoordinator,
    SwarmAgent,
    AgentConfiguration,
    AgentState,
    AgentSpecialization,
    AgentCapability,
    CoordinationEvent,
    CoordinationEventType,
    CoordinationResponse,
    DynamicAgentPool,
    CommunicationNetwork,
    SwarmExecution
)
from supervisor_agent.coordination.agent_collaboration_engine import (
    AgentCollaborationEngine,
    CollaborationType,
    CollaborationStatus,
    ReviewOutcome,
    CollaborationRequest,
    CollaborationSession,
    PeerReviewResult,
    KnowledgeTransfer,
    CollaborationNetwork
)


class TestSwarmCoordinator:
    """Test suite for IntelligentSwarmCoordinator."""

    @pytest.fixture
    def mock_claude_agent(self):
        """Create a mock Claude agent."""
        mock_agent = Mock()
        mock_agent.execute_task = AsyncMock(return_value={
            "result": '{"response_type": "test", "recommended_actions": ["test_action"], "resource_allocations": {}, "success_probability": 0.8, "estimated_completion_time": 1.0}'
        })
        return mock_agent

    @pytest.fixture
    def agent_pool(self):
        """Create a DynamicAgentPool instance."""
        return DynamicAgentPool()

    @pytest.fixture
    def coordinator(self, mock_claude_agent, agent_pool):
        """Create an IntelligentSwarmCoordinator instance."""
        return IntelligentSwarmCoordinator(mock_claude_agent, agent_pool)

    @pytest.fixture
    def sample_agent_config(self):
        """Create a sample agent configuration."""
        capability = AgentCapability(
            capability_name="test_capability",
            proficiency_level=0.8,
            tools_required=["test_tool"],
            estimated_throughput=2.0,
            quality_score=0.9
        )
        
        return AgentConfiguration(
            agent_id="test_agent_001",
            specialization=AgentSpecialization.SOLUTION_ARCHITECT,
            capabilities=[capability],
            resource_limits={"memory_gb": 8, "cpu_cores": 4},
            communication_preferences={"protocol": "async"},
            collaboration_rules={"max_handoffs": 5},
            performance_targets={"tasks_per_hour": 3},
            tools_access=["test_tool"]
        )

    @pytest.fixture
    def sample_agents(self, agent_pool, sample_agent_config):
        """Create sample agents for testing."""
        agents = {}
        specializations = [
            AgentSpecialization.REQUIREMENTS_ANALYST,
            AgentSpecialization.SOLUTION_ARCHITECT,
            AgentSpecialization.QUALITY_ASSURANCE
        ]
        
        for i, spec in enumerate(specializations):
            config = AgentConfiguration(
                agent_id=f"agent_{spec.value}_{i}",
                specialization=spec,
                capabilities=[AgentCapability(
                    capability_name=f"{spec.value}_capability",
                    proficiency_level=0.8,
                    tools_required=["basic_tool"],
                    estimated_throughput=2.0,
                    quality_score=0.85
                )],
                resource_limits={"memory_gb": 4, "cpu_cores": 2},
                communication_preferences={"protocol": "async"},
                collaboration_rules={"max_handoffs": 3},
                performance_targets={"tasks_per_hour": 2},
                tools_access=["basic_tool"]
            )
            
            agent = SwarmAgent(
                agent_id=config.agent_id,
                configuration=config,
                current_state=AgentState.IDLE
            )
            agents[agent.agent_id] = agent
        
        return agents

    def test_coordinator_initialization(self, coordinator):
        """Test coordinator initialization."""
        assert coordinator.claude_agent is not None
        assert coordinator.agent_pool is not None
        assert coordinator.conflict_resolver is not None
        assert coordinator.performance_tracker is not None
        assert len(coordinator.active_executions) == 0

    @pytest.mark.asyncio
    async def test_agent_creation(self, agent_pool, sample_agent_config):
        """Test agent creation in the pool."""
        agent = await agent_pool.create_agent(sample_agent_config)
        
        assert agent.agent_id == sample_agent_config.agent_id
        assert agent.configuration.specialization == AgentSpecialization.SOLUTION_ARCHITECT
        assert agent.current_state == AgentState.IDLE
        assert len(agent.configuration.capabilities) == 1

    @pytest.mark.asyncio
    async def test_best_agent_selection(self, agent_pool, sample_agents):
        """Test best agent selection for tasks."""
        # Add agents to pool
        for agent in sample_agents.values():
            agent_pool.available_agents[agent.agent_id] = agent
        
        # Test task requirements
        task_requirements = {
            "required_capabilities": ["solution_architect_capability"],
            "priority": "high"
        }
        
        best_agent = await agent_pool.get_best_agent_for_task(task_requirements)
        
        assert best_agent is not None
        assert "solution_architect" in best_agent.agent_id
        assert best_agent.can_accept_task(task_requirements)

    def test_agent_capability_matching(self, sample_agents):
        """Test agent capability matching."""
        architect_agent = next(a for a in sample_agents.values() if "solution_architect" in a.agent_id)
        
        # Test capability score retrieval
        score = architect_agent.get_capability_score("solution_architect_capability")
        assert score == 0.8
        
        # Test non-existent capability
        score = architect_agent.get_capability_score("non_existent_capability")
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_coordination_event_handling(self, coordinator):
        """Test coordination event handling."""
        event = CoordinationEvent(
            event_id="test_event_001",
            event_type=CoordinationEventType.TASK_HANDOFF,
            from_agent="agent_1",
            to_agent="agent_2",
            from_agent_context={"workload": 3},
            to_agent_context={"workload": 1},
            task_context={"task_id": "test_task"},
            intermediate_results={"progress": 0.5}
        )
        
        response = await coordinator.handle_inter_agent_coordination(event)
        
        assert isinstance(response, CoordinationResponse)
        assert response.event_id == event.event_id
        assert response.response_type is not None

    @pytest.mark.asyncio
    async def test_resource_allocation_optimization(self, coordinator):
        """Test resource allocation optimization."""
        event = CoordinationEvent(
            event_id="resource_test_001",
            event_type=CoordinationEventType.RESOURCE_CONTENTION,
            from_agent="agent_1",
            to_agent="agent_2",
            from_agent_context={"resource_need": "cpu"},
            to_agent_context={"resource_usage": "high"},
            task_context={"priority": "high"},
            intermediate_results={}
        )
        
        response = await coordinator._optimize_resource_allocation(event)
        
        assert response.event_id == event.event_id
        assert "resource" in response.response_type or response.response_type == "test"
        assert len(response.recommended_actions) > 0

    @pytest.mark.asyncio
    async def test_quality_escalation_handling(self, coordinator):
        """Test quality escalation handling."""
        event = CoordinationEvent(
            event_id="quality_test_001",
            event_type=CoordinationEventType.QUALITY_CONCERN,
            from_agent="qa_agent",
            to_agent="dev_agent",
            from_agent_context={"quality_issue": "code_quality"},
            to_agent_context={"code_submitted": True},
            task_context={"review_required": True},
            intermediate_results={"quality_score": 0.6}
        )
        
        response = await coordinator._handle_quality_escalation(event)
        
        assert response.event_id == event.event_id
        assert response.success_probability > 0

    @pytest.mark.asyncio
    async def test_performance_issue_handling(self, coordinator):
        """Test performance issue handling."""
        event = CoordinationEvent(
            event_id="perf_test_001",
            event_type=CoordinationEventType.PERFORMANCE_ISSUE,
            from_agent="monitor_agent",
            to_agent=None,
            from_agent_context={"performance_degradation": "high_latency"},
            to_agent_context=None,
            task_context={"threshold_exceeded": True},
            intermediate_results={"response_time": 5000}
        )
        
        response = await coordinator._handle_performance_issue(event)
        
        assert response.event_id == event.event_id
        assert response.estimated_completion_time > 0

    def test_communication_network(self, sample_agents):
        """Test communication network functionality."""
        comm_network = CommunicationNetwork(sample_agents)
        
        # Test message queue setup
        assert len(comm_network.message_queues) == len(sample_agents)
        
        # Test message sending
        agent_ids = list(sample_agents.keys())
        from_agent = agent_ids[0]
        to_agent = agent_ids[1]
        
        asyncio.run(comm_network.send_message(
            from_agent, to_agent, {"type": "test", "content": "hello"}
        ))
        
        # Test message retrieval
        messages = asyncio.run(comm_network.get_messages(to_agent))
        assert len(messages) == 1
        assert messages[0]["from"] == from_agent

    @pytest.mark.asyncio
    async def test_execution_metrics_calculation(self, coordinator, sample_agents):
        """Test execution metrics calculation."""
        # Create mock execution
        mock_execution = Mock()
        mock_execution.execution_id = "test_execution"
        mock_execution.agents = sample_agents
        mock_execution.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        
        # Set different agent states
        agent_list = list(sample_agents.values())
        agent_list[0].current_state = AgentState.WORKING
        agent_list[0].current_workload = 2
        agent_list[1].current_state = AgentState.IDLE
        agent_list[1].current_workload = 0
        agent_list[2].current_state = AgentState.BLOCKED
        agent_list[2].current_workload = 1
        
        metrics = await coordinator._calculate_execution_metrics(mock_execution)
        
        assert metrics["total_agents"] == 3
        assert metrics["active_agents"] == 1
        assert metrics["idle_agents"] == 1
        assert metrics["blocked_agents"] == 1
        assert metrics["average_workload"] == 1.0
        assert "efficiency_score" in metrics
        assert "coordination_score" in metrics

    def test_workload_variance_calculation(self, coordinator, sample_agents):
        """Test workload variance calculation."""
        # Set different workloads
        agent_list = list(sample_agents.values())
        agent_list[0].current_workload = 3
        agent_list[1].current_workload = 1
        agent_list[2].current_workload = 2
        
        mock_execution = Mock()
        mock_execution.agents = sample_agents
        
        variance = coordinator._calculate_workload_variance(mock_execution)
        
        # Expected variance: mean = 2, variance = ((3-2)² + (1-2)² + (2-2)²) / 3 = 2/3
        expected_variance = 2.0 / 3.0
        assert abs(variance - expected_variance) < 0.1

    @pytest.mark.asyncio
    async def test_execution_completion_check(self, coordinator, sample_agents):
        """Test execution completion checking."""
        # Create mock execution
        mock_execution = Mock()
        mock_execution.execution_id = "test_completion"
        mock_execution.agents = sample_agents
        mock_execution.started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        mock_execution.workflow_def = Mock()
        
        # Test with all agents idle (should be complete)
        for agent in sample_agents.values():
            agent.current_state = AgentState.IDLE
        
        is_complete = coordinator._is_execution_complete(mock_execution)
        assert is_complete is True
        
        # Test with working agents (should not be complete)
        list(sample_agents.values())[0].current_state = AgentState.WORKING
        
        is_complete = coordinator._is_execution_complete(mock_execution)
        assert is_complete is False


class TestAgentCollaborationEngine:
    """Test suite for AgentCollaborationEngine."""

    @pytest.fixture
    def mock_claude_agent(self):
        """Create a mock Claude agent."""
        mock_agent = Mock()
        mock_agent.execute_task = AsyncMock(return_value={
            "result": '{"objectives": ["test_objective"], "roles": {"agent1": "reviewer"}, "workflow": ["step1", "step2"], "communication_plan": {"method": "direct"}}'
        })
        return mock_agent

    @pytest.fixture
    def collaboration_engine(self, mock_claude_agent):
        """Create an AgentCollaborationEngine instance."""
        return AgentCollaborationEngine(mock_claude_agent)

    @pytest.fixture
    def sample_collaboration_request(self):
        """Create a sample collaboration request."""
        return CollaborationRequest(
            request_id="test_request_001",
            requesting_agent="agent_1",
            target_agents=["agent_2", "agent_3"],
            collaboration_type=CollaborationType.PEER_REVIEW,
            priority=7,
            description="Code review for critical feature",
            context={
                "artifact": "feature_implementation.py",
                "required_skills": ["python", "code_review"],
                "deadline": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            }
        )

    def test_collaboration_engine_initialization(self, collaboration_engine):
        """Test collaboration engine initialization."""
        assert collaboration_engine.claude_agent is not None
        assert collaboration_engine.collaboration_network is not None
        assert len(collaboration_engine.active_sessions) == 0
        assert len(collaboration_engine.pending_requests) == 0

    def test_collaboration_network_initialization(self):
        """Test collaboration network initialization."""
        network = CollaborationNetwork()
        
        assert len(network.collaboration_history) == 0
        assert len(network.agent_relationships) == 0
        assert len(network.collaboration_patterns) == 0
        assert len(network.skill_registry) == 0

    @pytest.mark.asyncio
    async def test_collaboration_request_creation(self, collaboration_engine):
        """Test collaboration request creation."""
        request_id = await collaboration_engine.request_collaboration(
            requesting_agent="agent_1",
            collaboration_type=CollaborationType.PEER_REVIEW,
            context={
                "artifact": "test_code.py",
                "description": "Review test implementation"
            },
            target_agents=["agent_2"],
            priority=8
        )
        
        assert request_id is not None
        assert len(collaboration_engine.active_sessions) > 0

    @pytest.mark.asyncio
    async def test_peer_review_initiation(self, collaboration_engine, sample_collaboration_request):
        """Test peer review session initiation."""
        # Create session
        session = CollaborationSession(
            session_id="test_session_001",
            collaboration_type=CollaborationType.PEER_REVIEW,
            participants=["agent_1", "agent_2", "agent_3"],
            initiator="agent_1",
            status=CollaborationStatus.INITIATED,
            context=sample_collaboration_request.context
        )
        
        collaboration_engine.active_sessions[session.session_id] = session
        
        # Test peer review initiation
        plan = {"quality_gates": ["correctness", "performance", "maintainability"]}
        await collaboration_engine._initiate_peer_review(session, plan)
        
        assert session.status == CollaborationStatus.IN_PROGRESS
        assert "review_tasks" in session.shared_artifacts
        assert len(session.shared_artifacts["review_tasks"]) == 2  # agent_2 and agent_3

    @pytest.mark.asyncio
    async def test_peer_review_submission(self, collaboration_engine):
        """Test peer review submission."""
        # Create session with peer review
        session = CollaborationSession(
            session_id="review_session_001",
            collaboration_type=CollaborationType.PEER_REVIEW,
            participants=["initiator", "reviewer_1", "reviewer_2"],
            initiator="initiator",
            status=CollaborationStatus.IN_PROGRESS,
            context={"artifact": "test_code.py"}
        )
        
        collaboration_engine.active_sessions[session.session_id] = session
        
        # Submit first review
        review_id_1 = await collaboration_engine.submit_peer_review(
            reviewer_agent="reviewer_1",
            session_id=session.session_id,
            review_feedback="Good implementation, minor improvements needed",
            quality_score=85.0,
            outcome=ReviewOutcome.NEEDS_REVISION,
            suggestions=["Add error handling", "Improve documentation"]
        )
        
        assert review_id_1 is not None
        assert review_id_1 in collaboration_engine.peer_reviews
        assert len(session.review_feedback) == 1
        
        # Submit second review to complete the session
        review_id_2 = await collaboration_engine.submit_peer_review(
            reviewer_agent="reviewer_2",
            session_id=session.session_id,
            review_feedback="Excellent work, ready for deployment",
            quality_score=95.0,
            outcome=ReviewOutcome.APPROVED,
            suggestions=["Consider adding unit tests"]
        )
        
        assert review_id_2 is not None
        assert len(session.review_feedback) == 2
        assert session.status == CollaborationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_knowledge_transfer_initiation(self, collaboration_engine):
        """Test knowledge transfer session initiation."""
        session = CollaborationSession(
            session_id="transfer_session_001",
            collaboration_type=CollaborationType.KNOWLEDGE_TRANSFER,
            participants=["expert_agent", "learner_agent_1", "learner_agent_2"],
            initiator="expert_agent",
            status=CollaborationStatus.INITIATED,
            context={
                "knowledge": {"topic": "machine_learning", "content": "ML best practices"},
                "knowledge_type": "best_practices"
            }
        )
        
        collaboration_engine.active_sessions[session.session_id] = session
        
        # Test knowledge transfer initiation
        plan = {"objectives": ["transfer_ml_knowledge"]}
        await collaboration_engine._initiate_knowledge_transfer(session, plan)
        
        assert session.status == CollaborationStatus.IN_PROGRESS
        assert "knowledge_transfers" in session.shared_artifacts
        assert len(session.shared_artifacts["knowledge_transfers"]) == 2  # Two learners

    @pytest.mark.asyncio
    async def test_task_delegation_optimization(self, collaboration_engine):
        """Test task delegation optimization."""
        delegate_agents = ["agent_1", "agent_2", "agent_3"]
        task_details = {
            "task_name": "feature_development",
            "complexity": "high",
            "estimated_effort": "2_weeks"
        }
        required_skills = ["python", "api_development", "testing"]
        
        assignments = await collaboration_engine._optimize_task_delegation(
            delegate_agents, task_details, required_skills
        )
        
        assert "task_breakdown" in assignments
        assert "agent_assignments" in assignments
        assert "coordination_plan" in assignments

    @pytest.mark.asyncio
    async def test_collaborative_solving_initiation(self, collaboration_engine):
        """Test collaborative solving session initiation."""
        session = CollaborationSession(
            session_id="solving_session_001",
            collaboration_type=CollaborationType.COLLABORATIVE_SOLVING,
            participants=["agent_1", "agent_2", "agent_3", "agent_4"],
            initiator="agent_1",
            status=CollaborationStatus.INITIATED,
            context={
                "problem": {
                    "type": "optimization",
                    "description": "Optimize system performance",
                    "constraints": ["budget", "timeline"]
                }
            }
        )
        
        collaboration_engine.active_sessions[session.session_id] = session
        
        # Test collaborative solving initiation
        plan = {"objectives": ["identify_bottlenecks", "propose_solutions"]}
        await collaboration_engine._initiate_collaborative_solving(session, plan)
        
        assert session.status == CollaborationStatus.IN_PROGRESS
        assert "solving_framework" in session.shared_artifacts
        framework = session.shared_artifacts["solving_framework"]
        assert "brainstorming_phase" in framework
        assert "analysis_phase" in framework
        assert "solution_phase" in framework

    @pytest.mark.asyncio
    async def test_consensus_building_initiation(self, collaboration_engine):
        """Test consensus building session initiation."""
        session = CollaborationSession(
            session_id="consensus_session_001",
            collaboration_type=CollaborationType.CONSENSUS_BUILDING,
            participants=["agent_1", "agent_2", "agent_3"],
            initiator="agent_1",
            status=CollaborationStatus.INITIATED,
            context={
                "decision": {
                    "topic": "architecture_choice",
                    "description": "Choose microservices vs monolith"
                },
                "options": ["microservices", "monolith", "hybrid"]
            }
        )
        
        collaboration_engine.active_sessions[session.session_id] = session
        
        # Test consensus building initiation
        plan = {"success_criteria": ["majority_agreement", "technical_feasibility"]}
        await collaboration_engine._initiate_consensus_building(session, plan)
        
        assert session.status == CollaborationStatus.IN_PROGRESS
        assert "consensus_framework" in session.shared_artifacts
        framework = session.shared_artifacts["consensus_framework"]
        assert "available_options" in framework
        assert len(framework["available_options"]) == 3
        assert "agent_preferences" in framework

    @pytest.mark.asyncio
    async def test_collaboration_status_retrieval(self, collaboration_engine):
        """Test collaboration status retrieval."""
        # Create active session
        session = CollaborationSession(
            session_id="status_test_001",
            collaboration_type=CollaborationType.PEER_REVIEW,
            participants=["agent_1", "agent_2"],
            initiator="agent_1",
            status=CollaborationStatus.IN_PROGRESS,
            context={"artifact": "test.py"}
        )
        
        collaboration_engine.active_sessions[session.session_id] = session
        
        # Get status
        status = await collaboration_engine.get_collaboration_status(session.session_id)
        
        assert status["session_id"] == session.session_id
        assert status["collaboration_type"] == CollaborationType.PEER_REVIEW.value
        assert status["status"] == CollaborationStatus.IN_PROGRESS.value
        assert len(status["participants"]) == 2
        assert "duration_minutes" in status

    @pytest.mark.asyncio
    async def test_agent_skill_registration(self, collaboration_engine):
        """Test agent skill registration."""
        skills = {
            "python": 0.9,
            "javascript": 0.7,
            "code_review": 0.8,
            "testing": 0.85
        }
        
        await collaboration_engine.register_agent_skills("test_agent", skills)
        
        registered_skills = collaboration_engine.collaboration_network.skill_registry["test_agent"]
        assert len(registered_skills) == 4
        assert registered_skills["python"] == 0.9
        assert registered_skills["javascript"] == 0.7

    @pytest.mark.asyncio
    async def test_collaboration_recommendations(self, collaboration_engine):
        """Test collaboration recommendation generation."""
        # Register some agents with skills
        await collaboration_engine.register_agent_skills("expert_agent", {
            "python": 0.95, "architecture": 0.9, "code_review": 0.85
        })
        await collaboration_engine.register_agent_skills("junior_agent", {
            "python": 0.6, "testing": 0.7
        })
        
        # Simulate some collaboration history for trust scores
        collaboration_engine.collaboration_network.agent_relationships["test_agent"] = {
            "expert_agent": 0.9,
            "junior_agent": 0.7
        }
        
        task_context = {
            "required_skills": ["python", "code_review"],
            "task_type": "code_review",
            "complexity": "medium"
        }
        
        recommendations = await collaboration_engine.get_collaboration_recommendations(
            "test_agent", task_context
        )
        
        assert len(recommendations) > 0
        for rec in recommendations:
            assert "agent_id" in rec
            assert "trust_score" in rec
            assert "collaboration_type" in rec
            assert 0 <= rec["trust_score"] <= 1

    @pytest.mark.asyncio
    async def test_collaboration_history_retrieval(self, collaboration_engine):
        """Test agent collaboration history retrieval."""
        # Create mock collaboration session
        session = CollaborationSession(
            session_id="history_test_001",
            collaboration_type=CollaborationType.PEER_REVIEW,
            participants=["test_agent", "other_agent"],
            initiator="test_agent",
            status=CollaborationStatus.COMPLETED,
            context={"artifact": "test.py"}
        )
        
        # Add to history
        collaboration_engine.collaboration_network.collaboration_history["test_agent"].append(session)
        
        # Add some peer reviews
        review = PeerReviewResult(
            review_id="test_review_001",
            reviewer_agent="test_agent",
            reviewed_artifact="code.py",
            outcome=ReviewOutcome.APPROVED,
            feedback="Good work",
            suggestions=[],
            quality_score=85.0,
            confidence=0.9
        )
        collaboration_engine.peer_reviews[review.review_id] = review
        
        # Get history
        history = await collaboration_engine.get_agent_collaboration_history("test_agent")
        
        assert history["agent_id"] == "test_agent"
        assert history["total_collaborations"] == 1
        assert history["successful_collaborations"] == 1
        assert history["success_rate"] == 1.0
        assert history["peer_reviews_given"] == 1
        assert len(history["recent_collaborations"]) == 1

    def test_collaboration_network_trust_updates(self):
        """Test collaboration network trust score updates."""
        network = CollaborationNetwork()
        
        # Create successful collaboration session
        session = CollaborationSession(
            session_id="trust_test_001",
            collaboration_type=CollaborationType.PEER_REVIEW,
            participants=["agent_1", "agent_2"],
            initiator="agent_1",
            status=CollaborationStatus.COMPLETED,
            context={}
        )
        
        # Update collaboration success
        network.update_collaboration_success(session)
        
        # Check trust scores updated
        assert "agent_2" in network.agent_relationships["agent_1"]
        assert "agent_1" in network.agent_relationships["agent_2"]
        
        trust_score = network.agent_relationships["agent_1"]["agent_2"]
        assert 0.5 <= trust_score <= 1.0  # Should be positive due to successful collaboration

    def test_skill_matching_calculation(self):
        """Test skill matching calculation."""
        network = CollaborationNetwork()
        
        # Register agent skills
        network.skill_registry["skilled_agent"] = {
            "python": 0.9,
            "javascript": 0.7,
            "testing": 0.8
        }
        
        # Test perfect skill match
        required_skills = ["python", "testing"]
        match_score = network._calculate_skill_match("skilled_agent", required_skills)
        assert match_score > 0.8  # Should be high due to good skill match
        
        # Test partial skill match
        required_skills = ["python", "java", "c++"]
        match_score = network._calculate_skill_match("skilled_agent", required_skills)
        assert 0 < match_score < 0.5  # Should be lower due to missing skills
        
        # Test no skill match
        required_skills = ["rust", "go"]
        match_score = network._calculate_skill_match("skilled_agent", required_skills)
        assert match_score == 0.0  # No matching skills

    @pytest.mark.asyncio
    async def test_review_confidence_calculation(self, collaboration_engine):
        """Test review confidence calculation."""
        # Add some historical reviews for an agent
        for i in range(5):
            review = PeerReviewResult(
                review_id=f"hist_review_{i}",
                reviewer_agent="experienced_reviewer",
                reviewed_artifact=f"code_{i}.py",
                outcome=ReviewOutcome.APPROVED,
                feedback="Good",
                suggestions=[],
                quality_score=90.0,
                confidence=0.8
            )
            collaboration_engine.peer_reviews[review.review_id] = review
        
        # Register skills for the reviewer
        await collaboration_engine.register_agent_skills("experienced_reviewer", {
            "code_review": 0.95,
            "python": 0.9
        })
        
        # Test confidence calculation
        context = {"required_skills": ["code_review", "python"]}
        confidence = collaboration_engine._calculate_review_confidence("experienced_reviewer", context)
        
        assert confidence > 0.8  # Should be high due to experience and skill match

    def test_collaboration_request_validation(self, sample_collaboration_request):
        """Test collaboration request validation."""
        assert sample_collaboration_request.request_id == "test_request_001"
        assert sample_collaboration_request.requesting_agent == "agent_1"
        assert len(sample_collaboration_request.target_agents) == 2
        assert sample_collaboration_request.collaboration_type == CollaborationType.PEER_REVIEW
        assert sample_collaboration_request.priority == 7
        assert "artifact" in sample_collaboration_request.context
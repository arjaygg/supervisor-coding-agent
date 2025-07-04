# supervisor_agent/coordination/agent_collaboration_engine.py
"""
Agent Collaboration Engine

This module provides sophisticated agent collaboration capabilities including
dynamic task delegation, peer review, knowledge sharing, and collaborative 
problem solving across multi-agent systems.
"""

import asyncio
import json
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import structlog

from supervisor_agent.coordination.swarm_coordinator import (
    AgentSpecialization,
    AgentState,
    CoordinationEvent,
    CoordinationEventType,
    SwarmAgent,
)
from supervisor_agent.intelligence.workflow_synthesizer import ClaudeAgentWrapper
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
structured_logger = structlog.get_logger(__name__)


class CollaborationType(Enum):
    """Types of agent collaboration patterns."""
    PEER_REVIEW = "peer_review"
    KNOWLEDGE_TRANSFER = "knowledge_transfer"
    TASK_DELEGATION = "task_delegation"
    COLLABORATIVE_SOLVING = "collaborative_solving"
    CONSENSUS_BUILDING = "consensus_building"
    SKILL_SHARING = "skill_sharing"
    RESOURCE_SHARING = "resource_sharing"
    MENTORING = "mentoring"


class CollaborationStatus(Enum):
    """Status of collaboration sessions."""
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    REVIEW_PENDING = "review_pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewOutcome(Enum):
    """Outcomes of peer review sessions."""
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"
    ESCALATED = "escalated"
    DEFERRED = "deferred"


@dataclass
class CollaborationRequest:
    """Request for agent collaboration."""
    request_id: str
    requesting_agent: str
    target_agents: List[str]
    collaboration_type: CollaborationType
    priority: int  # 1-10, higher is more urgent
    description: str
    context: Dict[str, Any]
    required_skills: List[str] = field(default_factory=list)
    estimated_duration: int = 60  # minutes
    deadline: Optional[datetime] = None
    prerequisites: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CollaborationSession:
    """Active collaboration session between agents."""
    session_id: str
    collaboration_type: CollaborationType
    participants: List[str]
    initiator: str
    status: CollaborationStatus
    context: Dict[str, Any]
    shared_artifacts: Dict[str, Any] = field(default_factory=dict)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    review_feedback: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_shared: List[Dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    outcome: Optional[Dict[str, Any]] = None


@dataclass
class PeerReviewResult:
    """Result of a peer review session."""
    review_id: str
    reviewer_agent: str
    reviewed_artifact: str
    outcome: ReviewOutcome
    feedback: str
    suggestions: List[str]
    quality_score: float  # 0-100
    confidence: float  # 0-1
    review_criteria: List[str] = field(default_factory=list)
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class KnowledgeTransfer:
    """Knowledge transfer between agents."""
    transfer_id: str
    source_agent: str
    target_agent: str
    knowledge_type: str
    content: Dict[str, Any]
    context: str
    effectiveness_score: Optional[float] = None
    validation_status: Optional[str] = None
    transferred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CollaborationNetwork:
    """Manages collaboration relationships and patterns between agents."""
    
    def __init__(self):
        self.collaboration_history: Dict[str, List[CollaborationSession]] = defaultdict(list)
        self.agent_relationships: Dict[str, Dict[str, float]] = defaultdict(dict)  # Trust scores
        self.collaboration_patterns: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.skill_registry: Dict[str, Dict[str, float]] = defaultdict(dict)  # Agent skills
        
    def update_collaboration_success(self, session: CollaborationSession):
        """Update collaboration success metrics."""
        for participant in session.participants:
            self.collaboration_history[participant].append(session)
            
            # Update trust scores between participants
            for other_participant in session.participants:
                if other_participant != participant:
                    success_factor = 1.0 if session.status == CollaborationStatus.COMPLETED else 0.5
                    current_trust = self.agent_relationships[participant].get(other_participant, 0.5)
                    # Exponential moving average for trust updates
                    self.agent_relationships[participant][other_participant] = (
                        0.8 * current_trust + 0.2 * success_factor
                    )
    
    def get_collaboration_recommendations(self, agent_id: str, task_context: Dict[str, Any]) -> List[str]:
        """Get recommended collaboration partners for an agent."""
        required_skills = task_context.get("required_skills", [])
        
        # Score potential collaborators
        candidates = []
        for other_agent, trust_score in self.agent_relationships[agent_id].items():
            skill_match = self._calculate_skill_match(other_agent, required_skills)
            collaboration_score = trust_score * 0.6 + skill_match * 0.4
            candidates.append((other_agent, collaboration_score))
        
        # Sort by collaboration score and return top candidates
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [agent for agent, _ in candidates[:5]]  # Top 5
    
    def _calculate_skill_match(self, agent_id: str, required_skills: List[str]) -> float:
        """Calculate how well an agent's skills match requirements."""
        if not required_skills:
            return 0.5
        
        agent_skills = self.skill_registry.get(agent_id, {})
        matches = 0
        total_skill_level = 0
        
        for skill in required_skills:
            if skill in agent_skills:
                matches += 1
                total_skill_level += agent_skills[skill]
        
        if matches == 0:
            return 0.0
        
        return (matches / len(required_skills)) * (total_skill_level / matches)


class AgentCollaborationEngine:
    """
    Advanced engine for managing dynamic agent collaboration, peer review,
    knowledge sharing, and collaborative problem solving.
    """
    
    def __init__(self, claude_agent: ClaudeAgentWrapper):
        self.claude_agent = claude_agent
        self.collaboration_network = CollaborationNetwork()
        
        # Active sessions and requests
        self.active_sessions: Dict[str, CollaborationSession] = {}
        self.pending_requests: Dict[str, CollaborationRequest] = {}
        
        # Review and knowledge management
        self.peer_reviews: Dict[str, PeerReviewResult] = {}
        self.knowledge_transfers: Dict[str, KnowledgeTransfer] = {}
        
        # Communication and coordination
        self.collaboration_queue: asyncio.Queue = asyncio.Queue()
        self.notification_handlers: Dict[str, callable] = {}
        
        # Performance tracking
        self.collaboration_metrics: Dict[str, Any] = defaultdict(dict)
        
        self.logger = structured_logger.bind(component="collaboration_engine")
    
    async def request_collaboration(
        self, 
        requesting_agent: str,
        collaboration_type: CollaborationType,
        context: Dict[str, Any],
        target_agents: Optional[List[str]] = None,
        priority: int = 5
    ) -> str:
        """Request collaboration with other agents."""
        
        request_id = str(uuid.uuid4())
        
        # Auto-discover target agents if not specified
        if not target_agents:
            target_agents = self.collaboration_network.get_collaboration_recommendations(
                requesting_agent, context
            )
        
        # Create collaboration request
        request = CollaborationRequest(
            request_id=request_id,
            requesting_agent=requesting_agent,
            target_agents=target_agents,
            collaboration_type=collaboration_type,
            priority=priority,
            description=context.get("description", "Collaboration request"),
            context=context,
            required_skills=context.get("required_skills", [])
        )
        
        self.pending_requests[request_id] = request
        
        # Process collaboration request
        await self._process_collaboration_request(request)
        
        self.logger.info(
            "Collaboration request created",
            request_id=request_id,
            requesting_agent=requesting_agent,
            collaboration_type=collaboration_type.value,
            target_agents=target_agents
        )
        
        return request_id
    
    async def _process_collaboration_request(self, request: CollaborationRequest):
        """Process a collaboration request and initiate sessions."""
        
        try:
            # Analyze collaboration requirements using AI
            collaboration_plan = await self._generate_collaboration_plan(request)
            
            # Create collaboration session
            session_id = str(uuid.uuid4())
            session = CollaborationSession(
                session_id=session_id,
                collaboration_type=request.collaboration_type,
                participants=[request.requesting_agent] + request.target_agents,
                initiator=request.requesting_agent,
                status=CollaborationStatus.INITIATED,
                context=request.context
            )
            
            self.active_sessions[session_id] = session
            
            # Initialize collaboration based on type
            if request.collaboration_type == CollaborationType.PEER_REVIEW:
                await self._initiate_peer_review(session, collaboration_plan)
            elif request.collaboration_type == CollaborationType.KNOWLEDGE_TRANSFER:
                await self._initiate_knowledge_transfer(session, collaboration_plan)
            elif request.collaboration_type == CollaborationType.TASK_DELEGATION:
                await self._initiate_task_delegation(session, collaboration_plan)
            elif request.collaboration_type == CollaborationType.COLLABORATIVE_SOLVING:
                await self._initiate_collaborative_solving(session, collaboration_plan)
            elif request.collaboration_type == CollaborationType.CONSENSUS_BUILDING:
                await self._initiate_consensus_building(session, collaboration_plan)
            else:
                await self._initiate_generic_collaboration(session, collaboration_plan)
            
            # Remove from pending requests
            if request.request_id in self.pending_requests:
                del self.pending_requests[request.request_id]
                
        except Exception as e:
            self.logger.error(
                "Failed to process collaboration request",
                request_id=request.request_id,
                error=str(e)
            )
    
    async def _generate_collaboration_plan(self, request: CollaborationRequest) -> Dict[str, Any]:
        """Generate an AI-powered collaboration plan."""
        
        collaboration_prompt = f"""
        Generate an optimal collaboration plan for multi-agent coordination:
        
        Collaboration Request: {json.dumps({
            "type": request.collaboration_type.value,
            "requesting_agent": request.requesting_agent,
            "target_agents": request.target_agents,
            "context": request.context,
            "required_skills": request.required_skills,
            "priority": request.priority
        }, indent=2)}
        
        Analyze this collaboration requirement and create a detailed plan:
        1. What are the specific objectives of this collaboration?
        2. How should the agents coordinate and communicate?
        3. What are the roles and responsibilities of each participant?
        4. What is the optimal workflow and sequence of activities?
        5. What artifacts should be shared or reviewed?
        6. How should progress be monitored and quality ensured?
        7. What are the success criteria and completion conditions?
        8. What potential challenges should be anticipated?
        
        Provide a comprehensive collaboration plan in JSON format with:
        - objectives: clear collaboration goals
        - roles: specific roles for each participant
        - workflow: step-by-step collaboration process
        - communication_plan: how agents should interact
        - artifacts: expected deliverables and shared resources
        - quality_gates: checkpoints and review criteria
        - success_criteria: conditions for successful completion
        - risk_mitigation: strategies for handling challenges
        - timeline: estimated duration and milestones
        
        Focus on maximizing collaboration effectiveness and ensuring high-quality outcomes.
        """
        
        result = await self.claude_agent.execute_task(
            {"type": "collaboration_planning", "prompt": collaboration_prompt},
            shared_memory={"collaboration_context": request.context}
        )
        
        try:
            return json.loads(result["result"])
        except (json.JSONDecodeError, KeyError):
            # Return basic plan as fallback
            return self._create_basic_collaboration_plan(request)
    
    def _create_basic_collaboration_plan(self, request: CollaborationRequest) -> Dict[str, Any]:
        """Create a basic collaboration plan as fallback."""
        return {
            "objectives": [f"Complete {request.collaboration_type.value} collaboration"],
            "roles": {agent: "participant" for agent in [request.requesting_agent] + request.target_agents},
            "workflow": [
                "Initialize collaboration",
                "Share context and requirements",
                "Execute collaboration activities",
                "Review and validate outcomes",
                "Complete collaboration"
            ],
            "communication_plan": {"method": "direct", "frequency": "as_needed"},
            "artifacts": {"shared_context": request.context},
            "quality_gates": ["peer_review", "outcome_validation"],
            "success_criteria": ["objectives_met", "quality_approved"],
            "timeline": {"estimated_duration": request.estimated_duration}
        }
    
    async def _initiate_peer_review(self, session: CollaborationSession, plan: Dict[str, Any]):
        """Initiate a peer review collaboration session."""
        
        session.status = CollaborationStatus.IN_PROGRESS
        
        # Extract review artifact and criteria
        review_artifact = session.context.get("artifact", "")
        review_criteria = plan.get("quality_gates", ["correctness", "completeness", "efficiency"])
        
        # Assign reviewers (exclude initiator)
        reviewers = [p for p in session.participants if p != session.initiator]
        
        # Generate review tasks for each reviewer
        for reviewer in reviewers:
            review_task = await self._generate_review_task(
                reviewer, review_artifact, review_criteria, session.context
            )
            
            # Store review task in session
            if "review_tasks" not in session.shared_artifacts:
                session.shared_artifacts["review_tasks"] = {}
            session.shared_artifacts["review_tasks"][reviewer] = review_task
        
        self.logger.info(
            "Peer review session initiated",
            session_id=session.session_id,
            reviewers=reviewers,
            criteria=review_criteria
        )
    
    async def _generate_review_task(
        self, 
        reviewer: str, 
        artifact: str, 
        criteria: List[str], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a specific review task for a reviewer."""
        
        review_prompt = f"""
        Generate a comprehensive peer review task for agent collaboration:
        
        Reviewer: {reviewer}
        Artifact to Review: {artifact}
        Review Criteria: {criteria}
        Context: {json.dumps(context, indent=2)}
        
        Create a detailed review task that includes:
        1. Specific aspects to evaluate based on the criteria
        2. Questions to guide the review process
        3. Quality metrics to assess
        4. Expected deliverables from the review
        5. Review methodology and best practices
        6. Timeline and priorities
        
        Provide the review task in JSON format with:
        - evaluation_aspects: specific areas to review
        - guiding_questions: questions to structure the review
        - quality_metrics: measurable quality indicators
        - deliverables: expected review outputs
        - methodology: recommended review approach
        - priority_areas: most critical aspects to focus on
        - success_criteria: what constitutes a good review
        
        Focus on thorough, constructive, and actionable feedback.
        """
        
        result = await self.claude_agent.execute_task(
            {"type": "review_task_generation", "prompt": review_prompt},
            shared_memory={"review_context": context}
        )
        
        try:
            return json.loads(result["result"])
        except (json.JSONDecodeError, KeyError):
            return {
                "evaluation_aspects": criteria,
                "guiding_questions": [f"How well does this meet {criterion}?" for criterion in criteria],
                "quality_metrics": ["accuracy", "completeness", "clarity"],
                "deliverables": ["feedback", "score", "recommendations"],
                "methodology": "systematic_evaluation"
            }
    
    async def _initiate_knowledge_transfer(self, session: CollaborationSession, plan: Dict[str, Any]):
        """Initiate a knowledge transfer collaboration session."""
        
        session.status = CollaborationStatus.IN_PROGRESS
        
        knowledge_source = session.initiator
        knowledge_targets = [p for p in session.participants if p != session.initiator]
        
        # Extract knowledge to transfer
        knowledge_content = session.context.get("knowledge", {})
        knowledge_type = session.context.get("knowledge_type", "general")
        
        # Create knowledge transfer records
        for target_agent in knowledge_targets:
            transfer_id = str(uuid.uuid4())
            transfer = KnowledgeTransfer(
                transfer_id=transfer_id,
                source_agent=knowledge_source,
                target_agent=target_agent,
                knowledge_type=knowledge_type,
                content=knowledge_content,
                context=session.context.get("description", "Knowledge transfer")
            )
            
            self.knowledge_transfers[transfer_id] = transfer
            
            # Store transfer in session
            if "knowledge_transfers" not in session.shared_artifacts:
                session.shared_artifacts["knowledge_transfers"] = []
            session.shared_artifacts["knowledge_transfers"].append(transfer_id)
        
        self.logger.info(
            "Knowledge transfer session initiated",
            session_id=session.session_id,
            source=knowledge_source,
            targets=knowledge_targets,
            knowledge_type=knowledge_type
        )
    
    async def _initiate_task_delegation(self, session: CollaborationSession, plan: Dict[str, Any]):
        """Initiate a task delegation collaboration session."""
        
        session.status = CollaborationStatus.IN_PROGRESS
        
        delegating_agent = session.initiator
        delegate_agents = [p for p in session.participants if p != session.initiator]
        
        # Extract task details
        task_details = session.context.get("task", {})
        required_skills = session.context.get("required_skills", [])
        
        # Assign optimal delegates based on skills and availability
        delegation_assignments = await self._optimize_task_delegation(
            delegate_agents, task_details, required_skills
        )
        
        # Store delegation assignments
        session.shared_artifacts["delegation_assignments"] = delegation_assignments
        session.shared_artifacts["task_details"] = task_details
        
        self.logger.info(
            "Task delegation session initiated",
            session_id=session.session_id,
            delegating_agent=delegating_agent,
            assignments=delegation_assignments
        )
    
    async def _optimize_task_delegation(
        self, 
        delegate_agents: List[str], 
        task_details: Dict[str, Any], 
        required_skills: List[str]
    ) -> Dict[str, Any]:
        """Optimize task delegation assignments using AI."""
        
        delegation_prompt = f"""
        Optimize task delegation assignments for multi-agent collaboration:
        
        Available Delegates: {delegate_agents}
        Task Details: {json.dumps(task_details, indent=2)}
        Required Skills: {required_skills}
        
        Analyze the task requirements and delegate capabilities to create optimal assignments:
        1. How should the task be broken down into subtasks?
        2. Which delegate is best suited for each subtask?
        3. What are the dependencies between subtasks?
        4. How should progress be monitored and coordinated?
        5. What are the communication requirements?
        6. What quality assurance measures are needed?
        
        Provide optimal delegation strategy in JSON format with:
        - task_breakdown: subtasks with clear definitions
        - agent_assignments: which agent handles which subtasks
        - dependencies: relationships between subtasks
        - coordination_plan: how agents should coordinate
        - progress_tracking: monitoring and reporting approach
        - quality_gates: checkpoints and validation criteria
        - timeline: estimated completion schedule
        
        Focus on maximizing efficiency while ensuring quality delivery.
        """
        
        result = await self.claude_agent.execute_task(
            {"type": "task_delegation_optimization", "prompt": delegation_prompt},
            shared_memory={"delegation_context": task_details}
        )
        
        try:
            return json.loads(result["result"])
        except (json.JSONDecodeError, KeyError):
            # Basic assignment as fallback
            return {
                "task_breakdown": [{"subtask": "complete_task", "assigned_to": delegate_agents[0] if delegate_agents else ""}],
                "agent_assignments": {delegate_agents[0]: ["complete_task"] if delegate_agents else {}},
                "coordination_plan": {"method": "periodic_updates"},
                "timeline": {"estimated_duration": 60}
            }
    
    async def _initiate_collaborative_solving(self, session: CollaborationSession, plan: Dict[str, Any]):
        """Initiate a collaborative problem solving session."""
        
        session.status = CollaborationStatus.IN_PROGRESS
        
        problem_context = session.context.get("problem", {})
        
        # Create collaborative solving structure
        solving_framework = {
            "problem_definition": problem_context,
            "brainstorming_phase": {"ideas": [], "contributors": []},
            "analysis_phase": {"evaluations": [], "criteria": []},
            "solution_phase": {"proposals": [], "consensus": None},
            "validation_phase": {"tests": [], "results": []}
        }
        
        session.shared_artifacts["solving_framework"] = solving_framework
        
        self.logger.info(
            "Collaborative solving session initiated",
            session_id=session.session_id,
            participants=session.participants,
            problem_type=problem_context.get("type", "general")
        )
    
    async def _initiate_consensus_building(self, session: CollaborationSession, plan: Dict[str, Any]):
        """Initiate a consensus building collaboration session."""
        
        session.status = CollaborationStatus.IN_PROGRESS
        
        decision_context = session.context.get("decision", {})
        options = session.context.get("options", [])
        
        # Create consensus building structure
        consensus_framework = {
            "decision_context": decision_context,
            "available_options": options,
            "agent_preferences": {},
            "discussion_points": [],
            "consensus_criteria": plan.get("success_criteria", ["majority_agreement"]),
            "final_decision": None
        }
        
        session.shared_artifacts["consensus_framework"] = consensus_framework
        
        self.logger.info(
            "Consensus building session initiated",
            session_id=session.session_id,
            participants=session.participants,
            options_count=len(options)
        )
    
    async def _initiate_generic_collaboration(self, session: CollaborationSession, plan: Dict[str, Any]):
        """Initiate a generic collaboration session."""
        
        session.status = CollaborationStatus.IN_PROGRESS
        
        # Create basic collaboration structure
        collaboration_framework = {
            "objectives": plan.get("objectives", []),
            "workflow": plan.get("workflow", []),
            "shared_resources": session.context,
            "progress_tracking": {"completed_steps": [], "current_step": 0},
            "participant_contributions": {p: [] for p in session.participants}
        }
        
        session.shared_artifacts["collaboration_framework"] = collaboration_framework
        
        self.logger.info(
            "Generic collaboration session initiated",
            session_id=session.session_id,
            collaboration_type=session.collaboration_type.value,
            participants=session.participants
        )
    
    async def submit_peer_review(
        self, 
        reviewer_agent: str, 
        session_id: str, 
        review_feedback: str,
        quality_score: float,
        outcome: ReviewOutcome,
        suggestions: List[str] = None
    ) -> str:
        """Submit a peer review result."""
        
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.active_sessions[session_id]
        
        if reviewer_agent not in session.participants:
            raise ValueError(f"Agent {reviewer_agent} not a participant in session {session_id}")
        
        # Create peer review result
        review_id = str(uuid.uuid4())
        review = PeerReviewResult(
            review_id=review_id,
            reviewer_agent=reviewer_agent,
            reviewed_artifact=session.context.get("artifact", ""),
            outcome=outcome,
            feedback=review_feedback,
            suggestions=suggestions or [],
            quality_score=quality_score,
            confidence=self._calculate_review_confidence(reviewer_agent, session.context)
        )
        
        self.peer_reviews[review_id] = review
        session.review_feedback.append(review_id)
        
        # Check if all reviews are complete
        expected_reviewers = [p for p in session.participants if p != session.initiator]
        if len(session.review_feedback) >= len(expected_reviewers):
            await self._finalize_peer_review_session(session)
        
        self.logger.info(
            "Peer review submitted",
            review_id=review_id,
            reviewer=reviewer_agent,
            session_id=session_id,
            outcome=outcome.value,
            quality_score=quality_score
        )
        
        return review_id
    
    def _calculate_review_confidence(self, reviewer_agent: str, context: Dict[str, Any]) -> float:
        """Calculate reviewer confidence based on expertise and context."""
        # Base confidence
        confidence = 0.7
        
        # Adjust based on agent's historical review performance
        agent_reviews = [r for r in self.peer_reviews.values() if r.reviewer_agent == reviewer_agent]
        if agent_reviews:
            avg_quality = sum(r.quality_score for r in agent_reviews[-10:]) / min(len(agent_reviews), 10)
            confidence += (avg_quality / 100) * 0.2
        
        # Adjust based on skill match
        required_skills = context.get("required_skills", [])
        agent_skills = self.collaboration_network.skill_registry.get(reviewer_agent, {})
        
        if required_skills and agent_skills:
            skill_match = sum(agent_skills.get(skill, 0) for skill in required_skills) / len(required_skills)
            confidence += skill_match * 0.1
        
        return min(1.0, confidence)
    
    async def _finalize_peer_review_session(self, session: CollaborationSession):
        """Finalize a peer review session and determine overall outcome."""
        
        reviews = [self.peer_reviews[review_id] for review_id in session.review_feedback]
        
        # Aggregate review results
        avg_quality_score = sum(r.quality_score for r in reviews) / len(reviews)
        approval_count = len([r for r in reviews if r.outcome == ReviewOutcome.APPROVED])
        rejection_count = len([r for r in reviews if r.outcome == ReviewOutcome.REJECTED])
        
        # Determine overall outcome
        if approval_count > rejection_count:
            overall_outcome = ReviewOutcome.APPROVED
        elif rejection_count > approval_count:
            overall_outcome = ReviewOutcome.REJECTED
        else:
            overall_outcome = ReviewOutcome.NEEDS_REVISION
        
        # Finalize session
        session.status = CollaborationStatus.COMPLETED
        session.completed_at = datetime.now(timezone.utc)
        session.outcome = {
            "type": "peer_review",
            "overall_outcome": overall_outcome.value,
            "average_quality_score": avg_quality_score,
            "review_count": len(reviews),
            "approval_rate": approval_count / len(reviews)
        }
        
        # Update collaboration network
        self.collaboration_network.update_collaboration_success(session)
        
        self.logger.info(
            "Peer review session finalized",
            session_id=session.session_id,
            overall_outcome=overall_outcome.value,
            avg_quality_score=avg_quality_score,
            review_count=len(reviews)
        )
    
    async def get_collaboration_status(self, session_id: str) -> Dict[str, Any]:
        """Get the current status of a collaboration session."""
        
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        session = self.active_sessions[session_id]
        
        status_info = {
            "session_id": session_id,
            "collaboration_type": session.collaboration_type.value,
            "status": session.status.value,
            "participants": session.participants,
            "initiator": session.initiator,
            "started_at": session.started_at.isoformat(),
            "duration_minutes": (datetime.now(timezone.utc) - session.started_at).total_seconds() / 60,
            "shared_artifacts_count": len(session.shared_artifacts),
            "decisions_made": len(session.decisions),
            "knowledge_shared_count": len(session.knowledge_shared)
        }
        
        if session.completed_at:
            status_info["completed_at"] = session.completed_at.isoformat()
            status_info["total_duration_minutes"] = (session.completed_at - session.started_at).total_seconds() / 60
        
        if session.outcome:
            status_info["outcome"] = session.outcome
        
        # Add type-specific information
        if session.collaboration_type == CollaborationType.PEER_REVIEW:
            status_info["reviews_submitted"] = len(session.review_feedback)
            
        elif session.collaboration_type == CollaborationType.KNOWLEDGE_TRANSFER:
            transfer_ids = session.shared_artifacts.get("knowledge_transfers", [])
            status_info["knowledge_transfers"] = len(transfer_ids)
        
        return status_info
    
    async def get_agent_collaboration_history(self, agent_id: str) -> Dict[str, Any]:
        """Get collaboration history and metrics for an agent."""
        
        agent_sessions = self.collaboration_network.collaboration_history.get(agent_id, [])
        
        # Calculate collaboration metrics
        total_collaborations = len(agent_sessions)
        successful_collaborations = len([s for s in agent_sessions if s.status == CollaborationStatus.COMPLETED])
        
        collaboration_types = defaultdict(int)
        for session in agent_sessions:
            collaboration_types[session.collaboration_type.value] += 1
        
        # Calculate average ratings from peer reviews
        agent_reviews = [r for r in self.peer_reviews.values() if r.reviewer_agent == agent_id]
        avg_review_quality = sum(r.quality_score for r in agent_reviews) / len(agent_reviews) if agent_reviews else 0
        
        # Get collaboration partners and trust scores
        trust_scores = self.collaboration_network.agent_relationships.get(agent_id, {})
        
        return {
            "agent_id": agent_id,
            "total_collaborations": total_collaborations,
            "successful_collaborations": successful_collaborations,
            "success_rate": successful_collaborations / total_collaborations if total_collaborations > 0 else 0,
            "collaboration_types": dict(collaboration_types),
            "peer_reviews_given": len(agent_reviews),
            "average_review_quality": avg_review_quality,
            "collaboration_partners": len(trust_scores),
            "trust_scores": trust_scores,
            "registered_skills": self.collaboration_network.skill_registry.get(agent_id, {}),
            "recent_collaborations": [
                {
                    "session_id": s.session_id,
                    "type": s.collaboration_type.value,
                    "status": s.status.value,
                    "participants": len(s.participants),
                    "started_at": s.started_at.isoformat()
                }
                for s in sorted(agent_sessions, key=lambda x: x.started_at, reverse=True)[:10]
            ]
        }
    
    async def register_agent_skills(self, agent_id: str, skills: Dict[str, float]):
        """Register or update an agent's skills in the collaboration network."""
        
        # Validate skill levels (0-1)
        validated_skills = {
            skill: max(0.0, min(1.0, level)) 
            for skill, level in skills.items()
        }
        
        self.collaboration_network.skill_registry[agent_id].update(validated_skills)
        
        self.logger.info(
            "Agent skills registered",
            agent_id=agent_id,
            skills=validated_skills
        )
    
    async def get_collaboration_recommendations(self, agent_id: str, task_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get AI-powered collaboration recommendations for an agent."""
        
        # Get basic recommendations from network
        recommended_agents = self.collaboration_network.get_collaboration_recommendations(agent_id, task_context)
        
        # Enhance with AI analysis
        recommendation_prompt = f"""
        Provide intelligent collaboration recommendations for multi-agent task execution:
        
        Requesting Agent: {agent_id}
        Task Context: {json.dumps(task_context, indent=2)}
        Available Collaborators: {recommended_agents}
        
        Agent Collaboration History: {await self.get_agent_collaboration_history(agent_id)}
        
        Analyze the task requirements and recommend optimal collaboration strategies:
        1. What type of collaboration would be most beneficial?
        2. Which agents should be involved and in what roles?
        3. What collaboration patterns would work best?
        4. What are the potential benefits and risks?
        5. How should the collaboration be structured and managed?
        
        Provide recommendations in JSON format with:
        - collaboration_type: recommended type of collaboration
        - recommended_agents: specific agents to collaborate with
        - collaboration_strategy: how to structure the collaboration
        - expected_benefits: anticipated advantages
        - success_factors: critical elements for success
        - timeline: recommended schedule and milestones
        - quality_measures: how to ensure high-quality outcomes
        
        Focus on maximizing task success through effective collaboration.
        """
        
        result = await self.claude_agent.execute_task(
            {"type": "collaboration_recommendation", "prompt": recommendation_prompt},
            shared_memory={"recommendation_context": task_context}
        )
        
        try:
            ai_recommendations = json.loads(result["result"])
            
            # Combine with network-based recommendations
            recommendations = []
            for agent in recommended_agents:
                trust_score = self.collaboration_network.agent_relationships[agent_id].get(agent, 0.5)
                recommendations.append({
                    "agent_id": agent,
                    "trust_score": trust_score,
                    "collaboration_type": ai_recommendations.get("collaboration_type", "collaborative_solving"),
                    "expected_benefits": ai_recommendations.get("expected_benefits", []),
                    "recommended_role": "collaborator"
                })
            
            return recommendations
            
        except (json.JSONDecodeError, KeyError):
            # Return basic recommendations
            return [
                {
                    "agent_id": agent,
                    "trust_score": self.collaboration_network.agent_relationships[agent_id].get(agent, 0.5),
                    "collaboration_type": "collaborative_solving",
                    "expected_benefits": ["shared_expertise", "improved_quality"],
                    "recommended_role": "collaborator"
                }
                for agent in recommended_agents
            ]


# Factory function for easy integration
async def create_collaboration_engine(claude_api_key: Optional[str] = None) -> AgentCollaborationEngine:
    """Factory function to create configured collaboration engine."""
    
    claude_agent = ClaudeAgentWrapper(api_key=claude_api_key)
    return AgentCollaborationEngine(claude_agent)
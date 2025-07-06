"""
Intelligent Swarm Coordinator

This module provides AI-powered orchestration of multi-agent collaboration.
It handles dynamic agent creation, task assignment, conflict resolution, and
real-time optimization of swarm execution.
"""

import asyncio
import concurrent.futures
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog
from pydantic import BaseModel

# from supervisor_agent.db.workflow_models import WorkflowContext, WorkflowStatus
from supervisor_agent.intelligence.workflow_synthesizer import (
    ClaudeAgentWrapper,
    EnhancedWorkflowDefinition,
    TenantContext,
)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
structured_logger = structlog.get_logger(__name__)


class AgentState(Enum):
    """Agent states in the swarm"""

    IDLE = "idle"
    ASSIGNED = "assigned"
    WORKING = "working"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class CoordinationEventType(Enum):
    """Types of coordination events between agents"""

    TASK_HANDOFF = "task_handoff"
    CONFLICT_RESOLUTION = "conflict_resolution"
    RESOURCE_CONTENTION = "resource_contention"
    QUALITY_CONCERN = "quality_concern"
    PERFORMANCE_ISSUE = "performance_issue"
    COLLABORATION_REQUEST = "collaboration_request"


class AgentSpecialization(Enum):
    """Agent specialization types"""

    GENERALIST = "generalist"
    REQUIREMENTS_ANALYST = "requirements_analyst"
    SOLUTION_ARCHITECT = "solution_architect"
    SECURITY_SPECIALIST = "security_specialist"
    PERFORMANCE_ENGINEER = "performance_engineer"
    QUALITY_ASSURANCE = "quality_assurance"
    INTEGRATION_SPECIALIST = "integration_specialist"
    DEVOPS_ENGINEER = "devops_engineer"


@dataclass
class AgentCapability:
    """Individual agent capability"""

    capability_name: str
    proficiency_level: float  # 0.0 to 1.0
    tools_required: List[str]
    estimated_throughput: float  # tasks per hour
    quality_score: float  # historical quality metric


@dataclass
class AgentConfiguration:
    """Configuration for an agent in the swarm"""

    agent_id: str
    specialization: AgentSpecialization
    capabilities: List[AgentCapability]
    resource_limits: Dict[str, Any]
    communication_preferences: Dict[str, Any]
    collaboration_rules: Dict[str, Any]
    performance_targets: Dict[str, float]
    tools_access: List[str]
    context_window_size: int = 32000
    max_concurrent_tasks: int = 3

    @classmethod
    def from_claude_response(cls, response: str, agent_id: str) -> "AgentConfiguration":
        """Create agent configuration from Claude response"""
        try:
            data = json.loads(response)

            # Parse capabilities
            capabilities = []
            for cap_data in data.get("capabilities", []):
                capability = AgentCapability(
                    capability_name=cap_data.get("capability_name", "generic"),
                    proficiency_level=cap_data.get("proficiency_level", 0.5),
                    tools_required=cap_data.get("tools_required", []),
                    estimated_throughput=cap_data.get("estimated_throughput", 1.0),
                    quality_score=cap_data.get("quality_score", 0.7),
                )
                capabilities.append(capability)

            return cls(
                agent_id=agent_id,
                specialization=AgentSpecialization(
                    data.get("specialization", "generalist")
                ),
                capabilities=capabilities,
                resource_limits=data.get("resource_limits", {}),
                communication_preferences=data.get("communication_preferences", {}),
                collaboration_rules=data.get("collaboration_rules", {}),
                performance_targets=data.get("performance_targets", {}),
                tools_access=data.get("tools_access", []),
                context_window_size=data.get("context_window_size", 32000),
                max_concurrent_tasks=data.get("max_concurrent_tasks", 3),
            )

        except (json.JSONDecodeError, KeyError, ValueError):
            # Return default configuration
            return cls._create_default_config(agent_id)

    @classmethod
    def _create_default_config(cls, agent_id: str) -> "AgentConfiguration":
        """Create default agent configuration"""
        default_capability = AgentCapability(
            capability_name="general_task_processing",
            proficiency_level=0.7,
            tools_required=["basic_tools"],
            estimated_throughput=1.0,
            quality_score=0.7,
        )

        return cls(
            agent_id=agent_id,
            specialization=AgentSpecialization.GENERALIST,
            capabilities=[default_capability],
            resource_limits={"memory_gb": 4, "cpu_cores": 2},
            communication_preferences={"protocol": "async", "batch_size": 10},
            collaboration_rules={"max_handoffs": 3, "peer_review": True},
            performance_targets={
                "tasks_per_hour": 2,
                "quality_threshold": 0.8,
            },
            tools_access=["basic_tools"],
        )


@dataclass
class SwarmAgent:
    """Individual agent in the swarm"""

    agent_id: str
    configuration: AgentConfiguration
    current_state: AgentState
    assigned_tasks: List[str] = field(default_factory=list)
    current_workload: int = 0
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    last_activity: Optional[datetime] = None
    context_memory: Dict[str, Any] = field(default_factory=dict)
    collaboration_history: List[Dict[str, Any]] = field(default_factory=list)

    def can_accept_task(self, task_requirements: Dict[str, Any]) -> bool:
        """Check if agent can accept a new task"""
        if self.current_state not in [AgentState.IDLE, AgentState.WORKING]:
            return False

        if self.current_workload >= self.configuration.max_concurrent_tasks:
            return False

        # Check capability match
        required_capabilities = task_requirements.get("required_capabilities", [])
        agent_capabilities = [
            cap.capability_name for cap in self.configuration.capabilities
        ]

        return any(req_cap in agent_capabilities for req_cap in required_capabilities)

    def get_capability_score(self, capability_name: str) -> float:
        """Get proficiency score for a specific capability"""
        for capability in self.configuration.capabilities:
            if capability.capability_name == capability_name:
                return capability.proficiency_level
        return 0.0


@dataclass
class CoordinationEvent:
    """Event requiring coordination between agents"""

    event_id: str
    event_type: CoordinationEventType
    from_agent: str
    to_agent: Optional[str]
    from_agent_context: Dict[str, Any]
    to_agent_context: Optional[Dict[str, Any]]
    task_context: Dict[str, Any]
    intermediate_results: Dict[str, Any]
    priority: int = 5  # 1-10, higher is more urgent
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "from_agent_context": self.from_agent_context,
            "to_agent_context": self.to_agent_context,
            "task_context": self.task_context,
            "intermediate_results": self.intermediate_results,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CoordinationResponse:
    """Response to a coordination event"""

    response_id: str
    event_id: str
    response_type: str
    recommended_actions: List[str]
    resource_allocations: Dict[str, Any]
    success_probability: float
    estimated_completion_time: float

    @classmethod
    def from_claude_response(
        cls, response: str, event_id: str
    ) -> "CoordinationResponse":
        """Create coordination response from Claude response"""
        try:
            data = json.loads(response)
            return cls(
                response_id=str(uuid.uuid4()),
                event_id=event_id,
                response_type=data.get("response_type", "default"),
                recommended_actions=data.get("recommended_actions", []),
                resource_allocations=data.get("resource_allocations", {}),
                success_probability=data.get("success_probability", 0.5),
                estimated_completion_time=data.get("estimated_completion_time", 1.0),
            )
        except (json.JSONDecodeError, KeyError):
            return cls._create_fallback_response(event_id)

    @classmethod
    def _create_fallback_response(cls, event_id: str) -> "CoordinationResponse":
        """Create fallback coordination response"""
        return cls(
            response_id=str(uuid.uuid4()),
            event_id=event_id,
            response_type="fallback",
            recommended_actions=["manual_review_required"],
            resource_allocations={},
            success_probability=0.3,
            estimated_completion_time=2.0,
        )


@dataclass
class SwarmExecution:
    """Represents a swarm execution instance"""

    execution_id: str
    workflow_def: EnhancedWorkflowDefinition
    agents: Dict[str, SwarmAgent]
    communication_network: "CommunicationNetwork"
    coordinator: "IntelligentSwarmCoordinator"
    execution_state: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CommunicationNetwork:
    """Manages communication between agents in the swarm"""

    def __init__(self, agents: Dict[str, SwarmAgent]):
        self.agents = agents
        self.message_queues: Dict[str, asyncio.Queue] = {}
        self.broadcast_queue: asyncio.Queue = asyncio.Queue()
        self._setup_communication_channels()

    def _setup_communication_channels(self):
        """Setup communication channels for all agents"""
        for agent_id in self.agents:
            self.message_queues[agent_id] = asyncio.Queue()

    async def send_message(
        self, from_agent: str, to_agent: str, message: Dict[str, Any]
    ):
        """Send message between agents"""
        if to_agent in self.message_queues:
            await self.message_queues[to_agent].put(
                {
                    "from": from_agent,
                    "to": to_agent,
                    "message": message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    async def broadcast_message(self, from_agent: str, message: Dict[str, Any]):
        """Broadcast message to all agents"""
        await self.broadcast_queue.put(
            {
                "from": from_agent,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def get_messages(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get pending messages for an agent"""
        messages = []

        # Get direct messages
        while not self.message_queues[agent_id].empty():
            try:
                message = self.message_queues[agent_id].get_nowait()
                messages.append(message)
            except asyncio.QueueEmpty:
                break

        # Get broadcast messages (simplified - in practice would need filtering)
        broadcast_messages = []
        temp_queue = asyncio.Queue()

        while not self.broadcast_queue.empty():
            try:
                message = self.broadcast_queue.get_nowait()
                if message["from"] != agent_id:  # Don't send own broadcasts back
                    broadcast_messages.append(message)
                temp_queue.put_nowait(message)
            except asyncio.QueueEmpty:
                break

        # Put broadcast messages back
        while not temp_queue.empty():
            try:
                message = temp_queue.get_nowait()
                self.broadcast_queue.put_nowait(message)
            except asyncio.QueueEmpty:
                break

        messages.extend(broadcast_messages)
        return messages


class DynamicAgentPool:
    """Manages a pool of dynamic agents"""

    def __init__(self):
        self.available_agents: Dict[str, SwarmAgent] = {}
        self.agent_types: Dict[AgentSpecialization, int] = {}
        self.performance_tracker = AgentPerformanceTracker()

    async def create_agent(self, configuration: AgentConfiguration) -> SwarmAgent:
        """Create a new agent with the given configuration"""
        agent = SwarmAgent(
            agent_id=configuration.agent_id,
            configuration=configuration,
            current_state=AgentState.IDLE,
            last_activity=datetime.now(timezone.utc),
        )

        self.available_agents[agent.agent_id] = agent
        return agent

    async def get_best_agent_for_task(
        self, task_requirements: Dict[str, Any]
    ) -> Optional[SwarmAgent]:
        """Find the best available agent for a task"""
        candidates = []

        for agent in self.available_agents.values():
            if agent.can_accept_task(task_requirements):
                score = self._calculate_agent_suitability_score(
                    agent, task_requirements
                )
                candidates.append((agent, score))

        if not candidates:
            return None

        # Return agent with highest suitability score
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _calculate_agent_suitability_score(
        self, agent: SwarmAgent, task_requirements: Dict[str, Any]
    ) -> float:
        """Calculate how suitable an agent is for a task"""
        score = 0.0

        # Capability match score
        required_capabilities = task_requirements.get("required_capabilities", [])
        for req_cap in required_capabilities:
            capability_score = agent.get_capability_score(req_cap)
            score += capability_score

        # Workload penalty
        workload_penalty = agent.current_workload * 0.1
        score -= workload_penalty

        # Performance bonus
        performance_bonus = agent.performance_metrics.get("success_rate", 0.5) * 0.2
        score += performance_bonus

        return score

    def get_available_types(self) -> List[str]:
        """Get available agent specialization types"""
        return [spec.value for spec in AgentSpecialization]


class AgentPerformanceTracker:
    """Tracks agent performance for optimization"""

    def __init__(self):
        self.performance_data: Dict[str, Dict[str, Any]] = {}

    async def get_performance_patterns(self) -> Dict[str, Any]:
        """Get historical performance patterns"""
        # TODO: Implement performance pattern analysis
        return {}

    async def record_agent_performance(self, agent_id: str, metrics: Dict[str, Any]):
        """Record performance metrics for an agent"""
        if agent_id not in self.performance_data:
            self.performance_data[agent_id] = {
                "total_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "average_completion_time": 0.0,
                "quality_scores": [],
            }

        data = self.performance_data[agent_id]
        data["total_tasks"] += 1

        if metrics.get("success", False):
            data["completed_tasks"] += 1
        else:
            data["failed_tasks"] += 1

        if "completion_time" in metrics:
            # Update average completion time
            old_avg = data["average_completion_time"]
            old_count = data["total_tasks"] - 1
            new_time = metrics["completion_time"]
            data["average_completion_time"] = (old_avg * old_count + new_time) / data[
                "total_tasks"
            ]

        if "quality_score" in metrics:
            data["quality_scores"].append(metrics["quality_score"])
            # Keep only last 100 scores
            if len(data["quality_scores"]) > 100:
                data["quality_scores"] = data["quality_scores"][-100:]


class AIConflictResolver:
    """AI-powered conflict resolution for agent coordination"""

    def __init__(self, claude_agent: ClaudeAgentWrapper):
        self.claude_agent = claude_agent

    async def resolve_conflict(self, event: CoordinationEvent) -> CoordinationResponse:
        """Resolve conflicts between agents using AI"""

        conflict_prompt = f"""
        Resolve a conflict between agents in a multi-agent swarm:
        
        Conflict Details: {json.dumps(event.to_dict(), indent=2)}
        
        Analyze the conflict and provide resolution strategy:
        1. What is the root cause of the conflict?
        2. What are the possible resolution approaches?
        3. Which approach minimizes disruption to other agents?
        4. What resources need to be reallocated?
        5. How can similar conflicts be prevented?
        
        Provide resolution in JSON format with:
        - response_type: type of resolution strategy
        - recommended_actions: specific actions to take
        - resource_allocations: any resource changes needed
        - success_probability: likelihood of success (0-1)
        - estimated_completion_time: time to resolve (hours)
        - prevention_measures: steps to prevent similar conflicts
        
        Focus on maintaining swarm efficiency and agent collaboration.
        """

        result = await self.claude_agent.execute_task(
            {"type": "conflict_resolution", "prompt": conflict_prompt}
        )

        return CoordinationResponse.from_claude_response(
            result["result"], event.event_id
        )


class IntelligentSwarmCoordinator:
    """
    AI-powered orchestration of multi-agent collaboration.

    Handles dynamic agent creation, task assignment, conflict resolution,
    and real-time optimization of swarm execution.
    """

    def __init__(self, claude_agent: ClaudeAgentWrapper, agent_pool: DynamicAgentPool):
        self.claude_agent = claude_agent
        self.agent_pool = agent_pool
        self.communication_hub = None  # Set during execution
        self.conflict_resolver = AIConflictResolver(claude_agent)
        self.performance_tracker = AgentPerformanceTracker()
        self.active_executions: Dict[str, SwarmExecution] = {}
        self.coordination_events: asyncio.Queue = asyncio.Queue()
        self.logger = structured_logger.bind(component="swarm_coordinator")

    async def orchestrate_swarm_execution(
        self,
        workflow_def: EnhancedWorkflowDefinition,
        execution_context: Dict[str, Any],
    ) -> SwarmExecution:
        """Orchestrate intelligent multi-agent execution"""

        execution_id = str(uuid.uuid4())
        self.logger.info(
            "Starting swarm orchestration",
            execution_id=execution_id,
            workflow=workflow_def.name,
        )

        try:
            # Generate optimal agent configuration using Claude
            agent_config = await self._generate_intelligent_agent_config(
                workflow_def, execution_context
            )

            # Create specialized agents dynamically
            agents = await self._create_specialized_agents(agent_config)

            # Establish communication network
            communication_network = CommunicationNetwork(agents)
            self.communication_hub = communication_network

            # Create swarm execution
            execution = SwarmExecution(
                execution_id=execution_id,
                workflow_def=workflow_def,
                agents=agents,
                communication_network=communication_network,
                coordinator=self,
            )

            self.active_executions[execution_id] = execution

            # Begin intelligent coordination
            asyncio.create_task(self._coordinate_execution(execution))

            self.logger.info(
                "Swarm orchestration initiated",
                execution_id=execution_id,
                agent_count=len(agents),
            )

            return execution

        except Exception as e:
            self.logger.error(
                "Swarm orchestration failed",
                execution_id=execution_id,
                error=str(e),
            )
            raise

    async def handle_inter_agent_coordination(
        self, coordination_event: CoordinationEvent
    ) -> CoordinationResponse:
        """Intelligent handling of agent coordination needs"""

        self.logger.info(
            "Handling coordination event",
            event_type=coordination_event.event_type.value,
            from_agent=coordination_event.from_agent,
        )

        if coordination_event.event_type == CoordinationEventType.TASK_HANDOFF:
            return await self._handle_intelligent_handoff(coordination_event)
        elif coordination_event.event_type == CoordinationEventType.CONFLICT_RESOLUTION:
            return await self.conflict_resolver.resolve_conflict(coordination_event)
        elif coordination_event.event_type == CoordinationEventType.RESOURCE_CONTENTION:
            return await self._optimize_resource_allocation(coordination_event)
        elif coordination_event.event_type == CoordinationEventType.QUALITY_CONCERN:
            return await self._handle_quality_escalation(coordination_event)
        elif coordination_event.event_type == CoordinationEventType.PERFORMANCE_ISSUE:
            return await self._handle_performance_issue(coordination_event)
        else:
            return await self._handle_generic_coordination(coordination_event)

    async def _generate_intelligent_agent_config(
        self, workflow_def: EnhancedWorkflowDefinition, context: Dict[str, Any]
    ) -> Dict[str, AgentConfiguration]:
        """Use Claude to generate optimal agent specializations"""

        config_prompt = f"""
        Design optimal agent specializations for this workflow:
        
        Workflow Definition: {json.dumps(workflow_def.to_dict(), indent=2)}
        Execution Context: {json.dumps(context, indent=2)}
        Available Agent Types: {self.agent_pool.get_available_types()}
        Past Performance Data: {await self.performance_tracker.get_performance_patterns()}
        
        For each workflow phase, determine:
        1. What specific expertise is needed?
        2. Which agents should work in parallel vs sequentially?
        3. What tools should each agent have access to?
        4. How should agents collaborate and share context?
        5. What are the handoff points between agents?
        6. How should conflicts be resolved?
        7. What performance targets should be set?
        
        Design agent specializations that:
        - Minimize overlap and maximize complementary skills
        - Enable efficient parallel execution
        - Include built-in quality checks and peer review
        - Have clear communication protocols
        - Can adapt based on intermediate results
        
        Return structured agent configuration in JSON format with:
        - agents: array of agent configurations
        - collaboration_matrix: how agents should interact
        - resource_allocation: resource distribution strategy
        - performance_targets: expected performance metrics
        
        For each agent include:
        - specialization: agent specialization type
        - capabilities: array of capabilities with proficiency levels
        - resource_limits: computational resource limits
        - communication_preferences: how agent prefers to communicate
        - collaboration_rules: rules for working with other agents
        - performance_targets: expected performance metrics
        - tools_access: tools this agent should have access to
        """

        result = await self.claude_agent.execute_task(
            {"type": "agent_configuration", "prompt": config_prompt},
            shared_memory={
                "workflow": workflow_def.to_dict(),
                "context": context,
            },
        )

        return await self._parse_agent_config_response(result["result"])

    async def _parse_agent_config_response(
        self, response: str
    ) -> Dict[str, AgentConfiguration]:
        """Parse Claude's agent configuration response"""
        try:
            data = json.loads(response)
            agent_configs = {}

            for agent_data in data.get("agents", []):
                agent_id = agent_data.get("agent_id", str(uuid.uuid4()))
                config = AgentConfiguration.from_claude_response(
                    json.dumps(agent_data), agent_id
                )
                agent_configs[agent_id] = config

            return agent_configs

        except (json.JSONDecodeError, KeyError):
            # Return default configuration
            return self._create_default_agent_configs()

    def _create_default_agent_configs(self) -> Dict[str, AgentConfiguration]:
        """Create default agent configurations as fallback"""
        configs = {}

        # Create a diverse set of default agents
        specializations = [
            AgentSpecialization.REQUIREMENTS_ANALYST,
            AgentSpecialization.SOLUTION_ARCHITECT,
            AgentSpecialization.QUALITY_ASSURANCE,
        ]

        for spec in specializations:
            agent_id = f"agent_{spec.value}_{uuid.uuid4().hex[:8]}"
            config = AgentConfiguration._create_default_config(agent_id)
            config.specialization = spec
            configs[agent_id] = config

        return configs

    async def _create_specialized_agents(
        self, agent_configs: Dict[str, AgentConfiguration]
    ) -> Dict[str, SwarmAgent]:
        """Create specialized agents based on configurations"""
        agents = {}

        for agent_id, config in agent_configs.items():
            agent = await self.agent_pool.create_agent(config)
            agents[agent_id] = agent

        return agents

    async def _coordinate_execution(self, execution: SwarmExecution):
        """Coordinate the execution of a swarm"""
        self.logger.info(
            "Starting execution coordination",
            execution_id=execution.execution_id,
        )

        try:
            # Main coordination loop
            while not self._is_execution_complete(execution):
                # Process coordination events
                await self._process_coordination_events()

                # Monitor agent states
                await self._monitor_agent_states(execution)

                # Optimize resource allocation
                await self._optimize_execution(execution)

                # Brief pause before next iteration
                await asyncio.sleep(1.0)

            self.logger.info(
                "Execution coordination completed",
                execution_id=execution.execution_id,
            )

        except Exception as e:
            self.logger.error(
                "Execution coordination failed",
                execution_id=execution.execution_id,
                error=str(e),
            )
        finally:
            # Cleanup
            if execution.execution_id in self.active_executions:
                del self.active_executions[execution.execution_id]

    async def _handle_intelligent_handoff(
        self, event: CoordinationEvent
    ) -> CoordinationResponse:
        """AI-powered intelligent task handoff between agents"""

        handoff_prompt = f"""
        Two agents need to coordinate a task handoff:
        
        From Agent: {event.from_agent} (context: {json.dumps(event.from_agent_context, indent=2)})
        To Agent: {event.to_agent} (context: {json.dumps(event.to_agent_context, indent=2)})
        Task Context: {json.dumps(event.task_context, indent=2)}
        Current Results: {json.dumps(event.intermediate_results, indent=2)}
        
        Determine the optimal handoff strategy:
        1. What context needs to be transferred?
        2. What intermediate results are most valuable?
        3. Are there any quality checks needed before handoff?
        4. What should the receiving agent focus on?
        5. Are there any risks or considerations?
        6. How can continuity be maintained?
        
        Design a handoff plan in JSON format with:
        - response_type: handoff strategy type
        - recommended_actions: specific handoff steps
        - context_transfer: what context to transfer
        - quality_checks: validation steps before handoff
        - success_probability: likelihood of successful handoff
        - estimated_completion_time: time to complete handoff
        
        Focus on maximizing continuity and quality while minimizing delay.
        """

        result = await self.claude_agent.execute_task(
            {"type": "handoff_optimization", "prompt": handoff_prompt},
            shared_memory={"handoff_context": event.to_dict()},
        )

        return CoordinationResponse.from_claude_response(
            result["result"], event.event_id
        )

    async def _optimize_resource_allocation(
        self, event: CoordinationEvent
    ) -> CoordinationResponse:
        """Optimize resource allocation for resource contention"""
        resource_prompt = f"""
        Resolve resource contention between agents in a multi-agent swarm:
        
        Resource Contention Event: {json.dumps(event.to_dict(), indent=2)}
        
        Analyze the resource contention and provide optimal allocation strategy:
        1. What specific resources are being contested?
        2. What are the priority levels of the competing agents/tasks?
        3. How can resources be fairly distributed while maximizing overall efficiency?
        4. Are there alternative resources that can be substituted?
        5. Should any tasks be queued, prioritized, or redistributed?
        6. What are the performance implications of different allocation strategies?
        
        Provide resource allocation strategy in JSON format with:
        - response_type: allocation strategy type (prioritize/queue/redistribute/scale)
        - recommended_actions: specific allocation actions to take
        - resource_allocations: detailed resource distribution plan
        - priority_adjustments: any priority changes needed
        - alternative_resources: suggested resource substitutions
        - success_probability: likelihood of resolving contention (0-1)
        - estimated_completion_time: time to implement allocation (hours)
        - monitoring_requirements: metrics to track allocation effectiveness
        
        Focus on fairness, efficiency, and minimizing disruption to overall swarm performance.
        """

        result = await self.claude_agent.execute_task(
            {"type": "resource_allocation", "prompt": resource_prompt},
            shared_memory={"resource_context": event.to_dict()},
        )

        return CoordinationResponse.from_claude_response(
            result["result"], event.event_id
        )

    async def _handle_quality_escalation(
        self, event: CoordinationEvent
    ) -> CoordinationResponse:
        """Handle quality concerns in agent execution"""
        quality_prompt = f"""
        Address a quality concern escalation in multi-agent execution:
        
        Quality Escalation Event: {json.dumps(event.to_dict(), indent=2)}
        
        Analyze the quality concern and provide escalation response:
        1. What specific quality issues have been identified?
        2. How severe is the quality concern (low/medium/high/critical)?
        3. What is the root cause of the quality degradation?
        4. Which agents or processes need immediate attention?
        5. Should work be paused, reviewed, or redirected?
        6. What quality assurance measures should be implemented?
        7. How can similar quality issues be prevented in the future?
        
        Provide quality escalation response in JSON format with:
        - response_type: escalation strategy (review/pause/redirect/enhance_qa)
        - recommended_actions: immediate quality improvement actions
        - quality_gates: checkpoints to implement going forward
        - resource_allocations: any additional QA resources needed
        - review_requirements: peer review or expert consultation needed
        - prevention_measures: steps to prevent similar quality issues
        - success_probability: likelihood of quality recovery (0-1)
        - estimated_completion_time: time to address quality issues (hours)
        
        Prioritize delivering high-quality results while maintaining swarm momentum.
        """

        result = await self.claude_agent.execute_task(
            {"type": "quality_escalation", "prompt": quality_prompt},
            shared_memory={"quality_context": event.to_dict()},
        )

        return CoordinationResponse.from_claude_response(
            result["result"], event.event_id
        )

    async def _handle_performance_issue(
        self, event: CoordinationEvent
    ) -> CoordinationResponse:
        """Handle performance issues in agent execution"""
        performance_prompt = f"""
        Address a performance issue in multi-agent swarm execution:
        
        Performance Issue Event: {json.dumps(event.to_dict(), indent=2)}
        
        Analyze the performance issue and provide optimization response:
        1. What specific performance degradation has been observed?
        2. Which agents or components are causing the bottleneck?
        3. Is this a resource constraint, algorithmic inefficiency, or coordination issue?
        4. What are the performance metrics indicating (response time, throughput, etc.)?
        5. Should workload be redistributed or agents be scaled?
        6. Are there immediate optimizations that can be applied?
        7. What monitoring should be enhanced to prevent future issues?
        
        Provide performance optimization response in JSON format with:
        - response_type: optimization strategy (scale/redistribute/optimize/throttle)
        - recommended_actions: immediate performance improvement actions
        - resource_allocations: resource adjustments needed
        - workload_redistribution: how to rebalance agent workloads
        - optimization_targets: specific performance metrics to improve
        - monitoring_enhancements: additional monitoring to implement
        - success_probability: likelihood of performance recovery (0-1)
        - estimated_completion_time: time to implement optimizations (hours)
        
        Focus on restoring optimal performance while maintaining result quality.
        """

        result = await self.claude_agent.execute_task(
            {"type": "performance_optimization", "prompt": performance_prompt},
            shared_memory={"performance_context": event.to_dict()},
        )

        return CoordinationResponse.from_claude_response(
            result["result"], event.event_id
        )

    async def _handle_generic_coordination(
        self, event: CoordinationEvent
    ) -> CoordinationResponse:
        """Handle generic coordination events"""
        generic_prompt = f"""
        Handle a general coordination request in multi-agent swarm execution:
        
        Coordination Event: {json.dumps(event.to_dict(), indent=2)}
        
        Analyze this coordination requirement and provide appropriate response:
        1. What type of coordination is being requested?
        2. Which agents need to be involved in this coordination?
        3. What is the urgency and priority of this coordination need?
        4. Are there dependencies or prerequisites that must be met?
        5. What communication or synchronization is required?
        6. How should the coordination be monitored and validated?
        7. What are the success criteria for this coordination?
        
        Provide coordination response in JSON format with:
        - response_type: coordination strategy (sync/async/broadcast/peer_review)
        - recommended_actions: specific coordination steps to take
        - agent_assignments: which agents should handle what aspects
        - communication_plan: how agents should communicate and synchronize
        - dependencies: any prerequisites or dependencies to manage
        - validation_criteria: how to verify successful coordination
        - success_probability: likelihood of successful coordination (0-1)
        - estimated_completion_time: time to complete coordination (hours)
        
        Focus on efficient coordination that enhances overall swarm effectiveness.
        """

        result = await self.claude_agent.execute_task(
            {"type": "generic_coordination", "prompt": generic_prompt},
            shared_memory={"coordination_context": event.to_dict()},
        )

        return CoordinationResponse.from_claude_response(
            result["result"], event.event_id
        )

    async def _process_coordination_events(self):
        """Process pending coordination events"""
        while not self.coordination_events.empty():
            try:
                event = self.coordination_events.get_nowait()
                response = await self.handle_inter_agent_coordination(event)

                # Apply coordination response
                await self._apply_coordination_response(event, response)

            except asyncio.QueueEmpty:
                break
            except Exception as e:
                self.logger.error(
                    "Error processing coordination event",
                    event_id=getattr(event, "event_id", "unknown"),
                    error=str(e),
                )

    async def _apply_coordination_response(
        self, event: CoordinationEvent, response: CoordinationResponse
    ):
        """Apply the coordination response to the swarm execution"""
        try:
            # Log coordination response
            self.logger.info(
                "Applying coordination response",
                event_id=event.event_id,
                response_type=response.response_type,
            )

            # Execute recommended actions
            for action in response.recommended_actions:
                await self._execute_coordination_action(action, event, response)

            # Apply resource allocations
            if response.resource_allocations:
                await self._apply_resource_allocations(
                    response.resource_allocations, event
                )

            # Update agent states based on coordination outcome
            await self._update_agents_post_coordination(event, response)

        except Exception as e:
            self.logger.error(
                "Failed to apply coordination response",
                event_id=event.event_id,
                error=str(e),
            )

    async def _execute_coordination_action(
        self,
        action: str,
        event: CoordinationEvent,
        response: CoordinationResponse,
    ):
        """Execute a specific coordination action"""
        # Parse and execute coordination actions
        if action.startswith("reassign_task"):
            await self._reassign_task_between_agents(action, event)
        elif action.startswith("pause_agent"):
            await self._pause_agent_execution(action, event)
        elif action.startswith("scale_resources"):
            await self._scale_agent_resources(action, event)
        elif action.startswith("peer_review"):
            await self._initiate_peer_review(action, event)
        elif action.startswith("broadcast_message"):
            await self._broadcast_coordination_message(action, event)
        else:
            self.logger.debug(f"Generic coordination action: {action}")

    async def _apply_resource_allocations(
        self, allocations: Dict[str, Any], event: CoordinationEvent
    ):
        """Apply resource allocation changes"""
        for resource_type, allocation in allocations.items():
            if resource_type == "cpu_allocation":
                await self._adjust_cpu_allocation(allocation, event)
            elif resource_type == "memory_allocation":
                await self._adjust_memory_allocation(allocation, event)
            elif resource_type == "priority_adjustment":
                await self._adjust_task_priorities(allocation, event)

    async def _reassign_task_between_agents(
        self, action: str, event: CoordinationEvent
    ):
        """Reassign task from one agent to another"""
        # Implementation for task reassignment
        self.logger.info(f"Reassigning task based on coordination: {action}")

    async def _pause_agent_execution(self, action: str, event: CoordinationEvent):
        """Pause agent execution for review or resource management"""
        self.logger.info(f"Pausing agent execution: {action}")

    async def _scale_agent_resources(self, action: str, event: CoordinationEvent):
        """Scale agent resources up or down"""
        self.logger.info(f"Scaling agent resources: {action}")

    async def _initiate_peer_review(self, action: str, event: CoordinationEvent):
        """Initiate peer review process between agents"""
        self.logger.info(f"Initiating peer review: {action}")

    async def _broadcast_coordination_message(
        self, action: str, event: CoordinationEvent
    ):
        """Broadcast coordination message to relevant agents"""
        if self.communication_hub:
            message = {
                "type": "coordination_update",
                "event_id": event.event_id,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self.communication_hub.broadcast_message("coordinator", message)

    async def _adjust_cpu_allocation(self, allocation: Any, event: CoordinationEvent):
        """Adjust CPU allocation for agents"""
        self.logger.debug(f"Adjusting CPU allocation: {allocation}")

    async def _adjust_memory_allocation(
        self, allocation: Any, event: CoordinationEvent
    ):
        """Adjust memory allocation for agents"""
        self.logger.debug(f"Adjusting memory allocation: {allocation}")

    async def _adjust_task_priorities(self, allocation: Any, event: CoordinationEvent):
        """Adjust task priorities based on coordination needs"""
        self.logger.debug(f"Adjusting task priorities: {allocation}")

    async def _update_agents_post_coordination(
        self, event: CoordinationEvent, response: CoordinationResponse
    ):
        """Update agent states after coordination"""
        # Update agent configurations and states based on coordination outcome
        if event.from_agent in self.active_executions:
            execution = list(self.active_executions.values())[
                0
            ]  # Get first execution for now
            if event.from_agent in execution.agents:
                agent = execution.agents[event.from_agent]
                # Update agent collaboration history
                agent.collaboration_history.append(
                    {
                        "event_id": event.event_id,
                        "event_type": event.event_type.value,
                        "response_type": response.response_type,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "success_probability": response.success_probability,
                    }
                )

    async def _monitor_agent_states(self, execution: SwarmExecution):
        """Monitor and update agent states"""
        current_time = datetime.now(timezone.utc)

        for agent in execution.agents.values():
            # Update last activity
            agent.last_activity = current_time

            # Check for timeouts or issues
            await self._check_agent_health(agent, execution)
            await self._update_agent_performance_metrics(agent)
            await self._detect_agent_issues(agent, execution)

    async def _check_agent_health(self, agent: SwarmAgent, execution: SwarmExecution):
        """Check individual agent health and responsiveness"""
        current_time = datetime.now(timezone.utc)

        # Check for timeout (no activity in last 5 minutes)
        if agent.last_activity:
            inactive_duration = (current_time - agent.last_activity).total_seconds()
            if inactive_duration > 300:  # 5 minutes
                self.logger.warning(
                    "Agent inactive for extended period",
                    agent_id=agent.agent_id,
                    inactive_seconds=inactive_duration,
                )

                # Create coordination event for timeout
                timeout_event = CoordinationEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=CoordinationEventType.PERFORMANCE_ISSUE,
                    from_agent=agent.agent_id,
                    to_agent=None,
                    from_agent_context={
                        "issue": "timeout",
                        "inactive_seconds": inactive_duration,
                    },
                    to_agent_context=None,
                    task_context={"execution_id": execution.execution_id},
                    intermediate_results={
                        "performance_metrics": agent.performance_metrics
                    },
                    priority=8,
                )
                await self.coordination_events.put(timeout_event)

        # Check workload balance
        if agent.current_workload > agent.configuration.max_concurrent_tasks:
            self.logger.warning(
                "Agent workload exceeds capacity",
                agent_id=agent.agent_id,
                current_workload=agent.current_workload,
                max_capacity=agent.configuration.max_concurrent_tasks,
            )

    async def _update_agent_performance_metrics(self, agent: SwarmAgent):
        """Update agent performance metrics"""
        # Calculate current performance indicators
        success_rate = agent.performance_metrics.get("success_rate", 0.0)
        completion_time = agent.performance_metrics.get("avg_completion_time", 0.0)

        # Update performance tracking
        if hasattr(self, "performance_tracker"):
            await self.performance_tracker.record_agent_performance(
                agent.agent_id,
                {
                    "success_rate": success_rate,
                    "completion_time": completion_time,
                    "workload": agent.current_workload,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

    async def _detect_agent_issues(self, agent: SwarmAgent, execution: SwarmExecution):
        """Detect potential issues with agent performance or state"""
        issues_detected = []

        # Check for performance degradation
        success_rate = agent.performance_metrics.get("success_rate", 1.0)
        if success_rate < 0.8:
            issues_detected.append(
                {
                    "type": "low_success_rate",
                    "severity": "high" if success_rate < 0.6 else "medium",
                    "value": success_rate,
                }
            )

        # Check for excessive completion times
        avg_completion_time = agent.performance_metrics.get("avg_completion_time", 0.0)
        if avg_completion_time > 300:  # 5 minutes
            issues_detected.append(
                {
                    "type": "slow_completion",
                    "severity": "medium",
                    "value": avg_completion_time,
                }
            )

        # Check for blocked state
        if agent.current_state == AgentState.BLOCKED:
            issues_detected.append(
                {
                    "type": "blocked_state",
                    "severity": "high",
                    "duration": (
                        datetime.now(timezone.utc) - agent.last_activity
                    ).total_seconds(),
                }
            )

        # Create coordination events for detected issues
        for issue in issues_detected:
            if issue["severity"] in ["high", "critical"]:
                issue_event = CoordinationEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=CoordinationEventType.PERFORMANCE_ISSUE,
                    from_agent=agent.agent_id,
                    to_agent=None,
                    from_agent_context={"agent_state": agent.current_state.value},
                    to_agent_context=None,
                    task_context={"execution_id": execution.execution_id},
                    intermediate_results={
                        "issue_details": issue,
                        "performance_metrics": agent.performance_metrics,
                    },
                    priority=9 if issue["severity"] == "critical" else 7,
                )
                await self.coordination_events.put(issue_event)

    async def _optimize_execution(self, execution: SwarmExecution):
        """Optimize execution in real-time"""
        try:
            # Analyze current execution state
            execution_metrics = await self._calculate_execution_metrics(execution)

            # Identify optimization opportunities
            optimizations = await self._identify_execution_optimizations(
                execution, execution_metrics
            )

            # Apply optimizations
            for optimization in optimizations:
                await self._apply_execution_optimization(execution, optimization)

            # Update execution state
            execution.performance_metrics.update(execution_metrics)
            execution.execution_state["last_optimization"] = datetime.now(
                timezone.utc
            ).isoformat()

        except Exception as e:
            self.logger.error(
                "Failed to optimize execution",
                execution_id=execution.execution_id,
                error=str(e),
            )

    async def _calculate_execution_metrics(
        self, execution: SwarmExecution
    ) -> Dict[str, Any]:
        """Calculate current execution performance metrics"""
        metrics = {
            "total_agents": len(execution.agents),
            "active_agents": len(
                [
                    a
                    for a in execution.agents.values()
                    if a.current_state == AgentState.WORKING
                ]
            ),
            "idle_agents": len(
                [
                    a
                    for a in execution.agents.values()
                    if a.current_state == AgentState.IDLE
                ]
            ),
            "blocked_agents": len(
                [
                    a
                    for a in execution.agents.values()
                    if a.current_state == AgentState.BLOCKED
                ]
            ),
            "average_workload": (
                sum(a.current_workload for a in execution.agents.values())
                / len(execution.agents)
                if execution.agents
                else 0
            ),
            "total_workload": sum(
                a.current_workload for a in execution.agents.values()
            ),
            "execution_duration": (
                datetime.now(timezone.utc) - execution.started_at
            ).total_seconds(),
            "coordination_events_processed": len(
                [e for e in self.coordination_events._queue if hasattr(e, "event_id")]
            ),
        }

        # Calculate performance scores
        metrics["efficiency_score"] = self._calculate_efficiency_score(
            execution, metrics
        )
        metrics["coordination_score"] = self._calculate_coordination_score(
            execution, metrics
        )

        return metrics

    def _calculate_efficiency_score(
        self, execution: SwarmExecution, metrics: Dict[str, Any]
    ) -> float:
        """Calculate execution efficiency score (0-100)"""
        # Base efficiency on agent utilization and progress
        utilization_score = min(
            100, (metrics["average_workload"] / 3.0) * 100
        )  # Assume max 3 tasks per agent

        # Penalty for blocked agents
        blocked_penalty = (
            (metrics["blocked_agents"] / metrics["total_agents"]) * 30
            if metrics["total_agents"] > 0
            else 0
        )

        # Bonus for balanced workload
        workload_variance = self._calculate_workload_variance(execution)
        balance_bonus = max(0, 20 - workload_variance)

        efficiency = max(
            0, min(100, utilization_score - blocked_penalty + balance_bonus)
        )
        return efficiency

    def _calculate_coordination_score(
        self, execution: SwarmExecution, metrics: Dict[str, Any]
    ) -> float:
        """Calculate coordination effectiveness score (0-100)"""
        # Score based on successful coordination events and agent collaboration
        base_score = 80.0  # Start with good score

        # Analyze coordination history
        total_coordination_events = 0
        successful_events = 0

        for agent in execution.agents.values():
            for event in agent.collaboration_history:
                total_coordination_events += 1
                if event.get("success_probability", 0) > 0.7:
                    successful_events += 1

        if total_coordination_events > 0:
            success_rate = successful_events / total_coordination_events
            coordination_score = base_score * success_rate
        else:
            coordination_score = base_score

        return min(100, coordination_score)

    def _calculate_workload_variance(self, execution: SwarmExecution) -> float:
        """Calculate variance in agent workloads"""
        if not execution.agents:
            return 0.0

        workloads = [agent.current_workload for agent in execution.agents.values()]
        mean_workload = sum(workloads) / len(workloads)
        variance = sum((w - mean_workload) ** 2 for w in workloads) / len(workloads)
        return variance

    async def _identify_execution_optimizations(
        self, execution: SwarmExecution, metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify potential optimizations for execution"""
        optimizations = []

        # Check for load balancing opportunities
        if metrics["efficiency_score"] < 70:
            workload_variance = self._calculate_workload_variance(execution)
            if workload_variance > 1.0:
                optimizations.append(
                    {
                        "type": "load_balancing",
                        "priority": "high",
                        "description": "Rebalance workload across agents",
                        "target_variance": 0.5,
                    }
                )

        # Check for idle agent utilization
        if metrics["idle_agents"] > 0 and metrics["total_workload"] > 0:
            optimizations.append(
                {
                    "type": "idle_utilization",
                    "priority": "medium",
                    "description": "Assign work to idle agents",
                    "idle_agents": metrics["idle_agents"],
                }
            )

        # Check for blocked agent intervention
        if metrics["blocked_agents"] > 0:
            optimizations.append(
                {
                    "type": "unblock_agents",
                    "priority": "high",
                    "description": "Resolve blocked agent states",
                    "blocked_agents": metrics["blocked_agents"],
                }
            )

        # Check for coordination improvements
        if metrics["coordination_score"] < 60:
            optimizations.append(
                {
                    "type": "improve_coordination",
                    "priority": "medium",
                    "description": "Enhance agent coordination mechanisms",
                    "current_score": metrics["coordination_score"],
                }
            )

        return optimizations

    async def _apply_execution_optimization(
        self, execution: SwarmExecution, optimization: Dict[str, Any]
    ):
        """Apply a specific execution optimization"""
        optimization_type = optimization["type"]

        if optimization_type == "load_balancing":
            await self._rebalance_agent_workloads(execution)
        elif optimization_type == "idle_utilization":
            await self._assign_work_to_idle_agents(execution)
        elif optimization_type == "unblock_agents":
            await self._resolve_blocked_agents(execution)
        elif optimization_type == "improve_coordination":
            await self._enhance_coordination_mechanisms(execution)

        self.logger.info(
            "Applied execution optimization",
            execution_id=execution.execution_id,
            optimization_type=optimization_type,
            priority=optimization["priority"],
        )

    async def _rebalance_agent_workloads(self, execution: SwarmExecution):
        """Rebalance workloads across agents"""
        # Find overloaded and underloaded agents
        overloaded = [a for a in execution.agents.values() if a.current_workload > 2]
        underloaded = [a for a in execution.agents.values() if a.current_workload < 1]

        # Create coordination events for workload redistribution
        for overloaded_agent in overloaded:
            if underloaded:
                target_agent = underloaded[0]

                rebalance_event = CoordinationEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=CoordinationEventType.TASK_HANDOFF,
                    from_agent=overloaded_agent.agent_id,
                    to_agent=target_agent.agent_id,
                    from_agent_context={"workload": overloaded_agent.current_workload},
                    to_agent_context={"workload": target_agent.current_workload},
                    task_context={"optimization": "load_balancing"},
                    intermediate_results={},
                    priority=6,
                )
                await self.coordination_events.put(rebalance_event)

    async def _assign_work_to_idle_agents(self, execution: SwarmExecution):
        """Assign available work to idle agents"""
        idle_agents = [
            a for a in execution.agents.values() if a.current_state == AgentState.IDLE
        ]

        for idle_agent in idle_agents:
            # Create collaboration request
            work_request_event = CoordinationEvent(
                event_id=str(uuid.uuid4()),
                event_type=CoordinationEventType.COLLABORATION_REQUEST,
                from_agent=idle_agent.agent_id,
                to_agent=None,  # Broadcast to find work
                from_agent_context={
                    "state": "idle",
                    "capabilities": [
                        c.capability_name for c in idle_agent.configuration.capabilities
                    ],
                },
                to_agent_context=None,
                task_context={"optimization": "idle_utilization"},
                intermediate_results={},
                priority=5,
            )
            await self.coordination_events.put(work_request_event)

    async def _resolve_blocked_agents(self, execution: SwarmExecution):
        """Resolve blocked agent states"""
        blocked_agents = [
            a
            for a in execution.agents.values()
            if a.current_state == AgentState.BLOCKED
        ]

        for blocked_agent in blocked_agents:
            # Create unblock coordination event
            unblock_event = CoordinationEvent(
                event_id=str(uuid.uuid4()),
                event_type=CoordinationEventType.CONFLICT_RESOLUTION,
                from_agent=blocked_agent.agent_id,
                to_agent=None,
                from_agent_context={
                    "state": "blocked",
                    "issue": "execution_blocked",
                },
                to_agent_context=None,
                task_context={"optimization": "unblock_agents"},
                intermediate_results={
                    "performance_metrics": blocked_agent.performance_metrics
                },
                priority=8,
            )
            await self.coordination_events.put(unblock_event)

    async def _enhance_coordination_mechanisms(self, execution: SwarmExecution):
        """Enhance coordination mechanisms between agents"""
        # Analyze coordination patterns and improve communication
        self.logger.info(
            "Enhancing coordination mechanisms",
            execution_id=execution.execution_id,
            agent_count=len(execution.agents),
        )

    def _is_execution_complete(self, execution: SwarmExecution) -> bool:
        """Check if execution is complete"""
        try:
            # Check if all agents are in completed or idle state
            agent_states = [agent.current_state for agent in execution.agents.values()]

            # Execution is complete if no agents are working or blocked
            working_agents = [
                state
                for state in agent_states
                if state
                in [
                    AgentState.WORKING,
                    AgentState.ASSIGNED,
                    AgentState.BLOCKED,
                ]
            ]

            if len(working_agents) == 0:
                # All agents are idle, completed, failed, or terminated
                self.logger.info(
                    "Execution appears complete - no active agents",
                    execution_id=execution.execution_id,
                    agent_states=[state.value for state in agent_states],
                )
                return True

            # Check execution duration timeout (optional failsafe)
            execution_duration = (
                datetime.now(timezone.utc) - execution.started_at
            ).total_seconds()
            max_execution_time = 3600  # 1 hour default timeout

            if execution_duration > max_execution_time:
                self.logger.warning(
                    "Execution timeout reached",
                    execution_id=execution.execution_id,
                    duration_seconds=execution_duration,
                    max_time=max_execution_time,
                )
                return True

            # Check if workflow definition has completion criteria
            if hasattr(execution.workflow_def, "completion_criteria"):
                completion_criteria = execution.workflow_def.completion_criteria
                if self._check_completion_criteria(execution, completion_criteria):
                    self.logger.info(
                        "Execution completed based on workflow criteria",
                        execution_id=execution.execution_id,
                        criteria=completion_criteria,
                    )
                    return True

            return False

        except Exception as e:
            self.logger.error(
                "Error checking execution completion",
                execution_id=execution.execution_id,
                error=str(e),
            )
            # Default to not complete on error
            return False

    def _check_completion_criteria(
        self, execution: SwarmExecution, criteria: Dict[str, Any]
    ) -> bool:
        """Check if custom completion criteria are met"""
        try:
            # Check various completion criteria types
            if "all_tasks_completed" in criteria:
                # Check if all assigned tasks are completed
                all_completed = all(
                    len(agent.assigned_tasks) == 0
                    or agent.current_state in [AgentState.COMPLETED, AgentState.IDLE]
                    for agent in execution.agents.values()
                )
                if not all_completed:
                    return False

            if "minimum_success_rate" in criteria:
                # Check if success rate threshold is met
                required_rate = criteria["minimum_success_rate"]
                current_rate = self._calculate_current_success_rate(execution)
                if current_rate < required_rate:
                    return False

            if "target_outputs_produced" in criteria:
                # Check if target number of outputs have been produced
                target_outputs = criteria["target_outputs_produced"]
                current_outputs = len(execution.execution_state.get("outputs", []))
                if current_outputs < target_outputs:
                    return False

            if "maximum_errors" in criteria:
                # Check if error count is within acceptable limits
                max_errors = criteria["maximum_errors"]
                current_errors = execution.execution_state.get("error_count", 0)
                if current_errors > max_errors:
                    return True  # Complete due to too many errors

            return True

        except Exception as e:
            self.logger.error(
                "Error checking completion criteria",
                execution_id=execution.execution_id,
                error=str(e),
            )
            return False

    def _calculate_current_success_rate(self, execution: SwarmExecution) -> float:
        """Calculate current overall success rate for the execution"""
        total_tasks = 0
        successful_tasks = 0

        for agent in execution.agents.values():
            completed_tasks = agent.performance_metrics.get("completed_tasks", 0)
            failed_tasks = agent.performance_metrics.get("failed_tasks", 0)

            total_tasks += completed_tasks + failed_tasks
            successful_tasks += completed_tasks

        if total_tasks == 0:
            return 1.0  # No tasks yet, assume success

        return successful_tasks / total_tasks


# Factory function for easy integration
async def create_swarm_coordinator(
    claude_api_key: Optional[str] = None,
) -> IntelligentSwarmCoordinator:
    """Factory function to create configured swarm coordinator"""

    claude_agent = ClaudeAgentWrapper(api_key=claude_api_key)
    agent_pool = DynamicAgentPool()
    return IntelligentSwarmCoordinator(claude_agent, agent_pool)

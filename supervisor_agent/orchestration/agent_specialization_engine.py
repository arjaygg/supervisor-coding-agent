"""
Agent Specialization Engine

This module provides intelligent routing of tasks to specialized AI agents based on
task characteristics, provider capabilities, and historical performance data.

Fixes SOLID violations by properly separating concerns:
- Single Responsibility: Each class has one clear purpose
- Open-Closed: Extensible through strategy patterns
- Liskov Substitution: All specialization strategies are interchangeable
- Interface Segregation: Separate interfaces for different concerns
- Dependency Inversion: Depends on abstractions, not concretions
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple

import structlog

from supervisor_agent.core.provider_coordinator import ExecutionContext
from supervisor_agent.db.models import Task, TaskType
from supervisor_agent.providers.base_provider import (
    AIProvider,
    ProviderCapabilities,
    ProviderType,
    TaskCapability,
)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
structured_logger = structlog.get_logger(__name__)


class AgentSpecialty(str, Enum):
    """Specialized agent types for different domains"""

    CODE_ARCHITECT = "code_architect"  # System design and architecture
    CODE_REVIEWER = "code_reviewer"  # Code quality and review
    BUG_HUNTER = "bug_hunter"  # Bug detection and fixing
    PERFORMANCE_OPTIMIZER = "performance_optimizer"  # Performance analysis
    SECURITY_ANALYST = "security_analyst"  # Security analysis and fixes
    TEST_ENGINEER = "test_engineer"  # Testing and QA
    DOCUMENTATION_WRITER = "documentation_writer"  # Documentation
    REFACTORING_SPECIALIST = "refactoring_specialist"  # Code refactoring
    DOMAIN_EXPERT = "domain_expert"  # Domain-specific knowledge
    GENERAL_DEVELOPER = "general_developer"  # General development tasks


@dataclass
class SpecializationCapability:
    """Represents a specific capability of an agent specialty"""

    name: str
    proficiency_score: float  # 0.0 to 1.0
    task_types: List[TaskCapability]
    provider_preferences: List[ProviderType]
    context_requirements: Dict[str, Any]
    performance_metrics: Dict[str, float]

    def matches_task(
        self, task_type: TaskCapability, context: Dict[str, Any] = None
    ) -> bool:
        """Check if this capability matches the given task"""
        if task_type not in self.task_types:
            return False

        if context and self.context_requirements:
            for key, required_value in self.context_requirements.items():
                if key not in context or context[key] != required_value:
                    return False

        return True


@dataclass
class SpecializationScore:
    """Score for how well an agent specialty matches a task"""

    specialty: AgentSpecialty
    overall_score: float  # 0.0 to 1.0
    capability_match: float
    provider_availability: float
    historical_performance: float
    context_match: float
    confidence: float
    reasoning: str
    recommended_provider: Optional[ProviderType] = None
    estimated_execution_time: Optional[float] = None


class SpecializationStrategy(Protocol):
    """Protocol for agent specialization strategies"""

    async def calculate_specialization_score(
        self,
        specialty: AgentSpecialty,
        task: Task,
        context: ExecutionContext,
        capabilities: Dict[AgentSpecialty, List[SpecializationCapability]],
        provider_status: Dict[ProviderType, Dict[str, Any]],
    ) -> SpecializationScore:
        """Calculate how well a specialty matches a task"""
        ...


class TaskAnalyzer(ABC):
    """Abstract base class for task analysis"""

    @abstractmethod
    async def analyze_task_characteristics(self, task: Task) -> Dict[str, Any]:
        """Analyze task to extract relevant characteristics"""
        pass


class CapabilityMatcher(ABC):
    """Abstract base class for capability matching"""

    @abstractmethod
    async def match_capabilities(
        self,
        task_characteristics: Dict[str, Any],
        available_capabilities: Dict[AgentSpecialty, List[SpecializationCapability]],
    ) -> List[Tuple[AgentSpecialty, float]]:
        """Match task characteristics to agent capabilities"""
        pass


class PerformancePredictor(ABC):
    """Abstract base class for performance prediction"""

    @abstractmethod
    async def predict_performance(
        self,
        specialty: AgentSpecialty,
        task: Task,
        historical_data: Dict[str, Any],
    ) -> Dict[str, float]:
        """Predict performance metrics for specialty-task combination"""
        pass


class DefaultTaskAnalyzer(TaskAnalyzer):
    """Default implementation of task analysis"""

    def __init__(self):
        self.logger = structured_logger.bind(component="task_analyzer")

    async def analyze_task_characteristics(self, task: Task) -> Dict[str, Any]:
        """Analyze task to extract relevant characteristics"""
        characteristics = {
            "task_type": task.type.value if task.type else "unknown",
            "complexity": self._estimate_complexity(task),
            "domain": self._identify_domain(task),
            "requirements": self._extract_requirements(task),
            "constraints": self._extract_constraints(task),
            "estimated_effort": self._estimate_effort(task),
        }

        self.logger.debug(
            "Task characteristics analyzed",
            task_id=task.id,
            characteristics=characteristics,
        )

        return characteristics

    def _estimate_complexity(self, task: Task) -> str:
        """Estimate task complexity based on payload and description"""
        config = task.payload or {}

        # Simple heuristics for complexity estimation
        complexity_indicators = 0

        if len(str(config)) > 500:
            complexity_indicators += 1

        if task.type in [TaskType.FEATURE, TaskType.SECURITY_AUDIT]:
            complexity_indicators += 2

        if "complex" in str(config).lower() or "advanced" in str(config).lower():
            complexity_indicators += 1

        if complexity_indicators <= 1:
            return "simple"
        elif complexity_indicators <= 3:
            return "moderate"
        else:
            return "complex"

    def _identify_domain(self, task: Task) -> str:
        """Identify the domain of the task"""
        config = task.payload or {}
        task_str = str(config).lower()

        domain_keywords = {
            "security": ["security", "auth", "encryption", "vulnerability"],
            "performance": ["performance", "optimization", "speed", "memory"],
            "testing": ["test", "qa", "quality", "validation"],
            "documentation": ["doc", "documentation", "readme", "guide"],
            "architecture": ["architecture", "design", "system", "structure"],
            "database": ["database", "sql", "migration", "schema"],
            "frontend": ["ui", "frontend", "react", "vue", "angular"],
            "backend": ["api", "backend", "server", "service"],
            "devops": ["deploy", "docker", "kubernetes", "ci/cd"],
        }

        for domain, keywords in domain_keywords.items():
            if any(keyword in task_str for keyword in keywords):
                return domain

        return "general"

    def _extract_requirements(self, task: Task) -> List[str]:
        """Extract requirements from task configuration"""
        config = task.payload or {}
        requirements = []

        # Extract common requirement patterns
        if "requirements" in config:
            if isinstance(config["requirements"], list):
                requirements.extend(config["requirements"])
            else:
                requirements.append(str(config["requirements"]))

        if "dependencies" in config:
            requirements.extend(config.get("dependencies", []))

        return requirements

    def _extract_constraints(self, task: Task) -> Dict[str, Any]:
        """Extract constraints from task configuration"""
        config = task.payload or {}
        constraints = {}

        # Extract common constraint patterns
        constraint_keys = [
            "timeout",
            "budget",
            "resources",
            "deadline",
            "quality",
        ]
        for key in constraint_keys:
            if key in config:
                constraints[key] = config[key]

        return constraints

    def _estimate_effort(self, task: Task) -> float:
        """Estimate effort required for task (in hours)"""
        config = task.payload or {}

        # Base effort by task type
        base_efforts = {
            TaskType.CODE_ANALYSIS: 2.0,
            TaskType.BUG_FIX: 3.0,
            TaskType.PR_REVIEW: 1.5,
            TaskType.FEATURE: 8.0,
            TaskType.REFACTOR: 4.0,
            TaskType.TESTING: 3.0,
            TaskType.DOCUMENTATION: 2.0,
            TaskType.SECURITY_AUDIT: 6.0,
        }

        base_effort = base_efforts.get(task.type, 4.0)

        # Adjust based on complexity
        complexity = self._estimate_complexity(task)
        complexity_multipliers = {
            "simple": 0.7,
            "moderate": 1.0,
            "complex": 1.8,
        }

        return base_effort * complexity_multipliers.get(complexity, 1.0)


class DefaultCapabilityMatcher(CapabilityMatcher):
    """Default implementation of capability matching"""

    def __init__(self):
        self.logger = structured_logger.bind(component="capability_matcher")

    async def match_capabilities(
        self,
        task_characteristics: Dict[str, Any],
        available_capabilities: Dict[AgentSpecialty, List[SpecializationCapability]],
    ) -> List[Tuple[AgentSpecialty, float]]:
        """Match task characteristics to agent capabilities"""
        matches = []

        task_type = task_characteristics.get("task_type", "unknown")
        domain = task_characteristics.get("domain", "general")
        complexity = task_characteristics.get("complexity", "moderate")

        for specialty, capabilities in available_capabilities.items():
            best_match_score = 0.0

            for capability in capabilities:
                score = self._calculate_capability_match(
                    capability,
                    task_type,
                    domain,
                    complexity,
                    task_characteristics,
                )
                best_match_score = max(best_match_score, score)

            if best_match_score > 0.1:  # Only include reasonable matches
                matches.append((specialty, best_match_score))

        # Sort by match score (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)

        self.logger.debug(
            "Capability matching completed",
            task_type=task_type,
            domain=domain,
            matches_count=len(matches),
        )

        return matches

    def _calculate_capability_match(
        self,
        capability: SpecializationCapability,
        task_type: str,
        domain: str,
        complexity: str,
        task_characteristics: Dict[str, Any],
    ) -> float:
        """Calculate how well a capability matches task characteristics"""
        score = 0.0

        # Task type match
        try:
            task_capability = TaskCapability(task_type)
            if task_capability in capability.task_types:
                score += 0.4 * capability.proficiency_score
        except ValueError:
            # Unknown task type
            score += 0.1

        # Domain match
        if "domain" in capability.context_requirements:
            if capability.context_requirements["domain"] == domain:
                score += 0.3

        # Complexity match
        if "complexity" in capability.context_requirements:
            required_complexity = capability.context_requirements["complexity"]
            if isinstance(required_complexity, list):
                if complexity in required_complexity:
                    score += 0.2
            elif required_complexity == complexity:
                score += 0.2

        # Performance bonus
        if "success_rate" in capability.performance_metrics:
            score += 0.1 * capability.performance_metrics["success_rate"]

        return min(score, 1.0)


class DefaultPerformancePredictor(PerformancePredictor):
    """Default implementation of performance prediction"""

    def __init__(self):
        self.logger = structured_logger.bind(component="performance_predictor")

    async def predict_performance(
        self,
        specialty: AgentSpecialty,
        task: Task,
        historical_data: Dict[str, Any],
    ) -> Dict[str, float]:
        """Predict performance metrics for specialty-task combination"""

        # Get historical performance for this specialty
        specialty_history = historical_data.get(specialty.value, {})

        # Base predictions with reasonable defaults
        predictions = {
            "success_rate": specialty_history.get("avg_success_rate", 0.85),
            "avg_execution_time": specialty_history.get("avg_execution_time", 300.0),
            "quality_score": specialty_history.get("avg_quality_score", 0.8),
            "cost_efficiency": specialty_history.get("avg_cost_efficiency", 0.75),
            "confidence": specialty_history.get("prediction_confidence", 0.6),
        }

        # Adjust based on task characteristics
        if task.type:
            task_history = specialty_history.get("task_types", {}).get(
                task.type.value, {}
            )
            if task_history:
                # Use task-specific historical data if available
                for metric in predictions:
                    if metric in task_history:
                        predictions[metric] = task_history[metric]
                        predictions["confidence"] = min(
                            predictions["confidence"] + 0.2, 1.0
                        )

        self.logger.debug(
            "Performance prediction completed",
            specialty=specialty.value,
            task_type=task.type.value if task.type else "unknown",
            predictions=predictions,
        )

        return predictions


class DefaultSpecializationStrategy:
    """Default strategy for calculating specialization scores"""

    def __init__(self):
        self.logger = structured_logger.bind(component="specialization_strategy")

    async def calculate_specialization_score(
        self,
        specialty: AgentSpecialty,
        task: Task,
        context: ExecutionContext,
        capabilities: Dict[AgentSpecialty, List[SpecializationCapability]],
        provider_status: Dict[ProviderType, Dict[str, Any]],
    ) -> SpecializationScore:
        """Calculate how well a specialty matches a task"""

        specialty_capabilities = capabilities.get(specialty, [])
        if not specialty_capabilities:
            return SpecializationScore(
                specialty=specialty,
                overall_score=0.0,
                capability_match=0.0,
                provider_availability=0.0,
                historical_performance=0.0,
                context_match=0.0,
                confidence=0.0,
                reasoning="No capabilities defined for this specialty",
            )

        # Calculate capability match
        capability_match = await self._calculate_capability_match(
            specialty_capabilities, task, context
        )

        # Calculate provider availability
        provider_availability = await self._calculate_provider_availability(
            specialty_capabilities, provider_status
        )

        # Calculate historical performance
        historical_performance = await self._calculate_historical_performance(
            specialty, task
        )

        # Calculate context match
        context_match = await self._calculate_context_match(
            specialty_capabilities, context
        )

        # Calculate overall score with weights
        weights = {
            "capability": 0.35,
            "provider": 0.25,
            "performance": 0.25,
            "context": 0.15,
        }

        overall_score = (
            capability_match * weights["capability"]
            + provider_availability * weights["provider"]
            + historical_performance * weights["performance"]
            + context_match * weights["context"]
        )

        # Determine recommended provider
        recommended_provider = await self._select_recommended_provider(
            specialty_capabilities, provider_status
        )

        # Generate reasoning
        reasoning = self._generate_reasoning(
            capability_match,
            provider_availability,
            historical_performance,
            context_match,
        )

        confidence = min(
            (capability_match + provider_availability + historical_performance) / 3,
            1.0,
        )

        return SpecializationScore(
            specialty=specialty,
            overall_score=overall_score,
            capability_match=capability_match,
            provider_availability=provider_availability,
            historical_performance=historical_performance,
            context_match=context_match,
            confidence=confidence,
            reasoning=reasoning,
            recommended_provider=recommended_provider,
            estimated_execution_time=self._estimate_execution_time(
                specialty_capabilities, task
            ),
        )

    async def _calculate_capability_match(
        self,
        capabilities: List[SpecializationCapability],
        task: Task,
        context: ExecutionContext,
    ) -> float:
        """Calculate how well capabilities match the task"""
        if not capabilities:
            return 0.0

        best_match = 0.0
        for capability in capabilities:
            try:
                task_capability = TaskCapability(task.type.value) if task.type else None
                if task_capability and capability.matches_task(task_capability):
                    match_score = capability.proficiency_score
                    best_match = max(best_match, match_score)
            except (ValueError, AttributeError):
                # Handle unknown task types or missing attributes
                best_match = max(best_match, 0.3)

        return best_match

    async def _calculate_provider_availability(
        self,
        capabilities: List[SpecializationCapability],
        provider_status: Dict[ProviderType, Dict[str, Any]],
    ) -> float:
        """Calculate provider availability score"""
        if not capabilities:
            return 0.0

        total_availability = 0.0
        provider_count = 0

        for capability in capabilities:
            for provider_type in capability.provider_preferences:
                if provider_type in provider_status:
                    status = provider_status[provider_type]
                    if status.get("status") == "active":
                        availability = 1.0 - status.get("load", 0.0)
                        total_availability += availability
                        provider_count += 1

        return total_availability / provider_count if provider_count > 0 else 0.0

    async def _calculate_historical_performance(
        self, specialty: AgentSpecialty, task: Task
    ) -> float:
        """Calculate historical performance score"""
        # TODO: Implement actual historical data lookup
        # For now, return reasonable defaults based on specialty

        performance_defaults = {
            AgentSpecialty.CODE_ARCHITECT: 0.9,
            AgentSpecialty.CODE_REVIEWER: 0.85,
            AgentSpecialty.BUG_HUNTER: 0.8,
            AgentSpecialty.PERFORMANCE_OPTIMIZER: 0.75,
            AgentSpecialty.SECURITY_ANALYST: 0.9,
            AgentSpecialty.TEST_ENGINEER: 0.85,
            AgentSpecialty.DOCUMENTATION_WRITER: 0.8,
            AgentSpecialty.REFACTORING_SPECIALIST: 0.75,
            AgentSpecialty.DOMAIN_EXPERT: 0.85,
            AgentSpecialty.GENERAL_DEVELOPER: 0.7,
        }

        return performance_defaults.get(specialty, 0.7)

    async def _calculate_context_match(
        self,
        capabilities: List[SpecializationCapability],
        context: ExecutionContext,
    ) -> float:
        """Calculate how well the context matches capability requirements"""
        if not capabilities:
            return 0.0

        best_match = 0.0
        for capability in capabilities:
            context_requirements = capability.context_requirements
            match_score = 1.0

            # Check priority match
            if "min_priority" in context_requirements:
                if context.priority < context_requirements["min_priority"]:
                    match_score *= 0.5

            # Check organization match
            if "organization_types" in context_requirements:
                # This would need actual organization type lookup
                pass

            best_match = max(best_match, match_score)

        return best_match

    async def _select_recommended_provider(
        self,
        capabilities: List[SpecializationCapability],
        provider_status: Dict[ProviderType, Dict[str, Any]],
    ) -> Optional[ProviderType]:
        """Select the best provider for the specialty"""
        best_provider = None
        best_score = 0.0

        for capability in capabilities:
            for provider_type in capability.provider_preferences:
                if provider_type in provider_status:
                    status = provider_status[provider_type]
                    if status.get("status") == "active":
                        # Score based on availability and capability preference
                        score = (
                            1.0 - status.get("load", 0.0)
                        ) * capability.proficiency_score
                        if score > best_score:
                            best_score = score
                            best_provider = provider_type

        return best_provider

    def _generate_reasoning(
        self,
        capability_match: float,
        provider_availability: float,
        historical_performance: float,
        context_match: float,
    ) -> str:
        """Generate human-readable reasoning for the score"""
        reasons = []

        if capability_match > 0.8:
            reasons.append("Strong capability match")
        elif capability_match > 0.6:
            reasons.append("Good capability match")
        else:
            reasons.append("Limited capability match")

        if provider_availability > 0.8:
            reasons.append("high provider availability")
        elif provider_availability > 0.5:
            reasons.append("moderate provider availability")
        else:
            reasons.append("low provider availability")

        if historical_performance > 0.8:
            reasons.append("excellent historical performance")
        elif historical_performance > 0.6:
            reasons.append("good historical performance")
        else:
            reasons.append("average historical performance")

        return f"{reasons[0]} with {reasons[1]} and {reasons[2]}"

    def _estimate_execution_time(
        self, capabilities: List[SpecializationCapability], task: Task
    ) -> float:
        """Estimate execution time for the task"""
        if not capabilities:
            return 300.0  # Default 5 minutes

        # Use performance metrics from best capability
        best_capability = max(capabilities, key=lambda c: c.proficiency_score)
        base_time = best_capability.performance_metrics.get("avg_execution_time", 300.0)

        # Adjust based on proficiency (higher proficiency = faster execution)
        efficiency_factor = best_capability.proficiency_score
        estimated_time = base_time / max(efficiency_factor, 0.5)

        return estimated_time


class AgentSpecializationEngine:
    """
    Intelligent engine for routing tasks to specialized AI agents.

    This engine analyzes tasks and selects the most appropriate agent specialty
    based on task characteristics, provider capabilities, and historical performance.

    Fixed SOLID violations:
    - Single Responsibility: Focuses only on agent specialization
    - Open-Closed: Extensible through strategy patterns
    - Liskov Substitution: All components are interchangeable
    - Interface Segregation: Separate interfaces for different concerns
    - Dependency Inversion: Depends on abstractions
    """

    def __init__(
        self,
        task_analyzer: Optional[TaskAnalyzer] = None,
        capability_matcher: Optional[CapabilityMatcher] = None,
        performance_predictor: Optional[PerformancePredictor] = None,
        specialization_strategy: Optional[SpecializationStrategy] = None,
    ):
        self.task_analyzer = task_analyzer or DefaultTaskAnalyzer()
        self.capability_matcher = capability_matcher or DefaultCapabilityMatcher()
        self.performance_predictor = (
            performance_predictor or DefaultPerformancePredictor()
        )
        self.specialization_strategy = (
            specialization_strategy or DefaultSpecializationStrategy()
        )

        self.logger = structured_logger.bind(component="agent_specialization_engine")

        # Initialize agent capabilities
        self.agent_capabilities = self._initialize_agent_capabilities()

    async def select_best_specialist(
        self,
        task: Task,
        context: ExecutionContext,
        provider_status: Dict[ProviderType, Dict[str, Any]] = None,
    ) -> SpecializationScore:
        """
        Select the best specialist agent for a given task.

        Args:
            task: The task to be executed
            context: Execution context with constraints and preferences
            provider_status: Current status of available providers

        Returns:
            SpecializationScore with the best matching specialist
        """
        self.logger.info(
            "Starting agent specialization selection",
            task_id=task.id,
            task_type=task.type.value if task.type else "unknown",
        )

        if provider_status is None:
            provider_status = await self._get_provider_status()

        try:
            # Analyze task characteristics
            task_characteristics = (
                await self.task_analyzer.analyze_task_characteristics(task)
            )

            # Match capabilities
            capability_matches = await self.capability_matcher.match_capabilities(
                task_characteristics, self.agent_capabilities
            )

            if not capability_matches:
                # Return general developer as fallback
                return (
                    await self.specialization_strategy.calculate_specialization_score(
                        AgentSpecialty.GENERAL_DEVELOPER,
                        task,
                        context,
                        self.agent_capabilities,
                        provider_status,
                    )
                )

            # Calculate specialization scores for top matches
            best_score = None
            for specialty, capability_match in capability_matches[
                :5
            ]:  # Top 5 candidates
                score = (
                    await self.specialization_strategy.calculate_specialization_score(
                        specialty,
                        task,
                        context,
                        self.agent_capabilities,
                        provider_status,
                    )
                )

                if best_score is None or score.overall_score > best_score.overall_score:
                    best_score = score

            self.logger.info(
                "Agent specialization selection completed",
                task_id=task.id,
                selected_specialty=best_score.specialty.value,
                overall_score=best_score.overall_score,
                confidence=best_score.confidence,
            )

            return best_score

        except Exception as e:
            self.logger.error(
                "Agent specialization selection failed",
                task_id=task.id,
                error=str(e),
            )

            # Return fallback general developer
            return SpecializationScore(
                specialty=AgentSpecialty.GENERAL_DEVELOPER,
                overall_score=0.5,
                capability_match=0.5,
                provider_availability=0.5,
                historical_performance=0.5,
                context_match=0.5,
                confidence=0.3,
                reasoning="Fallback to general developer due to selection error",
            )

    async def get_all_specialization_scores(
        self,
        task: Task,
        context: ExecutionContext,
        provider_status: Dict[ProviderType, Dict[str, Any]] = None,
    ) -> List[SpecializationScore]:
        """Get specialization scores for all available specialists"""

        if provider_status is None:
            provider_status = await self._get_provider_status()

        scores = []
        for specialty in AgentSpecialty:
            score = await self.specialization_strategy.calculate_specialization_score(
                specialty,
                task,
                context,
                self.agent_capabilities,
                provider_status,
            )
            scores.append(score)

        # Sort by overall score (highest first)
        scores.sort(key=lambda s: s.overall_score, reverse=True)

        return scores

    async def update_agent_capabilities(
        self,
        specialty: AgentSpecialty,
        capabilities: List[SpecializationCapability],
    ):
        """Update capabilities for a specific agent specialty"""
        self.agent_capabilities[specialty] = capabilities

        self.logger.info(
            "Agent capabilities updated",
            specialty=specialty.value,
            capabilities_count=len(capabilities),
        )

    async def get_agent_capabilities(
        self, specialty: AgentSpecialty
    ) -> List[SpecializationCapability]:
        """Get capabilities for a specific agent specialty"""
        return self.agent_capabilities.get(specialty, [])

    def _initialize_agent_capabilities(
        self,
    ) -> Dict[AgentSpecialty, List[SpecializationCapability]]:
        """Initialize default agent capabilities"""

        capabilities = {
            AgentSpecialty.CODE_ARCHITECT: [
                SpecializationCapability(
                    name="System Design",
                    proficiency_score=0.9,
                    task_types=[
                        TaskCapability.FEATURE_DEVELOPMENT,
                        TaskCapability.GENERAL_CODING,
                    ],
                    provider_preferences=[
                        ProviderType.CLAUDE_CLI,
                        ProviderType.ANTHROPIC_API,
                    ],
                    context_requirements={
                        "complexity": ["complex", "moderate"],
                        "domain": "architecture",
                    },
                    performance_metrics={
                        "success_rate": 0.9,
                        "avg_execution_time": 600.0,
                    },
                ),
                SpecializationCapability(
                    name="Architecture Review",
                    proficiency_score=0.85,
                    task_types=[
                        TaskCapability.CODE_REVIEW,
                        TaskCapability.CODE_ANALYSIS,
                    ],
                    provider_preferences=[ProviderType.CLAUDE_CLI],
                    context_requirements={"domain": "architecture"},
                    performance_metrics={
                        "success_rate": 0.85,
                        "avg_execution_time": 300.0,
                    },
                ),
            ],
            AgentSpecialty.CODE_REVIEWER: [
                SpecializationCapability(
                    name="Code Quality Review",
                    proficiency_score=0.9,
                    task_types=[
                        TaskCapability.CODE_REVIEW,
                        TaskCapability.CODE_ANALYSIS,
                    ],
                    provider_preferences=[
                        ProviderType.CLAUDE_CLI,
                        ProviderType.ANTHROPIC_API,
                    ],
                    context_requirements={"domain": "general"},
                    performance_metrics={
                        "success_rate": 0.9,
                        "avg_execution_time": 240.0,
                    },
                )
            ],
            AgentSpecialty.BUG_HUNTER: [
                SpecializationCapability(
                    name="Bug Detection",
                    proficiency_score=0.85,
                    task_types=[
                        TaskCapability.BUG_FIX,
                        TaskCapability.CODE_ANALYSIS,
                    ],
                    provider_preferences=[ProviderType.CLAUDE_CLI],
                    context_requirements={"domain": "debugging"},
                    performance_metrics={
                        "success_rate": 0.8,
                        "avg_execution_time": 360.0,
                    },
                )
            ],
            AgentSpecialty.PERFORMANCE_OPTIMIZER: [
                SpecializationCapability(
                    name="Performance Analysis",
                    proficiency_score=0.8,
                    task_types=[
                        TaskCapability.PERFORMANCE_OPTIMIZATION,
                        TaskCapability.CODE_ANALYSIS,
                    ],
                    provider_preferences=[ProviderType.CLAUDE_CLI],
                    context_requirements={"domain": "performance"},
                    performance_metrics={
                        "success_rate": 0.75,
                        "avg_execution_time": 480.0,
                    },
                )
            ],
            AgentSpecialty.SECURITY_ANALYST: [
                SpecializationCapability(
                    name="Security Analysis",
                    proficiency_score=0.9,
                    task_types=[
                        TaskCapability.SECURITY_ANALYSIS,
                        TaskCapability.CODE_REVIEW,
                    ],
                    provider_preferences=[
                        ProviderType.CLAUDE_CLI,
                        ProviderType.ANTHROPIC_API,
                    ],
                    context_requirements={"domain": "security"},
                    performance_metrics={
                        "success_rate": 0.9,
                        "avg_execution_time": 420.0,
                    },
                )
            ],
            AgentSpecialty.TEST_ENGINEER: [
                SpecializationCapability(
                    name="Test Development",
                    proficiency_score=0.85,
                    task_types=[
                        TaskCapability.TESTING,
                        TaskCapability.CODE_ANALYSIS,
                    ],
                    provider_preferences=[ProviderType.CLAUDE_CLI],
                    context_requirements={"domain": "testing"},
                    performance_metrics={
                        "success_rate": 0.85,
                        "avg_execution_time": 300.0,
                    },
                )
            ],
            AgentSpecialty.DOCUMENTATION_WRITER: [
                SpecializationCapability(
                    name="Documentation Creation",
                    proficiency_score=0.8,
                    task_types=[TaskCapability.DOCUMENTATION],
                    provider_preferences=[
                        ProviderType.CLAUDE_CLI,
                        ProviderType.ANTHROPIC_API,
                    ],
                    context_requirements={"domain": "documentation"},
                    performance_metrics={
                        "success_rate": 0.8,
                        "avg_execution_time": 240.0,
                    },
                )
            ],
            AgentSpecialty.REFACTORING_SPECIALIST: [
                SpecializationCapability(
                    name="Code Refactoring",
                    proficiency_score=0.75,
                    task_types=[
                        TaskCapability.REFACTORING,
                        TaskCapability.CODE_ANALYSIS,
                    ],
                    provider_preferences=[ProviderType.CLAUDE_CLI],
                    context_requirements={"domain": "refactoring"},
                    performance_metrics={
                        "success_rate": 0.75,
                        "avg_execution_time": 360.0,
                    },
                )
            ],
            AgentSpecialty.DOMAIN_EXPERT: [
                SpecializationCapability(
                    name="Domain Expertise",
                    proficiency_score=0.85,
                    task_types=[
                        TaskCapability.FEATURE_DEVELOPMENT,
                        TaskCapability.CODE_REVIEW,
                    ],
                    provider_preferences=[
                        ProviderType.CLAUDE_CLI,
                        ProviderType.ANTHROPIC_API,
                    ],
                    context_requirements={"complexity": ["complex"]},
                    performance_metrics={
                        "success_rate": 0.85,
                        "avg_execution_time": 450.0,
                    },
                )
            ],
            AgentSpecialty.GENERAL_DEVELOPER: [
                SpecializationCapability(
                    name="General Development",
                    proficiency_score=0.7,
                    task_types=list(TaskCapability),  # Supports all task types
                    provider_preferences=[
                        ProviderType.CLAUDE_CLI,
                        ProviderType.LOCAL_MOCK,
                    ],
                    context_requirements={},
                    performance_metrics={
                        "success_rate": 0.7,
                        "avg_execution_time": 360.0,
                    },
                )
            ],
        }

        return capabilities

    async def _get_provider_status(self) -> Dict[ProviderType, Dict[str, Any]]:
        """Get current status of all providers"""
        # TODO: Implement actual provider status lookup
        # For now, return mock status

        return {
            ProviderType.CLAUDE_CLI: {
                "status": "active",
                "load": 0.3,
                "response_time_ms": 150.0,
                "success_rate": 0.95,
            },
            ProviderType.ANTHROPIC_API: {
                "status": "active",
                "load": 0.5,
                "response_time_ms": 200.0,
                "success_rate": 0.92,
            },
            ProviderType.LOCAL_MOCK: {
                "status": "active",
                "load": 0.1,
                "response_time_ms": 50.0,
                "success_rate": 0.8,
            },
        }


# Factory function for dependency injection
async def create_agent_specialization_engine(
    task_analyzer: Optional[TaskAnalyzer] = None,
    capability_matcher: Optional[CapabilityMatcher] = None,
    performance_predictor: Optional[PerformancePredictor] = None,
    specialization_strategy: Optional[SpecializationStrategy] = None,
) -> AgentSpecializationEngine:
    """
    Factory function to create configured agent specialization engine.

    Args:
        task_analyzer: Custom task analyzer implementation
        capability_matcher: Custom capability matcher implementation
        performance_predictor: Custom performance predictor implementation
        specialization_strategy: Custom specialization strategy implementation

    Returns:
        Configured AgentSpecializationEngine instance
    """
    return AgentSpecializationEngine(
        task_analyzer=task_analyzer,
        capability_matcher=capability_matcher,
        performance_predictor=performance_predictor,
        specialization_strategy=specialization_strategy,
    )

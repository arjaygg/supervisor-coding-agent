# supervisor_agent/intelligence/decision_engine.py
"""
Intelligent Decision Engine

This module provides AI-powered decision making capabilities for the supervisor agent.
It handles complex decision scenarios, multi-criteria optimization, strategic planning,
and adaptive decision making based on context and historical performance.
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

from supervisor_agent.intelligence.workflow_synthesizer import ClaudeAgentWrapper
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
structured_logger = structlog.get_logger(__name__)


class DecisionType(Enum):
    """Types of decisions the engine can make."""
    RESOURCE_ALLOCATION = "resource_allocation"
    TASK_PRIORITIZATION = "task_prioritization"
    WORKFLOW_OPTIMIZATION = "workflow_optimization"
    CONFLICT_RESOLUTION = "conflict_resolution"
    STRATEGIC_PLANNING = "strategic_planning"
    RISK_MITIGATION = "risk_mitigation"
    PERFORMANCE_TUNING = "performance_tuning"
    CAPACITY_PLANNING = "capacity_planning"


class DecisionUrgency(Enum):
    """Urgency levels for decisions."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DEFERRED = "deferred"


class DecisionStatus(Enum):
    """Status of decision processing."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    DECIDED = "decided"
    IMPLEMENTING = "implementing"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


@dataclass
class DecisionCriteria:
    """Criteria for decision evaluation."""
    criterion_id: str
    name: str
    weight: float  # 0.0 to 1.0
    optimization_direction: str  # "maximize" or "minimize"
    evaluation_function: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class DecisionOption:
    """A potential decision option to evaluate."""
    option_id: str
    name: str
    description: str
    parameters: Dict[str, Any]
    estimated_impact: Dict[str, float]
    implementation_cost: float
    risk_assessment: Dict[str, Any]
    time_to_implement: int  # minutes
    reversibility: bool
    confidence_score: float = 0.0


@dataclass
class DecisionContext:
    """Context information for decision making."""
    context_id: str
    decision_type: DecisionType
    urgency: DecisionUrgency
    stakeholders: List[str]
    constraints: Dict[str, Any]
    available_resources: Dict[str, Any]
    historical_context: Dict[str, Any]
    environmental_factors: Dict[str, Any]
    success_metrics: Dict[str, Any]
    deadline: Optional[datetime] = None


@dataclass
class DecisionRequest:
    """A request for decision making."""
    request_id: str
    decision_type: DecisionType
    context: DecisionContext
    criteria: List[DecisionCriteria]
    options: List[DecisionOption]
    requesting_entity: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionResult:
    """Result of a decision making process."""
    decision_id: str
    request_id: str
    selected_option: DecisionOption
    reasoning: str
    confidence_score: float
    alternative_options: List[DecisionOption]
    implementation_plan: Dict[str, Any]
    risk_analysis: Dict[str, Any]
    monitoring_requirements: Dict[str, Any]
    rollback_plan: Dict[str, Any]
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionEngine:
    """
    Intelligent Decision Engine that provides AI-powered decision making
    capabilities with multi-criteria optimization and strategic reasoning.
    """
    
    def __init__(self, claude_agent: ClaudeAgentWrapper):
        self.claude_agent = claude_agent
        
        # Decision tracking
        self.active_decisions: Dict[str, DecisionRequest] = {}
        self.decision_history: deque = deque(maxlen=1000)
        self.decision_results: Dict[str, DecisionResult] = {}
        
        # Decision performance tracking
        self.performance_metrics: Dict[str, Any] = defaultdict(dict)
        self.learning_database: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Configuration
        self.max_concurrent_decisions = 10
        self.decision_timeout_minutes = 30
        self.confidence_threshold = 0.7
        
        # Strategy patterns
        self.decision_strategies: Dict[str, Dict[str, Any]] = {
            "conservative": {"risk_tolerance": 0.3, "change_preference": 0.2},
            "balanced": {"risk_tolerance": 0.5, "change_preference": 0.5},
            "aggressive": {"risk_tolerance": 0.8, "change_preference": 0.8},
            "adaptive": {"risk_tolerance": 0.6, "change_preference": 0.7}
        }
        
        self.logger = structured_logger.bind(component="decision_engine")
    
    async def make_decision(
        self, 
        decision_request: DecisionRequest,
        strategy: str = "adaptive"
    ) -> DecisionResult:
        """
        Make an intelligent decision based on the provided request and context.
        
        Args:
            decision_request: The decision request with context and options
            strategy: Decision making strategy to use
            
        Returns:
            DecisionResult with the recommended decision and reasoning
        """
        
        try:
            self.logger.info(
                "Processing decision request",
                request_id=decision_request.request_id,
                decision_type=decision_request.decision_type.value,
                urgency=decision_request.context.urgency.value,
                options_count=len(decision_request.options)
            )
            
            # Store active decision
            self.active_decisions[decision_request.request_id] = decision_request
            
            # Generate comprehensive decision analysis
            decision_analysis = await self._analyze_decision_context(decision_request, strategy)
            
            # Evaluate all options using AI-powered multi-criteria analysis
            option_evaluations = await self._evaluate_decision_options(
                decision_request, decision_analysis, strategy
            )
            
            # Select optimal decision using intelligent selection algorithms
            optimal_decision = await self._select_optimal_decision(
                decision_request, option_evaluations, decision_analysis
            )
            
            # Generate implementation and monitoring plans
            implementation_plan = await self._generate_implementation_plan(
                decision_request, optimal_decision
            )
            
            # Create decision result
            decision_result = DecisionResult(
                decision_id=str(uuid.uuid4()),
                request_id=decision_request.request_id,
                selected_option=optimal_decision,
                reasoning=decision_analysis.get("reasoning", "AI-powered decision analysis"),
                confidence_score=optimal_decision.confidence_score,
                alternative_options=option_evaluations.get("alternatives", []),
                implementation_plan=implementation_plan,
                risk_analysis=decision_analysis.get("risk_analysis", {}),
                monitoring_requirements=decision_analysis.get("monitoring", {}),
                rollback_plan=decision_analysis.get("rollback_plan", {})
            )
            
            # Store results and update learning
            self.decision_results[decision_result.decision_id] = decision_result
            self.decision_history.append(decision_result)
            await self._update_learning_database(decision_request, decision_result)
            
            # Clean up active decision
            if decision_request.request_id in self.active_decisions:
                del self.active_decisions[decision_request.request_id]
            
            self.logger.info(
                "Decision completed successfully",
                decision_id=decision_result.decision_id,
                selected_option=optimal_decision.name,
                confidence=optimal_decision.confidence_score
            )
            
            return decision_result
            
        except Exception as e:
            self.logger.error(
                "Decision making failed",
                request_id=decision_request.request_id,
                error=str(e)
            )
            raise
    
    async def _analyze_decision_context(
        self, 
        request: DecisionRequest, 
        strategy: str
    ) -> Dict[str, Any]:
        """Analyze the decision context using AI-powered reasoning."""
        
        # Gather historical patterns and learnings
        historical_insights = await self._gather_historical_insights(request.decision_type)
        
        # Analyze environmental factors and constraints
        environmental_analysis = await self._analyze_environmental_factors(request.context)
        
        context_analysis_prompt = f"""
        Perform comprehensive decision context analysis for intelligent decision making:
        
        Decision Request: {json.dumps({
            "type": request.decision_type.value,
            "urgency": request.context.urgency.value,
            "stakeholders": request.context.stakeholders,
            "constraints": request.context.constraints,
            "available_resources": request.context.available_resources,
            "success_metrics": request.context.success_metrics
        }, indent=2)}
        
        Historical Insights: {json.dumps(historical_insights, indent=2)}
        Environmental Analysis: {json.dumps(environmental_analysis, indent=2)}
        Strategy: {strategy} - {self.decision_strategies.get(strategy, {})}
        
        Analyze this decision context and provide comprehensive insights:
        1. What are the key factors that should influence this decision?
        2. What are the primary risks and opportunities?
        3. How do historical patterns inform this decision?
        4. What environmental factors create constraints or opportunities?
        5. What are the potential second and third-order effects?
        6. How should the urgency level impact the decision approach?
        7. What stakeholder considerations are most critical?
        8. What success criteria should guide the evaluation?
        
        Provide analysis in JSON format with:
        - key_factors: most important decision influencers
        - risk_analysis: detailed risk assessment and mitigation strategies
        - opportunity_analysis: potential benefits and value creation
        - stakeholder_impact: analysis of effects on different stakeholders
        - environmental_considerations: external factors and market conditions
        - historical_patterns: lessons from similar past decisions
        - urgency_implications: how time pressure affects options
        - success_criteria: metrics for evaluating decision effectiveness
        - strategic_alignment: how options align with long-term objectives
        - implementation_considerations: practical factors for execution
        - monitoring_requirements: what to track after implementation
        - rollback_plan: how to reverse the decision if needed
        
        Focus on comprehensive analysis that enables optimal decision making.
        """
        
        result = await self.claude_agent.execute_task(
            {"type": "decision_context_analysis", "prompt": context_analysis_prompt},
            shared_memory={"decision_context": request.context.__dict__}
        )
        
        try:
            analysis = json.loads(result["result"])
            
            # Add reasoning summary
            analysis["reasoning"] = self._generate_decision_reasoning(request, analysis)
            
            return analysis
            
        except (json.JSONDecodeError, KeyError):
            # Return basic analysis as fallback
            return self._create_basic_context_analysis(request)
    
    async def _evaluate_decision_options(
        self, 
        request: DecisionRequest, 
        context_analysis: Dict[str, Any],
        strategy: str
    ) -> Dict[str, Any]:
        """Evaluate all decision options using multi-criteria analysis."""
        
        evaluation_results = {
            "primary_option": None,
            "alternatives": [],
            "evaluation_matrix": {},
            "criteria_weights": {},
            "risk_assessments": {}
        }
        
        for option in request.options:
            # AI-powered option evaluation
            option_evaluation = await self._evaluate_single_option(
                option, request, context_analysis, strategy
            )
            
            # Multi-criteria scoring
            criteria_scores = await self._calculate_criteria_scores(
                option, request.criteria, context_analysis
            )
            
            # Risk-adjusted scoring
            risk_adjusted_score = await self._calculate_risk_adjusted_score(
                option, criteria_scores, context_analysis
            )
            
            # Update option confidence
            option.confidence_score = risk_adjusted_score
            
            # Store evaluation results
            evaluation_results["evaluation_matrix"][option.option_id] = {
                "option": option,
                "criteria_scores": criteria_scores,
                "risk_adjusted_score": risk_adjusted_score,
                "ai_evaluation": option_evaluation
            }
        
        # Rank options by confidence score
        ranked_options = sorted(
            request.options,
            key=lambda x: x.confidence_score,
            reverse=True
        )
        
        evaluation_results["primary_option"] = ranked_options[0] if ranked_options else None
        evaluation_results["alternatives"] = ranked_options[1:5]  # Top 4 alternatives
        
        return evaluation_results
    
    async def _evaluate_single_option(
        self, 
        option: DecisionOption, 
        request: DecisionRequest,
        context_analysis: Dict[str, Any],
        strategy: str
    ) -> Dict[str, Any]:
        """Evaluate a single decision option using AI reasoning."""
        
        option_evaluation_prompt = f"""
        Evaluate decision option using comprehensive AI-powered analysis:
        
        Option Details: {json.dumps({
            "name": option.name,
            "description": option.description,
            "parameters": option.parameters,
            "estimated_impact": option.estimated_impact,
            "implementation_cost": option.implementation_cost,
            "risk_assessment": option.risk_assessment,
            "time_to_implement": option.time_to_implement,
            "reversibility": option.reversibility
        }, indent=2)}
        
        Decision Context: {json.dumps({
            "type": request.decision_type.value,
            "urgency": request.context.urgency.value,
            "constraints": request.context.constraints,
            "success_metrics": request.context.success_metrics
        }, indent=2)}
        
        Context Analysis: {json.dumps(context_analysis, indent=2)}
        Strategy: {strategy}
        
        Evaluate this option comprehensively:
        1. How well does this option address the core decision requirements?
        2. What are the potential benefits and positive outcomes?
        3. What are the risks and potential negative consequences?
        4. How feasible is implementation given current constraints?
        5. What resources and capabilities are required?
        6. How does this option align with strategic objectives?
        7. What are the short-term and long-term implications?
        8. How does this compare to alternative approaches?
        
        Provide evaluation in JSON format with:
        - effectiveness_score: how well option solves the problem (0-100)
        - feasibility_score: implementation practicality (0-100)
        - risk_score: overall risk level (0-100, lower is better)
        - strategic_alignment: alignment with long-term goals (0-100)
        - resource_efficiency: efficient use of resources (0-100)
        - stakeholder_acceptance: likely stakeholder support (0-100)
        - reversibility_factor: ease of reversal if needed (0-100)
        - innovation_potential: opportunity for innovation (0-100)
        - strengths: key advantages of this option
        - weaknesses: significant limitations or concerns
        - implementation_challenges: practical difficulties
        - success_factors: what needs to go right
        - alternative_considerations: how this compares to other options
        
        Focus on thorough evaluation that supports optimal decision making.
        """
        
        result = await self.claude_agent.execute_task(
            {"type": "option_evaluation", "prompt": option_evaluation_prompt},
            shared_memory={"option_context": option.__dict__}
        )
        
        try:
            return json.loads(result["result"])
        except (json.JSONDecodeError, KeyError):
            return self._create_basic_option_evaluation(option)
    
    async def _calculate_criteria_scores(
        self, 
        option: DecisionOption, 
        criteria: List[DecisionCriteria],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate scores for each decision criterion."""
        
        scores = {}
        
        for criterion in criteria:
            if criterion.evaluation_function:
                # Use custom evaluation function if provided
                score = await self._evaluate_custom_criterion(option, criterion, context_analysis)
            else:
                # Use standard evaluation approach
                score = await self._evaluate_standard_criterion(option, criterion, context_analysis)
            
            scores[criterion.criterion_id] = score
        
        return scores
    
    async def _calculate_risk_adjusted_score(
        self, 
        option: DecisionOption, 
        criteria_scores: Dict[str, float],
        context_analysis: Dict[str, Any]
    ) -> float:
        """Calculate risk-adjusted confidence score for an option."""
        
        # Calculate weighted criteria score
        total_weight = sum(
            criterion.weight for criterion in self.active_decisions[
                list(self.active_decisions.keys())[0]
            ].criteria
        )
        
        if total_weight == 0:
            weighted_score = 0.5
        else:
            weighted_score = sum(
                score * (criterion.weight / total_weight)
                for criterion in self.active_decisions[
                    list(self.active_decisions.keys())[0]
                ].criteria
                for score in [criteria_scores.get(criterion.criterion_id, 0.5)]
            )
        
        # Apply risk adjustment
        risk_factor = 1.0 - (option.risk_assessment.get("overall_risk", 0.5) * 0.3)
        
        # Apply implementation feasibility factor
        feasibility_factor = 1.0 - (option.implementation_cost / 1000000.0 * 0.1)  # Adjust based on cost
        
        # Apply confidence adjustment based on context analysis
        context_confidence = context_analysis.get("confidence_factor", 0.8)
        
        # Calculate final risk-adjusted score
        final_score = weighted_score * risk_factor * feasibility_factor * context_confidence
        
        return min(1.0, max(0.0, final_score))
    
    async def _select_optimal_decision(
        self, 
        request: DecisionRequest, 
        option_evaluations: Dict[str, Any],
        context_analysis: Dict[str, Any]
    ) -> DecisionOption:
        """Select the optimal decision using intelligent selection algorithms."""
        
        # Get primary option from evaluations
        primary_option = option_evaluations.get("primary_option")
        
        if not primary_option:
            raise ValueError("No viable decision options found")
        
        # Verify decision meets minimum confidence threshold
        if primary_option.confidence_score < self.confidence_threshold:
            # Consider escalation or additional analysis
            if request.context.urgency in [DecisionUrgency.CRITICAL, DecisionUrgency.HIGH]:
                # Accept lower confidence for urgent decisions
                self.logger.warning(
                    "Accepting decision below confidence threshold due to urgency",
                    confidence=primary_option.confidence_score,
                    threshold=self.confidence_threshold,
                    urgency=request.context.urgency.value
                )
            else:
                # Recommend escalation for non-urgent low-confidence decisions
                self.logger.warning(
                    "Decision confidence below threshold - consider escalation",
                    confidence=primary_option.confidence_score,
                    threshold=self.confidence_threshold
                )
        
        return primary_option
    
    async def _generate_implementation_plan(
        self, 
        request: DecisionRequest, 
        selected_option: DecisionOption
    ) -> Dict[str, Any]:
        """Generate detailed implementation plan for the selected decision."""
        
        implementation_prompt = f"""
        Generate comprehensive implementation plan for decision execution:
        
        Selected Decision: {json.dumps({
            "name": selected_option.name,
            "description": selected_option.description,
            "parameters": selected_option.parameters,
            "estimated_impact": selected_option.estimated_impact,
            "implementation_cost": selected_option.implementation_cost,
            "time_to_implement": selected_option.time_to_implement
        }, indent=2)}
        
        Decision Context: {json.dumps({
            "type": request.decision_type.value,
            "urgency": request.context.urgency.value,
            "stakeholders": request.context.stakeholders,
            "constraints": request.context.constraints,
            "available_resources": request.context.available_resources
        }, indent=2)}
        
        Create detailed implementation plan:
        1. What are the specific implementation steps and sequence?
        2. What resources and capabilities are required for each step?
        3. What are the key milestones and checkpoints?
        4. How should progress be monitored and measured?
        5. What risks need to be managed during implementation?
        6. What stakeholder communication is required?
        7. What success criteria indicate successful implementation?
        8. What contingency plans are needed for potential issues?
        
        Provide implementation plan in JSON format with:
        - implementation_steps: detailed sequence of actions
        - resource_requirements: needed resources for each step
        - timeline: estimated schedule with milestones
        - responsibilities: who is responsible for each step
        - success_criteria: measurable indicators of success
        - risk_mitigation: strategies for managing implementation risks
        - monitoring_plan: how to track progress and performance
        - communication_plan: stakeholder updates and reporting
        - quality_gates: checkpoints for validation and approval
        - contingency_procedures: backup plans for common issues
        - rollback_triggers: conditions that would require reversal
        - post_implementation: follow-up activities and optimization
        
        Focus on practical, actionable implementation guidance.
        """
        
        result = await self.claude_agent.execute_task(
            {"type": "implementation_planning", "prompt": implementation_prompt},
            shared_memory={"implementation_context": selected_option.__dict__}
        )
        
        try:
            return json.loads(result["result"])
        except (json.JSONDecodeError, KeyError):
            return self._create_basic_implementation_plan(selected_option)
    
    async def _gather_historical_insights(self, decision_type: DecisionType) -> Dict[str, Any]:
        """Gather insights from historical decisions of similar type."""
        
        historical_decisions = [
            result for result in self.decision_history
            if result.request_id in self.active_decisions and 
            self.active_decisions[result.request_id].decision_type == decision_type
        ]
        
        if not historical_decisions:
            return {"insights": [], "patterns": [], "lessons_learned": []}
        
        # Analyze success patterns
        successful_decisions = [
            d for d in historical_decisions 
            if d.confidence_score > 0.8
        ]
        
        # Extract common patterns
        patterns = self._extract_decision_patterns(successful_decisions)
        
        return {
            "total_decisions": len(historical_decisions),
            "successful_decisions": len(successful_decisions),
            "success_rate": len(successful_decisions) / len(historical_decisions),
            "patterns": patterns,
            "insights": self._generate_historical_insights(historical_decisions),
            "lessons_learned": self._extract_lessons_learned(historical_decisions)
        }
    
    async def _analyze_environmental_factors(self, context: DecisionContext) -> Dict[str, Any]:
        """Analyze environmental factors that may impact the decision."""
        
        return {
            "resource_availability": self._assess_resource_availability(context.available_resources),
            "constraint_severity": self._assess_constraint_severity(context.constraints),
            "stakeholder_alignment": self._assess_stakeholder_alignment(context.stakeholders),
            "urgency_pressure": self._assess_urgency_pressure(context.urgency),
            "environmental_stability": self._assess_environmental_stability(context.environmental_factors)
        }
    
    def _generate_decision_reasoning(
        self, 
        request: DecisionRequest, 
        analysis: Dict[str, Any]
    ) -> str:
        """Generate human-readable reasoning for the decision."""
        
        key_factors = analysis.get("key_factors", [])
        risk_analysis = analysis.get("risk_analysis", {})
        opportunity_analysis = analysis.get("opportunity_analysis", {})
        
        reasoning_parts = [
            f"Decision for {request.decision_type.value} with {request.context.urgency.value} urgency.",
            f"Key factors considered: {', '.join(key_factors[:3])}." if key_factors else "",
            f"Primary risks: {', '.join(risk_analysis.get('primary_risks', [])[:2])}." if risk_analysis else "",
            f"Main opportunities: {', '.join(opportunity_analysis.get('primary_opportunities', [])[:2])}." if opportunity_analysis else "",
            "AI-powered analysis optimized for multi-criteria decision making."
        ]
        
        return " ".join(part for part in reasoning_parts if part)
    
    async def _update_learning_database(
        self, 
        request: DecisionRequest, 
        result: DecisionResult
    ):
        """Update the learning database with decision outcomes."""
        
        learning_entry = {
            "decision_type": request.decision_type.value,
            "context_signature": self._generate_context_signature(request.context),
            "selected_option": result.selected_option.name,
            "confidence_score": result.confidence_score,
            "implementation_success": None,  # To be updated later
            "stakeholder_satisfaction": None,  # To be updated later
            "lessons_learned": [],
            "timestamp": result.decided_at.isoformat()
        }
        
        self.learning_database[request.decision_type.value].append(learning_entry)
        
        # Maintain database size limits
        if len(self.learning_database[request.decision_type.value]) > 100:
            self.learning_database[request.decision_type.value] = \
                self.learning_database[request.decision_type.value][-100:]
    
    # Helper methods for analysis and evaluation
    
    def _create_basic_context_analysis(self, request: DecisionRequest) -> Dict[str, Any]:
        """Create basic context analysis as fallback."""
        return {
            "key_factors": ["urgency", "resources", "constraints"],
            "risk_analysis": {"primary_risks": ["implementation_risk", "resource_risk"]},
            "opportunity_analysis": {"primary_opportunities": ["process_improvement"]},
            "reasoning": f"Basic analysis for {request.decision_type.value} decision"
        }
    
    def _create_basic_option_evaluation(self, option: DecisionOption) -> Dict[str, Any]:
        """Create basic option evaluation as fallback."""
        return {
            "effectiveness_score": 70,
            "feasibility_score": 75,
            "risk_score": 30,
            "strategic_alignment": 60,
            "strengths": ["viable_solution"],
            "weaknesses": ["requires_validation"]
        }
    
    def _create_basic_implementation_plan(self, option: DecisionOption) -> Dict[str, Any]:
        """Create basic implementation plan as fallback."""
        return {
            "implementation_steps": [
                "Prepare implementation",
                "Execute decision",
                "Monitor results",
                "Optimize as needed"
            ],
            "timeline": {"estimated_duration": option.time_to_implement},
            "success_criteria": ["implementation_completed", "objectives_met"],
            "monitoring_plan": {"frequency": "daily", "metrics": ["progress", "issues"]}
        }
    
    async def _evaluate_custom_criterion(
        self, 
        option: DecisionOption, 
        criterion: DecisionCriteria,
        context_analysis: Dict[str, Any]
    ) -> float:
        """Evaluate option against custom criterion."""
        # Placeholder for custom evaluation logic
        return 0.7
    
    async def _evaluate_standard_criterion(
        self, 
        option: DecisionOption, 
        criterion: DecisionCriteria,
        context_analysis: Dict[str, Any]
    ) -> float:
        """Evaluate option against standard criterion."""
        # Basic scoring based on criterion type
        if "cost" in criterion.name.lower():
            return max(0.0, 1.0 - (option.implementation_cost / 100000.0))
        elif "risk" in criterion.name.lower():
            return 1.0 - option.risk_assessment.get("overall_risk", 0.5)
        elif "time" in criterion.name.lower():
            return max(0.0, 1.0 - (option.time_to_implement / 1440.0))  # 1 day = 1440 minutes
        else:
            return 0.7  # Default score
    
    def _extract_decision_patterns(self, decisions: List[DecisionResult]) -> List[str]:
        """Extract common patterns from successful decisions."""
        patterns = []
        if decisions:
            avg_confidence = sum(d.confidence_score for d in decisions) / len(decisions)
            if avg_confidence > 0.8:
                patterns.append("high_confidence_decisions_successful")
            
            reversible_decisions = [d for d in decisions if d.selected_option.reversibility]
            if len(reversible_decisions) / len(decisions) > 0.7:
                patterns.append("reversible_options_preferred")
        
        return patterns
    
    def _generate_historical_insights(self, decisions: List[DecisionResult]) -> List[str]:
        """Generate insights from historical decision data."""
        insights = []
        if decisions:
            avg_implementation_time = sum(
                d.selected_option.time_to_implement for d in decisions
            ) / len(decisions)
            insights.append(f"Average implementation time: {avg_implementation_time:.0f} minutes")
            
            high_confidence_rate = len([
                d for d in decisions if d.confidence_score > 0.8
            ]) / len(decisions)
            insights.append(f"High confidence rate: {high_confidence_rate:.1%}")
        
        return insights
    
    def _extract_lessons_learned(self, decisions: List[DecisionResult]) -> List[str]:
        """Extract lessons learned from historical decisions."""
        lessons = []
        if decisions:
            lessons.append("Consider implementation complexity in evaluation")
            lessons.append("Stakeholder alignment critical for success")
            lessons.append("Monitor early indicators for course correction")
        
        return lessons
    
    def _generate_context_signature(self, context: DecisionContext) -> str:
        """Generate a signature for decision context for pattern matching."""
        factors = [
            context.decision_type.value,
            context.urgency.value,
            str(len(context.stakeholders)),
            str(len(context.constraints))
        ]
        return "|".join(factors)
    
    def _assess_resource_availability(self, resources: Dict[str, Any]) -> str:
        """Assess availability of resources."""
        if not resources:
            return "limited"
        
        resource_count = len(resources)
        if resource_count > 5:
            return "abundant"
        elif resource_count > 2:
            return "adequate"
        else:
            return "limited"
    
    def _assess_constraint_severity(self, constraints: Dict[str, Any]) -> str:
        """Assess severity of constraints."""
        if not constraints:
            return "minimal"
        
        constraint_count = len(constraints)
        if constraint_count > 5:
            return "severe"
        elif constraint_count > 2:
            return "moderate"
        else:
            return "minimal"
    
    def _assess_stakeholder_alignment(self, stakeholders: List[str]) -> str:
        """Assess stakeholder alignment potential."""
        stakeholder_count = len(stakeholders)
        if stakeholder_count > 10:
            return "complex"
        elif stakeholder_count > 5:
            return "moderate"
        else:
            return "simple"
    
    def _assess_urgency_pressure(self, urgency: DecisionUrgency) -> str:
        """Assess pressure from urgency level."""
        if urgency == DecisionUrgency.CRITICAL:
            return "extreme"
        elif urgency == DecisionUrgency.HIGH:
            return "high"
        elif urgency == DecisionUrgency.MEDIUM:
            return "moderate"
        else:
            return "low"
    
    def _assess_environmental_stability(self, factors: Dict[str, Any]) -> str:
        """Assess environmental stability."""
        if not factors:
            return "stable"
        
        # Simple assessment based on factor count and types
        instability_indicators = len([
            f for f in factors.keys() 
            if any(word in f.lower() for word in ["volatile", "changing", "uncertain"])
        ])
        
        if instability_indicators > 2:
            return "unstable"
        elif instability_indicators > 0:
            return "moderate"
        else:
            return "stable"
    
    # Public API methods
    
    async def get_decision_status(self, request_id: str) -> Dict[str, Any]:
        """Get the status of a decision request."""
        if request_id in self.active_decisions:
            return {
                "status": "active",
                "request": self.active_decisions[request_id],
                "progress": "analyzing"
            }
        
        # Look for completed decision
        for decision in self.decision_history:
            if decision.request_id == request_id:
                return {
                    "status": "completed",
                    "result": decision,
                    "progress": "done"
                }
        
        return {"status": "not_found"}
    
    async def get_decision_recommendations(
        self, 
        decision_type: DecisionType,
        context_summary: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get recommendations for decision making based on historical patterns."""
        
        historical_data = self.learning_database.get(decision_type.value, [])
        
        recommendations = [
            {
                "recommendation": "Consider implementation complexity early",
                "confidence": 0.8,
                "based_on": "historical_analysis"
            },
            {
                "recommendation": "Ensure stakeholder alignment before proceeding",
                "confidence": 0.9,
                "based_on": "success_patterns"
            },
            {
                "recommendation": "Plan for monitoring and adjustment",
                "confidence": 0.85,
                "based_on": "best_practices"
            }
        ]
        
        return recommendations
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get decision engine performance metrics."""
        
        total_decisions = len(self.decision_history)
        if total_decisions == 0:
            return {"total_decisions": 0, "metrics": "insufficient_data"}
        
        avg_confidence = sum(d.confidence_score for d in self.decision_history) / total_decisions
        
        decision_types = defaultdict(int)
        for decision in self.decision_history:
            if decision.request_id in self.active_decisions:
                decision_type = self.active_decisions[decision.request_id].decision_type.value
                decision_types[decision_type] += 1
        
        return {
            "total_decisions": total_decisions,
            "average_confidence": avg_confidence,
            "decisions_by_type": dict(decision_types),
            "active_decisions": len(self.active_decisions),
            "learning_database_size": sum(len(entries) for entries in self.learning_database.values())
        }


# Factory function for easy integration
async def create_decision_engine(claude_api_key: Optional[str] = None) -> DecisionEngine:
    """Factory function to create configured decision engine."""
    
    claude_agent = ClaudeAgentWrapper(api_key=claude_api_key)
    return DecisionEngine(claude_agent)
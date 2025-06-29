"""
Human-Loop Intelligence Detector

This module provides AI-powered detection of when human intervention is needed
and generates dynamic approval workflows. It goes beyond simple rules to 
intelligent analysis of risk, complexity, and organizational context.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

import structlog
from pydantic import BaseModel, Field

from supervisor_agent.intelligence.workflow_synthesizer import (
    RequirementAnalysis, TenantContext, ClaudeAgentWrapper
)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
structured_logger = structlog.get_logger(__name__)


class RiskLevel(Enum):
    """Risk levels for human involvement decisions"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalUrgency(Enum):
    """Urgency levels for approvals"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class HumanInvolvementType(Enum):
    """Types of human involvement"""
    APPROVAL = "approval"
    REVIEW = "review"
    CONSULTATION = "consultation"
    OVERSIGHT = "oversight"
    ESCALATION = "escalation"


@dataclass
class RiskFactor:
    """Individual risk factor assessment"""
    factor_name: str
    risk_level: RiskLevel
    description: str
    mitigation_possible: bool
    human_expertise_required: bool
    confidence_score: float


@dataclass
class HumanInvolvementPoint:
    """A point where human involvement may be needed"""
    checkpoint_id: str
    involvement_type: HumanInvolvementType
    urgency: ApprovalUrgency
    required_roles: List[str]
    context: Dict[str, Any]
    can_be_parallelized: bool
    bypass_conditions: Dict[str, Any]
    escalation_triggers: List[str]
    estimated_time_hours: float
    confidence_score: float


@dataclass
class HumanInvolvementAnalysis:
    """Complete analysis of human involvement requirements"""
    analysis_id: str
    requirements: RequirementAnalysis
    team_context: TenantContext
    risk_assessment: List[RiskFactor]
    involvement_points: List[HumanInvolvementPoint]
    autonomous_capabilities: Dict[str, Any]
    recommendations: Dict[str, Any]
    confidence_score: float
    analysis_timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "requirements": self.requirements.to_dict(),
            "team_context": self.team_context.to_dict(),
            "risk_assessment": [asdict(risk) for risk in self.risk_assessment],
            "involvement_points": [asdict(point) for point in self.involvement_points],
            "autonomous_capabilities": self.autonomous_capabilities,
            "recommendations": self.recommendations,
            "confidence_score": self.confidence_score,
            "analysis_timestamp": self.analysis_timestamp.isoformat()
        }
    
    @classmethod
    def from_claude_response(cls, response: str, requirements: RequirementAnalysis, 
                           team_context: TenantContext) -> 'HumanInvolvementAnalysis':
        """Create analysis from Claude response"""
        try:
            data = json.loads(response)
            
            # Parse risk assessment
            risk_assessment = []
            for risk_data in data.get("risk_assessment", []):
                risk_factor = RiskFactor(
                    factor_name=risk_data.get("factor_name", "unknown"),
                    risk_level=RiskLevel(risk_data.get("risk_level", "medium")),
                    description=risk_data.get("description", ""),
                    mitigation_possible=risk_data.get("mitigation_possible", True),
                    human_expertise_required=risk_data.get("human_expertise_required", False),
                    confidence_score=risk_data.get("confidence_score", 0.5)
                )
                risk_assessment.append(risk_factor)
            
            # Parse involvement points
            involvement_points = []
            for point_data in data.get("involvement_points", []):
                involvement_point = HumanInvolvementPoint(
                    checkpoint_id=point_data.get("checkpoint_id", str(uuid.uuid4())),
                    involvement_type=HumanInvolvementType(point_data.get("involvement_type", "review")),
                    urgency=ApprovalUrgency(point_data.get("urgency", "normal")),
                    required_roles=point_data.get("required_roles", []),
                    context=point_data.get("context", {}),
                    can_be_parallelized=point_data.get("can_be_parallelized", False),
                    bypass_conditions=point_data.get("bypass_conditions", {}),
                    escalation_triggers=point_data.get("escalation_triggers", []),
                    estimated_time_hours=point_data.get("estimated_time_hours", 1.0),
                    confidence_score=point_data.get("confidence_score", 0.5)
                )
                involvement_points.append(involvement_point)
            
            return cls(
                analysis_id=str(uuid.uuid4()),
                requirements=requirements,
                team_context=team_context,
                risk_assessment=risk_assessment,
                involvement_points=involvement_points,
                autonomous_capabilities=data.get("autonomous_capabilities", {}),
                recommendations=data.get("recommendations", {}),
                confidence_score=data.get("confidence_score", 0.5),
                analysis_timestamp=datetime.now(timezone.utc)
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Return fallback analysis
            return cls._create_fallback_analysis(requirements, team_context, str(e))
    
    @classmethod
    def _create_fallback_analysis(cls, requirements: RequirementAnalysis, 
                                team_context: TenantContext, error: str) -> 'HumanInvolvementAnalysis':
        """Create fallback analysis when parsing fails"""
        
        # Conservative fallback - require human review for everything
        involvement_point = HumanInvolvementPoint(
            checkpoint_id=str(uuid.uuid4()),
            involvement_type=HumanInvolvementType.REVIEW,
            urgency=ApprovalUrgency.NORMAL,
            required_roles=["project_lead"],
            context={"fallback_reason": error},
            can_be_parallelized=False,
            bypass_conditions={},
            escalation_triggers=["timeout", "failure"],
            estimated_time_hours=2.0,
            confidence_score=0.1
        )
        
        return cls(
            analysis_id=str(uuid.uuid4()),
            requirements=requirements,
            team_context=team_context,
            risk_assessment=[],
            involvement_points=[involvement_point],
            autonomous_capabilities={},
            recommendations={"error": "fallback_analysis_used", "reason": error},
            confidence_score=0.1,
            analysis_timestamp=datetime.now(timezone.utc)
        )


@dataclass
class ApprovalStep:
    """Individual step in approval workflow"""
    step_id: str
    step_name: str
    required_roles: List[str]
    parallel_with: List[str]
    depends_on: List[str]
    auto_approve_conditions: Dict[str, Any]
    timeout_hours: float
    escalation_target: Optional[str]


@dataclass
class ApprovalWorkflow:
    """Dynamic approval workflow"""
    workflow_id: str
    name: str
    description: str
    steps: List[ApprovalStep]
    parallel_groups: List[List[str]]
    total_estimated_time_hours: float
    bypass_conditions: Dict[str, Any]
    emergency_override: Dict[str, Any]
    
    @classmethod
    def from_claude_response(cls, response: str) -> 'ApprovalWorkflow':
        """Create approval workflow from Claude response"""
        try:
            data = json.loads(response)
            
            steps = []
            for step_data in data.get("steps", []):
                step = ApprovalStep(
                    step_id=step_data.get("step_id", str(uuid.uuid4())),
                    step_name=step_data.get("step_name", "Approval Step"),
                    required_roles=step_data.get("required_roles", []),
                    parallel_with=step_data.get("parallel_with", []),
                    depends_on=step_data.get("depends_on", []),
                    auto_approve_conditions=step_data.get("auto_approve_conditions", {}),
                    timeout_hours=step_data.get("timeout_hours", 24.0),
                    escalation_target=step_data.get("escalation_target")
                )
                steps.append(step)
            
            return cls(
                workflow_id=str(uuid.uuid4()),
                name=data.get("name", "Dynamic Approval Workflow"),
                description=data.get("description", ""),
                steps=steps,
                parallel_groups=data.get("parallel_groups", []),
                total_estimated_time_hours=data.get("total_estimated_time_hours", 8.0),
                bypass_conditions=data.get("bypass_conditions", {}),
                emergency_override=data.get("emergency_override", {})
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            return cls._create_fallback_workflow(str(e))
    
    @classmethod
    def _create_fallback_workflow(cls, error: str) -> 'ApprovalWorkflow':
        """Create fallback workflow when parsing fails"""
        
        fallback_step = ApprovalStep(
            step_id=str(uuid.uuid4()),
            step_name="Manual Review Required",
            required_roles=["admin"],
            parallel_with=[],
            depends_on=[],
            auto_approve_conditions={},
            timeout_hours=48.0,
            escalation_target=None
        )
        
        return cls(
            workflow_id=str(uuid.uuid4()),
            name="Fallback Approval Workflow",
            description=f"Fallback workflow due to parsing error: {error}",
            steps=[fallback_step],
            parallel_groups=[],
            total_estimated_time_hours=48.0,
            bypass_conditions={},
            emergency_override={"admin_override": True}
        )


class DecisionHistory:
    """Manages historical decision data for learning"""
    
    def __init__(self):
        self._history_cache = {}
    
    async def get_similar_projects(self, requirements: RequirementAnalysis) -> List[Dict[str, Any]]:
        """Get similar historical projects for reference"""
        # TODO: Implement similarity search in long-term memory
        return []
    
    async def record_decision_outcome(self, analysis_id: str, actual_outcome: Dict[str, Any]):
        """Record the actual outcome of a human involvement decision"""
        # TODO: Implement outcome recording for learning
        pass


class RiskAnalyzer:
    """Analyzes risk factors for human involvement decisions"""
    
    def __init__(self):
        self.risk_thresholds = {
            "complexity_high": 0.8,
            "security_sensitive": 0.9,
            "business_critical": 0.85,
            "regulatory_impact": 0.95
        }
    
    async def assess_risks(self, requirements: RequirementAnalysis) -> Dict[str, Any]:
        """Assess various risk factors"""
        
        risks = {
            "complexity_risk": self._assess_complexity_risk(requirements),
            "security_risk": self._assess_security_risk(requirements),
            "business_risk": self._assess_business_risk(requirements),
            "technical_risk": self._assess_technical_risk(requirements),
            "timeline_risk": self._assess_timeline_risk(requirements)
        }
        
        # Calculate overall risk score
        risk_scores = [risk.get("score", 0.0) for risk in risks.values()]
        overall_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0
        
        risks["overall_risk"] = {
            "score": overall_risk,
            "level": self._score_to_level(overall_risk),
            "description": "Overall risk assessment"
        }
        
        return risks
    
    def _assess_complexity_risk(self, requirements: RequirementAnalysis) -> Dict[str, Any]:
        """Assess complexity-based risk"""
        complexity_scores = {
            "simple": 0.2,
            "moderate": 0.5,
            "complex": 0.8,
            "enterprise": 0.9
        }
        
        score = complexity_scores.get(requirements.complexity.value, 0.5)
        
        return {
            "score": score,
            "level": self._score_to_level(score),
            "factors": ["task_complexity", "dependency_count", "skill_requirements"],
            "description": f"Complexity level: {requirements.complexity.value}"
        }
    
    def _assess_security_risk(self, requirements: RequirementAnalysis) -> Dict[str, Any]:
        """Assess security-related risk"""
        security_keywords = ["security", "auth", "encryption", "sensitive", "private"]
        
        has_security_aspects = any(
            keyword in requirements.description.lower() 
            for keyword in security_keywords
        )
        
        score = 0.8 if has_security_aspects else 0.3
        
        return {
            "score": score,
            "level": self._score_to_level(score),
            "factors": ["data_sensitivity", "access_control", "compliance"],
            "description": "Security impact assessment"
        }
    
    def _assess_business_risk(self, requirements: RequirementAnalysis) -> Dict[str, Any]:
        """Assess business impact risk"""
        business_keywords = ["critical", "production", "revenue", "customer", "public"]
        
        has_business_impact = any(
            keyword in requirements.description.lower() 
            for keyword in business_keywords
        )
        
        score = 0.7 if has_business_impact else 0.4
        
        return {
            "score": score,
            "level": self._score_to_level(score),
            "factors": ["business_impact", "customer_facing", "revenue_impact"],
            "description": "Business impact assessment"
        }
    
    def _assess_technical_risk(self, requirements: RequirementAnalysis) -> Dict[str, Any]:
        """Assess technical risk"""
        technical_factors = len(requirements.dependencies) + len(requirements.required_skills)
        
        # Normalize to 0-1 scale
        score = min(technical_factors / 10.0, 1.0)
        
        return {
            "score": score,
            "level": self._score_to_level(score),
            "factors": ["dependency_complexity", "skill_requirements", "integration_points"],
            "description": "Technical complexity assessment"
        }
    
    def _assess_timeline_risk(self, requirements: RequirementAnalysis) -> Dict[str, Any]:
        """Assess timeline-related risk"""
        # Higher duration increases risk due to uncertainty
        duration_score = min(requirements.estimated_duration_hours / 100.0, 1.0)
        
        return {
            "score": duration_score,
            "level": self._score_to_level(duration_score),
            "factors": ["duration_uncertainty", "deadline_pressure", "resource_availability"],
            "description": "Timeline risk assessment"
        }
    
    def _score_to_level(self, score: float) -> RiskLevel:
        """Convert numeric score to risk level"""
        if score < 0.3:
            return RiskLevel.LOW
        elif score < 0.6:
            return RiskLevel.MEDIUM
        elif score < 0.8:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL


class HumanLoopIntelligenceDetector:
    """
    AI-powered detection of when human intervention is needed.
    
    Goes beyond simple rules to intelligent analysis of risk, complexity,
    organizational context, and historical patterns.
    """
    
    def __init__(self, claude_agent: ClaudeAgentWrapper):
        self.claude_agent = claude_agent
        self.risk_analyzer = RiskAnalyzer()
        self.decision_history = DecisionHistory()
        self.logger = structured_logger.bind(component="human_loop_detector")
    
    async def analyze_human_involvement_need(self,
                                           requirements: RequirementAnalysis,
                                           team_context: TenantContext) -> HumanInvolvementAnalysis:
        """Intelligent analysis of human involvement requirements"""
        
        self.logger.info("Starting human involvement analysis",
                        requirements_domain=requirements.domain.value,
                        complexity=requirements.complexity.value)
        
        try:
            # Assess risks comprehensively
            risk_assessment = await self.risk_analyzer.assess_risks(requirements)
            
            # Get historical context
            historical_projects = await self.decision_history.get_similar_projects(requirements)
            
            # Build analysis context
            analysis_context = {
                "requirements": requirements.to_dict(),
                "team_context": team_context.to_dict(),
                "risk_assessment": self._serialize_risk_assessment(risk_assessment),
                "historical_projects": historical_projects,
                "organizational_policies": team_context.approval_policies
            }
            
            # Get AI analysis from Claude
            claude_analysis = await self._get_claude_analysis(analysis_context)
            
            # Parse and create structured analysis
            analysis = HumanInvolvementAnalysis.from_claude_response(
                claude_analysis["result"], requirements, team_context
            )
            
            self.logger.info("Human involvement analysis completed",
                           analysis_id=analysis.analysis_id,
                           involvement_points=len(analysis.involvement_points),
                           confidence=analysis.confidence_score)
            
            return analysis
            
        except Exception as e:
            self.logger.error("Human involvement analysis failed", error=str(e))
            return HumanInvolvementAnalysis._create_fallback_analysis(
                requirements, team_context, str(e)
            )
    
    async def generate_dynamic_approval_workflow(self,
                                               involvement_analysis: HumanInvolvementAnalysis) -> ApprovalWorkflow:
        """Generate intelligent approval workflow based on analysis"""
        
        self.logger.info("Generating dynamic approval workflow",
                        analysis_id=involvement_analysis.analysis_id)
        
        try:
            # Build workflow generation context
            workflow_context = {
                "involvement_analysis": self._serialize_involvement_analysis(involvement_analysis.to_dict()),
                "optimization_goals": {
                    "minimize_bottlenecks": True,
                    "maximize_parallelization": True,
                    "respect_org_hierarchy": True,
                    "enable_auto_approval": True
                }
            }
            
            # Get workflow design from Claude
            workflow_result = await self._get_workflow_design(workflow_context)
            
            # Parse and create workflow
            workflow = ApprovalWorkflow.from_claude_response(workflow_result["result"])
            
            self.logger.info("Dynamic approval workflow generated",
                           workflow_id=workflow.workflow_id,
                           steps=len(workflow.steps),
                           estimated_hours=workflow.total_estimated_time_hours)
            
            return workflow
            
        except Exception as e:
            self.logger.error("Approval workflow generation failed", error=str(e))
            return ApprovalWorkflow._create_fallback_workflow(str(e))
    
    async def evaluate_bypass_conditions(self,
                                       analysis: HumanInvolvementAnalysis,
                                       current_context: Dict[str, Any]) -> Dict[str, bool]:
        """Evaluate if human involvement can be bypassed"""
        
        bypass_results = {}
        
        for point in analysis.involvement_points:
            can_bypass = await self._evaluate_point_bypass(point, current_context)
            bypass_results[point.checkpoint_id] = can_bypass
        
        return bypass_results
    
    async def detect_escalation_triggers(self,
                                       execution_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect conditions that trigger human escalation"""
        
        triggers = []
        
        # Check for common escalation conditions
        if execution_context.get("failure_count", 0) > 3:
            triggers.append({
                "type": "repeated_failures",
                "urgency": "high",
                "description": "Multiple task failures detected"
            })
        
        if execution_context.get("execution_time_ratio", 1.0) > 2.0:
            triggers.append({
                "type": "timeline_overrun",
                "urgency": "medium", 
                "description": "Execution taking significantly longer than expected"
            })
        
        if execution_context.get("error_rate", 0.0) > 0.3:
            triggers.append({
                "type": "high_error_rate",
                "urgency": "high",
                "description": "High error rate detected in workflow execution"
            })
        
        return triggers
    
    async def _get_claude_analysis(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get human involvement analysis from Claude"""
        
        analysis_prompt = f"""
        Analyze whether human involvement is needed for this project:
        
        Project Requirements: {json.dumps(context["requirements"], indent=2)}
        Risk Assessment: {json.dumps(context["risk_assessment"], indent=2)}
        Team Context: {json.dumps(context["team_context"], indent=2)}
        Organizational Policies: {json.dumps(context["organizational_policies"], indent=2)}
        Similar Historical Projects: {json.dumps(context["historical_projects"], indent=2)}
        
        For each potential human checkpoint, analyze:
        1. Is human expertise actually needed, or can AI handle it?
        2. What specific value does human input provide?
        3. What are the risks of proceeding without human input?
        4. Who is the most qualified person for this decision?
        5. How urgent is this checkpoint?
        6. Can this be parallelized with other work?
        7. What conditions would allow bypassing this checkpoint?
        
        Provide analysis in JSON format with:
        - risk_assessment: array of risk factors with scores
        - involvement_points: array of human involvement checkpoints
        - autonomous_capabilities: what AI can handle independently
        - recommendations: specific recommendations for optimization
        - confidence_score: confidence in this analysis (0-1)
        
        For each involvement_point, include:
        - checkpoint_id: unique identifier
        - involvement_type: approval|review|consultation|oversight|escalation
        - urgency: low|normal|high|critical
        - required_roles: array of required roles/skills
        - context: additional context for decision makers
        - can_be_parallelized: boolean
        - bypass_conditions: conditions that allow skipping
        - escalation_triggers: conditions that escalate urgency
        - estimated_time_hours: time estimate
        - confidence_score: confidence in this specific point
        
        Focus on minimizing unnecessary human bottlenecks while ensuring quality and compliance.
        """
        
        return await self.claude_agent.execute_task({
            "type": "human_loop_analysis",
            "prompt": analysis_prompt
        }, shared_memory=context)
    
    async def _get_workflow_design(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get approval workflow design from Claude"""
        
        workflow_prompt = f"""
        Create an optimal approval workflow based on this analysis:
        
        Human Involvement Analysis: {json.dumps(context["involvement_analysis"], indent=2)}
        Optimization Goals: {json.dumps(context["optimization_goals"], indent=2)}
        
        Design a workflow that:
        1. Minimizes human bottlenecks through parallelization
        2. Routes decisions to the most qualified experts
        3. Provides clear context and recommendations to humans
        4. Has intelligent escalation paths
        5. Includes timeout handling and auto-approvals where safe
        6. Maximizes autonomous work while ensuring quality
        7. Respects organizational hierarchy and policies
        
        Return structured approval workflow in JSON format with:
        - name: descriptive workflow name
        - description: workflow purpose and scope
        - steps: array of approval steps
        - parallel_groups: groups of steps that can run in parallel
        - total_estimated_time_hours: total time estimate
        - bypass_conditions: conditions that allow skipping entire workflow
        - emergency_override: emergency procedures
        
        For each step include:
        - step_id: unique identifier
        - step_name: descriptive name
        - required_roles: roles that can approve this step
        - parallel_with: other steps this can run parallel with
        - depends_on: prerequisite steps
        - auto_approve_conditions: conditions for automatic approval
        - timeout_hours: timeout before escalation
        - escalation_target: who to escalate to on timeout
        
        Optimize for speed while maintaining quality and compliance.
        """
        
        return await self.claude_agent.execute_task({
            "type": "approval_workflow_generation",
            "prompt": workflow_prompt
        }, shared_memory=context)
    
    async def _evaluate_point_bypass(self,
                                   point: HumanInvolvementPoint,
                                   current_context: Dict[str, Any]) -> bool:
        """Evaluate if a specific involvement point can be bypassed"""
        
        # Check bypass conditions
        bypass_conditions = point.bypass_conditions
        
        for condition_key, condition_value in bypass_conditions.items():
            context_value = current_context.get(condition_key)
            
            if condition_key == "quality_score_above":
                if context_value and context_value >= condition_value:
                    continue
                else:
                    return False
            elif condition_key == "automated_tests_pass":
                if context_value and condition_value:
                    continue
                else:
                    return False
            elif condition_key == "low_risk_assessment":
                if context_value and context_value <= condition_value:
                    continue
                else:
                    return False
            else:
                # Generic equality check
                if context_value == condition_value:
                    continue
                else:
                    return False
        
        return True  # All bypass conditions met
    
    def _serialize_risk_assessment(self, risk_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Convert risk assessment with enums to JSON-serializable format"""
        serialized = {}
        
        for risk_type, risk_data in risk_assessment.items():
            if isinstance(risk_data, dict):
                serialized_risk = {}
                for key, value in risk_data.items():
                    if hasattr(value, 'value'):  # It's an enum
                        serialized_risk[key] = value.value
                    else:
                        serialized_risk[key] = value
                serialized[risk_type] = serialized_risk
            else:
                serialized[risk_type] = risk_data
                
        return serialized
    
    def _serialize_involvement_analysis(self, analysis_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Convert involvement analysis with enums to JSON-serializable format"""
        serialized = {}
        
        for key, value in analysis_dict.items():
            if key == "involvement_points" and isinstance(value, list):
                serialized_points = []
                for point in value:
                    if isinstance(point, dict):
                        serialized_point = {}
                        for point_key, point_value in point.items():
                            if hasattr(point_value, 'value'):  # It's an enum
                                serialized_point[point_key] = point_value.value
                            else:
                                serialized_point[point_key] = point_value
                        serialized_points.append(serialized_point)
                    else:
                        serialized_points.append(point)
                serialized[key] = serialized_points
            elif key == "risk_assessment" and isinstance(value, list):
                serialized_risks = []
                for risk in value:
                    if isinstance(risk, dict):
                        serialized_risk = {}
                        for risk_key, risk_value in risk.items():
                            if hasattr(risk_value, 'value'):  # It's an enum
                                serialized_risk[risk_key] = risk_value.value
                            else:
                                serialized_risk[risk_key] = risk_value
                        serialized_risks.append(serialized_risk)
                    else:
                        serialized_risks.append(risk)
                serialized[key] = serialized_risks
            else:
                serialized[key] = value
                
        return serialized


# Factory function for easy integration
async def create_human_loop_detector(claude_api_key: Optional[str] = None) -> HumanLoopIntelligenceDetector:
    """Factory function to create configured human loop detector"""
    
    claude_agent = ClaudeAgentWrapper(api_key=claude_api_key)
    return HumanLoopIntelligenceDetector(claude_agent)
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ExecutiveSummary(BaseModel):
    """Executive summary fields tailored for non-technical stakeholders."""

    headline: str
    what_happened: str
    business_impact: str
    immediate_actions_taken: str
    key_recommendations: List[str] = Field(..., min_length=1)


class TechnicalReport(BaseModel):
    """Detailed technical assessment of the incident."""

    incident_overview: str
    timeline_summary: str
    attack_description: str
    root_cause: str
    blast_radius_summary: str


class RemediationActionItem(BaseModel):
    """Actionable mitigation step assigned and scoped."""

    action_id: str
    priority: Literal["immediate", "short_term", "long_term"]
    category: Literal[
        "access_control",
        "patching",
        "monitoring",
        "process",
        "training",
        "configuration",
        "third_party",
    ]
    title: str
    description: str
    owner: str
    estimated_effort: str
    verification_method: str


class ComplianceAction(BaseModel):
    """Required reporting and action obligations generated under compliance rules."""

    regulation: str
    action_required: str
    deadline: str
    responsible_party: str


class ConfidenceBreakdown(BaseModel):
    """Breakdown of confidence scores across the four agents and overall score."""

    agent1_forensic: float = Field(..., ge=0.0, le=1.0)
    agent2_attribution: float = Field(..., ge=0.0, le=1.0)
    agent3_impact: float = Field(..., ge=0.0, le=1.0)
    agent4_postmortem: float = Field(..., ge=0.0, le=1.0)
    overall: float = Field(..., ge=0.0, le=1.0)


class PostMortemReport(BaseModel):
    """Authoritative post-incident post-mortem report and mitigations."""

    report_version: str = "1.0"
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    overall_severity: Literal["low", "medium", "high", "critical"]
    executive_summary: ExecutiveSummary
    technical_report: TechnicalReport
    remediation_plan: List[RemediationActionItem] = Field(..., min_length=1)
    lessons_learned: List[str] = Field(default_factory=list)
    compliance_actions: List[ComplianceAction] = Field(default_factory=list)
    confidence_breakdown: ConfidenceBreakdown
    agent_notes: Optional[str] = ""

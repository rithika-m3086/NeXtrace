from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class BlastRadius(BaseModel):
    """Details of the systems and users affected by the breach."""

    systems_compromised: List[str] = Field(..., min_length=1)
    systems_compromised_count: int = Field(..., ge=0)
    users_affected: List[str] = Field(default_factory=list)
    users_affected_count: int = Field(..., ge=0)
    estimated_records_exposed: int = Field(default=-1)  # Use -1 if unknown
    data_categories_exposed: List[
        Literal["pii", "financial", "health", "credentials", "ip", "internal", "public", "unknown"]
    ] = Field(default_factory=list)


class BusinessImpact(BaseModel):
    """Categorized business and operations impact."""

    severity: Literal["low", "medium", "high", "critical"]
    estimated_downtime_minutes: int = Field(default=0, ge=0)
    revenue_impact: Literal["none", "low", "medium", "high", "unknown"]
    reputational_risk: Literal["low", "medium", "high", "critical"]
    description: str


class ComplianceFlag(BaseModel):
    """Regulatory and compliance assessment flag."""

    regulation: Literal["GDPR", "HIPAA", "SOC2", "PCI_DSS", "CCPA", "none"]
    triggered: bool
    reason: str
    mandatory_notification: bool
    notification_deadline_hours: Optional[int] = None
    notification_recipients: List[str] = Field(default_factory=list)


class RootCauseFactor(BaseModel):
    """Individual root cause factor and its classification."""

    factor: str
    category: Literal["process", "technical", "human", "configuration", "third_party"]
    contributing_weight: Literal["primary", "contributing", "minor"]


class ImpactAssessment(BaseModel):
    """Schema for evaluating the blast radius, compliance, and severity."""

    pipeline_run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    blast_radius: BlastRadius
    business_impact: BusinessImpact
    compliance_flags: List[ComplianceFlag] = Field(default_factory=list)
    root_cause_factors: List[RootCauseFactor] = Field(default_factory=list)
    agent_notes: Optional[str] = ""

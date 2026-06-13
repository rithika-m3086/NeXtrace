from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class AttackClassification(BaseModel):
    """Classification details of the attack vector and actor."""

    attack_type: Literal[
        "credential_theft",
        "data_exfiltration",
        "ransomware",
        "insider_threat",
        "supply_chain",
        "brute_force",
        "sql_injection",
        "phishing",
        "misconfiguration",
        "unknown",
    ]
    threat_actor_type: Literal[
        "opportunistic", "targeted", "insider", "automated_bot", "unknown"
    ]
    sophistication_level: Literal["low", "medium", "high"]


class EntryPoint(BaseModel):
    """Details identifying the entry point of the breach."""

    identified: bool
    resource: str
    method: str
    first_seen: Optional[datetime] = None
    vulnerability_description: str


class AttackChainStep(BaseModel):
    """A single sequential step mapped to the MITRE ATT&CK matrix."""

    step: int = Field(..., ge=1)
    description: str
    mitre_technique_id: str  # e.g. T1078
    mitre_technique_name: str
    mitre_tactic: str  # e.g. Initial Access
    evidence_event_ids: List[str] = Field(default_factory=list)


class LateralMovement(BaseModel):
    """Traces lateral movement within the network."""

    detected: bool
    systems_traversed: List[str] = Field(default_factory=list)
    description: Optional[str] = ""


class DataTargeted(BaseModel):
    """Identifies targeted data systems and related evidence."""

    likely_target: str
    evidence: str


class IndicatorOfCompromise(BaseModel):
    """Indicator of Compromise (IoC) extracted from logs."""

    ioc_type: Literal["ip_address", "domain", "file_hash", "user_account", "api_key", "url"]
    value: str
    description: str


class AttributionReport(BaseModel):
    """Schema for the attack attribution and MITRE ATT&CK mapping."""

    pipeline_run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    attack_classification: AttackClassification
    entry_point: EntryPoint
    attack_chain: List[AttackChainStep] = Field(..., min_length=1)
    lateral_movement: LateralMovement
    data_targeted: DataTargeted
    indicators_of_compromise: List[IndicatorOfCompromise] = Field(default_factory=list)
    agent_notes: Optional[str] = ""

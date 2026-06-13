from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator


class TimelineEvent(BaseModel):
    """A single parsed event in the incident timeline."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime
    event_type: Literal[
        "authentication",
        "access",
        "exfiltration",
        "lateral_movement",
        "persistence",
        "discovery",
        "execution",
        "unknown",
    ]
    source_ip: Optional[str] = None
    source_user: Optional[str] = None
    target_resource: str
    action: str
    outcome: Literal["success", "failure", "unknown"]
    severity: Literal["low", "medium", "high", "critical"]
    raw_log_reference: str
    flags: List[str] = Field(default_factory=list)


class Anomaly(BaseModel):
    """Anomalous pattern or indicator discovered during parsing."""

    anomaly_id: str
    description: str
    severity: Literal["low", "medium", "high", "critical"]
    related_event_ids: List[str] = Field(default_factory=list)


class ForensicTimeline(BaseModel):
    """Comprehensive chronological timeline of the incident."""

    incident_id: str
    pipeline_run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    raw_event_count: int = Field(..., ge=0)
    filtered_event_count: int = Field(..., ge=0)
    timeline_start: datetime
    timeline_end: datetime
    events: List[TimelineEvent] = Field(..., min_length=1)
    affected_systems: List[str] = Field(..., min_length=1)
    affected_users: List[str] = Field(default_factory=list)
    anomalies: List[Anomaly] = Field(default_factory=list)
    agent_notes: Optional[str] = ""

    @model_validator(mode="after")
    def sort_events_chronologically(self) -> "ForensicTimeline":
        """Ensures that the parsed timeline events are sorted by timestamp in ascending order."""
        self.events.sort(key=lambda x: x.timestamp)
        return self

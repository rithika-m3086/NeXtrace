from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class LogSource(BaseModel):
    """Represents a single source of raw log files/evidence."""

    source_name: str
    source_type: Literal[
        "cloudtrail", "s3_access", "github_audit", "firewall", "auth", "syslog", "custom"
    ]
    content: str
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None


class RawEvidenceInput(BaseModel):
    """Schema for raw security evidence submitted to the pipeline."""

    pipeline_run_id: str
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    organization_name: Optional[str] = "Unknown"
    incident_description: Optional[str] = ""
    log_sources: List[LogSource] = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)

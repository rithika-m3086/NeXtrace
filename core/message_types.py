from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


class BandMessage(BaseModel):
    """Standard message envelope for all messages sent over the Band platform."""

    message_id: UUID = Field(default_factory=uuid4)
    pipeline_run_id: str
    channel: str
    agent_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sequence: int
    status: Literal["success", "partial", "error"]
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        pipeline_run_id: str,
        agent_id: str,
        channel: str,
        sequence: int,
        status: Literal["success", "partial", "error"],
        confidence: float,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "BandMessage":
        """Factory method to construct a BandMessage with auto-set values."""
        return cls(
            pipeline_run_id=pipeline_run_id,
            agent_id=agent_id,
            channel=channel,
            sequence=sequence,
            status=status,
            confidence=confidence,
            payload=payload,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Pydantic model into a dictionary suitable for JSON serialization."""
        data = self.model_dump()
        # Convert UUID and datetime to string formats
        data["message_id"] = str(data["message_id"])
        data["timestamp"] = data["timestamp"].isoformat()
        return data

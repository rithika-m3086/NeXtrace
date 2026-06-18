import pytest
from pydantic import ValidationError
from datetime import datetime, timezone
from schemas.timeline_schema import ForensicTimeline
from schemas.attribution_schema import AttributionReport
from schemas.impact_schema import ImpactAssessment
from schemas.postmortem_schema import PostMortemReport
from core.message_types import BandMessage


def test_schemas_reject_empty_dicts():
    """Assert all schemas reject empty dicts by raising ValidationError."""
    for schema in [ForensicTimeline, AttributionReport, ImpactAssessment, PostMortemReport]:
        with pytest.raises(ValidationError):
            schema.model_validate({})


def test_confidence_score_boundaries():
    """Assert confidence_score boundaries are strictly enforced on ForensicTimeline."""
    valid_event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "access",
        "target_resource": "s3://bucket",
        "action": "GetObject",
        "outcome": "success",
        "severity": "low",
        "raw_log_reference": "{}"
    }
    base_ft = {
        "incident_id": "inc-123",
        "pipeline_run_id": "run-123",
        "confidence_score": 0.5,
        "raw_event_count": 1,
        "filtered_event_count": 1,
        "timeline_start": datetime.now(timezone.utc).isoformat(),
        "timeline_end": datetime.now(timezone.utc).isoformat(),
        "events": [valid_event],
        "affected_systems": ["s3"]
    }

    # 0.0 is valid
    ft_0 = dict(base_ft, confidence_score=0.0)
    assert ForensicTimeline.model_validate(ft_0).confidence_score == 0.0

    # 1.0 is valid
    ft_1 = dict(base_ft, confidence_score=1.0)
    assert ForensicTimeline.model_validate(ft_1).confidence_score == 1.0

    # 1.1 raises ValidationError
    ft_high = dict(base_ft, confidence_score=1.1)
    with pytest.raises(ValidationError):
        ForensicTimeline.model_validate(ft_high)

    # -0.1 raises ValidationError
    ft_low = dict(base_ft, confidence_score=-0.1)
    with pytest.raises(ValidationError):
        ForensicTimeline.model_validate(ft_low)


def test_event_type_enum_enforced():
    """Assert event_type enum is enforced on TimelineEvent in ForensicTimeline."""
    valid_event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "access",
        "target_resource": "s3://bucket",
        "action": "GetObject",
        "outcome": "success",
        "severity": "low",
        "raw_log_reference": "{}"
    }
    base_ft = {
        "incident_id": "inc-123",
        "pipeline_run_id": "run-123",
        "confidence_score": 0.5,
        "raw_event_count": 1,
        "filtered_event_count": 1,
        "timeline_start": datetime.now(timezone.utc).isoformat(),
        "timeline_end": datetime.now(timezone.utc).isoformat(),
        "events": [valid_event],
        "affected_systems": ["s3"]
    }

    # invalid event type raises ValidationError
    invalid_event = dict(valid_event, event_type="invalid_type")
    ft_invalid = dict(base_ft, events=[invalid_event])
    with pytest.raises(ValidationError):
        ForensicTimeline.model_validate(ft_invalid)


def test_band_message_auto_gen():
    """Assert BandMessage auto-generates unique message_ids and sets valid timestamps."""
    msg1 = BandMessage(
        pipeline_run_id="run-1",
        channel="raw_evidence_input",
        agent_id="orchestrator",
        sequence=1,
        status="success",
        confidence=1.0
    )
    msg2 = BandMessage(
        pipeline_run_id="run-1",
        channel="raw_evidence_input",
        agent_id="orchestrator",
        sequence=1,
        status="success",
        confidence=1.0
    )
    assert msg1.message_id != msg2.message_id
    assert isinstance(msg1.timestamp, datetime)
    assert isinstance(msg2.timestamp, datetime)

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from schemas.input_schema import RawEvidenceInput, LogSource
from schemas.timeline_schema import ForensicTimeline, TimelineEvent, Anomaly
from schemas.attribution_schema import (
    AttributionReport,
    AttackClassification,
    EntryPoint,
    AttackChainStep,
    LateralMovement,
    DataTargeted,
)
from schemas.impact_schema import (
    ImpactAssessment,
    BlastRadius,
    BusinessImpact,
    ComplianceFlag,
    RootCauseFactor,
)
from schemas.postmortem_schema import (
    PostMortemReport,
    ExecutiveSummary,
    TechnicalReport,
    RemediationActionItem,
    ConfidenceBreakdown,
)


def test_raw_evidence_input():
    """Verify RawEvidenceInput handles log sources correctly."""
    # Valid input
    raw_input = RawEvidenceInput(
        pipeline_run_id="run-1",
        log_sources=[
            LogSource(
                source_name="s3_logs",
                source_type="s3_access",
                content="some raw content",
            )
        ],
    )
    assert raw_input.pipeline_run_id == "run-1"
    assert raw_input.organization_name == "Unknown"

    # Invalid input (empty log sources list)
    with pytest.raises(ValidationError):
        RawEvidenceInput(pipeline_run_id="run-1", log_sources=[])


def test_timeline_chronological_sorting():
    """Verify ForensicTimeline sorts events in ascending timestamp order."""
    t1 = datetime(2026, 6, 13, 7, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 6, 13, 7, 5, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 6, 13, 6, 30, 0, tzinfo=timezone.utc)

    event_early = TimelineEvent(
        timestamp=t3,
        event_type="discovery",
        target_resource="bucket",
        action="list",
        outcome="success",
        severity="low",
        raw_log_reference="ref",
    )
    event_mid = TimelineEvent(
        timestamp=t1,
        event_type="access",
        target_resource="bucket",
        action="read",
        outcome="success",
        severity="medium",
        raw_log_reference="ref",
    )
    event_late = TimelineEvent(
        timestamp=t2,
        event_type="exfiltration",
        target_resource="bucket",
        action="download",
        outcome="success",
        severity="high",
        raw_log_reference="ref",
    )

    # Pass events out of order (late, mid, early)
    timeline = ForensicTimeline(
        incident_id="inc-1",
        pipeline_run_id="run-1",
        confidence_score=0.9,
        raw_event_count=3,
        filtered_event_count=3,
        timeline_start=t3,
        timeline_end=t2,
        events=[event_late, event_mid, event_early],
        affected_systems=["bucket"],
    )

    # They should be sorted early -> mid -> late
    assert timeline.events[0].timestamp == t3
    assert timeline.events[1].timestamp == t1
    assert timeline.events[2].timestamp == t2


def test_attribution_report():
    """Verify AttributionReport values boundary constraints."""
    # Valid
    report = AttributionReport(
        pipeline_run_id="run-1",
        confidence_score=0.8,
        attack_classification=AttackClassification(
            attack_type="data_exfiltration",
            threat_actor_type="opportunistic",
            sophistication_level="low",
        ),
        entry_point=EntryPoint(
            identified=True,
            resource="github_repo",
            method="leak",
            vulnerability_description="exposed key",
        ),
        attack_chain=[
            AttackChainStep(
                step=1,
                description="leaked key",
                mitre_technique_id="T1078",
                mitre_technique_name="Valid Accounts",
                mitre_tactic="Initial Access",
            )
        ],
        lateral_movement=LateralMovement(detected=False),
        data_targeted=DataTargeted(likely_target="s3 bucket", evidence="logs"),
    )
    assert report.confidence_score == 0.8

    # Invalid confidence (greater than 1.0)
    with pytest.raises(ValidationError):
        AttributionReport(
            pipeline_run_id="run-1",
            confidence_score=1.5,
            attack_classification=AttackClassification(
                attack_type="data_exfiltration",
                threat_actor_type="opportunistic",
                sophistication_level="low",
            ),
            entry_point=EntryPoint(
                identified=True,
                resource="github_repo",
                method="leak",
                vulnerability_description="exposed key",
            ),
            attack_chain=[],
            lateral_movement=LateralMovement(detected=False),
            data_targeted=DataTargeted(likely_target="s3 bucket", evidence="logs"),
        )


def test_impact_assessment():
    """Verify compliance triggers and blast radius validation."""
    impact = ImpactAssessment(
        pipeline_run_id="run-1",
        confidence_score=0.75,
        blast_radius=BlastRadius(
            systems_compromised=["aws_s3_bucket"],
            systems_compromised_count=1,
            users_affected_count=100,
            estimated_records_exposed=5000,
            data_categories_exposed=["pii"],
        ),
        business_impact=BusinessImpact(
            severity="high",
            estimated_downtime_minutes=15,
            revenue_impact="low",
            reputational_risk="medium",
            description="PII exfiltrated",
        ),
        compliance_flags=[
            ComplianceFlag(
                regulation="GDPR",
                triggered=True,
                reason="Customer names and emails exposed",
                mandatory_notification=True,
                notification_deadline_hours=72,
            )
        ],
        root_cause_factors=[
            RootCauseFactor(
                factor="API key leaked",
                category="human",
                contributing_weight="primary",
            )
        ],
    )
    assert impact.blast_radius.estimated_records_exposed == 5000
    assert impact.compliance_flags[0].regulation == "GDPR"
    assert impact.compliance_flags[0].notification_deadline_hours == 72


def test_postmortem_report():
    """Verify PostMortemReport creation and validation."""
    pm = PostMortemReport(
        pipeline_run_id="run-1",
        confidence_score=0.95,
        overall_severity="high",
        executive_summary=ExecutiveSummary(
            headline="Key leaked and rotated.",
            what_happened="An AWS access key was committed.",
            business_impact="PII accessed.",
            immediate_actions_taken="Rotated key.",
            key_recommendations=["Add secrets scanner"],
        ),
        technical_report=TechnicalReport(
            incident_overview="overview",
            timeline_summary="timeline",
            attack_description="attack",
            root_cause="cause",
            blast_radius_summary="radius",
        ),
        remediation_plan=[
            RemediationActionItem(
                action_id="REM-001",
                priority="immediate",
                category="access_control",
                title="Rotate API Key",
                description="Immediately disable and delete the leaked IAM key",
                owner="DevOps",
                estimated_effort="hours",
                verification_method="Run list-keys",
            )
        ],
        confidence_breakdown=ConfidenceBreakdown(
            agent1_forensic=0.9,
            agent2_attribution=0.8,
            agent3_impact=0.75,
            agent4_postmortem=0.95,
            overall=0.95,
        ),
    )
    assert len(pm.remediation_plan) == 1
    assert pm.remediation_plan[0].priority == "immediate"

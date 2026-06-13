from datetime import datetime, timezone
import pytest
import asyncio
from unittest.mock import patch

from core.client import BandClient
from core.coordinator import BandCoordinator
from pipeline.state_manager import PipelineStateManager
from pipeline.orchestrator import PipelineOrchestrator

from schemas.timeline_schema import ForensicTimeline, TimelineEvent
from schemas.attribution_schema import (
    AttributionReport,
    AttackClassification,
    EntryPoint,
    AttackChainStep,
    LateralMovement,
    DataTargeted,
)
from schemas.impact_schema import ImpactAssessment, BlastRadius, BusinessImpact, ComplianceFlag
from schemas.postmortem_schema import (
    PostMortemReport,
    ExecutiveSummary,
    TechnicalReport,
    RemediationActionItem,
    ConfidenceBreakdown,
)


# Mock objects matching schema structures
mock_timeline = ForensicTimeline(
    incident_id="inc-test",
    pipeline_run_id="run-test",
    confidence_score=0.9,
    raw_event_count=1,
    filtered_event_count=1,
    timeline_start=datetime.now(timezone.utc),
    timeline_end=datetime.now(timezone.utc),
    events=[
        TimelineEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="discovery",
            target_resource="bucket-x",
            action="list",
            outcome="success",
            severity="low",
            raw_log_reference="logs",
        )
    ],
    affected_systems=["bucket-x"],
)

mock_attribution = AttributionReport(
    pipeline_run_id="run-test",
    confidence_score=0.85,
    attack_classification=AttackClassification(
        attack_type="data_exfiltration",
        threat_actor_type="opportunistic",
        sophistication_level="low",
    ),
    entry_point=EntryPoint(
        identified=True,
        resource="github_repo",
        method="key_leak",
        vulnerability_description="exposed credentials",
    ),
    attack_chain=[
        AttackChainStep(
            step=1,
            description="extracted keys",
            mitre_technique_id="T1078",
            mitre_technique_name="Valid Accounts",
            mitre_tactic="Initial Access",
        )
    ],
    lateral_movement=LateralMovement(detected=False),
    data_targeted=DataTargeted(likely_target="bucket-x", evidence="logs"),
)

mock_impact = ImpactAssessment(
    pipeline_run_id="run-test",
    confidence_score=0.8,
    blast_radius=BlastRadius(
        systems_compromised=["bucket-x"],
        systems_compromised_count=1,
        users_affected_count=10,
        estimated_records_exposed=100,
        data_categories_exposed=["pii"],
    ),
    business_impact=BusinessImpact(
        severity="medium",
        estimated_downtime_minutes=0,
        revenue_impact="none",
        reputational_risk="low",
        description="minimal access",
    ),
    compliance_flags=[],  # Generated deterministically downstream
)

mock_postmortem = PostMortemReport(
    pipeline_run_id="run-test",
    confidence_score=0.95,
    overall_severity="medium",
    executive_summary=ExecutiveSummary(
        headline="Exposed AWS key handled",
        what_happened="An AWS key was accidentally committed and exploited.",
        business_impact="PII in S3 was accessed briefly.",
        immediate_actions_taken="Rotated keys, locked bucket.",
        key_recommendations=["Rotate keys", "Enable scanner"],
    ),
    technical_report=TechnicalReport(
        incident_overview="Adversary obtained valid keys and listed bucket.",
        timeline_summary="First leak on github followed by S3 list events.",
        attack_description="Mapped to valid accounts technique.",
        root_cause="GitHub commit leak.",
        blast_radius_summary="AWS S3 bucket accessed.",
    ),
    reremediation_plan=[],  # field name updated: remediation_plan
    remediation_plan=[
        RemediationActionItem(
            action_id="REM-001",
            priority="immediate",
            category="access_control",
            title="Disable Keys",
            description="Immediately disable exposed IAM access keys",
            owner="Security Team",
            estimated_effort="hours",
            verification_method="Check console",
        )
    ],
    confidence_breakdown=ConfidenceBreakdown(
        agent1_forensic=0.9,
        agent2_attribution=0.85,
        agent3_impact=0.8,
        agent4_postmortem=0.95,
        overall=0.95,
    ),
)


@pytest.mark.asyncio
async def test_full_orchestrated_pipeline():
    """Verify that orchestrator coordinates all agents successfully in sequence."""
    client = BandClient()  # In mock mode
    state_manager = PipelineStateManager()
    coordinator = BandCoordinator(client)
    orchestrator = PipelineOrchestrator(client, state_manager, coordinator)

    # Patch the _call_model_json method on each agent to return canned data
    with patch("agents.agent1_forensic.ForensicEvidenceAgent._call_model_json", return_value=mock_timeline), \
         patch("agents.agent2_attribution.AttackAttributionAgent._call_model_json", return_value=mock_attribution), \
         patch("agents.agent3_impact.ImpactAssessmentAgent._call_model_json", return_value=mock_impact), \
         patch("agents.agent4_postmortem.PostMortemAgent._call_model_json", return_value=mock_postmortem):

        result = await orchestrator.run_pipeline("sample raw security logs contents", timeout_seconds=10)

        # Assertions
        assert result["status"] == "completed"
        assert result["error"] is None
        assert result["result"]["executive_summary"]["headline"] == "Exposed AWS key handled"
        
        # Verify state recording
        stages = result["stages"]
        assert "forensic_timeline" in stages
        assert "attack_attribution" in stages
        assert "impact_assessment" in stages
        
        # Confirm stages are populated with correct keys
        assert stages["forensic_timeline"]["incident_id"] == "inc-test"
        assert stages["attack_attribution"]["attack_classification"]["attack_type"] == "data_exfiltration"
        assert stages["impact_assessment"]["blast_radius"]["estimated_records_exposed"] == 100
        
        # Verify that compliance rules populated GDPR flag
        compliance_flags = stages["impact_assessment"]["compliance_flags"]
        assert len(compliance_flags) > 0
        assert compliance_flags[0]["regulation"] == "GDPR"
        assert compliance_flags[0]["triggered"] is True

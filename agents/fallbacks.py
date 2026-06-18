"""Graceful-degradation fallbacks for the agent pipeline.

When an agent's LLM call cannot produce a schema-valid result — e.g. oversized,
malformed, or content-free evidence — the agent emits one of these minimal,
schema-valid placeholder payloads with low confidence and ``status="partial"``
instead of erroring out. This keeps the whole investigation resilient: the user
gets a clearly-degraded (low-confidence) report rather than a hard pipeline
failure. Normal, parseable evidence never triggers these paths.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from schemas.timeline_schema import ForensicTimeline, TimelineEvent
from schemas.attribution_schema import (
    AttributionReport, AttackClassification, EntryPoint, AttackChainStep,
    LateralMovement, DataTargeted,
)
from schemas.impact_schema import ImpactAssessment, BlastRadius, BusinessImpact
from schemas.postmortem_schema import (
    PostMortemReport, ExecutiveSummary, TechnicalReport, RemediationActionItem,
    ConfidenceBreakdown,
)

_NOTE = (
    "Degraded output: the model could not produce a structured result for this "
    "stage from the provided evidence. A low-confidence placeholder was emitted "
    "so the investigation could continue end-to-end."
)
_LOW = 0.1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def forensic_timeline_fallback(run_id: str) -> dict:
    now = _now()
    return ForensicTimeline(
        incident_id=f"degraded-{str(uuid4())[:8]}",
        pipeline_run_id=run_id,
        confidence_score=_LOW,
        raw_event_count=0,
        filtered_event_count=0,
        timeline_start=now,
        timeline_end=now,
        events=[TimelineEvent(
            timestamp=now,
            event_type="unknown",
            target_resource="unknown",
            action="insufficient structured evidence to reconstruct events",
            outcome="unknown",
            severity="low",
            raw_log_reference="n/a",
        )],
        affected_systems=["unknown"],
        agent_notes=_NOTE,
    ).model_dump(mode="json")


def attribution_fallback(run_id: str) -> dict:
    return AttributionReport(
        pipeline_run_id=run_id,
        confidence_score=_LOW,
        attack_classification=AttackClassification(
            attack_type="unknown", threat_actor_type="unknown", sophistication_level="low",
        ),
        entry_point=EntryPoint(
            identified=False, resource="unknown", method="unknown",
            vulnerability_description="Entry point could not be determined from available evidence.",
        ),
        attack_chain=[AttackChainStep(
            step=1, description="Attack path could not be reconstructed from available evidence.",
            mitre_technique_id="T0000", mitre_technique_name="Unknown", mitre_tactic="Unknown",
        )],
        lateral_movement=LateralMovement(detected=False),
        data_targeted=DataTargeted(likely_target="unknown", evidence="none"),
        agent_notes=_NOTE,
    ).model_dump(mode="json")


def impact_fallback(run_id: str) -> dict:
    return ImpactAssessment(
        pipeline_run_id=run_id,
        confidence_score=_LOW,
        blast_radius=BlastRadius(
            systems_compromised=["unknown"], systems_compromised_count=0,
            users_affected_count=0, estimated_records_exposed=-1,
            data_categories_exposed=["unknown"],
        ),
        business_impact=BusinessImpact(
            severity="low", revenue_impact="unknown", reputational_risk="low",
            description="Business impact could not be assessed from available evidence.",
        ),
        compliance_flags=[],
        root_cause_factors=[],
        agent_notes=_NOTE,
    ).model_dump(mode="json")


def postmortem_fallback(run_id: str) -> dict:
    return PostMortemReport(
        confidence_score=_LOW,
        overall_severity="low",
        executive_summary=ExecutiveSummary(
            headline="Degraded incident report",
            what_happened="The pipeline could not fully reconstruct this incident from the provided evidence.",
            business_impact="Undetermined.",
            immediate_actions_taken="None — automated assessment was inconclusive.",
            key_recommendations=["Re-run the investigation with more complete or higher-fidelity log evidence."],
        ),
        technical_report=TechnicalReport(
            incident_overview="Insufficient structured evidence for an automated assessment.",
            timeline_summary="Unavailable.",
            attack_description="Unavailable.",
            root_cause="Undetermined.",
            blast_radius_summary="Undetermined.",
        ),
        remediation_plan=[RemediationActionItem(
            action_id="REM-000", priority="short_term", category="process",
            title="Collect higher-fidelity evidence and re-run the investigation",
            description="The provided evidence was insufficient for an automated assessment.",
            owner="security-team", estimated_effort="varies",
            verification_method="A complete, higher-confidence report is produced on re-run.",
        )],
        lessons_learned=["Ensure log evidence is complete and well-formed before analysis."],
        compliance_actions=[],
        confidence_breakdown=ConfidenceBreakdown(
            agent1_forensic=_LOW, agent2_attribution=_LOW,
            agent3_impact=_LOW, agent4_postmortem=_LOW, overall=_LOW,
        ),
        agent_notes=_NOTE,
    ).model_dump(mode="json")

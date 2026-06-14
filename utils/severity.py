"""Aggregate the overall incident severity and agent confidence.

The post-mortem report already carries ``overall_severity`` and a
``confidence_breakdown``; this helper surfaces a single authoritative summary
for the top of the UI report and gracefully degrades when the pipeline stopped
early (e.g. sparse-evidence or timeout runs) by reconstructing the numbers from
whatever stages did complete.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_RANK_SEVERITY = {v: k for k, v in _SEVERITY_RANK.items()}


def _safe(d: Any, *keys: str, default: Any = None) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def aggregate_summary(stages: Dict[str, Any]) -> Dict[str, Any]:
    """Return a top-line summary dict.

    Keys: ``severity``, ``severity_rank``, ``overall_confidence``,
    ``confidence_breakdown`` (per-agent), ``attack_type``, ``entry_point``,
    ``records_exposed``, ``compliance_count``, ``redactions``.
    """
    timeline = stages.get("forensic_timeline") or {}
    attribution = stages.get("attack_attribution") or {}
    impact = stages.get("impact_assessment") or {}
    postmortem = stages.get("postmortem_complete") or {}
    pii = stages.get("pii_masking") or {}

    # --- Severity: prefer post-mortem, else impact business severity, else
    # derive from the worst timeline event. ---
    severity = (
        postmortem.get("overall_severity")
        or _safe(impact, "business_impact", "severity")
    )
    if not severity:
        events = timeline.get("events") or []
        ranks = [_SEVERITY_RANK.get(e.get("severity", "low"), 1) for e in events]
        severity = _RANK_SEVERITY.get(max(ranks), "low") if ranks else "low"

    # --- Confidence breakdown. ---
    breakdown = postmortem.get("confidence_breakdown") or {}
    per_agent = {
        "Forensic": breakdown.get("agent1_forensic", timeline.get("confidence_score")),
        "Attribution": breakdown.get("agent2_attribution", attribution.get("confidence_score")),
        "Impact": breakdown.get("agent3_impact", impact.get("confidence_score")),
        "Post-Mortem": breakdown.get("agent4_postmortem", postmortem.get("confidence_score")),
    }
    scored = [v for v in per_agent.values() if isinstance(v, (int, float))]
    overall = breakdown.get("overall")
    if not isinstance(overall, (int, float)):
        overall = round(sum(scored) / len(scored), 2) if scored else None

    compliance_flags = [
        f for f in (impact.get("compliance_flags") or []) if f.get("triggered")
    ]

    return {
        "severity": severity,
        "severity_rank": _SEVERITY_RANK.get(severity, 0),
        "overall_confidence": overall,
        "confidence_breakdown": per_agent,
        "attack_type": _safe(attribution, "attack_classification", "attack_type"),
        "threat_actor": _safe(attribution, "attack_classification", "threat_actor_type"),
        "entry_point": _safe(attribution, "entry_point", "resource"),
        "records_exposed": _safe(impact, "blast_radius", "estimated_records_exposed"),
        "systems_compromised": _safe(impact, "blast_radius", "systems_compromised_count"),
        "compliance_count": len(compliance_flags),
        "compliance_regulations": [f.get("regulation") for f in compliance_flags],
        "redactions": pii.get("redaction_count", 0),
    }


def severity_color(severity: Optional[str]) -> str:
    """Return a hex color for a severity label (dark-theme console palette)."""
    return {
        "critical": "#ef4444",
        "high": "#f97316",
        "medium": "#eab308",
        "low": "#22c55e",
    }.get((severity or "").lower(), "#64748b")

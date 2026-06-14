"""Generate a static PDF incident report for auditors / executives.

Compliance windows (e.g. GDPR's 72-hour notification) require a fixed,
record-keeping artifact. This renders the timeline, MITRE attack chain,
triggered compliance flags and remediation plan into a single PDF using
reportlab (pure-Python, no system dependencies).
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover
    REPORTLAB_AVAILABLE = False


def _safe(d: Any, *keys: str, default: Any = "—") -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur not in (None, "") else default


def build_incident_pdf(
    stages: Dict[str, Any],
    summary: Dict[str, Any],
    run_id: str,
    org_name: str = "Organization",
) -> Optional[bytes]:
    """Render the incident report to PDF bytes, or ``None`` if reportlab missing."""
    if not REPORTLAB_AVAILABLE:
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"NeXtrace Incident Report {run_id}",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("H1x", parent=styles["Heading1"], textColor=colors.HexColor("#0f172a"), fontSize=20))
    styles.add(ParagraphStyle("H2x", parent=styles["Heading2"], textColor=colors.HexColor("#1e293b"), fontSize=13))
    styles.add(ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.5, leading=13))
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, textColor=colors.HexColor("#64748b"))

    story: List[Any] = []
    timeline = stages.get("forensic_timeline") or {}
    attribution = stages.get("attack_attribution") or {}
    impact = stages.get("impact_assessment") or {}
    postmortem = stages.get("postmortem_complete") or {}

    # --- Header ---
    story.append(Paragraph("NeXtrace — Security Incident Report", styles["H1x"]))
    story.append(Paragraph(
        f"{org_name} &nbsp;·&nbsp; Run ID {run_id} &nbsp;·&nbsp; "
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        small,
    ))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#cbd5e1")))
    story.append(Spacer(1, 8))

    # --- Summary table ---
    sev = str(summary.get("severity", "—")).upper()
    conf = summary.get("overall_confidence")
    conf_str = f"{conf:.0%}" if isinstance(conf, (int, float)) else "—"
    summ_rows = [
        ["Overall severity", sev, "Confidence", conf_str],
        ["Attack type", str(summary.get("attack_type", "—")), "Threat actor", str(summary.get("threat_actor", "—"))],
        ["Entry point", str(summary.get("entry_point", "—")), "Records exposed", str(summary.get("records_exposed", "—"))],
        ["Systems compromised", str(summary.get("systems_compromised", "—")), "PII redacted", str(summary.get("redactions", 0))],
    ]
    t = Table(summ_rows, colWidths=[34 * mm, 50 * mm, 34 * mm, 46 * mm])
    sev_color = {"CRITICAL": "#ef4444", "HIGH": "#f97316", "MEDIUM": "#eab308", "LOW": "#22c55e"}.get(sev, "#64748b")
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (1, 0), (1, 0), colors.HexColor(sev_color)),
        ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # --- Executive summary ---
    exec_sum = postmortem.get("executive_summary") or {}
    if exec_sum:
        story.append(Paragraph("Executive Summary", styles["H2x"]))
        if exec_sum.get("headline"):
            story.append(Paragraph(f"<b>{exec_sum['headline']}</b>", styles["Body"]))
        for label in ("what_happened", "business_impact", "immediate_actions_taken"):
            if exec_sum.get(label):
                story.append(Paragraph(exec_sum[label], styles["Body"]))
                story.append(Spacer(1, 2))
        story.append(Spacer(1, 8))

    # --- Timeline ---
    events = timeline.get("events") or []
    if events:
        story.append(Paragraph("Forensic Timeline", styles["H2x"]))
        rows = [["Time (UTC)", "Type", "Actor / IP", "Action", "Sev"]]
        for e in events[:25]:
            ts = str(e.get("timestamp", ""))[:19].replace("T", " ")
            actor = e.get("source_user") or e.get("source_ip") or "—"
            rows.append([
                ts, e.get("event_type", ""), str(actor)[:24],
                str(e.get("action", ""))[:40], e.get("severity", ""),
            ])
        tt = Table(rows, colWidths=[34 * mm, 22 * mm, 34 * mm, 56 * mm, 18 * mm], repeatRows=1)
        tt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(tt)
        story.append(Spacer(1, 8))

    # --- MITRE attack chain ---
    chain = attribution.get("attack_chain") or []
    if chain:
        story.append(Paragraph("MITRE ATT&CK Mapping", styles["H2x"]))
        rows = [["#", "Tactic", "Technique", "ID", "Description"]]
        for s in sorted(chain, key=lambda x: x.get("step", 0)):
            rows.append([
                str(s.get("step", "")), s.get("mitre_tactic", ""),
                s.get("mitre_technique_name", ""), s.get("mitre_technique_id", ""),
                str(s.get("description", ""))[:52],
            ])
        tt = Table(rows, colWidths=[8 * mm, 30 * mm, 38 * mm, 18 * mm, 70 * mm], repeatRows=1)
        tt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7f1d1d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fef2f2")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(tt)
        story.append(Spacer(1, 8))

    # --- Compliance flags ---
    flags = [f for f in (impact.get("compliance_flags") or []) if f.get("triggered")]
    if flags:
        story.append(Paragraph("Triggered Compliance Obligations", styles["H2x"]))
        rows = [["Regulation", "Notify?", "Deadline (h)", "Reason"]]
        for f in flags:
            rows.append([
                f.get("regulation", ""),
                "Yes" if f.get("mandatory_notification") else "No",
                str(f.get("notification_deadline_hours", "—")),
                str(f.get("reason", ""))[:64],
            ])
        tt = Table(rows, colWidths=[26 * mm, 18 * mm, 24 * mm, 96 * mm], repeatRows=1)
        tt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#713f12")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fffbeb")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(tt)
        story.append(Spacer(1, 8))

    # --- Remediation plan ---
    plan = postmortem.get("remediation_plan") or []
    if plan:
        story.append(Paragraph("Remediation Plan", styles["H2x"]))
        rows = [["Priority", "Title", "Owner", "Effort"]]
        for item in plan:
            rows.append([
                item.get("priority", ""), str(item.get("title", ""))[:54],
                item.get("owner", ""), item.get("estimated_effort", ""),
            ])
        tt = Table(rows, colWidths=[24 * mm, 84 * mm, 30 * mm, 26 * mm], repeatRows=1)
        tt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14532d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdf4")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(tt)
        story.append(Spacer(1, 10))

    story.append(HRFlowable(width="100%", color=colors.HexColor("#cbd5e1")))
    story.append(Paragraph(
        "Generated by NeXtrace — multi-agent security incident intelligence, coordinated through Band. "
        "This document is an automated audit artifact; verify findings before regulatory submission.",
        small,
    ))

    doc.build(story)
    return buf.getvalue()

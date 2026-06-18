"""Generate a structured PDF report from postmortem data."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def generate_pdf_report(postmortem_data: Dict[str, Any], output_path: str) -> str:
    """Generate a PDF report using reportlab and save it to output_path."""
    if not postmortem_data:
        raise ValueError("postmortem_data is None or empty")

    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab library is not installed")

    parent_dir = Path(output_path).parent
    if not parent_dir.exists():
        raise IOError(f"Directory {parent_dir} does not exist")

    from schemas.postmortem_schema import PostMortemReport
    try:
        report = PostMortemReport.model_validate(postmortem_data)
    except Exception as e:
        raise ValueError(f"Invalid postmortem_data schema: {e}")

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="NeXtrace Security Incident Report",
    )
    styles = getSampleStyleSheet()

    h1_style = ParagraphStyle(
        "H1_custom",
        parent=styles["Heading1"],
        textColor=colors.HexColor("#0f172a"),
        fontSize=20,
        spaceAfter=10
    )
    h2_style = ParagraphStyle(
        "H2_custom",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#1e293b"),
        fontSize=14,
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        "Body_custom",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8
    )
    bold_body_style = ParagraphStyle(
        "BoldBody_custom",
        parent=body_style,
        fontName="Helvetica-Bold"
    )
    caption_style = ParagraphStyle(
        "Caption_custom",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#64748b"),
        leading=10
    )

    story = []

    # Header
    story.append(Paragraph("NeXtrace Security Incident Report", h1_style))

    # Run ID and timestamp
    run_id = postmortem_data.get("pipeline_run_id", "Unknown ID")
    timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(Paragraph(f"<b>Run ID:</b> {run_id} &nbsp;|&nbsp; <b>Generated:</b> {timestamp_str}", caption_style))
    story.append(Spacer(1, 4))

    # Overall severity badge
    sev = report.overall_severity.upper()
    sev_color = {"CRITICAL": "#ef4444", "HIGH": "#f97316", "MEDIUM": "#eab308", "LOW": "#22c55e"}.get(sev, "#64748b")

    sev_text_style = ParagraphStyle("SevText", parent=body_style, textColor=colors.white, fontName="Helvetica-Bold")
    severity_table = Table([[Paragraph(f"OVERALL SEVERITY: <b>{sev}</b>", sev_text_style)]], colWidths=[174 * mm])
    severity_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(sev_color)),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(severity_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#cbd5e1"), thickness=1))
    story.append(Spacer(1, 10))

    # Executive Summary section
    story.append(Paragraph("Executive Summary", h2_style))
    story.append(Paragraph(f"<b>Headline:</b> {report.executive_summary.headline}", body_style))
    story.append(Paragraph(f"<b>What Happened:</b> {report.executive_summary.what_happened}", body_style))
    story.append(Paragraph(f"<b>Business Impact:</b> {report.executive_summary.business_impact}", body_style))
    story.append(Paragraph(f"<b>Immediate Actions Taken:</b> {report.executive_summary.immediate_actions_taken}", body_style))

    if report.executive_summary.key_recommendations:
        story.append(Paragraph("<b>Key Recommendations:</b>", bold_body_style))
        for rec in report.executive_summary.key_recommendations:
            story.append(Paragraph(f"• {rec}", body_style))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#e2e8f0"), thickness=0.5))

    # Technical Report section
    story.append(Paragraph("Technical Report", h2_style))
    tr = report.technical_report
    story.append(Paragraph(f"<b>Incident Overview:</b> {tr.incident_overview}", body_style))
    story.append(Paragraph(f"<b>Timeline Summary:</b> {tr.timeline_summary}", body_style))
    story.append(Paragraph(f"<b>Attack Description:</b> {tr.attack_description}", body_style))
    story.append(Paragraph(f"<b>Root Cause:</b> {tr.root_cause}", body_style))
    story.append(Paragraph(f"<b>Blast Radius Summary:</b> {tr.blast_radius_summary}", body_style))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#e2e8f0"), thickness=0.5))

    # Remediation Plan as numbered list
    story.append(Paragraph("Remediation Plan", h2_style))
    for idx, item in enumerate(report.remediation_plan, 1):
        item_text = (
            f"<b>{idx}. [{item.priority.upper()}] {item.title}</b><br/>"
            f"<i>Category:</i> {item.category} &nbsp;|&nbsp; <i>Owner:</i> {item.owner} &nbsp;|&nbsp; <i>Effort:</i> {item.estimated_effort}<br/>"
            f"<i>Description:</i> {item.description}<br/>"
            f"<i>Verification Method:</i> {item.verification_method}"
        )
        story.append(Paragraph(item_text, body_style))
        story.append(Spacer(1, 4))

    # Compliance Actions if any
    if report.compliance_actions:
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", color=colors.HexColor("#e2e8f0"), thickness=0.5))
        story.append(Paragraph("Compliance Actions", h2_style))
        for action in report.compliance_actions:
            action_text = (
                f"• <b>{action.regulation}</b>: {action.action_required}<br/>"
                f"<i>Deadline:</i> {action.deadline} &nbsp;|&nbsp; <i>Responsible Party:</i> {action.responsible_party}"
            )
            story.append(Paragraph(action_text, body_style))
            story.append(Spacer(1, 4))

    # Lessons Learned if any
    if report.lessons_learned:
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", color=colors.HexColor("#e2e8f0"), thickness=0.5))
        story.append(Paragraph("Lessons Learned", h2_style))
        for lesson in report.lessons_learned:
            story.append(Paragraph(f"• {lesson}", body_style))
            story.append(Spacer(1, 4))

    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#cbd5e1"), thickness=1))
    story.append(Spacer(1, 5))

    # Confidence breakdown at bottom
    cb = report.confidence_breakdown
    breakdown_text = (
        f"<b>Confidence Score: {report.confidence_score * 100:.0f}%</b> (Overall: {cb.overall * 100:.0f}%)<br/>"
        f"Forensic: {cb.agent1_forensic * 100:.0f}% &nbsp;•&nbsp; "
        f"Attribution: {cb.agent2_attribution * 100:.0f}% &nbsp;•&nbsp; "
        f"Impact: {cb.agent3_impact * 100:.0f}% &nbsp;•&nbsp; "
        f"Post-Mortem: {cb.agent4_postmortem * 100:.0f}%"
    )
    story.append(Paragraph(breakdown_text, caption_style))

    doc.build(story)
    return output_path

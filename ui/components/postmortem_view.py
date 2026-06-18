"""Post-mortem tab — executive summary, technical report, and remediation plan."""

from __future__ import annotations

import html
from typing import Any, Dict, Optional

import streamlit as st

from schemas.postmortem_schema import PostMortemReport
from ui.styles.theme import severity_badge_html


def _parse_postmortem(data: Optional[Dict[str, Any]]) -> Optional[PostMortemReport]:
    if not data:
        return None
    try:
        return PostMortemReport.model_validate(data)
    except Exception:
        return None


def render_postmortem_view(stage_data: Optional[Dict[str, Any]]) -> None:
    """Render blameless post-mortem report and prioritized remediation tasks."""
    report = _parse_postmortem(stage_data)
    if report is None:
        st.info("No post-mortem report available. Run an investigation to populate this tab.")
        return

    sev = report.overall_severity.lower()
    st.markdown(
        f"Overall severity: {severity_badge_html(sev)} · "
        f"Confidence: **{report.confidence_score * 100:.0f}%** · "
        f"Version {report.report_version}",
        unsafe_allow_html=True,
    )

    es = report.executive_summary
    st.markdown(
        f'<div class="nx-callout">'
        f'<div class="nx-callout-title">Executive Summary</div>'
        f"<h3 style='margin:0 0 0.5rem 0;'>{html.escape(es.headline)}</h3>"
        f"<p><strong>What happened:</strong> {html.escape(es.what_happened)}</p>"
        f"<p><strong>Business impact:</strong> {html.escape(es.business_impact)}</p>"
        f"<p><strong>Immediate actions:</strong> {html.escape(es.immediate_actions_taken)}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if es.key_recommendations:
        st.markdown("**Key recommendations:**")
        for rec in es.key_recommendations:
            st.markdown(f"- {rec}")

    st.subheader("Technical Report")
    tr = report.technical_report
    st.markdown(f"**Incident overview**\n\n{tr.incident_overview}")
    st.markdown(f"**Timeline summary**\n\n{tr.timeline_summary}")
    st.markdown(f"**Attack description**\n\n{tr.attack_description}")
    st.markdown(f"**Root cause**\n\n{tr.root_cause}")
    st.markdown(f"**Blast radius**\n\n{tr.blast_radius_summary}")

    st.subheader("Remediation Plan")
    priority_order = {"immediate": 0, "short_term": 1, "long_term": 2}
    sorted_items = sorted(
        report.remediation_plan,
        key=lambda r: priority_order.get(r.priority, 99),
    )
    for item in sorted_items:
        priority_class = f"nx-priority-{item.priority}"
        st.markdown(
            f'<div class="nx-remediation-item {priority_class}">'
            f"<strong>[{html.escape(item.priority.upper())}] {html.escape(item.title)}</strong>"
            f"<br/><span style='color:#8b949e;'>{html.escape(item.description)}</span>"
            f"<br/><span style='font-size:0.8rem;'>Owner: {html.escape(item.owner)} · "
            f"Effort: {html.escape(item.estimated_effort)} · "
            f"Verify: {html.escape(item.verification_method)}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    if report.lessons_learned:
        with st.expander("Lessons learned", expanded=False):
            for lesson in report.lessons_learned:
                st.markdown(f"- {lesson}")

    if report.compliance_actions:
        with st.expander("Compliance actions", expanded=False):
            for action in report.compliance_actions:
                st.markdown(
                    f"- **{action.regulation}**: {action.action_required} "
                    f"(deadline: {action.deadline}, owner: {action.responsible_party})"
                )

    cb = report.confidence_breakdown
    st.caption(
        f"Confidence breakdown — Forensic: {cb.agent1_forensic:.0%} · "
        f"Attribution: {cb.agent2_attribution:.0%} · "
        f"Impact: {cb.agent3_impact:.0%} · "
        f"Post-mortem: {cb.agent4_postmortem:.0%} · "
        f"Overall: {cb.overall:.0%}"
    )

    if report.agent_notes:
        st.caption(f"Agent notes: {report.agent_notes}")

    if st.button("Download PDF Report"):
        import tempfile, os
        from utils.pdf_exporter import generate_pdf_report
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False
        ) as tmp:
            path = generate_pdf_report(
                stage_data, tmp.name
            )
        with open(path, "rb") as f:
            st.download_button(
                label="Save PDF",
                data=f.read(),
                file_name="nextrace_report.pdf",
                mime="application/pdf",
            )


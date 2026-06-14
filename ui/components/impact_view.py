"""Impact assessment tab — blast radius metrics and compliance alert banners."""

from __future__ import annotations

import html
from typing import Any, Dict, Optional

import streamlit as st

from schemas.impact_schema import ImpactAssessment
from ui.styles.theme import severity_badge_html


def _parse_impact(data: Optional[Dict[str, Any]]) -> Optional[ImpactAssessment]:
    if not data:
        return None
    try:
        return ImpactAssessment.model_validate(data)
    except Exception:
        return None


def render_impact_view(stage_data: Optional[Dict[str, Any]]) -> None:
    """Render blast radius metrics and triggered compliance regulations."""
    impact = _parse_impact(stage_data)
    if impact is None:
        st.info("No impact assessment available. Run an investigation to populate this tab.")
        return

    br = impact.blast_radius
    bi = impact.business_impact

    records = br.estimated_records_exposed
    records_display = f"{records:,}" if records >= 0 else "Unknown"

    metrics_html = (
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:1.25rem;">'
        f'<div class="nx-metric-card"><div class="nx-metric-value">{br.systems_compromised_count}</div>'
        f'<div class="nx-metric-label">Systems Compromised</div></div>'
        f'<div class="nx-metric-card"><div class="nx-metric-value">{br.users_affected_count}</div>'
        f'<div class="nx-metric-label">Users Affected</div></div>'
        f'<div class="nx-metric-card"><div class="nx-metric-value">{html.escape(records_display)}</div>'
        f'<div class="nx-metric-label">Records Exposed</div></div>'
        "</div>"
    )
    st.markdown(metrics_html, unsafe_allow_html=True)

    sev = bi.severity.lower()
    st.markdown(
        f"Business impact: {severity_badge_html(sev)} "
        f"**{html.escape(bi.description)}** · "
        f"Downtime est. {bi.estimated_downtime_minutes} min · "
        f"Revenue: `{bi.revenue_impact}` · Reputational: `{bi.reputational_risk}`",
        unsafe_allow_html=True,
    )

    if br.data_categories_exposed:
        st.caption(f"Data categories exposed: {', '.join(br.data_categories_exposed)}")

    triggered = [f for f in impact.compliance_flags if f.triggered]
    if triggered:
        st.subheader("Compliance Alerts")

        gdpr_flags = [f for f in triggered if f.regulation == "GDPR"]
        if gdpr_flags:
            deadline_h = gdpr_flags[0].notification_deadline_hours or 72
            st.markdown(
                f'<div class="nx-gdpr-clock">'
                f'<div class="nx-clock-label">GDPR Mandatory Notification Deadline</div>'
                f'<div class="nx-clock-value">{deadline_h} hours</div>'
                f'<div style="color:#8b949e;font-size:0.85rem;margin-top:0.5rem;">'
                f"Article 33 — supervisory authority notification window"
                f"</div></div>",
                unsafe_allow_html=True,
            )

        for flag in triggered:
            deadline_text = ""
            if flag.notification_deadline_hours is not None:
                deadline_text = (
                    f'<div class="nx-deadline">⏱ Notification deadline: '
                    f"{flag.notification_deadline_hours} hours</div>"
                )
            recipients = ""
            if flag.notification_recipients:
                recipients = (
                    f"<br/><span style='color:#8b949e;font-size:0.85rem;'>"
                    f"Notify: {html.escape(', '.join(flag.notification_recipients))}"
                    f"</span>"
                )
            st.markdown(
                f'<div class="nx-compliance-alert">'
                f'<div class="nx-alert-title">🚨 {html.escape(flag.regulation)} — TRIGGERED</div>'
                f"<div>{html.escape(flag.reason)}</div>"
                f"{deadline_text}{recipients}"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.success("No regulatory compliance flags triggered.")

    if impact.root_cause_factors:
        with st.expander("Root cause factors", expanded=False):
            for factor in impact.root_cause_factors:
                st.markdown(
                    f"- **[{factor.contributing_weight}]** {factor.factor} "
                    f"(`{factor.category}`)"
                )

    st.metric("Assessment Confidence", f"{impact.confidence_score * 100:.0f}%")

    if impact.agent_notes:
        st.caption(f"Agent notes: {impact.agent_notes}")

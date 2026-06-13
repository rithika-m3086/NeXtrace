"""Attack attribution tab — entry point, MITRE kill chain, and IOC table."""

from __future__ import annotations

import html
from typing import Any, Dict, Optional

import streamlit as st

from schemas.attribution_schema import AttributionReport


def _parse_attribution(data: Optional[Dict[str, Any]]) -> Optional[AttributionReport]:
    if not data:
        return None
    try:
        return AttributionReport.model_validate(data)
    except Exception:
        return None


def render_attribution_view(stage_data: Optional[Dict[str, Any]]) -> None:
    """Render attribution report: entry point, kill chain, and IOCs."""
    report = _parse_attribution(stage_data)
    if report is None:
        st.info("No attribution report available. Run an investigation to populate this tab.")
        return

    st.metric("Attribution Confidence", f"{report.confidence_score * 100:.0f}%")

    ac = report.attack_classification
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"**Attack type:** `{ac.attack_type}`")
    col2.markdown(f"**Threat actor:** `{ac.threat_actor_type}`")
    col3.markdown(f"**Sophistication:** `{ac.sophistication_level}`")

    ep = report.entry_point
    first_seen = ep.first_seen.strftime("%Y-%m-%d %H:%M UTC") if ep.first_seen else "Unknown"
    entry_html = (
        '<div class="nx-callout">'
        '<div class="nx-callout-title">Entry Point</div>'
        f"<strong>{html.escape(ep.resource)}</strong><br/>"
        f"Method: {html.escape(ep.method)} · First seen: {html.escape(first_seen)}<br/>"
        f"<span style='color:#8b949e;'>{html.escape(ep.vulnerability_description)}</span>"
        "</div>"
    )
    st.markdown(entry_html, unsafe_allow_html=True)

    st.subheader("MITRE ATT&CK Kill Chain")
    steps_html: list[str] = []
    for step in sorted(report.attack_chain, key=lambda s: s.step):
        steps_html.append(
            f'<div class="nx-killchain-step">'
            f'<div class="nx-step-num">{step.step}</div>'
            f"<div>"
            f'<span class="nx-mitre-tag">{html.escape(step.mitre_technique_id)}</span>'
            f"<strong>{html.escape(step.mitre_technique_name)}</strong>"
            f" · {html.escape(step.mitre_tactic)}<br/>"
            f'<span style="color:#8b949e;">{html.escape(step.description)}</span>'
            f"</div></div>"
        )
    st.markdown("".join(steps_html), unsafe_allow_html=True)

    lm = report.lateral_movement
    if lm.detected:
        st.warning(
            f"Lateral movement detected: {lm.description or 'Movement across internal systems.'} "
            f"Systems: {', '.join(lm.systems_traversed) or '—'}"
        )

    dt = report.data_targeted
    st.markdown(
        f"**Data targeted:** {html.escape(dt.likely_target)} — _{html.escape(dt.evidence)}_"
    )

    st.subheader("Indicators of Compromise")
    if report.indicators_of_compromise:
        ioc_rows = ""
        for ioc in report.indicators_of_compromise:
            ioc_rows += (
                "<tr>"
                f"<td>{html.escape(ioc.ioc_type)}</td>"
                f"<td><code>{html.escape(ioc.value)}</code></td>"
                f"<td>{html.escape(ioc.description)}</td>"
                "</tr>"
            )
        ioc_table = (
            '<div class="nx-timeline-wrap">'
            '<table class="nx-timeline-table">'
            "<thead><tr><th>Type</th><th>Value</th><th>Description</th></tr></thead>"
            f"<tbody>{ioc_rows}</tbody></table></div>"
        )
        st.markdown(ioc_table, unsafe_allow_html=True)
    else:
        st.caption("No IOCs extracted.")

    if report.agent_notes:
        st.caption(f"Agent notes: {report.agent_notes}")

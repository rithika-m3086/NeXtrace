"""Forensic timeline tab — chronologically sorted events with severity highlighting."""

from __future__ import annotations

import html
from typing import Any, Dict, Optional

import streamlit as st

from schemas.timeline_schema import ForensicTimeline
from ui.styles.theme import severity_badge_html


def _parse_timeline(data: Optional[Dict[str, Any]]) -> Optional[ForensicTimeline]:
    if not data:
        return None
    try:
        return ForensicTimeline.model_validate(data)
    except Exception:
        return None


def render_timeline_view(stage_data: Optional[Dict[str, Any]]) -> None:
    """Render the forensic timeline table from pipeline stage data."""
    timeline = _parse_timeline(stage_data)
    if timeline is None:
        st.info("No forensic timeline available. Run an investigation to populate this tab.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Events Parsed", timeline.filtered_event_count)
    col2.metric("Raw Events", timeline.raw_event_count)
    col3.metric("Confidence", f"{timeline.confidence_score * 100:.0f}%")
    col4.metric("Duration", _format_duration(timeline.timeline_start, timeline.timeline_end))

    if timeline.affected_systems:
        st.caption(f"**Affected systems:** {', '.join(timeline.affected_systems)}")
    if timeline.affected_users:
        st.caption(f"**Affected users:** {', '.join(timeline.affected_users)}")

    if timeline.anomalies:
        with st.expander(f"Anomalies detected ({len(timeline.anomalies)})", expanded=False):
            for anomaly in timeline.anomalies:
                st.markdown(
                    f"{severity_badge_html(anomaly.severity)} "
                    f"**{html.escape(anomaly.anomaly_id)}** — {html.escape(anomaly.description)}",
                    unsafe_allow_html=True,
                )

    rows: list[str] = []
    for event in timeline.events:
        ts = event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        sev = event.severity.lower()
        rows.append(
            f'<tr class="nx-row-{sev}">'
            f"<td>{html.escape(ts)}</td>"
            f"<td>{severity_badge_html(sev)}</td>"
            f"<td>{html.escape(event.event_type)}</td>"
            f"<td>{html.escape(event.action)}</td>"
            f"<td>{html.escape(event.target_resource)}</td>"
            f"<td>{html.escape(event.outcome)}</td>"
            f"<td>{html.escape(event.source_ip or '—')}</td>"
            f"<td>{html.escape(event.source_user or '—')}</td>"
            f"</tr>"
        )

    table_html = (
        '<div class="nx-timeline-wrap">'
        '<table class="nx-timeline-table">'
        "<thead><tr>"
        "<th>Timestamp</th><th>Severity</th><th>Type</th><th>Action</th>"
        "<th>Target</th><th>Outcome</th><th>Source IP</th><th>User</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

    if timeline.agent_notes:
        st.caption(f"Agent notes: {timeline.agent_notes}")


def _format_duration(start, end) -> str:
    delta = end - start
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 60:
        return f"{total_minutes}m"
    hours, mins = divmod(total_minutes, 60)
    return f"{hours}h {mins}m"

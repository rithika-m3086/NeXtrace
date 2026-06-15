"""Interactive remediation checklist + ticket / PDF export.

Bridges reporting and actioning: the responder can tick off remediation items,
file them as GitHub Issues or Jira tickets in one click, or download an audit
PDF / markdown checklist for the compliance record.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import streamlit as st

from utils.pdf_report import build_incident_pdf
from utils.ticketing import (
    ExportResult,
    export_to_github,
    export_to_jira,
    remediation_to_markdown,
    remediation_to_json,
    remediation_to_csv,
)


def _remediation_plan(stages: Dict[str, Any]) -> List[Dict[str, Any]]:
    postmortem = stages.get("postmortem_complete") or {}
    plan = postmortem.get("remediation_plan") or []
    order = {"immediate": 0, "short_term": 1, "long_term": 2}
    return sorted(plan, key=lambda r: order.get(r.get("priority", ""), 99))


def _render_result(result: ExportResult) -> None:
    if result.success_count:
        st.success(f"Created {result.success_count} {result.provider} ticket(s).")
    for t in result.created:
        if t.ok and t.url:
            st.markdown(f"- ✅ [{t.title}]({t.url})")
        elif t.ok:
            st.markdown(f"- ✅ {t.title}")
        else:
            st.markdown(f"- ❌ {t.title or '(setup)'} — {t.error}")


def render_ticket_export(
    stages: Dict[str, Any],
    run_id: str,
    summary: Optional[Dict[str, Any]] = None,
    org_name: str = "Organization",
) -> None:
    """Render the interactive remediation checklist and export controls."""
    plan = _remediation_plan(stages)
    if not plan:
        st.info("No remediation plan available yet. Run an investigation to populate it.")
        return

    incident_ref = f"NeXtrace incident {run_id}"

    st.markdown("#### Interactive Remediation Checklist")
    done = 0
    for item in plan:
        key = f"chk_{run_id}_{item.get('action_id', item.get('title', ''))}"
        label = f"**[{item.get('priority', '').upper()}]** {item.get('title', '')}"
        checked = st.checkbox(label, key=key)
        if checked:
            done += 1
        st.caption(
            f"{item.get('description', '')}  \n"
            f"Owner: {item.get('owner', '—')} · Effort: {item.get('estimated_effort', '—')} · "
            f"Verify: {item.get('verification_method', '—')}"
        )
    st.progress(done / len(plan) if plan else 0.0,
                text=f"{done}/{len(plan)} remediation tasks acknowledged")

    st.divider()
    st.markdown("#### Export")
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    # GitHub.
    with col1:
        gh_ready = bool(os.getenv("GITHUB_TOKEN")) and not os.getenv("GITHUB_TOKEN", "").startswith("your_")
        if st.button("Export to GitHub Issues", use_container_width=True, disabled=not gh_ready,
                     help=None if gh_ready else "Set GITHUB_TOKEN and GITHUB_REPO in your environment."):
            with st.spinner("Filing GitHub issues…"):
                st.session_state["ticket_result"] = export_to_github(plan, incident_ref)
        if not gh_ready:
            st.caption("Configure `GITHUB_TOKEN` + `GITHUB_REPO`.")

    # Jira.
    with col2:
        jira_ready = bool(os.getenv("JIRA_API_TOKEN")) and not os.getenv("JIRA_API_TOKEN", "").startswith("your_")
        if st.button("Export to Jira", use_container_width=True, disabled=not jira_ready,
                     help=None if jira_ready else "Set Jira env vars to enable."):
            with st.spinner("Filing Jira issues…"):
                st.session_state["ticket_result"] = export_to_jira(plan, incident_ref)
        if not jira_ready:
            st.caption("Configure `JIRA_*` env vars.")

    # Markdown checklist download.
    with col3:
        md = remediation_to_markdown(plan, incident_ref)
        st.download_button(
            "Download checklist (.md)",
            data=md,
            file_name=f"remediation_{run_id[:8]}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    # PDF audit report.
    with col4:
        pdf_bytes = build_incident_pdf(stages, summary or {}, run_id, org_name=org_name)
        if pdf_bytes:
            st.download_button(
                "Download PDF report",
                data=pdf_bytes,
                file_name=f"nextrace_incident_{run_id[:8]}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.caption("Install `reportlab` for PDF export.")

    # JSON checklist download.
    with col5:
        js_data = remediation_to_json(plan, incident_ref)
        st.download_button(
            "Download checklist (.json)",
            data=js_data,
            file_name=f"remediation_{run_id[:8]}.json",
            mime="application/json",
            use_container_width=True,
        )

    # CSV checklist download.
    with col6:
        csv_data = remediation_to_csv(plan, incident_ref)
        st.download_button(
            "Download checklist (.csv)",
            data=csv_data,
            file_name=f"remediation_{run_id[:8]}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if st.session_state.get("ticket_result"):
        st.divider()
        _render_result(st.session_state["ticket_result"])

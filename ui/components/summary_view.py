"""Top-of-report incident summary — overall severity + agent confidence.

Surfaces the single most important numbers (severity, confidence, blast radius,
compliance exposure, PII redactions) as a row of console metric cards so a judge
or responder grasps the verdict before scrolling into the detail tabs.
"""

from __future__ import annotations

import html
from typing import Any, Dict

import streamlit as st

from ui.styles.theme import COLORS, severity_badge_html, severity_color
from utils.severity import aggregate_summary


def _metric_card(value: str, label: str, value_color: str = COLORS["accent"]) -> str:
    return (
        f'<div class="nx-metric-card">'
        f'<div class="nx-metric-value" style="color:{value_color};">{value}</div>'
        f'<div class="nx-metric-label">{html.escape(label)}</div>'
        f"</div>"
    )


def render_incident_summary(stages: Dict[str, Any]) -> Dict[str, Any]:
    """Render the summary band and return the computed summary dict."""
    summary = aggregate_summary(stages)

    sev = (summary.get("severity") or "unknown").lower()
    sev_color = severity_color(sev) if sev != "unknown" else COLORS["text_secondary"]
    conf = summary.get("overall_confidence")
    conf_str = f"{conf * 100:.0f}%" if isinstance(conf, (int, float)) else "—"

    records = summary.get("records_exposed")
    records_str = "Unknown" if records in (None, -1) else f"{records:,}"
    compliance_n = summary.get("compliance_count", 0)

    st.markdown(
        '<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;'
        'color:#8b949e;margin:0.25rem 0 0.5rem 0;">Incident Verdict</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(5)
    cards = [
        _metric_card(sev.upper(), "Overall severity", sev_color),
        _metric_card(conf_str, "Agent confidence"),
        _metric_card(records_str, "Records exposed",
                     COLORS["critical"] if isinstance(records, int) and records > 0 else COLORS["accent"]),
        _metric_card(str(compliance_n), "Compliance flags",
                     COLORS["high"] if compliance_n else COLORS["low"]),
        _metric_card(str(summary.get("redactions", 0)), "PII redacted",
                     COLORS["low"]),
    ]
    for col, card in zip(cols, cards):
        col.markdown(card, unsafe_allow_html=True)

    # Secondary line: attack type, entry point, regulations.
    bits = []
    if summary.get("attack_type"):
        bits.append(f"Attack: **{summary['attack_type'].replace('_', ' ')}**")
    if summary.get("entry_point"):
        bits.append(f"Entry point: `{summary['entry_point']}`")
    if summary.get("compliance_regulations"):
        regs = ", ".join(r for r in summary["compliance_regulations"] if r and r != "none")
        if regs:
            bits.append(f"Regulations: **{regs}**")
    if bits:
        st.markdown(" &nbsp;·&nbsp; ".join(bits), unsafe_allow_html=True)

    # Per-agent confidence chips.
    breakdown = summary.get("confidence_breakdown") or {}
    chips = []
    for name, val in breakdown.items():
        if isinstance(val, (int, float)):
            chips.append(
                f'<span class="nx-mitre-tag" style="color:{COLORS["accent"]};'
                f'background:{COLORS["accent_dim"]};">{html.escape(name)} {val:.0%}</span>'
            )
    if chips:
        st.markdown(
            '<div style="margin-top:0.4rem;">' + "".join(chips) + "</div>",
            unsafe_allow_html=True,
        )

    return summary

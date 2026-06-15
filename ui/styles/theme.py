"""Dark security-console theme tokens and Streamlit CSS injection."""

from __future__ import annotations

from typing import Literal

import streamlit as st

Severity = Literal["critical", "high", "medium", "low"]

# ── Color tokens ──────────────────────────────────────────────────────────────
COLORS = {
    "bg_primary": "#0d1117",
    "bg_panel": "#161b22",
    "bg_elevated": "#1c2128",
    "border": "#30363d",
    "border_subtle": "#21262d",
    "text_primary": "#e6edf3",
    "text_secondary": "#8b949e",
    "text_muted": "#6e7681",
    "accent": "#58a6ff",
    "accent_dim": "#388bfd33",
    "mono": "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace",
    "critical": "#ff4444",
    "critical_bg": "#ff444418",
    "high": "#ff8c00",
    "high_bg": "#ff8c0018",
    "medium": "#f0b429",
    "medium_bg": "#f0b42918",
    "low": "#3fb950",
    "low_bg": "#3fb95018",
    "success": "#3fb950",
    "warning": "#d29922",
    "error": "#f85149",
    "processing": "#58a6ff",
}

SEVERITY_COLORS: dict[str, tuple[str, str]] = {
    "critical": (COLORS["critical"], COLORS["critical_bg"]),
    "high": (COLORS["high"], COLORS["high_bg"]),
    "medium": (COLORS["medium"], COLORS["medium_bg"]),
    "low": (COLORS["low"], COLORS["low_bg"]),
}


def severity_color(severity: str) -> str:
    """Return foreground hex color for a severity level."""
    return SEVERITY_COLORS.get(severity.lower(), (COLORS["text_secondary"], ""))[0]


def severity_bg(severity: str) -> str:
    """Return background hex color for a severity level."""
    return SEVERITY_COLORS.get(severity.lower(), ("", COLORS["bg_elevated"]))[1]


def inject_theme() -> None:
    """Inject global dark security-console CSS into the Streamlit page."""
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');

    /* ── Base page ── */
    .stApp {{
        background-color: {COLORS["bg_primary"]};
        color: {COLORS["text_primary"]};
    }}

    header[data-testid="stHeader"] {{
        background-color: transparent !important;
    }}

    [data-testid="stSidebar"] {{
        background-color: {COLORS["bg_panel"]};
        border-right: 1px solid {COLORS["border"]};
    }}

    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] label {{
        color: {COLORS["text_primary"]} !important;
    }}

    h1, h2, h3, h4 {{
        color: {COLORS["text_primary"]} !important;
        font-weight: 600 !important;
    }}

    /* ── Metric cards ── */
    .nx-metric-card {{
        background: {COLORS["bg_panel"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 8px;
        padding: 1rem 1.25rem;
        text-align: center;
    }}
    .nx-metric-card .nx-metric-value {{
        font-family: {COLORS["mono"]};
        font-size: 2rem;
        font-weight: 600;
        color: {COLORS["accent"]};
        line-height: 1.2;
    }}
    .nx-metric-card .nx-metric-label {{
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: {COLORS["text_secondary"]};
        margin-top: 0.35rem;
    }}

    /* ── Severity badges ── */
    .nx-severity-badge {{
        display: inline-block;
        font-family: {COLORS["mono"]};
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding: 0.15rem 0.55rem;
        border-radius: 4px;
        border: 1px solid transparent;
    }}
    .nx-severity-critical {{ color: {COLORS["critical"]}; background: {COLORS["critical_bg"]}; border-color: {COLORS["critical"]}44; }}
    .nx-severity-high     {{ color: {COLORS["high"]};     background: {COLORS["high_bg"]};     border-color: {COLORS["high"]}44; }}
    .nx-severity-medium   {{ color: {COLORS["medium"]};   background: {COLORS["medium_bg"]};   border-color: {COLORS["medium"]}44; }}
    .nx-severity-low      {{ color: {COLORS["low"]};      background: {COLORS["low_bg"]};      border-color: {COLORS["low"]}44; }}

    /* ── Band status log ── */
    .nx-status-log {{
        background: {COLORS["bg_panel"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-family: {COLORS["mono"]};
        font-size: 0.82rem;
        max-height: 420px;
        overflow-y: auto;
    }}
    .nx-status-log .nx-log-line {{
        display: flex;
        align-items: flex-start;
        gap: 0.6rem;
        padding: 0.35rem 0;
        border-bottom: 1px solid {COLORS["border_subtle"]};
        animation: nx-fade-in 0.35s ease-out;
    }}
    .nx-status-log .nx-log-line:last-child {{
        border-bottom: none;
    }}
    .nx-log-icon {{ flex-shrink: 0; width: 1.2rem; text-align: center; }}
    .nx-log-meta {{
        color: {COLORS["text_muted"]};
        font-size: 0.72rem;
        margin-left: auto;
        white-space: nowrap;
    }}
    .nx-log-agent {{ color: {COLORS["accent"]}; font-weight: 600; }}
    .nx-log-channel {{ color: {COLORS["text_secondary"]}; }}
    .nx-log-status-processing {{ color: {COLORS["processing"]}; }}
    .nx-log-status-completed  {{ color: {COLORS["success"]}; }}
    .nx-log-status-error      {{ color: {COLORS["error"]}; }}

    @keyframes nx-fade-in {{
        from {{ opacity: 0; transform: translateY(4px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}

    /* ── Timeline table ── */
    .nx-timeline-wrap {{
        overflow-x: auto;
        border: 1px solid {COLORS["border"]};
        border-radius: 8px;
    }}
    .nx-timeline-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
    }}
    .nx-timeline-table th {{
        background: {COLORS["bg_elevated"]};
        color: {COLORS["text_secondary"]};
        font-family: {COLORS["mono"]};
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding: 0.6rem 0.75rem;
        text-align: left;
        border-bottom: 1px solid {COLORS["border"]};
    }}
    .nx-timeline-table td {{
        padding: 0.55rem 0.75rem;
        border-bottom: 1px solid {COLORS["border_subtle"]};
        color: {COLORS["text_primary"]};
        vertical-align: top;
    }}
    .nx-timeline-table tr:hover td {{
        background: {COLORS["bg_elevated"]};
    }}
    .nx-row-critical td {{ border-left: 3px solid {COLORS["critical"]}; }}
    .nx-row-high     td {{ border-left: 3px solid {COLORS["high"]}; }}
    .nx-row-medium   td {{ border-left: 3px solid {COLORS["medium"]}; }}
    .nx-row-low      td {{ border-left: 3px solid {COLORS["low"]}; }}

    /* ── Callout panels ── */
    .nx-callout {{
        background: {COLORS["bg_panel"]};
        border: 1px solid {COLORS["border"]};
        border-left: 4px solid {COLORS["accent"]};
        border-radius: 6px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
    }}
    .nx-callout-title {{
        font-family: {COLORS["mono"]};
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: {COLORS["accent"]};
        margin-bottom: 0.4rem;
    }}

    /* ── Kill chain steps ── */
    .nx-killchain-step {{
        display: flex;
        gap: 1rem;
        padding: 0.75rem 0;
        border-bottom: 1px solid {COLORS["border_subtle"]};
    }}
    .nx-step-num {{
        flex-shrink: 0;
        width: 2rem;
        height: 2rem;
        border-radius: 50%;
        background: {COLORS["accent_dim"]};
        border: 1px solid {COLORS["accent"]};
        color: {COLORS["accent"]};
        font-family: {COLORS["mono"]};
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.85rem;
    }}
    .nx-mitre-tag {{
        font-family: {COLORS["mono"]};
        font-size: 0.75rem;
        color: {COLORS["high"]};
        background: {COLORS["high_bg"]};
        padding: 0.1rem 0.45rem;
        border-radius: 3px;
        margin-right: 0.4rem;
    }}

    /* ── Compliance alert banners ── */
    .nx-compliance-alert {{
        background: {COLORS["critical_bg"]};
        border: 1px solid {COLORS["critical"]}66;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }}
    .nx-compliance-alert .nx-alert-title {{
        color: {COLORS["critical"]};
        font-weight: 600;
        font-size: 1rem;
        margin-bottom: 0.35rem;
    }}
    .nx-compliance-alert .nx-deadline {{
        font-family: {COLORS["mono"]};
        color: {COLORS["high"]};
        font-size: 0.9rem;
        margin-top: 0.4rem;
    }}
    .nx-gdpr-clock {{
        background: linear-gradient(135deg, {COLORS["critical_bg"]}, {COLORS["high_bg"]});
        border: 2px solid {COLORS["critical"]};
        border-radius: 10px;
        padding: 1.25rem;
        text-align: center;
        margin-bottom: 1rem;
    }}
    .nx-gdpr-clock .nx-clock-value {{
        font-family: {COLORS["mono"]};
        font-size: 2.5rem;
        font-weight: 700;
        color: {COLORS["critical"]};
    }}
    .nx-gdpr-clock .nx-clock-label {{
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: {COLORS["text_secondary"]};
    }}

    /* ── Remediation tasks ── */
    .nx-remediation-item {{
        background: {COLORS["bg_panel"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 6px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.5rem;
    }}
    .nx-priority-immediate  {{ border-left: 4px solid {COLORS["critical"]}; }}
    .nx-priority-short_term {{ border-left: 4px solid {COLORS["high"]}; }}
    .nx-priority-long_term  {{ border-left: 4px solid {COLORS["medium"]}; }}

    /* ── Streamlit widget overrides ── */
    .stButton > button[kind="primary"] {{
        background-color: {COLORS["accent"]} !important;
        color: {COLORS["bg_primary"]} !important;
        border: none !important;
        font-weight: 600 !important;
    }}
    div[data-testid="stMetric"] {{
        background: {COLORS["bg_panel"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 8px;
        padding: 0.75rem;
    }}

    /* Dropdown / Selectbox styling */
    div[data-baseweb="select"] > div,
    div[data-baseweb="select"] ul {{
        background-color: {COLORS["bg_panel"]} !important;
        border-color: {COLORS["border"]} !important;
        color: {COLORS["text_primary"]} !important;
    }}
    div[data-baseweb="select"] li {{
        background-color: {COLORS["bg_panel"]} !important;
        color: {COLORS["text_primary"]} !important;
    }}
    div[data-baseweb="select"] li:hover {{
        background-color: {COLORS["bg_elevated"]} !important;
    }}
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] svg {{
        color: {COLORS["text_primary"]} !important;
    }}

    /* Text input / Text area styling */
    div[data-testid="stTextInput"] > div,
    div[data-testid="stTextArea"] > div,
    div[data-baseweb="base-input"],
    div[data-baseweb="input"] {{
        background-color: {COLORS["bg_panel"]} !important;
        border-color: {COLORS["border"]} !important;
        color: {COLORS["text_primary"]} !important;
    }}
    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-baseweb="base-input"] input,
    div[data-baseweb="input"] input,
    div[data-baseweb="textarea"] textarea {{
        background-color: transparent !important;
        color: {COLORS["text_primary"]} !important;
    }}

    /* Radio choices & checkbox text color */
    div[data-testid="stRadio"] label,
    div[data-testid="stRadio"] label p,
    div[data-testid="stCheckbox"] label,
    div[data-testid="stCheckbox"] label p,
    div[data-testid="stToggle"] label,
    div[data-testid="stToggle"] label p {{
        color: {COLORS["text_primary"]} !important;
    }}

    /* Widget labels */
    div[data-testid="stWidgetLabel"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] label p,
    [data-testid="stSidebar"] div[data-testid="stWidgetLabel"] p {{
        color: {COLORS["text_secondary"]} !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def severity_badge_html(severity: str) -> str:
    """Render an inline severity badge."""
    sev = severity.lower()
    return f'<span class="nx-severity-badge nx-severity-{sev}">{sev}</span>'

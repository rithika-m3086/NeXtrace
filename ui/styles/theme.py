"""Dark security-console theme — Streamlit CSS injection.

Implements the **NeXtrace Design System** (Claude Design handoff) on top of the
existing Streamlit app: a refined dark SOC console with a full design-token
layer (colors, Inter + JetBrains Mono type, 8px spacing grid, radii, elevation,
status glows, calm motion). The palette is the product's own; the system adds
the grotesk UI font, accent hover/press states, subtle shadows, status-dot
glows, and the fade-in / processing-pulse / glow-pulse micro-interactions that
make the live agent hand-off log feel alive.
"""

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
    "accent_hover": "#79b8ff",
    "accent_press": "#388bfd",
    "accent_dim": "#388bfd33",
    "accent_faint": "#58a6ff14",
    "mono": "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace",
    "sans": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif",
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
    "live": "#3fb950",
    "mock": "#d29922",
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
    """Inject the NeXtrace Design System CSS into the Streamlit page."""
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    /* ── Design tokens ───────────────────────────────────────────────── */
    :root {
        --nx-bg-base: #0d1117;
        --nx-bg-panel: #161b22;
        --nx-bg-elevated: #1c2128;
        --nx-border: #30363d;
        --nx-border-subtle: #21262d;
        --nx-text-primary: #e6edf3;
        --nx-text-secondary: #8b949e;
        --nx-text-muted: #6e7681;
        --nx-accent: #58a6ff;
        --nx-accent-hover: #79b8ff;
        --nx-accent-press: #388bfd;
        --nx-accent-dim: #388bfd33;
        --nx-accent-faint: #58a6ff14;
        --nx-critical: #ff4444;  --nx-critical-bg: #ff444418;
        --nx-high: #ff8c00;      --nx-high-bg: #ff8c0018;
        --nx-medium: #f0b429;    --nx-medium-bg: #f0b42918;
        --nx-low: #3fb950;       --nx-low-bg: #3fb95018;
        --nx-success: #3fb950;   --nx-warning: #d29922;   --nx-error: #f85149;
        --nx-processing: #58a6ff; --nx-live: #3fb950; --nx-mock: #d29922;

        --nx-font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
        --nx-font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'SF Mono', Consolas, monospace;
        --nx-tracking-wide: 0.06em;  --nx-tracking-wider: 0.08em;  --nx-tracking-widest: 0.1em;

        --nx-radius-xs: 3px; --nx-radius-sm: 4px; --nx-radius-md: 6px;
        --nx-radius-lg: 8px; --nx-radius-xl: 10px; --nx-radius-full: 9999px;

        --nx-shadow-sm: 0 1px 2px rgba(1,4,9,0.4);
        --nx-shadow-md: 0 4px 12px rgba(1,4,9,0.5);
        --nx-shadow-lg: 0 8px 28px rgba(1,4,9,0.6);
        --nx-glow-accent: 0 0 8px rgba(88,166,255,0.6);
        --nx-glow-live: 0 0 8px rgba(63,185,80,0.7);
        --nx-glow-mock: 0 0 8px rgba(210,153,34,0.7);
        --nx-ring: 0 0 0 3px rgba(88,166,255,0.35);
        --nx-ease-out: cubic-bezier(0.16, 1, 0.3, 1);
        --nx-ease-inout: cubic-bezier(0.65, 0, 0.35, 1);
        --nx-dur-fast: 0.12s; --nx-dur-base: 0.2s; --nx-dur-slow: 0.35s;
    }

    /* ── Base page + typography ─────────────────────────────────────── */
    .stApp { background-color: var(--nx-bg-base); color: var(--nx-text-primary); }
    html, body, .stApp, [data-testid="stAppViewContainer"],
    .stMarkdown, p, span, div, label, button, input, select, textarea {
        font-family: var(--nx-font-sans);
    }
    h1, h2, h3, h4 {
        color: var(--nx-text-primary) !important;
        font-family: var(--nx-font-sans);
        font-weight: 600 !important;
        letter-spacing: -0.01em;
    }
    /* Title gets a touch more presence */
    h1 { font-weight: 700 !important; letter-spacing: -0.02em; }
    code, kbd, pre, .nx-mono { font-family: var(--nx-font-mono); }

    [data-testid="stSidebar"] {
        background-color: var(--nx-bg-panel);
        border-right: 1px solid var(--nx-border);
    }
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] label { color: var(--nx-text-primary) !important; }
    [data-testid="stSidebar"] > div { padding-top: 1.25rem; }
    /* Sidebar section headers → refined uppercase eyebrows */
    [data-testid="stSidebar"] h2 { font-size: 0.95rem !important; font-weight: 600 !important; }
    [data-testid="stSidebar"] h3 {
        font-size: 0.72rem !important;
        text-transform: uppercase;
        letter-spacing: var(--nx-tracking-wider);
        color: var(--nx-text-secondary) !important;
        margin-top: 0.5rem !important;
    }

    /* ── Hide Streamlit prototype chrome (Deploy btn, menu, footer, ribbon) ── */
    [data-testid="stHeader"] { background: transparent !important; }
    [data-testid="stToolbar"], [data-testid="stStatusWidget"],
    #MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }
    /* Tighten content gutters now the top bar is gone */
    .block-container, [data-testid="stMainBlockContainer"] {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1400px;
    }

    /* ── Product app-bar (replaces the bare H1) ── */
    .nx-appbar {
        display: flex; align-items: center; justify-content: space-between;
        gap: 1rem; padding-bottom: 1rem; margin-bottom: 1.5rem;
        border-bottom: 1px solid var(--nx-border);
    }
    .nx-appbar-left { display: flex; align-items: center; gap: 0.85rem; }
    .nx-logo {
        display: flex; align-items: center; justify-content: center;
        width: 44px; height: 44px; border-radius: var(--nx-radius-lg);
        background: var(--nx-accent-faint); border: 1px solid #58a6ff33;
        box-shadow: var(--nx-shadow-sm); flex-shrink: 0;
    }
    .nx-appbar-title {
        font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em;
        line-height: 1.1; color: var(--nx-text-primary);
    }
    .nx-appbar-sub { font-size: 0.8rem; color: var(--nx-text-secondary); margin-top: 0.1rem; }
    .nx-appbar-chip {
        font-family: var(--nx-font-mono); font-size: 0.72rem; color: var(--nx-text-secondary);
        border: 1px solid var(--nx-border); background: var(--nx-bg-panel);
        padding: 0.35rem 0.75rem; border-radius: var(--nx-radius-full); white-space: nowrap;
    }

    /* ── Sidebar brand block ── */
    .nx-sb-brand {
        display: flex; align-items: center; gap: 0.6rem;
        padding-bottom: 0.85rem; margin-bottom: 0.85rem;
        border-bottom: 1px solid var(--nx-border-subtle);
    }
    .nx-sb-logo {
        width: 32px; height: 32px; border-radius: var(--nx-radius-md);
        background: var(--nx-accent-faint); border: 1px solid #58a6ff33;
        display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    }
    .nx-sb-name { font-weight: 700; letter-spacing: -0.01em; font-size: 1rem; line-height: 1.1; }
    .nx-sb-tag {
        font-size: 0.65rem; color: var(--nx-text-muted); text-transform: uppercase;
        letter-spacing: var(--nx-tracking-wide); margin-top: 0.1rem;
    }

    /* ── Section eyebrow (main area) ── */
    .nx-eyebrow {
        font-family: var(--nx-font-mono); font-size: 0.7rem; text-transform: uppercase;
        letter-spacing: var(--nx-tracking-widest); color: var(--nx-text-secondary);
        margin: 0.25rem 0 0.6rem 0;
    }

    /* ── Empty state ── */
    .nx-empty {
        border: 1px dashed var(--nx-border); border-radius: var(--nx-radius-lg);
        background: linear-gradient(180deg, var(--nx-bg-panel), var(--nx-bg-base));
        padding: 3rem 2rem; text-align: center;
    }
    .nx-empty-icon { font-size: 1.9rem; opacity: 0.85; }
    .nx-empty-title { font-weight: 600; font-size: 1.05rem; margin-top: 0.6rem; color: var(--nx-text-primary); }
    .nx-empty-sub { font-size: 0.85rem; color: var(--nx-text-secondary); margin-top: 0.4rem; line-height: 1.6; }

    /* ── Slider + radio accent polish ── */
    [data-baseweb="slider"] [role="slider"] { background-color: var(--nx-accent) !important; }

    /* ── Metric cards ───────────────────────────────────────────────── */
    .nx-metric-card {
        background: var(--nx-bg-panel);
        border: 1px solid var(--nx-border);
        border-radius: var(--nx-radius-lg);
        padding: 1rem 1.25rem;
        text-align: center;
        box-shadow: var(--nx-shadow-sm);
        transition: transform var(--nx-dur-base) var(--nx-ease-out),
                    border-color var(--nx-dur-base) var(--nx-ease-out),
                    box-shadow var(--nx-dur-base) var(--nx-ease-out);
    }
    .nx-metric-card:hover {
        transform: translateY(-2px);
        border-color: var(--nx-accent);
        box-shadow: var(--nx-shadow-md);
    }
    .nx-metric-card .nx-metric-value {
        font-family: var(--nx-font-mono);
        font-size: 2rem;
        font-weight: 600;
        color: var(--nx-accent);
        line-height: 1.2;
    }
    .nx-metric-card .nx-metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: var(--nx-tracking-wider);
        color: var(--nx-text-secondary);
        margin-top: 0.35rem;
    }

    /* ── Severity badges ────────────────────────────────────────────── */
    .nx-severity-badge {
        display: inline-block;
        font-family: var(--nx-font-mono);
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: var(--nx-tracking-wide);
        padding: 0.15rem 0.55rem;
        border-radius: var(--nx-radius-sm);
        border: 1px solid transparent;
    }
    .nx-severity-critical { color: var(--nx-critical); background: var(--nx-critical-bg); border-color: #ff444444; }
    .nx-severity-high     { color: var(--nx-high);     background: var(--nx-high-bg);     border-color: #ff8c0044; }
    .nx-severity-medium   { color: var(--nx-medium);   background: var(--nx-medium-bg);   border-color: #f0b42944; }
    .nx-severity-low      { color: var(--nx-low);      background: var(--nx-low-bg);      border-color: #3fb95044; }

    /* ── Band status log (signature element) ────────────────────────── */
    .nx-status-log {
        background: var(--nx-bg-panel);
        border: 1px solid var(--nx-border);
        border-radius: var(--nx-radius-lg);
        padding: 0.75rem 1rem;
        font-family: var(--nx-font-mono);
        font-size: 0.8125rem;
        max-height: 440px;
        overflow-y: auto;
        box-shadow: var(--nx-shadow-sm);
    }
    .nx-status-log .nx-log-line {
        display: flex;
        align-items: flex-start;
        gap: 0.6rem;
        padding: 0.4rem 0;
        border-bottom: 1px solid var(--nx-border-subtle);
        animation: nx-fade-in 0.35s var(--nx-ease-out);
    }
    .nx-status-log .nx-log-line:last-child { border-bottom: none; }
    .nx-log-icon { flex-shrink: 0; width: 1.2rem; text-align: center; }
    /* Active "processing" lines pulse to feel alive */
    .nx-log-line:has(.nx-log-status-processing) .nx-log-icon {
        animation: nx-pulse 1.2s var(--nx-ease-inout) infinite;
    }
    .nx-log-meta {
        color: var(--nx-text-muted);
        font-size: 0.72rem;
        margin-left: auto;
        white-space: nowrap;
    }
    .nx-log-agent { color: var(--nx-accent); font-weight: 600; }
    .nx-log-channel { color: var(--nx-text-secondary); }
    .nx-log-status-processing { color: var(--nx-processing); }
    .nx-log-status-completed  { color: var(--nx-success); }
    .nx-log-status-error      { color: var(--nx-error); }

    /* ── Timeline table ─────────────────────────────────────────────── */
    .nx-timeline-wrap { overflow-x: auto; border: 1px solid var(--nx-border); border-radius: var(--nx-radius-lg); }
    .nx-timeline-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    .nx-timeline-table th {
        background: var(--nx-bg-elevated);
        color: var(--nx-text-secondary);
        font-family: var(--nx-font-mono);
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: var(--nx-tracking-wide);
        padding: 0.6rem 0.75rem;
        text-align: left;
        border-bottom: 1px solid var(--nx-border);
    }
    .nx-timeline-table td {
        padding: 0.55rem 0.75rem;
        border-bottom: 1px solid var(--nx-border-subtle);
        color: var(--nx-text-primary);
        vertical-align: top;
    }
    .nx-timeline-table tr { transition: background var(--nx-dur-fast) var(--nx-ease-out); }
    .nx-timeline-table tr:hover td { background: var(--nx-bg-elevated); }
    .nx-row-critical td { border-left: 4px solid var(--nx-critical); }
    .nx-row-high     td { border-left: 4px solid var(--nx-high); }
    .nx-row-medium   td { border-left: 4px solid var(--nx-medium); }
    .nx-row-low      td { border-left: 4px solid var(--nx-low); }

    /* ── Callout panels ─────────────────────────────────────────────── */
    .nx-callout {
        background: var(--nx-bg-panel);
        border: 1px solid var(--nx-border);
        border-left: 4px solid var(--nx-accent);
        border-radius: var(--nx-radius-md);
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: var(--nx-shadow-sm);
    }
    .nx-callout-title {
        font-family: var(--nx-font-mono);
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: var(--nx-tracking-wider);
        color: var(--nx-accent);
        margin-bottom: 0.4rem;
    }

    /* ── Kill chain steps + MITRE tags ──────────────────────────────── */
    .nx-killchain-step {
        display: flex; gap: 1rem; padding: 0.75rem 0;
        border-bottom: 1px solid var(--nx-border-subtle);
    }
    .nx-step-num {
        flex-shrink: 0; width: 2rem; height: 2rem; border-radius: var(--nx-radius-full);
        background: var(--nx-accent-dim); border: 1px solid var(--nx-accent);
        color: var(--nx-accent); font-family: var(--nx-font-mono); font-weight: 600;
        display: flex; align-items: center; justify-content: center; font-size: 0.85rem;
    }
    .nx-mitre-tag {
        font-family: var(--nx-font-mono); font-size: 0.75rem;
        color: var(--nx-high); background: var(--nx-high-bg);
        padding: 0.1rem 0.45rem; border-radius: var(--nx-radius-xs); margin-right: 0.4rem;
    }

    /* ── Compliance alerts + GDPR clock ─────────────────────────────── */
    .nx-compliance-alert {
        background: var(--nx-critical-bg);
        border: 1px solid #ff444466;
        border-radius: var(--nx-radius-lg);
        padding: 1rem 1.25rem; margin-bottom: 0.75rem;
    }
    .nx-compliance-alert .nx-alert-title { color: var(--nx-critical); font-weight: 600; font-size: 1rem; margin-bottom: 0.35rem; }
    .nx-compliance-alert .nx-deadline { font-family: var(--nx-font-mono); color: var(--nx-high); font-size: 0.9rem; margin-top: 0.4rem; }
    .nx-gdpr-clock {
        background: linear-gradient(135deg, var(--nx-critical-bg), var(--nx-high-bg));
        border: 2px solid var(--nx-critical);
        border-radius: var(--nx-radius-xl);
        padding: 1.25rem; text-align: center; margin-bottom: 1rem;
        box-shadow: var(--nx-shadow-md);
    }
    .nx-gdpr-clock .nx-clock-value { font-family: var(--nx-font-mono); font-size: 2.5rem; font-weight: 700; color: var(--nx-critical); }
    .nx-gdpr-clock .nx-clock-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: var(--nx-tracking-widest); color: var(--nx-text-secondary); }

    /* ── Remediation cards ──────────────────────────────────────────── */
    .nx-remediation-item {
        background: var(--nx-bg-panel);
        border: 1px solid var(--nx-border);
        border-radius: var(--nx-radius-md);
        padding: 0.85rem 1rem; margin-bottom: 0.5rem;
        transition: border-color var(--nx-dur-base) var(--nx-ease-out), box-shadow var(--nx-dur-base) var(--nx-ease-out);
    }
    .nx-remediation-item:hover { border-color: var(--nx-accent); box-shadow: var(--nx-shadow-sm); }
    .nx-priority-immediate  { border-left: 4px solid var(--nx-critical); }
    .nx-priority-short_term { border-left: 4px solid var(--nx-high); }
    .nx-priority-long_term  { border-left: 4px solid var(--nx-medium); }

    /* ── Streamlit widget overrides ─────────────────────────────────── */
    .stButton > button {
        border-radius: var(--nx-radius-lg) !important;
        font-weight: 600 !important;
        font-family: var(--nx-font-sans) !important;
        transition: filter var(--nx-dur-fast) var(--nx-ease-out),
                    border-color var(--nx-dur-fast) var(--nx-ease-out) !important;
    }
    .stButton > button:hover { filter: brightness(1.12); }
    .stButton > button:active { filter: brightness(0.95); }
    .stButton > button[kind="primary"] {
        background-color: var(--nx-accent) !important;
        color: var(--nx-bg-base) !important;
        border: 1px solid var(--nx-accent) !important;
        box-shadow: var(--nx-shadow-sm) !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: var(--nx-bg-elevated) !important;
        color: var(--nx-text-primary) !important;
        border: 1px solid var(--nx-border) !important;
    }
    /* Download buttons → secondary console style */
    [data-testid="stDownloadButton"] > button {
        background-color: var(--nx-bg-elevated) !important;
        color: var(--nx-text-primary) !important;
        border: 1px solid var(--nx-border) !important;
        border-radius: var(--nx-radius-lg) !important;
        font-weight: 600 !important;
    }
    [data-testid="stDownloadButton"] > button:hover { border-color: var(--nx-accent) !important; }

    /* Metric (st.metric) */
    div[data-testid="stMetric"] {
        background: var(--nx-bg-panel);
        border: 1px solid var(--nx-border);
        border-radius: var(--nx-radius-lg);
        padding: 0.75rem;
        box-shadow: var(--nx-shadow-sm);
    }

    /* Tabs — accent active underline */
    .stTabs [data-baseweb="tab-list"] { gap: 0.25rem; border-bottom: 1px solid var(--nx-border); }
    .stTabs [data-baseweb="tab"] {
        font-family: var(--nx-font-sans); font-weight: 500;
        color: var(--nx-text-secondary);
    }
    .stTabs [aria-selected="true"] { color: var(--nx-accent) !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: var(--nx-accent) !important; }

    /* Inputs / selects / textarea */
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-baseweb="select"] > div {
        background-color: var(--nx-bg-elevated) !important;
        border-radius: var(--nx-radius-sm) !important;
    }
    [data-testid="stTextInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus {
        box-shadow: var(--nx-ring) !important;
        border-color: var(--nx-accent) !important;
    }

    /* Inline code chips */
    code { color: var(--nx-accent); background: var(--nx-accent-faint); border-radius: var(--nx-radius-xs); }

    /* ── Keyframes ──────────────────────────────────────────────────── */
    @keyframes nx-fade-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes nx-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
    @keyframes nx-glow-pulse {
        0%,100% { box-shadow: 0 0 6px rgba(63,185,80,0.5); }
        50%     { box-shadow: 0 0 12px rgba(63,185,80,0.9); }
    }
    @keyframes nx-glow-pulse-mock {
        0%,100% { box-shadow: 0 0 6px rgba(210,153,34,0.5); }
        50%     { box-shadow: 0 0 12px rgba(210,153,34,0.9); }
    }
    @keyframes nx-scan { 0% { transform: translateX(-100%); } 100% { transform: translateX(400%); } }
    @keyframes nx-spin { to { transform: rotate(360deg); } }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def severity_badge_html(severity: str) -> str:
    """Render an inline severity badge."""
    sev = severity.lower()
    return f'<span class="nx-severity-badge nx-severity-{sev}">{sev}</span>'

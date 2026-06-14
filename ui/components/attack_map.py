"""Visual attack journey — Mermaid attack-path diagram + GeoIP origin map."""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st
import streamlit.components.v1 as components

from utils.geoip import extract_source_ips, resolve_ips
from utils.mermaid import build_attack_flow, mermaid_html


def render_attack_flow(attribution: Dict[str, Any]) -> None:
    """Render the attacker's journey as a Mermaid flowchart."""
    diagram = build_attack_flow(attribution)
    if not diagram:
        st.caption("Attack-path diagram unavailable — no attack chain was reconstructed.")
        return
    st.markdown("#### Attack Path")
    st.caption("Reconstructed from the MITRE ATT&CK chain — read left to right.")
    components.html(mermaid_html(diagram), height=380, scrolling=True)
    with st.expander("View Mermaid source", expanded=False):
        st.code(diagram, language="mermaid")


def render_geo_map(stages: Dict[str, Any]) -> None:
    """Resolve attacker source IPs and pin their origins on a map."""
    ips = extract_source_ips(stages)
    if not ips:
        st.caption("No public source IPs were observed in the evidence.")
        return

    st.markdown("#### Attacker Origin")
    with st.spinner("Resolving source IP geolocation…"):
        records = resolve_ips(ips)

    if not records:
        st.caption(
            f"Observed {len(ips)} source IP(s), but none resolved to a public "
            "geolocation (private/internal ranges or lookup unavailable)."
        )
        return

    # Map points.
    try:
        import pandas as pd

        df = pd.DataFrame(
            [{"lat": r["lat"], "lon": r["lon"]} for r in records if r.get("lat") and r.get("lon")]
        )
        if not df.empty:
            st.map(df, size=40, color="#ff4444")
    except Exception:  # noqa: BLE001
        pass

    # Detail table.
    rows: List[Dict[str, Any]] = []
    for r in records:
        rows.append({
            "IP": r.get("ip"),
            "Country": r.get("country"),
            "City": r.get("city"),
            "ISP": r.get("isp") or r.get("org"),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(
        "Geolocation is approximate (ip-api.com) and shown for triage context — "
        "attackers frequently route through VPNs, proxies, or compromised hosts."
    )

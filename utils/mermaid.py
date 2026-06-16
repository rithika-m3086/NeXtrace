"""Render the attacker's journey as a Mermaid flowchart.

Reading a list of MITRE steps is tedious; a left-to-right state diagram makes
the attack path obvious at a glance (Credential Committed → S3 Recon → Bulk
Exfiltration). Built deterministically from Agent 2's structured
``attack_chain`` so there is no extra LLM call and no hallucination risk.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


_TACTIC_CLASS = {
    "initial access": "entry",
    "execution": "exec",
    "persistence": "persist",
    "privilege escalation": "escalate",
    "defense evasion": "evade",
    "credential access": "creds",
    "discovery": "discover",
    "lateral movement": "lateral",
    "collection": "collect",
    "exfiltration": "exfil",
    "impact": "impact",
}


def _sanitize(text: str, limit: int = 42) -> str:
    """Make a label safe for Mermaid node text."""
    text = (text or "").replace('"', "'").replace("\n", " ").strip()
    text = text.replace("[", "(").replace("]", ")").replace("{", "(").replace("}", ")")
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def build_attack_flow(attribution: Optional[Dict[str, Any]]) -> Optional[str]:
    """Produce a Mermaid ``flowchart LR`` string from an attribution payload.

    Returns ``None`` if there is no usable attack chain.
    """
    if not attribution:
        return None

    chain = attribution.get("attack_chain") or []
    if not chain:
        return None

    lines = ["flowchart LR"]
    class_defs = {
        "entry": "fill:#7f1d1d,stroke:#f87171,color:#fee2e2",
        "exfil": "fill:#831843,stroke:#f472b6,color:#fce7f3",
        "impact": "fill:#713f12,stroke:#fbbf24,color:#fef3c7",
        "default": "fill:#1e293b,stroke:#38bdf8,color:#e2e8f0",
    }

    # Optional explicit entry-point node.
    entry = attribution.get("entry_point") or {}
    prev_node = None
    if entry.get("identified") and entry.get("resource"):
        label = _sanitize(f"Entry: {entry.get('resource')}")
        lines.append(f'    E0["🚪 {label}"]:::entry')
        prev_node = "E0"

    node_classes: Dict[str, str] = {}
    for raw in sorted(chain, key=lambda s: s.get("step", 0)):
        step = raw.get("step", 0)
        node_id = f"S{step}"
        tactic = (raw.get("mitre_tactic") or "").strip().lower()
        tech_id = raw.get("mitre_technique_id", "")
        desc = _sanitize(raw.get("description") or raw.get("mitre_technique_name") or tactic)
        tactic_label = _sanitize(raw.get("mitre_tactic") or "", 28)
        # htmlLabels (enabled via securityLevel:'loose' in mermaid_html) supports
        # <br/> and <b>; avoid <small>, which older mermaid parsers choke on.
        label = f"<b>{tactic_label}</b><br/>{desc}<br/>{tech_id}"
        cls = _TACTIC_CLASS.get(tactic, "default")
        if cls in ("entry", "exfil", "impact"):
            node_classes[node_id] = cls
        lines.append(f'    {node_id}["{label}"]')
        if prev_node is not None:
            lines.append(f"    {prev_node} --> {node_id}")
        prev_node = node_id

    # Class definitions and assignments.
    for name, style in class_defs.items():
        if name == "default":
            continue
        lines.append(f"    classDef {name} {style}")
    lines.append(f"    classDef default {class_defs['default']}")
    for node_id, cls in node_classes.items():
        lines.append(f"    class {node_id} {cls}")

    return "\n".join(lines)


def mermaid_html(diagram: str, height: int = 360) -> str:
    """Wrap a Mermaid diagram in a self-contained HTML snippet (mermaid.js CDN).

    Usable directly with ``streamlit.components.v1.html`` — no extra dependency.
    """
    safe = diagram.replace("`", "\\`")
    return f"""
<div class="mermaid-wrap" style="background:#0b1220;border-radius:12px;padding:12px;">
  <pre class="mermaid" style="background:transparent;">{safe}</pre>
</div>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{
    startOnLoad: false,
    securityLevel: 'loose',
    theme: 'dark',
    flowchart: {{ htmlLabels: true, curve: 'basis', useMaxWidth: true }},
    themeVariables: {{ fontSize: '13px' }}
  }});
  try {{
    await mermaid.run({{ querySelector: '.mermaid' }});
  }} catch (e) {{
    document.querySelector('.mermaid-wrap').insertAdjacentHTML(
      'beforeend', '<div style="color:#f87171;font-size:12px;">Diagram render error: ' + e + '</div>');
  }}
</script>"""

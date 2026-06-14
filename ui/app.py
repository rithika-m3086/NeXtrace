"""NeXtrace Streamlit dashboard — live Band coordination and investigation results."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv

# Ensure project root is on sys.path when launched via `streamlit run ui/app.py`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.client import BandClient
from core.coordinator import BandCoordinator
from core.live_band import is_live_configured
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.state_manager import PipelineStateManager
from schemas.input_schema import LogSource
from ui.components.attack_map import render_attack_flow, render_geo_map
from ui.components.attribution_view import render_attribution_view
from ui.components.band_status import BandStatusMonitor, render_band_status_log, render_log_html
from ui.components.impact_view import render_impact_view
from ui.components.postmortem_view import render_postmortem_view
from ui.components.summary_view import render_incident_summary
from ui.components.ticket_export import render_ticket_export
from ui.components.timeline_view import render_timeline_view
from ui.styles.theme import COLORS, inject_theme

load_dotenv(ROOT / ".env")

SCENARIOS: Dict[str, List[Dict[str, str]]] = {
    "API Key Leak (GitHub + CloudTrail + S3)": [
        {"file": "api_key_leak_github_audit.json", "source_name": "github_audit", "source_type": "github_audit"},
        {"file": "api_key_leak_cloudtrail.json", "source_name": "cloudtrail", "source_type": "cloudtrail"},
        {"file": "api_key_leak_s3_access.json", "source_name": "s3_access", "source_type": "s3_access"},
    ],
    "Sparse Logs (Insufficient Evidence)": [
        {"file": "sparse_logs.json", "source_name": "cloudtrail", "source_type": "cloudtrail"},
    ],
    "Noisy Logs (Buried Attack)": [
        {"file": "noisy_logs.json", "source_name": "cloudtrail", "source_type": "cloudtrail"},
    ],
    "Credential Stuffing (Brute Force)": [
        {"file": "credential_stuffing_logs.json", "source_name": "auth_logs", "source_type": "custom"},
    ],
    "Malformed Logs (Truncated JSON)": [
        {"file": "malformed_logs.json", "source_name": "cloudtrail", "source_type": "cloudtrail"},
    ],
}

SAMPLE_LOGS_DIR = ROOT / "data" / "sample_logs"


def _init_session_state() -> None:
    defaults = {
        "pipeline_result": None,
        "status_log_html": None,
        "investigation_running": False,
        "last_run_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _load_scenario_log_sources(scenario_key: str) -> List[LogSource]:
    sources: List[LogSource] = []
    for spec in SCENARIOS[scenario_key]:
        path = SAMPLE_LOGS_DIR / spec["file"]
        content = path.read_text(encoding="utf-8")
        sources.append(
            LogSource(
                source_name=spec["source_name"],
                source_type=spec["source_type"],  # type: ignore[arg-type]
                content=content,
            )
        )
    return sources


def _load_custom_log_sources(
    input_mode: str,
    uploaded_files: Optional[List[Any]],
    pasted_content: str,
    pasted_source_name: str,
) -> List[LogSource]:
    sources: List[LogSource] = []
    if input_mode == "Upload Logs":
        if uploaded_files:
            for file in uploaded_files:
                source_name = Path(file.name).stem
                content = file.read()
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
                else:
                    content = str(content)
                sources.append(
                    LogSource(
                        source_name=source_name,
                        source_type="custom",
                        content=content,
                    )
                )
    elif input_mode == "Paste Logs":
        sources.append(
            LogSource(
                source_name=pasted_source_name,
                source_type="custom",
                content=pasted_content,
            )
        )
    return sources


def _render_band_mode_badge() -> None:
    """Show whether the app is coordinating over live Band or the local simulator."""
    live = is_live_configured()
    if live:
        color, label, detail = COLORS["success"], "LIVE · Band", "Agents coordinating through a Band chat room"
    else:
        color, label, detail = COLORS["warning"], "MOCK · Local bus", "Offline simulator (set Band creds for live mode)"
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:0.5rem;padding:0.5rem 0.75rem;'
        f'border:1px solid {color}55;border-radius:8px;background:{color}14;margin-bottom:0.75rem;">'
        f'<span style="width:9px;height:9px;border-radius:50%;background:{color};'
        f'box-shadow:0 0 8px {color};"></span>'
        f'<div><div style="font-family:monospace;font-weight:600;color:{color};font-size:0.8rem;">'
        f'{label}</div><div style="font-size:0.68rem;color:#8b949e;">{detail}</div></div></div>',
        unsafe_allow_html=True,
    )


def _build_metadata(org_name: str, enable_soc2: bool, enable_hipaa: bool) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "state": "CA",
        "is_us_consumer": True,
        "organization": org_name,
    }
    if enable_soc2:
        metadata["has_soc2"] = True
    if enable_hipaa:
        metadata["hipaa_covered_entity"] = True
    return metadata


async def _run_pipeline_with_live_log(
    orchestrator: PipelineOrchestrator,
    log_sources: List[LogSource],
    metadata: Dict[str, Any],
    timeout_seconds: int,
    monitor: BandStatusMonitor,
    log_placeholder: st.delta_generator.DeltaGenerator,
    alert_placeholder: st.delta_generator.DeltaGenerator,
) -> Dict[str, Any]:
    """Execute the pipeline while refreshing the Band status log."""

    async def refresh_loop() -> None:
        while True:
            render_band_status_log(monitor, placeholder=log_placeholder)
            
            # Display warning/error alert dynamically
            entries = monitor.get_sorted_entries()
            errors = [e for e in entries if e.status == "error"]
            if errors:
                latest_error = errors[-1]
                if "Retrying..." in (latest_error.error or ""):
                    alert_placeholder.warning(f"⚠️ Transient error encountered: {latest_error.error} Retrying in background...")
                else:
                    alert_placeholder.error(f"❌ Pipeline error: {latest_error.error}")
            else:
                alert_placeholder.empty()
                
            await asyncio.sleep(0.25)

    # In live mode, open the Band WebSocket connections concurrently so agents
    # actually receive their @mentions. No-op in mock mode.
    connect_task = None
    if getattr(orchestrator.client, "mode", "mock") == "live":
        connect_task = asyncio.create_task(orchestrator.client.start())

    refresh_task = asyncio.create_task(refresh_loop())
    try:
        result = await orchestrator.run_pipeline(
            log_sources,
            timeout_seconds=timeout_seconds,
            metadata=metadata,
        )
    finally:
        refresh_task.cancel()
        if connect_task is not None:
            connect_task.cancel()
        try:
            await refresh_task
        except asyncio.CancelledError:
            pass
        render_band_status_log(monitor, placeholder=log_placeholder)
    return result


def _run_investigation(
    org_name: str,
    scenario: str,
    enable_soc2: bool,
    enable_hipaa: bool,
    timeout_seconds: int,
    log_placeholder: st.delta_generator.DeltaGenerator,
    alert_placeholder: st.delta_generator.DeltaGenerator,
    input_mode: str,
    uploaded_files: Optional[List[Any]] = None,
    pasted_content: str = "",
    pasted_source_name: str = "pasted_logs",
) -> Dict[str, Any]:
    """Synchronous wrapper that runs the async pipeline on a dedicated event loop."""
    client = BandClient()
    state_manager = PipelineStateManager()
    coordinator = BandCoordinator(client)
    orchestrator = PipelineOrchestrator(client, state_manager, coordinator)

    monitor = BandStatusMonitor(band_client=client)
    monitor.subscribe()
    monitor.add_orchestrator_start()

    if input_mode == "Sample Scenario":
        log_sources = _load_scenario_log_sources(scenario)
    else:
        log_sources = _load_custom_log_sources(
            input_mode, uploaded_files, pasted_content, pasted_source_name
        )
    metadata = _build_metadata(org_name, enable_soc2, enable_hipaa)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            _run_pipeline_with_live_log(
                orchestrator,
                log_sources,
                metadata,
                timeout_seconds,
                monitor,
                log_placeholder,
                alert_placeholder,
            )
        )
    finally:
        loop.close()
        st.session_state["status_log_html"] = render_log_html(monitor.get_sorted_entries())


def main() -> None:
    st.set_page_config(
        page_title="NeXtrace — Security Incident Intelligence",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_theme()
    _init_session_state()

    st.title("NeXtrace")
    st.caption("Multi-agent security incident intelligence · Band-coordinated pipeline")

    with st.sidebar:
        _render_band_mode_badge()
        st.header("Investigation Controls")
        org_name = st.text_input("Organization name", value="Acme Corp")
        scenario = st.selectbox("Scenario", options=list(SCENARIOS.keys()))
        input_mode = st.radio("Log Input Mode", ["Sample Scenario", "Upload Logs", "Paste Logs"])

        uploaded_files = None
        pasted_content = ""
        pasted_source_name = "pasted_logs"

        if input_mode == "Upload Logs":
            uploaded_files = st.file_uploader(
                "Upload Log Files",
                type=["json", "txt"],
                accept_multiple_files=True,
            )
        elif input_mode == "Paste Logs":
            pasted_content = st.text_area(
                "Paste Logs",
                placeholder="Paste raw log content here...",
            )
            pasted_source_name = st.text_input(
                "Source Name",
                value="pasted_logs",
            )

        st.subheader("Compliance Context")
        enable_soc2 = st.toggle("SOC 2 certified organization", value=True)
        enable_hipaa = st.toggle("HIPAA covered entity", value=True)
        timeout_seconds = st.slider("Pipeline timeout (seconds)", min_value=60, max_value=600, value=200, step=10)
        run_clicked = st.button("Run Investigation", type="primary", use_container_width=True)

    st.subheader("Live Band Coordination Log")
    alert_placeholder = st.empty()
    log_placeholder = st.empty()

    if st.session_state.status_log_html and not st.session_state.investigation_running:
        log_placeholder.markdown(st.session_state.status_log_html, unsafe_allow_html=True)

    if run_clicked and not st.session_state.investigation_running:
        has_error = False
        if input_mode == "Upload Logs" and not uploaded_files:
            st.warning("Please provide log input before running.")
            has_error = True
        elif input_mode == "Paste Logs" and not pasted_content.strip():
            st.warning("Please provide log input before running.")
            has_error = True

        if not has_error:
            st.session_state.investigation_running = True
            st.session_state.pipeline_result = None
            st.session_state.status_log_html = None

            with st.spinner("Investigation in progress — agents coordinating over Band…"):
                try:
                    result = _run_investigation(
                        org_name=org_name,
                        scenario=scenario,
                        enable_soc2=enable_soc2,
                        enable_hipaa=enable_hipaa,
                        timeout_seconds=timeout_seconds,
                        log_placeholder=log_placeholder,
                        alert_placeholder=alert_placeholder,
                        input_mode=input_mode,
                        uploaded_files=uploaded_files,
                        pasted_content=pasted_content,
                        pasted_source_name=pasted_source_name,
                    )
                    st.session_state.pipeline_result = result
                    st.session_state.last_run_id = result.get("run_id")
                except Exception as exc:
                    st.session_state.pipeline_result = {
                        "status": "failed",
                        "error": str(exc),
                        "stages": {},
                    }
                    st.error(f"Investigation failed: {exc}")
                finally:
                    st.session_state.investigation_running = False

            st.rerun()

    result: Optional[Dict[str, Any]] = st.session_state.pipeline_result
    if result:
        status = result.get("status", "unknown")
        run_id = result.get("run_id", st.session_state.last_run_id)
        if status == "completed":
            st.success(f"Investigation complete · Run ID `{run_id}`")
        elif status == "timeout":
            st.warning(f"Pipeline timed out · Run ID `{run_id}` — {result.get('error')}")
        elif status == "failed":
            st.error(f"Investigation failed · {result.get('error')}")

        stages = result.get("stages", {})

        # Top-of-report verdict: overall severity + agent confidence.
        summary = render_incident_summary(stages)
        st.divider()

        tab_timeline, tab_attribution, tab_impact, tab_postmortem = st.tabs(
            ["Forensic Timeline", "Attack Attribution", "Impact & Compliance", "Post-Mortem"]
        )
        with tab_timeline:
            render_timeline_view(stages.get("forensic_timeline"))
        with tab_attribution:
            render_attribution_view(stages.get("attack_attribution"))
            attribution_data = stages.get("attack_attribution")
            if attribution_data:
                st.divider()
                render_attack_flow(attribution_data)
                st.divider()
                render_geo_map(stages)
        with tab_impact:
            render_impact_view(stages.get("impact_assessment"))
        with tab_postmortem:
            render_postmortem_view(stages.get("postmortem_complete"))
            if stages.get("postmortem_complete"):
                st.divider()
                render_ticket_export(stages, run_id or "", summary=summary, org_name=org_name)
    elif not st.session_state.investigation_running:
        st.info("Configure settings in the sidebar and click **Run Investigation** to start.")


if __name__ == "__main__":
    main()

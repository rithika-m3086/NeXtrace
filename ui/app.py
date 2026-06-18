"""NeXtrace Streamlit dashboard — live Band coordination and investigation results."""

from __future__ import annotations

import asyncio
import sys
import json
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

# Startup check for API key presence
import os
aiml_key = os.getenv("AIML_API_KEY")
if aiml_key:
    if aiml_key.startswith("your_"):
        aiml_status = "Placeholder (starts with your_)"
    else:
        aiml_status = f"Present (last 4: ...{aiml_key[-4:]})"
else:
    aiml_status = "Absent"
print(f"[STARTUP CHECK] AIML_API_KEY is {aiml_status}")


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
        try:
            content = path.read_text(encoding="utf-8")
        except (IOError, OSError) as e:
            st.error(
                f"Failed to load scenario file "
                f"'{spec['file']}': {e}"
            )
            return []
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
                if file.size > 10 * 1024 * 1024:
                    st.error(
                        f"'{file.name}' exceeds 10MB limit. "
                        f"Please upload a smaller file."
                    )
                    continue
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
        color, label, detail = COLORS["live"], "LIVE · Band", "Agents coordinating through a Band chat room"
        anim = "nx-glow-pulse 1.6s var(--nx-ease-inout) infinite"
    else:
        color, label, detail = COLORS["mock"], "MOCK · Local bus", "Offline simulator (set Band creds for live mode)"
        anim = "nx-glow-pulse-mock 1.6s var(--nx-ease-inout) infinite"
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:0.6rem;padding:0.55rem 0.8rem;'
        f'border:1px solid {color}55;border-radius:var(--nx-radius-lg);background:{color}14;'
        f'margin-bottom:0.85rem;box-shadow:var(--nx-shadow-sm);">'
        f'<span style="width:9px;height:9px;border-radius:50%;background:{color};'
        f'flex-shrink:0;box-shadow:0 0 8px {color};animation:{anim};"></span>'
        f'<div style="line-height:1.3;"><div style="font-family:var(--nx-font-mono);font-weight:600;'
        f'color:{color};font-size:0.8rem;">{label}</div>'
        f'<div style="font-size:0.68rem;color:var(--nx-text-secondary);">{detail}</div></div></div>',
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
    resume_run_id: Optional[str] = None,
    stop_after: Optional[str] = None,
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
            resume_run_id=resume_run_id,
            stop_after=stop_after,
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
    resume_run_id: Optional[str] = None,
    stop_after: Optional[str] = None,
) -> Dict[str, Any]:
    """Synchronous wrapper that runs the async pipeline on a dedicated event loop."""
    client = BandClient()
    state_manager = PipelineStateManager()
    coordinator = BandCoordinator(client)
    orchestrator = PipelineOrchestrator(client, state_manager, coordinator)

    monitor = BandStatusMonitor(band_client=client)
    monitor.subscribe()
    monitor.add_orchestrator_start()

    if resume_run_id:
        log_sources = []
    else:
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
                resume_run_id=resume_run_id,
                stop_after=stop_after,
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

        # Check API Keys and Model Config
        aiml_key = os.getenv("AIML_API_KEY")
        model_name = os.getenv("MODEL_NAME")
        keys_missing = not aiml_key or aiml_key.startswith("your_") or not model_name

        if keys_missing:
            if not aiml_key or aiml_key.startswith("your_"):
                st.error("🛑 AIML_API_KEY not loaded — the app cannot run investigations. Please configure it in your `.env` file.")
            if not model_name:
                st.error("🛑 MODEL_NAME not set — the app cannot run investigations. Please configure it in your `.env` file.")

        # Resume Controls
        state_mgr = PipelineStateManager()
        saved_runs = state_mgr.list_saved_runs()
        resume_run_id = None
        resume_clicked = False
        if saved_runs:
            st.subheader("Resume Investigation")
            options = ["-- Select a run --"] + list(saved_runs.keys())
            def format_run_option(opt):
                if opt == "-- Select a run --":
                    return opt
                stage = saved_runs.get(opt, "none")
                return f"{opt[:8]}... ({stage})"
            selected_resume = st.selectbox(
                "Resume last failed run",
                options=options,
                format_func=format_run_option,
                key="resume_run_id_select"
            )
            if selected_resume != "-- Select a run --":
                resume_run_id = selected_resume
                resume_clicked = st.button("Resume Selected Run", type="primary", use_container_width=True, disabled=keys_missing)
                st.divider()

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

        # Staged review toggle
        skip_review = st.toggle("Skip review / run straight through", value=True)

        run_clicked = st.button("Run Investigation", type="primary", use_container_width=True, disabled=keys_missing)

    st.subheader("Live Band Coordination Log")
    alert_placeholder = st.empty()
    log_placeholder = st.empty()

    if st.session_state.status_log_html and not st.session_state.investigation_running:
        log_placeholder.markdown(st.session_state.status_log_html, unsafe_allow_html=True)

    is_triggered = (run_clicked or resume_clicked) and not st.session_state.investigation_running
    if is_triggered:
        has_error = False
        if not resume_clicked:
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
                    stop_after = "forensic_timeline" if (not skip_review and not resume_clicked) else None
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
                        resume_run_id=resume_run_id if resume_clicked else None,
                        stop_after=stop_after,
                    )
                    st.session_state.pipeline_result = result
                    st.session_state.last_run_id = result.get("run_id")
                except Exception as exc:
                    st.session_state.pipeline_result = {
                        "status": "failed",
                        "error": "Investigation failed. See logs for details.",
                        "stages": {},
                    }
                    import logging
                    logging.getLogger("nextrace").error(
                        f"Investigation failed", exc_info=True
                    )
                    st.error(
                        "Investigation failed. Check the terminal logs "
                        "for details."
                    )
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
        elif status == "paused":
            st.warning(f"Investigation paused for review · Run ID `{run_id}`")
            stages = result.get("stages", {})
            timeline_data = stages.get("forensic_timeline")
            
            if timeline_data:
                st.markdown("### Forensic Timeline Editor")
                st.info("The investigation is paused. Edit the timeline events below, then click **Continue Investigation**.")
                
                events = timeline_data.get("events", [])
                editor_key = f"timeline_editor_data_{run_id}"
                if editor_key not in st.session_state:
                    st.session_state[editor_key] = [
                        {
                            "keep": True,
                            "confirmed_malicious": "confirmed_malicious" in ev.get("flags", []),
                            "timestamp": ev.get("timestamp"),
                            "severity": ev.get("severity"),
                            "event_type": ev.get("event_type"),
                            "action": ev.get("action"),
                            "target_resource": ev.get("target_resource"),
                            "outcome": ev.get("outcome"),
                            "source_ip": ev.get("source_ip"),
                            "source_user": ev.get("source_user"),
                            "event_id": ev.get("event_id"),
                            "raw_log_reference": ev.get("raw_log_reference"),
                            "flags": ev.get("flags", []),
                        }
                        for ev in events
                    ]
                
                edited_rows = st.data_editor(
                    st.session_state[editor_key],
                    key=f"timeline_editor_control_{run_id}",
                    column_config={
                        "keep": st.column_config.CheckboxColumn("Keep?", default=True),
                        "confirmed_malicious": st.column_config.CheckboxColumn("Confirmed Malicious?", default=False),
                        "event_id": st.column_config.TextColumn("Event ID", disabled=True),
                        "raw_log_reference": st.column_config.TextColumn("Raw Log Ref", disabled=True),
                        "flags": st.column_config.ListColumn("Flags", disabled=True),
                    },
                    use_container_width=True,
                    num_rows="dynamic"
                )
                
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    if st.button("Continue Investigation", type="primary", use_container_width=True):
                        try:
                            cleaned_events = []
                            for ev in edited_rows:
                                if not ev.get("keep", True):
                                    continue
                                cleaned_ev = {k: v for k, v in ev.items() if k not in ("keep", "confirmed_malicious")}
                                flags = list(ev.get("flags", []))
                                if ev.get("confirmed_malicious"):
                                    if "confirmed_malicious" not in flags:
                                        flags.append("confirmed_malicious")
                                else:
                                    if "confirmed_malicious" in flags:
                                        flags.remove("confirmed_malicious")
                                cleaned_ev["flags"] = flags
                                cleaned_events.append(cleaned_ev)
                                
                            if not cleaned_events:
                                st.error("Cannot continue with an empty timeline. Please keep at least one event.")
                            else:
                                from schemas.timeline_schema import ForensicTimeline
                                timeline_payload = {
                                    "incident_id": timeline_data.get("incident_id"),
                                    "pipeline_run_id": run_id,
                                    "created_at": timeline_data.get("created_at"),
                                    "confidence_score": timeline_data.get("confidence_score", 1.0),
                                    "raw_event_count": timeline_data.get("raw_event_count", len(cleaned_events)),
                                    "filtered_event_count": len(cleaned_events),
                                    "timeline_start": cleaned_events[0]["timestamp"] if cleaned_events else timeline_data.get("timeline_start"),
                                    "timeline_end": cleaned_events[-1]["timestamp"] if cleaned_events else timeline_data.get("timeline_end"),
                                    "events": cleaned_events,
                                    "affected_systems": list(set(ev["target_resource"] for ev in cleaned_events if ev.get("target_resource"))),
                                    "affected_users": list(set(ev["source_user"] for ev in cleaned_events if ev.get("source_user"))),
                                    "anomalies": timeline_data.get("anomalies", []),
                                    "agent_notes": timeline_data.get("agent_notes", "")
                                }
                                
                                validated = ForensicTimeline.model_validate(timeline_payload)
                                new_payload = validated.model_dump(mode="json")
                                
                                filepath = os.path.join("outputs", f"{run_id}.json")
                                if os.path.exists(filepath):
                                    with open(filepath, "r", encoding="utf-8") as f:
                                        state_json = json.load(f)
                                else:
                                    state_json = {"stages": {}, "status": "in_progress"}
                                
                                state_json["stages"]["forensic_timeline"] = new_payload
                                state_json["status"] = "in_progress"
                                
                                os.makedirs("outputs", exist_ok=True)
                                with open(filepath, "w", encoding="utf-8") as f:
                                    json.dump(state_json, f, indent=2)
                                    
                                if editor_key in st.session_state:
                                    del st.session_state[editor_key]
                                    
                                st.session_state.investigation_running = True
                                st.session_state.pipeline_result = None
                                st.session_state.status_log_html = None
                                
                                with st.spinner("Continuing investigation..."):
                                    res = _run_investigation(
                                        org_name=org_name,
                                        scenario=scenario,
                                        enable_soc2=enable_soc2,
                                        enable_hipaa=enable_hipaa,
                                        timeout_seconds=timeout_seconds,
                                        log_placeholder=log_placeholder,
                                        alert_placeholder=alert_placeholder,
                                        input_mode=input_mode,
                                        resume_run_id=run_id,
                                    )
                                    st.session_state.pipeline_result = res
                                    st.session_state.last_run_id = res.get("run_id")
                                
                                st.session_state.investigation_running = False
                                st.rerun()
                        except Exception as e:
                            st.error(f"Failed to validate timeline edits: {e}")

        stages = result.get("stages", {})

        # Check for failed agent/stage
        failed_agent_name = None
        failed_reason = None
        failed_stage = None
        stage_agents = {
            "forensic_timeline": ("Agent 1 (Forensic)", "forensic_timeline"),
            "attack_attribution": ("Agent 2 (Attribution)", "attack_attribution"),
            "impact_assessment": ("Agent 3 (Impact)", "impact_assessment"),
            "postmortem_complete": ("Agent 4 (Post-Mortem)", "postmortem_complete"),
        }
        for stage_name, (agent_title, _) in stage_agents.items():
            stage_data = stages.get(stage_name)
            if stage_data and isinstance(stage_data, dict) and stage_data.get("status") == "error":
                failed_stage = stage_name
                failed_agent_name = agent_title
                failed_reason = stage_data.get("error_message")
                break

        # Display agent failure banner if found
        if failed_agent_name:
            st.error(f"❌ {failed_agent_name} failed: {failed_reason}. Investigation halted — results below are incomplete.")

        # Top-of-report verdict: overall severity + agent confidence. Only render if Agent 1 at least succeeded
        timeline_data = stages.get("forensic_timeline")
        if timeline_data and isinstance(timeline_data, dict) and timeline_data.get("status") != "error":
            summary = render_incident_summary(stages)
            st.divider()

            tab_timeline, tab_attribution, tab_impact, tab_postmortem = st.tabs(
                ["Forensic Timeline", "Attack Attribution", "Impact & Compliance", "Post-Mortem"]
            )
            with tab_timeline:
                render_timeline_view(timeline_data)
                
            with tab_attribution:
                attribution_data = stages.get("attack_attribution")
                if attribution_data and isinstance(attribution_data, dict) and attribution_data.get("status") != "error":
                    render_attribution_view(attribution_data)
                    st.divider()
                    render_attack_flow(attribution_data)
                    st.divider()
                    render_geo_map(stages)
                else:
                    st.info("No Attack Attribution findings available due to stage/upstream failure.")
                    
            with tab_impact:
                impact_data = stages.get("impact_assessment")
                if impact_data and isinstance(impact_data, dict) and impact_data.get("status") != "error":
                    render_impact_view(impact_data)
                else:
                    st.info("No Impact & Compliance findings available due to stage/upstream failure.")
                    
            with tab_postmortem:
                postmortem_data = stages.get("postmortem_complete")
                if postmortem_data and isinstance(postmortem_data, dict) and postmortem_data.get("status") != "error":
                    render_postmortem_view(postmortem_data)
                    st.divider()
                    render_ticket_export(stages, run_id or "", summary=summary, org_name=org_name)
                else:
                    st.info("No Post-Mortem findings available due to stage/upstream failure.")
        else:
            st.warning("No forensic timeline findings available due to Agent 1 (Forensic) failure.")
    elif not st.session_state.investigation_running:
        st.info("Configure settings in the sidebar and click **Run Investigation** to start.")


if __name__ == "__main__":
    main()

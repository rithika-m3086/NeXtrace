"""Live Band coordination status log — streams agent hand-offs in real time."""

from __future__ import annotations

import html
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

import streamlit as st

from core.client import BandClient
from core.message_types import BandMessage

STAGE_ORDER = {
    "forensic_timeline": 1,
    "attack_attribution": 2,
    "impact_assessment": 3,
    "postmortem_complete": 4,
}

AGENT_LABELS = {
    "agent1_forensic": "Agent 1 · Forensic Timeline",
    "agent2_attribution": "Agent 2 · Attack Attribution",
    "agent3_impact": "Agent 3 · Impact Assessment",
    "agent4_postmortem": "Agent 4 · Post-Mortem Report",
    "orchestrator": "Orchestrator",
}

CHANNEL_LABELS = {
    "forensic_timeline": "forensic_timeline",
    "attack_attribution": "attack_attribution",
    "impact_assessment": "impact_assessment",
    "postmortem_complete": "postmortem_complete",
    "raw_evidence_input": "raw_evidence_input",
}

STATUS_ICONS = {
    "processing": "⏳",
    "completed": "✅",
    "error": "❌",
    "started": "🚀",
}


@dataclass
class StatusLogEntry:
    """Single line in the Band coordination log."""

    entry_id: str
    timestamp: datetime
    agent_id: str
    channel: str
    status: str
    confidence: Optional[float]
    elapsed_seconds: float
    error: Optional[str] = None
    sequence: int = 0


@dataclass
class BandStatusMonitor:
    """Subscribes to pipeline_status / pipeline_errors and accumulates log entries."""

    band_client: BandClient
    run_id: Optional[str] = None
    entries: List[StatusLogEntry] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _start_time: float = field(default_factory=time.time)
    _entry_counter: int = 0
    _subscribed: bool = False

    def bind_run(self, run_id: str) -> None:
        """Scope the monitor to a specific pipeline run."""
        self.run_id = run_id
        self.entries.clear()
        self._start_time = time.time()
        self._entry_counter = 0

    def subscribe(self) -> None:
        """Register Band channel listeners (idempotent)."""
        if self._subscribed:
            return
        self.band_client.subscribe("pipeline_status", self._on_status)
        self.band_client.subscribe("pipeline_errors", self._on_error)
        self._subscribed = True

    def add_orchestrator_start(self) -> None:
        """Seed the log with the pipeline kick-off line."""
        self._append_entry(
            agent_id="orchestrator",
            channel="raw_evidence_input",
            status="started",
            confidence=1.0,
            error=None,
            sequence=0,
        )

    def _on_status(self, message: BandMessage) -> None:
        if self.run_id is None:
            self.run_id = message.pipeline_run_id
        elif message.pipeline_run_id != self.run_id:
            return
        payload = message.payload or {}
        stage = payload.get("stage", message.channel)
        status = payload.get("status", "processing")
        self._append_entry(
            agent_id=message.agent_id,
            channel=stage,
            status=status,
            confidence=message.confidence,
            error=None,
            sequence=message.sequence,
            timestamp=message.timestamp,
        )

    def _on_error(self, message: BandMessage) -> None:
        if self.run_id is None:
            self.run_id = message.pipeline_run_id
        elif message.pipeline_run_id != self.run_id:
            return
        payload = message.payload or {}
        stage = payload.get("stage", message.channel)
        error_text = payload.get("error", "Unknown error")
        self._append_entry(
            agent_id=message.agent_id,
            channel=stage,
            status="error",
            confidence=0.0,
            error=error_text,
            sequence=message.sequence,
            timestamp=message.timestamp,
        )

    def _append_entry(
        self,
        agent_id: str,
        channel: str,
        status: str,
        confidence: Optional[float],
        error: Optional[str],
        sequence: int,
        timestamp: Optional[datetime] = None,
    ) -> None:
        with self._lock:
            self._entry_counter += 1
            entry = StatusLogEntry(
                entry_id=f"{sequence}-{self._entry_counter}",
                timestamp=timestamp or datetime.now(timezone.utc),
                agent_id=agent_id,
                channel=channel,
                status=status,
                confidence=confidence,
                elapsed_seconds=time.time() - self._start_time,
                error=error,
                sequence=sequence,
            )
            self.entries.append(entry)

    def get_sorted_entries(self) -> List[StatusLogEntry]:
        """Return entries ordered by pipeline stage then sequence."""
        with self._lock:
            return sorted(
                self.entries,
                key=lambda e: (
                    STAGE_ORDER.get(e.channel, 99),
                    e.sequence,
                    e.elapsed_seconds,
                ),
            )


def _format_confidence(confidence: Optional[float]) -> str:
    if confidence is None:
        return "—"
    return f"{confidence * 100:.0f}%"


def _format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs}s"


def render_log_html(entries: List[StatusLogEntry], *, show_header: bool = True) -> str:
    """Build HTML for the status log container."""
    lines_html: List[str] = []
    for entry in entries:
        icon = STATUS_ICONS.get(entry.status, "•")
        agent_label = AGENT_LABELS.get(entry.agent_id, entry.agent_id)
        channel_label = CHANNEL_LABELS.get(entry.channel, entry.channel)
        status_class = f"nx-log-status-{entry.status}"
        status_text = entry.status.upper()

        meta_parts = [
            _format_elapsed(entry.elapsed_seconds),
            f"conf {_format_confidence(entry.confidence)}",
            f"seq {entry.sequence}",
        ]
        meta = " · ".join(meta_parts)

        detail = ""
        if entry.error:
            detail = (
                f'<div style="color:#f85149;font-size:0.75rem;margin-top:0.2rem;">'
                f"{html.escape(entry.error)}</div>"
            )

        lines_html.append(
            f'<div class="nx-log-line">'
            f'<span class="nx-log-icon">{icon}</span>'
            f'<div style="flex:1;">'
            f'<span class="nx-log-agent">{html.escape(agent_label)}</span>'
            f' → <span class="nx-log-channel">{html.escape(channel_label)}</span>'
            f' · <span class="{status_class}">{status_text}</span>'
            f"{detail}"
            f"</div>"
            f'<span class="nx-log-meta">{html.escape(meta)}</span>'
            f"</div>"
        )

    header = ""
    if show_header:
        header = (
            '<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;'
            'color:#8b949e;margin-bottom:0.5rem;">Band Coordination Log</div>'
        )

    body = "".join(lines_html) if lines_html else (
        '<div style="color:#6e7681;padding:0.5rem 0;">Awaiting agent activity…</div>'
    )

    return f'{header}<div class="nx-status-log">{body}</div>'


def render_band_status_log(
    monitor: BandStatusMonitor,
    placeholder: Optional[st.delta_generator.DeltaGenerator] = None,
    *,
    expanded: bool = True,
) -> None:
    """Render the live Band status log into a Streamlit container."""
    entries = monitor.get_sorted_entries()
    log_html = render_log_html(entries)

    if placeholder is not None:
        placeholder.markdown(log_html, unsafe_allow_html=True)
    else:
        with st.status("Band Coordination Log", expanded=expanded) as status_box:
            st.markdown(log_html, unsafe_allow_html=True)
            if entries and all(e.status in ("completed", "error") for e in entries if e.status != "started"):
                processing = [e for e in entries if e.status == "processing"]
                if not processing:
                    status_box.update(label="Investigation complete", state="complete")


def create_ui_refresh_loop(
    monitor: BandStatusMonitor,
    placeholder: st.delta_generator.DeltaGenerator,
    stop_event: threading.Event,
    interval: float = 0.3,
) -> Callable[[], None]:
    """Return a callable that refreshes the log until stop_event is set."""

    def refresh_once() -> None:
        render_band_status_log(monitor, placeholder=placeholder)

    def run_loop() -> None:
        while not stop_event.is_set():
            refresh_once()
            time.sleep(interval)
        refresh_once()

    return run_loop

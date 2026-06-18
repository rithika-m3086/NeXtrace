import asyncio
import os
from typing import Any, Dict, Optional
from uuid import uuid4

from core.client import BandClient
from utils.log_filter import filter_log_sources, get_filter_stats
from utils.chunker import chunk_log_sources, get_chunk_stats
from utils.pii_masker import mask_log_sources
from utils.rate_limiter import default_rate_limiter
from core.message_types import BandMessage
from core.coordinator import BandCoordinator
from pipeline.state_manager import PipelineStateManager
from schemas.input_schema import RawEvidenceInput, LogSource

# Import specialized agents
from agents.agent1_forensic import ForensicEvidenceAgent
from agents.agent2_attribution import AttackAttributionAgent
from agents.agent3_impact import ImpactAssessmentAgent
from agents.agent4_postmortem import PostMortemAgent


class PipelineOrchestrator:
    """Manages the full lifecycle of a SecPostMortem execution run."""

    def __init__(
        self,
        band_client: BandClient,
        state_manager: PipelineStateManager,
        coordinator: BandCoordinator,
    ):
        self.client = band_client
        self.state_manager = state_manager
        self.coordinator = coordinator

    async def run_pipeline(
        self,
        raw_logs: Any,
        timeout_seconds: int = 120,
        metadata: Optional[Dict[str, Any]] = None,
        resume_run_id: Optional[str] = None,
        stop_after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Kicks off the multi-agent pipeline and returns the final deliverables.

        Args:
            raw_logs: Unstructured log content input (str) or list of LogSource objects.
            timeout_seconds: Duration to wait before raising TimeoutError.
            metadata: Optional dictionary of organization metadata.
            resume_run_id: Optional ID of a previous run to resume from.
            stop_after: Optional stage name to pause execution after.
        """
        if resume_run_id:
            run_id = resume_run_id
            loaded = self.state_manager.load_from_disk(run_id)
            if loaded:
                cached_stages = self.state_manager.get_full_context(run_id)
                with self.state_manager._lock:
                    if run_id in self.state_manager._states:
                        self.state_manager._states[run_id]["status"] = "in_progress"
                        self.state_manager._states[run_id]["error"] = None
            else:
                cached_stages = {}
        else:
            run_id = str(uuid4())
            cached_stages = {}
        
        # Initialize or Load State
        if not cached_stages:
            # Validate Input Schema
            try:
                if isinstance(raw_logs, list):
                    log_sources = raw_logs
                else:
                    log_sources = [
                        LogSource(
                            source_name="raw_logs_input",
                            source_type="custom",
                            content=str(raw_logs),
                        )
                    ]

                input_data = RawEvidenceInput(
                    pipeline_run_id=run_id,
                    log_sources=log_sources,
                    metadata=metadata or {},
                )
            except Exception as e:
                error_msg = f"Input validation failed: {e}"
                self.state_manager.create_run(run_id)
                self.state_manager.mark_failed(run_id, error_msg)
                self.state_manager.save_to_disk(run_id)
                
                # Publish to pipeline_errors so UI monitor receives it
                err_msg = BandMessage.create(
                    pipeline_run_id=run_id,
                    agent_id="orchestrator",
                    channel="pipeline_errors",
                    sequence=1,
                    status="error",
                    confidence=0.0,
                    payload={"error": error_msg, "stage": "raw_evidence_input"}
                )
                self.client.publish("pipeline_errors", err_msg)
                
                return {
                    "run_id": run_id,
                    "status": "failed",
                    "result": None,
                    "error": error_msg,
                    "stages": self.state_manager.get_full_context(run_id),
                }



        self.coordinator.start_pipeline_run(run_id, timeout_seconds=timeout_seconds)

        # Use an asyncio.Event to trigger synchronization on pipeline completion
        completion_event = asyncio.Event()
        result_container: Dict[str, Any] = {
            "status": "in_progress",
            "data": None,
            "error": None,
        }

        # Setup message interceptors to capture intermediate output states
        def handle_agent_error(msg: BandMessage):
            error_msg = msg.payload.get("error_message", "Unknown agent error")
            self.state_manager.mark_failed(run_id, error_msg)
            self.state_manager.save_to_disk(run_id)
            result_container["status"] = "failed"
            result_container["error"] = f"{msg.agent_id} failed: {error_msg}"
            
            # Publish to pipeline_errors so the UI monitor receives it
            err_msg = BandMessage.create(
                pipeline_run_id=run_id,
                agent_id="orchestrator",
                channel="pipeline_errors",
                sequence=msg.sequence + 1,
                status="error",
                confidence=0.0,
                payload={"error": error_msg, "stage": msg.channel}
            )
            self.client.publish("pipeline_errors", err_msg)
            completion_event.set()

        def on_timeline(msg: BandMessage):
            if msg.pipeline_run_id == run_id:
                self.state_manager.update_stage(run_id, "forensic_timeline", msg.payload)
                self.state_manager.save_to_disk(run_id)
                stats = default_rate_limiter.get_stats()
                self.client.logger.debug(f"Rate limiter stats after agent call: {stats}", extra={"pipeline_run_id": run_id})
                if msg.status == "error":
                    handle_agent_error(msg)
                    return
                if stop_after == "forensic_timeline":
                    result_container["status"] = "paused"
                    completion_event.set()

        def on_attribution(msg: BandMessage):
            if msg.pipeline_run_id == run_id:
                self.state_manager.update_stage(run_id, "attack_attribution", msg.payload)
                self.state_manager.save_to_disk(run_id)
                stats = default_rate_limiter.get_stats()
                self.client.logger.debug(f"Rate limiter stats after agent call: {stats}", extra={"pipeline_run_id": run_id})
                if msg.status == "error":
                    handle_agent_error(msg)
                    return
                if stop_after == "attack_attribution":
                    result_container["status"] = "paused"
                    completion_event.set()

        def on_impact(msg: BandMessage):
            if msg.pipeline_run_id == run_id:
                self.state_manager.update_stage(run_id, "impact_assessment", msg.payload)
                self.state_manager.save_to_disk(run_id)
                stats = default_rate_limiter.get_stats()
                self.client.logger.debug(f"Rate limiter stats after agent call: {stats}", extra={"pipeline_run_id": run_id})
                if msg.status == "error":
                    handle_agent_error(msg)
                    return
                if stop_after == "impact_assessment":
                    result_container["status"] = "paused"
                    completion_event.set()

        def on_postmortem(msg: BandMessage):
            if msg.pipeline_run_id == run_id:
                self.state_manager.update_stage(run_id, "postmortem_complete", msg.payload)
                stats = default_rate_limiter.get_stats()
                self.client.logger.debug(f"Rate limiter stats after agent call: {stats}", extra={"pipeline_run_id": run_id})
                if msg.status == "error":
                    handle_agent_error(msg)
                    return
                self.state_manager.mark_complete(run_id, msg.payload)
                self.state_manager.save_to_disk(run_id)
                result_container["status"] = "completed"
                result_container["data"] = msg.payload
                completion_event.set()

        def on_error(msg: BandMessage):
            if msg.pipeline_run_id == run_id:
                is_transient = msg.payload.get("transient", False)
                error_msg = msg.payload.get("error", "Unknown pipeline error")
                if is_transient:
                    self.client.logger.warning(
                        f"Orchestrator: Observed transient error from {msg.agent_id}: {error_msg}",
                        extra={"pipeline_run_id": run_id}
                    )
                else:
                    self.state_manager.mark_failed(run_id, error_msg)
                    self.state_manager.save_to_disk(run_id)
                    result_container["status"] = "failed"
                    result_container["error"] = error_msg
                    completion_event.set()

        # Register subscriptions
        self.client.subscribe("forensic_timeline", on_timeline)
        self.client.subscribe("attack_attribution", on_attribution)
        self.client.subscribe("impact_assessment", on_impact)
        self.client.subscribe("postmortem_complete", on_postmortem)
        self.client.subscribe("pipeline_errors", on_error)

        # Instantiate agents
        agent1 = ForensicEvidenceAgent(self.client)
        agent2 = AttackAttributionAgent(self.client)
        agent3 = ImpactAssessmentAgent(self.client, self.state_manager)
        agent4 = PostMortemAgent(self.client, self.state_manager)

        STAGES_ORDER = ["raw_evidence_input", "forensic_timeline", "attack_attribution", "impact_assessment", "postmortem_complete"]

        def is_after_stop(stage_name: str) -> bool:
            if not stop_after:
                return False
            try:
                return STAGES_ORDER.index(stage_name) > STAGES_ORDER.index(stop_after)
            except ValueError:
                return False

        # Start listening loops only for non-cached and non-stopped agents
        if "forensic_timeline" not in cached_stages and not is_after_stop("forensic_timeline"):
            agent1.run()
        if "attack_attribution" not in cached_stages and not is_after_stop("attack_attribution"):
            agent2.run()
        if "impact_assessment" not in cached_stages and not is_after_stop("impact_assessment"):
            agent3.run()
        if "postmortem_complete" not in cached_stages and not is_after_stop("postmortem_complete"):
            agent4.run()

        if not cached_stages:
            # Publish initial raw logs message to kick-off pipeline
            payload = input_data.model_dump(mode="json")
            original_sources = payload.get("log_sources", [])
            filtered_sources = filter_log_sources(original_sources, chunk=False)
            stats = get_filter_stats(original_sources, filtered_sources)

            # Privacy-by-design: redact secrets / PII BEFORE any payload leaves the
            # box for the LLM provider. Deterministic tokens preserve correlation.
            pii_disabled = os.getenv("DISABLE_PII_MASKING", "false").lower() == "true"
            redaction_count = 0
            if not pii_disabled:
                filtered_sources, pii_mapping = mask_log_sources(filtered_sources)
                redaction_count = len(pii_mapping)
                self.state_manager.update_stage(
                    run_id,
                    "pii_masking",
                    {"redaction_count": redaction_count, "enabled": True},
                )
                self.client.logger.info(
                    f"PII pre-processor redacted {redaction_count} secret/PII value(s) before LLM dispatch",
                    extra={"pipeline_run_id": run_id},
                )

            # Apply chunking
            chunked_sources = chunk_log_sources(filtered_sources)
            chunk_stats = get_chunk_stats(filtered_sources, chunked_sources)
            payload["log_sources"] = chunked_sources

            # Log filter statistics
            self.client.logger.info(
                f"SIEM pre-filter execution stats: {stats}",
                extra={"pipeline_run_id": run_id}
            )

            # Log chunk statistics
            self.client.logger.info(
                f"Context window protection chunk stats: {chunk_stats}",
                extra={"pipeline_run_id": run_id}
            )

            # Cache the preprocessed raw_evidence_input stage payload
            self.state_manager.create_run(run_id)
            self.state_manager.update_stage(run_id, "raw_evidence_input", payload)
            self.state_manager.save_to_disk(run_id)

            initial_msg = BandMessage.create(
                pipeline_run_id=run_id,
                agent_id="orchestrator",
                channel="raw_evidence_input",
                sequence=1,
                status="success",
                confidence=1.0,
                payload=payload,
            )

            self.client.publish("raw_evidence_input", initial_msg)
        else:
            # Find the last cached stage to re-publish
            last_cached_stage = None
            for stage in reversed(STAGES_ORDER):
                if stage in cached_stages:
                    last_cached_stage = stage
                    break

            if last_cached_stage:
                if last_cached_stage == "raw_evidence_input":
                    seq = 1
                    sender_id = "orchestrator"
                elif last_cached_stage == "forensic_timeline":
                    seq = 2
                    sender_id = "agent1_forensic"
                elif last_cached_stage == "attack_attribution":
                    seq = 3
                    sender_id = "agent2_attribution"
                elif last_cached_stage == "impact_assessment":
                    seq = 4
                    sender_id = "agent3_impact"
                else:
                    seq = 5
                    sender_id = "agent4_postmortem"

                payload = cached_stages[last_cached_stage]
                confidence = 1.0
                if isinstance(payload, dict):
                    confidence = payload.get("confidence_score", 1.0)

                resume_msg = BandMessage.create(
                    pipeline_run_id=run_id,
                    agent_id=sender_id,
                    channel=last_cached_stage,
                    sequence=seq,
                    status="success",
                    confidence=confidence,
                    payload=payload,
                )
                self.client.logger.info(
                    f"Resuming pipeline run {run_id}. Re-publishing stage '{last_cached_stage}' (seq {seq}) to trigger downstream agents."
                )
                self.client.publish(last_cached_stage, resume_msg)

        # Wait for either completion event or timeout
        try:
            await asyncio.wait_for(completion_event.wait(), timeout=float(timeout_seconds))
        except asyncio.TimeoutError:
            self.state_manager.mark_failed(run_id, "Pipeline timed out.")
            self.state_manager.save_to_disk(run_id)
            result_container["status"] = "timeout"
            result_container["error"] = f"Pipeline execution timed out after {timeout_seconds} seconds."

        return {
            "run_id": run_id,
            "status": result_container["status"],
            "result": result_container["data"],
            "error": result_container["error"],
            "stages": self.state_manager.get_full_context(run_id),
        }


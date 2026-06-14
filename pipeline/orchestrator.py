import asyncio
from typing import Any, Dict, Optional
from uuid import uuid4

from core.client import BandClient
from utils.log_filter import filter_log_sources, get_filter_stats
from utils.chunker import chunk_log_sources, get_chunk_stats
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
    ) -> Dict[str, Any]:
        """Kicks off the multi-agent pipeline and returns the final deliverables.

        Args:
            raw_logs: Unstructured log content input (str) or list of LogSource objects.
            timeout_seconds: Duration to wait before raising TimeoutError.
            metadata: Optional dictionary of organization metadata.
        """
        run_id = str(uuid4())
        
        # Validate Input Schema
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

        # Initialize State Contexts
        self.state_manager.create_run(run_id)
        self.state_manager.update_stage(run_id, "raw_evidence_input", input_data.model_dump(mode="json"))
        self.coordinator.start_pipeline_run(run_id, timeout_seconds=timeout_seconds)

        # Use an asyncio.Event to trigger synchronization on pipeline completion
        completion_event = asyncio.Event()
        result_container: Dict[str, Any] = {
            "status": "in_progress",
            "data": None,
            "error": None,
        }

        # Setup message interceptors to capture intermediate output states
        def on_timeline(msg: BandMessage):
            if msg.pipeline_run_id == run_id:
                self.state_manager.update_stage(run_id, "forensic_timeline", msg.payload)
                stats = default_rate_limiter.get_stats()
                self.client.logger.debug(f"Rate limiter stats after agent call: {stats}", extra={"pipeline_run_id": run_id})

        def on_attribution(msg: BandMessage):
            if msg.pipeline_run_id == run_id:
                self.state_manager.update_stage(run_id, "attack_attribution", msg.payload)
                stats = default_rate_limiter.get_stats()
                self.client.logger.debug(f"Rate limiter stats after agent call: {stats}", extra={"pipeline_run_id": run_id})

        def on_impact(msg: BandMessage):
            if msg.pipeline_run_id == run_id:
                self.state_manager.update_stage(run_id, "impact_assessment", msg.payload)
                stats = default_rate_limiter.get_stats()
                self.client.logger.debug(f"Rate limiter stats after agent call: {stats}", extra={"pipeline_run_id": run_id})

        def on_postmortem(msg: BandMessage):
            if msg.pipeline_run_id == run_id:
                self.state_manager.update_stage(run_id, "postmortem_complete", msg.payload)
                self.state_manager.mark_complete(run_id, msg.payload)
                result_container["status"] = "completed"
                result_container["data"] = msg.payload
                stats = default_rate_limiter.get_stats()
                self.client.logger.debug(f"Rate limiter stats after agent call: {stats}", extra={"pipeline_run_id": run_id})
                completion_event.set()

        def on_error(msg: BandMessage):
            if msg.pipeline_run_id == run_id:
                error_msg = msg.payload.get("error", "Unknown pipeline error")
                self.state_manager.mark_failed(run_id, error_msg)
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

        # Start listening loops
        agent1.run()
        agent2.run()
        agent3.run()
        agent4.run()

        # Publish initial raw logs message to kick-off pipeline
        payload = input_data.model_dump(mode="json")
        original_sources = payload.get("log_sources", [])
        filtered_sources = filter_log_sources(original_sources, chunk=False)
        stats = get_filter_stats(original_sources, filtered_sources)

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

        # Wait for either completion event or timeout
        try:
            await asyncio.wait_for(completion_event.wait(), timeout=float(timeout_seconds))
        except asyncio.TimeoutError:
            self.state_manager.mark_failed(run_id, "Pipeline timed out.")
            result_container["status"] = "timeout"
            result_container["error"] = f"Pipeline execution timed out after {timeout_seconds} seconds."

        return {
            "run_id": run_id,
            "status": result_container["status"],
            "result": result_container["data"],
            "error": result_container["error"],
            "stages": self.state_manager.get_full_context(run_id),
        }

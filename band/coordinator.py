import time
from typing import Dict, Any, Optional
from band.channels import BandChannel
from band.message_types import BandMessage
from utils.logger import get_logger


class PipelineTimeoutError(Exception):
    """Exception raised when a pipeline run exceeds the timeout limit."""
    pass


class BandCoordinator:
    """Monitors and manages the sequence of multi-agent handoffs, status tracking, and timeouts."""

    def __init__(self, band_client, logger=None):
        self.client = band_client
        self.logger = logger or get_logger("band_coordinator")
        
        # Track active pipeline states: {run_id: {"start_time": timestamp, "current_stage": stage, "status": status}}
        self.active_runs: Dict[str, Dict[str, Any]] = {}
        
        # Subscribe coordinator to status and error channels
        self.client.subscribe(BandChannel.PIPELINE_STATUS.value, self.handle_status_update)
        self.client.subscribe(BandChannel.PIPELINE_ERRORS.value, self.handle_error)

    def start_pipeline_run(self, run_id: str, timeout_seconds: int = 120):
        """Registers the start of a pipeline execution."""
        self.active_runs[run_id] = {
            "start_time": time.time(),
            "timeout_seconds": timeout_seconds,
            "current_stage": "started",
            "status": "in_progress",
            "stages": {}
        }
        self.logger.info(
            f"Coordinator: Started monitoring pipeline run {run_id}",
            extra={"pipeline_run_id": run_id}
        )

    def handle_status_update(self, message: BandMessage):
        """Processes status updates from individual agents."""
        run_id = message.pipeline_run_id
        if run_id not in self.active_runs:
            # Register run dynamically if it started elsewhere
            self.start_pipeline_run(run_id)
            
        run_state = self.active_runs[run_id]
        agent_id = message.agent_id
        payload = message.payload
        
        stage = payload.get("stage", "unknown")
        status = payload.get("status", "unknown")
        
        run_state["current_stage"] = stage
        run_state["stages"][stage] = {
            "agent_id": agent_id,
            "status": status,
            "timestamp": message.timestamp.isoformat(),
            "confidence": message.confidence
        }
        
        self.logger.info(
            f"Coordinator: Run {run_id} updated: Agent '{agent_id}' reported stage '{stage}' with status '{status}'",
            extra={"pipeline_run_id": run_id}
        )

    def handle_error(self, message: BandMessage):
        """Handles pipeline errors published by any agent."""
        run_id = message.pipeline_run_id
        if run_id in self.active_runs:
            self.active_runs[run_id]["status"] = "failed"
            self.active_runs[run_id]["error_details"] = message.payload
            
        error_msg = message.payload.get("error", "Unknown error")
        self.logger.error(
            f"Coordinator: Pipeline run {run_id} failed. Error reported by agent '{message.agent_id}': {error_msg}",
            extra={"pipeline_run_id": run_id}
        )

    def check_timeouts(self) -> list[str]:
        """Scans active runs and marks any that have timed out as failed.

        Returns a list of run_ids that timed out.
        """
        now = time.time()
        timed_out_runs = []
        
        for run_id, state in list(self.active_runs.items()):
            if state["status"] == "in_progress":
                elapsed = now - state["start_time"]
                if elapsed > state["timeout_seconds"]:
                    state["status"] = "timeout"
                    timed_out_runs.append(run_id)
                    self.logger.error(
                        f"Coordinator: Pipeline run {run_id} timed out after {elapsed:.1f}s",
                        extra={"pipeline_run_id": run_id}
                    )
                    
        return timed_out_runs

    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Returns the status and stage tracking info for a specific run."""
        return self.active_runs.get(run_id)

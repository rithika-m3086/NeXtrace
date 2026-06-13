import threading
from typing import Any, Dict, Optional


class PipelineStateManager:
    """Thread-safe, in-memory state manager for tracking active pipeline runs and accumulated context."""

    def __init__(self):
        self._lock = threading.Lock()
        # Storage format: {run_id: {"status": str, "error": str, "stages": {stage_name: data}, "final_output": dict}}
        self._states: Dict[str, Dict[str, Any]] = {}

    def create_run(self, run_id: str):
        """Initializes state context for a new pipeline execution."""
        with self._lock:
            self._states[run_id] = {
                "status": "in_progress",
                "error": None,
                "stages": {},
                "final_output": None,
            }

    def update_stage(self, run_id: str, stage_name: str, data: Any):
        """Records data returned from a specific stage in the pipeline."""
        with self._lock:
            if run_id in self._states:
                self._states[run_id]["stages"][stage_name] = data

    def get_stage(self, run_id: str, stage_name: str) -> Optional[Any]:
        """Retrieves cached output from a specific stage."""
        with self._lock:
            run_state = self._states.get(run_id)
            if run_state:
                return run_state["stages"].get(stage_name)
            return None

    def get_full_context(self, run_id: str) -> Dict[str, Any]:
        """Returns all completed stages and their respective outputs for a run."""
        with self._lock:
            run_state = self._states.get(run_id)
            if run_state:
                # Returns a shallow copy of stage data
                return run_state["stages"].copy()
            return {}

    def mark_complete(self, run_id: str, final_output: Any):
        """Finalizes the pipeline run with status complete and captures final output."""
        with self._lock:
            if run_id in self._states:
                self._states[run_id]["status"] = "completed"
                self._states[run_id]["final_output"] = final_output

    def mark_failed(self, run_id: str, error: str):
        """Marks the run status as failed and registers error details."""
        with self._lock:
            if run_id in self._states:
                self._states[run_id]["status"] = "failed"
                self._states[run_id]["error"] = error

    def get_status(self, run_id: str) -> Optional[str]:
        """Returns the current execution status of a run (in_progress, completed, failed)."""
        with self._lock:
            run_state = self._states.get(run_id)
            if run_state:
                return run_state["status"]
            return None

    def get_run_details(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Returns all details of a run for debugging/inspection."""
        with self._lock:
            return self._states.get(run_id)

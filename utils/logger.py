import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Custom formatter to output JSON log lines."""

    def __init__(self, component_name: str):
        super().__init__()
        self.component_name = component_name

    def format(self, record: logging.LogRecord) -> str:
        # Get baseline log structure
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "component": self.component_name,
            "message": record.getMessage(),
        }

        # Extract extra information if present
        pipeline_run_id = getattr(record, "pipeline_run_id", None)
        if pipeline_run_id is not None:
            log_entry["pipeline_run_id"] = str(pipeline_run_id)

        # Include details for exceptions
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class PipelineLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter to facilitate adding pipeline_run_id to log messages."""

    def __init__(self, logger: logging.Logger, extra: Dict[str, Any]):
        super().__init__(logger, extra)

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        extra = self.extra.copy()
        # Allow passing override run_id dynamically in extra
        if "extra" in kwargs:
            extra.update(kwargs["extra"])
            del kwargs["extra"]
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(component_name: str, pipeline_run_id: Optional[str] = None) -> logging.LoggerAdapter:
    """Configures and returns a JSON logger wrapped in a PipelineLoggerAdapter.

    Args:
        component_name: The name of the component (e.g. agent1_forensic).
        pipeline_run_id: Optional UUID/string representing the execution run.
    """
    logger = logging.getLogger(component_name)
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if get_logger is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = JSONFormatter(component_name)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

    extra = {}
    if pipeline_run_id:
        extra["pipeline_run_id"] = pipeline_run_id

    return PipelineLoggerAdapter(logger, extra)

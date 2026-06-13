import time
import pytest
from core.client import BandClient, BandClientError
from core.coordinator import BandCoordinator, PipelineTimeoutError
from core.channels import BandChannel
from core.message_types import BandMessage


def test_band_client_mode_detection():
    """Verify BandClient correctly determines mode based on API key."""
    # Placeholder API Key -> Mock mode
    client_mock1 = BandClient(api_key="your_api_key_here")
    assert client_mock1.mode == "mock"

    # None API Key -> Mock mode
    client_mock2 = BandClient(api_key=None)
    assert client_mock2.mode == "mock"

    # Real-looking API Key -> Live mode (or error if not importable, but since we have it, it should detect 'live')
    client_live = BandClient(api_key="real-key-12345", agent_id="agent-abc")
    assert client_live.mode == "live"


def test_mock_pub_sub():
    """Verify MockBandClient routes published messages to subscribers."""
    client = BandClient()
    received_messages = []

    def test_callback(msg: BandMessage):
        received_messages.append(msg)

    client.subscribe(BandChannel.RAW_EVIDENCE_INPUT.value, test_callback)

    msg = BandMessage.create(
        pipeline_run_id="run-1",
        agent_id="test_sender",
        channel=BandChannel.RAW_EVIDENCE_INPUT.value,
        sequence=1,
        status="success",
        confidence=0.95,
        payload={"data": "test payload"}
    )

    success = client.publish(BandChannel.RAW_EVIDENCE_INPUT.value, msg)
    assert success is True
    assert len(received_messages) == 1
    assert received_messages[0].pipeline_run_id == "run-1"
    assert received_messages[0].payload["data"] == "test payload"


def test_coordinator_stage_tracking():
    """Verify BandCoordinator captures and logs stage transitions."""
    client = BandClient()
    coordinator = BandCoordinator(client)

    run_id = "run-coord-test"
    coordinator.start_pipeline_run(run_id, timeout_seconds=10)

    # Publish stage update message
    msg = BandMessage.create(
        pipeline_run_id=run_id,
        agent_id="agent1_forensic",
        channel=BandChannel.PIPELINE_STATUS.value,
        sequence=1,
        status="success",
        confidence=0.9,
        payload={"stage": "forensic_timeline", "status": "completed"}
    )

    client.publish(BandChannel.PIPELINE_STATUS.value, msg)

    status = coordinator.get_run_status(run_id)
    assert status is not None
    assert status["current_stage"] == "forensic_timeline"
    assert status["stages"]["forensic_timeline"]["status"] == "completed"
    assert status["status"] == "in_progress"


def test_coordinator_error_tracking():
    """Verify BandCoordinator catches failures."""
    client = BandClient()
    coordinator = BandCoordinator(client)

    run_id = "run-err-test"
    coordinator.start_pipeline_run(run_id, timeout_seconds=10)

    # Publish error message
    msg = BandMessage.create(
        pipeline_run_id=run_id,
        agent_id="agent2_attribution",
        channel=BandChannel.PIPELINE_ERRORS.value,
        sequence=2,
        status="error",
        confidence=0.0,
        payload={"error": "JSON timeline was malformed", "stage": "attribution"}
    )

    client.publish(BandChannel.PIPELINE_ERRORS.value, msg)

    status = coordinator.get_run_status(run_id)
    assert status is not None
    assert status["status"] == "failed"
    assert status["error_details"]["error"] == "JSON timeline was malformed"


def test_coordinator_timeouts():
    """Verify BandCoordinator flags timed out runs."""
    client = BandClient()
    coordinator = BandCoordinator(client)

    run_id = "run-timeout-test"
    # Register run with 0 second timeout (instant timeout)
    coordinator.start_pipeline_run(run_id, timeout_seconds=-1)

    timed_outs = coordinator.check_timeouts()
    assert run_id in timed_outs

    status = coordinator.get_run_status(run_id)
    assert status["status"] == "timeout"


def test_context_manager():
    """Verify context manager works and cleans up."""
    with BandClient() as client:
        assert client.mode == "mock"

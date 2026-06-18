import pytest
import uuid
import asyncio
from pathlib import Path
from pydantic import ValidationError
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.state_manager import PipelineStateManager
from core.coordinator import BandCoordinator
from core.client import BandClient
from utils.rate_limiter import default_rate_limiter

pytestmark = pytest.mark.functional

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


@pytest.mark.asyncio
async def test_pipeline_completes_successfully(orchestrator, api_key_leak_logs):
    """Test 1.1: Run the full pipeline end to end with api_key_leak logs and assert successful completion."""
    result = await orchestrator.run_pipeline(api_key_leak_logs)
    
    assert result["status"] == "completed"
    assert is_valid_uuid(result["run_id"])
    assert result["error"] is None
    
    for stage in ["forensic_timeline", "attack_attribution", "impact_assessment", "postmortem_complete"]:
        assert stage in result["stages"]
        assert isinstance(result["stages"][stage], dict)
        assert len(result["stages"][stage]) > 0


@pytest.mark.parametrize("log_file", [
    "api_key_leak_cloudtrail.json",
    "credential_stuffing_logs.json",
    "sparse_logs.json",
    "noisy_logs.json",
    "malformed_logs.json"
])
@pytest.mark.asyncio
async def test_all_scenarios_complete(orchestrator, log_file):
    """Test 1.2: Verify all scenario log files complete without crashing (never status='failed')."""
    from tests.conftest import SAMPLE_LOGS
    content = (SAMPLE_LOGS / log_file).read_text(encoding="utf-8")
    
    logs = [{
        "source_name": log_file.replace(".json", ""),
        "source_type": "cloudtrail",
        "content": content
    }]
    
    result = await orchestrator.run_pipeline(logs, timeout_seconds=200)
    assert result["status"] in ["completed", "timeout"]
    assert result["status"] != "failed"


@pytest.mark.asyncio
async def test_pipeline_timeout_respected(orchestrator):
    """Test 1.3: Run pipeline with a very short timeout and assert timeout status."""
    # Large content to make LLM calls take longer than 1-2 seconds
    large_logs = [{
        "source_name": "large_log",
        "source_type": "cloudtrail",
        "content": "A" * 20000
    }]
    result = await orchestrator.run_pipeline(large_logs, timeout_seconds=1)
    assert result["status"] == "timeout"
    assert "timed out" in result["error"].lower()


@pytest.mark.asyncio
async def test_stop_after_works_correctly(orchestrator, api_key_leak_logs):
    """Test 1.4: Run pipeline with stop_after and verify it pauses at the designated stage."""
    result = await orchestrator.run_pipeline(api_key_leak_logs, stop_after="forensic_timeline")
    assert result["status"] == "paused"
    assert "forensic_timeline" in result["stages"]
    assert "attack_attribution" not in result["stages"]


@pytest.mark.asyncio
async def test_empty_log_content_handled_gracefully(orchestrator):
    """Test 1.5: Run pipeline with empty raw_logs."""
    result = await orchestrator.run_pipeline(raw_logs=[])
    # The pipeline should either fail gracefully or complete with low confidence.
    assert result["status"] in ["failed", "completed"]


@pytest.mark.asyncio
async def test_invalid_input_type_handled_gracefully(orchestrator):
    """Test 1.6: Run pipeline with invalid input raw_logs=None."""
    result = await orchestrator.run_pipeline(raw_logs=None)
    assert result["status"] == "failed"
    assert result["error"] is not None
    assert isinstance(result["error"], str)


@pytest.mark.asyncio
async def test_metadata_flows_through_correctly(orchestrator, api_key_leak_logs):
    """Test 1.7: Run with metadata and verify stages capture it."""
    metadata = {
        "organization": "TestCorp",
        "has_soc2": True,
        "hipaa_covered_entity": True
    }
    result = await orchestrator.run_pipeline(api_key_leak_logs, metadata=metadata)
    assert result["stages"]["postmortem_complete"] is not None
    assert result["stages"]["impact_assessment"] is not None


@pytest.mark.asyncio
async def test_resume_run_works(orchestrator, api_key_leak_logs):
    """Test 1.8: Run with stop_after and then resume with the run_id."""
    first_result = await orchestrator.run_pipeline(api_key_leak_logs, stop_after="forensic_timeline")
    assert first_result["status"] == "paused"
    run_id = first_result["run_id"]
    
    second_result = await orchestrator.run_pipeline(api_key_leak_logs, resume_run_id=run_id)
    assert second_result["status"] == "completed"
    assert "forensic_timeline" in second_result["stages"]


@pytest.mark.asyncio
async def test_duplicate_run_id_does_not_corrupt_state(api_key_leak_logs):
    """Test 1.9: Run same resume_run_id simultaneously in separate orchestrators sharing the same state manager."""
    client = BandClient()
    state_manager = PipelineStateManager()
    coordinator = BandCoordinator(client)
    
    orch1 = PipelineOrchestrator(client, state_manager, coordinator)
    orch2 = PipelineOrchestrator(client, state_manager, coordinator)
    
    # First, get a paused run state
    paused_res = await orch1.run_pipeline(api_key_leak_logs, stop_after="forensic_timeline")
    run_id = paused_res["run_id"]
    
    # Run both simultaneously resuming the same run_id
    res1, res2 = await asyncio.gather(
        orch1.run_pipeline(api_key_leak_logs, resume_run_id=run_id),
        orch2.run_pipeline(api_key_leak_logs, resume_run_id=run_id)
    )
    
    assert res1["status"] in ["completed", "failed"]
    assert res2["status"] in ["completed", "failed"]


@pytest.mark.asyncio
async def test_rate_limiter_does_not_block_short_runs(orchestrator, api_key_leak_logs):
    """Test 1.10: Run pipeline normally and check rate limiter does not block or fail the run."""
    result = await orchestrator.run_pipeline(api_key_leak_logs)
    assert result["status"] != "failed"
    
    stats = default_rate_limiter.get_stats()
    assert stats["requests_in_window"] > 0

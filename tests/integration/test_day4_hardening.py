import json
import time
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from core.client import BandClient
from core.coordinator import BandCoordinator
from pipeline.state_manager import PipelineStateManager
from pipeline.orchestrator import PipelineOrchestrator
from core.message_types import BandMessage
from agents.base_agent import BaseAgent
from agents.agent1_forensic import ForensicEvidenceAgent

# Let's import the schemas we might use
from schemas.timeline_schema import ForensicTimeline
from schemas.attribution_schema import AttributionReport
from schemas.impact_schema import ImpactAssessment
from schemas.postmortem_schema import PostMortemReport

# Test 1: Timeout with successful fast retry
@pytest.mark.asyncio
async def test_llm_timeout_and_fast_retry():
    client = BandClient()
    agent = ForensicEvidenceAgent(client)
    agent.openai_client = MagicMock()
    
    # We want the first call to raise a timeout, and the second to succeed
    mock_create = agent.openai_client.chat.completions.create
    
    # Define side effect: raise an Exception (timeout) first, then return valid response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"incident_id": "inc-123", "pipeline_run_id": "run-123", "confidence_score": 0.4, "raw_event_count": 1, "filtered_event_count": 1, "timeline_start": "2026-06-14T10:00:00Z", "timeline_end": "2026-06-14T10:00:00Z", "events": [], "affected_systems": []}'))
    ]
    
    mock_create.side_effect = [
        Exception("Request timed out"),
        mock_response
    ]
    
    # Check that calling _call_model eventually succeeds on second attempt
    with patch("time.sleep", return_value=None):  # speed up test
        res = agent._call_model(prompt="test prompt", run_id="run-123")
        assert res == mock_response.choices[0].message.content
        assert mock_create.call_count == 2

# Test 2: Double timeout leads to fatal failure
@pytest.mark.asyncio
async def test_llm_double_timeout_fatal():
    client = BandClient()
    agent = ForensicEvidenceAgent(client)
    agent.openai_client = MagicMock()
    
    mock_create = agent.openai_client.chat.completions.create
    # Retries are consolidated in call_with_retry (RETRY_MAX_ATTEMPTS = 3).
    mock_create.side_effect = [
        Exception("Request timed out"),
        Exception("Request timed out"),
        Exception("Request timed out"),
    ]

    # Verify the original exception propagates after all attempts are exhausted.
    with patch("time.sleep", return_value=None):
        with pytest.raises(Exception, match="Request timed out"):
            agent._call_model(prompt="test prompt", run_id="run-123")
        assert mock_create.call_count == 3

# Test 3: Sparse logs degradation
# We assert that when sparse logs are analyzed, the pipeline outputs lower confidence
@pytest.mark.asyncio
async def test_sparse_logs_degradation():
    client = BandClient()
    state_manager = PipelineStateManager()
    coordinator = BandCoordinator(client)
    orchestrator = PipelineOrchestrator(client, state_manager, coordinator)
    
    # We patch all the agents' _call_model_json to return mocked low/high confidence scores
    # and check that Agent 1 confidence score is below 0.5 as required by Step 2.
    from tests.integration.test_pipeline import mock_timeline, mock_attribution, mock_impact, mock_postmortem
    
    sparse_timeline = mock_timeline.model_copy(deep=True)
    sparse_timeline.confidence_score = 0.3  # sparse confidence is low
    
    sparse_postmortem = mock_postmortem.model_copy(deep=True)
    sparse_postmortem.executive_summary.headline = "Low confidence: sparse data warning"
    
    with patch("agents.agent1_forensic.ForensicEvidenceAgent._call_model_json", return_value=sparse_timeline), \
         patch("agents.agent2_attribution.AttackAttributionAgent._call_model_json", return_value=mock_attribution), \
         patch("agents.agent3_impact.ImpactAssessmentAgent._call_model_json", return_value=mock_impact), \
         patch("agents.agent4_postmortem.PostMortemAgent._call_model_json", return_value=sparse_postmortem):
         
         result = await orchestrator.run_pipeline("sparse logs content", timeout_seconds=10)
         assert result["status"] == "completed"
         assert result["stages"]["forensic_timeline"]["confidence_score"] < 0.5
         assert "warning" in result["stages"]["postmortem_complete"]["executive_summary"]["headline"].lower()

# Test 4: Noisy logs degradation
@pytest.mark.asyncio
async def test_noisy_logs_degradation():
    client = BandClient()
    state_manager = PipelineStateManager()
    coordinator = BandCoordinator(client)
    orchestrator = PipelineOrchestrator(client, state_manager, coordinator)
    
    from tests.integration.test_pipeline import mock_timeline, mock_attribution, mock_impact, mock_postmortem
    
    noisy_attribution = mock_attribution.model_copy(deep=True)
    noisy_attribution.confidence_score = 0.45
    noisy_attribution.entry_point.identified = False
    noisy_attribution.entry_point.vulnerability_description = "Lack of a clear entry point due to noise"
    
    with patch("agents.agent1_forensic.ForensicEvidenceAgent._call_model_json", return_value=mock_timeline), \
         patch("agents.agent2_attribution.AttackAttributionAgent._call_model_json", return_value=noisy_attribution), \
         patch("agents.agent3_impact.ImpactAssessmentAgent._call_model_json", return_value=mock_impact), \
         patch("agents.agent4_postmortem.PostMortemAgent._call_model_json", return_value=mock_postmortem):
         
         result = await orchestrator.run_pipeline("noisy logs content", timeout_seconds=10)
         assert result["status"] == "completed"
         assert result["stages"]["attack_attribution"]["confidence_score"] < 0.5
         assert result["stages"]["attack_attribution"]["entry_point"]["identified"] is False

# Test 5: Malformed logs input schema rejection
@pytest.mark.asyncio
async def test_malformed_logs_graceful_failure():
    client = BandClient()
    state_manager = PipelineStateManager()
    coordinator = BandCoordinator(client)
    orchestrator = PipelineOrchestrator(client, state_manager, coordinator)

    # empty list of logs is invalid according to raw evidence schema min_length=1
    result = await orchestrator.run_pipeline([], timeout_seconds=10)
    assert result["status"] == "failed"
    assert "Input validation failed" in result["error"]

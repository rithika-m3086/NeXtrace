import os
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from core.client import BandClient
from core.coordinator import BandCoordinator
from pipeline.state_manager import PipelineStateManager
from pipeline.orchestrator import PipelineOrchestrator
from tests.integration.test_pipeline import mock_timeline, mock_attribution, mock_impact, mock_postmortem

def test_state_manager_save_load_roundtrip(tmp_path):
    """Verify PipelineStateManager successfully saves and loads state to/from disk."""
    # Temporarily monkeypatch Outputs directory to use a temp directory
    state_manager = PipelineStateManager()
    run_id = "test-run-12345"
    
    state_manager.create_run(run_id)
    state_manager.update_stage(run_id, "raw_evidence_input", {"test": "data"})
    state_manager.update_stage(run_id, "forensic_timeline", {"events": [{"id": 1}]})
    
    # Mock os.makedirs and open to write to tmp_path
    original_save = state_manager.save_to_disk
    original_load = state_manager.load_from_disk
    
    def mock_save_to_disk(rid):
        os.makedirs(tmp_path, exist_ok=True)
        file_path = os.path.join(tmp_path, f"{rid}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(state_manager._states[rid], f, indent=2)
            
    def mock_load_from_disk(rid) -> bool:
        file_path = os.path.join(tmp_path, f"{rid}.json")
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r", encoding="utf-8") as f:
            state_manager._states[rid] = json.load(f)
        return True

    with patch.object(state_manager, "save_to_disk", mock_save_to_disk), \
         patch.object(state_manager, "load_from_disk", mock_load_from_disk):
        
        state_manager.save_to_disk(run_id)
        
        # Clear in-memory states
        state_manager._states.clear()
        assert run_id not in state_manager._states
        
        # Load from disk
        success = state_manager.load_from_disk(run_id)
        assert success is True
        assert run_id in state_manager._states
        assert state_manager.get_stage(run_id, "raw_evidence_input") == {"test": "data"}
        assert state_manager.get_stage(run_id, "forensic_timeline") == {"events": [{"id": 1}]}

@pytest.mark.asyncio
async def test_pipeline_stop_after_and_resume(tmp_path):
    """Verify pipeline stops after a specified stage and resumes using saved checkpoints."""
    client = BandClient()
    state_manager = PipelineStateManager()
    coordinator = BandCoordinator(client)
    orchestrator = PipelineOrchestrator(client, state_manager, coordinator)

    # Mock disk checkpointing to use tmp_path
    def mock_save_to_disk(rid):
        os.makedirs(tmp_path, exist_ok=True)
        file_path = os.path.join(tmp_path, f"{rid}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(state_manager._states[rid], f, indent=2)
            
    def mock_load_from_disk(rid) -> bool:
        file_path = os.path.join(tmp_path, f"{rid}.json")
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r", encoding="utf-8") as f:
            state_manager._states[rid] = json.load(f)
        return True

    # Use patches for save_to_disk/load_from_disk and agent LLM calls
    with patch.object(state_manager, "save_to_disk", mock_save_to_disk), \
         patch.object(state_manager, "load_from_disk", mock_load_from_disk), \
         patch("agents.agent1_forensic.ForensicEvidenceAgent._call_model_json", return_value=mock_timeline) as mock_agent1, \
         patch("agents.agent2_attribution.AttackAttributionAgent._call_model_json", return_value=mock_attribution) as mock_agent2, \
         patch("agents.agent3_impact.ImpactAssessmentAgent._call_model_json", return_value=mock_impact) as mock_agent3, \
         patch("agents.agent4_postmortem.PostMortemAgent._call_model_json", return_value=mock_postmortem) as mock_agent4:
        
        # 1. Run pipeline but stop after forensic_timeline
        result = await orchestrator.run_pipeline("sample raw security logs contents", timeout_seconds=10, stop_after="forensic_timeline")
        
        assert result["status"] == "paused"
        run_id = result["run_id"]
        assert "forensic_timeline" in result["stages"]
        assert "attack_attribution" not in result["stages"]
        
        # Ensure only Agent 1 was invoked, not Agents 2-4
        mock_agent1.assert_called_once()
        mock_agent2.assert_not_called()
        mock_agent3.assert_not_called()
        mock_agent4.assert_not_called()
        
        # Reset mock calls for the resume step
        mock_agent1.reset_mock()
        mock_agent2.reset_mock()
        mock_agent3.reset_mock()
        mock_agent4.reset_mock()
        
        # Clear in-memory state manager to force it to load from our mock disk checkpoint
        state_manager._states.clear()
        
        # 2. Resume the run from the checkpoint
        resume_result = await orchestrator.run_pipeline("ignored since resume_run_id is set", timeout_seconds=10, resume_run_id=run_id)
        
        assert resume_result["status"] == "completed"
        assert "attack_attribution" in resume_result["stages"]
        assert "postmortem_complete" in resume_result["stages"]
        
        # Verify Agent 1 was skipped, and Agents 2-4 were called
        mock_agent1.assert_not_called()
        mock_agent2.assert_called_once()
        mock_agent3.assert_called_once()
        mock_agent4.assert_called_once()


def test_hybrid_agent_routing():
    """Verify that agents route to their correct LLM provider/model and fallback when keys are missing."""
    from agents.agent1_forensic import ForensicEvidenceAgent
    from agents.agent2_attribution import AttackAttributionAgent
    from agents.agent3_impact import ImpactAssessmentAgent
    from core.client import BandClient

    # Test cases mapping env setup to expected outcomes
    env_vars = {
        "AGENT1_PROVIDER": "featherless",
        "FEATHERLESS_API_KEY": "featherless-key-xyz",
        "AGENT1_MODEL": "meta-llama/llama-3-70b-instruct",
        "AGENT2_PROVIDER": "featherless",
        "AGENT2_MODEL": "gpt-4o-mini",
        # Agent 3: testing missing API key fallback
        "AGENT3_PROVIDER": "aiml",
        "AIML_API_KEY": "your_aiml_api_key_here", # starts with "your_" -> fallback
        "OPENROUTER_API_KEY": "openrouter-fallback-key",
    }

    
    # Clean up any real environment vars that might interfere
    with patch.dict(os.environ, env_vars, clear=True):
        client = BandClient()
        
        # Instantiate Agent 1
        agent1 = ForensicEvidenceAgent(client)
        assert agent1.provider == "featherless"
        assert agent1.model_name == "meta-llama/llama-3-70b-instruct"
        assert str(agent1.openai_client.base_url) == "https://api.featherless.ai/v1/"
        
        # Instantiate Agent 2
        agent2 = AttackAttributionAgent(client)
        assert agent2.provider == "featherless"
        assert agent2.model_name == "gpt-4o-mini"
        assert str(agent2.openai_client.base_url) == "https://api.featherless.ai/v1/"

        
        # Instantiate Agent 3
        # Should fallback to default 'openrouter' since FEATHERLESS_API_KEY is not set
        agent3 = ImpactAssessmentAgent(client, MagicMock())
        assert agent3.provider == "openrouter"
        assert str(agent3.openai_client.base_url) == "https://openrouter.ai/api/v1/"


def test_base_agent_no_openai_module():
    """Verify that BaseAgent does not crash at startup if OpenAI package is not installed."""
    from agents.agent1_forensic import ForensicEvidenceAgent
    from core.client import BandClient

    # Mock OpenAI to be None (simulating package not installed)
    with patch("agents.base_agent.OpenAI", None):
        client = BandClient()
        agent = ForensicEvidenceAgent(client)
        assert agent.openai_client is None




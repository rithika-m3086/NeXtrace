import pytest
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@pytest.fixture(autouse=True)
def mock_band_env(monkeypatch):
    monkeypatch.setenv("BAND_ROOM_ID", "your_band_chat_room_id_here")
    monkeypatch.setenv("BAND_AGENT1_API_KEY", "your_agent1_api_key_here")
    monkeypatch.setenv("BAND_AGENT1_ID", "your_agent1_uuid_here")
    monkeypatch.setenv("BAND_AGENT2_API_KEY", "your_agent2_api_key_here")
    monkeypatch.setenv("BAND_AGENT2_ID", "your_agent2_uuid_here")
    monkeypatch.setenv("BAND_AGENT3_API_KEY", "your_agent3_api_key_here")
    monkeypatch.setenv("BAND_AGENT3_ID", "your_agent3_uuid_here")
    monkeypatch.setenv("BAND_AGENT4_API_KEY", "your_agent4_api_key_here")
    monkeypatch.setenv("BAND_AGENT4_ID", "your_agent4_uuid_here")


ROOT = Path(__file__).parent.parent
SAMPLE_LOGS = ROOT / "data" / "sample_logs"

@pytest.fixture
def api_key_leak_logs():
    sources = []
    for filename in [
        "api_key_leak_cloudtrail.json",
        "api_key_leak_github_audit.json", 
        "api_key_leak_s3_access.json"
    ]:
        content = (SAMPLE_LOGS / filename).read_text()
        sources.append({
            "source_name": filename.replace(".json", ""),
            "source_type": "cloudtrail",
            "content": content
        })
    return sources

@pytest.fixture
def orchestrator():
    from core.client import BandClient
    from core.coordinator import BandCoordinator
    from pipeline.state_manager import PipelineStateManager
    from pipeline.orchestrator import PipelineOrchestrator
    client = BandClient()
    state = PipelineStateManager()
    coord = BandCoordinator(client)
    return PipelineOrchestrator(client, state, coord)

@pytest.fixture
def run_pipeline(orchestrator):
    async def _run(logs, **kwargs):
        return await orchestrator.run_pipeline(logs, **kwargs)
    def run(logs, **kwargs):
        return asyncio.run(_run(logs, **kwargs))
    return run

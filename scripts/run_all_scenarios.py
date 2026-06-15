import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure the root of NeXtrace is in the python path
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

from core.client import BandClient
from core.coordinator import BandCoordinator
from pipeline.state_manager import PipelineStateManager
from pipeline.orchestrator import PipelineOrchestrator
from schemas.input_schema import LogSource

SCENARIOS = {
    "API Key Leak (GitHub + CloudTrail + S3)": [
        {"file": "api_key_leak_github_audit.json", "source_name": "github_audit", "source_type": "github_audit"},
        {"file": "api_key_leak_cloudtrail.json", "source_name": "cloudtrail", "source_type": "cloudtrail"},
        {"file": "api_key_leak_s3_access.json", "source_name": "s3_access", "source_type": "s3_access"},
    ],
    "Sparse Logs (Insufficient Evidence)": [
        {"file": "sparse_logs.json", "source_name": "cloudtrail", "source_type": "cloudtrail"},
    ],
    "Noisy Logs (Buried Attack)": [
        {"file": "noisy_logs.json", "source_name": "cloudtrail", "source_type": "cloudtrail"},
    ],
    "Credential Stuffing (Brute Force)": [
        {"file": "credential_stuffing_logs.json", "source_name": "auth_logs", "source_type": "custom"},
    ],
    "Malformed Logs (Truncated JSON)": [
        {"file": "malformed_logs.json", "source_name": "cloudtrail", "source_type": "cloudtrail"},
    ],
}

def read_log_file(filename: str) -> str:
    path = Path(__file__).parent.parent / "data" / "sample_logs" / filename
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

async def run_scenario(name, specs):
    print(f"\n==========================================")
    print(f"RUNNING SCENARIO: {name}")
    print(f"==========================================")
    
    # Reload env and initialize pipeline classes fresh for each run
    load_dotenv()
    client = BandClient()
    state_manager = PipelineStateManager()
    coordinator = BandCoordinator(client)
    orchestrator = PipelineOrchestrator(client, state_manager, coordinator)
    
    log_sources = []
    for spec in specs:
        content = read_log_file(spec["file"])
        log_sources.append(LogSource(
            source_name=spec["source_name"],
            source_type=spec["source_type"],
            content=content
        ))
        
    metadata = {
        "state": "CA",
        "is_us_consumer": True,
        "has_soc2": True
    }
    
    try:
        result = await orchestrator.run_pipeline(log_sources, timeout_seconds=200, metadata=metadata)
        print(f"Status: {result['status']}")
        print(f"Completed Stages: {list(result.get('stages', {}).keys())}")
        if result['status'] == "failed":
            print(f"Error: {result['error']}")
        return result
    except Exception as e:
        print(f"Exception raised: {e}")
        return {"status": "failed", "error": str(e)}

async def main():
    results = {}
    for name, specs in SCENARIOS.items():
        results[name] = await run_scenario(name, specs)
        
    print("\n\n==========================================")
    print("FINAL SUMMARY REPORT")
    print("==========================================")
    for name, res in results.items():
        status = res.get("status")
        stages = list(res.get("stages", {}).keys())
        err = res.get("error", "None")
        print(f"- {name}: {status.upper()} | Stages: {stages} | Error: {err}")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Ensure the root of NeXtrace is in the python path
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

from core.client import BandClient
from core.coordinator import BandCoordinator
from pipeline.state_manager import PipelineStateManager
from pipeline.orchestrator import PipelineOrchestrator
from schemas.input_schema import LogSource, RawEvidenceInput

def read_log_file(filename: str) -> str:
    path = Path(__file__).parent.parent / "data" / "sample_logs" / filename
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

async def main():
    # Load environment variables
    load_dotenv()

    # 1. Initialize Band client in MOCK mode (if BAND_API_KEY is placeholder)
    client = BandClient()
    state_manager = PipelineStateManager()
    coordinator = BandCoordinator(client)
    orchestrator = PipelineOrchestrator(client, state_manager, coordinator)

    print("=== loading log fixtures ===")
    github_content = read_log_file("api_key_leak_github_audit.json")
    cloudtrail_content = read_log_file("api_key_leak_cloudtrail.json")
    s3_content = read_log_file("api_key_leak_s3_access.json")

    # 2. Build LogSource models
    log_sources = [
        LogSource(
            source_name="github_audit",
            source_type="github_audit",
            content=github_content,
        ),
        LogSource(
            source_name="cloudtrail",
            source_type="cloudtrail",
            content=cloudtrail_content,
        ),
        LogSource(
            source_name="s3_access",
            source_type="s3_access",
            content=s3_content,
        ),
    ]

    # Include metadata to trigger regulatory compliance rule evaluation (GDPR, CCPA, HIPAA, SOC2)
    # We set state='CA' to trigger CCPA and has_soc2=True to trigger SOC2.
    # The log sources have medical records ('health' data category) and personal identities ('pii' data category).
    print("=== kicking off NeXtrace multi-agent pipeline ===")
    
    metadata = {
        "state": "CA",
        "is_us_consumer": True,
        "has_soc2": True
    }
    
    # Run the pipeline with metadata
    result = await orchestrator.run_pipeline(log_sources, timeout_seconds=200, metadata=metadata)

    print("\n=== pipeline run completed ===")
    print(f"Run ID: {result['run_id']}")
    print(f"Status: {result['status']}")
    print(f"Error: {result['error']}")
    
    stages = result.get("stages", {})
    
    if "forensic_timeline" in stages:
        print("\n=== Agent 1: Forensic Timeline ===")
        ft = stages["forensic_timeline"]
        print(f"Confidence: {ft.get('confidence_score')}")
        print(f"Total Parsed Events: {len(ft.get('events', []))}")
        print(f"Affected Systems: {ft.get('affected_systems')}")
        print(f"Affected Users: {ft.get('affected_users')}")
        for event in ft.get("events", [])[:5]:
            print(f"  [{event.get('timestamp')}] {event.get('event_type').upper()} -> Action: {event.get('action')} on {event.get('target_resource')} (IP: {event.get('source_ip')})")
            
    if "attack_attribution" in stages:
        print("\n=== Agent 2: Attack Attribution ===")
        att = stages["attack_attribution"]
        print(f"Confidence: {att.get('confidence_score')}")
        print(f"Attack Type: {att.get('attack_classification', {}).get('attack_type')}")
        print(f"Entry Point Resource: {att.get('entry_point', {}).get('resource')}")
        print(f"Entry Point Method: {att.get('entry_point', {}).get('method')}")
        print("MITRE ATT&CK Steps:")
        for step in att.get("attack_chain", []):
            print(f"  - Step {step.get('step')}: {step.get('mitre_technique_id')} ({step.get('mitre_technique_name')}) -> {step.get('description')}")
            
    if "impact_assessment" in stages:
        print("\n=== Agent 3: Impact Assessment & Compliance ===")
        imp = stages["impact_assessment"]
        print(f"Confidence: {imp.get('confidence_score')}")
        print(f"Records Exposed: {imp.get('blast_radius', {}).get('estimated_records_exposed')}")
        print(f"Data Categories: {imp.get('blast_radius', {}).get('data_categories_exposed')}")
        print("Regulatory Compliance Flags:")
        for flag in imp.get("compliance_flags", []):
            print(f"  - [{flag.get('regulation')}] Triggered: {flag.get('triggered')} | Reason: {flag.get('reason')}")
            
    if "postmortem_complete" in stages:
        print("\n=== Agent 4: Post-Mortem & Remediation Report ===")
        pm = stages["postmortem_complete"]
        print(f"Confidence: {pm.get('confidence_score')}")
        print(f"Headline: {pm.get('executive_summary', {}).get('headline')}")
        print(f"What Happened:\n{pm.get('executive_summary', {}).get('what_happened')}")
        print("\nRemediation Plan:")
        for item in pm.get("remediation_plan", []):
            print(f"  - [{item.get('priority').upper()}] {item.get('title')} (Owner: {item.get('owner')})")
            print(f"    Desc: {item.get('description')}")

if __name__ == "__main__":
    asyncio.run(main())

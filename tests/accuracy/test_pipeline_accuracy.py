import pytest
from schemas.timeline_schema import ForensicTimeline
from schemas.attribution_schema import AttributionReport
from schemas.impact_schema import ImpactAssessment
from schemas.postmortem_schema import PostMortemReport

pytestmark = pytest.mark.accuracy

async def _get_pipeline_outputs(orchestrator, logs, metadata=None):
    """Helper to run the orchestrator and parse all stage outputs into Pydantic models."""
    result = await orchestrator.run_pipeline(logs, metadata=metadata)
    assert result["status"] == "completed", f"Pipeline failed: {result.get('error')}"
    
    stages = result["stages"]
    ft = ForensicTimeline.model_validate(stages["forensic_timeline"])
    att = AttributionReport.model_validate(stages["attack_attribution"])
    imp = ImpactAssessment.model_validate(stages["impact_assessment"])
    pm = PostMortemReport.model_validate(stages["postmortem_complete"])
    return ft, att, imp, pm


@pytest.mark.asyncio
async def test_api_key_leak_forensic_timeline(orchestrator, api_key_leak_logs):
    """Test 2.1: Verify Agent 1 forensic timeline accuracy on api_key_leak logs."""
    ft, _, _, _ = await _get_pipeline_outputs(orchestrator, api_key_leak_logs)
    
    assert ft.confidence_score >= 0.5
    assert len(ft.events) >= 3
    assert any(e.event_type in ["authentication", "access"] for e in ft.events)
    assert any(e.severity in ["high", "critical"] for e in ft.events)
    assert len(ft.affected_systems) > 0
    assert len(ft.anomalies) >= 1


@pytest.mark.asyncio
async def test_api_key_leak_attribution(orchestrator, api_key_leak_logs):
    """Test 2.2: Verify Agent 2 attribution accuracy on api_key_leak logs."""
    _, att, _, _ = await _get_pipeline_outputs(orchestrator, api_key_leak_logs)
    
    assert att.confidence_score >= 0.4
    assert att.entry_point.identified is True
    assert len(att.attack_chain) >= 1
    assert att.attack_chain[0].mitre_technique_id is not None
    assert att.attack_chain[0].mitre_technique_id != ""
    assert att.attack_classification.attack_type != "unknown"
    assert len(att.indicators_of_compromise) >= 1


@pytest.mark.asyncio
async def test_api_key_leak_impact_assessment(orchestrator, api_key_leak_logs):
    """Test 2.3: Verify Agent 3 impact assessment accuracy on api_key_leak logs."""
    _, _, imp, _ = await _get_pipeline_outputs(orchestrator, api_key_leak_logs)
    
    assert imp.confidence_score >= 0.4
    assert imp.blast_radius.systems_compromised_count >= 1
    assert imp.business_impact.severity in ["medium", "high", "critical"]
    assert len(imp.compliance_flags) >= 1
    assert any(f.triggered is True for f in imp.compliance_flags)
    assert len(imp.root_cause_factors) >= 1


@pytest.mark.asyncio
async def test_api_key_leak_postmortem(orchestrator, api_key_leak_logs):
    """Test 2.4: Verify Agent 4 post-mortem report accuracy on api_key_leak logs."""
    _, _, _, pm = await _get_pipeline_outputs(orchestrator, api_key_leak_logs)
    
    assert pm.confidence_score >= 0.4
    assert pm.executive_summary.headline != ""
    assert pm.executive_summary.what_happened != ""
    assert len(pm.remediation_plan) >= 3
    assert any(item.priority == "immediate" for item in pm.remediation_plan)
    assert pm.technical_report.root_cause != ""
    assert len(pm.lessons_learned) >= 1
    assert pm.confidence_breakdown.agent1_forensic > 0
    assert pm.confidence_breakdown.overall > 0


@pytest.mark.asyncio
async def test_credential_stuffing_attack_type(orchestrator):
    """Test 2.5: Verify correct credential stuffing attack type classification."""
    from tests.conftest import SAMPLE_LOGS
    content = (SAMPLE_LOGS / "credential_stuffing_logs.json").read_text(encoding="utf-8")
    
    logs = [{
        "source_name": "credential_stuffing",
        "source_type": "custom",
        "content": content
    }]
    
    _, att, _, _ = await _get_pipeline_outputs(orchestrator, logs)
    
    # Accept unknown only if confidence score is low
    if att.confidence_score < 0.4:
        assert att.attack_classification.attack_type in ["brute_force", "credential_theft", "unknown"]
    else:
        assert att.attack_classification.attack_type in ["brute_force", "credential_theft"]
        
    assert att.entry_point.method != ""


@pytest.mark.asyncio
async def test_sparse_logs_low_confidence(orchestrator):
    """Test 2.6: Verify sparse logs produce a low confidence score and do not crash."""
    from tests.conftest import SAMPLE_LOGS
    content = (SAMPLE_LOGS / "sparse_logs.json").read_text(encoding="utf-8")
    
    logs = [{
        "source_name": "sparse",
        "source_type": "cloudtrail",
        "content": content
    }]
    
    result = await orchestrator.run_pipeline(logs)
    assert result["status"] == "completed"
    
    ft = ForensicTimeline.model_validate(result["stages"]["forensic_timeline"])
    assert ft.confidence_score <= 0.6


@pytest.mark.asyncio
async def test_noisy_logs_signal_extracted(orchestrator):
    """Test 2.7: Verify signal is successfully extracted from noisy logs."""
    from tests.conftest import SAMPLE_LOGS
    content = (SAMPLE_LOGS / "noisy_logs.json").read_text(encoding="utf-8")
    
    logs = [{
        "source_name": "noisy",
        "source_type": "cloudtrail",
        "content": content
    }]
    
    result = await orchestrator.run_pipeline(logs)
    assert result["status"] == "completed"
    
    ft = ForensicTimeline.model_validate(result["stages"]["forensic_timeline"])
    assert len(ft.events) >= 1
    assert ft.confidence_score >= 0.3


@pytest.mark.asyncio
async def test_blameless_language(orchestrator, api_key_leak_logs):
    """Test 2.8: Verify post-mortem report uses blameless language."""
    _, _, _, pm = await _get_pipeline_outputs(orchestrator, api_key_leak_logs)
    
    what_happened = pm.executive_summary.what_happened.lower()
    blame_words = ["fault", "mistake", "negligent", "negligence", "careless", "incompetent", "blamed", "at fault"]
    for word in blame_words:
        assert word not in what_happened, f"Blame word '{word}' found in executive summary!"


@pytest.mark.asyncio
async def test_compliance_flags_fire_correctly(orchestrator, api_key_leak_logs):
    """Test 2.9: Verify GDPR/HIPAA/SOC2 flags fire correctly under appropriate metadata."""
    metadata = {
        "organization": "HealthTech",
        "has_soc2": True,
        "hipaa_covered_entity": True,
        "is_us_consumer": True,
        "state": "CA"
    }
    _, _, imp, _ = await _get_pipeline_outputs(orchestrator, api_key_leak_logs, metadata=metadata)
    
    triggered_regs = [f.regulation for f in imp.compliance_flags if f.triggered]
    assert any(reg in ["GDPR", "HIPAA", "SOC2"] for reg in triggered_regs)


@pytest.mark.asyncio
async def test_remediation_is_scenario_specific(orchestrator, api_key_leak_logs):
    """Test 2.10: Verify remediation items contain scenario-specific context instead of boilerplate."""
    _, _, _, pm = await _get_pipeline_outputs(orchestrator, api_key_leak_logs)
    
    combined_plan_text = " ".join(
        f"{item.title} {item.description}" for item in pm.remediation_plan
    ).lower()
    
    expected_context_words = ["key", "rotate", "credential", "secret", "access", "github", "aws", "s3", "iam"]
    assert any(word in combined_plan_text for word in expected_context_words)

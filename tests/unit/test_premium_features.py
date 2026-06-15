"""Unit tests for the premium feature modules (PII masking, severity
aggregation, Mermaid attack path, GeoIP extraction, ticketing/markdown)."""

from __future__ import annotations

from utils.pii_masker import PIIMasker, mask_log_sources
from utils.severity import aggregate_summary, severity_color
from utils.mermaid import build_attack_flow
from utils.geoip import extract_source_ips, _is_public
from utils.ticketing import remediation_to_markdown


# ── PII masking ──────────────────────────────────────────────────────────────
def test_masks_email_and_aws_key_deterministically():
    masker = PIIMasker()
    text = "user admin@acme.com used AKIA1234567890ABCDEF then admin@acme.com again"
    result = masker.mask_text(text)
    assert "admin@acme.com" not in result.text
    assert "AKIA1234567890ABCDEF" not in result.text
    # Same email → same token (referential integrity).
    tokens = [t for t in result.text.split() if t.startswith("<REDACTED_EMAIL")]
    assert len(set(tokens)) == 1
    assert result.redaction_count >= 2


def test_credit_card_luhn_filtering():
    masker = PIIMasker()
    # Valid Visa test number (passes Luhn) vs a non-Luhn 16-digit string.
    valid = "4111111111111111"
    invalid = "1234567812345678"
    out = masker.mask_text(f"{valid} and {invalid}")
    assert valid not in out.text
    assert invalid in out.text  # not masked — fails Luhn


def test_ip_preserved_by_default_but_maskable():
    keep = PIIMasker().mask_text("login from 203.0.113.5")
    assert "203.0.113.5" in keep.text
    masked = PIIMasker(mask_ip=True).mask_text("login from 203.0.113.5")
    assert "203.0.113.5" not in masked.text


def test_mask_log_sources_wrapper():
    sources = [{"source_name": "s1", "source_type": "custom", "content": "token sk-abcdefghijklmnopqrstuvwx"}]
    masked, mapping = mask_log_sources(sources)
    assert "sk-abcdefghijklmnopqrstuvwx" not in masked[0]["content"]
    assert len(mapping) == 1


# ── Severity aggregation ─────────────────────────────────────────────────────
def test_aggregate_prefers_postmortem_severity():
    stages = {
        "postmortem_complete": {
            "overall_severity": "critical",
            "confidence_breakdown": {
                "agent1_forensic": 0.9, "agent2_attribution": 0.8,
                "agent3_impact": 0.85, "agent4_postmortem": 0.95, "overall": 0.88,
            },
        },
        "impact_assessment": {"business_impact": {"severity": "high"},
                              "blast_radius": {"estimated_records_exposed": 5000},
                              "compliance_flags": [{"regulation": "GDPR", "triggered": True}]},
    }
    summary = aggregate_summary(stages)
    assert summary["severity"] == "critical"
    assert summary["overall_confidence"] == 0.88
    assert summary["records_exposed"] == 5000
    assert summary["compliance_count"] == 1


def test_aggregate_degrades_to_timeline():
    stages = {"forensic_timeline": {"events": [
        {"severity": "low"}, {"severity": "high"}, {"severity": "medium"}]}}
    summary = aggregate_summary(stages)
    assert summary["severity"] == "high"


def test_severity_color_known_and_unknown():
    assert severity_color("critical").startswith("#")
    assert severity_color("nonsense").startswith("#")


# ── Mermaid attack path ──────────────────────────────────────────────────────
def test_build_attack_flow():
    attribution = {
        "entry_point": {"identified": True, "resource": "leaked-key"},
        "attack_chain": [
            {"step": 1, "description": "Use creds", "mitre_technique_id": "T1078",
             "mitre_technique_name": "Valid Accounts", "mitre_tactic": "Initial Access"},
            {"step": 2, "description": "Exfil bucket", "mitre_technique_id": "T1530",
             "mitre_technique_name": "Cloud Storage", "mitre_tactic": "Exfiltration"},
        ],
    }
    diagram = build_attack_flow(attribution)
    assert diagram.startswith("flowchart LR")
    assert "T1078" in diagram and "T1530" in diagram
    assert "S1 --> S2" in diagram


def test_build_attack_flow_empty():
    assert build_attack_flow({}) is None
    assert build_attack_flow({"attack_chain": []}) is None


# ── GeoIP extraction (no network) ────────────────────────────────────────────
def test_extract_source_ips():
    stages = {
        "forensic_timeline": {"events": [{"source_ip": "203.0.113.5"}, {"source_ip": None}]},
        "attack_attribution": {"indicators_of_compromise": [
            {"ioc_type": "ip_address", "value": "198.51.100.9"},
            {"ioc_type": "api_key", "value": "x"}]},
    }
    ips = extract_source_ips(stages)
    assert ips == ["203.0.113.5", "198.51.100.9"]


def test_is_public_filters_private():
    assert _is_public("8.8.8.8")
    assert not _is_public("10.0.0.1")
    assert not _is_public("127.0.0.1")
    assert not _is_public("not-an-ip")


# ── Ticketing markdown fallback ──────────────────────────────────────────────
def test_remediation_to_markdown():
    plan = [{"priority": "immediate", "title": "Rotate key", "category": "access_control",
             "owner": "secops", "estimated_effort": "1h", "description": "Rotate the leaked key",
             "verification_method": "Key no longer valid"}]
    md = remediation_to_markdown(plan, "incident-123")
    assert "# Remediation Plan — incident-123" in md
    assert "Rotate key" in md
    assert "- [ ] Key no longer valid" in md


def test_remediation_to_json_and_csv():
    from utils.ticketing import remediation_to_json, remediation_to_csv
    import json
    import csv

    plan = [{
        "action_id": "REM-001",
        "priority": "immediate",
        "category": "access_control",
        "title": "Rotate key",
        "description": "Rotate the leaked key",
        "owner": "secops",
        "estimated_effort": "1h",
        "verification_method": "Key no longer valid"
    }]
    
    # Test JSON Exporter
    js = remediation_to_json(plan, "incident-123")
    data = json.loads(js)
    assert data["incident_ref"] == "incident-123"
    assert data["remediation_plan"][0]["title"] == "Rotate key"
    assert data["remediation_plan"][0]["action_id"] == "REM-001"

    # Test CSV Exporter
    csv_str = remediation_to_csv(plan, "incident-123")
    reader = csv.DictReader(csv_str.splitlines())
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["action_id"] == "REM-001"
    assert rows[0]["priority"] == "immediate"
    assert rows[0]["category"] == "access_control"
    assert rows[0]["title"] == "Rotate key"
    assert rows[0]["description"] == "Rotate the leaked key"
    assert rows[0]["owner"] == "secops"
    assert rows[0]["estimated_effort"] == "1h"
    assert rows[0]["verification_method"] == "Key no longer valid"


import pytest
import os
import tempfile
import pdfplumber
from pathlib import Path
from utils.pdf_exporter import generate_pdf_report

pytestmark = pytest.mark.functional

@pytest.fixture(scope="module")
def valid_postmortem_data():
    """Run pipeline once to generate a valid postmortem_complete stage dict for PDF tests.

    Loads the sample logs directly (rather than via the function-scoped
    ``api_key_leak_logs`` fixture) so this module-scoped fixture has no scope
    mismatch and runs the pipeline only once for the whole module.
    """
    from core.client import BandClient
    from core.coordinator import BandCoordinator
    from pipeline.state_manager import PipelineStateManager
    from pipeline.orchestrator import PipelineOrchestrator
    from tests.conftest import SAMPLE_LOGS
    import asyncio

    logs = []
    for filename in [
        "api_key_leak_cloudtrail.json",
        "api_key_leak_github_audit.json",
        "api_key_leak_s3_access.json",
    ]:
        logs.append({
            "source_name": filename.replace(".json", ""),
            "source_type": "cloudtrail",
            "content": (SAMPLE_LOGS / filename).read_text(encoding="utf-8"),
        })

    client = BandClient()
    state = PipelineStateManager()
    coord = BandCoordinator(client)
    orch = PipelineOrchestrator(client, state, coord)

    result = asyncio.run(orch.run_pipeline(logs))
    assert result["status"] == "completed", f"Setup failed: {result.get('error')}"
    return result["stages"]["postmortem_complete"]


def test_pdf_generates_without_error(valid_postmortem_data):
    """Test 4.1: Verify PDF report generation succeeds and creates a non-empty file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = str(Path(tmp_dir) / "report.pdf")
        path = generate_pdf_report(valid_postmortem_data, output_path)
        
        assert os.path.exists(path)
        assert path == output_path
        assert os.path.getsize(path) > 1000  # Non-empty PDF check


def test_pdf_contains_expected_content(valid_postmortem_data):
    """Test 4.2: Verify the generated PDF contains key textual markers."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = str(Path(tmp_dir) / "report.pdf")
        path = generate_pdf_report(valid_postmortem_data, output_path)
        
        # Extract text from all pages
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
                
        assert "NeXtrace" in text
        assert "Executive Summary" in text
        assert "Remediation" in text


def test_pdf_raises_on_empty_data():
    """Test 4.3: Verify ValueError is raised when postmortem data is empty or None."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = str(Path(tmp_dir) / "report.pdf")
        
        with pytest.raises(ValueError):
            generate_pdf_report(None, output_path)
            
        with pytest.raises(ValueError):
            generate_pdf_report({}, output_path)


def test_pdf_raises_on_invalid_path(valid_postmortem_data):
    """Test 4.4: Verify IOError is raised when the output directory path does not exist."""
    invalid_path = "/nonexistent/path/report.pdf"
    
    with pytest.raises(IOError):
        generate_pdf_report(valid_postmortem_data, invalid_path)

from typing import Any
from ui.app import _load_custom_log_sources
from schemas.input_schema import LogSource


class MockUploadedFile:
    def __init__(self, name: str, content: bytes):
        self.name = name
        self.content = content

    def read(self) -> bytes:
        return self.content


def test_load_custom_log_sources_upload():
    uploaded_files = [
        MockUploadedFile("log1.json", b'{"key": "value"}'),
        MockUploadedFile("log2.txt", b"plain text logs"),
    ]
    sources = _load_custom_log_sources(
        input_mode="Upload Logs",
        uploaded_files=uploaded_files,
        pasted_content="",
        pasted_source_name="pasted_logs"
    )
    assert len(sources) == 2
    assert sources[0].source_name == "log1"
    assert sources[0].source_type == "custom"
    assert sources[0].content == '{"key": "value"}'
    assert sources[1].source_name == "log2"
    assert sources[1].source_type == "custom"
    assert sources[1].content == "plain text logs"


def test_load_custom_log_sources_paste():
    sources = _load_custom_log_sources(
        input_mode="Paste Logs",
        uploaded_files=None,
        pasted_content="pasted text here",
        pasted_source_name="my_custom_source"
    )
    assert len(sources) == 1
    assert sources[0].source_name == "my_custom_source"
    assert sources[0].source_type == "custom"
    assert sources[0].content == "pasted text here"

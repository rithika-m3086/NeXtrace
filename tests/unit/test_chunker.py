import json
from utils.chunker import chunk_log_sources, get_chunk_stats, MAX_CHARS_PER_SOURCE


def test_chunk_log_sources_plain_text():
    large_source = {
        "source_name": "large_text",
        "content": "A" * (MAX_CHARS_PER_SOURCE - 100) + "\n" + "B" * 200,
    }

    chunked = chunk_log_sources([large_source])
    assert len(chunked) >= 2
    assert chunked[0]["source_name"] == "large_text_chunk_1"
    assert chunked[1]["source_name"] == "large_text_chunk_2"
    assert len(chunked[0]["content"]) <= MAX_CHARS_PER_SOURCE


def test_chunk_log_sources_json_array():
    large_list = [{"id": i, "data": "A" * 100} for i in range(200)]
    large_source = {
        "source_name": "large_json",
        "content": json.dumps(large_list),
    }

    chunked = chunk_log_sources([large_source])
    assert len(chunked) >= 2
    for chunk in chunked:
        assert chunk["source_name"].startswith("large_json_chunk_")
        assert len(chunk["content"]) <= MAX_CHARS_PER_SOURCE
        parsed = json.loads(chunk["content"])
        assert isinstance(parsed, list)
        assert len(parsed) > 0


def test_chunk_log_sources_json_dict_with_array():
    large_dict = {
        "Records": [{"id": i, "data": "B" * 200} for i in range(100)]
    }
    large_source = {
        "source_name": "large_dict",
        "content": json.dumps(large_dict),
    }

    chunked = chunk_log_sources([large_source])
    assert len(chunked) >= 2
    for chunk in chunked:
        assert chunk["source_name"].startswith("large_dict_chunk_")
        assert len(chunk["content"]) <= MAX_CHARS_PER_SOURCE
        parsed = json.loads(chunk["content"])
        assert isinstance(parsed, dict)
        assert isinstance(parsed["Records"], list)
        assert len(parsed["Records"]) > 0


def test_chunk_log_sources_non_array_json():
    large_dict = {"data": "A" * (MAX_CHARS_PER_SOURCE + 50)}
    large_source = {
        "source_name": "large_non_array",
        "content": json.dumps(large_dict),
    }
    chunked = chunk_log_sources([large_source])
    assert len(chunked) == 1
    assert "[TRUNCATED - original size:" in chunked[0]["content"]


def test_get_chunk_stats():
    original = [
        {"source_name": "s1", "content": "A" * 5000},
        {"source_name": "s2", "content": "B\n" * (MAX_CHARS_PER_SOURCE // 2 + 1000)},
    ]
    chunked = chunk_log_sources(original)
    stats = get_chunk_stats(original, chunked)
    assert stats["original_source_count"] == 2
    assert stats["chunked_source_count"] >= 3
    assert stats["sources_that_were_split"] == ["s2"]
    assert stats["largest_source_chars"] == len(original[1]["content"])

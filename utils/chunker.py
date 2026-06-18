import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("nextrace")

MAX_CHARS_PER_SOURCE = 12000


def find_array_field(data: Any) -> Optional[str]:
    """Finds the key of a list field within a JSON dictionary, looking for standard names."""
    if not isinstance(data, dict):
        return None
    for field in ["events", "Records", "items", "logs"]:
        if field in data and isinstance(data[field], list):
            return field
    for key, val in data.items():
        if isinstance(val, list):
            return key
    return None


def chunk_json_array(
    entries: List[Any],
    array_key: Optional[str] = None,
    original_dict: Optional[dict] = None,
) -> List[str]:
    """Groups JSON entries into chunks such that each serialized chunk is within MAX_CHARS_PER_SOURCE."""
    chunks: List[str] = []
    current_chunk_entries = []

    def serialize_chunk(entries_to_serialize: List[Any]) -> str:
        if original_dict is not None and array_key is not None:
            chunk_dict = dict(original_dict)
            chunk_dict[array_key] = entries_to_serialize
            return json.dumps(chunk_dict, indent=2)
        else:
            return json.dumps(entries_to_serialize, indent=2)

    for entry in entries:
        entry_str = serialize_chunk([entry])
        if len(entry_str) > MAX_CHARS_PER_SOURCE:
            # If a single entry itself exceeds the limit, emit current chunk, then emit this large entry
            if current_chunk_entries:
                chunks.append(serialize_chunk(current_chunk_entries))
                current_chunk_entries = []
            chunks.append(entry_str)
            continue

        test_entries = current_chunk_entries + [entry]
        test_str = serialize_chunk(test_entries)
        if len(test_str) <= MAX_CHARS_PER_SOURCE:
            current_chunk_entries = test_entries
        else:
            if current_chunk_entries:
                chunks.append(serialize_chunk(current_chunk_entries))
            current_chunk_entries = [entry]

    if current_chunk_entries:
        chunks.append(serialize_chunk(current_chunk_entries))

    return chunks


def chunk_plain_text(content: str) -> List[str]:
    """Groups plain text lines into chunks within MAX_CHARS_PER_SOURCE."""
    lines = content.splitlines(keepends=True)
    chunks: List[str] = []
    current_chunk_lines = []
    current_len = 0

    for line in lines:
        if len(line) > MAX_CHARS_PER_SOURCE:
            if current_chunk_lines:
                chunks.append("".join(current_chunk_lines))
                current_chunk_lines = []
                current_len = 0
            chunks.append(line[:MAX_CHARS_PER_SOURCE])
            continue

        if current_len + len(line) <= MAX_CHARS_PER_SOURCE:
            current_chunk_lines.append(line)
            current_len += len(line)
        else:
            if current_chunk_lines:
                chunks.append("".join(current_chunk_lines))
            current_chunk_lines = [line]
            current_len = len(line)

    if current_chunk_lines:
        chunks.append("".join(current_chunk_lines))

    return chunks


def chunk_log_sources(log_sources: List[Dict]) -> List[Dict]:
    """Splits large log sources into chunks of MAX_CHARS_PER_SOURCE."""
    chunked_sources = []
    for source in log_sources:
        content = source.get("content", "")
        if len(content) <= MAX_CHARS_PER_SOURCE:
            chunked_sources.append(source)
            continue

        is_json = False
        parsed_json = None
        try:
            parsed_json = json.loads(content)
            is_json = True
        except Exception:
            pass

        if is_json:
            if isinstance(parsed_json, list):
                chunks = chunk_json_array(parsed_json)
            else:
                array_key = find_array_field(parsed_json)
                if array_key:
                    chunks = chunk_json_array(
                        parsed_json[array_key],
                        array_key=array_key,
                        original_dict=parsed_json,
                    )
                else:
                    # Truncate and add a note
                    truncated_content = (
                        content[:MAX_CHARS_PER_SOURCE]
                        + f"\n[TRUNCATED - original size: {len(content)} chars]"
                    )
                    new_source = dict(source)
                    new_source["content"] = truncated_content
                    chunked_sources.append(new_source)
                    continue
        else:
            chunks = chunk_plain_text(content)

        MAX_ALLOWED_CHUNKS = 15
        if len(chunks) > MAX_ALLOWED_CHUNKS:
            logger.warning(
                f"Log source truncated from {len(chunks)} to "
                f"{MAX_ALLOWED_CHUNKS} chunks to protect API credits."
            )
            chunks = chunks[:MAX_ALLOWED_CHUNKS]

        for i, chunk_content in enumerate(chunks, 1):
            new_source = dict(source)
            new_source["source_name"] = f"{source.get('source_name', 'unknown')}_chunk_{i}"
            new_source["content"] = chunk_content
            chunked_sources.append(new_source)

    return chunked_sources


def get_chunk_stats(original_sources: List[Dict], chunked_sources: List[Dict]) -> Dict:
    """Computes statistics about the chunking operation."""
    sources_that_were_split = []
    largest_source_chars = 0

    for src in original_sources:
        content_len = len(src.get("content", ""))
        if content_len > largest_source_chars:
            largest_source_chars = content_len
        if content_len > MAX_CHARS_PER_SOURCE:
            sources_that_were_split.append(src.get("source_name", ""))

    return {
        "original_source_count": len(original_sources),
        "chunked_source_count": len(chunked_sources),
        "sources_that_were_split": sources_that_were_split,
        "largest_source_chars": largest_source_chars,
    }

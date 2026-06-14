import json
from typing import Any, Dict, List, Optional


def has_data_modification(entry: dict) -> bool:
    """Detect if an entry indicates a data modification operation."""
    keys_to_check = [
        "operation",
        "method",
        "request_method",
        "request_uri",
        "requestUri",
        "eventName",
        "action",
    ]
    write_indicators = [
        "delete",
        "put",
        "post",
        "create",
        "modify",
        "update",
        "write",
        "patch",
        "upload",
    ]
    for k in keys_to_check:
        val = entry.get(k)
        if isinstance(val, str):
            val_lower = val.lower()
            if any(ind in val_lower for ind in write_indicators):
                return True
    if entry.get("readOnly") is False:
        return True
    return False


def matches_noise_pattern(entry: dict) -> bool:
    """Check if the log entry matches any of the defined noise patterns."""
    # 1. Event type contains: healthcheck, heartbeat, ping, describe, list, get
    keys_to_check = [
        "eventType",
        "event_type",
        "eventName",
        "event_name",
        "action",
        "operation",
    ]
    noise_types = ["healthcheck", "heartbeat", "ping", "describe", "list", "get"]
    for k in keys_to_check:
        val = entry.get(k)
        if isinstance(val, str):
            val_lower = val.lower()
            if any(noise in val_lower for noise in noise_types):
                return True

    # 2. HTTP status codes 200 with no data modification
    status_keys = ["http_status", "status", "statusCode", "status_code", "httpStatus"]
    is_status_200 = False
    for sk in status_keys:
        status_val = entry.get(sk)
        if status_val == 200 or status_val == "200":
            is_status_200 = True
            break
    if is_status_200 and not has_data_modification(entry):
        return True

    # 3. User agent contains: aws-sdk-go/health, ELB-HealthChecker, kube-probe, GoogleHC
    ua_keys = ["user_agent", "userAgent", "User-Agent"]
    ua_noise = ["aws-sdk-go/health", "elb-healthchecker", "kube-probe", "googlehc"]
    for uak in ua_keys:
        ua_val = entry.get(uak)
        if isinstance(ua_val, str):
            ua_val_lower = ua_val.lower()
            if any(n in ua_val_lower for n in ua_noise):
                return True

    # 4. Source IP is a known internal health check range: 127.0.0.1, 169.254.169.254
    ip_keys = [
        "sourceIPAddress",
        "remote_ip",
        "client_ip",
        "source_ip",
        "ip",
        "ip_address",
        "ipAddress",
    ]
    ip_noise = {"127.0.0.1", "169.254.169.254"}
    for ipk in ip_keys:
        ip_val = entry.get(ipk)
        if isinstance(ip_val, str):
            if ip_val.strip() in ip_noise:
                return True

    return False


def contains_security_signal(entry: dict) -> bool:
    """Check if the log entry contains any of the security signals."""
    # 1. Check severity/level
    severity_keys = ["severity", "level", "log_level", "priority"]
    severity_values = {"high", "critical"}
    for sk in severity_keys:
        sv = entry.get(sk)
        if isinstance(sv, str):
            if sv.lower() in severity_values:
                return True

    # 2. Check string values recursively
    signals = [
        "fail",
        "error",
        "deny",
        "denied",
        "deni",
        "reject",
        "unauthorized",
        "forbidden",
        "delete",
        "put",
        "post",
        "create",
        "modify",
        "update",
        "login",
        "auth",
        "credential",
        "token",
        "key",
        "secret",
        "export",
        "download",
        "exfil",
        "copy",
        "transfer",
    ]

    def check_value(val) -> bool:
        if isinstance(val, str):
            val_lower = val.lower()
            if any(sig in val_lower for sig in signals):
                return True
        elif isinstance(val, dict):
            for v in val.values():
                if check_value(v):
                    return True
        elif isinstance(val, list):
            for item in val:
                if check_value(item):
                    return True
        return False

    return check_value(entry)


def filter_entries_list(entries: List[dict]) -> List[dict]:
    """Filter list of entries: keep if security signal present, discard if noise matches."""
    filtered = []
    for entry in entries:
        if contains_security_signal(entry):
            filtered.append(entry)
        elif matches_noise_pattern(entry):
            continue
        else:
            filtered.append(entry)
    return filtered


def filter_log_sources(log_sources: List[Dict], chunk: bool = True) -> List[Dict]:
    """Pre-filters raw log sources content, stripping out noise entries."""
    cleaned_sources = []
    for source in log_sources:
        content_str = source.get("content", "")
        # Try parsing content as JSON
        is_json = False
        parsed_json = None
        try:
            parsed_json = json.loads(content_str)
            is_json = True
        except Exception:
            pass

        if not is_json:
            # Keep full content as-is (don't try to filter plain text)
            cleaned_sources.append(source)
            continue

        # Valid JSON
        if isinstance(parsed_json, list):
            filtered_entries = filter_entries_list(parsed_json)
            new_content = json.dumps(filtered_entries, indent=2)
        elif (
            isinstance(parsed_json, dict)
            and "Records" in parsed_json
            and isinstance(parsed_json["Records"], list)
        ):
            filtered_entries = filter_entries_list(parsed_json["Records"])
            # Create a shallow copy of parsed_json to modify it
            updated_json = dict(parsed_json)
            updated_json["Records"] = filtered_entries
            new_content = json.dumps(updated_json, indent=2)
        elif isinstance(parsed_json, dict):
            filtered_entries = filter_entries_list([parsed_json])
            if filtered_entries:
                new_content = json.dumps(filtered_entries[0], indent=2)
            else:
                new_content = "{}"
        else:
            # Non-standard JSON format (number, string etc.), keep as-is
            cleaned_sources.append(source)
            continue

        new_source = dict(source)
        new_source["content"] = new_content
        cleaned_sources.append(new_source)

    if chunk:
        from utils.chunker import chunk_log_sources
        return chunk_log_sources(cleaned_sources)
    return cleaned_sources


def count_events(content_str: str) -> int:
    """Utility to count events in JSON content or lines in plain text."""
    try:
        parsed = json.loads(content_str)
        if isinstance(parsed, list):
            return len(parsed)
        elif (
            isinstance(parsed, dict)
            and "Records" in parsed
            and isinstance(parsed["Records"], list)
        ):
            return len(parsed["Records"])
        elif isinstance(parsed, dict):
            return 1
    except Exception:
        pass
    lines = [line for line in content_str.splitlines() if line.strip()]
    return len(lines) if lines else 1


def get_filter_stats(original_sources: List[Dict], filtered_sources: List[Dict]) -> Dict:
    """Generates statistics mapping log size reduction."""
    total_original = 0
    total_filtered = 0
    per_source_stats = []

    for orig in original_sources:
        name = orig.get("source_name", "unknown")
        orig_count = count_events(orig.get("content", ""))
        total_original += orig_count

        filt_count = orig_count
        for filt in filtered_sources:
            if filt.get("source_name") == name:
                filt_count = count_events(filt.get("content", ""))
                break
        total_filtered += filt_count
        per_source_stats.append(
            {"source_name": name, "original": orig_count, "filtered": filt_count}
        )

    if total_original > 0:
        reduction_percentage = ((total_original - total_filtered) / total_original) * 100.0
    else:
        reduction_percentage = 0.0

    return {
        "total_original_events": total_original,
        "total_filtered_events": total_filtered,
        "reduction_percentage": round(reduction_percentage, 2),
        "per_source": per_source_stats,
    }

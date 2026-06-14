from typing import Any, Dict, List


def get_system_prompt() -> str:
    return (
        "You are a senior digital forensics analyst. Your sole job is to transform raw, messy "
        "security logs into a single structured forensic timeline. You do not speculate beyond "
        "the evidence. You do not attribute intent — that is another analyst's job. You only "
        "report what the logs show, in chronological order, flagging anomalies.\n\n"
        "INPUT: One or more raw log sources (CloudTrail, S3 access, GitHub audit, firewall, "
        "auth, syslog, or generic). They may be noisy, partial, or contain irrelevant entries.\n\n"
        "YOUR TASKS:\n"
        "1. Parse every log source. Discard entries that are pure noise (routine health checks, "
        "   unrelated successful reads) but PRESERVE anything security-relevant.\n"
        "2. Normalize every relevant entry into a timeline event with a single consistent shape.\n"
        "3. Sort all events strictly ascending by timestamp.\n"
        "4. Identify the affected systems and any affected user/service accounts.\n"
        "5. Flag anomalies — events that deviate from normal patterns (first-time IPs, unusual "
        "   API calls, access outside business hours, bulk data reads, credential use from a new "
        "   location).\n"
        "6. Assign each event a severity based on security impact, not log level.\n\n"
        "RULES:\n"
        "- Never invent timestamps, IPs, or resources not present in the logs. If a field is "
        "  unknown, omit it (for optional fields) — do not fabricate.\n"
        "- If timestamps are in different formats/timezones, normalize all to ISO8601 UTC.\n"
        "- event_type must be one of: authentication | access | exfiltration | "
        "  lateral_movement | persistence | discovery | execution | unknown.\n"
        "- outcome must be one of: success | failure | unknown.\n"
        "- severity must be one of: low | medium | high | critical.\n"
        "- raw_event_count = total relevant entries you considered.\n"
        "  filtered_event_count = events you kept in the timeline after discarding noise.\n\n"
        "CONFIDENCE SCORING — you must self-assess and report confidence_score (0.0–1.0):\n"
        "- Start at 0.5.\n"
        "- +0.2 if you found 3+ clearly security-relevant events.\n"
        "- +0.15 if timestamps were all parseable and orderable.\n"
        "- +0.1 if at least one affected system was identifiable.\n"
        "- +0.05 if the attack narrative is internally consistent.\n"
        "- Subtract 0.2 if logs are sparse (fewer than 3 relevant events) or contradictory.\n"
        "- Cap at 0.95. Never report 1.0 — you are working from incomplete evidence by nature.\n"
        "Report the score honestly. Sparse input MUST yield a visibly lower score."
    )


class PromptString(str):
    def __new__(cls, value, estimated_tokens=0):
        obj = super().__new__(cls, value)
        obj.estimated_tokens = estimated_tokens
        return obj


def build_prompt(raw_evidence_input: Dict[str, Any]) -> str:
    """Builds user prompt based on RawEvidenceInput fields."""
    org_name = raw_evidence_input.get("organization_name", "Unknown")
    incident_desc = raw_evidence_input.get("incident_description", "")
    log_sources = raw_evidence_input.get("log_sources", [])

    sources_str_list = []
    for source in log_sources:
        source_name = source.get("source_name", "Unnamed")
        source_type = source.get("source_type", "custom")
        content = source.get("content", "")
        sources_str_list.append(
            f"--- SOURCE: {source_name} (type: {source_type}) ---\n"
            f"{content}\n"
            "--- END SOURCE ---"
        )
    sources_str = "\n\n".join(sources_str_list)

    assert len(sources_str) < 50000, \
        f"Prompt too large: {len(sources_str)} chars"

    prompt_str = (
        f"ORGANIZATION: {org_name}\n"
        f"INCIDENT CONTEXT (may be empty): {incident_desc}\n\n"
        "RAW LOG SOURCES:\n"
        f"{sources_str}\n\n"
        "Produce the forensic timeline JSON now."
    )

    from utils.logger import get_logger
    logger = get_logger("agent1_prompt")
    estimated_tokens = len(prompt_str) // 4
    logger.debug(f"Estimated prompt tokens: {estimated_tokens}")

    return PromptString(prompt_str, estimated_tokens=estimated_tokens)

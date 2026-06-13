from enum import Enum


class BandChannel(str, Enum):
    """Named communication channels for the multi-agent pipeline."""

    # Publisher: Orchestrator | Subscriber: Agent 1 (Forensic)
    RAW_EVIDENCE_INPUT = "raw_evidence_input"

    # Publisher: Agent 1 (Forensic) | Subscriber: Agent 2 (Attribution)
    FORENSIC_TIMELINE = "forensic_timeline"

    # Publisher: Agent 2 (Attribution) | Subscriber: Agent 3 (Impact)
    ATTACK_ATTRIBUTION = "attack_attribution"

    # Publisher: Agent 3 (Impact) | Subscriber: Agent 4 (Post-Mortem)
    IMPACT_ASSESSMENT = "impact_assessment"

    # Publisher: Agent 4 (Post-Mortem) | Subscriber: Orchestrator
    POSTMORTEM_COMPLETE = "postmortem_complete"

    # Publisher: All components | Subscriber: UI Component (monitoring)
    PIPELINE_STATUS = "pipeline_status"

    # Publisher: All components | Subscriber: Orchestrator (error-handling)
    PIPELINE_ERRORS = "pipeline_errors"

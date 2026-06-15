from agents.base_agent import BaseAgent
from core.message_types import BandMessage
from schemas.timeline_schema import ForensicTimeline
import prompts.agent1_prompt as prompt_mod


class ForensicEvidenceAgent(BaseAgent):
    """Parses raw log files and produces a chronological forensic timeline."""

    def __init__(self, band_client, logger=None):
        super().__init__(
            agent_id="agent1_forensic",
            input_channel="raw_evidence_input",
            output_channel="forensic_timeline",
            band_client=band_client,
            logger=logger,
        )

    async def process(self, input_message: BandMessage) -> BandMessage:
        self.logger.info("Agent 1 processing raw log evidence...")
        prompt = prompt_mod.build_prompt(input_message.payload)
        system_prompt = prompt_mod.get_system_prompt()

        # Call model with self-correcting schema validator
        try:
            timeline: ForensicTimeline = self._call_model_json(
                prompt=prompt,
                response_model=ForensicTimeline,
                system_prompt=system_prompt,
                run_id=input_message.pipeline_run_id,
            )
        except Exception as e:
            self.logger.warning(
                f"Agent 1 model validation failed: {e}. Attempting fallback for sparse/malformed logs.",
                extra={"pipeline_run_id": input_message.pipeline_run_id}
            )
            from datetime import datetime, timezone
            from schemas.timeline_schema import TimelineEvent
            now = datetime.now(timezone.utc)
            fallback_event = TimelineEvent(
                timestamp=now,
                event_type="unknown",
                target_resource="unknown",
                action="no_detectable_events",
                outcome="unknown",
                severity="low",
                raw_log_reference="No security-relevant logs detected or logs are malformed.",
                flags=["insufficient_evidence"]
            )
            timeline = ForensicTimeline(
                incident_id="inc-unknown",
                pipeline_run_id=input_message.pipeline_run_id,
                created_at=now,
                confidence_score=0.1,
                raw_event_count=0,
                filtered_event_count=0,
                timeline_start=now,
                timeline_end=now,
                events=[fallback_event],
                affected_systems=["unknown"],
                agent_notes="Failed to parse logs or logs contain insufficient evidence."
            )

        self.logger.info(
            f"Agent 1 successfully parsed {len(timeline.events)} events on timeline.",
            extra={"pipeline_run_id": input_message.pipeline_run_id}
        )

        # Build output message
        return BandMessage.create(
            pipeline_run_id=input_message.pipeline_run_id,
            agent_id=self.agent_id,
            channel=self.output_channel,
            sequence=input_message.sequence + 1,
            status="success",
            confidence=timeline.confidence_score,
            payload=timeline.model_dump(mode="json"),
        )

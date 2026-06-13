import json
from agents.base_agent import BaseAgent
from core.message_types import BandMessage
from schemas.attribution_schema import AttributionReport
import prompts.agent2_prompt as prompt_mod


class AttackAttributionAgent(BaseAgent):
    """Analyzes a forensic timeline to identify the entry point and MITRE ATT&CK techniques."""

    def __init__(self, band_client, logger=None):
        super().__init__(
            agent_id="agent2_attribution",
            input_channel="forensic_timeline",
            output_channel="attack_attribution",
            band_client=band_client,
            logger=logger,
        )

    async def process(self, input_message: BandMessage) -> BandMessage:
        self.logger.info("Agent 2 processing forensic timeline...")
        # Payload of input message contains the ForensicTimeline JSON
        timeline_data = json.dumps(input_message.payload)

        prompt = prompt_mod.build_prompt(timeline_data, input_message.confidence)
        system_prompt = prompt_mod.get_system_prompt()

        # Call model with self-correcting schema validator
        report: AttributionReport = self._call_model_json(
            prompt=prompt,
            response_model=AttributionReport,
            system_prompt=system_prompt,
        )

        self.logger.info(
            f"Agent 2 successfully mapped {len(report.attack_chain)} attack chain steps.",
            extra={"pipeline_run_id": input_message.pipeline_run_id}
        )

        # Build output message
        return BandMessage.create(
            pipeline_run_id=input_message.pipeline_run_id,
            agent_id=self.agent_id,
            channel=self.output_channel,
            sequence=input_message.sequence + 1,
            status="success",
            confidence=report.confidence_score,
            payload=report.model_dump(mode="json"),
        )

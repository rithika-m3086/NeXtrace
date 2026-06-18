import json
from agents.base_agent import BaseAgent
from agents.fallbacks import attribution_fallback
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

        # Propagate upstream error if any
        if input_message.status == "error":
            err_msg = input_message.payload.get("error_message", "Unknown upstream error")
            self.logger.error(f"Agent 2 received upstream error: {err_msg}")
            return BandMessage.create(
                pipeline_run_id=input_message.pipeline_run_id,
                agent_id=self.agent_id,
                channel=self.output_channel,
                sequence=input_message.sequence + 1,
                status="error",
                confidence=0.0,
                payload={
                    "status": "error",
                    "error_message": f"Upstream error: {err_msg}"
                }
            )

        # Payload of input message contains the ForensicTimeline JSON
        timeline_data = json.dumps(input_message.payload)
        prompt = prompt_mod.build_prompt(timeline_data, input_message.confidence)
        system_prompt = prompt_mod.get_system_prompt()

        try:
            report: AttributionReport = self._call_model_json(
                prompt=prompt,
                response_model=AttributionReport,
                system_prompt=system_prompt,
                run_id=input_message.pipeline_run_id,
            )
            self.logger.info(
                f"Agent 2 successfully mapped {len(report.attack_chain)} attack chain steps.",
                extra={"pipeline_run_id": input_message.pipeline_run_id}
            )
            return BandMessage.create(
                pipeline_run_id=input_message.pipeline_run_id,
                agent_id=self.agent_id,
                channel=self.output_channel,
                sequence=input_message.sequence + 1,
                status="success",
                confidence=report.confidence_score,
                payload=report.model_dump(mode="json"),
            )
        except Exception as e:
            import traceback
            error_details = f"{type(e).__name__}: {e}"
            self.logger.error(
                f"Agent 2 (AttackAttributionAgent) failed: {error_details} — emitting degraded fallback attribution.\n{traceback.format_exc()}",
                extra={"pipeline_run_id": input_message.pipeline_run_id}
            )
            # Graceful degradation: emit a low-confidence valid attribution.
            return BandMessage.create(
                pipeline_run_id=input_message.pipeline_run_id,
                agent_id=self.agent_id,
                channel=self.output_channel,
                sequence=input_message.sequence + 1,
                status="partial",
                confidence=0.1,
                payload=attribution_fallback(input_message.pipeline_run_id),
            )

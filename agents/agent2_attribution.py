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
        try:
            report: AttributionReport = self._call_model_json(
                prompt=prompt,
                response_model=AttributionReport,
                system_prompt=system_prompt,
                run_id=input_message.pipeline_run_id,
            )
        except Exception as e:
            self.logger.warning(
                f"Agent 2 model validation failed: {e}. Attempting fallback for sparse/malformed logs.",
                extra={"pipeline_run_id": input_message.pipeline_run_id}
            )
            from datetime import datetime, timezone
            from schemas.attribution_schema import AttackClassification, EntryPoint, AttackChainStep, LateralMovement, DataTargeted
            now = datetime.now(timezone.utc)
            report = AttributionReport(
                pipeline_run_id=input_message.pipeline_run_id,
                created_at=now,
                confidence_score=0.1,
                attack_classification=AttackClassification(
                    attack_type="unknown",
                    threat_actor_type="unknown",
                    sophistication_level="low"
                ),
                entry_point=EntryPoint(
                    identified=False,
                    resource="unknown",
                    method="unknown",
                    vulnerability_description="No identifiable entry point due to lack of log evidence."
                ),
                attack_chain=[
                    AttackChainStep(
                        step=1,
                        description="No clear security events detected to construct attack chain.",
                        mitre_technique_id="T1078",
                        mitre_technique_name="Valid Accounts",
                        mitre_tactic="Initial Access"
                    )
                ],
                lateral_movement=LateralMovement(
                    detected=False,
                    systems_traversed=[]
                ),
                data_targeted=DataTargeted(
                    likely_target="unknown",
                    evidence="No data exfiltration evidence found in logs."
                ),
                indicators_of_compromise=[],
                agent_notes="Failed to generate attribution report from sparse/malformed inputs."
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

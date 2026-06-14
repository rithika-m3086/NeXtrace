import json
from agents.base_agent import BaseAgent
from core.message_types import BandMessage
from schemas.postmortem_schema import PostMortemReport
from pipeline.state_manager import PipelineStateManager
import prompts.agent4_prompt as prompt_mod


class PostMortemAgent(BaseAgent):
    """Aggregates all prior stages and compiles the final PostMortemReport."""

    def __init__(self, band_client, state_manager: PipelineStateManager, logger=None):
        super().__init__(
            agent_id="agent4_postmortem",
            input_channel="impact_assessment",
            output_channel="postmortem_complete",
            band_client=band_client,
            logger=logger,
        )
        self.state_manager = state_manager

    async def process(self, input_message: BandMessage) -> BandMessage:
        self.logger.info("Agent 4 compiling final post-mortem report...")
        run_id = input_message.pipeline_run_id

        # Retrieve intermediate stage results from State Manager
        raw_input = self.state_manager.get_stage(run_id, "raw_evidence_input") or {}
        timeline_data = self.state_manager.get_stage(run_id, "forensic_timeline") or {}
        attribution_data = self.state_manager.get_stage(run_id, "attack_attribution") or {}
        impact_data = input_message.payload  # Current stage input

        # Extract values for the prompt builder
        org_name = raw_input.get("organization_name", "Unknown")
        agent1_conf = timeline_data.get("confidence_score", 0.8)
        agent2_conf = attribution_data.get("confidence_score", 0.8)
        agent3_conf = impact_data.get("confidence_score", 0.8)

        timeline_str = json.dumps(timeline_data, indent=2)
        attribution_str = json.dumps(attribution_data, indent=2)
        impact_str = json.dumps(impact_data, indent=2)
        compliance_flags_str = json.dumps(impact_data.get("compliance_flags", []), indent=2)

        prompt = prompt_mod.build_prompt(
            organization_name=org_name,
            agent1_confidence=agent1_conf,
            forensic_timeline_json=timeline_str,
            agent2_confidence=agent2_conf,
            attribution_json=attribution_str,
            agent3_confidence=agent3_conf,
            impact_json=impact_str,
            compliance_flags_json=compliance_flags_str,
        )
        system_prompt = prompt_mod.get_system_prompt()

        # Call model with self-correcting schema validator
        report: PostMortemReport = self._call_model_json(
            prompt=prompt,
            response_model=PostMortemReport,
            system_prompt=system_prompt,
            run_id=run_id,
        )

        self.logger.info(
            f"Agent 4 successfully compiled report with {len(report.remediation_plan)} remediation tasks.",
            extra={"pipeline_run_id": run_id}
        )

        # Build output message
        return BandMessage.create(
            pipeline_run_id=run_id,
            agent_id=self.agent_id,
            channel=self.output_channel,
            sequence=input_message.sequence + 1,
            status="success",
            confidence=report.confidence_score,
            payload=report.model_dump(mode="json"),
        )

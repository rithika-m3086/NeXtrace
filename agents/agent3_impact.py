import json
from agents.base_agent import BaseAgent
from core.message_types import BandMessage
from schemas.impact_schema import ImpactAssessment, ComplianceFlag
from pipeline.state_manager import PipelineStateManager
from utils.compliance_rules import evaluate as evaluate_compliance
import prompts.agent3_prompt as prompt_mod


class ImpactAssessmentAgent(BaseAgent):
    """Evaluates the business severity, blast radius, and compliance issues of the incident."""

    def __init__(self, band_client, state_manager: PipelineStateManager, logger=None):
        super().__init__(
            agent_id="agent3_impact",
            input_channel="attack_attribution",
            output_channel="impact_assessment",
            band_client=band_client,
            logger=logger,
        )
        self.state_manager = state_manager

    async def process(self, input_message: BandMessage) -> BandMessage:
        self.logger.info("Agent 3 processing attribution report...")
        run_id = input_message.pipeline_run_id
        attribution_data = json.dumps(input_message.payload)

        prompt = prompt_mod.build_prompt(attribution_data, input_message.confidence)
        system_prompt = prompt_mod.get_system_prompt()

        # Call model with self-correcting schema validator
        assessment: ImpactAssessment = self._call_model_json(
            prompt=prompt,
            response_model=ImpactAssessment,
            system_prompt=system_prompt,
        )

        # Retrieve organization metadata from raw evidence input
        raw_input = self.state_manager.get_stage(run_id, "raw_evidence_input") or {}
        metadata = raw_input.get("metadata", {})

        # Deterministically evaluate compliance regulations
        categories = assessment.blast_radius.data_categories_exposed
        self.logger.info(
            f"Agent 3: Evaluating compliance for categories: {categories} with metadata: {metadata}",
            extra={"pipeline_run_id": run_id}
        )
        compliance_dicts = evaluate_compliance(categories, metadata)

        # Merge compliance flags back into Pydantic model
        assessment.compliance_flags = [
            ComplianceFlag.model_validate(flag) for flag in compliance_dicts
        ]

        self.logger.info(
            f"Agent 3 successfully merged {len(assessment.compliance_flags)} compliance flags.",
            extra={"pipeline_run_id": run_id}
        )

        # Build output message
        return BandMessage.create(
            pipeline_run_id=run_id,
            agent_id=self.agent_id,
            channel=self.output_channel,
            sequence=input_message.sequence + 1,
            status="success",
            confidence=assessment.confidence_score,
            payload=assessment.model_dump(mode="json"),
        )

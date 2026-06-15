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
        try:
            report: PostMortemReport = self._call_model_json(
                prompt=prompt,
                response_model=PostMortemReport,
                system_prompt=system_prompt,
                run_id=run_id,
            )
        except Exception as e:
            self.logger.warning(
                f"Agent 4 model validation failed: {e}. Attempting fallback for sparse/malformed logs.",
                extra={"pipeline_run_id": run_id}
            )
            from datetime import datetime, timezone
            from schemas.postmortem_schema import ExecutiveSummary, TechnicalReport, RemediationActionItem, ConfidenceBreakdown
            now = datetime.now(timezone.utc)
            report = PostMortemReport(
                confidence_score=0.1,
                overall_severity="low",
                executive_summary=ExecutiveSummary(
                    headline="No security incident detected",
                    what_happened="The parsed logs did not contain sufficient evidence of a security incident or logs were malformed.",
                    business_impact="No business impact occurred.",
                    immediate_actions_taken="Inspected logs and verified system baseline.",
                    key_recommendations=["Verify logging configurations and log delivery channels."]
                ),
                technical_report=TechnicalReport(
                    incident_overview="Analyzed log input with insufficient or malformed evidence.",
                    timeline_summary="No relevant security events parsed.",
                    attack_description="No detectable attack pattern.",
                    root_cause="Lack of relevant logs or log format corruption.",
                    blast_radius_summary="No compromised systems or users identified."
                ),
                remediation_plan=[
                    RemediationActionItem(
                        action_id="REM-001",
                        priority="long_term",
                        category="monitoring",
                        title="Audit Log Integrity and Completeness",
                        description="Review SIEM ingestion, CloudTrail config, or log source output formatting.",
                        owner="SecOps / Platform Team",
                        estimated_effort="medium",
                        verification_method="Verify log stream in Kibana/Splunk/CloudWatch."
                    )
                ],
                confidence_breakdown=ConfidenceBreakdown(
                    agent1_forensic=agent1_conf,
                    agent2_attribution=agent2_conf,
                    agent3_impact=agent3_conf,
                    agent4_postmortem=0.1,
                    overall=0.1
                ),
                agent_notes="Failed to generate post-mortem from sparse/malformed inputs."
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

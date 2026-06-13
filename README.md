<p align="center">
  <!-- Product Logo placeholder (to be updated later) -->
  <!-- <img src="assets/nextrace_banner.png" width="600" alt="NeXtrace Logo" /> -->
</p>

<h2 align="center">NeXtrace — Security Incident Intelligence Platform</h2>

<div align="center">

<br/>

*Automate the full lifecycle of security incidents: from raw evidence to complete, blameless remediation.*

<br/>

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB?style=flat-square&logo=python)](https://www.python.org/)
[![Band](https://img.shields.io/badge/AI-Band%20(Thenvoi)-58a6ff?style=flat-square)](https://band.ai/)
[![Pydantic](https://img.shields.io/badge/Validation-Pydantic%20v2-E92063?style=flat-square&logo=pydantic)](https://pydantic.dev/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B?style=flat-square&logo=streamlit)](https://streamlit.io/)
[![OpenRouter](https://img.shields.io/badge/Inference-OpenRouter%20%7C%20AIML--API-black?style=flat-square)](https://openrouter.ai/)

</div>

---

## What is NeXtrace?

When a security breach occurs, organizations waste critical days manually investigating access logs, mapping attacker steps, calculating exposure boundaries, and compiling post-mortem reports.

**NeXtrace** solves this by deploying a collaborative pipeline of four specialized AI agents coordinated through **Band** as the live communication infrastructure. It automatically ingests raw logs, reconstructs a chronological forensic timeline, attributes techniques to the MITRE ATT&CK framework, runs a deterministic compliance rules engine, and compiles a comprehensive, blameless post-mortem with a prioritized remediation action plan — in minutes.

This is not a chatbot wrapper; it is an active multi-agent pipeline where agents delegate tasks, share context, and execute handoffs strictly over Band.

---

## Problem Statement

Incident response is bottlenecked by siloed processes. The forensic investigation team produces complex technical timelines. The compliance/post-mortem team translates these into business and legal reports. The engineering team awaits specific remediation instructions. 

Because these processes are manual and disconnected:
1. **Critical Delays**: Mandatory reporting deadlines (like GDPR's 72-hour window) are missed while analyzing logs.
2. **Imprecise Remediation**: Remediation guidelines end up generic (e.g., "patch your systems") instead of targeting the specific leaked IAM credential or misconfigured S3 bucket.
3. **Information Loss**: Context is lost during manual handoffs between analysts.
4. **AI Hallucinations**: Asking a single LLM to perform forensics, determine compliance, and generate a post-mortem results in high rates of hallucinated timestamps, fake IPs, or incorrect legal triggers.

---

## Proposed Solution

NeXtrace builds a highly reliable, structured multi-agent pipeline using a role-specialized collaboration model:
1. **Separation of Concerns**: Four distinct agents handle logs forensics, MITRE attribution, impact calculation, and post-mortem generation.
2. **Live Coordination via Band**: Agents do not invoke each other directly; they communicate by publishing and subscribing to named Band channels (`raw_evidence_input` -> `forensic_timeline` -> `attack_attribution` -> `impact_assessment` -> `postmortem_complete`).
3. **Deterministic Compliance Evaluation**: To prevent LLM hallucination of regulatory compliance obligations, we isolate the compliance engine. The AI identifies exposed data categories, and a pure Python rules engine deterministically triggers GDPR, HIPAA, SOC2, CCPA, or PCI DSS flags.
4. **Pydantic Validation Guardrails**: Every agent message envelope is validated against strict JSON schemas before being dispatched to the next channel, preventing cascading pipeline failures.

---

## The Build — Day by Day

| Day | What We Shipped |
|-----|----------------|
| **01** | 🏗️ Scaffolding & Core Architecture: Initialized folder structure, JSON structured logger, Band communication layer in `core/` (channels, coordinator, Mock + Live Thenvoi clients, `BandMessage` envelope), five Pydantic schemas, `base_agent` with self-correcting JSON extraction & single-retry guard, deterministic compliance rules engine, orchestrator, state manager, and unit/integration test suites. |
| **02** | 🗃️ Realistic Log Fixtures & E2E Validation: Created three correlated mock log fixtures (GitHub, CloudTrail, S3 Access) in `data/sample_logs/` for the API key leak scenario · Developed end-to-end scenario runner `scripts/run_scenario.py` · Verified multi-agent pipeline and tuned prompts to trigger GDPR, CCPA, HIPAA, and SOC2 alerts. |
| **03** | 🖥️ Streamlit Dashboard & Live Band Log: Shipped the dark-themed security console UI with CSS-injected severity tokens · Built live Band coordination log streaming agent hand-offs (processing → completed → error) with elapsed time and confidence metadata · Added tabbed result views for forensic timeline, MITRE attribution, impact/compliance (GDPR 72h clock), and blameless post-mortem · Wired sidebar controls, scenario fixtures, and session-state persistence in `ui/app.py`. |
| **04** | *[Add day 4 details here]* |
| **05** | *[Add day 5 details here]* |
| **06** | *[Add day 6 details here]* |

---

## Features

**Multi-Agent Band Pipeline**
Fully automated event-driven architecture mapping specialized agents (Forensic, Attribution, Blast Radius, Post-Mortem) to dedicated channels using `thenvoi-sdk`.

**Structured Pydantic Data Contracts**
End-to-end type safety and JSON schema validation for all agent message exchanges.

**Deterministic Compliance Evaluator**
Isolated Python rule evaluator preventing LLM hallucinations by calculating strict regulatory triggers (GDPR 72h, HIPAA, CCPA, PCI DSS, SOC2) downstream of Agent 3.

**Self-Correcting LLM Extraction Guardrails**
Built-in markdown-slicing parser and retry loop preventing invalid JSON formatting from breaking execution.

**Interactive Streamlit Dashboard**
Dark-themed security interface displaying real-time agent status streaming, forensic logs timeline, ATT&CK steps, and legal compliance reports.

**Blameless & Actionable Post-Mortem Writer**
Compiles objective incident reports with prioritized remediation plans.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Streamlit, Custom Vanilla CSS |
| **Backend Orchestrator** | Python 3.11+ |
| **Communication Bus** | Band Platform (`thenvoi-sdk` wrapper with mock pub-sub fallback) |
| **Data Contracts** | Pydantic v2 (Strict Schema Validation) |
| **Inference Models** | OpenRouter / AIML API (Claude 3.5 Sonnet / Gemini 2.5 Pro) |
| **Test Runner** | Pytest, Pytest-Asyncio |

---

## Multi-Agent Architecture

```
                      Raw Logs Input
                            │
                            ▼
                ┌───────────────────────┐
                │ ForensicEvidenceAgent │ (Agent 1: chronologically parses logs)
                └───────────────────────┘
                            │
                  [forensic_timeline]
                            ▼
                ┌────────────────────────┐
                │ AttackAttributionAgent │ (Agent 2: maps steps to MITRE ATT&CK)
                └────────────────────────┘
                            │
                  [attack_attribution]
                            ▼
                ┌───────────────────────┐
                │ ImpactAssessmentAgent │ (Agent 3: blast radius + compliance rules)
                └───────────────────────┘
                            │
                  [impact_assessment]
                            ▼
                 ┌──────────────────┐
                 │ PostMortemAgent  │ (Agent 4: compiles technical report)
                 └──────────────────┘
                            │
                  [postmortem_complete]
                            ▼
                     Orchestrator / UI
```

---

## Setup & Execution

### Prerequisites

- Python 3.11+
- OpenRouter API Key (or AIML API Key)

### 1. Clone the Repository

```bash
git clone https://github.com/rithika-m3086/NeXtrace.git
cd NeXtrace
```

### 2. Configure Environment

Install the frozen dependencies:

```bash
pip install -r requirements.txt
```

Create your `.env` file from the example:

```bash
cp .env.example .env
```

Open `.env` and configure your API keys:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
MODEL_NAME=anthropic/claude-3.5-sonnet
```

*Note: If `BAND_API_KEY` is not provided, the platform automatically switches to a local in-memory Mock pub-sub mechanism, allowing offline testing and development.*

### 3. Run Tests

To execute unit and integration test suites:

```bash
pytest
```

### 4. Run UI Dashboard

```bash
streamlit run ui/app.py
```

---

## Project Structure

```
NeXtrace/
├── agents/                  # Specialized Band-enabled AI agents
│   ├── base_agent.py        # Abstract BaseAgent with JSON guardrails and retry logic
│   ├── agent1_forensic.py   # Parses logs into normalized timeline events
│   ├── agent2_attribution.py# Maps threat activity to MITRE ATT&CK framework
│   ├── agent3_impact.py     # Calculates blast radius and data exposure
│   └── agent4_postmortem.py # Compiles professional post-mortem and remediation tasks
├── assets/                  # Images and logos
│   └── codeblooded_logo.jpg # Team CodeBlooded logo
├── core/                    # Communication bus wrapper and coordinator
│   ├── channels.py          # BandChannel definitions
│   ├── client.py            # BandClient & MockBandClient implementations
│   ├── coordinator.py       # Manages async subscribers and pipeline execution
│   └── message_types.py     # Standard message envelopes
├── data/                    # Sample evidence logs (CloudTrail, firewall, syslog)
├── outputs/                 # Directory where final reports are saved
├── pipeline/                # Orchestration and state manager
│   ├── orchestrator.py      # Hooks agents to channels and runs the pipeline
│   └── state_manager.py     # Aggregates context from all upstream stages
├── prompts/                 # System and user prompt templates
├── schemas/                 # Strict Pydantic data contracts
│   ├── input_schema.py      # RawEvidenceInput
│   ├── timeline_schema.py   # ForensicTimeline
│   ├── attribution_schema.py# AttributionReport
│   ├── impact_schema.py     # ImpactAssessment
│   └── postmortem_schema.py # PostMortemReport
├── tests/                   # Automated unit and integration test suites
│   ├── integration/
│   └── unit/
├── ui/                      # Streamlit UI dashboard components
│   ├── components/
│   └── styles/
├── utils/                   # Shared utility modules
│   ├── compliance_rules.py  # Deterministic regulatory rules engine
│   └── logger.py            # Structured JSON logger
├── pyproject.toml           # Project metadata and dependencies
└── requirements.txt         # Frozen package requirements
```

---

## Band Channels Reference

| Channel Name | Publisher | Subscriber | Message Schema |
|--------------|-----------|------------|----------------|
| `raw_evidence_input` | Orchestrator | Agent 1 | `RawEvidenceInput` |
| `forensic_timeline` | Agent 1 | Agent 2 | `ForensicTimeline` |
| `attack_attribution` | Agent 2 | Agent 3 | `AttributionReport` |
| `impact_assessment` | Agent 3 | Agent 4 | `ImpactAssessment` |
| `postmortem_complete` | Agent 4 | Orchestrator | `PostMortemReport` |
| `pipeline_status` | All Components | UI / Coordinator | `BandMessage` |
| `pipeline_errors` | All Agents | Orchestrator | `BandMessage` |

---

## Demo / Screenshots

*(Screenshots will be populated as frontend views are finalized)*

<table>
  <tr>
    <td width="50%"><img src="assets/dashboard_placeholder.png" alt="Dashboard" width="100%"/><br/><sub><b>Dashboard</b> — Multi-agent pipeline status and activity streams</sub></td>
    <td width="50%"><img src="assets/timeline_placeholder.png" alt="Timeline" width="100%"/><br/><sub><b>Incident Timeline</b> — Normalized events chronological list and attack map</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="assets/mitre_placeholder.png" alt="MITRE ATT&CK Matrix" width="100%"/><br/><sub><b>MITRE ATT&CK</b> — Identified tactics and techniques with confidence scores</sub></td>
    <td width="50%"><img src="assets/postmortem_placeholder.png" alt="Post-Mortem Report" width="100%"/><br/><sub><b>Post-Mortem & Remediation</b> — Auto-generated technical reports and action items</sub></td>
  </tr>
</table>

---

## Team

**CodeBlooded** — Built for the Band of Agents Hackathon (lablab.ai)

<p align="center">
  <img src="assets/codeblooded_logo.jpg" width="600" alt="CodeBlooded Logo" />
</p>

| Name | Role |
|------|------|
| **Dhanush Reddy S** | Backend Architecture · Multi-Agent Bus · Compliance Logic |
| **M Rithika** | UI/UX Development · Prompt Engineering · Integrations |

---

<div align="center">
<sub>Built with ☕ and zero sleep · CodeBlooded Team · 2026</sub>
</div>
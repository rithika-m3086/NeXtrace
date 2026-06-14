<h2 align="center">NeXtrace — Security Incident Intelligence Platform</h2>

<div align="center">

<br/>

*From raw machine logs to a blameless, actionable incident post-mortem — in minutes, coordinated by a band of specialized AI agents.*

<br/>

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB?style=flat-square&logo=python)](https://www.python.org/)
[![Band](https://img.shields.io/badge/Coordination-Band%20(Thenvoi)-58a6ff?style=flat-square)](https://band.ai/)
[![AI/ML API](https://img.shields.io/badge/Inference-AI%2FML%20API-black?style=flat-square)](https://aimlapi.com/)
[![Pydantic](https://img.shields.io/badge/Validation-Pydantic%20v2-E92063?style=flat-square&logo=pydantic)](https://pydantic.dev/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B?style=flat-square&logo=streamlit)](https://streamlit.io/)

Built for the **[Band of Agents Hackathon](https://lablab.ai/ai-hackathons/band-of-agents-hackathon)** · lablab.ai

</div>

---

## What is NeXtrace?

When a security breach occurs, organizations waste critical days manually investigating access logs, mapping attacker steps, calculating exposure boundaries, and compiling post-mortem reports — while mandatory reporting clocks (like GDPR's 72-hour window) are already ticking.

**NeXtrace** replaces that scramble with a **band of four specialized AI agents that collaborate through [Band](https://band.ai/)** as their live coordination layer. They join a shared Band chat room and hand work off to each other by **@mentioning** the next agent — exactly the way a human forensics → compliance → engineering team passes a case down the line, but in minutes.

The pipeline ingests raw logs, reconstructs a chronological forensic timeline, attributes attacker activity to the **MITRE ATT&CK** framework, runs a **deterministic compliance rules engine**, and compiles a **blameless post-mortem** with a prioritized, exportable remediation plan.

> This is not a chatbot wrapper. Band is the actual collaboration fabric — agents discover each other, divide work, pass shared context, and escalate errors over Band rooms.

---

## How Band is used (the core of this project)

NeXtrace treats Band as a real **multi-agent coordination layer**, not a notification sink:

- **Four separately-registered Band agents** — Forensic, Attribution, Impact, Post-Mortem — each with its own Band API key + agent UUID.
- **One shared chat room.** All agents join the same room and an orchestrator/observer identity streams the transcript into the UI.
- **Handoffs via @mention.** Each agent finishes its stage, posts a structured `BandMessage` envelope to the room via `create_agent_chat_message`, and **@mentions the next agent**. Band's per-agent delivery queue (`get_agent_next_message` → `mark_agent_message_processed`) routes the mention to the recipient, who runs its stage and mentions the agent after it.
- **Shared context + task state.** The envelope carries the accumulating incident context, a sequence number, confidence score, and stage status, so every agent works from the same evolving picture.
- **Role specialization & escalation.** Errors are published to an error channel and surfaced to the orchestrator; the live coordination log shows every hand-off, retry, and escalation in real time.

```
                 Band Chat Room  (@mention delivery queue · agent REST API)
   ┌───────────────────────────────────────────────────────────────────┐
   │  Orchestrator ──@Forensic──▶ Forensic ──@Attribution──▶ Attribution│
   │                                                  │                  │
   │                                            @Impact ▼                │
   │   UI  ◀──stream── Post-Mortem ◀──@PostMortem── Impact               │
   └───────────────────────────────────────────────────────────────────┘
```

> **Offline simulator:** when Band credentials are absent, NeXtrace runs the *exact same pipeline* over a faithful in-process pub/sub simulator (`MockBandClient`) that mirrors Band's channel + mention semantics — so the project runs anywhere for development and CI, and switches to live Band purely via configuration. The sidebar shows a **LIVE · Band / MOCK · Local bus** indicator at all times.

---

## Problem → Solution

| Incident-response pain | How NeXtrace addresses it |
|---|---|
| **Critical delays** — reporting deadlines missed while logs are analyzed by hand | Agents parallelize forensics → attribution → impact → post-mortem and finish in minutes |
| **Imprecise remediation** — "patch your systems" | Agent 4 emits a concrete, prioritized remediation plan you can file as **GitHub Issues / Jira tickets** in one click |
| **Context loss across manual handoffs** | Shared `BandMessage` envelope carries accumulating context through every Band hand-off |
| **LLM hallucinations** — one model doing forensics *and* law | Role separation + a **deterministic Python compliance engine** (no LLM) for GDPR/HIPAA/SOC2/CCPA/PCI-DSS triggers + Pydantic-validated contracts |
| **Sending secrets to a public LLM** is itself a breach | A **PII/secret masking pre-processor** redacts credentials, keys, cards and PII *before* any payload leaves the box |

---

## Features

**🔗 Band-coordinated multi-agent pipeline** — four specialized agents collaborate through a real Band chat room with @mention hand-offs, shared context, sequence/task state, and live status streaming.

**🧩 Strict Pydantic data contracts** — every inter-agent envelope is schema-validated before dispatch, preventing cascading failures.

**⚖️ Deterministic compliance evaluator** — an isolated pure-Python rules engine triggers GDPR (72h), HIPAA, SOC2, CCPA, and PCI-DSS obligations downstream of Agent 3, with zero hallucination risk.

**🛡️ PII / secret masking pre-processor** — deterministic, referential-integrity-preserving tokenization (`<REDACTED_EMAIL_1>`) of AWS keys, API tokens, JWTs, cards (Luhn-checked), SSNs, emails — *before* the LLM ever sees the logs. Security & privacy by design.

**🎯 Incident verdict summary** — overall severity, agent confidence, blast radius, compliance exposure, and redaction count surfaced as console metric cards at the top of every report.

**🗺️ Visual attack journey** — a Mermaid attack-path diagram generated deterministically from the MITRE chain, plus a **GeoIP origin map** pinning attacker source IPs.

**🎫 Interactive remediation & ticket export** — tick off remediation tasks and file them as **GitHub Issues** or **Jira** tickets, or export a **PDF audit report** / markdown checklist for the compliance record.

**🧱 Self-correcting LLM guardrails** — markdown-slicing JSON extraction + single-retry self-correction loop, 15s timeouts, exponential backoff, rolling rate-limiting, SIEM noise pre-filter, and context-window chunking.

**🖥️ Dark security-console UI** — Streamlit dashboard with a real-time Band coordination log (processing → completed → error, elapsed time, confidence) and a live/mock mode indicator.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Coordination layer** | **Band** (Thenvoi) via `thenvoi-sdk` — rooms, @mentions, per-agent delivery queue · faithful local simulator fallback |
| **Inference (partner)** | **[AI/ML API](https://aimlapi.com/)** (OpenAI-compatible) — Claude / GPT class models · optional OpenRouter fallback |
| **Frontend** | Streamlit + custom security-console CSS · Mermaid.js · `st.map` |
| **Data contracts** | Pydantic v2 (strict schema validation) |
| **Exports** | ReportLab (PDF) · GitHub Issues API · Jira Cloud API |
| **Tests** | Pytest, Pytest-Asyncio (44 tests) |

---

## Multi-Agent Architecture

| # | Agent | Input (subscribes) | Output (publishes → @mentions) | Schema |
|---|-------|--------------------|-------------------------------|--------|
| 1 | **ForensicEvidenceAgent** | `raw_evidence_input` | `forensic_timeline` → Agent 2 | `ForensicTimeline` |
| 2 | **AttackAttributionAgent** | `forensic_timeline` | `attack_attribution` → Agent 3 | `AttributionReport` |
| 3 | **ImpactAssessmentAgent** | `attack_attribution` | `impact_assessment` → Agent 4 | `ImpactAssessment` |
| 4 | **PostMortemAgent** | `impact_assessment` | `postmortem_complete` → Orchestrator | `PostMortemReport` |

`pipeline_status` and `pipeline_errors` carry live status/escalation to the orchestrator and UI.

---

## Setup & Execution

### Prerequisites
- Python **3.13** (pinned in `.python-version`; 3.11+ supported)
- An **AI/ML API** key (partner provider) — get one at [aimlapi.com](https://aimlapi.com/) and redeem the hackathon coupon
- *(Optional, for live coordination)* a **Band** account + four registered agents and one chat room

### 1. Clone & install
```bash
git clone https://github.com/rithika-m3086/NeXtrace.git
cd NeXtrace
pip install -r requirements.txt          # or: uv sync --extra test
```

### 2. Configure environment
```bash
cp .env.example .env
```
Minimum to run (offline mock coordination):
```env
AIML_API_KEY=your_aiml_api_key_here
MODEL_NAME=anthropic/claude-3.5-sonnet
```
To run **live over Band**, also register four agents + a room in [app.band.ai](https://app.band.ai) and set:
```env
BAND_ROOM_ID=...
BAND_AGENT1_API_KEY=...   BAND_AGENT1_ID=...
BAND_AGENT2_API_KEY=...   BAND_AGENT2_ID=...
BAND_AGENT3_API_KEY=...   BAND_AGENT3_ID=...
BAND_AGENT4_API_KEY=...   BAND_AGENT4_ID=...
```
*(Optional)* `GITHUB_TOKEN` + `GITHUB_REPO` or `JIRA_*` to enable ticket export.

> 🔒 **Never commit `.env`.** It is git-ignored. Rotate any key that has ever been committed.

### 3. Verify Band credentials (live mode)
```bash
uv run python scripts/verify_band.py
```
Validates each agent via `GET /agent/me` and confirms room membership.

### 4. Run the tests
```bash
uv run --extra test python -m pytest -q          # 44 passing
```

### 5. Launch the dashboard
```bash
streamlit run ui/app.py
```

---

## Hackathon Compliance

NeXtrace is built directly against the [Band of Agents](https://lablab.ai/ai-hackathons/band-of-agents-hackathon) judging criteria:

| Criterion | How NeXtrace meets it |
|---|---|
| **Use of Band as coordination layer** | 4 separately-registered agents collaborate through a shared Band room with @mention hand-offs, shared context, sequence/task state, and a live transcript — Band is the fabric, not a wrapper |
| **Clarity of explanation** | Real-time Band coordination log + Mermaid attack path make the multi-agent workflow visible step-by-step; the verdict summary states the outcome up front |
| **Real enterprise workflow** | Automates the forensics → compliance → engineering incident lifecycle, reduces manual coordination, and outputs filable tickets + an audit PDF |
| **Creative multi-agent collaboration** | Role-specialized agents that divide work, pass evolving context, and escalate errors — beyond a single-agent assistant |
| **Partner technology (AI/ML API)** | All agent reasoning is routed through AI/ML API |

**Submission assets:** working app (URL) · ≤5-min demo video · slide deck (PDF) · this public, MIT-compliant repository.

---

## Demo / Screenshots

<table>
  <tr>
    <td width="50%"><img src="assets/screenshots/01_dashboard.png" alt="Dashboard & live Band log" width="100%"/><br/><sub><b>Console + Live Band Log</b> — real-time agent hand-offs over Band</sub></td>
    <td width="50%"><img src="assets/screenshots/02_verdict_timeline.png" alt="Verdict & forensic timeline" width="100%"/><br/><sub><b>Incident Verdict + Timeline</b> — severity, confidence, normalized events</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="assets/screenshots/03_attack_map.png" alt="Mermaid attack path + GeoIP map" width="100%"/><br/><sub><b>Attack Path + Origin Map</b> — MITRE chain as a Mermaid diagram, attacker GeoIP</sub></td>
    <td width="50%"><img src="assets/screenshots/04_postmortem_export.png" alt="Post-mortem & ticket export" width="100%"/><br/><sub><b>Post-Mortem + Export</b> — remediation checklist, GitHub/Jira & PDF export</sub></td>
  </tr>
</table>

---

## Project Structure

```
NeXtrace/
├── agents/                  # Specialized Band-enabled agents (base + 4 roles)
├── core/
│   ├── channels.py          # BandChannel definitions
│   ├── client.py            # BandClient facade (Mock | Live) + MockBandClient
│   ├── live_band.py         # Live Band transport: room + @mention routing, WS receive
│   ├── coordinator.py       # Hand-off / status / timeout tracking
│   └── message_types.py     # BandMessage envelope
├── pipeline/                # Orchestrator + state manager
├── prompts/                 # System/user prompt templates per agent
├── schemas/                 # Strict Pydantic contracts
├── utils/
│   ├── compliance_rules.py  # Deterministic regulatory engine
│   ├── pii_masker.py        # Secret/PII masking pre-processor
│   ├── severity.py          # Incident verdict aggregation
│   ├── mermaid.py           # MITRE → Mermaid attack path
│   ├── geoip.py             # Attacker IP geolocation
│   ├── ticketing.py         # GitHub Issues / Jira / markdown export
│   ├── pdf_report.py        # PDF audit report (ReportLab)
│   ├── log_filter.py · chunker.py · rate_limiter.py · logger.py
├── ui/
│   ├── app.py               # Streamlit dashboard
│   ├── components/          # band_status, summary_view, attack_map, ticket_export, *_view
│   └── styles/theme.py      # Dark security-console theme
├── scripts/
│   ├── run_scenario.py      # CLI E2E runner
│   └── verify_band.py       # Live Band credential/room verifier
├── data/sample_logs/        # Correlated attack fixtures + edge cases
└── tests/                   # 44 unit + integration tests
```

---

## The Build — Day by Day

| Day | What We Shipped |
|-----|----------------|
| **01** | 🏗️ Scaffolding & core architecture: Band communication layer, five Pydantic schemas, self-correcting base agent, deterministic compliance engine, orchestrator, state manager, test suites. |
| **02** | 🗃️ Correlated mock log fixtures (GitHub + CloudTrail + S3) for an API-key-leak attack · CLI scenario runner · prompt tuning to trigger GDPR/CCPA/HIPAA/SOC2. |
| **03** | 🖥️ Dark-themed Streamlit console · live Band coordination log (processing → completed → error) · tabbed forensic / ATT&CK / impact / post-mortem views. |
| **04** | 🛡️ Hardening: sparse / noisy / malformed inputs · 15s LLM timeouts, retries, transient-error alerts · rate-limiting, SIEM pre-filter, context chunking · degradation tests. |
| **05** | 🚀 Real Band integration (room + @mention WebSocket transport, per-agent identities, `verify_band.py`) · AI/ML API partner inference · PII masking · incident verdict summary · Mermaid attack path · GeoIP map · GitHub/Jira ticket export · PDF audit report · live/mock indicator · packaging + Python pin fixes · 44 tests green. |
| **06** | ✅ Cold-start dry runs, deployment, and final submission assets (video, deck, public repo). |

---

## Team

**CodeBlooded** — Built for the Band of Agents Hackathon (lablab.ai)

| Name | Role |
|------|------|
| **Dhanush Reddy S** | Backend architecture · Multi-agent Band layer · Compliance logic |
| **M Rithika** | UI/UX development · Prompt engineering · Integrations |

<p align="center">
  <img src="assets/codeblooded_logo.jpg" width="420" alt="CodeBlooded Logo" />
</p>

---

<div align="center">
<sub>NeXtrace · multi-agent security incident intelligence, coordinated through Band · 2026</sub>
</div>

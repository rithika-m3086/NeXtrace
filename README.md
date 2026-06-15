<div align="center">

# 🛡️ NeXtrace

### Security Incident Intelligence, coordinated by a *band* of AI agents

*From raw machine logs to a blameless, board-ready incident post-mortem — in minutes, not days.*

<br/>

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Band](https://img.shields.io/badge/Coordinated_by-Band-58a6ff?style=for-the-badge)](https://band.ai/)
[![AI/ML API](https://img.shields.io/badge/Inference-AI%2FML_API-000000?style=for-the-badge)](https://aimlapi.com/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/tests-44_passing-3fb950?style=for-the-badge)](#-quickstart)

**[🎥 Demo Video](#-demo) · [🚀 Live App](#-demo) · [📊 Slide Deck](#-demo)** &nbsp;|&nbsp; Built for the **[Band of Agents Hackathon](https://lablab.ai/ai-hackathons/band-of-agents-hackathon)** · lablab.ai

</div>

---

> **TL;DR** — When a breach hits, four specialized AI agents (**Forensic → Attribution → Impact → Post-Mortem**) join a shared **Band** chat room and hand the case down the line by **@mentioning** each other — exactly like a human IR team, but in minutes. They turn raw logs into a forensic timeline, a MITRE ATT&CK attribution, a deterministic compliance assessment, and a blameless post-mortem with exportable remediation tickets.

---

## ⚡ Why NeXtrace wins

| Judging criterion | How we nail it |
|---|---|
| **Band as the coordination layer** | 4 separately-registered Band agents collaborate in one room via real `@mention` hand-offs — shared context, task state, role specialization. Band is the *fabric*, not a wrapper. |
| **Clarity of explanation** | A live Band coordination log streams every hand-off in real time; a Mermaid diagram draws the attack path; a verdict banner states the outcome up front. |
| **Real enterprise workflow** | Automates the forensics → compliance → engineering lifecycle and ends with **filable GitHub/Jira tickets** + an **audit PDF**. |
| **Creative multi-agent collaboration** | Role-specialized agents that divide work, pass evolving context, and escalate errors — far beyond a single-agent chatbot. |
| **Partner technology** | All agent reasoning runs on **AI/ML API**. |

---

## 🎬 Demo

| | |
|---|---|
| 🎥 **Demo video** | `<add YouTube/Loom link>` |
| 🚀 **Live app** | `<add Streamlit Community Cloud URL>` |
| 📊 **Slide deck** | `<add deck link>` |

<!--
  Screenshots are captured from a completed run (streamlit run ui/app.py) and
  live in assets/screenshots/. Uncomment once the PNGs are added.

<table>
  <tr>
    <td width="50%"><img src="assets/screenshots/01_dashboard.png" width="100%"/><br/><sub><b>Console + Live Band Log</b></sub></td>
    <td width="50%"><img src="assets/screenshots/02_verdict_timeline.png" width="100%"/><br/><sub><b>Incident Verdict + Timeline</b></sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="assets/screenshots/03_attack_map.png" width="100%"/><br/><sub><b>Attack Path + Origin Map</b></sub></td>
    <td width="50%"><img src="assets/screenshots/04_postmortem_export.png" width="100%"/><br/><sub><b>Post-Mortem + Ticket/PDF Export</b></sub></td>
  </tr>
</table>
-->

> 📸 *Screenshots are added to `assets/screenshots/` once the dashboard is run with a live inference key — see [the capture guide](assets/screenshots/README.md).*

---

## 🔥 The problem

When a security breach occurs, organizations waste **critical days** manually investigating access logs, mapping attacker steps, calculating exposure, and compiling reports — while mandatory reporting clocks (like **GDPR's 72-hour window**) are already ticking.

| Incident-response pain | How NeXtrace fixes it |
|---|---|
| **Delays** — deadlines missed while logs are read by hand | Agents parallelize the whole lifecycle and finish in minutes |
| **Imprecise remediation** — "patch your systems" | Concrete, prioritized plan you can file as **GitHub Issues / Jira tickets** in one click |
| **Context lost** across manual handoffs | A shared `BandMessage` envelope carries accumulating context through every Band hand-off |
| **LLM hallucination** — one model doing forensics *and* law | Role separation + a **deterministic Python compliance engine** (no LLM) + Pydantic-validated contracts |
| **Sending secrets to a public LLM** is itself a breach | A **PII/secret masker** redacts credentials, keys, cards & PII *before* anything leaves the box |

---

## 🤝 How Band is used (the heart of this project)

NeXtrace treats Band as a genuine **multi-agent coordination layer**, not a notification sink:

- **Four separately-registered Band agents** — Forensic, Attribution, Impact, Post-Mortem — each with its own Band API key + agent UUID.
- **One shared chat room.** All agents join the same room; an orchestrator/observer identity streams the transcript into the UI.
- **Hand-offs via @mention.** Each agent finishes its stage, posts a structured `BandMessage` envelope with `create_agent_chat_message`, and **@mentions the next agent**. Band's per-agent delivery queue (`get_agent_next_message` → `mark_agent_message_processed`) routes the mention to the recipient, who runs its stage and mentions the agent after it.
- **Shared context + task state.** The envelope carries the accumulating incident context, a sequence number, a confidence score, and stage status — so every agent works from the same evolving picture.
- **Role specialization & escalation.** Errors are published to an error channel and surfaced to the orchestrator; the live log shows every hand-off, retry, and escalation as it happens.

```
                 Band Chat Room  (@mention delivery queue · agent REST API)
   ┌───────────────────────────────────────────────────────────────────────┐
   │  Orchestrator ──@Forensic──▶ Forensic ──@Attribution──▶ Attribution    │
   │                                                    │                    │
   │                                              @Impact ▼                  │
   │     UI  ◀──stream── Post-Mortem ◀──@PostMortem── Impact                 │
   └───────────────────────────────────────────────────────────────────────┘
```

> **Runs anywhere.** With no Band credentials, the *exact same pipeline* runs over a faithful in-process pub/sub simulator (`MockBandClient`) that mirrors Band's channel + mention semantics — so development and CI work offline, and live Band is purely a config switch. The sidebar always shows a **🟢 LIVE · Band / 🟡 MOCK · Local bus** indicator.

---

## 🧠 The agent band

| # | Agent | Subscribes to | Publishes → @mentions | Schema |
|---|-------|---------------|------------------------|--------|
| 1 | **ForensicEvidenceAgent** | `raw_evidence_input` | `forensic_timeline` → Agent 2 | `ForensicTimeline` |
| 2 | **AttackAttributionAgent** | `forensic_timeline` | `attack_attribution` → Agent 3 | `AttributionReport` |
| 3 | **ImpactAssessmentAgent** | `attack_attribution` | `impact_assessment` → Agent 4 | `ImpactAssessment` |
| 4 | **PostMortemAgent** | `impact_assessment` | `postmortem_complete` → Orchestrator | `PostMortemReport` |

`pipeline_status` and `pipeline_errors` carry live status + escalation to the orchestrator and UI.

---

## ✨ Features

- 🔗 **Band-coordinated multi-agent pipeline** — real room, real @mention hand-offs, shared context, live status streaming.
- 🛡️ **PII / secret masking pre-processor** — deterministic, referential-integrity-preserving tokens (`<REDACTED_EMAIL_1>`) for AWS keys, API tokens, JWTs, Luhn-checked cards, SSNs, emails — *before* the LLM sees anything. Security & privacy by design.
- ⚖️ **Deterministic compliance evaluator** — pure-Python rules trigger GDPR (72h), HIPAA, SOC2, CCPA, PCI-DSS with zero hallucination risk.
- 🎯 **Incident verdict summary** — overall severity, agent confidence, blast radius, compliance exposure, redaction count, all up front.
- 🗺️ **Visual attack journey** — a Mermaid attack-path diagram from the MITRE chain + a **GeoIP origin map** of attacker IPs.
- 🎫 **Interactive remediation & export** — tick off tasks and file them as **GitHub Issues** / **Jira**, or export a **PDF audit report** / markdown checklist.
- 🧱 **Production-grade guardrails** — self-correcting JSON extraction, 15s timeouts, exponential backoff, rolling rate-limits, SIEM noise pre-filter, context-window chunking, Pydantic contracts.
- 🖥️ **Dark security-console UI** — Streamlit dashboard with a real-time Band coordination log and live/mock indicator.

---

## 🚀 Quickstart

**Prerequisites:** Python **3.13** · an **[AI/ML API](https://aimlapi.com/)** key · *(optional)* a Band account with 4 registered agents + 1 room.

```bash
# 1. Clone & install
git clone https://github.com/rithika-m3086/NeXtrace.git
cd NeXtrace
pip install -r requirements.txt           # or: uv sync --extra test

# 2. Configure
cp .env.example .env                       # then set AIML_API_KEY (+ Band creds for live mode)

# 3. Test  (44 passing)
uv run --extra test python -m pytest -q

# 4. (live mode) verify Band credentials
uv run python scripts/verify_band.py

# 5. Launch the console
streamlit run ui/app.py
```

**Minimum `.env` (offline mock coordination):**
```env
AIML_API_KEY=your_aiml_api_key_here
MODEL_NAME=anthropic/claude-3.5-sonnet
```

**Per-Agent Provider & Model Overrides (Hybrid Routing):**
Configure specific agents to utilize different providers (e.g. `aiml`, `featherless`, or `openrouter`) and model IDs:
```env
AGENT1_PROVIDER=featherless
AGENT1_MODEL=meta-llama/llama-3-70b-instruct
FEATHERLESS_API_KEY=your_featherless_api_key_here
```


**Live Band coordination** — register 4 agents + a room at [app.band.ai](https://app.band.ai), then add:
```env
BAND_ROOM_ID=...
BAND_AGENT1_API_KEY=...   BAND_AGENT1_ID=...
BAND_AGENT2_API_KEY=...   BAND_AGENT2_ID=...
BAND_AGENT3_API_KEY=...   BAND_AGENT3_ID=...
BAND_AGENT4_API_KEY=...   BAND_AGENT4_ID=...
```
*(Optional)* `GITHUB_TOKEN` + `GITHUB_REPO` or `JIRA_*` enable one-click ticket export.

> 🔒 **Never commit `.env`** (it's git-ignored). Rotate any key that has ever been committed.

---

## 🧰 Tech stack

| Layer | Technology |
|-------|-----------|
| **Coordination** | **Band** (Thenvoi) via `thenvoi-sdk` — rooms, @mentions, per-agent delivery queue · faithful local simulator fallback |
| **Inference (partner)** | **[AI/ML API](https://aimlapi.com/)** (OpenAI-compatible) · optional OpenRouter fallback |
| **Frontend** | Streamlit + custom security-console CSS · Mermaid.js · `st.map` |
| **Data contracts** | Pydantic v2 (strict schema validation) |
| **Exports** | ReportLab (PDF) · GitHub Issues API · Jira Cloud API |
| **Tests** | Pytest + Pytest-Asyncio (44 tests) |

---

## 🗂️ Project structure

```
NeXtrace/
├── agents/                  # base_agent + 4 role agents (Forensic, Attribution, Impact, Post-Mortem)
├── core/
│   ├── client.py            # BandClient facade (Mock | Live) + MockBandClient
│   ├── live_band.py         # Live Band transport: room + @mention routing, poll-ack receive
│   ├── coordinator.py       # Hand-off / status / timeout tracking
│   ├── channels.py          # BandChannel definitions
│   └── message_types.py     # BandMessage envelope
├── pipeline/                # orchestrator + state manager
├── prompts/                 # per-agent system/user templates
├── schemas/                 # strict Pydantic contracts
├── utils/
│   ├── compliance_rules.py  # deterministic regulatory engine
│   ├── pii_masker.py        # secret/PII masking pre-processor
│   ├── severity.py          # incident verdict aggregation
│   ├── mermaid.py           # MITRE → Mermaid attack path
│   ├── geoip.py             # attacker IP geolocation
│   ├── ticketing.py         # GitHub / Jira / markdown export
│   ├── pdf_report.py        # PDF audit report
│   └── log_filter.py · chunker.py · rate_limiter.py · logger.py
├── ui/
│   ├── app.py               # Streamlit dashboard
│   ├── components/          # band_status · summary_view · attack_map · ticket_export · *_view
│   └── styles/theme.py      # dark security-console theme
├── scripts/
│   ├── run_o.py      # CLI E2E runner
│   └── verify_band.py       # live Band credential / room verifier
├── data/sample_logs/        # correlated attack fixtures + edge cases
└── tests/                   # 44 unit + integration tests
```

---

## 🏆 Hackathon submission

- ✅ **Working app** (Streamlit) · ✅ **≤5-min demo video** · ✅ **slide deck (PDF)** · ✅ **public, MIT-compliant repo**
- 🎯 **Partner prize:** AI/ML API (all agent inference routed through it)
- 📅 Built for the [Band of Agents Hackathon](https://lablab.ai/ai-hackathons/band-of-agents-hackathon)

---

## 👥 Team — CodeBlooded

| Name | Role |
|------|------|
| **Dhanush Reddy S** | Backend architecture · Multi-agent Band layer · Compliance logic |
| **M Rithika** | UI/UX development · Prompt engineering · Integrations |

<p align="center">
  <img src="assets/codeblooded_logo.jpg" width="360" alt="CodeBlooded" />
</p>

<div align="center">
<sub>NeXtrace · multi-agent security incident intelligence, coordinated through Band · 2026</sub>
</div>

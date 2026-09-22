# TeamSync AI: Explainable Multi-Agent Project Intelligence Platform

## 1. Problem & Objectives
**Problem**: Teams detect coordination failures late; tools show *what* not *why*; data silos prevent synthesis; PMs manually correlate signals; institutional memory lost.

**Objectives**: (1) Modular multi-agent architecture for project intelligence; (2) Explainable AI with evidence chains, confidence scores, fallbacks; (3) Unified intelligence index (health, risk, comm, workload, memory); (4) Production-grade: multi-tenancy, real-time, scheduled analysis.

## 2. Architecture
```
Frontend (Next.js) → Core API (FastAPI) → PostgreSQL
                        ↓
                  AI Service (FastAPI) → Groq (Llama 3.1)
                        ↓
                  Redis → Celery Workers
```

| Service | Tech | Port | Role |
|---------|------|------|------|
| Frontend | Next.js 14, React 18, Tailwind, TS | 3000 | UI, dashboards, Kanban, WebSocket |
| Core API | FastAPI, SQLAlchemy 2.0, Pydantic v2 | 8000 | Auth, CRUD, multi-tenancy, WS, Celery |
| AI Service | FastAPI, LangGraph, Groq | 8001 | 10-agent pipeline, structured LLM output |
| DB | PostgreSQL 16 | 5432 | Primary persistence |
| Cache/Queue | Redis 7 | 6379 | Cache, Celery broker |
| Workers | Celery | - | Background tasks, scheduled analysis |

## 3. Core Backend (FastAPI)
**Auth**: JWT HS256, bcrypt, refresh rotation, RBAC (Owner/Admin/PM/Dev/Viewer), org-scoped multi-tenancy, tenant middleware.

**API** (`/api/v1/`): `/auth`, `/organizations`, `/projects`, `/tasks`, `/meetings`, `/analytics`, `/admin`, `/ws`

**Models**: User, Org, Role, Team, Project (health/risk scores), Milestone, Task (Kanban statuses), TaskDependency, TaskComment, Meeting, Participant, ActionItem, Decision, CommunicationEvent, RiskScore (6 types), Recommendation, AgentRun, OrganizationMemory, AuditLog, Notification, WorkloadSnapshot.

**Celery Beat**: Daily workload snapshots; Hourly scheduled analyses for stale projects.

## 4. AI Service - Multi-Agent Pipeline
**Pattern**: Coordinator → 7 Specialists (parallel) → Risk → Recommendation → (optional) Review Trio.

### Agents
| Agent | Input | Output | Risks Detected |
|-------|-------|--------|----------------|
| Planning | Milestones, tasks, capacity | Sprint readiness %, feasibility, capacity gaps | Delay, Dependency |
| Progress | Tasks, velocity history | Velocity trend, forecast, stalled work | Delay, Coordination |
| Meeting Intel | Transcript, participants | Decisions, actions, blockers, owners, deadlines | Coordination, Knowledge |
| Comm Intel | Events (14d) | Response delays, unanswered Qs, participation gaps | Silent Member, Coordination |
| Workload Intel | Assignments, story points | Overloaded/underutilized, SPOFs, dep concentration | Workload, Dependency |
| Risk Prediction | All specialist outputs | 6 risk scores + evidence, overall level | All 6 |
| Recommendation | Risk + specialist outputs | Prioritized actions with reasoning | N/A |

**Review Trio** (on-demand): Frontend (UI/UX/perf), Backend (scale/security/API), AI/ML (model/data/eval) → Consensus: Approve / Approve w/ Changes / Request Revision / Reject.

### Unified Output Schema (all agents)
```python
AgentOutput: summary, risk_level[low/med/high/crit], confidence[0-1],
             signals[{name, value, weight}], evidence[{source, ref_id, excerpt, relevance}],
             recommendations[{type, title, desc, reasoning, priority, confidence}],
             next_action, metadata
```

### LLM & Fallbacks
- **Groq Llama 3.1 70B**, JSON mode, schema-enforced, temp 0.1, 2 retries
- **Rule-based fallback** per agent (identical schema): capacity heuristics, velocity trends, keyword extraction, response-time analysis, load variance, risk aggregation, risk→action mapping

### Coordinator Flow
1. Run specialists in parallel (`asyncio.gather`)
2. Specialist outputs → RiskPredictionAgent
3. Risk + specialists → RecommendationAgent
4. Optional: Review Trio (3 agents parallel)
5. Merge recs, compute overall risk/confidence → `CoordinatorOutput`

### Team Intelligence Index (0-100)
`WEIGHTS = {health:0.25, risk:0.25, comm:0.20, workload:0.15, memory:0.15}` → Tiers: Excellent≥90, Good≥75, Fair≥60, Poor≥40, Critical<40.

### AI API
`POST /analyze` (background), `POST /agents/{name}`, `POST /review`, `GET /health`

## 5. Frontend (Next.js 14)
**Stack**: App Router, React 18, Tailwind, shadcn/ui, TanStack Query, Zustand, Socket.io, Recharts, @hello-pangea/dnd, Zod, RHF.

**Pages**: `/workspace`, `/projects/[id]/dashboard` (health/risk tabs), `/tasks` (Kanban), `/analytics`, `/meetings`, `/analytics/ai`.

**Real-time**: WS for task changes, risk updates, recommendations, notifications, presence.

## 6. Database (PostgreSQL)
**Core tables**: organizations, users, roles, user_roles, teams, team_members, projects, project_members, milestones, tasks, task_dependencies, task_comments, meetings, meeting_participants, meeting_action_items, meeting_decisions, communication_events, risk_scores, recommendations, agent_runs, organization_memory, audit_logs, notifications, workload_snapshots.

**Indexes**: Composite `(org_id, project_id)`, partial for status filters, JSONB GIN for evidence/factors/context.

## 7. Deployment
**Docker Compose**: postgres, redis, backend, ai-service, celery-worker, celery-beat, frontend.

**Env**: `JWT_SECRET`, `DB_PASSWORD`, `GROQ_API_KEY`, `AI_MODEL=llama-3.3-70b-versatile`, `AI_TEMPERATURE=0.1`, `AI_MAX_TOKENS=4096`, `AI_TIMEOUT_SECONDS=60`.

**K8s**: Manifests in `k8s/`, health checks, resource limits, secrets, Alembic migrations in CI/CD.

## 8. Key Innovations
1. **Modular agents**: Decompose intelligence → 7 specialists + coordinator; parallel execution; fault isolation; extensible.
2. **XAI by design**: Schema-enforced structured output; evidence-first (every signal/rec needs source); confidence propagation; deterministic fallback with identical schema.
3. **Unified Intelligence Index**: 5-dim weighted score; configurable weights; actionable tiers; historical tracking.
4. **Production engineering**: Multi-tenancy from ground up; async-first (FastAPI + SQLAlchemy 2.0 + asyncpg); Celery for long-running AI; WS for live UX.
5. **Professional Review Trio**: Domain-specific agents; structured consensus; proposal-driven.

## 9. Specs Summary
- **LOC**: ~21K (Backend 8K, AI 4.5K, Frontend 6K, Models 1.5K, Infra 1K)
- **Deps**: Backend: fastapi, sqlalchemy[asyncio], pydantic, python-jose, passlib, celery, redis, alembic, httpx; AI: fastapi, groq, pydantic, httpx, langgraph; Frontend: next, react, ts, tailwind, @tanstack/react-query, zustand, socket.io-client, recharts, @hello-pangea/dnd, zod, rhf, @radix-ui/*, lucide-react
- **API**: Core ~40 REST + WS; AI 4 endpoints; OpenAPI at `/docs`

## 10. Evaluation

All numbers below are reproducible from `ai-service/eval/`. Nothing here is
estimated or illustrative.

### 10.1 Engineering baseline
- **Tests**: backend 82, ai-service 85 (`pytest -m "not deferred"`), frontend 58 (`vitest run`), all run in CI on every push
- **Quality**: ruff/mypy (Py), eslint/prettier/tsc (TS)
- **Demo seed**: `make db-seed` → 1 org, 5 users, 3 projects, 50+ tasks

### 10.2 Synthetic detection correctness (`python -m eval.run_eval`)
180 generated scenarios (90 pos / 90 neg, 30 per risk type) where the anomaly
is injected deterministically, so the label is known by construction.

| Metric | Value |
|---|---|
| Precision / Recall / F1 / Accuracy | 1.00 / 1.00 / 1.00 / 1.00 |
| Stability | identical across 4 further seeds (1,200 extra trials) |

**Interpretation (important):** for deterministic threshold code on
unambiguous inputs, 100% is the *expected* result of correctness — this is
equivalent to "all unit tests pass", **not** evidence of generalization. It
is reported as an implementation-correctness check, nothing more.

A stronger, genuinely falsifiable check is the boundary sweep
(`python -m eval.boundary_eval`), which verifies each detector flips exactly
at its documented threshold:

| Signal | Documented | Observed transition |
|---|---|---|
| `overdue_ratio` | 0.10 | flips at exactly 0.10 |
| `silent_ratio` | 0.30 | 0.20 → 0.30 (exact) |
| `workload_skew` | 1.50 | bracketed 1.429 → 1.522 |

### 10.3 Efficiency and reliability

| Metric | Value | Component tested |
|---|---|---|
| Prompt tokens, 13 → 2,003 tasks | 266 → 390 (**1.47×** for a **154×** size increase) | `SubgraphSelector` |
| vs. pre-graph architecture at 2,003 tasks | 189,834 → 390 tokens (**99.8%**, 487×) | witness-subgraph selection |
| Deterministic pipeline latency (203 tasks, n=50) | p50 4.8–11.0 ms, p95 6.1–13.4 ms | build + metrics + select |
| Evidence-grounding enforcement | 200/200 fabricated refs stripped | `grounding.py` |

Latency varies with machine load between runs; the claim is "single-digit to
low-double-digit milliseconds", which is what justifies running analysis
synchronously without a queue.

### 10.4 Real-world evaluation — TAWOS

**Dataset.** TAWOS (Tawosi et al., MSR 2022), Apache 2.0 — 458,232 Jira
issues, 39 open-source projects, 12 public Jira repositories. Loaded via a
purpose-built mysqldump parser; **0 parse errors across the full 4.3 GB dump**
(row counts reconciled exactly against the published totals).

**Task.** Sprint-level delay prediction. TAWOS has no `due_date` field, so the
label is derived from data it does have: a sprint is *delayed* when ≥30% of
its issues were unresolved at sprint end. Eligible sprints: CLOSED, with an
end date, ≥15 issues → **987 sprints, 31 projects, 58.8% positive rate**.

**Point-in-time reconstruction.** Every issue in an archival dataset is long
since resolved, so current status cannot be used directly — that leaks the
future. Each task's state is reconstructed *as of sprint end*, and
`GraphMetrics` is evaluated with `now = sprint_end + 1 day`.

**Split discipline.** A fixed, project-level split (`tawos_split.json`):
9 projects / 717 sprints for tuning, **22 projects / 270 sprints held out**.
Splitting by project (not sprint) prevents a team's Jira conventions leaking
across the boundary. The held-out set was evaluated **once**.

#### Result on all 987 sprints (default, untuned parameters)

| | GraphMetrics | Baseline (story-point median) |
|---|---|---|
| Precision | 0.630 | 0.545 |
| Recall | **1.000** | 0.386 |
| F1 | **0.773** | 0.452 |
| Accuracy | 0.655 | 0.450 |
| AUC-ROC | 0.581 | — |

#### Held-out result (270 sprints, 22 unseen projects) — the headline number

| | F1 | Precision | Recall |
|---|---|---|---|
| **Deterministic single-signal rule (untuned)** | **0.712** | 0.552 | **1.000** |
| Tuned composite logistic model | 0.593 | 0.620 | 0.568 |

**The system flags every delayed sprint (recall 1.00) at the cost of
over-flagging roughly half the on-time ones.** After the deadline that recall is
structural — the label and the rule test the same condition — so read it as the
operating point rather than as skill; the mid-sprint numbers below are the
predictive ones. It is a high-sensitivity early warning, not a precise classifier,
which suits a project manager who can dismiss a false alarm cheaply.

**Mid-sprint, on the same 270 held-out sprints:** F1 0.706 (precision 0.581,
recall 0.902) at the halfway point and 0.756 at three-quarters, against 0.657
for flagging every sprint — differences of +0.050, 95% CI [+0.006, +0.094] and
+0.099, [+0.049, +0.148], both *p* < 0.001. AUC 0.792 and 0.874; a simple
open-work-share baseline ranks as well (0.802, 0.881), so the contribution is the
early, evidence-carrying warning rather than better ranking.

### 10.5 Three attempts to improve it — all negative results

Reported because negative results are results, and because they establish
that the simple rule is not leaving accuracy on the table.

1. **Threshold sweep** (`tawos_tune.py`) — *provably inert*. Every value from
   0.05 to 0.50 gave byte-identical output. Cause: with one shared sprint-end
   due date, `overdue_ratio` is always exactly 0.0 or 1.0, so no threshold in
   (0,1) can change any classification.
2. **Individualized per-task due dates** (`tawos_tune2.py`) — derived from
   tuning-set cycle time (2.96 days/story-point). This *did* un-collapse the
   signal (median ratio 0.76, 521/717 sprints intermediate) but **lowered AUC
   0.581 → 0.531**. Story points are too noisy a duration proxy.
3. **Composite logistic regression** (`tawos_composite.py`) over four live
   features, 3-fold group CV by project. Won on tuning data
   (**CV F1 0.816, AUC 0.887**) and **lost on held-out data (F1 0.593)**.
   Cause: the largest-magnitude weight fell on `idle_member_ratio`, which is
   *mechanically* coupled to the label (resolved work → zero open load → high
   idle) rather than independently predictive; its calibration is
   team-specific and did not transfer. The AUC collapse 0.887 → 0.658 is the
   signature of fitting project-specific structure.

**Conclusion:** the tuned model's advantage did not cross the project
boundary — CV F1 0.816 fell to 0.593, and a paired test cannot separate it from
the zero-parameter rule (exact McNemar *p* = 0.78). Added complexity bought no
measurable accuracy here, and it cost the explanation.

### 10.6 Threats to validity
- **Label is a proxy.** TAWOS lacks due dates; "≥30% unresolved at sprint end"
  is a defensible but not canonical definition of a delayed sprint.
- **Structural signals are dead in this reconstruction.** SPOF, dependency
  cycles, and coordination findings are ~0% non-zero, because issue links span
  a project's whole history and rarely fall inside one sprint window. The
  real-world result therefore evaluates *one* of six risk types (delay); the
  other five are validated only synthetically.
- **`blocked_ratio` never fires** — TAWOS's status vocabulary
  (To Do / In Progress / Done) contains no blocked state.
- **AUC is weak by construction** in the sprint-level setup, since all tasks in
  a reconstructed sprint share a deadline.
- **No live-LLM metrics.** Schema-validity rate and fallback-vs-LLM agreement
  (Cohen's κ) require a `GROQ_API_KEY` and are unmeasured; all results above
  are from the deterministic path.

### 10.7 Reproduction
```bash
cd ai-service
python -m eval.run_eval              # synthetic detection, tokens, latency, grounding
python -m eval.boundary_eval         # threshold-boundary sensitivity
python -m eval.datasets.tawos_load   # TAWOS .sql -> SQLite (one pass, ~4.3GB)
python -m eval.datasets.tawos_split  # fixed project-level split
python -m eval.datasets.tawos_score  # all-987-sprint result
python -m eval.datasets.tawos_holdout_eval   # the one-shot held-out number
```

**Citation required if used:** Tawosi, Al-Subaihin, Moussa & Sarro,
*A Versatile Dataset of Agile Open Source Software Projects*, MSR 2022,
doi:10.1145/3524842.3528029.

## 11. Future Research
- LangGraph workflows; vector embeddings for memory; fine-tuned Llama; causal inference; counterfactual recs; human-AI handoff patterns; transfer learning; multi-modal (code/diagrams/voice)
- Scale targets: 10K users, 1K orgs, <30s full analysis, sub-sec p95 API

## 12. Quick Start
```bash
git clone <url> && cd teamsync-ai
cp .env.example .env  # add GROQ_API_KEY
make up && make db-seed
# Frontend: localhost:3000 | Core API: localhost:8000/docs | AI: localhost:8001/docs
```

## 13. Docs Reference
`docs/architecture.md`, `agent-design.md`, `database.md`, `api.md`, `deployment.md`, `testing.md`, `demo-flow.md`

---
*MIT License. Groq, LangGraph, shadcn/ui, FastAPI, SQLAlchemy, Pydantic, Next.js, TanStack Query.*

## 14. Research Paper Template - Section Mapping

Use this to prompt the AI for each paper section. Replace `[...]` with your actual data.

### Title & Abstract
> "Write a 200-word abstract for a paper titled '[Your Title]' describing TeamSync AI: an explainable multi-agent platform predicting team coordination failures via 7 specialist agents + coordinator, with evidence-based recommendations, unified intelligence index, and rule-based LLM fallbacks. Mention: FastAPI/Next.js stack, Groq Llama 3.1, 6 risk types, multi-tenancy, real-time WebSocket, Celery background analysis."

### 1. Introduction (1-1.5 pages)
> "Write Introduction covering: (a) Problem - late risk detection, opaque tools, data silos in PM; (b) Gap - existing tools (Jira/Linear/Asana) lack predictive explainable AI; (c) Our approach - multi-agent decomposition, XAI by design, intelligence index; (d) Contributions - [list 4-5 from Section 8]; (e) Paper structure."

### 2. Related Work (1-2 pages)
> "Create Related Work table comparing TeamSync AI vs: (1) Traditional PM tools (Jira, Linear, Asana, Monday.com) - columns: Predictive AI, Explainability, Multi-agent, Real-time, Multi-tenancy; (2) Academic systems - PlanFormer, AgentBench, AutoGPT, MetaGPT, ChatDev - same columns; (3) XAI in SE - SHAP/LIME for defect prediction, explainable effort estimation. Highlight our unique combo: specialist agents + structured evidence + fallback + unified index."

### 3. System Architecture (1.5-2 pages)
> "Describe architecture from Section 2-3. Include: (a) Service diagram (text description fine); (b) Data flow: Frontend→Core API→AI Service→Groq, async via Celery; (c) Multi-tenancy model; (d) WebSocket real-time layer; (e) Deployment topology. Reference Section 2 tables."

### 4. Multi-Agent Design (2-3 pages) **CORE CONTRIBUTION**
> "Detail agent pipeline from Section 4 & 6. For each of 7 specialists + coordinator + review trio: (a) Input/output schema (ref Section 4.3); (b) System prompt strategy (planning vs progress vs meeting etc.); (c) Risk types detected; (d) Fallback algorithm (Section 4.5); (e) Coordinator orchestration pseudo-code (Section 4.6); (f) Review trio consensus mechanism. Include AgentOutput schema diagram."

### 5. Explainability & Intelligence Index (1-1.5 pages)
> "Explain XAI design: (a) Evidence chains - every signal/rec has source_id, excerpt, relevance; (b) Confidence propagation - signal→agent→overall; (c) Fallback transparency - metadata.fallback flag; (d) Team Intelligence Index formula (Section 4.7), weight justification, tier thresholds. Discuss why schema-enforced JSON > free-text."

### 6. Implementation (1 page)
> "Summarize Section 3, 5, 7: (a) Backend - FastAPI, SQLAlchemy 2.0, asyncpg, RBAC, Alembic; (b) AI Service - Groq client, structured output, validator; (c) Frontend - Next.js 14, TanStack Query, Socket.io, Kanban; (d) Database - 15 tables, indexing strategy; (e) Infrastructure - Docker Compose, K8s, Celery beat. Mention LOC (~21K)."

### 7. Evaluation (2-3 pages) — **DATA AVAILABLE, see Section 10**
> "Write the Evaluation section using the measured results in Section 10. Structure:
> (a) **Experimental Setup** — TAWOS dataset (458,232 Jira issues, 39 projects, MSR 2022, Apache 2.0); sprint-level delay task; the ≥30%-unresolved label and why a proxy was needed; point-in-time reconstruction to prevent future leakage; fixed project-level 717/270 split.
> (b) **Baselines** — story-point-median heuristic (F1 0.452); and the tuned composite model as an upper-complexity comparison.
> (c) **Metrics** — held-out F1 0.712 / precision 0.552 / recall 1.000; all-987-sprint F1 0.773; token cost 1.47× growth for 154× project size; latency p50 <15ms; grounding 200/200.
> (d) **Negative results** — Section 10.5's three failed improvement attempts; emphasize that the zero-parameter explainable rule *beat* the learned composite on held-out data (0.712 vs 0.593), and why (idle_member_ratio is mechanically coupled to the label, doesn't transfer across teams).
> (e) **Threats to validity** — reproduce Section 10.6 honestly: proxy label, five of six risk types validated only synthetically, no live-LLM metrics.
>
> Tone: report the negative results prominently rather than burying them. The strongest claim available is *'a simple, explainable, zero-parameter graph rule matches a tuned learned model on unseen projects, and warns halfway through a sprint rather than after it'* — do not overclaim beyond that, and avoid the word 'beats': the paired test cannot separate the two."

### 8. Discussion (1 page)
> "Cover: (a) Limitations - LLM cost/latency, fallback quality ceiling, 6 risk types may not generalize, no code analysis agent yet; (b) Threats to validity - synthetic data, single LLM provider, no longitudinal study; (c) Generalizability - other domains (sales, support, research); (d) Ethics - surveillance concerns, bias in risk scores, data privacy."

### 9. Future Work (0.5 page)
> "Expand Section 11: LangGraph workflows, vector memory, fine-tuning, causal inference, counterfactuals, human-AI handoff, transfer learning, multi-modal. Prioritize 2-3 with strongest research angle."

### 10. Conclusion (0.5 page)
> "Restate contributions, impact, one-sentence takeaway."

---

### Prompting Tips for Best Results
1. **Feed this file + the template section** to the AI in one context
2. **For each section**, use the prompt above + add: "Use technical details from the provided document. Write in [IEEE/ACM/Elsevier] style. Target [8/10/12] pages."
3. **Iterate**: "Expand Section 4 with more prompt engineering details", "Add Table 2 comparing fallback vs LLM accuracy"
4. **Figures**: Ask AI to generate Mermaid diagrams for architecture, agent pipeline, data flow
5. **Tables**: Request LaTeX/Markdown tables for related work, ablation, metrics

### Minimal Data You Should Add Before Generating
| Needed | Example |
|--------|---------|
| Evaluation metrics | "Risk F1: delay=0.78, coordination=0.72, workload=0.81..." |
| Latency numbers | "Full pipeline: 18.3s avg (LLM 12.1s, fallback 0.8s)" |
| Fallback rate | "12% of runs use fallback (Groq timeout/quota)" |
| User study | "5 PMs rated recommendations 4.2/5 usefulness" |
| Baseline comparison | "Single-prompt LLM: 0.61 F1 vs our 0.74" |
| Hardware | "Groq API, 8-core CPU, 16GB RAM, no GPU" |

Without these, the AI will write a **systems description paper** (acceptable for some venues). With them, it becomes an **empirical research paper**.
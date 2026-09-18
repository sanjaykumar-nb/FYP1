# TeamSync AI: Explainable, Graph-Grounded Multi-Agent Project Intelligence

A structured research reference — problem, proposed solution, architecture, features, novelty,
and evaluation, in that order. Every number in this document is measured and reproducible
(commands in §8); nothing is estimated.

---

## 1. Problem Statement

Teams using conventional project-management tools (Jira, Linear, Asana, Monday.com) run into
four compounding failures:

1. **Risk is detected late.** Coordination breakdowns — a silently overloaded engineer, a single
   point of failure, a critical-path task slipping — are visible only after they've already caused
   a delay. Tools show current state, not risk trajectory.
2. **Warnings are opaque.** When a tool does flag something "at risk," it rarely shows *which
   evidence* produced that verdict, so a manager can't act on it or challenge it.
3. **Signals are siloed.** Task status, meeting outcomes, and communication patterns live in
   disconnected views, so no single signal reveals a cross-cutting risk (e.g. "the one person who
   understands this component is also unresponsive and on the critical path").
4. **AI-based fixes introduce new problems.** Feeding raw project data into an LLM to find
   problems is expensive (cost scales with project size), non-deterministic (same input can yield
   different verdicts), and prone to hallucinated justifications with no way to check them.

**The question this project answers:** can a project-intelligence system detect coordination risk
early, explain it with *verifiable* evidence, and stay cheap enough to run continuously — without
trading away accuracy for that cheapness?

---

## 2. Proposed Solution

### 2.1 Summary

Don't ask an LLM to *find* risk in raw project data. Instead:

1. Compile the project's current state into a **typed knowledge graph** (people, tasks,
   milestones, dependencies, comments, projects — all already in the product's own data).
2. Compute all risk as **deterministic graph algorithms** (critical path, articulation points,
   weighted degree, community structure) — zero LLM tokens, zero randomness.
3. For each computed anomaly, extract a small **witness subgraph** — just the nodes actually
   relevant to that one finding.
4. Give the LLM *only* that witness subgraph and ask it to **narrate** the finding in plain
   language, citing node ids it was shown.
5. **Mechanically check** every citation against the witness subgraph after generation; discard
   anything that doesn't resolve to a real node.
6. Every agent also has a rule-based fallback with an identical output schema, so the system
   produces a complete result even with no LLM available.

This is the inverse of the typical "LLM finds the problem" architecture: **the LLM never sees or
judges the raw dataset — it only explains an already-computed, already-verified fact.**

### 2.2 Why this solves each part of the problem

| Problem | How the solution addresses it |
|---|---|
| Late detection | Graph algorithms make risk cheap enough to compute on every change, not just a periodic report |
| Opaque warnings | Every finding is a citation-carrying, evidence-linked, mechanically checkable object |
| Siloed signals | One graph unifies task, people, dependency, and comment data into a single queryable structure |
| Expensive/unreliable LLM use | The LLM only narrates a bounded witness subgraph, not the full dataset — cost stops scaling with project size, and the numeric answer never depends on the LLM at all |

---

## 3. Architecture — How It Actually Solves the Problem

### 3.1 Service topology

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Frontend   │ ───▶ │  Core API   │ ───▶ │ PostgreSQL  │
│  (Next.js)  │      │  (FastAPI)  │      │  (primary)  │
└─────────────┘      └──────┬──────┘      └─────────────┘
                             │
                             ▼
                      ┌─────────────┐        ┌─────────────┐
                      │ AI Service  │        │    Redis    │
                      │  (FastAPI)  │        │(cache/queue)│
                      └──────┬──────┘        └──────┬──────┘
                             │                       │
                             ▼                       ▼
                      ┌─────────────┐        ┌─────────────┐
                      │  Groq API   │        │   Celery    │
                      │ (Llama 3.x) │        │  Workers    │
                      └─────────────┘        └─────────────┘
```

### 3.2 The analysis pipeline, step by step

> **Figure 1** (`ai-service/eval/figures/fig1_architecture.svg`) draws this: the deterministic,
> zero-token core; the bounded narration layer; and the single boundary the witness subgraph
> crosses.


```
1. Postgres → ProjectSnapshot           (existing task/person/dependency/comment rows)
2. ProjectSnapshot → GraphBuilder       → ProjectGraph (NetworkX, in-memory, rebuilt per analysis)
3. ProjectGraph → GraphMetrics          → 6 risk-type findings   [0 LLM tokens, deterministic]
4. Each finding  → SubgraphSelector     → witness subgraph (bounded k-hop neighborhood, k=1)
5. Witness subgraph → Specialist agent  → natural-language explanation + cited evidence
6. Agent output → drop_ungrounded()     → strip any citation not in the witness subgraph
7. Risk agent aggregates the 6 graph scores → Recommendation agent proposes prioritized actions
8. Persist full AgentRun (outputs + risk scores + witness subgraph) → readable back via API
```

Steps 1–3 and 7 involve **no LLM call at all** — risk *scores* are always deterministic. Only
steps 5 (narration) touch the LLM, and only on a small, bounded slice of the graph.

### 3.3 Knowledge graph schema

**Nodes:** `Person`, `Task`, `Milestone`, `Project`, `Component`.

**Edges** (all derived from data the product already stores — no new collection required):

| Edge | Derived from |
|---|---|
| `Person -[ASSIGNED_TO {points}]-> Task` | task assignee + story points |
| `Person -[REPORTED]-> Task` | task reporter |
| `Task -[BLOCKS]-> Task` | task dependency |
| `Task -[SUBTASK_OF]-> Task` | parent task |
| `Task -[PART_OF]-> Milestone` | milestone link |
| `Person -[COMMENTED_ON]-> Task` | task comments |
| `Person -[MEMBER_OF]-> Project` | project membership |
| `Task -[TOUCHES]-> Component` | milestone-as-component proxy (MVP) |
| `Person -[KNOWS {depth}]-> Component` | `ASSIGNED_TO` ∘ `TOUCHES` |

### 3.4 The six risk types as graph algorithms

| Risk type | Graph computation |
|---|---|
| Dependency / critical path | Longest path through the `BLOCKS` DAG |
| Dependency concentration | Betweenness centrality of task nodes |
| Knowledge / single point of failure (SPOF) | Articulation points in the Person↔Component projection |
| Workload | Weighted degree of `Person` over `ASSIGNED_TO` (weight = story points) |
| Coordination | Community structure over the collaboration projection |
| Silent member | `COMMENTED_ON` degree ÷ `ASSIGNED_TO` degree |
| Delay | Critical-path tasks still open past their due date |

None of these require the LLM to "decide" anything — they are computed exactly, every time, from
the same input.

### 3.5 Multi-agent orchestration

**Coordinator → specialist agents (parallel) → Risk aggregator → Recommendation generator.**

| Agent | Reads | Produces |
|---|---|---|
| Planning | Milestones, capacity, graph metrics | Sprint readiness, feasibility, capacity gaps |
| Progress | Tasks, velocity, graph metrics | Velocity trend, forecast, stalled work |
| Workload | Assignments, graph metrics | Overload/underload, SPOFs, dependency concentration |
| Risk | The 6 graph-computed scores | Aggregated risk scores + evidence |
| Recommendation | Risk output + specialist outputs | Prioritized, evidence-linked actions |

Every agent shares one output schema:

```python
AgentOutput:
    summary, risk_level[low/medium/high/critical], confidence[0-1],
    signals[{name, value, weight}],
    evidence[{source, reference_id, excerpt, relevance}],
    recommendations[{type, title, description, reasoning, priority, confidence}],
    next_action, metadata
```

If the LLM is unavailable or fails, every agent falls back to an independent rule-based
implementation returning the **same schema** — the pipeline degrades gracefully instead of
failing.

---

## 4. Novelty — What Is Actually New Here

This is the core research contribution. Four claims, each independently testable.

### Novelty 1 — Graph-Grounded Agent Prompting

> Project state is compiled into a typed knowledge graph. Coordination risk is computed as a
> **deterministic graph invariant**, not inferred by a language model. The LLM receives only a
> single computed finding plus its minimal witness subgraph, and is required to cite node ids
> drawn from it.

This inverts the standard "LLM finds the problem" pattern. It is the reason the next three
properties are achievable at all.

### Novelty 2 — Prompt cost is O(anomalies), not O(project size)

Because the LLM only ever sees a bounded witness subgraph around an anomaly — never the full
dataset — prompt size stops scaling with how large the project is. **Measured:** 266 → 390 tokens
for a 154× increase in project size (13 → 2,003 tasks): a 1.47× growth for a 154× size increase.
Against the naive "stringify the whole dataset into the prompt" baseline this project started
from, that's a **99.8% (487×) token reduction** at 2,003 tasks. This is what makes continuous,
per-change analysis economically viable instead of a periodic expensive report.

**And the saving does not cost accuracy.** A head-to-head ablation (§6.5) scores both
architectures on identical scenarios against identical ground truth: the graph path reaches
F1 = 1.000, the naive full-dataset-into-the-prompt path F1 = 0.947 — identical on five of six
risk types, with the graph ahead on the sixth. The comparison is deliberately stacked in the
naive path's favour (tiny projects, full context in one call, good-faith prompt, lenient
parsing), so this is a floor on the graph path's relative standing, not a ceiling. The claim
worth making is precise: graph-grounding is *no worse* on detection while being ~487× cheaper at
scale — not that naive prompting cannot detect risk (on small projects, it detects it quite
well).

### Novelty 3 — Hallucinated evidence is mechanically detectable, not just discouraged

Most "explainable AI" systems ask the LLM nicely to cite sources and hope. Here, every citation is
checked after generation against the concrete, bounded set of node ids in the witness subgraph;
anything that doesn't resolve is discarded. **Measured:** 200/200 fabricated references correctly
stripped. This converts "the model was told to cite evidence" into "every surviving citation is
verifiably real."

### Novelty 4 — A tuned learned model's advantage did not survive unseen projects

Rather than reporting only favorable numbers, three separate attempts to improve accuracy with
more sophisticated methods (threshold tuning, individualized due-date estimation, a trained
logistic-regression composite score) were tried against a real-world dataset — and **all three
failed or backfired** on held-out projects (§6.7). The logistic composite reached cross-validated
F1 0.816 on the tuning projects and fell to **0.593** on 22 projects it had not seen, where the
untuned graph rule scored **0.712**. A paired test on those same sprints cannot separate the two
(exact McNemar *p* = 0.78; bootstrap F1 difference +0.119, 95% CI [−0.025, +0.291]), so the claim
is not that the rule predicts better. It is that the complexity bought no measurable accuracy
across project boundaries and cost the explanation — and that both approaches beat flagging every
sprint, the rule by F1 +0.055, 95% CI [+0.030, +0.080], *p* < 0.001.

### Novelty 5 — The same graph warns mid-sprint, while the plan can still change

Projecting the graph forward from the work completed so far flags sprints that will finish late
**halfway through**, rather than reporting them afterwards: **AUC 0.792 at the 50% checkpoint and
0.874 at 75%** on the 270 held-out sprints, with F1 0.706 and 0.756 against 0.657 for flagging
every sprint (+0.050, 95% CI [+0.006, +0.094]; +0.099, [+0.049, +0.148]; both *p* < 0.001). Stated
plainly, the projection does not *rank* better than counting the share of work still open (AUC
0.802 and 0.881); what it adds is that the warning arrives early and carries the same verifiable
evidence as every other finding (§6.3).

**One-sentence summary of the novelty, for an abstract:** *risk detection can be made both cheap
(graph-computed, O(anomalies) prompt cost) and trustworthy (mechanically grounded evidence)
without losing accuracy to a more complex learned model that did not generalise — and the same
graph warns mid-sprint, while the plan can still change.*

---

## 5. Features

### Core product
- Organization-based multi-tenancy; JWT auth with refresh rotation; role-scoped access.
- Projects with milestones and computed health/risk scores.
- Kanban board: drag-and-drop, dependencies, subtasks, comments, status workflow (Backlog →
  Planned → In Progress → Blocked → Review → Done).
- Real-time updates via WebSocket (task changes, risk changes, recommendations).

### AI intelligence layer
- Five active specialist agents (Planning, Progress, Workload, Risk, Recommendation) covering six
  risk types, computed from data the product already owns.
- Deterministic, zero-token graph-based risk scoring, with optional LLM narration layered on top.
- Rule-based fallback for every agent — the pipeline is fully functional with no LLM API key.
- Mechanically enforced evidence grounding on every recommendation.
- Full auditability: every analysis run persists its specialist outputs, risk scores, and the
  exact witness subgraph used to produce them.
- Real cycle detection on task dependencies (a correctness fix that fell directly out of having a
  graph — the previous check only caught direct self-loops, not multi-hop cycles).

### Designed but deferred (explicit scope boundary, not a hidden gap)
- Meeting Intelligence, Communication Intelligence (need transcript/chat data sources not yet in
  the product).
- Professional Review Trio (multi-agent proposal review with consensus).
- Organizational Memory / RAG, Team Intelligence Index (composite weighted score).
- Fine-grained RBAC enforcement, persistent graph storage (Neo4j).

---

## 6. Evaluation — Metrics, Values, and What They Mean

### 6.1 Synthetic correctness check

180 generated scenarios (90 positive / 90 negative, 30 per risk type), anomaly injected
deterministically so ground truth is known by construction.

| Metric | Value |
|---|---|
| Precision / Recall / F1 / Accuracy | 1.00 / 1.00 / 1.00 / 1.00 |
| Stability across 4 more seeds (1,200 extra trials) | identical |

**This checks implementation correctness, not generalization** — equivalent to "all unit tests
pass." The genuinely falsifiable check is the boundary sweep, verifying each detector flips
exactly at its documented threshold:

| Signal | Documented threshold | Observed flip point |
|---|---|---|
| `overdue_ratio` | 0.10 | exactly 0.10 |
| `silent_ratio` | 0.30 | 0.20 → 0.30 (exact) |
| `workload_skew` | 1.50 | bracketed 1.429 → 1.522 |

### 6.2 Efficiency metrics

> **Figure 2** (`fig2_token_scaling.svg`) plots this result on log-log axes.


| Metric | Value |
|---|---|
| Prompt tokens, 13 → 2,003 tasks | 266 → 390 (1.47× for 154× size growth) |
| Prompt tokens vs. pre-graph baseline, 2,003 tasks | 189,834 → 390 (99.8% reduction, 487×) |
| Deterministic pipeline latency (203 tasks, n=50) | p50 4.8–11.0 ms, p95 6.1–13.4 ms |
| Evidence-grounding enforcement | 200/200 fabricated references stripped |

### 6.3 Real-world evaluation

**Dataset:** TAWOS (Tawosi, Al-Subaihin, Moussa & Sarro, MSR 2022), Apache 2.0 — 458,232 Jira
issues, 39 open-source projects, 12 public Jira repositories.

**Where and how it's used:** loaded via a purpose-built mysqldump parser (0 parse errors across
the full 4.3 GB dump, row counts reconciled exactly against published totals), then used for
**sprint-level delay prediction**. TAWOS has no `due_date` field, so the label is derived from
data it does have: a sprint is *delayed* when ≥30% of its issues were unresolved at sprint end.
Each task's state is reconstructed *as of sprint end* (point-in-time reconstruction) to avoid
leaking future/resolved status into the label. Eligible sprints (CLOSED, has end date, ≥15
issues): **987 sprints, 31 projects, 58.8% positive rate.**

**Split:** fixed, project-level — 9 projects / 717 sprints for tuning, **22 projects / 270
sprints held out**, zero overlap, evaluated once.

#### All-987-sprint result (default, untuned parameters)

| Metric | GraphMetrics | Baseline (story-point median) |
|---|---|---|
| Precision | 0.630 | 0.545 |
| Recall | 1.000 | 0.386 |
| F1 | 0.773 | 0.452 |
| Accuracy | 0.655 | 0.450 |
| AUC-ROC | 0.581 | — |

#### Mid-sprint result (270 held-out sprints) — the headline number

Each sprint is rebuilt as it stood at a checkpoint — only issues created by then exist, only those
resolved by then are done — and the system projects the share of scope still unfinished at the
deadline, raising a delay risk from the severity cut-offs already used elsewhere. Checkpoints,
prediction and cut-offs were fixed before the held-out projects were touched; nothing was tuned.

| Checkpoint | Predictor | Precision | Recall | F1 | AUC |
|---|---|---|---|---|---|
| **50%** | Delay risk ≠ low | 0.581 | 0.902 | **0.706** | **0.792** |
| 50% | Flag every sprint | 0.489 | 1.000 | 0.657 | — |
| **75%** | Delay risk ≠ low | 0.623 | 0.962 | **0.756** | **0.874** |
| 75% | Delay risk high or worse | 0.719 | 0.909 | **0.803** | — |
| 75% | Flag every sprint | 0.489 | 1.000 | 0.657 | — |

Paired against flagging every sprint (cluster bootstrap by project, exact McNemar): **+0.050 F1**,
95% CI [+0.006, +0.094] at 50%, and **+0.099**, [+0.049, +0.148] at 75%; both *p* < 0.001. A
simple open-work-share baseline ranks the same sprints as well (AUC 0.802 and 0.881), so the
contribution is the early, explained warning rather than superior ranking.

#### Sprint-end result (270 sprints, 22 unseen projects) — sanity check

> **Figure 3** (`fig3_holdout_tawos.svg`) charts precision/recall/F1 for all three approaches.


| Model | F1 | Precision | Recall |
|---|---|---|---|
| **Deterministic single-signal rule (untuned)** | **0.712** | 0.552 | **1.000** |
| Tuned composite logistic regression | 0.593 | 0.620 | 0.568 |

**Interpretation:** the system flags every delayed sprint (recall 1.00) at the cost of
over-flagging roughly half the on-time ones. At sprint end that recall is guaranteed by the label
definition — a delayed sprint is one with work unfinished past the due date, which is the condition
the rule tests — so it demonstrates the operating point, not predictive skill. The mid-sprint
result above is where recall (0.90 halfway through) carries information.

### 6.4 Live-LLM narration layer — schema validity & LLM-vs-fallback agreement

Every result above the (§6.1–6.3) is from the **deterministic path only** — by design, since risk
*scores* never depend on the LLM. This subsection closes the two metrics that specifically
require a live model call: does the LLM's raw JSON response actually validate, and does its
narrated `risk_level` agree with the deterministic fallback's verdict on the same input?

**Method** ([`ai-service/eval/live_llm_eval.py`](ai-service/eval/live_llm_eval.py)): the real
production agents (`PlanningAgent`, `ProgressAgent`, `WorkloadIntelligenceAgent`) and the real
graph pipeline were run against synthetic scenarios through a live Groq endpoint
(`openai/gpt-oss-120b` — the Llama models originally targeted have since been decommissioned by
Groq). A wrapper around the LLM client recorded, per call, whether the raw response passed schema
validation and whether the pipeline fell back to the rule-based path. Three runs were made,
widening the sample and fixing issues found along the way:

| Run | Scenarios | Calls | `max_tokens` | Pacing | Schema-validity | Fallback rate | κ (n) |
|---|---|---|---|---|---|---|---|
| v1 | 18 | 54 | 600 | 4s | 27.8% | 72.2% | 0.35 (15) |
| v2 | 18 | 54 | 2000 | 18s | 61.1% | 38.9% | 0.84 (33) |
| **v3 (reported, all 6 risk types)** | 30 | 90 | 2000 | 20s + real 429 backoff | **41.1%** | 58.9% | **0.95 (37)** |

**v1 → v2 diagnosis:** `openai/gpt-oss-120b` is a reasoning model — a portion of `max_tokens` is
consumed by a hidden reasoning trace before the JSON answer is emitted. At 600 tokens several
responses were truncated mid-object (observed error: `"Missing required field: next_action"`).
Raising the budget to 2000 tokens resolved this class of failure.

**v2 → v3:** the sample was widened to 5 scenarios × all 6 risk types × 3 agents (90 calls,
vs. 18 scenarios covering only 3 risk types in v1/v2), and the client was changed to retry a 429
with real backoff (30s → 45s → 60s) instead of immediately recording it as a fallback outcome —
production's own built-in retry has no delay, which is useless against a still-active rate limit.
Even with backoff, this account's real sustained throughput proved far below its advertised
tokens/min limit and rate-limiting still dominates the failure count; the schema-validity rate is
correspondingly lower than v2's (41.1% vs 61.1%) simply because more of the 90 attempts landed in
a throttled window, not because the model got worse — see the corrected number below.

**The headline result — Cohen's κ = 0.95 (n=37), across all 6 risk types.** "Almost perfect"
agreement (Landis–Koch scale) between the LLM's narrated `risk_level` and the deterministic
fallback's verdict on identical input, now measured across the full risk taxonomy rather than 3
of 6 types:

| Risk type | n | κ |
|---|---|---|
| dependency | 14 | 1.00 |
| knowledge | 12 | 0.86 |
| workload | 8 | 1.00 |
| coordination | 1 | 1.00 |
| delay | 1 | 1.00 |
| silent_member | 1 | 1.00 |

Dependency, workload, coordination, delay, and silent_member all show perfect or near-perfect
agreement; knowledge (SPOF) is slightly lower at 0.86 but still "almost perfect." Five of six
categories have thin samples (n≤14, three at n=1) purely because of how much rate-limiting
throttled the total call budget — dependency and knowledge carry essentially all the statistical
weight here. This is direct evidence for the core design claim in §3–4 (the LLM explains an
already-computed finding rather than diverging into its own independent judgment), but the
per-risk-type table should be read as "consistent with the hypothesis," not as six independently
powered results.

**An important correction to the headline schema-validity number.** Of the diagnosed failures in
the final process run, 22 of 24 were HTTP 429 (rate-limit) and only **2 were genuine model
failures** — one confirmed schema-validation error (`"Field 'sprint_readiness' should be
number"` etc. — the Planning agent occasionally emits a wrongly-typed field). That gives two
honestly distinct numbers, as in v2:

| Definition | Value |
|---|---|
| Validity rate over **all** attempted calls (including rate-limit blocks) | **41.1%** (37/90) — measured |
| Validity rate over calls that **actually reached the model** | **54–95%** — bounded, not measured |

The second row is a range because only 24 of the 50 failures were diagnosed individually. If every
undiagnosed failure reached the model, validity is 37/68 = 54%; if none did, 37/39 = 95%. Quoting
"~92%" silently assumes the optimistic extreme. The range closes to a single number with one
re-run that logs every call's error — about an hour on a paid key.

The first is the fair number to quote for "how often does an analysis complete via the LLM path
end-to-end on this account's infrastructure." The second is the fair number for "how often does
the model itself produce a valid response once it actually answers." As in v2, conflating them
overstates or understates depending on which direction it's misquoted.

**Threat to validity specific to this measurement:** single provider, single model, one
rate-limited free-tier API key across all three runs. n=37 is still a modest sample for the
overall κ, and thin per-risk-type samples (as low as n=1) mean the per-risk-type breakdown is
suggestive, not conclusive. This is a first real measurement, strengthened over three iterations,
but still not a stable, repeated-trial estimate — a paid tier or a longer collection window would
be needed to close that gap.

### 6.5 Ablation — does graph-grounding cost detection accuracy?

§6.2 shows the graph architecture is ~487× cheaper in prompt tokens than the naive
"stringify the dataset into the prompt" approach this project started from. That result alone
invites an obvious objection: **did 99.8% fewer tokens buy a quietly worse detector?** This
ablation answers it directly.

**Method** ([`ai-service/eval/ablation_naive_vs_graph.py`](ai-service/eval/ablation_naive_vs_graph.py)):
both architectures are scored on the *same* 36 synthetic scenarios (18 positive / 18 negative,
6 per risk type) against the *same* deterministically-injected ground truth, and their
precision/recall/F1 compared head to head. All 36 naive LLM calls succeeded — no scenario was
dropped, so the comparison is strictly like-for-like.

**The design deliberately favours the naive path**, so that a graph win cannot be dismissed as a
strawman:

1. **Small projects only** (10–20 tasks) — where the naive prompt is most competitive and
   actually affordable. A 2,000-task project would not fit its budget at all.
2. **It receives everything in one call** — tasks, members, milestones, dependencies, comments.
   That is strictly more context than the real pre-graph architecture gave any single agent
   (which fanned partial data across three specialists), and more than the graph path's witness
   subgraph.
3. **Good-faith prompt** — all six risk types are defined explicitly, so the model is never
   guessing at the taxonomy.
4. **Lenient response parsing** — `SPOF`→`knowledge`, `"Silent Member"`→`silent_member`, and
   `{risk: true}` dicts are all accepted. Schema-compliance is measured separately (§6.4);
   penalising it twice here would conflate "can't format JSON" with "can't detect risk."

#### Result

> **Figure 4** (`fig4_ablation.svg`) shows the per-risk-type breakdown.

| | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|
| **Graph architecture** (deterministic, 0 tokens) | **1.000** | 1.000 | **1.000** | **1.000** |
| Naive architecture (full dataset → LLM) | 0.900 | 1.000 | 0.947 | 0.944 |

Per risk type, the two are **identical on five of six** (dependency, knowledge, workload, delay,
silent_member — both F1 = 1.00). The entire gap sits in one category:

| coordination | Precision | Recall | F1 |
|---|---|---|---|
| Graph | 1.00 | 1.00 | 1.00 |
| Naive | 0.60 | 1.00 | 0.75 |

**Conclusion: the token saving does not cost accuracy.** The graph path matches or beats the
naive path on every risk type and wins overall (F1 1.000 vs 0.947). The reviewer objection is
answered — but it should be answered *precisely*, not overstated (below).

#### What this result does **not** show

An honest reading requires three qualifications, one of which corrects an initial misreading of
the raw run log:

- **The naive baseline is not bad.** F1 = 0.947 on small projects with a good-faith prompt is a
  respectable score. An early eyeball of the run log suggested the naive path was "spraying false
  alarms everywhere" — a supplementary analysis of all 99 risk claims it made across the 36
  scenarios showed otherwise: it reports 2.75 risk types per scenario against the graph's 2.42,
  and only **12.1% of its claims were uncorroborated** by the deterministic graph. It
  over-reports, but modestly. The initial impression was wrong and is corrected here rather than
  quietly dropped.
- **The scoring is per-target-risk-type.** Each scenario scores only the dimension its anomaly
  was injected on, so extra risks the naive path reports on *other* dimensions are not counted
  against it. A stricter all-dimensions scoring would likely widen the gap — but ground truth for
  the non-target dimensions is not established by construction, so that stricter number is not
  claimed here.
- **Nothing is shown about naive accuracy at scale.** By design this tests 10–20 task projects.
  Whether the naive path holds F1 ≈ 0.95 at 2,000 tasks is untested — and largely untestable on
  any reasonable budget, which is itself part of the argument for the graph architecture.

**So the honest claim is:** graph-grounding is *no worse* on detection accuracy (marginally
better, 1.000 vs 0.947), while being ~487× cheaper at scale, fully deterministic, and
mechanically grounded. The cost, reproducibility and grounding properties remain the primary
arguments for the architecture; this ablation's contribution is to close off the "you traded
accuracy for tokens" objection, not to claim that naive prompting cannot detect risk.

> **Note on tokens in this experiment.** Mean prompt size here was 1,109 (graph) vs 1,804
> (naive) — a mere 1.6× gap, *not* the headline efficiency result. That is expected and by
> design: these are deliberately tiny projects chosen to give the naive path its best shot. The
> 487× gap in §6.2 appears at 2,003 tasks, where the naive prompt reaches 189,834 tokens. The two
> numbers must not be conflated.

### 6.6 Additional metrics used and what they measure

| Metric | Used for |
|---|---|
| Precision / Recall / F1 | Standard classification quality of the delay-risk detector |
| Accuracy | Overall correctness (less informative here given class imbalance ~59/41) |
| AUC-ROC | Rank-quality of the risk score, independent of any fixed threshold |
| Brier score | Calibration quality of the emitted confidence/probability |
| Point-biserial correlation | Screening which graph features actually correlate with the label before combining them into a composite score |
| Token count | Direct evidence for Novelty 2 |
| Latency (p50/p95) | Justifies synchronous (non-queued) execution |
| Grounding pass rate | Direct evidence for Novelty 3 |

### 6.7 Three attempts to improve accuracy — all negative results

Reported because they establish that the simple rule is not leaving accuracy on the table, and
they are what makes Novelty 4 credible rather than cherry-picked.

1. **Threshold sweep** — provably inert. Every value 0.05–0.50 gave byte-identical output, because
   with one shared sprint-end due date, `overdue_ratio` is always exactly 0.0 or 1.0.
2. **Individualized per-task due dates** (from tuning-set cycle time, 2.96 days/story-point) —
   un-collapsed the signal but **lowered AUC 0.581 → 0.531**; story points are too noisy a duration
   proxy.
3. **Composite logistic regression** over four features, 3-fold group cross-validation by
   project — won on tuning data (CV F1 0.816, AUC 0.887) and **lost on held-out data (F1 0.593)**.
   The dominant weight fell on `idle_member_ratio`, which is mechanically coupled to the label
   rather than independently predictive, and its calibration didn't transfer across teams (AUC
   collapse 0.887 → 0.658 — the signature of overfitting to project-specific structure).

### 6.8 Threats to validity

- The delay label is a proxy (TAWOS has no due dates).
- Structural signals (SPOF, cycles, coordination) are ~0% non-zero in this sprint reconstruction —
  the real-world result validates 1 of 6 risk types directly; the other 5 are validated only
  synthetically (§6.1).
- `blocked_ratio` never fires — TAWOS's status vocabulary has no blocked state.
- AUC is weak by construction at the sprint level, since all tasks in a reconstructed sprint share
  one deadline.
- The mid-sprint projection ranks no better than counting the share of work still open (AUC 0.792
  vs 0.802 at the halfway checkpoint; 0.874 vs 0.881 at three-quarters). Its contribution is the
  explained, integrated early warning, not rank quality.
- Sprint-end recall of 1.00 is structural: the label and the rule test the same condition once the
  deadline has passed. Only the mid-sprint recall is predictive.
- Live-LLM schema validity over calls that reached the model is a 54–95% range, not a number; only
  the end-to-end 41.1% is measured.
- Live-LLM metrics (§6.4) are now measured, but from a single small run on a single rate-limited
  API key against a single model — not a stable, repeated-trial estimate. Treat κ=0.95 (n=37, all
  6 risk types) as a strengthened but still first-pass signal, not a settled number — most of the
  weight comes from 2 of 6 risk types (dependency, knowledge); the other four have n≤14, three at
  n=1.

### 6.9 Independent verification

Every number above was re-audited from scratch before being reported: hand-recomputed confusion
matrices (exact match), confirmed zero project overlap between splits, confirmed the composite
model's normalization stats were frozen from tuning-only fitting, cross-checked sampled
ground-truth labels against raw SQL bypassing the ORM (exact match), verified the AUC and Brier
implementations against brute-force and known-answer cases (exact match), and re-ran both
headline scripts fresh — byte-identical to the originally reported numbers. No discrepancy found.

---

## 7. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind, shadcn/ui, TanStack Query, Socket.io |
| Core backend | FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, JWT auth, Celery, Redis, Alembic |
| AI service | FastAPI, NetworkX (graph engine), Groq client (Llama 3.x) |
| Database | PostgreSQL 16 (prod), SQLite (tests, via dialect-neutral models) |
| Infra | Docker Compose (dev), Kubernetes manifests (prod) |

---

## 8. Reproduction

```bash
cd ai-service
python -m eval.run_eval                     # synthetic detection, tokens, latency, grounding
python -m eval.boundary_eval                 # threshold-boundary sensitivity
python -m eval.datasets.tawos_load           # TAWOS .sql -> SQLite (one pass, ~4.3GB)
python -m eval.datasets.tawos_split          # fixed project-level split
python -m eval.datasets.tawos_score          # all-987-sprint result
python -m eval.datasets.tawos_holdout_eval   # the one-shot held-out number
python -m eval.live_llm_eval                 # live-LLM schema validity + Cohen's kappa (needs GROQ_API_KEY, makes billed calls)
python -m eval.ablation_naive_vs_graph       # naive-vs-graph accuracy ablation (needs GROQ_API_KEY, makes billed calls)
python -m eval.make_figures                  # regenerate all paper figures from the result JSONs (offline)
```

**Citation required if the dataset is used:** Tawosi, V., Al-Subaihin, A., Moussa, R., & Sarro, F.
*A Versatile Dataset of Agile Open Source Software Projects.* MSR 2022. doi:10.1145/3524842.3528029.

---

*License: MIT. Third-party: Groq, NetworkX, shadcn/ui, FastAPI, SQLAlchemy, Pydantic, Next.js,
TAWOS dataset (Apache 2.0, MSR 2022).*

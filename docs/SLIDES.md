# Presentation outline — 14 slides, ~15 minutes

Content for the defence deck: what goes on each slide, what to say, and the number to quote. Build
it in whatever tool you present with. Figures are in `docs/images/` as SVG (and in
`docs/paper_figures/` as PDF for LaTeX); `ai-service/eval/figures/` holds the full set.

Every figure quoted here is traceable to a committed result file — see
[IEEE_PAPER_REPORT.md §13](../IEEE_PAPER_REPORT.md) for the command that reproduces each one.

**Two words to avoid in the room:** *beats* (for the comparison with the learned model — the paired
test returns p = 0.78) and *more accurate* (for the mid-sprint projection — a trivial baseline ranks
as well). Both are easy to say by accident and both invite the question you cannot answer.

---

### 1 · Title

TeamSync AI — Explainable, Graph-Grounded Multi-Agent Project Intelligence. Your name, supervisor,
department, date.

### 2 · The problem *(1 min)*

Four failures, one line each:

- Risk is detected late — tools show state, not trajectory.
- Warnings are opaque — "at risk" with nothing behind it.
- Signals are siloed — no view crosses workload, knowledge and dependencies.
- Bolting on an LLM adds cost that scales with the project, different answers on the same input,
  and justifications nobody can check.

> Say: the fourth one is why this is a research problem and not a feature request.

### 3 · Research question

> *Can a system detect coordination risk early, explain it with verifiable evidence, and stay cheap
> enough to run continuously — without trading away accuracy?*

Leave it on screen for a beat. Every later slide answers one clause of it.

### 4 · Why the obvious approach fails *(1 min)*

The naive design: put the project data in the prompt, ask the model to find the risk. Measured on
this codebase, one analysis of a 200-task project sent **~62,000 tokens**, re-paid on every run,
growing with the project. Non-deterministic, and its reasons cannot be checked.

> Say: this was the starting architecture of this project. The numbers are from measuring it, not
> from arguing against a straw man.

### 5 · The idea *(2 min)* — **the slide that matters**

Three boxes, left to right:

**Compute** — project state → typed knowledge graph → every risk is a graph property. Zero tokens,
deterministic.
**Select** — take the small *witness subgraph* around each finding.
**Explain** — the model sees one finding and that subgraph, and narrates it. It may cite only nodes
from the subgraph; anything else is stripped.

> Say: the language model never decides whether a risk exists. It writes the sentence. That single
> inversion is what makes the next three slides possible.

### 6 · The six risks are graph algorithms

| Risk | Computation |
|---|---|
| Dependency | Critical path through the blocking DAG |
| Knowledge / single point of failure | Articulation points in the person–component graph |
| Workload | Weighted degree over assignments |
| Coordination | Community structure in the collaboration graph |
| Silent member | Comment degree ÷ assignment degree |
| Delay | Projected unfinished share at the deadline |

> Say: none of these needs a model to compute. They need a model to *say* — which is a much smaller
> job, and a checkable one.

### 7 · Two properties follow *(1 min)*

- **Cost tracks anomalies, not project size.** 1.47× the tokens for a project 154× larger
  (13 → 2,003 tasks); **487× cheaper** than naive prompting at 2,003 tasks.
  *Figure: `docs/images/eval-token-scaling.svg`.*
- **Citations are mechanically checked.** 200 fabricated references injected, **200 stripped**.

> Say: "the model was asked to cite evidence" becomes "every citation that survives is real".

### 8 · The product *(1 min)*

Screenshot of the evidence panel on the real Mesos sprint — the findings with their chips.

> Say: this is the same claim at the interface level. Every number on this screen can be traced to
> the issues and people it came from, and the whole thing runs with no API key configured.

### 9 · How it was evaluated

- **TAWOS** — 458,232 real Jira issues, 39 open-source projects (MSR 2022, Apache 2.0).
- Sprint reconstructed **point-in-time**, so no future state leaks into the label.
- **Project-level split**: 9 projects for tuning, **22 held out**, evaluated once.
- Label: a sprint is delayed when ≥30% of its issues are unresolved at sprint end.

> Say: the split is by project, not by sprint, because sprints inside one project share a team and
> a codebase. Splitting by sprint would have flattered every number here.

### 10 · Result — the warning arrives in time *(headline)*

270 held-out sprints, 22 unseen projects:

| Checkpoint | F1 | vs flag-every-sprint | AUC |
|---|---|---|---|
| Halfway | 0.706 | **+0.050** [+0.006, +0.094] | 0.792 |
| Three-quarters | 0.756 | **+0.099** [+0.049, +0.148] | 0.874 |

Both differences: exact McNemar *p* < 0.001.

> Say, before you are asked: the projection does **not** rank better than simply counting the share
> of work still open (0.802 and 0.881). What it adds is that the warning is early and carries its
> evidence. Saying this first is worth more than defending it later.

### 11 · Result — the negative ones

- Threshold sweep: **provably inert** — with one shared deadline the ratio is always 0 or 1.
- Individual due dates from cycle time: **AUC 0.581 → 0.531**.
- Tuned logistic model: CV F1 **0.816** → held-out **0.593**, AUC collapse 0.887 → 0.658.
- The zero-parameter rule scores 0.712 at sprint end — but paired, **McNemar p = 0.78**: the two
  cannot be separated.

> Say: the claim is that added complexity bought no measurable accuracy across project boundaries
> and cost the explanation — not that the simple rule predicts better. Both beat flagging every
> sprint.

### 12 · Engineering

- Three services, 95 + 85 + 61 automated tests, all run in CI on every push (the backend's on both
  SQLite and PostgreSQL) — plus a replay of
  the real sprint that fails the build if the demo stops showing what this deck says it shows.
- Works with no API key; the model is optional.
- Real bugs found by evaluating on real data, listed in the report — e.g. the witness subgraph
  once grew with the project (4.31×, now 1.007×), and the grounding check once treated an empty
  citation list as "allow everything".

> Say: the bug list is in the paper on purpose. It is the difference between a demo and a result.

### 13 · Limitations — say these before you are asked

- Only 1 of 6 risk types is validated on real data; the other five are synthetic only.
- The delay label is a proxy — TAWOS has no due dates.
- Sprint-end recall of 1.00 is **structural**, guaranteed by the label definition at that point.
- Live-LLM schema validity is a **range** (54–95%); only the end-to-end 41.1% is measured.
- **No human evaluation** of whether the explanations are useful — grounding shows the citations
  are real, not that they help.
- Nothing is claimed about the first quarter of a sprint: the pace signal is off by design.

### 14 · Contributions and what's next

**Contributions:** graph-grounded agent prompting · O(anomalies) prompt cost, measured · mechanical
evidence grounding · a pre-registered mid-sprint evaluation on held-out projects, negative results
included.

**Next:** human evaluation of explanation usefulness · meeting and communication intelligence once
a data source exists · longitudinal study.

---

## Backup slides

Keep these after the end; they answer the predictable questions.

| Question you'll get | Slide to have ready |
|---|---|
| "Why not use a graph database?" | NetworkX in memory; projects are hundreds of nodes; Neo4j is a migration path, not a need |
| "What if the LLM is wrong?" | Cohen's κ = 0.95 (n = 37) between the narration and the deterministic verdict — it narrates, it doesn't re-decide |
| "Is the efficiency gain just a smaller prompt?" | The ablation: F1 1.000 vs 0.947 on identical scenarios, so the cheap path is not the weaker one (n = 36, not significant) |
| "How do you know the 487× isn't cherry-picked?" | Token sweep across six project sizes, one script, committed output |
| "Why only one risk type validated?" | Issue links in TAWOS span a project's whole history, so structural signals are ~0% non-zero inside one sprint window |
| "Could a manager game it?" | Yes — anything computed from assignment and comment counts can be gamed; that is why findings cite evidence a human reads, rather than producing a score to optimise |

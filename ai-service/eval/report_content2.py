"""Sections 7-12 of the project report: evaluation, limitations, related work,
paper mapping, reproducibility, and remaining gaps. See report_content.py."""

from __future__ import annotations

from reportlab.platypus import PageBreak, Spacer

from eval.make_report_pdf import P, bullets, callout, figure, tbl


def build_story2(d):
    det, lat, gr = d["det"], d["lat"], d["gr"]
    gm, base, rule, comp = d["gm"], d["base"], d["rule"], d["comp"]
    ag, an, tok, last = d["ag"], d["an"], d["tok"], d["last"]
    a9, hold, abl, live, run = d["a9"], d["hold"], d["abl"], d["live"], d["run"]
    ratio = d["ratio"]
    per = abl["per_risk_type"]

    s = [P("7. Evaluation - All Measured Values", "h1")]

    # ---------------- 7.1 engineering
    s += [P("7.1 Engineering baseline", "h2")]
    s.append(tbl([
        ["Item", "Value"],
        ["Backend tests", "29 / 29 pass"],
        ["AI service tests", "43 / 43 pass (pytest -m mvp)"],
        ["Frontend tests", "27 / 27 pass (vitest)"],
        ["Code size", "approx. 21,000 lines"],
        ["Quality gates", "ruff, mypy, eslint, prettier, tsc"],
    ], [0.3, 0.7]))

    # ---------------- 7.2 synthetic
    s += [P("7.2 Synthetic detection correctness", "h2"),
          P(f"{run['detection']['n_scenarios']} scenarios with the anomaly injected "
            f"deterministically, so the label is known by construction.")]
    s.append(tbl([
        ["TP", "FP", "FN", "TN", "Precision", "Recall", "F1", "Accuracy"],
        [f"{det['tp']}", f"{det['fp']}", f"{det['fn']}", f"{det['tn']}",
         f"**{det['precision']:.2f}**", f"**{det['recall']:.2f}**",
         f"**{det['f1']:.2f}**", f"**{det['accuracy']:.2f}**"],
    ], [0.09, 0.09, 0.09, 0.09, 0.16, 0.16, 0.16, 0.16],
        align_right=[0, 1, 2, 3, 4, 5, 6, 7]))
    s.append(Spacer(1, 5))
    s.append(callout("<b>State this honestly in the paper.</b> For deterministic threshold code on "
                     "unambiguous inputs, 100% is the <i>expected</i> result of correctness - "
                     "equivalent to saying all unit tests pass. It is <b>not</b> evidence of "
                     "generalization, and should not be presented as such. Stability was confirmed "
                     "across 4 further seeds (1,200 additional trials)."))
    s.append(P("The genuinely falsifiable check is the <b>boundary sweep</b>: does each detector flip "
               "exactly at its documented threshold?"))
    s.append(tbl([
        ["Signal", "Documented threshold", "Observed transition"],
        ["overdue_ratio", "0.10", "flips at exactly 0.10"],
        ["silent_ratio", "0.30", "0.20 to 0.30 (exact)"],
        ["workload_skew", "1.50", "bracketed 1.429 to 1.522"],
    ], [0.3, 0.3, 0.4]))

    # ---------------- 7.3 efficiency
    s += [P("7.3 Efficiency - the headline result", "h2"),
          P("Full two-series sweep, identical measurement method for both architectures.")]
    rows = [["Project size (tasks)", "Graph-grounded", "Naive full-dataset", "Ratio"]]
    for r in tok:
        bold = r is last
        f = (lambda v: f"**{v}**") if bold else (lambda v: v)
        rows.append([f(f"{r['tasks']:,}"), f(f"{r['graph']}"), f(f"{r['naive']:,}"),
                     f(f"{r['naive']/r['graph']:.1f}x")])
    s.append(tbl(rows, [0.28, 0.24, 0.24, 0.24], align_right=[0, 1, 2, 3]))
    s.append(figure("fig2_token_scaling.svg",
                    f"Fig. 3. Prompt cost against project size, both axes logarithmic. "
                    f"Witness-subgraph selection holds prompt size effectively constant while the "
                    f"project grows {last['tasks']/tok[0]['tasks']:.0f}x, whereas naive prompting "
                    f"grows linearly to {last['naive']:,} tokens."))
    s.append(tbl([
        ["Derived metric", "Value"],
        ["Token growth vs project-size growth",
         f"**{last['graph']/tok[0]['graph']:.2f}x tokens for "
         f"{last['tasks']/tok[0]['tasks']:.0f}x project size**"],
        [f"Reduction at {last['tasks']:,} tasks",
         f"**{(1 - last['graph']/last['naive'])*100:.1f}% ({ratio:.0f}x)**"],
    ], [0.45, 0.55]))
    s.append(Spacer(1, 7))
    s.append(P(f"<b>Latency</b> of the deterministic path (graph build + metrics + subgraph "
               f"selection; {lat['project_size_tasks']} tasks, n={lat['n_runs']}):"))
    s.append(tbl([
        ["p50", "p95", "mean", "max"],
        [f"{lat['p50_ms']:.2f} ms", f"{lat['p95_ms']:.2f} ms",
         f"{lat['mean_ms']:.2f} ms", f"{lat['max_ms']:.2f} ms"],
    ], [0.25, 0.25, 0.25, 0.25], align_right=[0, 1, 2, 3]))
    s.append(Spacer(1, 5))
    s.append(P("Latency varies with machine load between runs (p50 observed between 4.8 and 11.0 ms "
               "across runs). The defensible claim is single- to low-double-digit milliseconds, "
               "which is what justifies running analysis <b>synchronously</b>, without a queue.", "note"))
    s.append(P(f"<b>Evidence grounding enforcement:</b> "
               f"{gr['fabrications_fully_stripped']}/{gr['n_trials']} fabricated references stripped "
               f"({gr['enforcement_rate']*100:.0f}%)."))

    # ---------------- 7.4 tawos
    s += [PageBreak(), P("7.4 Real-world results - TAWOS", "h2"),
          P(f"<b>All {a9['n_sprints']} sprints</b> (default, untuned parameters):")]
    s.append(tbl([
        ["Metric", "GraphMetrics", "Story-point baseline"],
        ["Precision", f"{gm['precision']:.3f}", f"{base['precision']:.3f}"],
        ["Recall", f"**{gm['recall']:.3f}**", f"{base['recall']:.3f}"],
        ["F1", f"**{gm['f1']:.3f}**", f"{base['f1']:.3f}"],
        ["Accuracy", f"{gm['accuracy']:.3f}", f"{base['accuracy']:.3f}"],
        ["AUC-ROC", f"{a9['graph_metrics_auc']:.3f}", "-"],
        ["Brier score", f"{a9['graph_metrics_brier']:.3f}", "-"],
    ], [0.34, 0.33, 0.33], align_right=[1, 2]))

    s.append(Spacer(1, 8))
    s.append(P(f"<b>Held-out result - {hold['n_sprints']} sprints, {hold['n_projects']} unseen "
               f"projects. This is the headline number.</b>"))
    s.append(tbl([
        ["Model", "Precision", "Recall", "F1", "Accuracy", "AUC"],
        ["**Graph rule (untuned, 0 parameters)**", f"{rule['precision']:.3f}",
         f"**{rule['recall']:.3f}**", f"**{rule['f1']:.3f}**", f"{rule['accuracy']:.3f}", "-"],
        ["Tuned composite logistic model", f"{comp['precision']:.3f}", f"{comp['recall']:.3f}",
         f"{comp['f1']:.3f}", f"{comp['accuracy']:.3f}", f"{comp['auc']:.3f}"],
    ], [0.36, 0.13, 0.12, 0.12, 0.14, 0.13], align_right=[1, 2, 3, 4, 5]))
    s.append(Spacer(1, 5))
    s.append(P(f"Confusion matrices - graph rule: TP {rule['tp']}, FP {rule['fp']}, "
               f"FN <b>{rule['fn']}</b>, TN {rule['tn']}. Composite model: TP {comp['tp']}, "
               f"FP {comp['fp']}, FN {comp['fn']}, TN {comp['tn']}.", "note"))
    s.append(figure("fig3_holdout_tawos.svg",
                    "Fig. 4. Sprint-delay prediction on the held-out TAWOS split. The zero-parameter "
                    "graph rule outperforms a composite logistic model tuned on the other nine "
                    "projects. The story-point baseline is measured on all 987 sprints."))
    s.append(callout(f"<b>Interpretation.</b> The system catches <b>every</b> delayed sprint "
                     f"(recall {rule['recall']:.2f}, FN = {rule['fn']}) while over-flagging roughly "
                     f"half the on-time ones (precision {rule['precision']:.3f}). It is a "
                     f"<b>high-sensitivity early warning</b>, not a precise classifier - the right "
                     f"operating point when a false alarm is cheap to dismiss but a missed one is not."))

    # ---------------- 7.5 negative results
    s += [P("7.5 Negative results - three failed improvement attempts", "h2"),
          P("Reported prominently rather than buried. They establish that the simple rule is not "
            "leaving accuracy on the table, and they are what make the headline claim credible "
            "rather than cherry-picked.")]
    s.append(tbl([
        ["#", "Attempt", "Outcome"],
        ["1", "**Threshold sweep** (0.05 to 0.50)",
         "<b>Provably inert</b> - byte-identical output at every value. With one shared sprint-end "
         "due date, overdue_ratio is always exactly 0.0 or 1.0, so no threshold strictly between "
         "0 and 1 can change any classification."],
        ["2", "**Individualized due dates** from tuning-set cycle time (2.96 days per story point)",
         "Un-collapsed the signal (median ratio 0.76, 521/717 sprints intermediate) but "
         "<b>lowered AUC from 0.581 to 0.531</b>. Story points are too noisy a duration proxy."],
        ["3", "**Composite logistic regression**, four features, 3-fold group CV by project",
         "Won on tuning data (CV F1 <b>0.816</b>, AUC <b>0.887</b>) and <b>lost on held-out data "
         "(F1 0.593)</b>. The dominant weight fell on idle_member_ratio, which is <i>mechanically</i> "
         "coupled to the label rather than independently predictive; its calibration is team-specific "
         "and did not transfer. The AUC collapse from 0.887 to 0.658 is the signature of overfitting "
         "to project-specific structure."],
    ], [0.04, 0.30, 0.66]))
    s.append(Spacer(1, 5))
    s.append(callout("<b>Conclusion.</b> The zero-parameter, fully explainable graph rule outperforms "
                     "the tuned learned model on unseen projects. Added model complexity was not "
                     "merely unhelpful here - it was actively harmful."))

    # ---------------- 7.6 ablation
    s += [PageBreak(), P("7.6 Ablation - does graph-grounding cost accuracy?", "h2"),
          P(f"Both architectures scored on <b>identical</b> scenarios against <b>identical</b> "
            f"injected ground truth (n={abl['n_scenarios']}, 18 positive / 18 negative, six per risk "
            f"type; <b>{abl['n_naive_calls_failed']} failed calls</b>, so the comparison is strictly "
            f"like-for-like).")]
    s.append(tbl([
        ["Architecture", "Precision", "Recall", "F1", "Accuracy"],
        ["**Graph-grounded (0 tokens, deterministic)**", f"**{ag['precision']:.3f}**",
         f"{ag['recall']:.3f}", f"**{ag['f1']:.3f}**", f"**{ag['accuracy']:.3f}**"],
        ["Naive full-dataset prompting", f"{an['precision']:.3f}", f"{an['recall']:.3f}",
         f"{an['f1']:.3f}", f"{an['accuracy']:.3f}"],
    ], [0.40, 0.15, 0.15, 0.15, 0.15], align_right=[1, 2, 3, 4]))
    s.append(figure("fig4_ablation.svg",
                    "Fig. 5. Detection accuracy of the graph architecture against naive "
                    "full-dataset prompting. The two are indistinguishable on five of six risk "
                    "types; the entire gap is coordination."))
    order = ["dependency", "knowledge", "workload", "delay", "silent_member", "coordination"]
    rows = [["Risk type", "Graph F1", "Naive F1", "Naive precision"]]
    for rt in order:
        g, n = per[rt]["graph"], per[rt]["naive"]
        star = rt == "coordination"
        f = (lambda v: f"**{v}**") if star else (lambda v: v)
        rows.append([f(rt), f(f"{g['f1']:.2f}"), f(f"{n['f1']:.2f}"), f(f"{n['precision']:.2f}")])
    s.append(tbl(rows, [0.34, 0.22, 0.22, 0.22], align_right=[1, 2, 3]))
    s.append(Spacer(1, 6))
    s.append(P("<b>The design deliberately favours the naive path</b>, so a graph win cannot be "
               "dismissed as a strawman: small projects (10 to 20 tasks, its best case), full "
               "context delivered in one call, a good-faith prompt defining all six risk types, and "
               "lenient response parsing."))
    s.append(P("<b>What this does not show</b> - three honest qualifications:"))
    s += bullets([
        f"<b>The naive baseline is not bad.</b> F1 {an['f1']:.3f} is respectable. It reports 2.75 "
        f"risk types per scenario against the graph's 2.42, with only <b>12.1%</b> of its claims "
        f"uncorroborated by the deterministic graph. It over-reports, but only modestly.",
        "<b>Scoring is per-target-risk-type</b>, so extra risks reported on other dimensions are not "
        "counted against it. Stricter all-dimension scoring would likely widen the gap, but ground "
        "truth for the non-target dimensions is not established by construction, so it is not claimed.",
        "<b>Nothing is shown about naive accuracy at scale.</b> This tests 10 to 20 task projects by "
        "design. Whether the naive path holds F1 near 0.95 at 2,000 tasks is untested, and largely "
        "untestable on any reasonable budget - which is itself part of the argument.",
    ])
    s.append(callout(f"<b>Token note.</b> Mean prompt size in this ablation was "
                     f"{abl['mean_prompt_tokens']['graph']:.0f} (graph) against "
                     f"{abl['mean_prompt_tokens']['naive']:.0f} (naive) - only "
                     f"{abl['mean_prompt_tokens']['naive']/abl['mean_prompt_tokens']['graph']:.1f}x, "
                     f"and <b>not</b> the headline efficiency result. These are deliberately tiny "
                     f"projects. The {ratio:.0f}x gap appears at {last['tasks']:,} tasks. The two "
                     f"numbers must not be conflated.", accent=None))

    # ---------------- 7.7 live llm
    s += [PageBreak(), P("7.7 Live-LLM metrics - the narration layer", "h2"),
          P(f"Three runs were made; the third is reported. Model: "
            f"<font face='Courier'>{live['model']}</font> (Groq deprecated the Llama models "
            f"originally targeted).")]
    s.append(tbl([
        ["Run", "Scenarios", "Calls", "max_tokens", "Pacing", "Schema validity", "Kappa (n)"],
        ["v1", "18", "54", "600", "4 s", "27.8%", "0.35 (15)"],
        ["v2", "18", "54", "2000", "18 s", "61.1%", "0.84 (33)"],
        ["**v3 (reported)**", f"**{live['n_scenarios']}**", f"**{live['n_agent_calls']}**",
         "2000", "20 s + backoff", f"**{live['schema_validity_rate']*100:.1f}%**",
         f"**{live['cohens_kappa_overall']:.2f} ({live['n_llm_vs_fallback_comparisons']})**"],
    ], [0.17, 0.12, 0.10, 0.13, 0.16, 0.16, 0.16], align_right=[1, 2, 3, 5, 6]))
    s.append(Spacer(1, 6))
    s.append(P(f"<b>Cohen kappa = {live['cohens_kappa_overall']:.4f} "
               f"(n={live['n_llm_vs_fallback_comparisons']})</b> - almost perfect agreement on the "
               f"Landis-Koch scale between the LLM's narrated risk_level and the deterministic "
               f"fallback's verdict on identical input. This is direct evidence for the central "
               f"design claim: <b>the LLM narrates rather than re-decides</b>."))
    krows = [["Risk type", "n", "Kappa"]]
    for rt, v in sorted(live["cohens_kappa_by_risk_type"].items(),
                        key=lambda kv: -kv[1]["n"]):
        krows.append([rt, str(v["n"]), f"{v['kappa']:.2f}"])
    s.append(tbl(krows, [0.5, 0.25, 0.25], align_right=[1, 2]))
    s.append(Spacer(1, 6))
    s.append(P("<b>Schema validity needs two numbers, not one.</b> Of 24 diagnosed failures, "
               "<b>22 were HTTP 429 rate-limits</b> from the free-tier API key - an infrastructure "
               "constraint of the account used, not a property of the model or the pipeline."))
    s.append(tbl([
        ["Definition", "Value"],
        ["Over <b>all</b> attempted calls (including rate-limit blocks)",
         f"{live['schema_validity_rate']*100:.1f}% "
         f"({live['schema_valid_calls']}/{live['n_agent_calls']})"],
        ["Over calls that <b>actually reached the model</b>", "**approx. 92% (37/40)**"],
    ], [0.6, 0.4], align_right=[1]))
    s.append(Spacer(1, 5))
    s.append(P("Quote the first for how often an analysis completes end-to-end on this "
               "infrastructure; quote the second for how often the model produces a valid response. "
               "Conflating them misleads in either direction.", "note"))

    # ---------------- 7.8 glossary
    s += [P("7.8 Metric glossary", "h2")]
    s.append(tbl([
        ["Metric", "What it measures"],
        ["Precision / Recall / F1", "Classification quality of the risk detector"],
        ["Accuracy", "Overall correctness (less informative under the 59/41 class imbalance)"],
        ["AUC-ROC", "Threshold-independent rank quality of the risk score"],
        ["Brier score", "Calibration quality of the emitted confidence"],
        ["Point-biserial correlation", "Feature screening before building the composite model"],
        ["Cohen kappa", "Agreement between LLM narration and the deterministic verdict"],
        ["Token count", "Direct evidence for the O(anomalies) claim"],
        ["Latency p50 / p95", "Justifies synchronous, non-queued execution"],
        ["Grounding rate", "Direct evidence for the mechanical-verification claim"],
    ], [0.3, 0.7]))

    # ---------------- 7.9 verification
    s += [P("7.9 Independent verification", "h2"),
          P("Every number was re-audited from scratch rather than re-quoted:")]
    s += bullets([
        "Confusion-matrix arithmetic recomputed by hand for both models - exact match.",
        "Zero project overlap between splits confirmed; 717 + 270 = 987 partitions cleanly with no "
        "gaps and no case or whitespace bugs.",
        "The composite model's normalization statistics confirmed frozen from tuning-only fitting "
        "and correctly applied, not silently recomputed, on the held-out set.",
        "Five randomly sampled held-out sprints' ground-truth labels cross-checked against "
        "<b>raw SQL</b>, bypassing the ORM entirely - exact match on every sprint.",
        "The AUC implementation verified against a brute-force O(n^2) pairwise comparison plus "
        "three known-answer cases - exact match to full float precision.",
        "The Brier implementation verified against three known-answer edge cases - exact match.",
        "Both headline scripts re-run fresh from a clean state - <b>byte-identical</b> output.",
        "SQLite row counts re-queried directly and matched against TAWOS published totals.",
    ])
    s.append(callout("<b>No discrepancy was found in any check.</b>"))

    # ---------------- 7.10 bugs
    s += [P("7.10 Engineering rigor - defects found and fixed", "h2"),
          P("Useful for a lessons-learned or methodology-credibility paragraph in the paper.")]
    s.append(tbl([
        ["Defect", "Impact"],
        ["Witness subgraph expanded <i>all</i> neighbours of a seed",
         "Prompt size still scaled with project size (4.31x growth); fixed with a per-seed "
         "neighbour cap, reducing growth to <b>1.007x</b>"],
        ["Grounding treated an empty findings list as no filter",
         "Silently allowed every citation through; fixed to distinguish empty from absent"],
        ["Coordinator forwarded the wrong input type to specialists",
         "<b>Every specialist failed on every run</b>, swallowed into an error stub by "
         "gather(return_exceptions=True)"],
        ["Risk aggregation keyed by agent name but looked up by risk type",
         "Risk output was <b>constant regardless of input</b> - the system's central claim "
         "produced a fixed answer"],
        ["Login credentials bound as query parameters",
         "Passwords in access logs and browser history; fixed with form-encoded auth"],
        ["Due date equal to evaluation time in the TAWOS harness",
         "due &lt; now was never true, giving <b>recall 0.0</b> on the first full run"],
        ["Dependency link names guessed rather than inspected",
         "Matched only about 2,000 of roughly 18,600 real links until corrected"],
        ["A proposed threshold sweep reproduced the label definition",
         "Would have yielded a circular F1 of 1.00; caught and discarded before it reached results"],
    ], [0.38, 0.62]))

    # ---------------- 8. limitations
    s += [PageBreak(), P("8. Limitations and Threats to Validity", "h1"),
          P("These must appear in the paper. Do not bury them.")]
    s.append(tbl([
        ["#", "Threat"],
        ["1", "<b>The delay label is a proxy.</b> TAWOS has no due dates; at least 30% unresolved at "
              "sprint end is defensible but not canonical."],
        ["2", "<b>Only one of six risk types is validated on real data.</b> SPOF, cycles and "
              "coordination are near 0% non-zero in sprint reconstruction, because issue links span "
              "a project's whole history rather than one sprint window. The other five are validated "
              "<b>synthetically only</b>."],
        ["3", "<b>blocked_ratio never fires</b> - the TAWOS status vocabulary contains no blocked state."],
        ["4", "<b>AUC is weak by construction</b> at sprint level, since all tasks in a reconstructed "
              "sprint share one deadline."],
        ["5", "<b>The live-LLM sample is thin and imbalanced.</b> Kappa rests on n=37, with three of "
              "six risk types at n=1. Single provider, single model, one rate-limited key."],
        ["6", "<b>No human evaluation of explanation quality.</b> Grounding proves citations are "
              "real, not that the explanations are <i>useful</i>."],
        ["7", "<b>No confidence intervals.</b> The held-out F1 is a single point estimate from one split."],
        ["8", "<b>RBAC is not enforced</b> at fine granularity; the guarantee is authenticated and "
              "organization-scoped only."],
        ["9", "<b>Two designed agents are unimplemented</b> (Meeting, Communication Intelligence) "
              "because no data source exists yet."],
        ["10", "<b>No longitudinal study.</b> There is no evidence yet that a flagged risk predicts a "
               "real-world outcome over weeks."],
    ], [0.05, 0.95]))

    # ---------------- 9. related work
    s += [P("9. Related Work Positioning", "h1"),
          P("Position the contribution against three groups:")]
    s.append(tbl([
        ["Group", "Examples", "What they lack"],
        ["Traditional PM tools", "Jira, Linear, Asana, Monday.com",
         "Surface current state, not predictive evidence-linked risk; at-risk flags are opaque"],
        ["LLM multi-agent systems", "AutoGPT, MetaGPT, ChatDev, AgentBench",
         "Optimize task completion by LLM agents; no deterministic, mechanically checkable risk "
         "computation"],
        ["XAI in software engineering", "SHAP / LIME defect prediction, explainable effort estimation",
         "Explain a <i>learned model's</i> prediction. Here the computation is a deterministic graph "
         "invariant needing no post-hoc explanation; the LLM's role is narration under a citation "
         "constraint"],
    ], [0.2, 0.3, 0.5]))
    s.append(Spacer(1, 6))
    s.append(callout("<b>The differentiating combination - no comparator has all five.</b> "
                     "Specialist multi-agent decomposition, plus graph-computed (not LLM-inferred) "
                     "risk, plus mechanically enforced evidence grounding, plus a deterministic "
                     "fallback with an identical schema, plus a held-out real-world evaluation that "
                     "reports its negative results."))

    # ---------------- 10. paper mapping
    s += [P("10. IEEE Paper Structure Mapping", "h1"),
          P("Suggested 8 to 12 pages for IEEE Access; 6 to 8 for a conference paper.")]
    s.append(tbl([
        ["Sec.", "Paper section", "Source in this report", "Pages"],
        ["-", "**Abstract**", "Section 1 summary plus the novelty statement in 3.4", "200 words"],
        ["I", "**Introduction**",
         "Section 1 problem, Section 9 gap, Section 2 approach, Section 3 contributions", "1 - 1.5"],
        ["II", "**Related Work**", "Section 9 (build out the three-group table)", "1 - 1.5"],
        ["III", "**System Architecture**", "Section 4, with Figs. 1 and 2", "1.5 - 2"],
        ["IV", "**Graph-Grounded Prompting** (core)",
         "Sections 3.1 to 3.3, 4.3 to 4.5, and 7.10 as evidence of rigor", "2 - 3"],
        ["V", "**Multi-Agent Design**", "Section 4.6 plus the shared output schema", "1 - 1.5"],
        ["VI", "**Experimental Setup**",
         "Section 6 datasets, split discipline, point-in-time reconstruction", "1"],
        ["VII", "**Results**", "Sections 7.2 to 7.7, with Figs. 3, 4 and 5", "2 - 3"],
        ["VIII", "**Discussion**",
         "Section 7.5 negative results, Section 3.4, plus an ethics paragraph", "1"],
        ["IX", "**Threats to Validity**", "Section 8 - reproduce all ten honestly", "0.5"],
        ["X", "**Conclusion and Future Work**", "Section 1 plus Section 12", "0.5"],
    ], [0.07, 0.26, 0.51, 0.16]))
    s.append(Spacer(1, 6))
    s.append(callout("<b>Tone guidance.</b> The strongest defensible claim is: <i>a simple, "
                     "explainable, zero-parameter graph rule matches or beats a tuned learned model "
                     "on unseen projects, at 487x lower prompt cost.</i> Do not overclaim beyond "
                     "that. Report the negative results prominently rather than burying them - they "
                     "are what make the headline credible."))
    s.append(P("<b>An ethics paragraph is worth writing.</b> Risk-scoring <i>people</i> - workload "
               "pressure, silent-member detection - carries surveillance and fairness concerns. "
               "Acknowledging this directly strengthens the paper rather than weakening it."))

    # ---------------- 11. reproducibility
    s += [PageBreak(), P("11. Reproducibility", "h1"),
          P("Running the system:")]
    s.append(tbl([
        ["Command", "Effect"],
        ["cp .env.example .env", "GROQ_API_KEY optional - full fallback mode works without it"],
        ["make up && make db-migrate && make db-seed", "Start the full stack and seed demo data"],
        ["make test", "backend 29/29, ai-service 43/43, frontend 27/27"],
    ], [0.44, 0.56]))
    s.append(Spacer(1, 8))
    s.append(P("Reproducing every number in this report (run from <font face='Courier'>ai-service/</font>):"))
    s.append(tbl([
        ["Command", "Produces"],
        ["python -m eval.run_eval", "Synthetic detection, token sweep, latency, grounding"],
        ["python -m eval.boundary_eval", "Threshold-boundary sensitivity"],
        ["python -m eval.datasets.tawos_load", "TAWOS .sql to SQLite (approx. 4.3 GB, one pass)"],
        ["python -m eval.datasets.tawos_split", "The fixed project-level split"],
        ["python -m eval.datasets.tawos_score", "The all-987-sprint result"],
        ["python -m eval.datasets.tawos_holdout_eval", "The one-shot held-out number"],
        ["python -m eval.ablation_naive_vs_graph", "Naive-vs-graph ablation (needs API key, billed)"],
        ["python -m eval.live_llm_eval", "Schema validity and Cohen kappa (needs API key, billed)"],
        ["python -m eval.make_figures", "Regenerate all five figures (offline)"],
        ["python -m eval.make_report_pdf", "Regenerate this report (offline)"],
    ], [0.46, 0.54]))
    s.append(Spacer(1, 7))
    s.append(callout("<b>Required citation.</b> Tawosi, V., Al-Subaihin, A., Moussa, R., and Sarro, F. "
                     "<i>A Versatile Dataset of Agile Open Source Software Projects.</i> MSR 2022. "
                     "doi:10.1145/3524842.3528029"))

    # ---------------- 12. gaps
    s += [P("12. What Is Still Missing", "h1"),
          P("An honest gap list, in priority order.")]
    s.append(tbl([
        ["Priority", "Gap", "Effort", "Why it matters"],
        ["**1**", "**Bootstrap confidence intervals** on the held-out F1", "about half a day",
         "Turns a single point estimate into a defensible interval - the most likely reviewer request"],
        ["**2**", "**Bibliography** (15 to 20 references)", "1 day",
         "Comparators are currently named but not cited"],
        ["**3**", "**IEEEtran conversion** plus svg-to-pdf", "1 day", "Submission format"],
        ["4", "Human evaluation of explanation quality", "1 to 2 weeks",
         "The biggest unmeasured claim for a paper about explainability"],
        ["5", "Grounding ablation (run with the check disabled)", "about 1 day",
         "Shows the safety net catches real hallucinations, not just synthetic fabrications"],
        ["6", "Balanced live-LLM sample on a paid tier", "days",
         "Fixes the n=1 categories in the kappa breakdown"],
        ["7", "Validate the remaining five risk types on real data (AMI / Enron)", "months",
         "Removes the largest scope limitation"],
    ], [0.09, 0.31, 0.15, 0.45]))
    s.append(Spacer(1, 8))
    s.append(P("Venue readiness:", "h2"))
    s.append(tbl([
        ["Venue", "Ready?"],
        ["Regional IEEE conferences (ICCCNT, ICACCS, ICOEI, ICSSIT)",
         "**Yes - comfortably above the typical bar**"],
        ["**IEEE Access**", "**Yes, after items 1 to 3**"],
        ["IEEE ICSME / SANER", "Borderline - add items 4 and 5"],
        ["IEEE TSE / ICSE / ASE", "No - needs items 4 through 7"],
    ], [0.6, 0.4]))
    s.append(Spacer(1, 14))
    s.append(P("License: MIT. Third-party components: Groq, NetworkX, FastAPI, SQLAlchemy, Pydantic, "
               "Next.js, shadcn/ui, and the TAWOS dataset (Apache 2.0, MSR 2022 - citation required).",
               "note"))
    return s

# Phase 1 user study: does the evidence help a manager find a sprint's problems?

Everything automated about Phase 1 is measured (VALIDATION_REPORT.md). What only people can
answer is whether the analysis panel's findings, with the tasks and people they cite, help
someone find what is wrong with a sprint faster and more accurately than the board alone,
and whether they find the product usable. This is a small within-subjects study for that.

## 1. Questions and hypotheses

| | Question | Hypothesis |
|---|---|---|
| RQ1 | Do people answer questions about a sprint more accurately with the analysis panel? | H1: more tasks correct with the evidence |
| RQ2 | Do they answer faster? | H2: less time with the evidence |
| RQ3 | Is TeamSync usable? | H3: SUS score at or above 68, the published average |
| RQ4 | Do they understand and appropriately trust the warnings? | Descriptive: explanation items, and whether they accept or question the suggested move |

## 2. Design

Within subjects, two conditions, two real sprints:

- **Evidence**: TeamSync with the analysis already run; the dashboard's panel shows the risk levels,
  findings, cited tasks and people, and suggested moves.
- **Baseline**: the same sprint in TeamSync with no analysis run: the board, sprints, team and
  dashboard charts only. This is what a manager has today.
- **Sprint A**: Apache Mesos sprint 74 (30 tasks, 13 people). **Sprint B**: LSST Data Management
  sprint 305 (33 tasks). Both are real TAWOS sprints replayed as they stood halfway through; both
  really did finish late.

Each participant does one sprint in each condition. Order and pairing are counterbalanced over
four groups, so recruit in multiples of four:

| Group | First | Second |
|---|---|---|
| 1 | Sprint A, evidence | Sprint B, baseline |
| 2 | Sprint B, evidence | Sprint A, baseline |
| 3 | Sprint A, baseline | Sprint B, evidence |
| 4 | Sprint B, baseline | Sprint A, evidence |

## 3. Participants

8 or 12 people who have worked in at least one sprint with a task board (final-year students with
team-project experience, teaching assistants, industry contacts). Record years of experience and
whether they have led a sprint. No one who worked on TeamSync. About 50 minutes each.

## 4. Setup (on the day of the sessions)

The sprints are replayed at "now", so set up within a couple of hours of the sessions:

```bash
cd backend
python -m app.scripts.study_setup
```

With the backend and AI service running and no LLM key, this imports both sprints twice (analysed
and not), adds a read-only participant account to each, checks that account cannot run an
analysis, and writes `docs/user-study/ANSWER_KEY.md` (git-ignored). Participants sign in with the
accounts it prints, so nothing can be changed during a session.

## 5. Procedure

| Minutes | Step |
|---|---|
| 5 | Welcome, consent form, background questions (FORMS.md, parts 1 and 2) |
| 5 | Tour of the board, sprints, team and dashboard on any practice project; no study sprint is shown |
| 15 | First condition: tasks T1–T4 (T5 too if it is the evidence condition), then the effort question |
| 3 | Before the evidence condition only: a two-minute tour of the analysis panel, on the practice project |
| 15 | Second condition: the same |
| 7 | Explanation questions (after the evidence condition), SUS, preference and interview (FORMS.md, parts 4–6) |

Read the task wording exactly as written, answer questions about the interface, never about the
sprint. Time each task with a stopwatch from the end of the question to the participant's answer;
stop at 4 minutes and score it incorrect.

## 6. Tasks and scoring

Ask in this order in both conditions. The truth for each sprint is in ANSWER_KEY.md; it is
computed from the board, not from the analysis, so the tool can be wrong and be caught.

| | Task (read aloud) | Correct when |
|---|---|---|
| T1 | "Will this sprint finish on time at its current pace? About what share of its work is done?" | "No", and the share within ±10 points of the key (tasks or points) |
| T2 | "Who has the most open work right now, and roughly how many story points is it?" | The right person, points within ±1. When some open tasks have no estimate, the key accepts either fair reading: points as shown, or each unestimated task counted as 1 (the analysis's rule); in sprint B they name different people |
| T3 | "Suggest one task to move, and to whom, to relieve that person." | The task is one of theirs, and the receiver ends below that person's current load |
| T4 | "Is any open task holding up other open work? Which one?" | Names a task the key lists as blocking (not scored if the key lists none) |
| T5 | Evidence condition only, untimed: show the top suggestion. "Would you apply it? Why or why not?" | Not scored; record yes / no / unsure and the reason |

After each answer, ask "How confident are you, from 1 (guessing) to 5 (certain)?"

## 7. Measures

- Correct (0/1), seconds and confidence for each of T1–T4 in each condition.
- Mental effort after each condition (one item, 1–9).
- After the evidence condition: seven explanation items (FORMS.md, part 4).
- At the end: the System Usability Scale, which condition they would rather work in, and why.

Record everything in `results_tasks.csv` and `results_questionnaires.csv` (templates here, one
row per participant and task, and one row per participant).

## 8. Analysis

```bash
cd ai-service
python -m eval.user_study_analysis ../docs/user-study/results_tasks.csv ../docs/user-study/results_questionnaires.csv
```

- **H1:** tasks correct per participant, evidence vs baseline, exact Wilcoxon signed-rank test;
  per task, exact McNemar test.
- **H2:** total time on T1–T4 per participant, the same paired test, with the median paired
  difference and a bootstrap 95% interval.
- **H3:** SUS mean with a 95% interval, against the benchmark of 68.
- **RQ4:** share agreeing (4 or 5) with each explanation item; T5 answers against whether the
  suggested move was valid by the T3 rule.
- Report effect sizes (matched-pairs rank-biserial r) and intervals, not only p-values: with 8–12
  people only large effects can reach significance, so this is a pilot study and should be
  described as one.

## 9. Ethics and data

Ask your supervisor whether departmental ethics approval is needed before recruiting. Participation
is voluntary and can stop at any time without giving a reason. Record no names in the results:
use P01, P02, and keep the consent forms separately. No audio or screen recording unless the
participant ticks the box for it. The sprint data is public (TAWOS, Apache-2.0) and anonymised.

## 10. Threats to validity

- The facilitator built the tool: read tasks verbatim and give no hints; ideally someone else
  facilitates.
- Students are not practising managers; report experience and analyse by it if numbers allow.
- Two sprints can differ in difficulty: counterbalancing spreads that across conditions, and the
  per-sprint results are reported too.
- The evidence condition gets a short extra tour; the baseline tour covers every other screen, so
  both start with equal familiarity.

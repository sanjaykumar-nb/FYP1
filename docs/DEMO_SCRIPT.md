# Demo video script — 6 minutes

A shot-by-shot script for recording the project demo. [DEMO.md](../DEMO.md) is the full
walkthrough and explains what is real in the data; this file is only the recording plan.

Every number below is checked automatically: `python -m app.scripts.check_demo` (from `backend/`,
with both services up) replays the sprint and fails if any claim in this script no longer holds, and
CI runs it on every push. Run it before you record. If a number on your screen still differs, see
[If a number looks wrong](#if-a-number-looks-wrong).

---

## Before you record

```bash
# Terminal 1 — AI service (no API key: the deterministic path is what the demo shows)
cd ai-service && python -m uvicorn app.main:app --port 8001

# Terminal 2 — backend, on a fresh database
cd backend && rm -f demo.db
DATABASE_URL="sqlite+aiosqlite:///./demo.db" JWT_SECRET="dev-secret-key-at-least-32-characters-long" \
  python -m uvicorn app.main:app --port 8000

# Terminal 3 — frontend
cd frontend && npm run dev

# Terminal 4 — the two projects the video uses
cd backend
python -m app.scripts.import_real_sprint app/scripts/fixtures/mesos_sprint_74.json
python -m app.scripts.import_real_sprint app/scripts/fixtures/mesos_sprint_74.json --at 0.5
```

Each import prints its own login. **Write both down** — the second one is the halfway replay.

Checklist:

- [ ] Browser at 100% zoom, window 1440×900 or larger, bookmarks bar hidden, dev tools closed.
- [ ] Both logins to hand; sign in to the full sprint before you start recording.
- [ ] A second browser profile (or private window) signed in as a **viewer** — see minute 4.
- [ ] Notifications silenced.
- [ ] Record at 1080p. Screen only; voice-over can be added after.

**Do not re-run the analysis before recording.** The Apply → re-run beat at minute 2 needs the
original run, where workload is still `high`.

---

## Shot list

### 0:00 – 0:30 · The problem *(Workspace)*

**On screen:** the workspace, one project card — *Apache Mesos — Mesosphere Sprint 74*,
**Health 10 · Risk 90**.

> "This is a real sprint from the Apache Mesos project — thirty issues, thirteen people, taken from
> a public dataset of Jira histories and replayed through this app's own API. Project tools show
> you what the state is. The question this project asks is: can a system tell you the sprint is in
> trouble, show you why, and be checkable when it does?"

### 0:30 – 1:15 · The work is real *(Task board)*

**On screen:** open the project → **Tasks**. Scroll the board once. Point at *MESOS-5814*'s red
**Blocked by 1** marker. Click it → **Dependencies** tab → *MESOS-5904 blocks this*. Close. Open
*MESOS-7605* → **Discussion** — ten real comments from four contributors.

> "Real issue keys, real assignees, real blocking links, real discussion. Twenty of these thirty
> issues were still open when the sprint closed — but nothing on this board tells you that yet."

*(Optional, 5 seconds: try to add MESOS-5814 as a blocker of MESOS-5904 — the app refuses with
"That would create a circular dependency.")*

### 1:15 – 2:15 · The analysis, and its evidence *(AI Insights)* — **the core shot**

**On screen:** **AI Insights** tab. The run is already there from the import. Read the top line,
then scroll slowly through the evidence panel.

> "Overall risk: critical. Six risk types, each scored from a graph of forty-five nodes and a
> hundred and seventeen links built from this project's own tasks, people, dependencies and
> comments.
>
> Delay: critical — twenty of twenty open tasks past their due date. Workload: high — contributor
> 3409 carries nine open points against a team mean of 3.8. Dependencies: the critical path runs
> through MESOS-5904 into MESOS-5814.
>
> Every finding names what it rests on. These chips are the actual issues and people behind the
> number — click one and you are looking at the task itself. No language model produced any of
> these figures: they are graph properties, computed the same way every time. The model's only job
> is to write the sentence, and it may only cite nodes it was given."

**Hold on the evidence chips for a full five seconds.** This is the contribution.

### 2:15 – 3:00 · It suggests the fix, and the fix works *(Recommendations)*

**On screen:** scroll to **Redistribute workload**. Three moves, each with an **Apply** button.
Click all three. Then **Run Analysis**.

> "The recommendation comes with the moves that would carry it out, computed on the same graph:
> take work off the person carrying the most, give it to whoever it evens out best. It predicts the
> effect before you act — heaviest load nine points down to six, workload high to medium.
>
> Apply them, and run the analysis again."

**On screen:** the workload row now reads **was high → medium**, and the finding names contributor
3481 with 6 points.

> "High, now medium — exactly what it predicted. The row shows what changed since the last run."

### 3:00 – 4:00 · The warning arrives in time *(halfway replay)*

**On screen:** sign in with the **second** login (the `--at 0.5` import). Go straight to **AI
Insights**.

> "Same sprint — but replayed as it stood halfway through. Only the issues that existed then, only
> the comments written by then. The deadline is a week away, so nothing is overdue, and the board
> looks unremarkable.
>
> The system already says delay: critical. '[Read the first number] percent through its schedule
> with eighteen percent of the work done; at this pace [read the last number] percent will still be
> open at the deadline.' Recommendation: re-plan before the deadline.

**Read the two percentages off the screen** — they depend on the hour you imported (milestone dates
are whole days): 50% through / 63% open just after midnight UTC, up to 57% / 67% just before it.
>
> The real sprint ended with twenty of thirty issues unfinished — sixty-seven percent. One sprint
> proves nothing on its own, so this was measured across two hundred and seventy sprints from
> twenty-two projects the system had never seen: area under the curve 0.79 at the halfway point,
> 0.87 at three-quarters."

### 4:00 – 4:30 · Roles are enforced *(viewer window)*

**On screen:** switch to the viewer window, same project, **AI Insights**.

> "A viewer sees everything and can change nothing — no Run Analysis, no Apply, no New Task, cards
> don't drag. It is enforced in the API, not hidden in the interface: the same request sent
> directly comes back 403."

### 4:30 – 5:20 · How it works *(architecture slide or diagram)*

**On screen:** the architecture figure (`docs/images/architecture-pipeline.svg`), or slide 5 of
the deck.

> "The pipeline inverts the usual design. Project state is compiled into a typed knowledge graph.
> Every risk is a graph property — critical path, articulation points, weighted degree, community
> structure — computed deterministically, at zero token cost. Only then is a language model shown
> one finding and the small witness subgraph behind it, and asked to narrate it.
>
> Two things follow. Prompt cost tracks the number of anomalies, not the size of the project:
> measured, 1.47 times the tokens for a project 154 times larger, and 487 times cheaper than
> sending the whole dataset. And because the model may only cite nodes from that subgraph, every
> citation can be checked — two hundred fabricated references were fed in during testing and all
> two hundred were stripped.
>
> With no API key at all, every number you have seen still appears. The language model is the
> narration layer, not the decision layer."

### 5:20 – 6:00 · What was measured, and what wasn't

**On screen:** slide 10 (results) or the results table from the report.

> "On the held-out projects the zero-parameter graph rule scores F1 0.712 at sprint end. A tuned
> logistic model reached 0.816 in cross-validation and fell to 0.593 on projects it hadn't seen —
> but a paired test can't separate it from the simple rule, so the honest claim is that the
> complexity bought nothing, not that the rule is better.
>
> Three attempts to improve the rule failed, and they are reported in full. The mid-sprint
> projection doesn't rank better than simply counting open work — what it adds is the warning
> arriving early, with its evidence attached.
>
> That's the system: risk you can check, in time to do something about it."

---

## If a number looks wrong

| What you see | Why | Do this |
|---|---|---|
| Different graph size than 45 nodes / 117 links | The database wasn't fresh, or extra tasks exist | `rm demo.db`, restart the backend, re-import |
| Workload still `high` after applying the moves | The re-run happened before all three applied | Check each row reads *Applied*, then re-run |
| No **Apply** buttons | The run predates the board's current state, or you are signed in as a viewer | Re-run the analysis as the owner |
| Different move list | Every fresh import suggests MESOS-8383, MESOS-8524, MESOS-8492 in that order; anything else means the board changed after the import | Re-import for a clean recording |
| Anything else | Something in the code changed what the demo shows | Run `python -m app.scripts.check_demo` — it names the claim that broke |
| Halfway replay shows nothing overdue | Correct — that is the point of the shot | — |

## If you have only three minutes

Keep 1:15 – 3:00 (analysis, evidence, apply, re-run) and 3:00 – 4:00 (the halfway warning). Open
with one sentence of context and close with the two sentences from 5:20. Everything else is
supporting material.

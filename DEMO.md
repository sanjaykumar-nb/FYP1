# Demo — TeamSync AI on a Real Sprint

This prototype is demonstrated on **real project history**, not invented data: sprint 74 of
**Apache Mesos**, taken from the public TAWOS dataset of Jira issues. The sprint is loaded into
the running app through its own REST API — the same endpoints a real team would use — and then
analysed live. Every result quoted below was produced that way and checked against the raw data.

---

## What is real, and what is derived

| Real, from the Jira history | Derived by the replay (and why) |
|---|---|
| All 30 issues: keys, **titles**, descriptions, types, priorities, story points | **Dates are shifted** by one constant so the sprint ended yesterday — every real interval is kept |
| Who was assigned each issue; who reported it | **Status is reconstructed as of sprint end** — done only if resolved by then — so today's outcome can't leak in |
| The 2 real "blocks" links between issues | **Every issue is due at sprint end**: Jira sprints have no per-issue due dates |
| 71 real comments, by their real authors, written before the sprint closed (45 later ones are left out) | **People are anonymous** ("Apache Mesos contributor #3409") because TAWOS anonymises them |
| | **Project team = the 13 people assigned sprint work**; the other 9 (reporters/commenters) get accounts and their comments still appear |
| | **The epic imports without points** — its 13 points roll up its children, not one person's work |

Source: Tawosi, Al-Subaihin, Moussa & Sarro, *A Versatile Dataset of Agile Open Source Software
Projects*, MSR 2022 (Apache 2.0). The extract is committed as
`backend/app/scripts/fixtures/mesos_sprint_74.json` (92 KB), so the demo needs no 4 GB dump.

## 1. Start the prototype

No Docker, no API keys — three processes.

```bash
# Terminal 1 — AI service (no LLM key needed; the deterministic path runs)
cd ai-service
python -m uvicorn app.main:app --port 8001
```

```bash
# Terminal 2 — backend, on a fresh database
cd backend
export DATABASE_URL="sqlite+aiosqlite:///./demo.db"
export JWT_SECRET="dev-secret-key-at-least-32-characters-long-ok"
python -m uvicorn app.main:app --port 8000
```

```bash
# Terminal 3 — frontend
cd frontend
npm run dev
```

## 2. Load the real sprint

With the backend and AI service running:

```bash
cd backend
python -m app.scripts.import_real_sprint app/scripts/fixtures/mesos_sprint_74.json
```

It prints what it loaded, runs the analysis, and ends with the login to use:

```
team: 13 assignees on the project; 9 reporters/commenters as organization users
tasks: 30 (10 resolved by sprint end, 20 still open)
dependencies: 2 real blocking links
comments: 71 written by sprint end (45 later ones excluded)

analysis completed: overall risk critical
Sign in at http://localhost:3000 as pm-<timestamp>@example.com / realsprint-2018
```

Each run creates its own organization, so it can be re-run any time.

## 3. Walkthrough

**Workspace** — one project, *Apache Mesos — Mesosphere Sprint 74*, showing **Risk 90 · Health
10**. Those scores come from the analysis the importer just ran.

**Project dashboard** — 25% complete (by story points), **20 overdue**, **team of 13**. Recent
tasks show real issue titles, e.g. *MESOS-5882: "`os::cloexec` does not exist on Windows"*.

**Task board** — all 30 issues where they stood when the sprint closed:
Planned 4 · In Progress 15 · Review 1 · Done 10. Cards show priority, points, due date and the
assignee (the avatar shows the contributor's number). *MESOS-7911* is unassigned — it genuinely was.
Drag a card to change its status; click one to edit it or change its assignee.

**Team tab** — the 13 people who carried sprint work. **Add teammate** creates a sign-in for a new
person and puts them on the project, so work can be assigned to them.

**AI Insights → Run Analysis** — live result on this sprint:

| Agent | Verdict | Output |
|---|---|---|
| Planning | low | 1 milestone, 30 tasks, sprint readiness 100% |
| Progress | medium | 10 of 30 done (33%) |
| Workload | high | 13 members, 3 overloaded, 4 under-used |
| **Overall** | **critical** | confidence 70% |

Recommendations, each checked against the raw sprint:

1. **Split large or overdue tasks** — *"20 of 20 open tasks are past their due date."*
   What it means in plain terms: **20 of the 30 issues committed to this sprint were unfinished
   when it closed.** (Every open task counts as overdue because all are due at sprint end.)
2. **Redistribute workload** — *"contributor #3409 carries 9 open points vs a team mean of 3.8."*
   True in the data: #3409 still held MESOS-8383, MESOS-8492 and MESOS-8567 at sprint end.

Also worth saying: **silent members — low.** On this real team, the people doing the work were
also talking about it.

## 4. What the prototype covers

| Working now | Later |
|---|---|
| Register, sign in, organization-scoped data | Meeting and communication intelligence |
| Create projects; **add teammates** | Fine-grained role permissions |
| Tasks with **assignees**, points, due dates, drag-and-drop board | Notifications, real-time presence |
| Dependencies and comments (via API) | Dependency and comment UI on the board |
| Run analysis; results persisted; **dashboard and workspace reflect them** | LLM narration (works with a Groq key; not needed for the demo) |

## 5. Found and fixed by testing on real data

None of these showed up with the invented seed data:

- **No way to add a teammate.** The "invite" endpoint was a stub that answered "Invitation sent"
  and did nothing, so tasks could never be assigned. Replaced with a working endpoint and a Team tab.
- **The dashboard metrics endpoint crashed** (HTTP 500, a missing import). The page silently showed
  zeros for completion, overdue and team size.
- **The project team list crashed** (HTTP 500).
- **The Planning agent crashed on unestimated tasks** — common in real Jira data. Fixed, with
  regression tests.
- **Analysis never updated the project's risk and health scores**, so the dashboard contradicted the
  AI panel.
- **The dashboard counted task statuses from the first page of tasks only.**

## 6. Known limitations to mention if asked

- The **coordination** measure only links people through assigned work; someone who only reviews
  and comments looks unconnected. This is why reporters/commenters are not project members here.
- Recall-first: the delay signal flags every unfinished sprint and some finished ones.
- Only the deterministic path is demonstrated; the language-model narration is optional.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| Importer stops with a connection error | Start the backend (port 8000) and AI service (port 8001) first |
| Importer reports `409` | Re-run it — each run uses a new timestamped organization |
| "Run Analysis" fails | The AI service on port 8001 isn't running |
| A tab doesn't switch when clicked through remote-desktop software | Click once more — a real mouse click always works |
| Want a clean slate | Stop the backend, delete `backend/demo.db`, start it again, re-run the importer |

The invented seed data (`python -m app.scripts.seed`, login `pm@demo.com` / `password123`) still
exists for quick UI checks, but it is not the demo.

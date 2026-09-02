# TeamSync AI — MVP Overview

A plain-language walkthrough of what the MVP actually does, how it's built, and why it works —
written for a reader who wants to understand the project without wading through research-paper
detail.

---

## 1. What Problem Does It Solve?

Project managers usually find out about team problems *after* they've already caused a delay:
someone's quietly overloaded, one person is the only one who understands a key part of the
project, or a task on the critical path has been sitting blocked for a week. Most PM tools (Jira,
Trello, Asana) show you the current board — they don't tell you which of these problems is
brewing, and if they try, they don't explain *why* they think so.

TeamSync AI is a project management tool with a built-in "early warning system" that looks at the
same task/assignment/dependency data every PM tool already has, and flags six kinds of team risk
— automatically, with a clear reason attached to every warning.

---

## 2. What's in the MVP

The MVP is a working, end-to-end product covering the parts that don't depend on data the app
doesn't yet have:

- **Login & teams** — sign up, create an organization, invite people, role-based access.
- **Projects & tasks** — create projects, add tasks with assignees, due dates, priority, and
  dependencies between tasks; a drag-and-drop Kanban board.
- **"Run Analysis" button** — one click analyzes the current project and shows:
  - Six risk categories (explained below), each with a severity level.
  - A short, evidence-backed explanation of *why* each risk was flagged.
  - A prioritized list of suggested actions.
- **Everything is saved** — every analysis is stored, so you can look back at what the system
  said and when.

**Deliberately left out of the MVP** (not because they're hard, but because they need data
sources this version of the app doesn't collect yet): analyzing meeting transcripts, analyzing
chat/email communication patterns, and an automated multi-agent code-review feature. These are
designed and ready to add once transcript/chat ingestion exists.

---

## 3. The Six Risks It Detects

| Risk | Plain-language meaning |
|---|---|
| **Delay** | A task on the critical path is overdue or stuck |
| **Workload imbalance** | One person is carrying much more work than their teammates |
| **Single point of failure** | Only one person understands or owns a part of the project |
| **Dependency risk** | Too much of the project funnels through one task or one person |
| **Coordination gap** | Team members are working in disconnected clusters, not talking to each other |
| **Silent member** | Someone has a lot of assigned work but almost no activity/comments — a sign they're stuck or checked out |

---

## 4. How It Works, In Simple Terms

Instead of just handing a giant pile of task data to an AI model and asking "find problems" (slow,
expensive, and prone to making things up), TeamSync AI does it in two clean steps:

**Step 1 — Compute the facts, no AI involved.**
The app turns your project data into a small internal "map" — who's connected to what, which
tasks block which other tasks, who's assigned to what. From that map, simple, well-established
graph math (the same kind used to find critical paths in scheduling software, or to find
"bottleneck" people in a network) calculates each of the six risks. This part is 100% predictable
— the same project data always gives the same answer, and it runs in a few milliseconds.

**Step 2 — Explain the facts, using AI.**
For each risk the math actually found, the app shows an AI model *just the small, relevant piece*
of the project map connected to that one finding — not the whole project — and asks it to explain
it in plain English and suggest what to do about it. Because the AI only ever writes an
explanation for something already proven true by the math, it can't accidentally invent a risk
that isn't there, and it can't fabricate "evidence" either — the system automatically checks that
every fact the AI cites is a real piece of your project data, and throws away anything that isn't.

**If the AI is unavailable** (no internet, no API key, hitting a rate limit), the app doesn't
break — it falls back to a simpler, rule-based explanation instead. You always get a complete
result either way.

**Why this two-step design matters practically:** because the AI is only ever shown a small
relevant slice of the project instead of the whole thing, this approach stays cheap even on large
projects — a 2,000-task project costs about the same to analyze as a 50-task one, instead of the
cost growing with project size the way a "dump everything into the AI" approach would.

---

## 5. Architecture, Simplified

```
 You (browser) ──▶ Web App (Next.js) ──▶ Core Backend (FastAPI) ──▶ Database (PostgreSQL)
                                                  │
                                                  ▼
                                        AI Analysis Service (FastAPI)
                                                  │
                                        ┌─────────┴─────────┐
                                        ▼                   ▼
                               Graph math (instant,     AI model (Groq/Llama)
                               no AI, always on)         explains findings
```

Three independent services, each doing one job:
1. **Frontend** — what you see and click.
2. **Core backend** — accounts, projects, tasks, saved analysis results.
3. **AI service** — builds the project map, runs the risk math, gets AI explanations.

They're separated so the AI service can be scaled, swapped, or taken offline without breaking the
rest of the product.

---

## 6. Technology Used (MVP)

| Part | Built with |
|---|---|
| Web app | Next.js, React, Tailwind CSS |
| Core backend | FastAPI (Python), PostgreSQL database |
| AI service | FastAPI (Python), NetworkX (the graph-math library), Groq (fast AI inference, Llama models) |
| Real-time updates | WebSockets |
| Running it locally | Docker Compose (one command starts everything) |

No exotic infrastructure — everything runs in a handful of containers on a laptop.

---

## 7. Why This Approach Is a Reasonable Engineering Choice

- **Cheap enough to run often.** Because the AI only sees a small slice of the project per
  finding, analysis stays fast and low-cost even as the project grows — so it can be re-run
  whenever the project changes, not just occasionally.
- **Trustworthy by construction.** The numbers (who's overloaded, what's on the critical path)
  come from plain math, not an AI guess — so they're consistent and checkable. The AI's only job
  is to describe them in words, and every fact it mentions is automatically verified against the
  real project data.
- **Doesn't fall over without an AI key.** Every part of the analysis has a non-AI fallback, so
  the product still fully works if the AI service is down or disabled.
- **Built the way a real product would be.** Multiple teams/organizations, permissions, saved
  history, real-time updates — not a one-off script or notebook demo.

---

## 8. Running It

```bash
git clone <repo-url> && cd teamsync-ai
cp .env.example .env        # AI key is optional — the app works fully without one
make up && make db-migrate && make db-seed
```

Then open:
- App: `http://localhost:3000`
- Backend API docs: `http://localhost:8000/docs`
- AI service docs: `http://localhost:8001/docs`

---

## 9. What Comes After the MVP

- Feeding in meeting transcripts and chat/email history so the AI can also catch coordination
  problems that only show up in conversation, not in the task board.
- A single combined "team health score" that blends all the signals into one number.
- Finer-grained permissions per role.
- A deeper, real-world accuracy study once transcript/chat data is available.

---

*This is the simplified companion to the full technical write-up — see `RESEARCH_PAPER.md` for
architecture detail, novelty claims, and the full evaluation methodology and results.*

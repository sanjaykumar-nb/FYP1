# TeamSync AI v1.0-mvp — release notes

The MVP release: a Kanban project tool whose AI layer computes six kinds of coordination risk
from a knowledge graph of the project, shows the tasks and people behind every finding, suggests
fixes you can apply, and warns mid-sprint when the plan will not make its deadline.

Everything below runs with **no LLM API key**. A Groq key is optional and only adds narration.

---

## What's in the bundle

| Part | Where | What it is |
|---|---|---|
| **Frontend** | `frontend/` | Next.js 14 web app, port 3000 |
| **Backend API** | `backend/` | FastAPI + SQLAlchemy (PostgreSQL or SQLite), port 8000 — accounts, organizations, roles, projects, sprints, tasks, dependencies, discussion, analysis history |
| **AI service** | `ai-service/` | FastAPI + NetworkX, port 8001 — knowledge graph, risk metrics, agents, evidence grounding |
| **Stack** | `docker-compose.yml` | PostgreSQL 16, Redis 7, the three services |
| **Demo data** | `backend/app/scripts/` | `seed.py` (invented demo org) and `import_real_sprint.py` (a real Apache Mesos sprint from TAWOS) |
| **Demo check** | `backend/app/scripts/check_demo.py` | Replays the real sprint and verifies every number the demo script quotes |
| **API reference** | [`docs/API.md`](docs/API.md), [`docs/api/*.json`](docs/api/) | Every endpoint, marked by whether the app uses it and whether a test covers it; OpenAPI specs for both services |
| **Research** | `IEEE_PAPER_REPORT.md`, `paper.tex`, `METRICS_INFERENCE.md`, `ai-service/eval/` | The evaluation, its results and the scripts that reproduce them |
| **Presenting** | `DEMO.md`, `docs/DEMO_SCRIPT.md`, `docs/SLIDES.md` | Walkthrough, six-minute recording script, slide outline |

### Web app

| Page | What you can do |
|---|---|
| `/` | What the product does, and the measured results |
| `/signup`, `/login` | Create an account (you own a new workspace) or sign in |
| `/workspace` | Your projects with health and risk scores; create one; restore archived ones |
| `/projects/:id/dashboard` | Overview, **Sprints**, Tasks, **Team** and **AI Insights**: run the analysis, read each finding's evidence, apply suggested moves |
| `/projects/:id/tasks` | Kanban board: drag between columns, sprint filter, components, *Blocked by* markers; task dialog with details, dependencies (cycles refused) and discussion |
| `/projects/:id/settings` | Rename, change status and dates, archive |
| `/profile` | Your name, and what your role allows |

### AI agents

One analysis runs this pipeline. Every number is computed from the graph; no language model
decides whether a risk exists.

| Agent | Job |
|---|---|
| **Coordinator** | Builds the project's knowledge graph, computes the six risk metrics, runs the specialists and assembles the result |
| **Planning** | Sprint readiness and schedule |
| **Progress** | Completion, velocity, stalled work |
| **Workload** | Load per person, overload and idle capacity |
| **Risk** | Scores delay, workload, knowledge concentration, dependency, coordination and silent-member risk, each finding citing the graph nodes behind it |
| **Recommendation** | One recommendation per significant risk; for workload, the reassignments that carry it out and their predicted effect |

With a key configured, each agent may also ask the LLM to narrate its finding; any citation the
model makes that is not in the finding's evidence is removed. Without a key the LLM is never
called. Meeting intelligence, communication intelligence and the review panel exist in the code
from the original design but have no data source in the product and are not part of the MVP.

### API

69 backend operations and 6 AI-service operations; [`docs/API.md`](docs/API.md) lists them all.
The **36 backend operations the app uses or the tests cover** are the MVP surface. The rest —
meetings, admin, organizational memory, the intelligence index, teams and custom roles — are code
from the original design that nothing in the product relies on. Don't demonstrate them as working.

---

## Run it

**With Docker** (PostgreSQL, as in production):

```bash
cp .env.example .env
docker compose up -d --build     # frontend :3000, backend :8000, AI service :8001
docker compose exec backend python -m app.scripts.import_real_sprint app/scripts/fixtures/mesos_sprint_74.json
```

The import prints a login. `make db-seed` loads the invented demo organization instead
(`pm@demo.com` / `password123`).

**Without Docker** (SQLite): see [README → Option B](README.md#option-b--without-docker), or the
four commands at the top of [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

---

## How it was verified

Every push runs, on GitHub Actions:

| Check | Result at release |
|---|---|
| Backend tests on SQLite | 65 passed |
| Backend tests on PostgreSQL 16 | 65 passed |
| AI service tests (deferred features excluded) | 73 passed |
| Frontend type check and tests | clean, 53 passed |
| Demo check — both services, SQLite | 14 of 14 claims hold |
| Demo check — both services, PostgreSQL | 14 of 14 claims hold |
| `docker compose up` stack, then the demo check against it | 14 of 14 claims hold |

---

## Changed for this release

- **PostgreSQL verified.** The backend had only ever run on SQLite; the full suite and the demo
  now pass on PostgreSQL 16 too, and CI checks both.
- **Docker verified.** The Compose stack is built and the demo replayed against it in CI.
  `.dockerignore` files keep `.env` secrets and the 4.7 GB evaluation dataset out of the images —
  before, a local `docker compose build` would have copied both in.
- **No key means no LLM call.** Without a real `GROQ_API_KEY` (including the placeholder in
  `.env.example`) the AI service answers from the deterministic path immediately, instead of
  calling Groq and waiting for a refusal — which could take the full timeout on a bad network.
- **Archived projects can be restored** from the workspace's *Archived* list. Project status only
  accepts the four statuses the product knows.
- **Dismissed notifications leave the page.** A closed toast used to stay mounted, invisible,
  for about 17 minutes, swallowing clicks on whatever was beneath it.
- **Same sprint, same suggestions.** Tied reassignment suggestions are now broken by task and
  person name rather than database id, so every import of a sprint suggests the same moves.
- **The landing page only claims what the product does.** Removed an unfounded "SOC2 Compliant"
  badge, a "free trial", features that are not in the MVP, a video placeholder and twelve dead
  links.
- **The backend test run exits.** It used to finish and then hang on Windows, held open by an
  undisposed SQLite connection thread.

---

## Known limitations

Stated in full in the README and in `IEEE_PAPER_REPORT.md` §9. The ones that matter in a demo:

- Roles apply across the organization; there are no per-project roles.
- Only the delay risk is validated on real data; the other five are validated on synthetic
  scenarios.
- No password reset, notifications, real-time updates or hosted instance.
- Tables are created on startup; there are no database migrations, so upgrading an existing
  PostgreSQL database with changed tables is manual.

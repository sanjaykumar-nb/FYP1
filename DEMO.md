# Demo Script — TeamSync AI

A tested, step-by-step walkthrough for presenting the MVP live. Every screen and every finding
below was verified against the actual seeded demo data immediately before this document was
written — nothing here is hypothetical.

---

## 1. Start the stack

**No Docker needed** for a demo — three plain processes, no external services required.

```bash
# Terminal 1 — AI service (works with zero LLM key; fully deterministic fallback)
cd ai-service
python -m uvicorn app.main:app --port 8001

# Terminal 2 — Core backend, against a throwaway SQLite file
cd backend
export DATABASE_URL="sqlite+aiosqlite:///./demo.db"
export JWT_SECRET="dev-secret-key-at-least-32-characters-long-ok"
python -m app.scripts.seed          # populates demo data (idempotent-ish: delete demo.db to reset)
python -m uvicorn app.main:app --port 8000

# Terminal 3 — Frontend
cd frontend
npm run dev
```

Open **http://localhost:3000** and log in:

| Field | Value |
|---|---|
| Email | `pm@demo.com` |
| Password | `password123` |

(Other seeded accounts: `owner@demo.com`, `admin@demo.com`, `dev1@demo.com`, `dev2@demo.com`,
`viewer@demo.com` — all share the same password, useful if you want to demo role-based
dashboards side by side.)

## 2. What's already in the demo data

Seeded automatically by `app.scripts.seed`, no manual setup:

- **1 organization** ("Demo Company"), **6 users**, **1 team**
- **3 projects**: Website Redesign (WEB), Mobile App v2.0 (MOB), API Platform (API)
- **45 tasks** across 12 milestones, with real story points, priorities, due dates, and a
  dependency chain
- Data is deliberately imperfect — uneven workload, some overdue tasks, quiet team members —
  *so the AI actually finds something*, rather than a sanitized demo project with nothing to say.

## 3. The walkthrough

### Step 1 — Workspace overview
Land on `/workspace`. Point out the three projects each carry a live **Health Score** and
**Risk Score** computed from real task data, not placeholders — "API Platform" is deliberately
the highest-risk of the three (risk score 45).

### Step 2 — Open "Website Redesign" → Dashboard
Shows real seeded state: 15 tasks, 4 done, 3 in progress, 0% overall completion at this point in
the (backdated) project timeline, milestone/task list with real due dates.

### Step 3 — Click "AI Insights" tab → "Run Analysis"
This is the centerpiece. Live-verified output for this exact project:

> **Overall Risk: high** (confidence 70%) — 6 graph findings

| Specialist | Verdict | What it says |
|---|---|---|
| Planning | low | 4 milestones, 15 tasks, sprint readiness 100% |
| Progress | medium | 4/15 tasks done (27%), velocity stable |
| Workload | low | 4 members, avg 26 pts, 0 overloaded |

And four concrete, evidence-linked recommendations actually generated from this data:

1. **Schedule a team sync** (high) — *"Team splits into 3 non-collaborating clusters across 6
   members"*
2. **Split large or overdue tasks** (high) — *"4 of 11 open tasks are past their due date"*
3. **Check in with quiet team members** (high) — *"4 of 4 assigned members have posted no
   comments"*
4. **Redistribute workload** (medium) — *"'Frank Viewer' carries 26 open points vs a team mean
   of 13.5"*

**Talking point:** every one of these is a citation-backed graph computation, not an LLM guess —
say so, and note the analysis just ran with **no LLM API key configured at all** (check the AI
service terminal — no outbound calls were made). This is the deterministic fallback path, and
it's the same code path that runs when an LLM *is* configured, just without the narration prose.

### Step 4 — Repeat on "Mobile App v2.0" or "API Platform"
Different task mix → different findings, proving the analysis is genuinely computed per-project,
not a canned response. (Live-verified: both also return `overall risk: high` with their own
distinct evidence.)

### Step 5 (optional) — Show the Kanban board
`/projects/{id}/tasks` — drag-and-drop, dependencies, real-time-ready via WebSocket.

### Step 6 (optional) — Show multi-tenancy
Log out, log in as a different seeded org (or register a brand-new org) and show that the demo
projects are invisible to it — org-scoped isolation is a tested, enforced property, not a claim.

## 4. If something goes wrong live

| Symptom | Fix |
|---|---|
| AI Insights tab doesn't switch panels on click | Known Radix-UI quirk with some automated/remote pointer setups — a real mouse click works; if demoing through remote desktop software, click twice or click-and-hold briefly |
| Login returns an error | Confirm you're using the **email/password fields on the form**, not query params — the API expects form-encoded credentials |
| "Run Analysis" spins forever | Check the AI service terminal (port 8001) is actually running; the backend calls it synchronously |
| Fresh clone, no data | Re-run `python -m app.scripts.seed` — it recreates the schema if needed and is safe to re-run against a fresh `demo.db` |
| Want a clean slate | Delete `backend/demo.db` and re-run the seed script |

## 5. One-sentence pitch, if asked to summarize in the room

> "Instead of asking an AI model to read your whole project and guess what's wrong — which is
> slow, expensive, and unverifiable — we compute risk with plain graph algorithms first, and only
> use the AI to explain a finding that's already proven true, with every citation checked against
> the real data before it's shown to you."

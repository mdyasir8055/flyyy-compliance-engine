# FLYYY.AI Compliance Platform

Full-stack app: React/Vite frontend + FastAPI backend + PostgreSQL, with control
extraction, evidence reconciliation, and audit reasoning powered by Groq (Llama
3.3 70B).

```
├── src/                 # React frontend (Vite)
├── backend/
│   ├── app/
│   │   ├── main.py          # app entrypoint
│   │   ├── models.py        # SQLAlchemy models (Policy, Control, Scan, ScanResult)
│   │   ├── routers/         # /api/policies, /api/scans, /api/dashboard
│   │   └── services/        # PDF text extraction, Groq client, evaluator
│   └── tests/                # pytest suite for the deterministic evaluator
└── docker-compose.yml    # local Postgres + backend
```

## Architecture

```
                         ┌─────────────────────┐
   Policy PDF  ────────► │  pypdf text extract   │
                         └──────────┬───────────┘
                                    │ raw policy text
                                    ▼
                         ┌─────────────────────┐
                         │  Groq: extract_controls│  (LLM, non-deterministic)
                         └──────────┬───────────┘
                                    │ structured controls
                                    │ (target, metric, operator, threshold)
                                    ▼
                            [ stored in Postgres ]

   Evidence JSON ─────┐              │
   (any shape/naming) │              │
                       ▼              ▼
              ┌────────────────────────────┐
              │ Groq: reconcile_evidence      │  (LLM: WHICH asset/field
              │                                │   matches which control -
              │                                │   never decides pass/fail)
              └──────────────┬─────────────────┘
                              │ per-control: matched asset(s),
                              │ raw value, confidence, note
                              ▼
              ┌────────────────────────────┐
              │ evaluator.py: compare_value() │  (pure Python, deterministic,
              │            interpret_truthy() │   unit-tested, no LLM call)
              └──────────────┬─────────────────┘
                              │ Passed / Failed / Not Evaluated
                              ▼
              ┌────────────────────────────┐
              │ Groq: generate_audit_reasoning│  (LLM: explain the verdict
              │                                │   in plain English - does
              │                                │   NOT change the verdict)
              └──────────────┬─────────────────┘
                              ▼
                    [ ScanResult rows in Postgres ]
                              │
                              ▼
                     React dashboard / results UI
```

**Key design decision: AI never decides pass/fail.** Two LLM calls touch a
scan (evidence reconciliation, audit reasoning), but the actual comparison
(`92 >= 85` → fail) always runs in plain, deterministic Python
(`evaluator.py`). This is deliberate: a compliance tool has to produce the
same verdict on the same evidence every time, and that has to be explainable
without pointing at "the AI decided." See **Trade-offs** below for why this
split matters more than it might first look.

## How it works

1. **Upload a policy PDF** → backend extracts text (`pypdf`) → Groq reads it
   and extracts structured controls (`target`, `metric`, `operator`,
   `threshold`, `severity`) → stored in Postgres.
2. **Run a scan** → you provide evidence JSON in *any* shape (see below) →
   Groq reconciles each control against the evidence, identifying which
   asset(s) and which raw field apply, even if the naming doesn't match the
   policy's wording at all → `evaluator.py` deterministically compares each
   matched value against the control's threshold → Groq writes a short,
   plain-English audit-reasoning sentence per result (this step never
   changes the verdict, only explains it).
3. **Dashboard / results** → real numbers pulled from Postgres.

## 1. Get a free Groq API key

Sign up at https://console.groq.com/keys and copy an API key. Groq's free
tier is generous and fast — this app uses `llama-3.3-70b-versatile`.

## 2. Run locally

### Backend + Postgres (Docker)

```bash
cp backend/.env.example backend/.env   # then edit GROQ_API_KEY
# Docker Compose auto-loads a root-level .env for variable substitution -
# add GROQ_API_KEY=your_key_here to a .env file in the project root too,
# or export it in your shell before running the command below.
docker compose up --build
```

This starts Postgres on `5432` and the API on `http://localhost:8000`
(docs at `http://localhost:8000/docs`). Tables are auto-created on startup.

### Backend without Docker

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL to point at your own Postgres, and GROQ_API_KEY
uvicorn app.main:app --reload
```

### Frontend

```bash
cp .env.example .env   # VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

Open the printed local URL (usually `http://localhost:5173`).

### Tests

```bash
cd backend
pip install pytest
pytest tests/ -v
```

Covers the deterministic evaluation core (`compare_value`, `interpret_truthy`,
`find_asset`) — the one part of the pipeline that must never be
non-deterministic. Includes regression tests for real bugs found during
development (see Trade-offs section).

## 3. Deploy

**Backend + Postgres — Render (free tier works)**
1. Push this repo to GitHub.
2. On Render: New → PostgreSQL → copy the "Internal Database URL".
3. New → Web Service → point at `backend/`, set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Env vars: `DATABASE_URL` (from step 2), `GROQ_API_KEY`, `GROQ_MODEL=llama-3.3-70b-versatile`,
     `CORS_ORIGINS=https://your-frontend-domain.com`
4. Railway and Fly.io work the same way if you prefer those — the `Dockerfile`
   in `backend/` is deploy-ready for any container host.

**Frontend — Vercel or Netlify**
1. Import the repo, set build command `npm run build`, output dir `dist`.
2. Set env var `VITE_API_URL=https://your-backend-url.onrender.com`.

## API reference (once running)

Interactive docs: `GET /docs` (Swagger UI) or `/redoc`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/policies` | list policies |
| GET | `/api/policies/{id}` | policy + its controls |
| POST | `/api/policies/upload` | upload PDF, AI-extract controls |
| DELETE | `/api/policies/{id}` | delete policy |
| POST | `/api/policies/{id}/controls` | add a control |
| PUT | `/api/policies/{id}/controls/{cid}` | edit a control |
| DELETE | `/api/policies/{id}/controls/{cid}` | delete a control |
| GET | `/api/scans` | list scans |
| POST | `/api/scans` | run a scan (`policy_id` + `evidence` JSON) |
| GET | `/api/scans/{id}` | scan + results |
| GET | `/api/dashboard/summary` | dashboard totals |

## Evidence JSON format (for running a scan)

The evaluation pipeline is designed to accept evidence in **any reasonable
shape** — different key names, nested vs. flat metrics, different asset
identifier fields — because real infrastructure inventory tools (CSPM tools,
cloud APIs, CMDBs) never agree on a schema, and a policy PDF almost never
names specific servers, only categories of them (e.g. "production database
servers", not "prod-db-01"). All of these are handled correctly:

```json
{
  "assets": [
    { "name": "production_database_server", "cpu_utilization": 92, "memory_utilization": 68 }
  ]
}
```

```json
{
  "scan_id": "SCAN-2026-0812",
  "environment": "production",
  "assets": [
    {
      "asset_id": "prod-db-server-01",
      "asset_type": "database_server",
      "metrics": { "cpu_utilization": 92, "auto_scaling_enabled": true }
    }
  ]
}
```

```json
{
  "assets": [
    { "asset_id": "web-fleet-01", "kind": "compute", "processorLoadPct": 78, "scalingPolicy": "elastic" }
  ]
}
```

An AI reconciliation step (`services/groq_client.py::reconcile_evidence`)
maps each extracted control to the right asset(s) and the right field,
regardless of naming. See **Trade-offs** below for exactly how this works,
its limits, and how failures are handled.

If a control genuinely has no matching evidence anywhere, the result is
**"Not Evaluated"**, never a silent pass or an unearned fail — evaluated per
the "missing evidence must be reported as NOT EVALUABLE" principle common to
real compliance policies (and to the sample policy used during development).

## Trade-offs, limitations, and what I'd do with more time

**Why AI matches evidence but never grades it.** Early versions of this app
required a control's `target` to exactly match an asset's `name` string
(`production_database_server` == `production_database_server`). This breaks
immediately against real evidence, because policies describe *categories*
("production database servers") while real inventory data uses concrete,
inconsistent identifiers (`prod-db-01`, `db-server-east-1`, `asset_id`
instead of `name`, nested `metrics` objects instead of flat fields). I
replaced the exact-match step with an LLM call that reconciles controls to
evidence semantically — but I deliberately kept the actual pass/fail
comparison in plain Python (`evaluator.py::compare_value`), never inside the
LLM call. A compliance verdict has to be reproducible and explainable on
its own terms ("92 >= 85, so this failed"), not "the AI said so" — and LLM
output isn't guaranteed to be identical across two runs of the same input.

**A real bug this approach caught: LLMs don't reliably include every field
you ask for.** The reconciliation prompt originally asked Groq to return an
extra `boolean_interpretation` field for yes/no controls, so that evidence
like `scalingPolicy: "elastic"` (which means "auto-scaling is enabled", but
isn't literally the word `true`) would grade correctly. In testing, Groq
sometimes omitted that field on some matches within the same response,
causing correct evidence to be reported as a false failure. Rather than
just prompt-engineer around it and hope, I added a second layer:
`evaluator.py::interpret_truthy()`, a small, fixed word list
(`elastic`/`daily`/`enabled` → true, `none`/`disabled`/`manual` → false)
that runs in plain code as a fallback whenever the AI's own interpretation
is missing. This is covered by regression tests in `backend/tests/` so it
can't silently break again. The general lesson: for anything actually used
to make a decision, don't trust an LLM to always emit a specific field
shape — validate/fallback in code.

**Low-confidence matches are never silently trusted.** If the reconciliation
step is unsure which asset/field a control maps to, the result is reported
as "Not Evaluated — needs manual review" rather than guessed at. This
mirrors how a human auditor should treat ambiguous evidence.

**Known limitations:**
- The reconciliation step adds one extra Groq call per scan (latency + API
  cost), on top of the control-extraction and audit-reasoning calls. For a
  policy with many controls and many assets, this could be optimized by
  batching or caching reconciliation results across repeat scans of the
  same policy/evidence shape.
- The word list in `interpret_truthy()` is deliberately small and English-only;
  it covers the common cases seen during testing, not every possible phrasing.
- There's no retry/backoff on Groq API failures — a failed call currently
  falls back to the legacy exact-match evaluator rather than retrying,
  which is safe but means a transient Groq outage degrades the scan's
  matching quality for that run rather than pausing to retry.
- No authentication/multi-tenancy — out of scope for this assignment, but
  would be a first requirement for a real multi-customer product.
- With more time: cache reconciliation results, add confidence-threshold
  configuration, support DOCX policies (currently PDF only, though
  `pdf_extract.py` is the only piece that would need to change), and add
  integration tests against a real (or mocked) Groq response for the full
  scan endpoint, not just the evaluator's pure functions.
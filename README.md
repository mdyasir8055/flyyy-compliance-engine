# FLYYY.AI Compliance Platform

An end-to-end compliance evaluation web app: upload an unstructured policy PDF,
extract it into structured, machine-evaluatable controls, evaluate arbitrary
evidence JSON against those controls, and get an explainable pass/fail
compliance verdict per control.

**Live demo:**
- Frontend: https://flyyy-compliance-engine.vercel.app
- Backend API docs: https://flyyy-compliance-engine.onrender.com/docs

*(Backend is on Render's free tier, which spins down after ~15 minutes of
inactivity - the first request after a gap can take 30-60 seconds to wake up.
This is a hosting-tier trade-off, not a bug.)*

---

## Requirements checklist

### Core requirements

| Requirement | Status | Notes |
|---|---|---|
| Language: Python | ✅ | FastAPI backend, Python 3.12 |
| Backend: FastAPI | ✅ | `backend/app/` |
| Frontend: React.js | ✅ | React 19 + Vite (Vite chosen over Next.js/Angular - a plain SPA, no server-side rendering needed for this app) |
| Database: RDBMS, PostgreSQL preferred | ✅ | SQLAlchemy + Postgres, both locally (Docker) and in production (Render) |
| Repository: public GitHub repo | ✅ | this repo |
| Deployment: deployed link, if possible | ✅ | both links above, live |
| Agent Framework: only if it adds clear value | ✅ (deliberately not used) | Direct Groq API calls are sufficient here - no multi-step agentic reasoning, tool use, or orchestration is needed for extraction/reconciliation/reasoning, so adding LangGraph or similar would be unjustified complexity, not a missing capability |
| System Design: architecture in README | ✅ | see **Architecture** below |
| Code Quality | ✅ | see **Engineering quality notes** below |

### Minimal UI requirements

| Screen | Requirement | Status |
|---|---|---|
| **1. Policy Upload & Extraction Preview** | Drag-and-drop/file selector for PDF | ✅ |
| | Extracted rules view: Control ID, Target, Metric, Condition/Threshold | ✅ (also shows Operator and Severity) |
| **2. Compliance Scan & Results Dashboard** | Evidence input (paste/upload JSON) | ✅ |
| | Trigger scan button | ✅ |
| | Results dashboard: overall status, asset-level checks, plain-text audit reasoning | ✅ |

### Verified against the assignment's own worked example

The assignment's problem statement includes a concrete input/output example.
This exact example was run against the live app as a correctness check, not
just implemented against:

**Input policy text:** *"Our production application and database servers are
required to operate with CPU utilization below 85%... We also keep
auto-scaling enabled..."*

**Input evidence (assignment's own literal JSON, unmodified):**
```json
{ "scan_id": "SCAN-2026-0812", "environment": "production",
  "assets": [{ "asset_id": "prod-db-server-01", "asset_type": "database_server",
               "metrics": { "cpu_utilization": 92, "auto_scaling_enabled": true } }] }
```

**Assignment's stated expected result:** CPU check Non-Compliant (92% > 85%),
auto-scaling check Compliant, overall status Non-Compliant.

**Actual app output:** CPU control → Failed, actual `92`. Auto-scaling
control → Passed, actual `True`. Overall status → At Risk (this app's
equivalent label for non-compliant). **Exact match**, including correctly
handling the `asset_id` + nested `metrics` structure the assignment's example
uses - a structure the evaluation engine does not hardcode against (see
Trade-offs below for why that mattered).

---

## Architecture

![Architecture diagram](flyyy-ai-compliance-platform-fullstack\image.png)

*(Excalidraw diagram: PDF text extraction → chunked control extraction via
Groq → merge/de-dupe → Postgres, then evidence JSON → Groq reconciliation
(matches controls to evidence) → deterministic Python evaluator (pass/fail,
bold-bordered to mark it as the one non-AI step) → Groq audit reasoning →
Postgres → React dashboard.)

**Key design decision: AI never decides pass/fail.** Three separate LLM calls
touch a scan (chunked control extraction, evidence reconciliation, audit
reasoning), but the actual comparison (`92 >= 85` → fail) always runs in
plain, deterministic Python (`evaluator.py`). A compliance verdict has to be
reproducible and explainable on its own terms, not "the AI said so" - this is
the direct answer to the assignment's core question of how to convert
unstructured policy language into rules that can be evaluated consistently.

**Why this isn't "just a keyword extractor with a few hardcoded conditions"**
(the specific anti-pattern the assignment calls out): there is no
policy-specific or evidence-specific logic anywhere in this codebase. The
same extraction, reconciliation, and evaluation code handled a one-paragraph
policy, a 32-page/48-control policy spanning 16 unrelated domains (security,
HR, AI governance, disaster recovery, etc.), and evidence in at least four
different JSON shapes/naming conventions during testing - all without a
single line of policy- or format-specific code.

## Engineering quality notes

- **Deterministic core is unit-tested** (`backend/tests/test_evaluator.py`) -
  the comparison logic, boolean-phrase interpretation, and legacy
  asset-lookup path all have direct test coverage, including regression
  tests for bugs found during manual testing.
- **Consistent error handling under real API failures**, not just the happy
  path: both LLM-dependent pipeline stages (extraction, reconciliation) retry
  with increasing backoff on rate limits, log failures instead of swallowing
  them, and degrade gracefully (a failed reconciliation falls back to
  exact-match evaluation rather than crashing the scan).
- **Consistent naming and structure**: routers/services/schemas/models are
  cleanly separated in the backend; the frontend's API client is centralized
  in `src/api.ts` rather than scattered fetch calls.
- **No dead code or unused scaffolding** - the repository was cleaned of an
  unused Next.js/shadcn template that shipped with the original project setup
  but was never part of the actual (Vite-based) application.

## How it works

1. **Upload a policy PDF** → text extracted (`pypdf`) → split into chunks →
   each chunk sent to Groq for control extraction, with automatic retry and
   backoff if the API is rate-limited → results merged and de-duplicated →
   stored in Postgres. This handles policy documents of any length.
2. **Run a scan** → provide evidence JSON in *any* shape → Groq semantically
   reconciles each control against the evidence (same retry/backoff
   protection) → `evaluator.py` deterministically compares each matched value
   against the control's threshold → Groq writes a plain-English audit
   reasoning sentence per result (never changes the verdict, only explains it).
3. **Dashboard / results** → real numbers from Postgres, filterable by
   status, filterable by date range, searchable policy list, with delete and
   full-reset controls for managing test data.

## 1. Get a free Groq API key

Sign up at https://console.groq.com/keys. This app uses `openai/gpt-oss-120b`
(see Trade-offs below for why the model is configurable rather than hardcoded).

## 2. Run locally

### Backend + Postgres (Docker)

```bash
cp backend/.env.example backend/.env   # then edit GROQ_API_KEY
```
Docker Compose reads variable substitution from a **root-level** `.env` file
(same folder as `docker-compose.yml`), not `backend/.env` - add your key
there too:
```
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-120b
```
```bash
docker compose up --build
```
Starts Postgres on `5432` and the API on `http://localhost:8000` (docs at
`/docs`). Tables are auto-created on startup.

### Backend without Docker

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL and GROQ_API_KEY
uvicorn app.main:app --reload
```

### Frontend

```bash
cp .env.example .env   # VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

### Tests

```bash
cd backend
pip install pytest
pytest tests/ -v
```
Covers the deterministic evaluation core (`compare_value`, `interpret_truthy`,
`find_asset`), including regression tests for real bugs found during
development.

## 3. Deployment

Live at the links above. Deployed as:
- **Backend + Postgres:** Render (free tier), Docker-based web service
- **Frontend:** Vercel, static Vite build

To redeploy your own copy: create a Postgres instance and a Docker-based web
service on Render pointing at `backend/` (Dockerfile path `backend/Dockerfile`),
set `DATABASE_URL`, `GROQ_API_KEY`, `GROQ_MODEL`, and `CORS_ORIGINS` as env
vars; then import the repo root into Vercel as a Vite project with
`VITE_API_URL` pointing at the Render backend URL, and update `CORS_ORIGINS`
on Render to match the real Vercel URL once deployed.

## API reference (once running)

Interactive docs: `GET /docs` (Swagger UI) or `/redoc`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/policies` | list policies |
| GET | `/api/policies/{id}` | policy + its controls |
| POST | `/api/policies/upload` | upload PDF, AI-extract controls (chunked) |
| DELETE | `/api/policies/{id}` | delete policy (cascades to its controls/scans) |
| POST | `/api/policies/{id}/controls` | add a control |
| PUT | `/api/policies/{id}/controls/{cid}` | edit a control |
| DELETE | `/api/policies/{id}/controls/{cid}` | delete a control |
| GET | `/api/scans?start_date=&end_date=` | list scans, optional date-range filter |
| POST | `/api/scans` | run a scan (`policy_id` + `evidence` JSON) |
| GET | `/api/scans/{id}` | scan + results |
| DELETE | `/api/scans/{id}` | delete a scan |
| GET | `/api/dashboard/summary?start_date=&end_date=` | dashboard totals, optional date-range filter |
| DELETE | `/api/dashboard/reset` | wipe all data (policies, controls, scans, results) |

## Evidence JSON format (for running a scan)

The evaluation pipeline accepts evidence in **any reasonable shape** -
different key names, nested vs. flat metrics, different asset identifier
fields - because real infrastructure inventory data never agrees on a schema,
and a policy PDF almost never names specific servers, only categories of them.
All of these are handled correctly:

```json
{ "assets": [{ "name": "production_database_server", "cpu_utilization": 92 }] }
```

```json
{
  "assets": [{
    "asset_id": "prod-db-server-01",
    "asset_type": "database_server",
    "metrics": { "cpu_utilization": 92, "auto_scaling_enabled": true }
  }]
}
```

```json
{ "assets": [{ "asset_id": "web-fleet-01", "kind": "compute", "scalingPolicy": "elastic" }] }
```

An AI reconciliation step (`services/groq_client.py::reconcile_evidence`)
maps each control to the right asset(s) and field, regardless of naming. If a
control genuinely has no matching evidence, the result is **"Not Evaluated,"**
never a silent pass or an unearned fail.

## How this maps to the stated evaluation criteria

| Criterion | Where it's addressed |
|---|---|
| **Problem understanding** | The core design decision (AI matches, code grades) directly targets the assignment's stated challenge: policies are unstructured and vary per customer, hardcoded logic doesn't scale, but grading still has to be deterministic and explainable. |
| **Depth of technical research** | Trade-offs section documents three real bugs found through actual testing against the assignment's own example evidence format and a 32-page stress-test document: input truncation silently dropping content, an LLM unreliably omitting a requested JSON field, and a missing retry path causing silent fallback to brittle exact-name matching. |
| **Engineering quality** | See **Engineering quality notes** above; deterministic core is unit-tested and isolated from all non-deterministic LLM calls. |
| **System design** | Architecture diagram above; three-stage LLM pipeline (extract → reconcile → explain) kept strictly separate from the one deterministic grading stage. |
| **Quality of implementation** | Chunked extraction scales to policies of any length; evidence reconciliation handles arbitrary JSON shapes, verified against the assignment's own literal example; low-confidence AI matches are surfaced as "needs review" rather than silently trusted. |
| **Ability to reason about trade-offs** | See Trade-offs section - each fix documents what it costs (latency, complexity) alongside what it solves. |
| **Handling of edge cases** | Missing evidence → "Not Evaluated" (never silent pass/fail); non-literal boolean phrasing ("elastic", "daily") handled via AI interpretation + a deterministic word-list fallback; rate-limit failures retried with backoff instead of failing the whole scan; one bad chunk can't take down extraction of the rest of the document. |
| **Clarity of documentation** | This section, the requirements checklist, the architecture diagram, and the Trade-offs section exist specifically to make the reasoning legible rather than requiring a read of the full commit history. |
| **Ability to explain why a particular approach was chosen** | Every major decision below is written as "considered X, chose Y, because Z" rather than just describing the final state. |
| **Ability to identify limitations and improve the solution** | Known Limitations subsection lists specific, concrete gaps rather than a generic disclaimer. |

## Trade-offs, limitations, and what I'd do with more time

**Why AI matches evidence but never grades it.** An early version of this app
required a control's `target` to exactly match an asset's `name` string. This
breaks immediately against real evidence: policies describe *categories*
("production database servers"), while real inventory data uses concrete,
inconsistent identifiers and structures. I replaced the exact-match step with
an LLM call that reconciles controls to evidence semantically, but kept the
actual pass/fail comparison in plain Python (`evaluator.py::compare_value`) -
a compliance verdict has to be reproducible on its own terms, and LLM output
isn't guaranteed identical across runs of the same input (confirmed directly:
re-extracting the same 32-page test policy twice produced slightly different
control wording each time, while grading logic remained unaffected).

**Large policy documents silently lost content - found via a deliberate stress
test.** Initial extraction truncated policy text to the first 12,000
characters before sending it to the model, with no warning to the user. A
32-page, 48-control test document exposed this concretely: only 9 controls
from the first 3 of 16 sections were extracted, with the remaining 13
sections - including the entire AI/ML governance section - silently dropped.
Fixed by splitting the document into ~8,000-character chunks, extracting each
independently, and merging/de-duplicating results by `(target, metric)`. This
scales to documents of any length, at the cost of one Groq call per chunk
instead of one call total.

**Free-tier rate limits required real retry logic, not just chunking.** Once
chunking was in place, rapid sequential calls for a large document still hit
Groq's per-minute token rate limit in aggregate, and any chunk that failed was
being silently swallowed. Fixed with an explicit retry loop (up to 4
attempts, 10/20/30-second increasing backoff) plus logging, so failures are
visible in server logs instead of invisible. **A related gap this surfaced:**
the evidence-reconciliation step initially had *no* retry logic at all,
unlike extraction - so under the same rate-limit pressure, a single failed
reconciliation call would silently fall back to strict exact-name matching,
producing a wave of false "Not Evaluated" results even when semantically
correct matches existed. This was caught by re-running the same test policy
twice and noticing the AI's own extraction wording changed between runs while
grading results did not adapt correctly - the fix applies the same
retry/backoff pattern to reconciliation that extraction already had.

**A model I depended on was deprecated mid-project.** The originally-used
`llama-3.3-70b-versatile` was shut down by Groq during development, causing a
404 on every request with no prior warning built into the app. Switched to
`openai/gpt-oss-120b` and made the model configurable via environment
variable with a safe default, rather than hardcoded, so a future deprecation
doesn't require a code change to recover from - only an environment variable
update.

**Low-confidence matches are never silently trusted.** If reconciliation is
unsure which asset/field a control maps to, the result is "Not Evaluated -
needs manual review" rather than guessed at, mirroring how a human auditor
should treat ambiguous evidence.

**Known limitations:**
- Chunked extraction and reconciliation add real latency under rate-limit
  pressure - a large document with several failing chunks can take minutes,
  not seconds. A background job queue (rather than a synchronous request)
  would make this invisible to the user instead of a long-held HTTP request.
- The `interpret_truthy()` word list for non-literal boolean phrasing is
  deliberately small and English-only; it covers cases seen during testing,
  not every possible phrasing.
- No authentication/multi-tenancy - out of scope for this assignment, but
  would be a first requirement for a real multi-customer product.
- Render's free tier spins down on inactivity, adding cold-start latency to
  the live demo after idle periods.
- No formal database migration system - schema changes rely on
  `Base.metadata.create_all()`, which creates missing tables but not missing
  columns on existing ones. Acceptable for this assignment's scope; a real
  product would need Alembic or similar before its second schema change.
- With more time: cache reconciliation results per policy/evidence-shape
  pair to reduce repeat-scan latency and cost; parallelize chunk extraction
  calls instead of running them sequentially (traded off against staying
  under rate limits); add integration tests against a mocked Groq response
  for the full scan endpoint, not just the evaluator's pure functions;
  support DOCX policies in addition to PDF; add a formal migration tool.  
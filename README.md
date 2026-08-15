# FLYYY.AI Compliance Platform

Full-stack app: React/Vite frontend + FastAPI backend + PostgreSQL, with control
extraction and audit reasoning powered by Groq (Llama 3.3 70B).

```
├── src/                 # React frontend (Vite)
├── backend/             # FastAPI backend
│   └── app/
│       ├── main.py          # app entrypoint
│       ├── models.py        # SQLAlchemy models (Policy, Control, Scan, ScanResult)
│       ├── routers/         # /api/policies, /api/scans, /api/dashboard
│       └── services/        # PDF text extraction, Groq client, evaluator
└── docker-compose.yml    # local Postgres + backend
```

## How it works

1. **Upload a policy PDF** → backend extracts text (pypdf) → sends it to Groq
   (Llama 3.3 70B) → gets back structured controls (target, metric, operator,
   threshold, severity) → stores policy + controls in Postgres.
2. **Run a scan** → you provide evidence JSON (asset name + metric values) →
   backend deterministically compares each control's rule against the
   evidence → Groq writes a short audit-reasoning sentence per result.
3. **Dashboard / results** → real numbers pulled from Postgres.

## 1. Get a free Groq API key

Sign up at https://console.groq.com/keys and copy an API key. Groq's free
tier is generous and fast — this app uses `llama-3.3-70b-versatile`.

## 2. Run locally

### Backend + Postgres (Docker)

```bash
cp backend/.env.example backend/.env   # then edit GROQ_API_KEY
export GROQ_API_KEY=your_key_here
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

```json
{
  "assets": [
    { "name": "production_database_server", "cpu_utilization": 92, "memory_utilization": 68 },
    { "name": "admin_users", "mfa_enabled": true }
  ]
}
```

Each control's `target` must match an asset `name`, and `metric` must match
a key on that asset. Missing target/metric → result is "Not Evaluated".

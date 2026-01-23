# prototype-ai-agent-social

Prototype with:
- Frontend (still mostly mock): onboarding → search → hard-coded journeys → matching list → profile reasons/badges → chat + calendar invite (mock).
- Backend (new): orchestrator + AI-generated (imaginary) “find people / find things” APIs (see `backend/`).

## Run locally

```bash
cd prototype-web
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Flow:
- Go to `/app` → type free-form input → it routes to `/app/agent` (orchestrator + card deck + results).

LLM:
- Uses Gemini `gemini-2.5-flash-lite` for orchestration and generating results.
- You must set `GEMINI_API_KEY` (AI Studio) OR Vertex AI credentials (`GOOGLE_CLOUD_PROJECT` + service account file).

## Deploy on Render

Use **Blueprint** (not “Web Service”) because this repo deploys **two services** from `render.yaml`:
- `agent-social-api` (FastAPI backend)
- `agent-social-prototype` (static frontend) and it needs the API URL injected via `VITE_API_BASE_URL`.

Steps:
1) Render → New → **Blueprint** → connect this repo (branch `main`)
2) After services are created, set Gemini creds on **`agent-social-api`**:
   - simplest: set env var `GEMINI_API_KEY`
   - or Vertex AI: set `GOOGLE_CLOUD_PROJECT` and add a Secret File at `/etc/secrets/google-credentials.json`
3) Redeploy `agent-social-api` (then `agent-social-prototype` if you changed frontend env vars)

## Deploy on Render

- Uses `render.yaml`:
  - Static frontend (`agent-social-prototype`)
  - Python API (`agent-social-api`)

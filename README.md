# prototype-ai-agent-social

Prototype with:
- Frontend (still mostly mock): onboarding → search → hard-coded journeys → matching list → profile reasons/badges → chat + calendar invite (mock).
- Backend (new): orchestrator + mock “find people / find things” APIs (see `backend/`).

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

## Deploy on Render

- Uses `render.yaml`:
  - Static frontend (`agent-social-prototype`)
  - Python API (`agent-social-api`)

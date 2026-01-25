# agent-social backend (prototype)

Implements a minimal backend for the “AI social agent prototype” flow:

- `POST /api/v1/find-people`: mock “find people”
- `POST /api/v1/find-things`: mock “find activities/groups”
- `POST /api/v1/orchestrate`: session orchestrator (history + memory) → planner → tool calls → UI blocks/results
- `GET /api/v1/health`

## Run locally

```bash
cd prototype-ai-agent-social/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Notes:
- Sessions are stored in memory (prototype). On Render restarts/scale-out, session state is not durable.
- Tool library (fat tools):
  - `intelligent_discovery`: searches/recommends people or events (AI-generated, then stored in session memory)
  - `deep_profile_analysis`: analyzes previously generated people/events by ID (detail/compare/compatibility)
- Planner uses Gemini (`gemini-2.5-flash-lite`) when configured, and falls back to a small heuristic planner when not.
- You must provide Gemini credentials via `GEMINI_API_KEY` (AI Studio) OR Vertex AI service account + `GOOGLE_CLOUD_PROJECT`.

## API overview

### Orchestrator

`POST /api/v1/orchestrate`

Request:
```json
{
  "sessionId": null,
  "message": "我在上海想找女生一起喝一杯，25-32岁，最好是设计师"
}
```

Response (examples):
- `action="chat"`: assistant asks clarifying questions (intent unknown)
- `action="form"`: returns a `deck` (multiple cards) for missing fields
- `action="results"`: returns `results` (people or groups)

Card submission (user fills a card and clicks ✅):
```json
{
  "sessionId": "…",
  "submit": {
    "cardId": "location",
    "data": { "location": "Shanghai" }
  }
}
```

### Find people (mock)

`POST /api/v1/find-people`

```json
{
  "location": "Shanghai",
  "genders": ["female"],
  "ageRange": { "min": 25, "max": 32 },
  "occupation": "Designer"
}
```

### Find things (mock)

`POST /api/v1/find-things`

```json
{
  "title": "Weekend hiking",
  "neededCount": 2
}
```

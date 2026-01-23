# agent-social backend (prototype)

Implements a minimal backend for the “AI social agent prototype” flow:

- `POST /api/v1/find-people`: mock “find people”
- `POST /api/v1/find-things`: mock “find activities/groups”
- `POST /api/v1/orchestrate`: intent routing + missing-info form + (if complete) calls the mock find APIs
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
- If you set `ENABLE_REAL_LLM=true` + one of `XAI_API_KEY` or `OPENAI_API_KEY`, `/api/v1/orchestrate` will use a real LLM to parse intent/slots; otherwise it falls back to heuristics + companion-style templates.

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

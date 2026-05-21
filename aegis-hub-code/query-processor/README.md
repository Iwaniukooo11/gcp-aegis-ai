# Query Processor

Cloud Run service that handles operator questions about incidents and surfaces
recent incident lists, with Vertex AI-powered analysis backed by Firestore
conversation history.

## Responsibilities

- `GET /v1/incidents/latest?limit=N` — BigQuery SELECT, no AI, no Firestore
- `POST /v1/incidents/{incident_id}/query` — full 3-step Gemini pipeline:
  1. Load Firestore session, append user turn
  2. Gemini 1 — decide which Cloud Monitoring metrics to fetch
  3. Execute Cloud Monitoring queries against the client project
  4. Gemini 2 — analyze metric results, produce root-cause candidates
  5. Gemini 3 — format Slack mrkdwn response
  6. Append model turn to Firestore session

## Vertex AI + Firestore pattern

Firestore is the sole conversation store. Vertex is stateless — on every
request, the full `messages[]` array is read from Firestore and converted to
`Content` history objects before calling Gemini:

```python
def messages_to_contents(messages: list[dict]) -> list[Content]:
    return [
        Content(
            role="user" if m["role"] == "user" else "model",
            parts=[Part.from_text(m["content"])],
        )
        for m in messages
    ]
```

Steps 1 and 2 use `generate_content` with `response_mime_type="application/json"`.
Step 3 produces a plain Slack mrkdwn string.

## Local dev

```bash
cp .env.example .env
gcloud auth application-default login
uv run uvicorn app.main:app --reload --port 8081
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GCP_PROJECT` | yes | Hub project ID |
| `GCP_REGION` | yes | Vertex AI region |
| `BIGQUERY_DATASET` | yes | `aegis_incidents` |
| `BIGQUERY_INCIDENTS_TABLE` | yes | `incidents` |
| `FIRESTORE_DATABASE` | yes | Firestore DB name |
| `ALLOWED_CLIENT_PROJECT_IDS` | no | Comma-separated project IDs for Monitoring queries |
| `VERTEX_MODEL` | no | Default: `gemini-2.5-flash` |
| `SESSION_TTL_HOURS` | no | Default: 24 |

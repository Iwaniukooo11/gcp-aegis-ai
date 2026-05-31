# Incident Analyzer

Cloud Run service that consumes Pub/Sub push messages from the Client Project
log sink, normalizes them into incidents, and alerts the SRE team via Slack.

## Responsibilities

- Receive authenticated Pub/Sub push on `POST /pubsub/push`
- Deduplicate redeliveries via Firestore `incident_receipts` collection
- Run 3× Gemini steps (normalize → classify → Slack alert text)
- Write one row to BigQuery `aegis_incidents.incidents`
- Create `sessions/{incident_id}` in Firestore (seed for Query Processor)
- POST alert payload to Slack Gateway `POST /v1/internal/incidents/alert`

## Vertex AI pattern

All three Gemini calls use **single-turn `generate_content`** — not `start_chat`.
The log payload is the full context; there is no prior conversation to replay.
Steps 1 and 2 use `response_mime_type="application/json"` for reliable JSON output.

```python
vertexai.init(project=GCP_PROJECT, location=GCP_REGION)
model = GenerativeModel(VERTEX_MODEL)
response = model.generate_content([system_prompt, user_prompt], generation_config=...)
```

## Firestore session seed

Before Slack handoff and final BigQuery insert, a `sessions/{incident_id}`
document is created with initial `messages: [{"role": "model", "content": "..."}]`,
`pod_name`, `log_timestamp`, `scenario`, `short_message`, `stack_trace_preview`,
`upstream_service`, `http_method`, `path`, and `status_code` from the source
Cloud Logging entry. This is the conversation history seed that Query Processor
appends user turns to later and the pod/time anchor for Cloud Monitoring
queries.

For the checkout demo, `path=/api/checkout` and `upstream_service=java-api`
are treated as a business dependency failure. Alerts should describe checkout
impact and pricing dependency symptoms, not the internal failure trigger.

## Incident ID format

`INC-YYYY-NNNNNN` (6-digit zero-padded sequence). Example: `INC-2026-000041`.

## Local dev

```bash
cp .env.example .env
# edit .env with real values
gcloud auth application-default login
uv run uvicorn app.main:app --reload --port 8080
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GCP_PROJECT` | yes | Hub project ID |
| `GCP_REGION` | yes | Vertex AI region |
| `BIGQUERY_DATASET` | yes | `aegis_incidents` |
| `BIGQUERY_INCIDENTS_TABLE` | yes | `incidents` |
| `FIRESTORE_DATABASE` | yes | Firestore DB name |
| `SLACK_GATEWAY_URL` | yes | Internal Slack Gateway Cloud Run URL |
| `VERTEX_MODEL` | no | Default: `gemini-2.5-flash` |
| `SESSION_TTL_HOURS` | no | Default: 24 |
| `RECEIPT_TTL_HOURS` | no | Default: 24 |

# Slack Gateway

Cloud Run service acting as a thin relay between Slack and internal Aegis Hub
services. No Firestore, BigQuery, Vertex AI, or Cloud Monitoring access.

## Responsibilities

- `POST /slack/events` — Slack Events API: handle `url_verification` and
  `app_mention`; return 200 immediately; process QP call asynchronously
- `POST /slack/commands` — `/aegis-latest-incidents` slash command; ack within
  3s and post full result via response_url
- `POST /v1/internal/incidents/alert` — receive alert payload from Incident
  Analyzer and post to `DEFAULT_SLACK_CHANNEL_ID`

## Message parsing

App mention parsing (extracting `INC-YYYY-NNNNNN` + question) happens here,
not in Query Processor. Regex: `INC-\d{4}-\d{6}`.

## OIDC outbound auth

All calls to Query Processor use Google OIDC:
```python
token = id_token.fetch_id_token(Request(), audience=QUERY_PROCESSOR_URL)
```
The `slack-gateway` service account must have `roles/run.invoker` on
the `aegis-query-processor` Cloud Run service.

## Local dev

```bash
cp .env.example .env
gcloud auth application-default login
uv run uvicorn app.main:app --reload --port 8082
```

Use [ngrok](https://ngrok.com) or similar to expose the local port for Slack
Events API verification.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | yes | From Secret Manager `slack-bot-token` |
| `SLACK_SIGNING_SECRET` | yes | From Secret Manager `slack-signing-secret` |
| `QUERY_PROCESSOR_URL` | yes | Internal Cloud Run URL for Query Processor |
| `DEFAULT_SLACK_CHANNEL_ID` | yes | Slack channel ID for incident alerts |
| `INTERNAL_ALERT_ALLOWED_SERVICE_ACCOUNT` | yes | Incident Analyzer service account allowed to call alert relay |
| `INCIDENT_ANALYZER_URL` | no | Used for potential future direct calls |
| `ENVIRONMENT` | no | Default: dev |

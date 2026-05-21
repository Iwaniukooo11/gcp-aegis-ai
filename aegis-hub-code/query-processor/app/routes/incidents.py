"""Query Processor incident routes.

GET  /v1/incidents/latest           — recent incidents from BigQuery (no Vertex)
POST /v1/incidents/{incident_id}/query  — Firestore-backed 3x Gemini pipeline
"""
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.integrations import (
    bigquery_incidents,
    firestore_sessions,
    metric_plan,
    monitoring,
    vertex,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


class QueryRequest(BaseModel):
    text: str


@router.get("/incidents/latest")
async def get_latest_incidents(limit: int = 10) -> dict:
    """Return the most recent successfully processed incidents from BigQuery."""
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
    try:
        rows = bigquery_incidents.get_latest_incidents(limit=limit)
    except Exception as exc:
        logger.error("BigQuery latest incidents query failed: %s", exc)
        raise HTTPException(status_code=500, detail="bigquery_query_failed") from exc

    now = datetime.now(tz=timezone.utc)

    def minutes_ago(created_at: object) -> int | None:
        if created_at is None:
            return None
        if isinstance(created_at, str):
            try:
                ts = datetime.fromisoformat(created_at)
            except ValueError:
                return None
        else:
            ts = created_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0, int((now - ts).total_seconds() / 60))

    incidents = [
        {
            "incident_id": r["incident_id"],
            "service_name": r.get("service_name"),
            "client_project_id": r.get("client_project_id"),
            "severity": r.get("severity"),
            "error_type": r.get("error_type"),
            "short_message": r.get("short_message"),
            "ai_summary": r.get("ai_summary"),
            "created_at": str(r.get("created_at")),
            "minutes_ago": minutes_ago(r.get("created_at")),
        }
        for r in rows
    ]
    return {"limit": limit, "count": len(incidents), "incidents": incidents}


@router.post("/incidents/{incident_id}/query")
async def query_incident(incident_id: str, body: QueryRequest) -> dict:
    """Run the 3-step Gemini pipeline for an operator question about an incident.

    Steps:
      1. Load Firestore session (404 if missing)
      2. Append user turn to messages
      3. Gemini 1 — metric plan
      4. Execute Cloud Monitoring queries
      5. Gemini 2 — analyze metric results
      6. Gemini 3 — format Slack response
      7. Append model turn; update Firestore TTL
    """
    start_ms = int(time.time() * 1000)

    session = firestore_sessions.get_session(incident_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "SESSION_NOT_FOUND", "incident_id": incident_id},
        )

    user_message = {"role": "user", "content": body.text}
    firestore_sessions.append_messages(incident_id, [user_message])

    messages_with_user = list(session.get("messages", [])) + [user_message]

    try:
        planned = vertex.plan_metrics(session, messages_with_user, body.text)
        metric_plan_body = metric_plan.supplement_metric_plan_for_question(
            planned, body.text, session
        )
    except Exception as exc:
        logger.error("Gemini metric plan failed for %s: %s", incident_id, exc)
        raise HTTPException(status_code=500, detail="gemini_metric_plan_failed") from exc

    metric_results: dict = {}
    metrics_fetched = False
    client_project_id = session.get("client_project_id", "")
    anchor_time = metric_plan.parse_session_anchor(session)
    if metric_plan_body.get("metrics") and client_project_id:
        try:
            metric_results = monitoring.execute_plan(
                client_project_id,
                metric_plan_body,
                anchor_time=anchor_time,
            )
            metrics_fetched = True
        except Exception as exc:
            logger.warning("Monitoring query failed for %s: %s", incident_id, exc)
            metric_results = {"error": str(exc)}

    metric_summary = metric_plan.summarize_metric_results(metric_results)

    try:
        analysis = vertex.analyze_metrics(
            session, messages_with_user, metric_plan_body, metric_results
        )
    except Exception as exc:
        logger.error("Gemini analysis failed for %s: %s", incident_id, exc)
        raise HTTPException(status_code=500, detail="gemini_analysis_failed") from exc

    try:
        slack_text = vertex.format_slack_response(
            incident_id, body.text, analysis, metric_summary
        )
    except Exception as exc:
        logger.error("Gemini Slack format failed for %s: %s", incident_id, exc)
        raise HTTPException(status_code=500, detail="gemini_format_failed") from exc

    model_message = {"role": "model", "content": slack_text}
    firestore_sessions.append_messages(incident_id, [model_message])

    elapsed_ms = int(time.time() * 1000) - start_ms
    return {
        "incident_id": incident_id,
        "slack_text": slack_text,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "session_updated": True,
        "metrics_fetched": metrics_fetched,
        "processing_ms": elapsed_ms,
    }

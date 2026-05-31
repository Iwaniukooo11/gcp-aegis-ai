"""BigQuery integration for Incident Analyzer.

Writes one row per real incident occurrence.
Retries are deduplication-protected via Firestore receipts — this module
only handles the actual insert and terminal-status updates.
"""
from datetime import datetime, timezone

from google.cloud import bigquery

from app.config import get_settings

_client: bigquery.Client | None = None


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=get_settings().gcp_project)
    return _client


def _table_ref() -> str:
    s = get_settings()
    return f"{s.gcp_project}.{s.bigquery_dataset}.{s.bigquery_incidents_table}"


def insert_incident(row: dict, insert_id: str | None = None) -> None:
    """Insert a single incident row into BigQuery.

    Expects a dict whose keys match the aegis_incidents.incidents schema.
    Raises on insert errors.
    """
    client = _get_client()
    kwargs = {"row_ids": [insert_id]} if insert_id else {}
    errors = client.insert_rows_json(_table_ref(), [row], **kwargs)
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")


def incident_exists_by_idempotency_key(idempotency_key: str) -> bool:
    """Return whether BigQuery already has an incident row for this idempotency key."""
    client = _get_client()
    query = (
        f"SELECT 1 FROM `{_table_ref()}` "
        "WHERE idempotency_key = @idempotency_key "
        "LIMIT 1"
    )
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("idempotency_key", "STRING", idempotency_key)
        ]
    )
    return next(iter(client.query(query, job_config=job_config)), None) is not None


def build_incident_row(
    incident_id: str,
    idempotency_key: str,
    event_id: str,
    source_log_insert_id: str,
    client_project_id: str,
    resource_type: str,
    cluster_name: str,
    namespace: str,
    service_name: str,
    pod_name: str,
    severity: str,
    error_type: str,
    short_message: str,
    stack_trace_preview: str,
    labels_json: str,
    ai_summary: str,
    ai_recommendation: str,
    terminal_status: str,
    terminal_failure_reason: str = "",
    slack_channel: str | None = None,
    slack_message_ts: str | None = None,
    first_alert_sent_at: str | None = None,
) -> dict:
    """Build a BigQuery row dict with all required and optional incident fields."""
    now = datetime.now(tz=timezone.utc).isoformat()
    return {
        "incident_id": incident_id,
        "idempotency_key": idempotency_key,
        "event_id": event_id,
        "source_log_insert_id": source_log_insert_id,
        "client_project_id": client_project_id,
        "resource_type": resource_type,
        "cluster_name": cluster_name,
        "namespace": namespace,
        "service_name": service_name,
        "pod_name": pod_name,
        "severity": severity,
        "error_type": error_type,
        "short_message": short_message,
        "stack_trace_preview": stack_trace_preview,
        "labels_json": labels_json,
        "ai_summary": ai_summary,
        "ai_recommendation": ai_recommendation,
        "slack_channel": slack_channel,
        "slack_message_ts": slack_message_ts,
        "created_at": now,
        "hub_received_at": now,
        "incident_persisted_at": now,
        "first_alert_sent_at": first_alert_sent_at,
        "ai_summary_completed_at": now if ai_summary else None,
        "processing_completed_at": now,
        "terminal_status": terminal_status,
        "terminal_failure_reason": terminal_failure_reason,
    }

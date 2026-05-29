"""BigQuery integration for Incident Analyzer.

Writes one row per real incident occurrence.
Retries resume from Firestore receipts — inserts are skipped when already persisted.
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


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_log_timestamp(raw: str) -> str | None:
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.isoformat()
    except ValueError:
        return None


def insert_incident(row: dict) -> None:
    """Insert a single incident row into BigQuery."""
    client = _get_client()
    errors = client.insert_rows_json(_table_ref(), [row])
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")


def update_incident_slack_delivery(
    incident_id: str,
    slack_channel: str,
    slack_message_ts: str,
    first_alert_sent_at: str | None = None,
) -> None:
    """Patch Slack delivery fields and processing completion after alert handoff."""
    sent_at = first_alert_sent_at or _iso_now()
    query = f"""
        UPDATE `{_table_ref()}`
        SET
            slack_channel = @slack_channel,
            slack_message_ts = @slack_message_ts,
            first_alert_sent_at = @first_alert_sent_at,
            processing_completed_at = @processing_completed_at
        WHERE incident_id = @incident_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("slack_channel", "STRING", slack_channel),
            bigquery.ScalarQueryParameter("slack_message_ts", "STRING", slack_message_ts),
            bigquery.ScalarQueryParameter("first_alert_sent_at", "TIMESTAMP", sent_at),
            bigquery.ScalarQueryParameter("processing_completed_at", "TIMESTAMP", _iso_now()),
            bigquery.ScalarQueryParameter("incident_id", "STRING", incident_id),
        ]
    )
    job = _get_client().query(query, job_config=job_config)
    job.result()


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
    hub_received_at: str | None = None,
    log_timestamp: str = "",
) -> dict:
    """Build a BigQuery row dict with distinct lifecycle timestamps."""
    received = hub_received_at or _iso_now()
    persisted = _iso_now()
    created = _parse_log_timestamp(log_timestamp) or received
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
        "slack_channel": None,
        "slack_message_ts": None,
        "created_at": created,
        "hub_received_at": received,
        "incident_persisted_at": persisted,
        "first_alert_sent_at": None,
        "ai_summary_completed_at": persisted if ai_summary else None,
        "processing_completed_at": None,
        "terminal_status": terminal_status,
        "terminal_failure_reason": terminal_failure_reason,
    }

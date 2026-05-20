"""BigQuery read integration for Query Processor.

Only reads incident rows — Query Processor never writes to BigQuery.
"""
from google.cloud import bigquery

from app.config import get_settings

_client: bigquery.Client | None = None


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=get_settings().gcp_project)
    return _client


def get_latest_incidents(limit: int = 10) -> list[dict]:
    """Return the most recent successfully processed incidents from BigQuery.

    Only rows with terminal_status = 'SUCCESS' are returned.
    Caller is responsible for formatting times as minutes_ago.
    """
    s = get_settings()
    table = f"`{s.gcp_project}.{s.bigquery_dataset}.{s.bigquery_incidents_table}`"
    query = f"""
        SELECT
            incident_id,
            service_name,
            client_project_id,
            severity,
            error_type,
            short_message,
            ai_summary,
            created_at
        FROM {table}
        WHERE terminal_status = 'SUCCESS'
        ORDER BY created_at DESC
        LIMIT @limit
    """
    job = _get_client().query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("limit", "INT64", limit)
            ]
        ),
    )
    return [dict(row) for row in job.result()]

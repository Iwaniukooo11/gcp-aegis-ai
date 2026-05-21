"""Vertex AI / Gemini integration for Query Processor.

Three specialized single-turn generate_content calls per query:
  1. Metric plan   — decide which Cloud Monitoring metrics to fetch
  2. Analysis      — root-cause and diagnosis from fetched metric results
  3. Slack format  — convert analysis to Slack mrkdwn

Firestore messages[] are mapped to Vertex Content history for calls #1 and #2
to give Gemini awareness of prior turns in the incident conversation.
"""
import json

import vertexai
from vertexai.generative_models import Content, GenerationConfig, GenerativeModel, Part

from app.config import get_settings
from app.integrations.metric_catalog import (
    ALLOWED_METRIC_TYPE_IDS,
    GCP_METRIC_TYPE_BY_ID,
    METRIC_PLAN_RESPONSE_SCHEMA,
    allowed_metrics_for_prompt,
)

_initialized = False


def _ensure_init() -> None:
    global _initialized
    if not _initialized:
        s = get_settings()
        vertexai.init(project=s.gcp_project, location=s.gcp_region)
        _initialized = True


def _get_model() -> GenerativeModel:
    _ensure_init()
    return GenerativeModel(get_settings().vertex_model)


def _build_k8s_container_filter(session: dict) -> str:
    parts = ['resource.type="k8s_container"']
    service_name = str(session.get("service_name") or "").strip()
    namespace = str(session.get("namespace") or "").strip()
    cluster_name = str(session.get("cluster_name") or "").strip()
    if service_name:
        parts.append(f'resource.labels.container_name="{service_name}"')
    if namespace:
        parts.append(f'resource.labels.namespace_name="{namespace}"')
    if cluster_name:
        parts.append(f'resource.labels.cluster_name="{cluster_name}"')
    return " AND ".join(parts)


def _normalize_metric_item(
    item: object,
    session: dict,
    window_minutes: int,
) -> dict | None:
    if not isinstance(item, dict):
        return None
    type_id = str(item.get("type") or "").strip()
    if type_id not in GCP_METRIC_TYPE_BY_ID:
        return None
    return {
        "metric_type": GCP_METRIC_TYPE_BY_ID[type_id],
        "type": type_id,
        "filter": _build_k8s_container_filter(session),
        "window_minutes": window_minutes,
    }


def _normalize_metric_plan(raw: object, session: dict | None = None) -> dict:
    """Coerce Gemini JSON into executor-ready MetricFetchPlan."""
    session = session or {}
    if not isinstance(raw, dict):
        return {"metrics": [], "rationale": "", "window_minutes": 30}
    try:
        plan_window = int(raw.get("window_minutes", 30))
    except (TypeError, ValueError):
        plan_window = 30
    plan_window = max(5, min(plan_window, 60))
    raw_metrics = raw.get("metrics")
    if not isinstance(raw_metrics, list):
        raw_metrics = []
    metrics = []
    for item in raw_metrics:
        spec = _normalize_metric_item(item, session, plan_window)
        if spec is not None:
            metrics.append(spec)
    return {
        "metrics": metrics,
        "rationale": str(raw.get("rationale", "") or ""),
        "window_minutes": plan_window,
    }


def _metric_planner_system_prompt() -> str:
    catalog = json.dumps(allowed_metrics_for_prompt(), indent=2)
    allowed = ", ".join(ALLOWED_METRIC_TYPE_IDS)
    return (
        "You are an SRE metric planner for a GKE mock client environment.\n"
        "Choose which allowlisted metrics to fetch from Cloud Monitoring.\n\n"
        "ALLOWLIST (only these type values are valid):\n"
        f"{catalog}\n\n"
        "Rules:\n"
        f"- Each metrics[].type must be one of: {allowed}.\n"
        "- Do not invent metric names or GCP paths; the service maps type to Monitoring.\n"
        "- Pick 0-3 metrics relevant to the user question and incident context.\n"
        "- window_minutes must be between 5 and 60.\n"
        "- Labels (container, namespace, cluster) are applied automatically from incident context.\n"
        "- Return JSON only, matching the response schema."
    )


def messages_to_contents(messages: list[dict]) -> list[Content]:
    """Convert Firestore messages[] to Vertex Content history objects.

    Firestore role "user" → Vertex role "user".
    Anything else (typically "model") → Vertex role "model".
    """
    return [
        Content(
            role="user" if m["role"] == "user" else "model",
            parts=[Part.from_text(m["content"])],
        )
        for m in messages
    ]


def plan_metrics(
    session: dict,
    messages: list[dict],
    user_question: str,
) -> dict:
    """Gemini step 1 — decide which allowlisted Cloud Monitoring metrics to fetch.

    Returns a MetricFetchPlan dict with keys:
      metrics: list of {type, metric_type, filter, window_minutes}
      rationale: string
      window_minutes: int
    """
    _ensure_init()
    model = GenerativeModel(
        get_settings().vertex_model,
        system_instruction=[_metric_planner_system_prompt()],
    )
    context_payload = {
        "incident_id": session.get("incident_id"),
        "service_name": session.get("service_name"),
        "client_project_id": session.get("client_project_id"),
        "cluster_name": session.get("cluster_name"),
        "namespace": session.get("namespace"),
        "error_type": session.get("error_type"),
        "ai_summary": session.get("ai_summary"),
        "user_question": user_question,
        "allowlisted_metric_types": list(ALLOWED_METRIC_TYPE_IDS),
    }
    history = messages_to_contents(messages[-10:])
    response = model.generate_content(
        history
        + [
            Content(
                role="user",
                parts=[
                    Part.from_text(
                        "Incident context:\n"
                        + json.dumps(context_payload)
                        + "\n\nSelect metrics to fetch from the allowlist."
                    )
                ],
            )
        ],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema=METRIC_PLAN_RESPONSE_SCHEMA,
            temperature=0.1,
        ),
    )
    return _normalize_metric_plan(json.loads(response.text), session)


def analyze_metrics(
    session: dict,
    messages: list[dict],
    metric_plan: dict,
    metric_results: dict,
) -> dict:
    """Gemini step 2 — analyze fetched metric results to identify root causes.

    Returns a dict with keys:
      root_cause_candidates: list of strings
      confidence: "high" | "medium" | "low"
      additional_signals_needed: list of strings
    """
    _ensure_init()
    system_prompt = (
        "You are an SRE root-cause analyst. "
        "Analyze the metric results for the incident and identify the most likely root causes. "
        "When metric_results contain CPU or memory series with points, describe utilization in "
        "root_cause_candidates or additional_signals_needed; do not claim metrics are missing "
        "when data is present. "
        "Return ONLY valid JSON with keys: "
        "root_cause_candidates (list of strings, most likely first), "
        "confidence (high|medium|low), "
        "additional_signals_needed (list of strings, can be empty)."
    )
    model = GenerativeModel(
        get_settings().vertex_model,
        system_instruction=[system_prompt],
    )
    analysis_payload = {
        "incident_id": session.get("incident_id"),
        "service_name": session.get("service_name"),
        "error_type": session.get("error_type"),
        "ai_summary": session.get("ai_summary"),
        "metric_plan": metric_plan,
        "metric_results": metric_results,
    }
    history = messages_to_contents(messages[-10:])
    response = model.generate_content(
        history
        + [
            Content(
                role="user",
                parts=[
                    Part.from_text(
                        "Metric data:\n" + json.dumps(analysis_payload, default=str)
                    )
                ],
            )
        ],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return json.loads(response.text)


def format_slack_response(
    incident_id: str,
    user_question: str,
    analysis: dict,
    metric_summary: dict | None = None,
) -> str:
    """Gemini step 3 — produce a concise Slack mrkdwn response.

    Returns a plain Slack mrkdwn string.
    """
    _ensure_init()
    system_prompt = (
        "You are formatting an SRE incident analysis response for Slack (mrkdwn). "
        "Be concise — max 8 lines. Use *bold* sparingly for key values. "
        "Answer the operator's question directly using metric_summary when it has status ok. "
        "For CPU questions, quote latest_value from kubernetes.io/container/cpu metrics. "
        "Only say CPU data is unavailable when metric_summary shows no_data or error for CPU. "
        "Then list root cause candidates. "
        "If confidence is low, say so clearly. "
        "Return ONLY the Slack mrkdwn string."
    )
    model = GenerativeModel(
        get_settings().vertex_model,
        system_instruction=[system_prompt],
    )
    payload = {
        "incident_id": incident_id,
        "user_question": user_question,
        "analysis": analysis,
        "metric_summary": metric_summary or {},
    }
    response = model.generate_content(
        [
            Content(
                role="user",
                parts=[Part.from_text(json.dumps(payload, default=str))],
            )
        ],
        generation_config=GenerationConfig(temperature=0.3),
    )
    return response.text.strip()

"""Vertex AI / Gemini integration for Query Processor."""
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


def build_k8s_container_filter(session: dict) -> str:
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


def _normalize_metric_item(item: object, session: dict, window_minutes: int) -> dict | None:
    if not isinstance(item, dict):
        return None
    type_id = str(item.get("type") or "").strip()
    if type_id not in GCP_METRIC_TYPE_BY_ID:
        return None
    return {
        "metric_type": GCP_METRIC_TYPE_BY_ID[type_id],
        "type": type_id,
        "filter": build_k8s_container_filter(session),
        "window_minutes": window_minutes,
    }


def _normalize_metric_plan(raw: object, session: dict | None = None) -> dict:
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
        "Choose which metrics to fetch from Cloud Monitoring.\n\n"
        "ALLOWLIST (pick only these type values):\n"
        f"{catalog}\n\n"
        "Rules:\n"
        f"- Each metrics[].type must be one of: {allowed}.\n"
        "- Pick 0-3 metrics relevant to the user question.\n"
        "- window_minutes between 5 and 60.\n"
        "- Container/namespace/cluster labels are applied automatically.\n"
        "- Return JSON only."
    )


def messages_to_contents(messages: list[dict]) -> list[Content]:
    return [
        Content(
            role="user" if m["role"] == "user" else "model",
            parts=[Part.from_text(m["content"])],
        )
        for m in messages
    ]


def plan_metrics(session: dict, messages: list[dict], user_question: str) -> dict:
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
    metric_facts: str | None = None,
) -> str:
    """Gemini step 3 — produce a concise Slack mrkdwn response.

    Returns a plain Slack mrkdwn string.
    """
    if metric_facts:
        try:
            analysis_body = format_analysis_only(
                incident_id, user_question, analysis, metric_summary
            )
        except Exception:
            analysis_body = _fallback_analysis_text(analysis)
        return f"{metric_facts}\n\n{analysis_body}"

    _ensure_init()
    system_prompt = (
        "You are formatting an SRE incident analysis response for Slack (mrkdwn). "
        "Be concise — max 6 lines. "
        "Use metric_summary.display and utilization_percent only; never invent CPU core counts. "
        "List root cause candidates from analysis. "
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


def format_analysis_only(
    incident_id: str,
    user_question: str,
    analysis: dict,
    metric_summary: dict | None = None,
) -> str:
    """Format root-cause section only; metric numbers come from metric_facts."""
    _ensure_init()
    system_prompt = (
        "Format root cause candidates for Slack (mrkdwn). Max 5 lines. "
        "Do not repeat or contradict metric_facts. Do not state CPU/memory numbers. "
        "Return ONLY mrkdwn."
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
        generation_config=GenerationConfig(temperature=0.2),
    )
    return response.text.strip()


def _fallback_analysis_text(analysis: dict) -> str:
    candidates = analysis.get("root_cause_candidates") or []
    confidence = analysis.get("confidence", "unknown")
    lines = ["*Root cause candidates:*"]
    for item in candidates[:5]:
        lines.append(f"• {item}")
    lines.append(f"Confidence: {confidence}")
    return "\n".join(lines)

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
    """Gemini step 1 — decide which Cloud Monitoring metrics to fetch.

    Returns a MetricFetchPlan dict with keys:
      metrics: list of {metric_type, filter, window_minutes}
      rationale: string
    """
    model = _get_model()
    system_prompt = (
        "You are an SRE metric planner. "
        "Given the incident context and the user's question, decide which "
        "Cloud Monitoring metric time-series to query. "
        "Return ONLY valid JSON matching this schema: "
        '{"metrics": [{"metric_type": "...", "filter": "...", "window_minutes": 30}], "rationale": "..."}. '
        "metric_type must be a valid GCP Monitoring metric type (e.g. kubernetes.io/container/memory/used_bytes). "
        "If no metrics are relevant return an empty metrics list."
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
    }
    history = messages_to_contents(messages[-10:])
    response = model.generate_content(
        history + [Content(role="user", parts=[Part.from_text(
            "Incident context:\n" + json.dumps(context_payload) + "\n\nPlan the metrics to fetch."
        )])],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    return json.loads(response.text)


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
    model = _get_model()
    system_prompt = (
        "You are an SRE root-cause analyst. "
        "Analyze the metric results for the incident and identify the most likely root causes. "
        "Return ONLY valid JSON with keys: "
        "root_cause_candidates (list of strings, most likely first), "
        "confidence (high|medium|low), "
        "additional_signals_needed (list of strings, can be empty)."
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
        history + [Content(role="user", parts=[Part.from_text(
            "Metric data:\n" + json.dumps(analysis_payload, default=str)
        )])],
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
) -> str:
    """Gemini step 3 — produce a concise Slack mrkdwn response.

    Returns a plain Slack mrkdwn string.
    """
    model = _get_model()
    system_prompt = (
        "You are formatting an SRE incident analysis response for Slack (mrkdwn). "
        "Be concise — max 8 lines. Use *bold* sparingly for key values. "
        "Answer the operator's question directly, then list root cause candidates. "
        "If confidence is low, say so clearly. "
        "Return ONLY the Slack mrkdwn string."
    )
    payload = {
        "incident_id": incident_id,
        "user_question": user_question,
        "analysis": analysis,
    }
    response = model.generate_content(
        [system_prompt, json.dumps(payload, default=str)],
        generation_config=GenerationConfig(temperature=0.3),
    )
    return response.text.strip()

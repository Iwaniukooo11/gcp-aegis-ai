"""Vertex AI / Gemini integration for Incident Analyzer.

All three Gemini steps use single-turn generate_content — no chat history
is needed here because the input is always the raw log payload, not a
conversation. Firestore is populated after these steps run.
"""
import json
import os

import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel

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


def _structured_payload(raw_log: dict) -> dict:
    payload = raw_log.get("jsonPayload")
    if isinstance(payload, dict):
        return payload
    text_payload = raw_log.get("textPayload", "")
    if not isinstance(text_payload, str):
        return {}
    try:
        decoded = json.loads(text_payload)
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _checkout_dependency_classification(raw_log: dict) -> dict | None:
    payload = _structured_payload(raw_log)
    if payload.get("path") != "/api/checkout" or payload.get("upstream_service") != "java-api":
        return None

    error_type = str(payload.get("error_type") or "")
    message = str(payload.get("message") or payload.get("stack_trace_preview") or "").strip()
    if "timeout" in error_type.lower() or "timeout" in message.lower():
        return {
            "ai_summary": (
                "Customer checkout failed because the java-api pricing dependency did not respond "
                "before the configured timeout."
            ),
            "ai_recommendation": (
                "Check java-api pricing latency and availability first, then verify pod CPU, memory, "
                "and recent rollout or configuration changes."
            ),
        }

    return {
        "ai_summary": (
            "Customer checkout failed because the java-api pricing dependency returned an error "
            "to python-api."
        ),
        "ai_recommendation": (
            "Inspect java-api pricing health, recent logs, and recent rollout or configuration changes; "
            "use Monitoring metrics to confirm whether CPU or memory pressure contributed."
        ),
    }


def normalize_log(raw_log: dict) -> dict:
    """Gemini step 1 — extract structured incident fields from a raw Cloud Logging entry.

    Returns a dict with keys: error_type, short_message, stack_trace_preview,
    service_name, severity.
    """
    model = _get_model()
    system_prompt = (
        "You are an SRE incident normalizer. "
        "Extract structured fields from the provided Cloud Logging LogEntry JSON. "
        "Return ONLY valid JSON with these keys: "
        "error_type (string), short_message (string, max 120 chars), "
        "stack_trace_preview (string, max 500 chars, most relevant part only), "
        "service_name (string), severity (string). "
        "If jsonPayload.upstream_service is present, short_message should mention the dependency. "
        "Do not call an incident chaos engineering unless the failing request path is /chaos/* "
        "or the message explicitly says chaos. "
        "If a field is unavailable set it to null."
    )
    response = model.generate_content(
        [system_prompt, "Log entry:\n" + json.dumps(raw_log, default=str)],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    return json.loads(response.text)


def classify_incident(normalized: dict, raw_log: dict) -> dict:
    """Gemini step 2 — classify incident and produce ai_summary + ai_recommendation.

    Returns a dict with keys: ai_summary (string), ai_recommendation (string).
    """
    business_classification = _checkout_dependency_classification(raw_log)
    if business_classification is not None:
        return business_classification

    model = _get_model()
    system_prompt = (
        "You are an SRE incident analyst. "
        "Given the normalized incident fields and original log, produce a concise diagnosis. "
        "Focus on the business symptom and dependency path. "
        "Do not describe an incident as intentional chaos unless the failing request path is /chaos/* "
        "or the log message explicitly says chaos. "
        "Return ONLY valid JSON with keys: "
        "ai_summary (1-2 sentences explaining likely cause), "
        "ai_recommendation (1-2 actionable next steps)."
    )
    payload = {
        "normalized_fields": normalized,
        "log_message": raw_log.get("textPayload") or raw_log.get("jsonPayload", {}),
    }
    response = model.generate_content(
        [system_prompt, json.dumps(payload, default=str)],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return json.loads(response.text)


def format_slack_alert(incident_id: str, normalized: dict, classification: dict) -> str:
    """Gemini step 3 — produce a ready-to-post Slack mrkdwn alert string.

    Returns a plain Slack mrkdwn string (no JSON wrapper).
    """
    model = _get_model()
    system_prompt = (
        "You are formatting an SRE incident alert for Slack (mrkdwn). "
        "Use *bold* for important values. Keep it concise — max 5 lines. "
        "Include: incident ID, service, error type, severity, AI summary, recommendation. "
        "Do not add chaos wording unless the provided AI summary or recommendation says chaos. "
        "End with a hint: reply with @aegis-bot <incident_id> <your question>. "
        "Return ONLY the Slack mrkdwn string, no JSON."
    )
    payload = {
        "incident_id": incident_id,
        **normalized,
        **classification,
    }
    response = model.generate_content(
        [system_prompt, json.dumps(payload, default=str)],
        generation_config=GenerationConfig(temperature=0.3),
    )
    return response.text.strip()

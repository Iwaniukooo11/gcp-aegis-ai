"""Vertex AI / Gemini integration for Incident Analyzer."""
import json

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


def normalize_log(raw_log: dict) -> dict:
    """Gemini step 1 — extract structured incident fields from a raw Cloud Logging entry."""
    model = _get_model()
    system_prompt = (
        "You are an SRE incident normalizer. "
        "Extract structured fields from the provided Cloud Logging LogEntry JSON. "
        "Prefer jsonPayload.message, jsonPayload.error_type, and stack_trace_preview over generic text. "
        "Do not use 'Request completed' as short_message when error_type or exception details exist. "
        "Return ONLY valid JSON with these keys: "
        "error_type (string), short_message (string, max 120 chars), "
        "stack_trace_preview (string, max 500 chars, most relevant part only), "
        "service_name (string), severity (string). "
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
    """Gemini step 2 — classify incident and produce ai_summary + ai_recommendation."""
    model = _get_model()
    system_prompt = (
        "You are an SRE incident analyst for a production microservice platform. "
        "Describe symptoms and likely causes as you would for an on-call engineer. "
        "Do not label incidents as chaos tests or experiments unless the log explicitly mentions "
        "chaos endpoints or drill keywords. "
        "Given the normalized incident fields and original log, produce a concise diagnosis. "
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
    """Gemini step 3 — produce a ready-to-post Slack mrkdwn alert string."""
    model = _get_model()
    system_prompt = (
        "You are formatting a production SRE incident alert for Slack (mrkdwn). "
        "Use *bold* for incident ID, service, and error type. Max 5 lines. "
        "Lead with the user-visible failure (error_type + short_message), then AI summary, then recommendation. "
        "Do not mention chaos engineering, drills, or simulated errors unless the payload explicitly says so. "
        "End with: reply `@Aegis INC-... your question` for follow-up. "
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

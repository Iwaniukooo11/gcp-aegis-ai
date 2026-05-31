import traceback

from fastapi import Request

MAX_STACK_TRACE_PREVIEW_CHARS = 4096


def set_observability(
    request: Request,
    *,
    scenario: str | None = None,
    error_type: str | None = None,
    incident_message: str | None = None,
    stack_trace_preview: str | None = None,
    upstream_service: str | None = None,
) -> None:
    if scenario is not None:
        request.state.scenario = scenario
    if error_type is not None:
        request.state.error_type = error_type
    if incident_message is not None:
        request.state.incident_message = incident_message
    if stack_trace_preview is not None:
        request.state.stack_trace_preview = stack_trace_preview
    if upstream_service is not None:
        request.state.upstream_service = upstream_service


def stack_trace_preview(exc: BaseException) -> str:
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
    if len(text) <= MAX_STACK_TRACE_PREVIEW_CHARS:
        return text
    return f"{text[:MAX_STACK_TRACE_PREVIEW_CHARS].rstrip()}\n... (truncated)"

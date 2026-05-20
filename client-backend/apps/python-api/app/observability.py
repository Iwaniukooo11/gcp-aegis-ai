from fastapi import Request


def set_observability(
    request: Request,
    *,
    scenario: str | None = None,
    error_type: str | None = None,
    stack_trace_preview: str | None = None,
    upstream_service: str | None = None,
) -> None:
    if scenario is not None:
        request.state.scenario = scenario
    if error_type is not None:
        request.state.error_type = error_type
    if stack_trace_preview is not None:
        request.state.stack_trace_preview = stack_trace_preview
    if upstream_service is not None:
        request.state.upstream_service = upstream_service


def stack_trace_preview(exc: BaseException) -> str:
    traceback = exc.__traceback__
    if traceback is None:
        return str(exc)
    while traceback.tb_next is not None:
        traceback = traceback.tb_next
    code = traceback.tb_frame.f_code
    return f"{exc.__class__.__name__}: {code.co_filename}:{traceback.tb_lineno}"

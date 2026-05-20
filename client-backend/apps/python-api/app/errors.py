from fastapi.responses import JSONResponse


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    service_name: str,
    scenario: str,
    correlation_id: str,
    error_type: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "service_name": service_name,
                "scenario": scenario,
                "correlation_id": correlation_id,
                "error_type": error_type,
            }
        },
    )

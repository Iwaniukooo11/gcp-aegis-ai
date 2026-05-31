import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.middleware import CORRELATION_HEADER


class JavaPricingResponse(BaseModel):
    service_name: str
    client_project_id: str
    environment: str
    scenario: str
    currency: str
    subtotal_cents: int
    tax_cents: int
    total_cents: int


class DownstreamTimeoutError(Exception):
    pass


class DownstreamBadResponseError(Exception):
    pass


class JavaApiClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport

    async def get_pricing(self, correlation_id: str) -> JavaPricingResponse:
        timeout_seconds = self._settings.java_api_timeout_ms / 1000
        async with httpx.AsyncClient(
            base_url=self._settings.java_api_base_url,
            timeout=timeout_seconds,
            transport=self._transport,
        ) as client:
            try:
                response = await client.get(
                    "/api/pricing",
                    headers={CORRELATION_HEADER: correlation_id},
                )
            except httpx.TimeoutException as exc:
                raise DownstreamTimeoutError("java-api pricing request exceeded configured timeout") from exc
            except httpx.HTTPError as exc:
                raise DownstreamBadResponseError("java-api pricing request failed before response") from exc

        if response.status_code >= 500:
            raise DownstreamBadResponseError(f"java-api pricing returned HTTP {response.status_code}")
        if response.status_code != 200:
            raise DownstreamBadResponseError(f"java-api pricing returned unexpected HTTP {response.status_code}")

        try:
            return JavaPricingResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise DownstreamBadResponseError("java-api pricing returned malformed response") from exc

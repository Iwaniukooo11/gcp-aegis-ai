from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service_name: str
    environment: str
    client_project_id: str


class InfoResponse(BaseModel):
    service_name: str
    client_project_id: str
    environment: str
    team: str
    version: str


class WorkResponse(BaseModel):
    service_name: str
    client_project_id: str
    environment: str
    scenario: str
    work_units: int
    result: str


class CheckoutResponse(BaseModel):
    service_name: str
    client_project_id: str
    environment: str
    scenario: str
    upstream_service: str
    currency: str
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    checkout_id: str
    result: str

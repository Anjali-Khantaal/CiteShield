from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str


_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_tenant_context(
    api_key: str | None = Depends(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> TenantContext:
    if api_key == settings.tenant_a_api_key:
        return TenantContext(tenant_id="tenant_a")
    if api_key == settings.tenant_b_api_key:
        return TenantContext(tenant_id="tenant_b")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key.",
    )

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str


@dataclass(frozen=True)
class SessionContext:
    role: str
    tenant_id: str | None = None


@dataclass(frozen=True)
class SuperuserContext:
    role: str = "superuser"


_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_session_context(
    api_key: str | None = Depends(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> SessionContext:
    if api_key == settings.tenant_a_api_key:
        return SessionContext(role="tenant", tenant_id="tenant_a")
    if api_key == settings.tenant_b_api_key:
        return SessionContext(role="tenant", tenant_id="tenant_b")
    if api_key == settings.superuser_api_key:
        return SessionContext(role="superuser")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key.",
    )


def get_tenant_context(
    session: SessionContext = Depends(get_session_context),
) -> TenantContext:
    if session.role != "tenant" or session.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant key required.",
        )

    return TenantContext(tenant_id=session.tenant_id)


def get_superuser_context(
    session: SessionContext = Depends(get_session_context),
) -> SuperuserContext:
    if session.role != "superuser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser key required.",
        )

    return SuperuserContext()

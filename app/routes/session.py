from fastapi import APIRouter, Depends

from app.auth import SessionContext, get_session_context
from app.models import SessionContextResponse

router = APIRouter(tags=["session"])


@router.get("/whoami", response_model=SessionContextResponse)
def whoami(
    session_context: SessionContext = Depends(get_session_context),
) -> SessionContextResponse:
    return SessionContextResponse(
        role=session_context.role,
        tenant_id=session_context.tenant_id,
    )

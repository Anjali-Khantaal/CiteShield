from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.auth import TenantContext, get_tenant_context
from app.config import Settings, get_settings

router = APIRouter(tags=["media"])

_ALLOWED_MEDIA_DIRS = {"images", "audio", "video"}


@router.get("/media/{tenant_id}/{media_path:path}")
def get_tenant_media(
    tenant_id: str,
    media_path: str,
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    if tenant.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant media access denied.",
        )

    parts = Path(media_path).parts
    if len(parts) < 2 or parts[0] != "media" or parts[1] not in _ALLOWED_MEDIA_DIRS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found.",
        )

    tenant_root = (Path(settings.data_root) / tenant_id).resolve()
    requested_path = (tenant_root / media_path).resolve()
    if not requested_path.is_relative_to(tenant_root) or not requested_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found.",
        )

    return FileResponse(requested_path)

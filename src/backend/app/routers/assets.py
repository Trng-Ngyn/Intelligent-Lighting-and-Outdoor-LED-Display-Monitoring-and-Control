from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import require_roles
from app.db import fetch_all_assets

router = APIRouter()


@router.get("")
def list_assets(
    tenant_id: str = Header(..., alias="X-Tenant-Id"),
    site_id: str = Header(..., alias="X-Site-Id"),
    user: dict = Depends(require_roles("ADMIN", "OPERATOR")),
):
    try:
        return {"items": fetch_all_assets(tenant_id, site_id)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Không truy vấn được TimescaleDB",
        )
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from app.core.security import require_roles
from app.db import fetch_telemetry_history, fetch_latest_telemetry, fetch_telemetry_summary

router = APIRouter()

@router.get("/history")
def telemetry_history(
    asset_id: UUID,
    start_time: datetime,
    end_time: datetime,
    limit: int = Query(default=500, ge=1, le=5000),
    user: dict = Depends(require_roles("ADMIN", "OPERATOR")),
):
    if start_time >= end_time:
        raise HTTPException(status_code=422, detail="start_time phải nhỏ hơn end_time")
    try:
        items = fetch_telemetry_history(str(asset_id), start_time, end_time, limit)
        return {"items": items, "count": len(items)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Không truy vấn được TimescaleDB")


@router.get("/latest")
def latest_telemetry(
    asset_id: UUID,
    user: dict = Depends(require_roles("ADMIN", "OPERATOR")),
):
    try:
        result = fetch_latest_telemetry(str(asset_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Kh?ng truy v?n ???c TimescaleDB")

    if result is None:
        raise HTTPException(status_code=404, detail="Ch?a c? telemetry cho thi?t b? n?y")

    return result


@router.get("/summary")
def telemetry_summary(
    asset_id: UUID,
    start_time: datetime,
    end_time: datetime,
    user: dict = Depends(require_roles("ADMIN", "OPERATOR")),
):
    if start_time >= end_time:
        raise HTTPException(status_code=422, detail="start_time ph?i nh? h?n end_time")

    try:
        result = fetch_telemetry_summary(
            str(asset_id),
            start_time,
            end_time,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Kh?ng truy v?n ???c TimescaleDB")

    return result

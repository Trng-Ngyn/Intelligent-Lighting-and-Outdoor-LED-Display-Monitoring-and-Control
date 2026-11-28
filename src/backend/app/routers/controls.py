from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import require_roles
from app.db import (
    fetch_all_assets,
    get_idempotency_record,
    claim_idempotency_key,
    update_idempotency_response,
    release_idempotency_key,
)
import hashlib
import json
import core_api

router = APIRouter()


class LightingDimRequest(BaseModel):
    asset_id: UUID
    brightness: int = Field(ge=0, le=100)
    policy_version: str = Field(default="v1.0", min_length=1, max_length=80)



@router.post("/dim", status_code=202)
def dim_lighting(
    body: LightingDimRequest,
    user: dict = Depends(require_roles("OPERATOR")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if core_api.MQTT_CLIENT is None or core_api.RUNTIME_CONFIG is None:
        raise HTTPException(status_code=503, detail="MQTT chua ket noi")

    key = idempotency_key.strip() if idempotency_key else None
    if idempotency_key is not None and (not key or len(key) > 255):
        raise HTTPException(status_code=422, detail="Idempotency-Key khong hop le")

    request_data = {
        "asset_id": str(body.asset_id),
        "brightness": body.brightness,
        "policy_version": body.policy_version,
    }
    request_hash = hashlib.sha256(
        json.dumps(request_data, sort_keys=True).encode("utf-8")
    ).hexdigest()

    if key:
        try:
            existing = get_idempotency_record(key, str(user["user_id"]))
        except SQLAlchemyError:
            raise HTTPException(status_code=503, detail="Loi truy cap Idempotency")

        if existing:
            if existing["request_hash"] != request_hash:
                raise HTTPException(status_code=409, detail="Idempotency-Key da duoc dung voi noi dung khac")
            if existing["response_json"] is None:
                raise HTTPException(status_code=409, detail="Lenh dang duoc xu ly")
            return existing["response_json"]

    try:
        assets = fetch_all_assets()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Khong truy van duoc TimescaleDB")

    asset = next(
        (item for item in assets if str(item.get("asset_id")) == str(body.asset_id)),
        None,
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Khong tim thay asset")

    if asset.get("kind") != "lighting":
        raise HTTPException(status_code=422, detail="Asset khong phai thiet bi chieu sang")

    asset_code = asset.get("asset_code")
    if not asset_code:
        raise HTTPException(status_code=422, detail="Asset chua co asset_code")

    spec = core_api._find_light_spec(str(asset_code))
    if spec is None:
        raise HTTPException(status_code=404, detail="Asset chua khop cau hinh MQTT")

    if key:
        try:
            claimed = claim_idempotency_key(
                key, str(user["user_id"]), request_hash
            )
        except SQLAlchemyError:
            raise HTTPException(status_code=503, detail="Khong tao duoc Idempotency-Key")

        if not claimed:
            try:
                existing = get_idempotency_record(key, str(user["user_id"]))
            except SQLAlchemyError:
                raise HTTPException(status_code=503, detail="Loi truy cap Idempotency")

            if existing:
                if existing["request_hash"] != request_hash:
                    raise HTTPException(status_code=409, detail="Idempotency-Key da duoc dung voi noi dung khac")
                if existing["response_json"] is not None:
                    return existing["response_json"]

            raise HTTPException(status_code=409, detail="Idempotency-Key dang duoc su dung")

    try:
        command_id = core_api.send_dim_command(str(asset_code), body.brightness)
    except ValueError as exc:
        if key:
            release_idempotency_key(key, str(user["user_id"]), request_hash)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        if key:
            release_idempotency_key(key, str(user["user_id"]), request_hash)
        raise HTTPException(status_code=503, detail="Gui lenh MQTT that bai")

    if command_id is None:
        if key:
            release_idempotency_key(key, str(user["user_id"]), request_hash)
        raise HTTPException(status_code=503, detail="Khong gui duoc lenh MQTT")

    response = {
        "status": "accepted",
        "command_id": command_id,
        "asset_id": str(body.asset_id),
        "asset_code": str(asset_code),
        "brightness": body.brightness,
    }

    if key:
        try:
            saved = update_idempotency_response(
                key, str(user["user_id"]), request_hash, response
            )
            if not saved:
                raise HTTPException(
                    status_code=503,
                    detail="Lenh da gui nhung khong luu duoc ket qua Idempotency",
                )
        except SQLAlchemyError:
            raise HTTPException(
                status_code=503,
                detail="Lenh da gui nhung loi luu ket qua Idempotency",
            )

    return response

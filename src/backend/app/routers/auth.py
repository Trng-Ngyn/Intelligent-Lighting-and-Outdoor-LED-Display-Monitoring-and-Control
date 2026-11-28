
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status, Depends, Response
from pydantic import BaseModel, Field
from jose import jwt, JWTError

from app.core.config import settings
from app.core.security import create_token, current_user
from app.db import (
    create_auth_session,
    get_auth_session,
    rotate_auth_session,
    revoke_auth_session,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    mfa_code: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "refresh" or not payload.get("sub"):
            raise ValueError("Invalid refresh token")
        if not payload.get("sid"):
            raise ValueError("Missing session ID")
        return payload
    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Refresh token không hợp lệ hoặc đã hết hạn",
        )


@router.post("/login")
def login(body: LoginRequest):
    if (
        body.username != settings.dev_username
        or body.password != settings.dev_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Sai tài khoản hoặc mật khẩu",
        )

    roles = [
        role.strip()
        for role in settings.dev_roles.split(",")
        if role.strip()
    ]

    session_id = str(uuid.uuid4())

    access_expires = timedelta(minutes=settings.access_token_minutes)
    refresh_expires = timedelta(days=settings.refresh_token_days)
    expires_at = datetime.now(timezone.utc) + refresh_expires

    access = create_token(
        settings.dev_user_id,
        roles,
        "access",
        access_expires,
        session_id,
    )

    refresh = create_token(
        settings.dev_user_id,
        roles,
        "refresh",
        refresh_expires,
        session_id,
    )

    create_auth_session(
        session_id,
        settings.dev_user_id,
        roles,
        _token_hash(refresh),
        expires_at,
    )

    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": int(access_expires.total_seconds()),
    }


@router.post("/refresh")
def refresh_token(body: RefreshRequest):
    payload = _decode_refresh_token(body.refresh_token)

    session_id = payload["sid"]
    old_hash = _token_hash(body.refresh_token)
    session = get_auth_session(session_id)

    if (
        not session
        or session["user_id"] != payload["sub"]
        or session["revoked_at"] is not None
        or session["expires_at"] <= datetime.now(timezone.utc)
        or session["refresh_token_hash"] != old_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Refresh token không hợp lệ hoặc đã được sử dụng",
        )

    roles = payload.get("roles", [])
    if not isinstance(roles, list):
        raise HTTPException(
            status_code=401,
            detail="Thông tin vai trò không hợp lệ",
        )

    access_expires = timedelta(minutes=settings.access_token_minutes)
    refresh_expires = timedelta(days=settings.refresh_token_days)
    expires_at = datetime.now(timezone.utc) + refresh_expires

    access = create_token(
        payload["sub"],
        roles,
        "access",
        access_expires,
        session_id,
    )

    refresh = create_token(
        payload["sub"],
        roles,
        "refresh",
        refresh_expires,
        session_id,
    )

    rotated = rotate_auth_session(
        session_id,
        old_hash,
        _token_hash(refresh),
        expires_at,
    )

    if not rotated:
        raise HTTPException(
            status_code=401,
            detail="Refresh token đã được sử dụng",
        )

    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": int(access_expires.total_seconds()),
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest):
    payload = _decode_refresh_token(body.refresh_token)

    session_id = payload["sid"]
    session = get_auth_session(session_id)

    if (
        not session
        or session["user_id"] != payload["sub"]
        or session["revoked_at"] is not None
        or session["expires_at"] <= datetime.now(timezone.utc)
        or session["refresh_token_hash"] != _token_hash(body.refresh_token)
    ):
        raise HTTPException(
            status_code=401,
            detail="Refresh token không hợp lệ hoặc phiên đã hết hiệu lực",
        )

    revoked = revoke_auth_session(session_id)

    if not revoked:
        raise HTTPException(
            status_code=401,
            detail="Không thể thu hồi phiên đăng nhập",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return user

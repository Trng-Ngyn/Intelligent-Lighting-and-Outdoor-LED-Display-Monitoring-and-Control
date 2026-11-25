
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.db import get_auth_session

bearer_scheme = HTTPBearer()
ALLOWED_ROLES = {"ADMIN", "OPERATOR", "CONTENT_AUTHOR", "CONTENT_APPROVER"}


def create_token(
    subject: str,
    roles: list[str],
    token_type: str,
    expires: timedelta,
    session_id: str,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "roles": roles,
        "type": token_type,
        "sid": session_id,
        "iat": now,
        "exp": now + expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    token = credentials.credentials    
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ, phiên đã bị thu hồi hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )

        if payload.get("type") != "access" or not payload.get("sub"):
            raise credentials_error

        roles = payload.get("roles", [])
        session_id = payload.get("sid")

        if (
            not isinstance(roles, list)
            or not set(roles).issubset(ALLOWED_ROLES)
            or not session_id
        ):
            raise credentials_error

        session = get_auth_session(session_id)

        if (
            not session
            or session["user_id"] != payload["sub"]
            or session["revoked_at"] is not None
            or session["expires_at"] <= datetime.now(timezone.utc)
        ):
            raise credentials_error

        return {
            "user_id": payload["sub"],
            "roles": roles,
            "session_id": session_id,
        }

    except (JWTError, ValueError, TypeError):
        raise credentials_error


def require_roles(*required_roles: str):
    def checker(user: dict = Depends(current_user)) -> dict:
        if "ADMIN" in user["roles"]:
            return user
        if not set(required_roles).intersection(user["roles"]):
            raise HTTPException(
                status_code=403,
                detail="Bạn không có quyền thực hiện thao tác này",
            )
        return user

    return checker

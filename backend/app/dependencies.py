"""
dependencies.py
---------------
FastAPI dependency functions shared across routers:
  - get_current_user (JWT Bearer token validation)
  - require_roles (role-based access control guard)
"""
from typing import Optional, Set
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.security import decode_access_token
from app.models import User, UserRole

# auto_error=False so we can explicitly return 401 Unauthorized for missing tokens
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate JWT and return the authenticated User. Raises 401 on failure."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.get(User, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*allowed_roles: str):
    """
    Enforces role-based access control (RBAC).
    Returns 403 Forbidden if current_user's role is not in allowed_roles.
    Example: Depends(require_roles("doctor", "admin"))
    """
    normalized_allowed: Set[str] = {
        r.value.lower() if hasattr(r, "value") else str(r).lower()
        for r in allowed_roles
    }

    async def role_guard(current_user: User = Depends(get_current_user)) -> User:
        user_role = (
            current_user.role.value.lower()
            if hasattr(current_user.role, "value")
            else str(current_user.role).lower()
        )
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: role '{user_role}' does not have permission for this resource",
            )
        return current_user

    return role_guard

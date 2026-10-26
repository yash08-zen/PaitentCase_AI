"""
routers/auth.py
---------------
Authentication endpoints: register, login, logout, profile, and audit logs.
Passwords are always stored hashed. JWTs are signed with the app secret key.
All login, logout, and failed login events are recorded in the audit trail.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserOut, LoginRequest, TokenResponse, AuditEventOut
from app.core.security import hash_password, verify_password, create_access_token
from app.dependencies import get_current_user, require_roles
from app.services.audit import log_audit_event, get_audit_events
from app.core.rate_limiter import rate_limit

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, bucket="auth_register"))],
)
async def register(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Register a new user account (admin only)."""
    existing = await db.scalar(select(User).where(User.username == payload.username))
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await log_audit_event(
        db,
        action="USER_REGISTERED",
        actor=current_user,
        resource_type="user",
        resource_id=str(user.id),
        change_summary=f"User {user.username} created with role {user.role}",
        ip_address=request.client.host if request.client else None,
    )
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, bucket="auth_login"))],
)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user, return JWT access token, and record audit event."""
    ip = request.client.host if request.client else None
    user = await db.scalar(select(User).where(User.username == payload.username))

    if not user or not verify_password(payload.password, user.password_hash):
        await log_audit_event(
            db,
            action="LOGIN_FAILED",
            actor_username=payload.username,
            resource_type="auth",
            change_summary=f"Failed login attempt for username: {payload.username}",
            ip_address=ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        await log_audit_event(
            db,
            action="LOGIN_FAILED",
            actor=user,
            resource_type="auth",
            resource_id=str(user.id),
            change_summary="Login rejected: account is inactive",
            ip_address=ip,
        )
        raise HTTPException(status_code=403, detail="Account is inactive")

    token = create_access_token({"sub": str(user.id), "role": user.role.value if hasattr(user.role, "value") else str(user.role)})

    await log_audit_event(
        db,
        action="LOGIN_SUCCESS",
        actor=user,
        resource_type="auth",
        resource_id=str(user.id),
        change_summary=f"User {user.username} logged in successfully",
        ip_address=ip,
    )
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record logout in the audit trail."""
    ip = request.client.host if request.client else None
    await log_audit_event(
        db,
        action="LOGOUT",
        actor=current_user,
        resource_type="auth",
        resource_id=str(current_user.id),
        change_summary=f"User {current_user.username} logged out",
        ip_address=ip,
    )
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """Return currently authenticated user profile."""
    return current_user


@router.get("/audit", response_model=List[AuditEventOut])
async def audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: Optional[str] = Query(None),
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve audit logs (admin only)."""
    return await get_audit_events(db, limit=limit, offset=offset, action=action)

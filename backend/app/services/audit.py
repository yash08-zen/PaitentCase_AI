"""
services/audit.py
-----------------
Audit logging service for security and clinical actions.
Events are append-only and record the actor, action, resource, and timestamp.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models import AuditEvent, User


async def log_audit_event(
    db: AsyncSession,
    action: str,
    actor: Optional[User] = None,
    actor_username: Optional[str] = None,
    actor_role: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    change_summary: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AuditEvent:
    """Record an audit trail event into the database."""
    if actor:
        actor_id = actor.id
        actor_username = actor_username or actor.username
        actor_role = actor_role or (actor.role.value if hasattr(actor.role, "value") else str(actor.role))
    else:
        actor_id = None

    event = AuditEvent(
        actor_id=actor_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        change_summary=change_summary,
        ip_address=ip_address,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def get_audit_events(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None,
) -> List[AuditEvent]:
    """Retrieve audit events, newest first."""
    query = select(AuditEvent).order_by(desc(AuditEvent.timestamp)).offset(offset).limit(limit)
    if action:
        query = query.where(AuditEvent.action == action)
    result = await db.scalars(query)
    return list(result.all())

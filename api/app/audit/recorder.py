"""Helper used by request handlers and dependencies to write audit events safely."""

import logging
import re
import uuid

from fastapi import Request

from app.audit.events import Action, AuditEvent, AuditSink, Outcome

logger = logging.getLogger("uw.audit")

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def new_correlation_id(incoming: str | None) -> str:
    """Accept a caller-supplied request ID only if it is a safe token; otherwise mint one."""
    if incoming and _SAFE_ID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


def correlation_id_of(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", "unknown"))


def record_event(
    request: Request,
    action: Action | str,
    outcome: Outcome,
    *,
    tenant_id: str | None = None,
    actor: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, str] | None = None,
) -> None:
    """Write an audit event. A failure to audit is logged loudly but never grants access."""
    sink: AuditSink = request.app.state.audit_sink
    event = AuditEvent(
        action=action,
        outcome=outcome,
        correlation_id=correlation_id_of(request),
        tenant_id=tenant_id,
        actor=actor,
        resource_type=resource_type,
        resource_id=resource_id,
        details=dict(details or {}),
    )
    try:
        sink.record(event)
    except Exception:
        logger.exception(
            "audit.write_failed action=%s correlation_id=%s", action, event.correlation_id
        )

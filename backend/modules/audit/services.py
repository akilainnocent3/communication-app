"""`record(...)` is the only way to write audit events."""

import logging

from common.http import client_ip, user_agent

from .models import AuditEvent

log = logging.getLogger(__name__)


def record(action: str, *, request=None, actor=None, mailbox=None, target_type: str = "", target_id="", metadata: dict | None = None) -> AuditEvent:
    if actor is None and request is not None and getattr(request, "user", None) and request.user.is_authenticated:
        actor = request.user
    event = AuditEvent.objects.create(
        actor=actor if actor and getattr(actor, "pk", None) else None,
        actor_email=getattr(actor, "email", "") or "",
        action=action,
        mailbox_id=getattr(mailbox, "pk", None),
        mailbox_email=getattr(mailbox, "email", "") or "",
        target_type=target_type,
        target_id=str(target_id or ""),
        ip=client_ip(request) if request is not None else None,
        user_agent=user_agent(request) if request is not None else "",
        metadata=metadata or {},
    )
    log.info("audit %s actor=%s mailbox=%s target=%s:%s", action, event.actor_email or "-", event.mailbox_email or "-", target_type, target_id)
    return event

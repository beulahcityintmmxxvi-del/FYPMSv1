from typing import Any

from flask import request

from app.extensions import db
from app.models.core import AuditLog


def log_action(
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata or {},
        ip_address=request.remote_addr,
        user_agent=(request.headers.get("User-Agent") or "")[:255],
    )
    db.session.add(entry)
    db.session.flush()
    return entry
from app.extensions import db
from app.models.core import Notification


def notify_user(
    user_id: int,
    title: str,
    message: str,
    notif_type: str = "info",
    action_url: str | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notif_type,
        action_url=action_url,
    )
    db.session.add(notif)
    db.session.flush()
    return notif


def mark_as_read(notification: Notification) -> Notification:
    notification.is_read = True
    from datetime import datetime

    notification.read_at = datetime.utcnow()
    db.session.flush()
    return notification
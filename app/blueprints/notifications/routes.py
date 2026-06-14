from datetime import datetime

from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.core import Notification
from app.utils.permissions import role_required

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
@login_required
@role_required("student", "supervisor", "admin", "department_admin")
def index():
    items = (
        Notification.query.filter_by(user_id=current_user.id, deleted_at=None)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return render_template("notifications/index.html", notifications=items)


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
@role_required("student", "supervisor", "admin", "department_admin")
def mark_read(notification_id):
    notif = Notification.query.get_or_404(notification_id)
    if notif.user_id != current_user.id:
        abort(403)

    notif.is_read = True
    notif.read_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("notifications.index"))
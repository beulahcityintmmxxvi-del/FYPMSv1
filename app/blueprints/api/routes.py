from functools import wraps
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import (
    current_user as jwt_current_user,
    jwt_required,
)
from app.extensions import csrf, db
from app.models.core import Notification, PlagiarismReport, Submission
from app.services.auth_service import authenticate_user, create_api_tokens
from app.services.reporting_service import get_admin_dashboard_data
from app.services.submission_service import create_submission
from app.utils.errors import AuthenticationError, FileError, ValidationError, WorkflowError

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")
csrf.exempt(api_bp)


def api_ok(data=None, message="OK", status=200):
    return jsonify({"success": True, "message": message, "data": data}), status


def api_fail(message="Error", status=400, details=None):
    payload = {"success": False, "message": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status


def require_api_role(*roles):
    """
    JWT-based role guard for API endpoints.
    Assumes jwt_current_user is populated by Flask-JWT-Extended user lookup.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not jwt_current_user or not getattr(jwt_current_user, "role", None):
                return api_fail("Forbidden", 403)

            if jwt_current_user.role.name not in roles:
                return api_fail("Forbidden", 403)

            return view_func(*args, **kwargs)

        return wrapped

    return decorator


@api_bp.post("/auth/login")
def api_login():
    payload = request.get_json(silent=True) or {}

    try:
        user = authenticate_user(
            payload.get("email", ""),
            payload.get("password", ""),
            request.remote_addr,
            request.headers.get("User-Agent"),
        )
        tokens = create_api_tokens(user)
        return api_ok(
            {
                "user": user.to_dict(),
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
            },
            "Login successful",
            200,
        )
    except AuthenticationError as exc:
        return api_fail(str(exc), 401)
    except Exception as exc:
        return api_fail("Login failed", 500, str(exc))


@api_bp.get("/me")
@jwt_required()
def me():
    if not jwt_current_user:
        return api_fail("Unauthorized", 401)

    return api_ok(jwt_current_user.to_dict(), "Current user")


@api_bp.get("/notifications")
@jwt_required()
def notifications():
    items = (
        Notification.query.filter_by(
            user_id=jwt_current_user.id,
            deleted_at=None,
        )
        .order_by(Notification.created_at.desc())
        .all()
    )

    data = [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "type": n.type,
            "is_read": n.is_read,
            "action_url": n.action_url,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in items
    ]
    return api_ok(data, "Notifications fetched")


@api_bp.post("/notifications/<int:notification_id>/read")
@jwt_required()
def mark_notification(notification_id):
    notif = Notification.query.get_or_404(notification_id)

    if notif.user_id != jwt_current_user.id:
        return api_fail("Forbidden", 403)

    notif.is_read = True
    notif.read_at = datetime.utcnow()
    db.session.commit()

    return api_ok({"id": notif.id}, "Notification marked as read")


@api_bp.get("/admin/analytics")
@jwt_required()
@require_api_role("admin")
def admin_analytics():
    return api_ok(get_admin_dashboard_data(), "Analytics fetched")


@api_bp.get("/submissions/<int:submission_id>")
@jwt_required()
def get_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)

    if jwt_current_user.has_role("student"):
        if submission.project.student_id != jwt_current_user.student.id:
            return api_fail("Forbidden", 403)

    if jwt_current_user.has_role("supervisor"):
        if submission.project.supervisor_id != jwt_current_user.supervisor.id:
            return api_fail("Forbidden", 403)

    return api_ok(submission.to_dict(), "Submission fetched")


@api_bp.get("/reports/<int:report_id>")
@jwt_required()
def get_report(report_id):
    report = PlagiarismReport.query.get_or_404(report_id)
    submission = report.submission

    if jwt_current_user.has_role("student"):
        if submission.project.student_id != jwt_current_user.student.id:
            return api_fail("Forbidden", 403)

    if jwt_current_user.has_role("supervisor"):
        if submission.project.supervisor_id != jwt_current_user.supervisor.id:
            return api_fail("Forbidden", 403)

    return api_ok(
        {
            "id": report.id,
            "submission_id": report.submission_id,
            "overall_similarity": round(report.overall_similarity * 100, 2),
            "risk_level": report.risk_level,
            "matched_documents": report.matched_documents_json,
            "suspicious_sections": report.suspicious_sections_json,
            "report_file_path": report.report_file_path,
        },
        "Report fetched",
    )


@api_bp.get("/reports/<int:report_id>/download")
@jwt_required()
def download_report(report_id):
    report = PlagiarismReport.query.get_or_404(report_id)

    if jwt_current_user.has_role("student"):
        if report.submission.project.student_id != jwt_current_user.student.id:
            return api_fail("Forbidden", 403)

    if jwt_current_user.has_role("supervisor"):
        if report.submission.project.supervisor_id != jwt_current_user.supervisor.id:
            return api_fail("Forbidden", 403)

    return send_file(report.report_file_path, as_attachment=True)


@api_bp.post("/submissions")
@jwt_required()
def upload_submission():
    stage = request.form.get("stage")
    title = request.form.get("title")
    file_obj = request.files.get("file")

    try:
        submission = create_submission(
            jwt_current_user,
            stage=stage,
            file_obj=file_obj,
            title=title,
        )
        return api_ok(submission.to_dict(), "Submission uploaded", 201)
    except (ValidationError, WorkflowError, FileError) as exc:
        return api_fail(str(exc), 400)
    except Exception as exc:
        return api_fail("Submission upload failed", 500, str(exc))
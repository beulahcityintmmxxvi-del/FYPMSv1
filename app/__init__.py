import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, redirect, request, url_for
from flask_jwt_extended import get_jwt_identity
from flask_login import current_user
from flask_talisman import Talisman

from app.config import config_by_name
from app.extensions import csrf, db, jwt, limiter, login_manager, migrate
from app.models.core import AcademicSession, Department, Role, SystemSetting, User
from app.blueprints.auth.routes import auth_bp
from app.blueprints.department_admin.routes import department_admin_bp
from app.blueprints.student.routes import student_bp
from app.blueprints.supervisor.routes import supervisor_bp
from app.blueprints.admin.routes import admin_bp
from app.blueprints.api.routes import api_bp
from app.blueprints.notifications import notifications_bp
from app.blueprints.notifications.routes import notifications_bp
from app.blueprints.department_admin.routes import department_admin_bp


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    config_name = config_name or os.getenv("APP_ENV", "development")
    app.config.from_object(config_by_name[config_name])

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["REPORT_FOLDER"], exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    jwt.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    csp = {
        "default-src": "'self'",
        "img-src": ["'self'", "data:"],
        "style-src": ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com"],
        "script-src": [
            "'self'",
            "'unsafe-inline'",
            "https://cdn.jsdelivr.net",
            "https://cdn.tailwindcss.com",
            "https://cdnjs.cloudflare.com",
        ],
        "connect-src": ["'self'"],
    }
    Talisman(app, content_security_policy=csp, force_https=app.config.get("FORCE_HTTPS", False))

    register_blueprints(app)
    register_error_handlers(app)
    register_logging(app)
    register_cli(app)
    register_jwt_callbacks(app)

    @app.context_processor
    def inject_globals():
        unread_count = 0
        recent_notifications = []
        active_session = AcademicSession.query.filter_by(is_active=True, deleted_at=None).first()

        if current_user.is_authenticated:
            from app.models.core import Notification

            unread_count = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False,
                deleted_at=None,
            ).count()

            recent_notifications = (
                Notification.query.filter_by(user_id=current_user.id, deleted_at=None)
                .order_by(Notification.created_at.desc())
                .limit(5)
                .all()
            )

        return {
            "unread_notifications_count": unread_count,
            "recent_notifications": recent_notifications,
            "active_session": active_session,
        }

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

    return app


def register_blueprints(app: Flask) -> None:
    blueprints = [
        auth_bp,
        student_bp,
        supervisor_bp,
        department_admin_bp,
        admin_bp,
        notifications_bp,
        api_bp,
    ]

    for bp in blueprints:
        if bp.name not in app.blueprints:
            app.register_blueprint(bp)

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.has_role("student"):
                return redirect(url_for("student.dashboard"))
            if current_user.has_role("supervisor"):
                return redirect(url_for("supervisor.dashboard"))
            if current_user.has_role("department_admin"):
                return redirect(url_for("department_admin.dashboard"))
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("auth.login"))

    @app.route("/dashboard")
    def dashboard():
        return index()

def register_blueprints(app: Flask) -> None:
    blueprints = [
        auth_bp,
        student_bp,
        supervisor_bp,
        department_admin_bp,
        admin_bp,
        notifications_bp,
        api_bp,
    ]

    for bp in blueprints:
        if bp.name not in app.blueprints:
            app.register_blueprint(bp)

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.has_role("student"):
                return redirect(url_for("student.dashboard"))
            if current_user.has_role("supervisor"):
                return redirect(url_for("supervisor.dashboard"))
            if current_user.has_role("department_admin"):
                return redirect(url_for("department_admin.dashboard"))
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("auth.login"))

    @app.route("/dashboard")
    def dashboard():
        return index()


def register_error_handlers(app: Flask) -> None:
    def is_api():
        return request.path.startswith("/api/")

    @app.errorhandler(400)
    def bad_request(_):
        return (jsonify({"success": False, "message": "Bad request"}) if is_api() else ("Bad request", 400))

    @app.errorhandler(401)
    def unauthorized(_):
        if is_api():
            return jsonify({"success": False, "message": "Authentication required"}), 401
        return redirect(url_for("auth.login"))

    @app.errorhandler(403)
    def forbidden(_):
        return (jsonify({"success": False, "message": "Forbidden"}) if is_api() else ("Forbidden", 403))

    @app.errorhandler(404)
    def not_found(_):
        return (jsonify({"success": False, "message": "Not found"}) if is_api() else ("Not found", 404))

    @app.errorhandler(413)
    def file_too_large(_):
        return (jsonify({"success": False, "message": "File too large"}) if is_api() else ("File too large", 413))

    @app.errorhandler(500)
    def server_error(_):
        return (jsonify({"success": False, "message": "Internal server error"}) if is_api() else ("Internal server error", 500))


def register_logging(app: Flask) -> None:
    if app.debug:
        return

    handler = RotatingFileHandler("logs/app.log", maxBytes=5_000_000, backupCount=5)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def register_jwt_callbacks(app: Flask) -> None:
    @jwt.user_lookup_loader
    def jwt_user_lookup(_jwt_header, jwt_data):
        return db.session.get(User, int(jwt_data["sub"]))

    @jwt.unauthorized_loader
    def jwt_missing(reason):
        return jsonify({"success": False, "message": "Missing or invalid token", "reason": reason}), 401

    @jwt.invalid_token_loader
    def jwt_invalid(reason):
        return jsonify({"success": False, "message": "Invalid token", "reason": reason}), 401

    @jwt.expired_token_loader
    def jwt_expired(_jwt_header, _jwt_payload):
        return jsonify({"success": False, "message": "Token expired"}), 401


def register_cli(app: Flask) -> None:
    @app.cli.command("seed-defaults")
    def seed_defaults():
        """Seed roles, default settings, and optional initial admin."""
        from app.extensions import db

        roles = [
            ("student", "Student user"),
            ("supervisor", "Supervisor user"),
            ("admin", "System administrator"),
            ("department_admin", "Departmental administrator"),
        ]
        
        departments = [
            ("CSC", "Computer Science"),
            ("MTE", "Mechatronics Engineering"),
            ("SLT", "Science Lab Tech"),
            ("FTH", "Food Technology"),
            ("HMT", "Hospitality Management"),
            ("EEE", "Electrical Engineering"),
            ("MEE", "Mechanical Engineering"),
            ("ACC", "Accountancy"),
            ("MKT", "Marketing"),
            ("PAB", "Public Administration"),
            ("BBA", "Business Administration"),
        ]

        for code, name in departments:
            if not Department.query.filter_by(code=code).first():
                db.session.add(Department(code=code, name=name))
        
        for name, desc in roles:
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name, description=desc))

        defaults = {
            "plagiarism_warning_threshold": "0.30",
            "plagiarism_critical_threshold": "0.60",
        }
        for key, value in defaults.items():
            if not SystemSetting.query.filter_by(key=key).first():
                db.session.add(SystemSetting(key=key, value=value, description=key.replace("_", " ").title()))

        db.session.commit()

        admin_email = os.getenv("INITIAL_ADMIN_EMAIL")
        admin_password = os.getenv("INITIAL_ADMIN_PASSWORD")
        admin_name = os.getenv("INITIAL_ADMIN_NAME", "System Administrator")

        if admin_email and admin_password and not User.query.filter_by(email=admin_email.lower()).first():
            admin_role = Role.query.filter_by(name="admin").first()
            admin = User(full_name=admin_name, email=admin_email.lower(), role=admin_role)
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from flask_jwt_extended import create_access_token, create_refresh_token
from sqlalchemy import func

from app.extensions import db
from app.models.core import (
    DepartmentAdmin,
    PasswordResetToken,
    Role,
    Student,
    Supervisor,
    User,
)
from app.services.audit_service import log_action
from app.services.notification_service import notify_user
from app.utils.errors import AuthenticationError, ValidationError
from app.utils.security import strong_password

MAX_LOGIN_ATTEMPTS = 5
LOCK_MINUTES = 15
DEFAULT_STUDENT_PASSWORD = "1234567"
DEFAULT_STUDENT_EMAIL_DOMAIN = "fpi.edu.ng"


def _resolve_user_by_identifier(identifier: str) -> User | None:
    ident = (identifier or "").strip()
    if not ident:
        return None

    user = User.query.filter(
        func.lower(User.email) == ident.lower(),
        User.deleted_at.is_(None),
    ).first()
    if user:
        return user

    student = Student.query.filter(
        func.upper(Student.matric_no) == ident.upper(),
        Student.deleted_at.is_(None),
    ).first()
    if student:
        return student.user

    supervisor = Supervisor.query.filter(
        func.upper(Supervisor.staff_no) == ident.upper(),
        Supervisor.deleted_at.is_(None),
    ).first()
    if supervisor:
        return supervisor.user

    return None


def register_student(
    full_name: str,
    email: str | None,
    password: str,
    matric_no: str,
    department_id: int,
    level: str,
    phone: str | None = None,
    address: str | None = None,
) -> User:
    matric_no_clean = matric_no.strip()

    if not matric_no_clean.isdigit() or len(matric_no_clean) != 10:
        raise ValidationError("Matric number must be exactly 10 digits, e.g. 2460141000.")

    email_value = (email or f"{matric_no_clean}@{DEFAULT_STUDENT_EMAIL_DOMAIN}").lower().strip()

    if User.query.filter_by(email=email_value, deleted_at=None).first():
        raise ValidationError("Email already exists.")

    if Student.query.filter_by(matric_no=matric_no_clean, deleted_at=None).first():
        raise ValidationError("Matric number already exists.")

    role = Role.query.filter_by(name="student", deleted_at=None).first()
    if not role:
        raise ValidationError("Student role is not configured.")

    user = User(
        full_name=full_name,
        email=email_value,
        role=role,
        phone=phone,
        must_change_password=True,
    )
    user.set_password(password)

    student = Student(
        user=user,
        matric_no=matric_no_clean,
        department_id=department_id,
        level=level,
        address=address,
    )

    db.session.add_all([user, student])
    db.session.flush()

    log_action(user.id, "student_registered", "User", user.id, {"matric_no": matric_no_clean})
    notify_user(
        user.id,
        "Account Created",
        f"Your student account has been created. Default password is {password}. Please change it after first login.",
        "success",
    )
    db.session.commit()
    return user


def register_supervisor(
    full_name: str,
    email: str,
    password: str,
    staff_no: str,
    department_id: int,
    title: str | None = None,
    phone: str | None = None,
    bio: str | None = None,
    must_change_password: bool = False,
) -> User:
    email_value = email.lower().strip()
    staff_no_clean = staff_no.strip().upper()

    if not strong_password(password):
        raise ValidationError(
            "Password must be at least 12 characters and include uppercase, lowercase, digit, and special character."
        )

    if User.query.filter_by(email=email_value, deleted_at=None).first():
        raise ValidationError("Email already exists.")

    if Supervisor.query.filter_by(staff_no=staff_no_clean, deleted_at=None).first():
        raise ValidationError("Staff number already exists.")

    role = Role.query.filter_by(name="supervisor", deleted_at=None).first()
    if not role:
        raise ValidationError("Supervisor role is not configured.")

    user = User(
        full_name=full_name,
        email=email_value,
        role=role,
        phone=phone,
        must_change_password=must_change_password,
    )
    user.set_password(password)

    supervisor = Supervisor(
        user=user,
        staff_no=staff_no_clean,
        department_id=department_id,
        title=title,
        bio=bio,
    )

    db.session.add_all([user, supervisor])
    db.session.flush()

    log_action(user.id, "supervisor_registered", "User", user.id, {"staff_no": staff_no_clean})
    notify_user(user.id, "Account Created", "Your supervisor account has been created successfully.", "success")
    db.session.commit()
    return user


def register_department_admin(
    full_name: str,
    email: str,
    password: str,
    department_id: int,
    phone: str | None = None,
    must_change_password: bool = True,
) -> User:
    email_value = email.lower().strip()

    if not strong_password(password):
        raise ValidationError(
            "Password must be at least 12 characters and include uppercase, lowercase, digit, and special character."
        )

    if User.query.filter_by(email=email_value, deleted_at=None).first():
        raise ValidationError("Email already exists.")

    if DepartmentAdmin.query.filter_by(department_id=department_id, deleted_at=None).first():
        raise ValidationError("This department already has a departmental admin.")

    role = Role.query.filter_by(name="department_admin", deleted_at=None).first()
    if not role:
        raise ValidationError("Department admin role is not configured.")

    user = User(
        full_name=full_name,
        email=email_value,
        role=role,
        phone=phone,
        must_change_password=must_change_password,
    )
    user.set_password(password)

    dept_admin = DepartmentAdmin(user=user, department_id=department_id)

    db.session.add_all([user, dept_admin])
    db.session.flush()

    log_action(
        user.id,
        "department_admin_registered",
        "User",
        user.id,
        {"department_id": department_id},
    )
    notify_user(user.id, "Account Created", "Your departmental admin account has been created.", "success")
    db.session.commit()
    return user


def authenticate_user(identifier: str, password: str, ip: str | None = None, user_agent: str | None = None) -> User:
    user = _resolve_user_by_identifier(identifier)

    if not user:
        raise AuthenticationError("Invalid login details.")

    if user.is_locked():
        raise AuthenticationError("Your account is temporarily locked. Try again later.")

    if not user.check_password(password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCK_MINUTES)

        db.session.flush()
        log_action(user.id, "login_failed", "User", user.id, {"identifier": identifier})
        db.session.commit()
        raise AuthenticationError("Invalid login details.")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()

    db.session.flush()
    log_action(
        user.id,
        "login_success",
        "User",
        user.id,
        {"identifier": identifier, "ip": ip, "user_agent": user_agent},
    )
    db.session.commit()
    return user


def change_own_password(user: User, current_password: str, new_password: str) -> User:
    if not user.check_password(current_password):
        raise AuthenticationError("Current password is incorrect.")

    if not strong_password(new_password):
        raise ValidationError(
            "Password must be at least 12 characters and include uppercase, lowercase, digit, and special character."
        )

    user.set_password(new_password)
    user.must_change_password = False

    db.session.flush()
    log_action(user.id, "password_changed", "User", user.id, {})
    notify_user(user.id, "Password Changed", "Your password was updated successfully.", "success")
    db.session.commit()
    return user


def request_password_reset(email: str) -> str:
    email_clean = (email or "").lower().strip()
    user = User.query.filter_by(email=email_clean, deleted_at=None).first()

    if not user:
        raise AuthenticationError("If the account exists, a reset link can be generated.")

    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    token_row = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.session.add(token_row)
    db.session.flush()

    log_action(user.id, "password_reset_requested", "User", user.id, {})
    db.session.commit()
    return raw_token


def reset_password(raw_token: str, new_password: str) -> User:
    if not strong_password(new_password):
        raise ValidationError(
            "Password must be at least 12 characters and include uppercase, lowercase, digit, and special character."
        )

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token_row = PasswordResetToken.query.filter_by(token_hash=token_hash).first()

    if not token_row or not token_row.is_valid():
        raise AuthenticationError("Reset token is invalid or expired.")

    user = token_row.user
    user.set_password(new_password)
    user.must_change_password = False
    token_row.used_at = datetime.utcnow()

    db.session.flush()
    log_action(user.id, "password_reset_completed", "User", user.id, {})
    notify_user(user.id, "Password Reset", "Your password was reset successfully.", "success")
    db.session.commit()
    return user


def create_api_tokens(user: User) -> dict:
    identity = str(user.id)
    return {
        "access_token": create_access_token(identity=identity, additional_claims={"role": user.role.name}),
        "refresh_token": create_refresh_token(identity=identity, additional_claims={"role": user.role.name}),
    }
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from flask_login import UserMixin
from sqlalchemy import Index, UniqueConstraint, func

from app.extensions import db, login_manager


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)


class Role(TimestampMixin, db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)

    users = db.relationship("User", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class Department(TimestampMixin, db.Model):
    __tablename__ = "departments"
    
    department_admins = db.relationship("DepartmentAdmin", back_populates="department")
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    students = db.relationship("Student", back_populates="department")
    supervisors = db.relationship("Supervisor", back_populates="department")
    projects = db.relationship("Project", back_populates="department")

    def __repr__(self) -> str:
        return f"<Department {self.code} - {self.name}>"


class AcademicSession(TimestampMixin, db.Model):
    __tablename__ = "academic_sessions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=False)

    projects = db.relationship("Project", back_populates="academic_session")

    def __repr__(self) -> str:
        return f"<AcademicSession {self.name}>"


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(
        db.Integer,
        db.ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    full_name = db.Column(db.String(120), nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    role = db.relationship("Role", back_populates="users")
    student = db.relationship(
        "Student",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    department_admin = db.relationship(
        "DepartmentAdmin",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    supervisor = db.relationship(
        "Supervisor",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    notifications = db.relationship("Notification", back_populates="user")
    audit_logs = db.relationship("AuditLog", back_populates="user")
    password_reset_tokens = db.relationship("PasswordResetToken", back_populates="user")

    def set_password(self, password: str) -> None:
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles: str) -> bool:
        return self.role is not None and self.role.name in roles

    def is_locked(self) -> bool:
        return self.locked_until is not None and self.locked_until > datetime.utcnow()

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role.name if self.role else None,
            "must_change_password": self.must_change_password,
        }
        
class DepartmentAdmin(TimestampMixin, db.Model):
    __tablename__ = "department_admins"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    user = db.relationship("User", back_populates="department_admin")
    department = db.relationship("Department", back_populates="department_admins")

    def __repr__(self) -> str:
        return f"<DepartmentAdmin user={self.user_id} department={self.department_id}>"


class Student(TimestampMixin, db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    matric_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    level = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(255), nullable=True)

    user = db.relationship("User", back_populates="student")
    department = db.relationship("Department", back_populates="students")
    projects = db.relationship("Project", back_populates="student")

    def __repr__(self) -> str:
        return f"<Student {self.matric_no}>"


class Supervisor(TimestampMixin, db.Model):
    __tablename__ = "supervisors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    staff_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    title = db.Column(db.String(50), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    max_students = db.Column(db.Integer, nullable=False, default=30)

    user = db.relationship("User", back_populates="supervisor")
    department = db.relationship("Department", back_populates="supervisors")
    projects = db.relationship("Project", back_populates="supervisor")

    def __repr__(self) -> str:
        return f"<Supervisor {self.staff_no}>"


class Project(TimestampMixin, db.Model):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "academic_session_id",
            name="uq_project_student_session",
        ),
        Index("ix_project_status_stage", "status", "current_stage"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supervisor_id = db.Column(
        db.Integer,
        db.ForeignKey("supervisors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    academic_session_id = db.Column(
        db.Integer,
        db.ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(255), nullable=True)
    abstract = db.Column(db.Text, nullable=True)
    current_stage = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="in_review")
    completed_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship("Student", back_populates="projects")
    supervisor = db.relationship("Supervisor", back_populates="projects")
    department = db.relationship("Department", back_populates="projects")
    academic_session = db.relationship("AcademicSession", back_populates="projects")
    submissions = db.relationship(
        "Submission",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Submission.version.asc()",
    )
    archived_record = db.relationship(
        "ArchivedProject",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Project {self.id} - {self.title or 'Untitled'}>"


class Submission(TimestampMixin, db.Model):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("project_id", "stage", "version", name="uq_submission_version"),
        Index("ix_submission_project_stage_status", "project_id", "stage", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submitted_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stage = db.Column(db.String(30), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)

    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    checksum = db.Column(db.String(64), nullable=False, index=True)

    extracted_text = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    similarity_score = db.Column(db.Float, nullable=False, default=0.0)
    ai_risk_level = db.Column(db.String(20), nullable=False, default="green")

    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    project = db.relationship("Project", back_populates="submissions")
    submitted_by = db.relationship("User")
    plagiarism_report = db.relationship(
        "PlagiarismReport",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )
    approval = db.relationship(
        "Approval",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )
    feedback = db.relationship(
        "SupervisorFeedback",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Submission {self.id} stage={self.stage} v{self.version}>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "stage": self.stage,
            "version": self.version,
            "status": self.status,
            "similarity_score": round(self.similarity_score * 100, 2),
            "risk_level": self.ai_risk_level,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
        }


class Approval(TimestampMixin, db.Model):
    __tablename__ = "approvals"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(
        db.Integer,
        db.ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    reviewer_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decision = db.Column(db.String(30), nullable=False, index=True)
    remarks = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    submission = db.relationship("Submission", back_populates="approval")
    reviewer = db.relationship("User")

    def __repr__(self) -> str:
        return f"<Approval submission={self.submission_id} decision={self.decision}>"


class SupervisorFeedback(TimestampMixin, db.Model):
    __tablename__ = "supervisor_feedback"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(
        db.Integer,
        db.ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    supervisor_id = db.Column(
        db.Integer,
        db.ForeignKey("supervisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    comments = db.Column(db.Text, nullable=False)
    annotations_json = db.Column(db.JSON, nullable=True)

    submission = db.relationship("Submission", back_populates="feedback")
    supervisor = db.relationship("Supervisor")

    def __repr__(self) -> str:
        return f"<SupervisorFeedback submission={self.submission_id}>"


class PlagiarismReport(TimestampMixin, db.Model):
    __tablename__ = "plagiarism_reports"
    __table_args__ = (Index("ix_plagiarism_similarity", "overall_similarity"),)

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(
        db.Integer,
        db.ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    overall_similarity = db.Column(db.Float, nullable=False, default=0.0)
    risk_level = db.Column(db.String(20), nullable=False, default="green", index=True)
    matched_documents_json = db.Column(db.JSON, nullable=True)
    suspicious_sections_json = db.Column(db.JSON, nullable=True)
    report_file_path = db.Column(db.String(500), nullable=False)
    generated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    submission = db.relationship("Submission", back_populates="plagiarism_report")

    def __repr__(self) -> str:
        return f"<PlagiarismReport submission={self.submission_id} score={self.overall_similarity}>"


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "is_read"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = db.Column(db.String(30), nullable=False, default="info")
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    action_url = db.Column(db.String(500), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    read_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification {self.id} to={self.user_id}>"


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_user_entity", "user_id", "entity_type"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} entity={self.entity_type}:{self.entity_id}>"


class ArchivedProject(TimestampMixin, db.Model):
    __tablename__ = "archived_projects"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    archived_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    archive_reason = db.Column(db.String(255), nullable=True)
    archived_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    data_snapshot = db.Column(db.JSON, nullable=False)

    project = db.relationship("Project", back_populates="archived_record")
    archived_by = db.relationship("User")

    def __repr__(self) -> str:
        return f"<ArchivedProject project={self.project_id}>"


class SystemSetting(TimestampMixin, db.Model):
    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=True)

    @classmethod
    def get(cls, key: str, default: str | None = None) -> str | None:
        row = cls.query.filter_by(key=key, deleted_at=None).first()
        return row.value if row else default

    @classmethod
    def get_float(cls, key: str, default: float) -> float:
        raw = cls.get(key, None)
        if raw is None:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    def __repr__(self) -> str:
        return f"<SystemSetting {self.key}>"


class PasswordResetToken(TimestampMixin, db.Model):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (Index("ix_reset_user_used", "user_id", "used_at"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="password_reset_tokens")

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > datetime.utcnow()

    def __repr__(self) -> str:
        return f"<PasswordResetToken user={self.user_id}>"


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


from __future__ import annotations

from datetime import datetime

from flask import current_app

from app.extensions import db
from app.models.core import (
    AcademicSession,
    ArchivedProject,
    Approval,
    Department,
    PlagiarismReport,
    Project,
    Student,
    Submission,
    SupervisorFeedback,
)
from app.services.audit_service import log_action
from app.services.notification_service import notify_user
from app.services.plagiarism_service import extract_text_from_file, generate_plagiarism_report
from app.services.workflow_service import STAGES, can_submit_stage, next_stage, workflow_complete
from app.utils.errors import FileError, ValidationError, WorkflowError
from app.utils.files import save_upload


def get_active_session() -> AcademicSession:
    session = AcademicSession.query.filter_by(is_active=True, deleted_at=None).first()
    if not session:
        raise WorkflowError("No active academic session is configured.")
    return session


def get_or_create_project(student: Student, title: str | None = None) -> Project:
    active_session = get_active_session()

    project = Project.query.filter_by(
        student_id=student.id,
        academic_session_id=active_session.id,
        deleted_at=None,
    ).first()

    if project:
        if title and not project.title:
            project.title = title
        return project

    if not title:
        raise ValidationError("Project title is required for proposal submission.")

    project = Project(
        student_id=student.id,
        department_id=student.department_id,
        academic_session_id=active_session.id,
        title=title,
        status="in_review",
    )
    db.session.add(project)
    db.session.flush()
    return project


def get_latest_stage_version(project_id: int, stage: str) -> int:
    latest = (
        Submission.query.filter_by(project_id=project_id, stage=stage, deleted_at=None)
        .order_by(Submission.version.desc())
        .first()
    )
    return (latest.version + 1) if latest else 1


def create_submission(user, stage: str, file_obj, title: str | None = None) -> Submission:
    if stage not in STAGES:
        raise WorkflowError("Invalid submission stage.")

    student = user.student
    if not student:
        raise ValidationError("Student profile is missing.")

    project = get_or_create_project(student, title if stage == "proposal" else None)

    allowed, reason = can_submit_stage(project, stage)
    if not allowed:
        raise WorkflowError(reason)

    folder_prefix = f"student_{student.id}/project_{project.id}/{stage}"
    file_info = save_upload(file_obj, stage, folder_prefix)

    submission = Submission(
        project_id=project.id,
        submitted_by_user_id=user.id,
        stage=stage,
        version=get_latest_stage_version(project.id, stage),
        original_filename=file_info["original_filename"],
        stored_filename=file_info["stored_filename"],
        storage_path=file_info["storage_path"],
        file_size=file_info["file_size"],
        mime_type=file_info["mime_type"],
        checksum=file_info["checksum"],
        status="pending",
    )

    if stage in STAGES[:-1]:
        extracted = extract_text_from_file(file_info["storage_path"])
        if not extracted.strip():
            raise FileError("Unable to extract analyzable text from the uploaded file.")
        submission.extracted_text = extracted
    else:
        submission.extracted_text = None

    db.session.add(submission)
    db.session.flush()

    project.status = "in_review"
    if stage == "proposal" and title:
        project.title = title

    if stage in STAGES[:-1]:
        report = generate_plagiarism_report(submission)
        db.session.add(report)

    notify_user(
        project.supervisor.user_id if project.supervisor else user.id,
        "New Submission Uploaded",
        f"{user.full_name} uploaded {stage} for review.",
        "info",
        action_url=f"/supervisor/submissions/{submission.id}/review",
    )
    notify_user(
        user.id,
        "Submission Received",
        f"Your {stage} submission was successfully uploaded.",
        "success",
        action_url=f"/student/submissions/{submission.id}",
    )

    log_action(user.id, "submission_created", "Submission", submission.id, {"stage": stage, "project_id": project.id})
    db.session.commit()
    return submission


def review_submission(
    submission: Submission,
    reviewer_user,
    decision: str,
    remarks: str | None = None,
    comments: str | None = None,
    annotations: list[dict] | None = None,
) -> Submission:
    if decision not in {"approved", "rejected", "revision_requested"}:
        raise ValidationError("Invalid review decision.")

    if submission.status == "approved":
        raise WorkflowError("This submission has already been approved.")

    submission.status = decision
    approval = Approval(
        submission_id=submission.id,
        reviewer_user_id=reviewer_user.id,
        decision=decision,
        remarks=remarks,
        reviewed_at=datetime.utcnow(),
    )
    db.session.add(approval)

    if comments:
        feedback = SupervisorFeedback(
            submission_id=submission.id,
            supervisor_id=reviewer_user.supervisor.id,
            comments=comments,
            annotations_json=annotations or [],
        )
        db.session.add(feedback)

    project = submission.project

    if decision == "approved":
        project.current_stage = submission.stage
        if submission.stage == "source_code":
            project.status = "completed"
            project.completed_at = datetime.utcnow()

            archived = ArchivedProject(
                project_id=project.id,
                archive_reason="Final source code approved",
                archived_by_user_id=reviewer_user.id,
                data_snapshot={
                    "project": {
                        "id": project.id,
                        "title": project.title,
                        "student_id": project.student_id,
                        "supervisor_id": project.supervisor_id,
                        "academic_session_id": project.academic_session_id,
                        "status": project.status,
                    },
                    "latest_submission_id": submission.id,
                },
            )
            db.session.add(archived)
            project.status = "archived"

        notify_user(
            project.student.user_id,
            "Approval Granted",
            f"Your {submission.stage} submission has been approved.",
            "success",
            action_url=f"/student/submissions/{submission.id}",
        )

    elif decision == "rejected":
        notify_user(
            project.student.user_id,
            "Submission Rejected",
            f"Your {submission.stage} submission was rejected.",
            "danger",
            action_url=f"/student/submissions/{submission.id}",
        )
    else:
        notify_user(
            project.student.user_id,
            "Revision Requested",
            f"Revisions were requested for your {submission.stage} submission.",
            "warning",
            action_url=f"/student/submissions/{submission.id}",
        )

    log_action(
        reviewer_user.id,
        "submission_reviewed",
        "Submission",
        submission.id,
        {"decision": decision, "stage": submission.stage, "project_id": project.id},
    )

    db.session.commit()
    return submission


def serialize_project(project: Project) -> dict:
    return {
        "id": project.id,
        "title": project.title,
        "status": project.status,
        "current_stage": project.current_stage,
        "student": project.student.user.full_name,
        "supervisor": project.supervisor.user.full_name if project.supervisor else None,
        "session": project.academic_session.name,
    }
    
def assign_supervisor_to_student(student: Student, supervisor: Supervisor) -> Project:
    """
    Assign a supervisor to a registered student.

    This creates or updates the student's project for the active session.
    """
    active_session = get_active_session()

    project = Project.query.filter_by(
        student_id=student.id,
        academic_session_id=active_session.id,
        deleted_at=None,
    ).first()

    if not project:
        project = Project(
            student_id=student.id,
            department_id=student.department_id,
            academic_session_id=active_session.id,
            title=None,
            status="assigned",
        )
        db.session.add(project)
        db.session.flush()

    project.supervisor_id = supervisor.id
    project.department_id = student.department_id
    project.status = "assigned"

    return project
from __future__ import annotations


from collections import Counter
from datetime import datetime

from app.models.core import (
    ArchivedProject,
    Department,
    PlagiarismReport,
    DepartmentAdmin,
    Student,
    Supervisor,
    Project,
    Submission,
    User,
)


def _monthly_bucket(dt: datetime) -> str:
    return dt.strftime("%Y-%m") if dt else "unknown"


def get_student_dashboard_data(student_id: int) -> dict:
    project = (
        Project.query.filter_by(student_id=student_id, deleted_at=None)
        .order_by(Project.created_at.desc())
        .first()
    )

    submissions = []
    if project:
        submissions = (
            Submission.query.filter_by(project_id=project.id, deleted_at=None)
            .order_by(Submission.submitted_at.desc())
            .all()
        )

    pending = sum(1 for s in submissions if s.status == "pending")
    approved = sum(1 for s in submissions if s.status == "approved")
    rejected = sum(1 for s in submissions if s.status == "rejected")
    avg_similarity = (
        round(sum(s.similarity_score for s in submissions) / len(submissions) * 100, 2)
        if submissions
        else 0.0
    )

    return {
        "project": project,
        "submissions": submissions,
        "cards": [
            {"label": "Pending Reviews", "value": pending},
            {"label": "Approved", "value": approved},
            {"label": "Rejected", "value": rejected},
            {"label": "Avg Similarity", "value": f"{avg_similarity}%"},
        ],
        "next_stage": "proposal" if not project else project.current_stage,
    }


def get_supervisor_dashboard_data(supervisor_id: int) -> dict:
    projects = Project.query.filter_by(supervisor_id=supervisor_id, deleted_at=None).all()
    pending_reviews = Submission.query.join(Project).filter(
        Project.supervisor_id == supervisor_id,
        Submission.status == "pending",
        Submission.deleted_at.is_(None),
        Project.deleted_at.is_(None),
    ).all()

    project_labels = []
    project_values = []

    for project in projects[:6]:
        student_name = (
            project.student.user.full_name
            if project.student and project.student.user
            else "Unknown Student"
        )
        project_labels.append(student_name)
        project_values.append(
            len([s for s in project.submissions if s.deleted_at is None])
        )

    avg_similarity = (
        round(sum(s.similarity_score for s in pending_reviews) / len(pending_reviews) * 100, 2)
        if pending_reviews
        else 0.0
    )

    return {
        "projects": projects,
        "pending_reviews": pending_reviews,
        "project_labels": project_labels,
        "project_values": project_values,
        "cards": [
            {"label": "Assigned Projects", "value": len(projects)},
            {"label": "Pending Reviews", "value": len(pending_reviews)},
            {"label": "Avg Pending Similarity", "value": f"{avg_similarity}%"},
        ],
    }


def get_admin_dashboard_data() -> dict:
    total_students = User.query.join(User.student).count()
    total_supervisors = User.query.join(User.supervisor).count()
    total_projects = Project.query.filter_by(deleted_at=None).count()
    total_submissions = Submission.query.filter_by(deleted_at=None).count()
    pending_reviews = Submission.query.filter_by(status="pending", deleted_at=None).count()
    completed_projects = Project.query.filter(
        Project.status.in_(["completed", "archived"]),
        Project.deleted_at.is_(None),
    ).count()
    archived_projects = ArchivedProject.query.filter_by(deleted_at=None).count()

    all_submissions = Submission.query.filter_by(deleted_at=None).all()
    plagiarism_reports = PlagiarismReport.query.all()

    monthly_submissions = Counter()
    plagiarism_trend = Counter()
    stage_counts = Counter()

    for submission in all_submissions:
        if submission.submitted_at:
            monthly_submissions[_monthly_bucket(submission.submitted_at)] += 1
        stage_counts[submission.stage] += 1
        plagiarism_trend[_monthly_bucket(submission.submitted_at)] += round(
            submission.similarity_score * 100,
            2,
        )

    avg_similarity = (
        round(sum(r.overall_similarity for r in plagiarism_reports) / len(plagiarism_reports) * 100, 2)
        if plagiarism_reports
        else 0.0
    )

    departments = Department.query.filter_by(deleted_at=None).all()
    department_labels = [d.name for d in departments]
    department_values = [
        Project.query.filter_by(department_id=d.id, deleted_at=None).count()
        for d in departments
    ]

    return {
        "cards": [
            {"label": "Students", "value": total_students},
            {"label": "Supervisors", "value": total_supervisors},
            {"label": "Projects", "value": total_projects},
            {"label": "Pending Reviews", "value": pending_reviews},
            {"label": "Completed", "value": completed_projects},
            {"label": "Archived Projects", "value": archived_projects},
            {"label": "Avg Similarity", "value": f"{avg_similarity}%"},
            {"label": "Submissions", "value": total_submissions},
        ],
        "monthly_labels": sorted(monthly_submissions.keys()),
        "monthly_values": [monthly_submissions[k] for k in sorted(monthly_submissions.keys())],
        "plagiarism_labels": sorted(plagiarism_trend.keys()),
        "plagiarism_values": [plagiarism_trend[k] for k in sorted(plagiarism_trend.keys())],
        "department_labels": department_labels,
        "department_values": department_values,
        "stage_counts": dict(stage_counts),
    }


def get_archived_projects_data() -> dict:
    archived_records = (
        ArchivedProject.query.filter_by(deleted_at=None)
        .order_by(ArchivedProject.archived_at.desc())
        .all()
    )

    items = []
    for archive in archived_records:
        project = archive.project
        items.append(
            {
                "archive_id": archive.id,
                "project_id": project.id if project else None,
                "title": project.title if project and project.title else "Untitled Project",
                "student": (
                    project.student.user.full_name
                    if project and project.student and project.student.user
                    else "Unknown Student"
                ),
                "supervisor": (
                    project.supervisor.user.full_name
                    if project and project.supervisor and project.supervisor.user
                    else "Unassigned"
                ),
                "department": project.department.name if project and project.department else "N/A",
                "session": (
                    project.academic_session.name
                    if project and project.academic_session
                    else "N/A"
                ),
                "status": project.status if project else "archived",
                "archived_at": archive.archived_at.strftime("%b %d, %Y %H:%M")
                if archive.archived_at
                else "N/A",
                "reason": archive.archive_reason or "No reason provided",
                "latest_submission_id": archive.data_snapshot.get("latest_submission_id")
                if archive.data_snapshot
                else None,
            }
        )

    return {
        "items": items,
        "count": len(items),
        "latest": items[0] if items else None,
    }


def get_admin_reports_data() -> dict:
    submissions = (
        Submission.query.filter_by(deleted_at=None)
        .order_by(Submission.submitted_at.desc())
        .all()
    )
    reports = PlagiarismReport.query.all()
    departments = Department.query.filter_by(deleted_at=None).order_by(Department.name).all()

    risk_counter = Counter()
    stage_counter = Counter()

    rows = []
    for submission in submissions:
        stage_counter[submission.stage] += 1

        report = submission.plagiarism_report
        risk = report.risk_level if report else "green"
        if report:
            risk_counter[risk] += 1

        rows.append(
            {
                "submission_id": submission.id,
                "student": (
                    submission.project.student.user.full_name
                    if submission.project and submission.project.student and submission.project.student.user
                    else "Unknown Student"
                ),
                "matric_no": (
                    submission.project.student.matric_no
                    if submission.project and submission.project.student
                    else "N/A"
                ),
                "department": (
                    submission.project.department.name
                    if submission.project and submission.project.department
                    else "N/A"
                ),
                "supervisor": (
                    submission.project.supervisor.user.full_name
                    if submission.project and submission.project.supervisor and submission.project.supervisor.user
                    else "Unassigned"
                ),
                "project_title": (
                    submission.project.title if submission.project and submission.project.title else "Untitled Project"
                ),
                "stage": submission.stage,
                "version": submission.version,
                "status": submission.status,
                "similarity": round(submission.similarity_score * 100, 2),
                "risk": submission.ai_risk_level,
                "submitted_at": submission.submitted_at.strftime("%b %d, %Y %H:%M")
                if submission.submitted_at
                else "N/A",
            }
        )

    avg_similarity = (
        round(sum(r.overall_similarity for r in reports) / len(reports) * 100, 2)
        if reports
        else 0.0
    )

    department_labels = [d.name for d in departments]
    department_values = [
        Project.query.filter_by(department_id=d.id, deleted_at=None).count()
        for d in departments
    ]

    return {
        "cards": [
            {"label": "Reports Generated", "value": len(reports)},
            {"label": "Avg Similarity", "value": f"{avg_similarity}%"},
            {"label": "Red Risk Reports", "value": risk_counter.get("red", 0)},
            {"label": "Yellow Risk Reports", "value": risk_counter.get("yellow", 0)},
            {"label": "Green Risk Reports", "value": risk_counter.get("green", 0)},
            {"label": "Archived Projects", "value": ArchivedProject.query.filter_by(deleted_at=None).count()},
        ],
        "risk_labels": ["green", "yellow", "red"],
        "risk_values": [
            risk_counter.get("green", 0),
            risk_counter.get("yellow", 0),
            risk_counter.get("red", 0),
        ],
        "stage_labels": list(stage_counter.keys()),
        "stage_values": list(stage_counter.values()),
        "department_labels": department_labels,
        "department_values": department_values,
        "rows": rows,
    }


def get_admin_report_rows() -> list[dict]:
    """
    Simple exportable row set for CSV downloads.
    """
    return get_admin_reports_data()["rows"]

def get_department_admin_dashboard_data(department_id: int) -> dict:
    students = (
        Student.query.filter_by(department_id=department_id, deleted_at=None)
        .join(Student.user)
        .order_by(Student.matric_no.asc())
        .all()
    )

    supervisors = (
        Supervisor.query.filter_by(department_id=department_id, deleted_at=None)
        .join(Supervisor.user)
        .order_by(Supervisor.staff_no.asc())
        .all()
    )

    projects = Project.query.filter_by(department_id=department_id, deleted_at=None).all()

    pending_reviews = Submission.query.join(Project).filter(
        Project.department_id == department_id,
        Submission.status == "pending",
        Submission.deleted_at.is_(None),
        Project.deleted_at.is_(None),
    ).all()

    return {
        "students": students,
        "supervisors": supervisors,
        "projects": projects,
        "pending_reviews": pending_reviews,
        "cards": [
            {"label": "Registered Students", "value": len(students)},
            {"label": "Supervisors", "value": len(supervisors)},
            {"label": "Projects", "value": len(projects)},
            {"label": "Pending Reviews", "value": len(pending_reviews)},
        ],
    }
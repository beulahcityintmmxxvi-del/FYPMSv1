from app.extensions import db
from app.models.core import AcademicSession, Project, Student
from app.services.workflow_service import can_submit_stage


def test_proposal_is_allowed_first(app):
    with app.app_context():
        student = Student.query.filter_by(matric_no="2460141000").first()
        session = AcademicSession.query.filter_by(is_active=True).first()

        project = Project(
            student_id=student.id,
            department_id=student.department_id,
            academic_session_id=session.id,
            title="Test Project",
            status="in_review",
        )
        db.session.add(project)
        db.session.commit()

        allowed, reason = can_submit_stage(project, "proposal")
        assert allowed is True
        assert reason == ""


def test_chapter_two_blocked_before_chapter_one_approval(app):
    with app.app_context():
        student = Student.query.filter_by(matric_no="2460141000").first()
        session = AcademicSession.query.filter_by(is_active=True).first()

        project = Project(
            student_id=student.id,
            department_id=student.department_id,
            academic_session_id=session.id,
            title="Test Project",
            status="in_review",
        )
        db.session.add(project)
        db.session.commit()

        allowed, reason = can_submit_stage(project, "chapter2")
        assert allowed is False
        assert "chapter1" in reason.lower()
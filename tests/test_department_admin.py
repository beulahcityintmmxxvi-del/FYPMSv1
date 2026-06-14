from app.extensions import db
from app.models.core import Department, Role, Student, Supervisor, User
from app.services.auth_service import register_department_admin
from app.services.submission_service import assign_supervisor_to_student


def test_register_department_admin(app):
    with app.app_context():
        dept = Department.query.filter_by(code="CSC").first()

        user = register_department_admin(
            full_name="Dept Admin One",
            email="deptadmin1@fpi.edu.ng",
            password="StrongPass123!",
            department_id=dept.id,
            phone="08000000000",
        )

        assert user.role.name == "department_admin"
        assert user.department_admin is not None
        assert user.department_admin.department_id == dept.id


def test_assign_supervisor_to_student_in_same_department(app):
    with app.app_context():
        dept = Department.query.filter_by(code="CSC").first()
        student_role = Role.query.filter_by(name="student").first()
        supervisor_role = Role.query.filter_by(name="supervisor").first()

        student_user = User(
            full_name="Student One",
            email="student1@fpi.edu.ng",
            role=student_role,
        )
        student_user.set_password("1234567")

        student = Student(
            user=student_user,
            matric_no="2460141101",
            department_id=dept.id,
            level="HND II",
        )

        supervisor_user = User(
            full_name="Supervisor One",
            email="super1@fpi.edu.ng",
            role=supervisor_role,
        )
        supervisor_user.set_password("StrongPass123!")

        supervisor = Supervisor(
            user=supervisor_user,
            staff_no="SUP/001",
            department_id=dept.id,
            title="Dr.",
        )

        db.session.add_all([student_user, student, supervisor_user, supervisor])
        db.session.commit()

        project = assign_supervisor_to_student(student, supervisor)
        db.session.commit()

        assert project.supervisor_id == supervisor.id
        assert project.department_id == dept.id
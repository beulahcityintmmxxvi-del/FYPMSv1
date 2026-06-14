from app.extensions import db
from app.models.core import Department, DepartmentAdmin, Role, Student, User
from werkzeug.security import generate_password_hash


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_department_admin_dashboard_only_own_department_students(app, client):
    with app.app_context():
        dept = Department.query.filter_by(code="CSC").first()
        other_dept = Department.query.filter_by(code="MTE").first()
        dept_admin_role = Role.query.filter_by(name="department_admin").first()
        student_role = Role.query.filter_by(name="student").first()

        admin_user = User(
            full_name="Dept Admin",
            email="deptadmin@fpi.edu.ng",
            role=dept_admin_role,
            password_hash=generate_password_hash("StrongPass123!"),
        )
        admin_profile = DepartmentAdmin(user=admin_user, department_id=dept.id)

        student_user_1 = User(
            full_name="Student A",
            email="studenta@fpi.edu.ng",
            role=student_role,
            password_hash=generate_password_hash("1234567"),
        )
        student_1 = Student(
            user=student_user_1,
            matric_no="2460141102",
            department_id=dept.id,
            level="HND II",
        )

        student_user_2 = User(
            full_name="Student B",
            email="studentb@fpi.edu.ng",
            role=student_role,
            password_hash=generate_password_hash("1234567"),
        )
        student_2 = Student(
            user=student_user_2,
            matric_no="2460141103",
            department_id=other_dept.id,
            level="HND II",
        )

        db.session.add_all([admin_user, admin_profile, student_user_1, student_1, student_user_2, student_2])
        db.session.commit()

        login_as(client, admin_user.id)
        response = client.get("/department-admin/")
        assert response.status_code == 200
        assert b"Student A" in response.data
        assert b"Student B" not in response.data
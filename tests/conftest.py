from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models.core import AcademicSession, Department, Role, Student, User


@pytest.fixture
def app():
    app = create_app("testing")

    with app.app_context():
        db.create_all()

        roles = [
            Role(name="student"),
            Role(name="supervisor"),
            Role(name="admin"),
            Role(name="department_admin"),
        ]

        departments = [
            Department(code="CSC", name="Computer Science"),
            Department(code="MTE", name="Mechatronics Engineering"),
            Department(code="SLT", name="Science Lab Tech"),
            Department(code="FTH", name="Food Technology"),
            Department(code="HMT", name="Hospitality Management"),
            Department(code="EEE", name="Electrical Engineering"),
            Department(code="MEE", name="Mechanical Engineering"),
            Department(code="ACC", name="Accountancy"),
            Department(code="MKT", name="Marketing"),
            Department(code="PAB", name="Public Administration"),
            Department(code="BBA", name="Business Administration"),
        ]

        session = AcademicSession(
            name="2024/2025",
            start_date=date(2024, 9, 1),
            end_date=date(2025, 8, 30),
            is_active=True,
        )

        db.session.add_all(roles + departments + [session])
        db.session.commit()

        # Seed one student for workflow tests
        student_role = Role.query.filter_by(name="student").first()
        csc_dept = Department.query.filter_by(code="CSC").first()

        student_user = User(
            full_name="Seed Student",
            email="seedstudent@fpi.edu.ng",
            role=student_role,
        )
        student_user.set_password("1234567")

        student = Student(
            user=student_user,
            matric_no="2460141000",
            department_id=csc_dept.id,
            level="HND II",
        )

        db.session.add_all([student_user, student])
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
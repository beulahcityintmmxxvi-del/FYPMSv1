import json

from flask import Blueprint, abort, flash, render_template, redirect, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import SupervisorAssignForm
from app.models.core import Student, Supervisor
from app.services.audit_service import log_action
from app.services.notification_service import notify_user
from app.services.reporting_service import get_department_admin_dashboard_data
from app.services.submission_service import assign_supervisor_to_student
from app.utils.permissions import role_required

department_admin_bp = Blueprint("department_admin", __name__, url_prefix="/department-admin")


@department_admin_bp.route("/")
@login_required
@role_required("department_admin")
def dashboard():
    dept_id = current_user.department_admin.department_id
    data = get_department_admin_dashboard_data(dept_id)

    form = SupervisorAssignForm()
    form.student_id.choices = [
        (s.id, f"{s.matric_no} - {s.user.full_name}")
        for s in data["students"]
    ]
    form.supervisor_id.choices = [
        (s.id, f"{s.staff_no} - {s.user.full_name}")
        for s in data["supervisors"]
    ]

    return render_template(
        "department_admin/dashboard.html",
        role="department_admin",
        page_title="Departmental Admin Dashboard",
        cards=data["cards"],
        students=data["students"],
        supervisors=data["supervisors"],
        pending_reviews=data["pending_reviews"],
        form=form,
    )


@department_admin_bp.route("/assign-supervisor", methods=["POST"])
@login_required
@role_required("department_admin")
def assign_supervisor():
    dept_id = current_user.department_admin.department_id
    form = SupervisorAssignForm()

    students = Student.query.filter_by(department_id=dept_id, deleted_at=None).all()
    supervisors = Supervisor.query.filter_by(department_id=dept_id, deleted_at=None).all()

    form.student_id.choices = [(s.id, f"{s.matric_no} - {s.user.full_name}") for s in students]
    form.supervisor_id.choices = [(s.id, f"{s.staff_no} - {s.user.full_name}") for s in supervisors]

    if form.validate_on_submit():
        student = Student.query.get_or_404(form.student_id.data)
        supervisor = Supervisor.query.get_or_404(form.supervisor_id.data)

        if student.department_id != dept_id or supervisor.department_id != dept_id:
            abort(403)

        project = assign_supervisor_to_student(student, supervisor)

        notify_user(
            student.user_id,
            "Supervisor Assigned",
            f"Supervisor {supervisor.user.full_name} has been assigned to your project.",
            "info",
            action_url=url_for("student.dashboard"),
        )
        notify_user(
            supervisor.user_id,
            "New Student Assigned",
            f"You have been assigned to {student.user.full_name}.",
            "info",
            action_url=url_for("supervisor.dashboard"),
        )

        log_action(
            current_user.id,
            "department_admin_assigned_supervisor",
            "Project",
            project.id,
            {"student_id": student.id, "supervisor_id": supervisor.id},
        )

        db.session.commit()
        flash("Supervisor assigned successfully.", "success")
        return redirect(url_for("department_admin.dashboard"))

    flash("Invalid assignment request.", "danger")
    return redirect(url_for("department_admin.dashboard"))
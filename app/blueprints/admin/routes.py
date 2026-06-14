import csv
import io
from datetime import datetime

from flask import Blueprint, flash, make_response, redirect, render_template, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import (
    AcademicSessionForm,
    DepartmentForm,
    SettingForm,
    SupervisorAssignForm,
    SupervisorRegistrationForm,
)
from app.models.core import ArchivedProject, Department, Project, Student, Supervisor, SystemSetting, Submission
from app.services.auth_service import register_supervisor
from app.services.export_service import build_reports_pdf, build_reports_xlsx
from app.services.notification_service import notify_user
from app.services.reporting_service import (
    get_admin_dashboard_data,
    get_admin_reports_data,
    get_archived_projects_data,
)
from app.forms import DepartmentAdminRegistrationForm
from app.services.auth_service import register_department_admin
from app.services.submission_service import assign_supervisor_to_student
from app.utils.permissions import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@role_required("admin")
def dashboard():
    data = get_admin_dashboard_data()
    return render_template(
        "admin/dashboard.html",
        role="admin",
        page_title="Admin Dashboard",
        cards=data["cards"],
        chart_data=data,
    )


@admin_bp.route("/departments", methods=["GET", "POST"])
@login_required
@role_required("admin")
def departments():
    form = DepartmentForm()
    items = Department.query.filter_by(deleted_at=None).order_by(Department.name).all()

    if form.validate_on_submit():
        try:
            dept = Department(code=form.code.data.upper().strip(), name=form.name.data.strip())
            db.session.add(dept)
            db.session.commit()
            flash("Department created successfully.", "success")
            return redirect(url_for("admin.departments"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template(
        "admin/manage.html",
        title="Departments",
        form=form,
        items=items,
        columns=[("code", "Code"), ("name", "Name"), ("is_active", "Active")],
    )


@admin_bp.route("/sessions", methods=["GET", "POST"])
@login_required
@role_required("admin")
def sessions():
    form = AcademicSessionForm()

    from app.models.core import AcademicSession
    items = AcademicSession.query.filter_by(deleted_at=None).order_by(AcademicSession.start_date.desc()).all()

    if form.validate_on_submit():
        try:
            if form.is_active.data:
                AcademicSession.query.update({"is_active": False})

            session = AcademicSession(
                name=form.name.data.strip(),
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                is_active=form.is_active.data,
            )
            db.session.add(session)
            db.session.commit()
            flash("Academic session saved.", "success")
            return redirect(url_for("admin.sessions"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template(
        "admin/manage.html",
        title="Academic Sessions",
        form=form,
        items=items,
        columns=[("name", "Session"), ("start_date", "Start"), ("end_date", "End"), ("is_active", "Active")],
    )


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@role_required("admin")
def settings():
    form = SettingForm()
    items = SystemSetting.query.filter_by(deleted_at=None).order_by(SystemSetting.key).all()

    if form.validate_on_submit():
        setting = SystemSetting.query.filter_by(key=form.key.data.strip(), deleted_at=None).first()
        if setting:
            setting.value = form.value.data.strip()
            setting.description = form.description.data
        else:
            setting = SystemSetting(
                key=form.key.data.strip(),
                value=form.value.data.strip(),
                description=form.description.data,
            )
            db.session.add(setting)
        db.session.commit()
        flash("System setting saved.", "success")
        return redirect(url_for("admin.settings"))

    return render_template(
        "admin/manage.html",
        title="System Settings",
        form=form,
        items=items,
        columns=[("key", "Key"), ("value", "Value"), ("description", "Description")],
    )


@admin_bp.route("/supervisors/register", methods=["GET", "POST"])
@login_required
@role_required("admin")
def register_supervisor_admin():
    form = SupervisorRegistrationForm()
    form.department_id.choices = [
        (d.id, d.name)
        for d in Department.query.filter_by(deleted_at=None, is_active=True).order_by(Department.name)
    ]

    if form.validate_on_submit():
        try:
            register_supervisor(
                full_name=form.full_name.data,
                email=form.email.data,
                password=form.password.data,
                staff_no=form.staff_no.data,
                department_id=form.department_id.data,
                title=form.title.data,
                phone=form.phone.data,
                bio=form.bio.data,
                must_change_password=True,
            )
            flash("Supervisor registered successfully.", "success")
            return redirect(url_for("admin.dashboard"))
        except Exception as exc:
            flash(str(exc), "danger")

    return render_template("form_page.html", title="Register Supervisor", form=form)


@admin_bp.route("/assign-supervisor", methods=["GET", "POST"])
@login_required
@role_required("admin")
def assign_supervisor():
    form = SupervisorAssignForm()

    students = (
        Student.query.filter_by(deleted_at=None)
        .join(Student.user)
        .order_by(Student.matric_no.asc())
        .all()
    )
    supervisors = (
        Supervisor.query.filter_by(deleted_at=None)
        .join(Supervisor.user)
        .order_by(Supervisor.staff_no.asc())
        .all()
    )

    form.student_id.choices = [(s.id, f"{s.matric_no} - {s.user.full_name}") for s in students]
    form.supervisor_id.choices = [(s.id, f"{s.staff_no} - {s.user.full_name}") for s in supervisors]

    if form.validate_on_submit():
        student = Student.query.get_or_404(form.student_id.data)
        supervisor = Supervisor.query.get_or_404(form.supervisor_id.data)

        active_supervisor_projects = [
            p for p in supervisor.projects
            if p.deleted_at is None and p.status != "archived"
        ]
        if len(active_supervisor_projects) >= supervisor.max_students:
            flash("Supervisor workload limit reached.", "danger")
            return redirect(url_for("admin.dashboard"))

        project = assign_supervisor_to_student(student, supervisor)

        db.session.flush()

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

        from app.services.audit_service import log_action
        log_action(
            current_user.id,
            "supervisor_assigned_to_student",
            "Project",
            project.id,
            {"student_id": student.id, "supervisor_id": supervisor.id},
        )

        db.session.commit()
        flash("Supervisor assigned to registered student successfully.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("form_page.html", title="Assign Supervisor", form=form)


@admin_bp.route("/archive/<int:project_id>", methods=["POST"])
@login_required
@role_required("admin")
def archive_project(project_id):
    project = Project.query.get_or_404(project_id)

    latest_submission = (
        Submission.query.filter_by(project_id=project.id, deleted_at=None)
        .order_by(Submission.submitted_at.desc())
        .first()
    )

    snapshot = {
        "project": {
            "id": project.id,
            "title": project.title,
            "student": project.student.user.full_name if project.student and project.student.user else None,
            "supervisor": project.supervisor.user.full_name if project.supervisor and project.supervisor.user else None,
            "department": project.department.name if project.department else None,
            "academic_session": project.academic_session.name if project.academic_session else None,
            "status": project.status,
        },
        "submissions": [s.to_dict() for s in project.submissions if s.deleted_at is None],
        "latest_submission_id": latest_submission.id if latest_submission else None,
    }

    if project.archived_record:
        project.archived_record.data_snapshot = snapshot
        project.archived_record.archive_reason = "Archived by administrator"
        project.archived_record.archived_by_user_id = current_user.id
        project.archived_record.archived_at = datetime.utcnow()
    else:
        db.session.add(
            ArchivedProject(
                project_id=project.id,
                archive_reason="Archived by administrator",
                archived_by_user_id=current_user.id,
                data_snapshot=snapshot,
            )
        )

    project.status = "archived"
    if project.completed_at is None:
        project.completed_at = datetime.utcnow()

    db.session.commit()
    flash("Project archived successfully.", "success")
    return redirect(url_for("admin.archived_projects"))


@admin_bp.route("/archived-projects")
@login_required
@role_required("admin")
def archived_projects():
    data = get_archived_projects_data()
    return render_template(
        "admin/archived_projects.html",
        role="admin",
        page_title="Archived Projects",
        archive_data=data,
    )


@admin_bp.route("/archived-projects/<int:archive_id>")
@login_required
@role_required("admin")
def archived_project_detail(archive_id):
    archive = ArchivedProject.query.get_or_404(archive_id)
    return render_template(
        "admin/archive_detail.html",
        role="admin",
        page_title="Archived Project Detail",
        archive=archive,
    )


@admin_bp.route("/reports")
@login_required
@role_required("admin")
def reports():
    data = get_admin_reports_data()
    return render_template(
        "admin/reports.html",
        role="admin",
        page_title="Institutional Reports",
        report_data=data,
    )


@admin_bp.route("/reports/export.csv")
@login_required
@role_required("admin")
def export_reports_csv():
    data = get_admin_reports_data()
    rows = data["rows"]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Submission ID",
        "Student",
        "Matric No",
        "Department",
        "Supervisor",
        "Project Title",
        "Stage",
        "Version",
        "Status",
        "Similarity %",
        "Risk",
        "Submitted At",
    ])

    for row in rows:
        writer.writerow([
            row["submission_id"],
            row["student"],
            row["matric_no"],
            row["department"],
            row["supervisor"],
            row["project_title"],
            row["stage"],
            row["version"],
            row["status"],
            row["similarity"],
            row["risk"],
            row["submitted_at"],
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=institutional_report.csv"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response


@admin_bp.route("/reports/export.pdf")
@login_required
@role_required("admin")
def export_reports_pdf():
    data = get_admin_reports_data()
    pdf_buffer = build_reports_pdf(data)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="institutional_report.pdf",
        mimetype="application/pdf",
    )


@admin_bp.route("/reports/export.xlsx")
@login_required
@role_required("admin")
def export_reports_xlsx():
    data = get_admin_reports_data()
    xlsx_buffer = build_reports_xlsx(data)
    return send_file(
        xlsx_buffer,
        as_attachment=True,
        download_name="institutional_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@admin_bp.route("/department-admins/register", methods=["GET", "POST"])
@login_required
@role_required("admin")
def register_department_admin_admin():
    form = DepartmentAdminRegistrationForm()
    form.department_id.choices = [
        (d.id, d.name)
        for d in Department.query.filter_by(deleted_at=None, is_active=True).order_by(Department.name)
    ]

    if form.validate_on_submit():
        try:
            register_department_admin(
                full_name=form.full_name.data,
                email=form.email.data,
                password=form.password.data,
                department_id=form.department_id.data,
                phone=form.phone.data,
                must_change_password=True,
            )
            flash("Departmental admin created successfully.", "success")
            return redirect(url_for("admin.dashboard"))
        except Exception as exc:
            flash(str(exc), "danger")

    return render_template("form_page.html", title="Create Departmental Admin", form=form)
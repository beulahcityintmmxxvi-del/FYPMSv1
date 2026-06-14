import json
import os

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.forms import SubmissionForm
from app.models.core import PlagiarismReport, Project, Submission
from app.services.reporting_service import get_student_dashboard_data
from app.services.submission_service import create_submission
from app.services.workflow_service import STAGES, next_unlocked_stage
from app.utils.permissions import role_required

student_bp = Blueprint("student", __name__, url_prefix="/student")


@student_bp.route("/")
@login_required
@role_required("student")
def dashboard():
    data = get_student_dashboard_data(current_user.student.id)
    project = data["project"]
    allowed_stage = next_unlocked_stage(project) if project else "proposal"

    return render_template(
        "student/dashboard.html",
        role="student",
        page_title="Student Dashboard",
        cards=data["cards"],
        project=project,
        submissions=data["submissions"],
        allowed_stage=allowed_stage,
    )


@student_bp.route("/submit/<stage>", methods=["GET", "POST"])
@login_required
@role_required("student")
def submit(stage):
    if stage not in STAGES:
        abort(404)

    data = get_student_dashboard_data(current_user.student.id)
    project = data["project"]
    if project and project.status == "archived":
        flash("This project has already been archived.", "warning")
        return redirect(url_for("student.dashboard"))

    form = SubmissionForm()

    if request.method == "POST" and form.validate_on_submit():
        try:
            submission = create_submission(
                current_user,
                stage=stage,
                file_obj=form.file.data,
                title=form.title.data,
            )
            flash(f"{stage.capitalize()} submitted successfully.", "success")
            return redirect(url_for("student.submission_detail", submission_id=submission.id))
        except Exception as exc:
            flash(str(exc), "danger")

    return render_template(
        "form_page.html",
        title=f"Submit {stage.capitalize()}",
        form=form,
        upload_mode=True,
        stage=stage,
        allowed_stage=project.current_stage if project else "proposal",
    )


@student_bp.route("/submissions/<int:submission_id>")
@login_required
@role_required("student")
def submission_detail(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if submission.project.student_id != current_user.student.id:
        abort(403)

    return render_template("submissions/detail.html", submission=submission)


@student_bp.route("/reports/<int:report_id>/download")
@login_required
@role_required("student")
def download_report(report_id):
    report = PlagiarismReport.query.get_or_404(report_id)
    if report.submission.project.student_id != current_user.student.id:
        abort(403)
    return send_file(report.report_file_path, as_attachment=True, download_name=os.path.basename(report.report_file_path))
import json

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.forms import ReviewForm
from app.models.core import Submission
from app.services.reporting_service import get_supervisor_dashboard_data
from app.services.submission_service import review_submission
from app.utils.permissions import role_required

supervisor_bp = Blueprint("supervisor", __name__, url_prefix="/supervisor")


@supervisor_bp.route("/")
@login_required
@role_required("supervisor")
def dashboard():
    data = get_supervisor_dashboard_data(current_user.supervisor.id)
    return render_template(
        "supervisor/dashboard.html",
        role="supervisor",
        page_title="Supervisor Dashboard",
        cards=data["cards"],
        projects=data["projects"],
        pending_reviews=data["pending_reviews"],
        project_labels=data["project_labels"],
        project_values=data["project_values"],
    )


@supervisor_bp.route("/submissions/<int:submission_id>/review", methods=["GET", "POST"])
@login_required
@role_required("supervisor")
def review_submission_view(submission_id):
    submission = Submission.query.get_or_404(submission_id)

    if submission.project.supervisor_id != current_user.supervisor.id:
        abort(403)

    form = ReviewForm()

    if form.validate_on_submit():
        try:
            annotations = json.loads(form.annotations.data) if form.annotations.data else []
            review_submission(
                submission=submission,
                reviewer_user=current_user,
                decision=form.decision.data,
                remarks=form.remarks.data,
                comments=form.comments.data,
                annotations=annotations,
            )
            flash("Review saved successfully.", "success")
            return redirect(url_for("supervisor.dashboard"))
        except Exception as exc:
            flash(str(exc), "danger")

    return render_template(
        "submissions/review.html",
        title="Review Submission",
        form=form,
        submission=submission,
    )
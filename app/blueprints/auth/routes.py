from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import limiter
from app.forms import (
    ChangePasswordForm,
    ForgotPasswordForm,
    LoginForm,
    RegistrationForm,
    ResetPasswordForm,
    SupervisorRegistrationForm,
)
from app.models.core import Department
from app.services.auth_service import (
    authenticate_user,
    change_own_password,
    register_student,
    register_supervisor,
    request_password_reset,
    reset_password,
)
from app.services.audit_service import log_action
from app.utils.errors import AuthenticationError, ValidationError
from app.utils.security import is_safe_next_url

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

def get_department_choices():
    return [
        (d.id, d.name)
        for d in Department.query.filter_by(deleted_at=None, is_active=True)
        .order_by(Department.name)
        .all()
    ]
    
@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = RegistrationForm()
    form.department_id.choices = get_department_choices()

    if form.validate_on_submit():
        try:
            register_student(
                full_name=form.full_name.data,
                email=form.email.data,
                password="1234567",
                matric_no=form.matric_no.data,
                department_id=form.department_id.data,
                level=form.level.data,
                phone=form.phone.data,
                address=form.address.data,
            )
            flash(
                "Account created successfully. Your login is your matric number and default password 1234567.",
                "success",
            )
            return redirect(url_for("auth.login"))
        except (ValidationError, AuthenticationError) as exc:
            flash(str(exc), "danger")

    return render_template("auth/register.html", form=form)


@auth_bp.route("/supervisor-register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def supervisor_register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = SupervisorRegistrationForm()
    form.department_id.choices = get_department_choices()

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
                must_change_password=False,
            )
            flash("Supervisor account created successfully.", "success")
            return redirect(url_for("auth.login"))
        except (ValidationError, AuthenticationError) as exc:
            flash(str(exc), "danger")

    return render_template("form_page.html", title="Supervisor Registration", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = LoginForm()
    next_page = request.args.get("next")

    if form.validate_on_submit():
        try:
            user = authenticate_user(
                form.identifier.data,
                form.password.data,
                request.remote_addr,
                request.headers.get("User-Agent"),
            )
            login_user(user, remember=form.remember_me.data)

            if current_app.config.get("SESSION_PERMANENT"):
                from flask import session
                session.permanent = True

            log_action(user.id, "web_login", "User", user.id, {"ip": request.remote_addr})

            if user.must_change_password:
                return redirect(url_for("auth.change_password", next=next_page or ""))

            if next_page and is_safe_next_url(next_page):
                return redirect(next_page)

            if user.has_role("student"):
                return redirect(url_for("student.dashboard"))
            if user.has_role("supervisor"):
                return redirect(url_for("supervisor.dashboard"))
            if user.has_role("department_admin"):
                return redirect(url_for("department_admin.dashboard"))
            return redirect(url_for("admin.dashboard"))
        except AuthenticationError as exc:
            flash(str(exc), "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()

    if form.validate_on_submit():
        try:
            change_own_password(current_user, form.current_password.data, form.new_password.data)
            flash("Password changed successfully.", "success")
            if current_user.has_role("student"):
                return redirect(url_for("student.dashboard"))
            if current_user.has_role("supervisor"):
                return redirect(url_for("supervisor.dashboard"))
            return redirect(url_for("admin.dashboard"))
        except (AuthenticationError, ValidationError) as exc:
            flash(str(exc), "danger")

    return render_template("form_page.html", title="Change Password", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    log_action(current_user.id, "web_logout", "User", current_user.id, {})
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    form = ForgotPasswordForm()
    reset_link = None

    if form.validate_on_submit():
        try:
            token = request_password_reset(form.email.data)
            reset_link = url_for("auth.reset_password_view", token=token, _external=True)
            flash("A reset link has been generated for your account.", "success")
        except AuthenticationError:
            flash("If the account exists, a reset link has been generated.", "info")

    return render_template("form_page.html", title="Password Reset", form=form, reset_link=reset_link)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password_view(token):
    form = ResetPasswordForm()

    if form.validate_on_submit():
        try:
            reset_password(token, form.password.data)
            flash("Password reset successful. Please log in.", "success")
            return redirect(url_for("auth.login"))
        except AuthenticationError as exc:
            flash(str(exc), "danger")
        except ValidationError as exc:
            flash(str(exc), "danger")

    return render_template("form_page.html", title="Reset Password", form=form)
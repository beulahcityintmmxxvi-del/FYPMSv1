import re

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    FileField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from app.models.core import DepartmentAdmin, Student, Supervisor, User
from app.utils.security import strong_password


class LoginForm(FlaskForm):
    identifier = StringField(
        "Matric Number / Staff No / Email",
        validators=[DataRequired(), Length(min=3, max=120)],
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Login")


class RegistrationForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=120)])
    matric_no = StringField("Matric Number", validators=[DataRequired(), Length(max=10)])
    department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
    level = StringField("Level", validators=[DataRequired(), Length(max=20)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    address = TextAreaField("Address", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Create Account")

    def validate_email(self, field):
        if field.data:
            if User.query.filter_by(email=field.data.lower().strip(), deleted_at=None).first():
                raise ValidationError("Email already registered.")

    def validate_matric_no(self, field):
        matric = field.data.strip()

        if not re.fullmatch(r"\d{10}", matric):
            raise ValidationError("Matric number must be exactly 10 digits, e.g. 2460141000.")

        if Student.query.filter_by(matric_no=matric, deleted_at=None).first():
            raise ValidationError("Matric number already exists.")


class SupervisorRegistrationForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    staff_no = StringField("Staff Number", validators=[DataRequired(), Length(max=50)])
    department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
    title = StringField("Title", validators=[Optional(), Length(max=50)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=1000)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=12)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("Create Supervisor Account")

    def validate_password(self, field):
        if not strong_password(field.data):
            raise ValidationError(
                "Password must be at least 12 characters and include uppercase, "
                "lowercase, digit, and special character."
            )

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower().strip(), deleted_at=None).first():
            raise ValidationError("Email already registered.")

    def validate_staff_no(self, field):
        if Supervisor.query.filter_by(staff_no=field.data.strip().upper(), deleted_at=None).first():
            raise ValidationError("Staff number already exists.")


class DepartmentAdminRegistrationForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=12)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("Create Department Admin")

    def validate_password(self, field):
        if not strong_password(field.data):
            raise ValidationError(
                "Password must be at least 12 characters and include uppercase, "
                "lowercase, digit, and special character."
            )

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower().strip(), deleted_at=None).first():
            raise ValidationError("Email already registered.")

    def validate_department_id(self, field):
        if DepartmentAdmin.query.filter_by(department_id=field.data, deleted_at=None).first():
            raise ValidationError("This department already has a departmental admin.")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField("Generate Reset Link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=12)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("Reset Password")

    def validate_password(self, field):
        if not strong_password(field.data):
            raise ValidationError(
                "Password must be at least 12 characters and include uppercase, "
                "lowercase, digit, and special character."
            )


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=12)])
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("new_password")],
    )
    submit = SubmitField("Change Password")

    def validate_new_password(self, field):
        if not strong_password(field.data):
            raise ValidationError(
                "Password must be at least 12 characters and include uppercase, "
                "lowercase, digit, and special character."
            )


class SubmissionForm(FlaskForm):
    title = StringField("Project Title", validators=[Optional(), Length(max=255)])
    file = FileField("Upload File", validators=[DataRequired()])
    submit = SubmitField("Submit")


class ReviewForm(FlaskForm):
    decision = SelectField(
        "Decision",
        choices=[
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("revision_requested", "Revision Requested"),
        ],
        validators=[DataRequired()],
    )
    remarks = TextAreaField("Remarks", validators=[Optional(), Length(max=2000)])
    comments = TextAreaField("Comments", validators=[Optional(), Length(max=4000)])
    annotations = TextAreaField("Annotations JSON", validators=[Optional()])
    submit = SubmitField("Save Review")


class DepartmentForm(FlaskForm):
    code = StringField("Code", validators=[DataRequired(), Length(max=20)])
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    submit = SubmitField("Save Department")


class AcademicSessionForm(FlaskForm):
    name = StringField("Session Name", validators=[DataRequired(), Length(max=30)])
    start_date = DateField("Start Date", validators=[DataRequired()])
    end_date = DateField("End Date", validators=[DataRequired()])
    is_active = BooleanField("Set Active")
    submit = SubmitField("Save Session")


class SettingForm(FlaskForm):
    key = StringField("Key", validators=[DataRequired(), Length(max=120)])
    value = StringField("Value", validators=[DataRequired(), Length(max=255)])
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Save Setting")


class SupervisorAssignForm(FlaskForm):
    student_id = SelectField("Student", coerce=int, validators=[DataRequired()])
    supervisor_id = SelectField("Supervisor", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Assign Supervisor")
from functools import wraps

from flask import abort
from flask_login import current_user


def role_required(*roles):
    """
    Restrict access to users whose role name matches one of the allowed roles.

    Usage:
        @role_required("student")
        @role_required("supervisor", "admin")
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            if not current_user.role or current_user.role.name not in roles:
                abort(403)

            return view_func(*args, **kwargs)

        return wrapped

    return decorator
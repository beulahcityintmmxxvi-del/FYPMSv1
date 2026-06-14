import re
from urllib.parse import urlparse

import bleach
from flask import request

PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{12,}$"
)


def strong_password(password: str) -> bool:
    return bool(PASSWORD_REGEX.match(password or ""))


def sanitize_text(value: str | None) -> str:
    return bleach.clean(value or "", strip=True)


def is_safe_next_url(target: str | None) -> bool:
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ("http", "https", "") and ref_url.netloc == test_url.netloc
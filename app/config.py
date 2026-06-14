import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fypms.db")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL

    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "instance/uploads")
    REPORT_FOLDER = os.getenv("REPORT_FOLDER", "instance/reports")

    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True

    WTF_CSRF_TIME_LIMIT = 3600
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

    PLAGIARISM_WARNING_THRESHOLD = float(
        os.getenv("PLAGIARISM_WARNING_THRESHOLD", "0.30")
    )
    PLAGIARISM_CRITICAL_THRESHOLD = float(
        os.getenv("PLAGIARISM_CRITICAL_THRESHOLD", "0.60")
    )

    ALLOWED_TEXT_EXTENSIONS = {"pdf", "docx", "txt"}
    ALLOWED_SOURCE_EXTENSIONS = {"zip"}
    FORCE_HTTPS = False
    TEMPLATES_AUTO_RELOAD = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(BaseConfig):
    DEBUG = False
    FORCE_HTTPS = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
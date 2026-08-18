import os

from dotenv import load_dotenv

load_dotenv()


class Config:

    # =========================================================
    # FLASK SECURITY
    # =========================================================

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "change-this-in-production"
    )

    # =========================================================
    # DATABASE
    # =========================================================

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///doc_ai.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # =========================================================
    # EMAIL
    # =========================================================

    MAIL_SERVER = os.environ.get(
        "MAIL_SERVER",
        "smtp.gmail.com"
    )

    MAIL_PORT = int(
        os.environ.get(
            "MAIL_PORT",
            587
        )
    )

    MAIL_USE_TLS = True

    MAIL_USERNAME = os.environ.get(
        "MAIL_USERNAME"
    )

    MAIL_PASSWORD = os.environ.get(
        "MAIL_PASSWORD"
    )

    # =========================================================
    # OTP
    # =========================================================

    OTP_EXPIRY_MINUTES = int(
        os.environ.get(
            "OTP_EXPIRY_MINUTES",
            5
        )
    )

    # =========================================================
    # SESSION SECURITY
    # =========================================================

    SESSION_COOKIE_HTTPONLY = True

    SESSION_COOKIE_SAMESITE = "Lax"

    # Enable this when deployed with HTTPS.
    # For local development keep it False.
    SESSION_COOKIE_SECURE = False


# =============================================================
# PADDLE
# =============================================================

os.environ[
    "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"
] = "True"
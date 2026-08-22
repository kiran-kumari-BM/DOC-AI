import os
import secrets
import hashlib
import traceback
import resend

from datetime import datetime, timedelta

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app
)

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from models import (
    db,
    User
)


# =========================================================
# BLUEPRINT
# =========================================================

auth = Blueprint(
    "auth",
    __name__
)


# =========================================================
# FLASK-MAIL COMPATIBILITY
# =========================================================
#
# app.py currently imports:
#
#     from auth import auth, mail
#
# We are using Resend instead of Flask-Mail.
#
# Keeping this variable prevents:
#
#     ImportError: cannot import name 'mail'
#
# DO NOT use mail.send().
# =========================================================

mail = None


# =========================================================
# CONFIGURATION HELPERS
# =========================================================

def get_resend_api_key():
    """
    Read Resend API key directly from the environment.

    Render environment variables are available through
    os.environ.
    """

    return os.environ.get(
        "RESEND_API_KEY"
    )


def get_mail_from():
    """
    Read sender email directly from environment.
    """

    return os.environ.get(
        "MAIL_FROM"
    )


def get_otp_expiry_minutes():
    """
    Get OTP expiry time.

    Defaults to 5 minutes.
    """

    value = os.environ.get(
        "OTP_EXPIRY_MINUTES",
        "5"
    )

    try:

        return int(value)

    except (TypeError, ValueError):

        return 5


# =========================================================
# HELPER — HASH OTP
# =========================================================

def hash_otp(otp):

    return hashlib.sha256(
        otp.encode("utf-8")
    ).hexdigest()


# =========================================================
# HELPER — GENERATE OTP
# =========================================================

def generate_otp():

    return str(
        secrets.randbelow(900000) + 100000
    )


# =========================================================
# HELPER — SEND EMAIL THROUGH RESEND
# =========================================================

def send_email(
    recipient,
    subject,
    body
):

    api_key = get_resend_api_key()

    mail_from = get_mail_from()

    # -----------------------------------------------------
    # DEBUG
    # -----------------------------------------------------

    print(
        "=" * 70,
        flush=True
    )

    print(
        "DOC AI RESEND EMAIL",
        flush=True
    )

    print(
        f"RECIPIENT: {recipient}",
        flush=True
    )

    print(
        f"RESEND_API_KEY EXISTS: {bool(api_key)}",
        flush=True
    )

    if api_key:

        print(
            f"RESEND_API_KEY PREFIX: "
            f"{api_key[:5]}...",
            flush=True
        )

    else:

        print(
            "RESEND_API_KEY PREFIX: NOT SET",
            flush=True
        )

    print(
        f"MAIL_FROM: {mail_from}",
        flush=True
    )

    print(
        f"SUBJECT: {subject}",
        flush=True
    )

    print(
        "=" * 70,
        flush=True
    )

    # -----------------------------------------------------
    # CHECK API KEY
    # -----------------------------------------------------

    if not api_key:

        raise RuntimeError(
            "RESEND_API_KEY is not configured in the environment."
        )

    # -----------------------------------------------------
    # CHECK MAIL FROM
    # -----------------------------------------------------

    if not mail_from:

        raise RuntimeError(
            "MAIL_FROM is not configured in the environment."
        )

    # -----------------------------------------------------
    # CONFIGURE RESEND
    # -----------------------------------------------------

    resend.api_key = api_key

    # -----------------------------------------------------
    # SEND EMAIL
    # -----------------------------------------------------

    try:

        response = resend.Emails.send(
            {
                "from": mail_from,
                "to": [recipient],
                "subject": subject,
                "text": body
            }
        )

        print(
            "=" * 70,
            flush=True
        )

        print(
            "DOC AI RESEND EMAIL SUCCESS",
            flush=True
        )

        print(
            f"RESEND RESPONSE: {response}",
            flush=True
        )

        print(
            "=" * 70,
            flush=True
        )

        return response

    except Exception as e:

        print(
            "=" * 70,
            flush=True
        )

        print(
            "DOC AI RESEND EMAIL FAILED",
            flush=True
        )

        print(
            f"ERROR TYPE: {type(e).__name__}",
            flush=True
        )

        print(
            f"ERROR: {str(e)}",
            flush=True
        )

        print(
            "FULL TRACEBACK:",
            flush=True
        )

        traceback.print_exc()

        print(
            "=" * 70,
            flush=True
        )

        raise


# =========================================================
# HELPER — SEND OTP EMAIL
# =========================================================

def send_otp_email(
    email,
    otp,
    purpose="Email Verification"
):

    # -----------------------------------------------------
    # EMAIL VERIFICATION
    # -----------------------------------------------------

    if purpose == "Email Verification":

        subject = (
            "DOC AI — Email Verification Code"
        )

        body = f"""
Hello,

Welcome to DOC AI.

Your email verification code is:

{otp}

This code will expire in 5 minutes.

If you did not request this code,
you can safely ignore this email.

Regards,
DOC AI Team
"""

    # -----------------------------------------------------
    # PASSWORD RESET
    # -----------------------------------------------------

    elif purpose == "Password Reset":

        subject = (
            "DOC AI — Password Reset Code"
        )

        body = f"""
Hello,

You requested to reset your DOC AI password.

Your password reset verification code is:

{otp}

This code will expire in 5 minutes.

If you did not request this password reset,
you can safely ignore this email.

Regards,
DOC AI Team
"""

    # -----------------------------------------------------
    # TEST EMAIL
    # -----------------------------------------------------

    else:

        subject = (
            "DOC AI — Test Email"
        )

        body = f"""
Hello,

This is a test email from DOC AI.

Your test verification code is:

{otp}

Regards,
DOC AI Team
"""

    return send_email(
        email,
        subject,
        body
    )


# =========================================================
# EMAIL CONFIGURATION DIAGNOSTIC
# =========================================================

@auth.route(
    "/email-config",
    methods=["GET"]
)
def email_config():

    try:

        api_key = get_resend_api_key()

        mail_from = get_mail_from()

        return {

            "status": "ok",

            "email_provider": "Resend",

            "RESEND_API_KEY_EXISTS":
                bool(api_key),

            "RESEND_API_KEY_PREFIX":
                (
                    api_key[:5] + "..."
                    if api_key
                    else "NOT SET"
                ),

            "MAIL_FROM":
                mail_from,

            "OTP_EXPIRY_MINUTES":
                get_otp_expiry_minutes()
        }

    except Exception as e:

        print(
            "EMAIL CONFIG ERROR",
            flush=True
        )

        traceback.print_exc()

        return {

            "status": "error",

            "error_type":
                type(e).__name__,

            "error":
                str(e)

        }, 500


# =========================================================
# EMAIL TEST
# =========================================================
#
# TEST:
#
# https://doc-ai-fsvt.onrender.com/email-test?to=YOUR_EMAIL
#
# =========================================================

@auth.route(
    "/email-test",
    methods=["GET"]
)
def email_test():

    recipient = request.args.get(
        "to",
        ""
    ).strip().lower()

    # -----------------------------------------------------
    # VALIDATE RECIPIENT
    # -----------------------------------------------------

    if not recipient:

        return {

            "status": "error",

            "message":
                "Missing ?to=email@example.com"

        }, 400

    # -----------------------------------------------------
    # GENERATE TEST OTP
    # -----------------------------------------------------

    test_otp = generate_otp()

    try:

        response = send_otp_email(
            recipient,
            test_otp,
            "Test"
        )

        return {

            "status":
                "success",

            "message":
                "Resend accepted the test email.",

            "recipient":
                recipient,

            "response":
                str(response)

        }

    except Exception as e:

        print(
            "=" * 70,
            flush=True
        )

        print(
            "DOC AI EMAIL TEST FAILED",
            flush=True
        )

        print(
            f"ERROR TYPE: {type(e).__name__}",
            flush=True
        )

        print(
            f"ERROR: {str(e)}",
            flush=True
        )

        traceback.print_exc()

        print(
            "=" * 70,
            flush=True
        )

        return {

            "status":
                "error",

            "error_type":
                type(e).__name__,

            "error":
                str(e),

            "message":
                "Resend test failed. Check Render logs."

        }, 500


# =========================================================
# REGISTER — STEP 1
# =========================================================

@auth.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        # -------------------------------------------------
        # VALIDATE EMAIL
        # -------------------------------------------------

        if not email:

            flash(
                "Please enter your email address.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )

        if (
            "@" not in email
            or "." not in email.split("@")[-1]
        ):

            flash(
                "Please enter a valid email address.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )

        # -------------------------------------------------
        # CHECK EXISTING USER
        # -------------------------------------------------

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "⚠ This email is already registered. Please login.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        # -------------------------------------------------
        # GENERATE OTP
        # -------------------------------------------------

        otp = generate_otp()

        # -------------------------------------------------
        # STORE REGISTRATION DATA
        # -------------------------------------------------

        session[
            "registration_email"
        ] = email

        session[
            "registration_otp"
        ] = hash_otp(
            otp
        )

        session[
            "registration_otp_expires"
        ] = (

            datetime.utcnow()

            + timedelta(
                minutes=
                get_otp_expiry_minutes()
            )

        ).isoformat()

        session[
            "registration_otp_attempts"
        ] = 0

        # -------------------------------------------------
        # SEND OTP
        # -------------------------------------------------

        try:

            send_otp_email(
                email,
                otp,
                "Email Verification"
            )

        except Exception as e:

            print(
                "=" * 70,
                flush=True
            )

            print(
                "DOC AI REGISTRATION EMAIL FAILED",
                flush=True
            )

            print(
                f"ERROR TYPE: {type(e).__name__}",
                flush=True
            )

            print(
                f"ERROR: {str(e)}",
                flush=True
            )

            traceback.print_exc()

            print(
                "=" * 70,
                flush=True
            )

            session.pop(
                "registration_otp",
                None
            )

            session.pop(
                "registration_otp_expires",
                None
            )

            session.pop(
                "registration_otp_attempts",
                None
            )

            flash(
                "❌ Unable to send verification email. Please try again.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        flash(
            "📧 Verification code sent to your email.",
            "success"
        )

        return redirect(
            url_for("auth.verify_otp")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# VERIFY REGISTRATION OTP — STEP 2
# =========================================================

@auth.route(
    "/register/verify",
    methods=["GET", "POST"]
)
def verify_otp():

    email = session.get(
        "registration_email"
    )

    otp_hash = session.get(
        "registration_otp"
    )

    expiry_string = session.get(
        "registration_otp_expires"
    )

    # -----------------------------------------------------
    # VALIDATE SESSION
    # -----------------------------------------------------

    if (
        not email
        or not otp_hash
        or not expiry_string
    ):

        flash(
            "Your registration session has expired. Please start again.",
            "danger"
        )

        return redirect(
            url_for("auth.register")
        )

    # -----------------------------------------------------
    # PARSE EXPIRY
    # -----------------------------------------------------

    try:

        expiry = datetime.fromisoformat(
            expiry_string
        )

    except ValueError:

        session.clear()

        flash(
            "Invalid verification session. Please try again.",
            "danger"
        )

        return redirect(
            url_for("auth.register")
        )

    # -----------------------------------------------------
    # CHECK EXPIRY
    # -----------------------------------------------------

    if datetime.utcnow() > expiry:

        session.pop(
            "registration_otp",
            None
        )

        session.pop(
            "registration_otp_expires",
            None
        )

        session.pop(
            "registration_otp_attempts",
            None
        )

        flash(
            "⏰ Verification code expired. Please request a new one.",
            "danger"
        )

        return redirect(
            url_for("auth.register")
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    if request.method == "POST":

        entered_otp = request.form.get(
            "otp",
            ""
        ).strip()

        # -------------------------------------------------
        # VALIDATE OTP
        # -------------------------------------------------

        if (
            not entered_otp.isdigit()
            or len(entered_otp) != 6
        ):

            flash(
                "Please enter the 6-digit verification code.",
                "danger"
            )

            return redirect(
                url_for("auth.verify_otp")
            )

        # -------------------------------------------------
        # ATTEMPT LIMIT
        # -------------------------------------------------

        attempts = session.get(
            "registration_otp_attempts",
            0
        )

        if attempts >= 5:

            session.pop(
                "registration_otp",
                None
            )

            session.pop(
                "registration_otp_expires",
                None
            )

            session.pop(
                "registration_otp_attempts",
                None
            )

            flash(
                "Too many incorrect attempts. Please request a new code.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )

        # -------------------------------------------------
        # COMPARE OTP
        # -------------------------------------------------

        entered_hash = hash_otp(
            entered_otp
        )

        if not secrets.compare_digest(
            entered_hash,
            otp_hash
        ):

            session[
                "registration_otp_attempts"
            ] = attempts + 1

            remaining = 4 - attempts

            flash(
                f"❌ Incorrect verification code. {remaining} attempts remaining.",
                "danger"
            )

            return redirect(
                url_for("auth.verify_otp")
            )

        # -------------------------------------------------
        # VERIFIED
        # -------------------------------------------------

        session[
            "registration_verified"
        ] = True

        session.pop(
            "registration_otp",
            None
        )

        session.pop(
            "registration_otp_expires",
            None
        )

        session.pop(
            "registration_otp_attempts",
            None
        )

        flash(
            "✅ Email verified successfully!",
            "success"
        )

        return redirect(
            url_for("auth.complete_registration")
        )

    return render_template(
        "verify_otp.html",
        email=email,
        expiry=expiry_string
    )


# =========================================================
# RESEND REGISTRATION OTP
# =========================================================

@auth.route(
    "/register/resend-otp",
    methods=["POST"]
)
def resend_otp():

    email = session.get(
        "registration_email"
    )

    if not email:

        flash(
            "Registration session expired.",
            "danger"
        )

        return redirect(
            url_for("auth.register")
        )

    # -----------------------------------------------------
    # CHECK EXISTING USER
    # -----------------------------------------------------

    existing_user = User.query.filter_by(
        email=email
    ).first()

    if existing_user:

        session.clear()

        flash(
            "This email is already registered.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )

    # -----------------------------------------------------
    # GENERATE NEW OTP
    # -----------------------------------------------------

    otp = generate_otp()

    session[
        "registration_otp"
    ] = hash_otp(
        otp
    )

    session[
        "registration_otp_expires"
    ] = (

        datetime.utcnow()

        + timedelta(
            minutes=
            get_otp_expiry_minutes()
        )

    ).isoformat()

    session[
        "registration_otp_attempts"
    ] = 0

    # -----------------------------------------------------
    # SEND
    # -----------------------------------------------------

    try:

        send_otp_email(
            email,
            otp,
            "Email Verification"
        )

    except Exception as e:

        print(
            "=" * 70,
            flush=True
        )

        print(
            "DOC AI RESEND OTP FAILED",
            flush=True
        )

        print(
            f"ERROR TYPE: {type(e).__name__}",
            flush=True
        )

        print(
            f"ERROR: {str(e)}",
            flush=True
        )

        traceback.print_exc()

        print(
            "=" * 70,
            flush=True
        )

        flash(
            "❌ Unable to send a new verification code.",
            "danger"
        )

        return redirect(
            url_for("auth.verify_otp")
        )

    flash(
        "📧 A new verification code has been sent.",
        "success"
    )

    return redirect(
        url_for("auth.verify_otp")
    )


# =========================================================
# REGISTER — STEP 3
# =========================================================

@auth.route(
    "/register/complete",
    methods=["GET", "POST"]
)
def complete_registration():

    email = session.get(
        "registration_email"
    )

    verified = session.get(
        "registration_verified"
    )

    if not email or not verified:

        flash(
            "Please verify your email first.",
            "danger"
        )

        return redirect(
            url_for("auth.register")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # -------------------------------------------------
        # NAME
        # -------------------------------------------------

        if not name:

            flash(
                "Please enter your name.",
                "danger"
            )

            return redirect(
                url_for("auth.complete_registration")
            )

        # -------------------------------------------------
        # PASSWORD
        # -------------------------------------------------

        if len(password) < 8:

            flash(
                "Password must contain at least 8 characters.",
                "danger"
            )

            return redirect(
                url_for("auth.complete_registration")
            )

        # -------------------------------------------------
        # CONFIRM PASSWORD
        # -------------------------------------------------

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("auth.complete_registration")
            )

        # -------------------------------------------------
        # DOUBLE CHECK USER
        # -------------------------------------------------

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            session.clear()

            flash(
                "This email is already registered.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        # -------------------------------------------------
        # CREATE USER
        # -------------------------------------------------

        hashed_password = generate_password_hash(
            password
        )

        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            role="user"
        )

        try:

            db.session.add(
                new_user
            )

            db.session.commit()

        except Exception:

            db.session.rollback()

            print(
                "DOC AI USER CREATION ERROR",
                flush=True
            )

            traceback.print_exc()

            flash(
                "❌ Unable to create your account. Please try again.",
                "danger"
            )

            return redirect(
                url_for("auth.complete_registration")
            )

        # -------------------------------------------------
        # CLEAR SESSION
        # -------------------------------------------------

        session.pop(
            "registration_email",
            None
        )

        session.pop(
            "registration_verified",
            None
        )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        flash(
            f"🎉 Welcome to DOC AI, {name}! Your account has been created successfully.",
            "success"
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template(
        "complete_registration.html",
        email=email
    )


# =========================================================
# FORGOT PASSWORD — STEP 1
# =========================================================

@auth.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        # -------------------------------------------------
        # VALIDATE EMAIL
        # -------------------------------------------------

        if not email:

            flash(
                "Please enter your email address.",
                "danger"
            )

            return redirect(
                url_for("auth.forgot_password")
            )

        if (
            "@" not in email
            or "." not in email.split("@")[-1]
        ):

            flash(
                "Please enter a valid email address.",
                "danger"
            )

            return redirect(
                url_for("auth.forgot_password")
            )

        # -------------------------------------------------
        # FIND USER
        # -------------------------------------------------

        user = User.query.filter_by(
            email=email
        ).first()

        if not user:

            flash(
                "❌ No DOC AI account exists with this email.",
                "danger"
            )

            return redirect(
                url_for("auth.forgot_password")
            )

        # -------------------------------------------------
        # GENERATE OTP
        # -------------------------------------------------

        otp = generate_otp()

        # -------------------------------------------------
        # STORE RESET DATA
        # -------------------------------------------------

        session[
            "password_reset_email"
        ] = email

        session[
            "password_reset_otp"
        ] = hash_otp(
            otp
        )

        session[
            "password_reset_otp_expires"
        ] = (

            datetime.utcnow()

            + timedelta(
                minutes=
                get_otp_expiry_minutes()
            )

        ).isoformat()

        session[
            "password_reset_otp_attempts"
        ] = 0

        session.pop(
            "password_reset_verified",
            None
        )

        # -------------------------------------------------
        # SEND RESET EMAIL
        # -------------------------------------------------

        try:

            send_otp_email(
                email,
                otp,
                "Password Reset"
            )

        except Exception as e:

            print(
                "=" * 70,
                flush=True
            )

            print(
                "DOC AI PASSWORD RESET EMAIL FAILED",
                flush=True
            )

            print(
                f"ERROR TYPE: {type(e).__name__}",
                flush=True
            )

            print(
                f"ERROR: {str(e)}",
                flush=True
            )

            traceback.print_exc()

            print(
                "=" * 70,
                flush=True
            )

            session.pop(
                "password_reset_otp",
                None
            )

            session.pop(
                "password_reset_otp_expires",
                None
            )

            session.pop(
                "password_reset_otp_attempts",
                None
            )

            flash(
                "❌ Unable to send password reset email. Please try again.",
                "danger"
            )

            return redirect(
                url_for("auth.forgot_password")
            )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        flash(
            "📧 Password reset code sent to your email.",
            "success"
        )

        return redirect(
            url_for("auth.verify_reset_otp")
        )

    return render_template(
        "forgot_password.html"
    )


# =========================================================
# FORGOT PASSWORD — STEP 2
# VERIFY RESET OTP
# =========================================================

@auth.route(
    "/verify-reset-otp",
    methods=["GET", "POST"]
)
def verify_reset_otp():

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    email = session.get(
        "password_reset_email"
    )

    otp_hash = session.get(
        "password_reset_otp"
    )

    expiry_string = session.get(
        "password_reset_otp_expires"
    )

    # -----------------------------------------------------
    # VALIDATE SESSION
    # -----------------------------------------------------

    if (
        not email
        or not otp_hash
        or not expiry_string
    ):

        flash(
            "❌ Password reset session has expired. Please start again.",
            "danger"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    # -----------------------------------------------------
    # PARSE EXPIRY
    # -----------------------------------------------------

    try:

        expiry = datetime.fromisoformat(
            expiry_string
        )

    except ValueError:

        session.pop(
            "password_reset_email",
            None
        )

        session.pop(
            "password_reset_otp",
            None
        )

        session.pop(
            "password_reset_otp_expires",
            None
        )

        flash(
            "❌ Invalid password reset session.",
            "danger"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    # -----------------------------------------------------
    # CHECK EXPIRY
    # -----------------------------------------------------

    if datetime.utcnow() > expiry:

        session.pop(
            "password_reset_otp",
            None
        )

        session.pop(
            "password_reset_otp_expires",
            None
        )

        session.pop(
            "password_reset_otp_attempts",
            None
        )

        flash(
            "⏰ Verification code has expired. Please request a new one.",
            "danger"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    if request.method == "POST":

        otp = request.form.get(
            "otp",
            ""
        ).strip()

        # -------------------------------------------------
        # VALIDATE OTP
        # -------------------------------------------------

        if (
            not otp.isdigit()
            or len(otp) != 6
        ):

            flash(
                "Please enter the 6-digit verification code.",
                "danger"
            )

            return redirect(
                url_for("auth.verify_reset_otp")
            )

        # -------------------------------------------------
        # ATTEMPT LIMIT
        # -------------------------------------------------

        attempts = session.get(
            "password_reset_otp_attempts",
            0
        )

        if attempts >= 5:

            session.pop(
                "password_reset_otp",
                None
            )

            session.pop(
                "password_reset_otp_expires",
                None
            )

            session.pop(
                "password_reset_otp_attempts",
                None
            )

            flash(
                "❌ Too many incorrect attempts. Please request a new code.",
                "danger"
            )

            return redirect(
                url_for("auth.forgot_password")
            )

        # -------------------------------------------------
        # COMPARE OTP
        # -------------------------------------------------

        entered_hash = hash_otp(
            otp
        )

        if not secrets.compare_digest(
            entered_hash,
            otp_hash
        ):

            session[
                "password_reset_otp_attempts"
            ] = attempts + 1

            remaining = 4 - attempts

            flash(
                f"❌ Incorrect verification code. {remaining} attempts remaining.",
                "danger"
            )

            return redirect(
                url_for("auth.verify_reset_otp")
            )

        # -------------------------------------------------
        # VERIFIED
        # -------------------------------------------------

        session[
            "password_reset_verified"
        ] = True

        session.pop(
            "password_reset_otp",
            None
        )

        session.pop(
            "password_reset_otp_expires",
            None
        )

        session.pop(
            "password_reset_otp_attempts",
            None
        )

        flash(
            "✅ Email verified. You can now create a new password.",
            "success"
        )

        return redirect(
            url_for("auth.reset_password")
        )

    return render_template(
        "verify_reset_otp.html",
        email=email
    )


# =========================================================
# FORGOT PASSWORD — STEP 3
# RESET PASSWORD
# =========================================================

@auth.route(
    "/reset-password",
    methods=["GET", "POST"]
)
def reset_password():

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    email = session.get(
        "password_reset_email"
    )

    verified = session.get(
        "password_reset_verified"
    )

    # -----------------------------------------------------
    # SECURITY
    # -----------------------------------------------------

    if not email or not verified:

        flash(
            "❌ Please verify your email first.",
            "danger"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # -------------------------------------------------
        # VALIDATE
        # -------------------------------------------------

        if (
            not password
            or not confirm_password
        ):

            flash(
                "Please enter and confirm your new password.",
                "danger"
            )

            return redirect(
                url_for("auth.reset_password")
            )

        if len(password) < 8:

            flash(
                "Password must contain at least 8 characters.",
                "danger"
            )

            return redirect(
                url_for("auth.reset_password")
            )

        if password != confirm_password:

            flash(
                "❌ Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("auth.reset_password")
            )

        # -------------------------------------------------
        # FIND USER
        # -------------------------------------------------

        user = User.query.filter_by(
            email=email
        ).first()

        if not user:

            session.clear()

            flash(
                "❌ Account no longer exists.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        # -------------------------------------------------
        # UPDATE PASSWORD
        # -------------------------------------------------

        user.password = generate_password_hash(
            password
        )

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            print(
                "DOC AI PASSWORD UPDATE ERROR",
                flush=True
            )

            traceback.print_exc()

            flash(
                "❌ Unable to update password. Please try again.",
                "danger"
            )

            return redirect(
                url_for("auth.reset_password")
            )

        # -------------------------------------------------
        # CLEAR RESET SESSION
        # -------------------------------------------------

        session.pop(
            "password_reset_email",
            None
        )

        session.pop(
            "password_reset_verified",
            None
        )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        flash(
            "✅ Password changed successfully. Please login.",
            "success"
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template(
        "reset_password.html"
    )


# =========================================================
# LOGIN
# =========================================================

@auth.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        # -------------------------------------------------
        # VALIDATE
        # -------------------------------------------------

        if not email or not password:

            flash(
                "Please enter your email and password.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        # -------------------------------------------------
        # FIND USER
        # -------------------------------------------------

        user = User.query.filter_by(
            email=email
        ).first()

        if not user:

            flash(
                "❌ No DOC AI account exists with this email.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        # -------------------------------------------------
        # CHECK PASSWORD
        # -------------------------------------------------

        if not check_password_hash(
            user.password,
            password
        ):

            flash(
                "❌ Incorrect password.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        # -------------------------------------------------
        # LOGIN
        # -------------------------------------------------

        login_user(
            user
        )

        flash(
            f"👋 Welcome back, {user.name}!",
            "success"
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@auth.route(
    "/logout",
    methods=["POST"]
)
@login_required
def logout():

    logout_user()

    flash(
        "You have been logged out successfully.",
        "info"
    )

    return redirect(
        url_for("auth.login")
    )


# =========================================================
# SETTINGS
# =========================================================

@auth.route(
    "/settings",
    methods=["GET", "POST"]
)
@login_required
def settings():

    if request.method == "POST":

        action = request.form.get(
            "action"
        )

        # =================================================
        # CHANGE PASSWORD
        # =================================================

        if action == "change_password":

            current_password = request.form.get(
                "current_password",
                ""
            )

            new_password = request.form.get(
                "new_password",
                ""
            )

            confirm_password = request.form.get(
                "confirm_password",
                ""
            )

            # -------------------------------------------------
            # CURRENT PASSWORD
            # -------------------------------------------------

            if not check_password_hash(
                current_user.password,
                current_password
            ):

                flash(
                    "❌ Current password is incorrect.",
                    "danger"
                )

                return redirect(
                    url_for("auth.settings")
                )

            # -------------------------------------------------
            # PASSWORD LENGTH
            # -------------------------------------------------

            if len(new_password) < 8:

                flash(
                    "⚠ New password must contain at least 8 characters.",
                    "danger"
                )

                return redirect(
                    url_for("auth.settings")
                )

            # -------------------------------------------------
            # CONFIRM PASSWORD
            # -------------------------------------------------

            if new_password != confirm_password:

                flash(
                    "⚠ New passwords do not match.",
                    "danger"
                )

                return redirect(
                    url_for("auth.settings")
                )

            # -------------------------------------------------
            # SAME PASSWORD
            # -------------------------------------------------

            if check_password_hash(
                current_user.password,
                new_password
            ):

                flash(
                    "⚠ New password must be different from your current password.",
                    "danger"
                )

                return redirect(
                    url_for("auth.settings")
                )

            # -------------------------------------------------
            # SAVE PASSWORD
            # -------------------------------------------------

            current_user.password = generate_password_hash(
                new_password
            )

            try:

                db.session.commit()

            except Exception:

                db.session.rollback()

                print(
                    "DOC AI SETTINGS PASSWORD ERROR",
                    flush=True
                )

                traceback.print_exc()

                flash(
                    "❌ Unable to change password.",
                    "danger"
                )

                return redirect(
                    url_for("auth.settings")
                )

            flash(
                "✅ Password changed successfully.",
                "success"
            )

            return redirect(
                url_for("auth.settings")
            )

        # =================================================
        # UPDATE PROFILE
        # =================================================

        if action == "update_profile":

            name = request.form.get(
                "name",
                ""
            ).strip()

            if not name:

                flash(
                    "⚠ Name cannot be empty.",
                    "danger"
                )

                return redirect(
                    url_for("auth.settings")
                )

            current_user.name = name

            try:

                db.session.commit()

            except Exception:

                db.session.rollback()

                print(
                    "DOC AI PROFILE UPDATE ERROR",
                    flush=True
                )

                traceback.print_exc()

                flash(
                    "❌ Unable to update profile.",
                    "danger"
                )

                return redirect(
                    url_for("auth.settings")
                )

            flash(
                "✅ Profile updated successfully.",
                "success"
            )

            return redirect(
                url_for("auth.settings")
            )

    return render_template(
        "settings.html",
        user=current_user
    )
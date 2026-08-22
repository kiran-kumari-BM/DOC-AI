import secrets
import hashlib
import traceback

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

from flask_mail import (
    Mail,
    Message
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
# FLASK MAIL
# =========================================================

mail = Mail()


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
# HELPER — SEND OTP EMAIL
# =========================================================

def send_otp_email(email, otp):

    msg = Message(
        subject="DOC AI — Email Verification Code",
        sender=current_app.config["MAIL_USERNAME"],
        recipients=[email]
    )

    msg.body = f"""
Hello,

Welcome to DOC AI.

Your email verification code is:

{otp}

This code will expire in 5 minutes.

If you did not request this code, you can safely ignore this email.

Regards,
DOC AI Team
"""

    mail.send(msg)


# =========================================================
# EMAIL DIAGNOSTIC — CONFIGURATION STATUS
# =========================================================
#
# IMPORTANT:
# This does NOT expose the actual email password.
#
# Open:
# https://doc-ai-fsvt.onrender.com/email-config
#
# =========================================================

@auth.route(
    "/email-config",
    methods=["GET"]
)
def email_config():

    try:

        config = current_app.config

        return {
            "status": "ok",

            "MAIL_SERVER":
                config.get("MAIL_SERVER"),

            "MAIL_PORT":
                config.get("MAIL_PORT"),

            "MAIL_USE_TLS":
                config.get("MAIL_USE_TLS"),

            "MAIL_USE_SSL":
                config.get("MAIL_USE_SSL"),

            "MAIL_USERNAME_EXISTS":
                bool(config.get("MAIL_USERNAME")),

            "MAIL_PASSWORD_EXISTS":
                bool(config.get("MAIL_PASSWORD")),

            "MAIL_DEFAULT_SENDER":
                config.get("MAIL_DEFAULT_SENDER"),

            "OTP_EXPIRY_MINUTES":
                config.get("OTP_EXPIRY_MINUTES")
        }

    except Exception as e:

        traceback.print_exc()

        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error": str(e)
        }, 500


# =========================================================
# EMAIL DIAGNOSTIC — SEND TEST EMAIL
# =========================================================
#
# IMPORTANT:
# This endpoint is for debugging only.
#
# Usage:
#
# /email-test?to=YOUR_EMAIL@gmail.com
#
# Example:
#
# https://doc-ai-fsvt.onrender.com/email-test?to=yourmail@gmail.com
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

    if not recipient:

        return {
            "status": "error",
            "message": "Missing ?to=email@example.com"
        }, 400

    try:

        # -------------------------------------------------
        # Print safe configuration information
        # -------------------------------------------------

        print(
            "=" * 70,
            flush=True
        )

        print(
            "DOC AI EMAIL TEST",
            flush=True
        )

        print(
            f"MAIL_SERVER: "
            f"{current_app.config.get('MAIL_SERVER')}",
            flush=True
        )

        print(
            f"MAIL_PORT: "
            f"{current_app.config.get('MAIL_PORT')}",
            flush=True
        )

        print(
            f"MAIL_USE_TLS: "
            f"{current_app.config.get('MAIL_USE_TLS')}",
            flush=True
        )

        print(
            f"MAIL_USE_SSL: "
            f"{current_app.config.get('MAIL_USE_SSL')}",
            flush=True
        )

        print(
            f"MAIL_USERNAME EXISTS: "
            f"{bool(current_app.config.get('MAIL_USERNAME'))}",
            flush=True
        )

        print(
            f"MAIL_PASSWORD EXISTS: "
            f"{bool(current_app.config.get('MAIL_PASSWORD'))}",
            flush=True
        )

        print(
            f"RECIPIENT: {recipient}",
            flush=True
        )

        print(
            "=" * 70,
            flush=True
        )

        # -------------------------------------------------
        # Create test email
        # -------------------------------------------------

        msg = Message(

            subject="DOC AI — Test Email",

            sender=current_app.config[
                "MAIL_USERNAME"
            ],

            recipients=[
                recipient
            ]

        )

        msg.body = """
Hello,

This is a test email from DOC AI.

If you received this message,
your SMTP configuration is working correctly.

Regards,
DOC AI Team
"""

        # -------------------------------------------------
        # Send
        # -------------------------------------------------

        mail.send(
            msg
        )

        print(
            "=" * 70,
            flush=True
        )

        print(
            "DOC AI EMAIL TEST SUCCESS",
            flush=True
        )

        print(
            "=" * 70,
            flush=True
        )

        return {
            "status": "success",
            "message": "Test email sent successfully.",
            "recipient": recipient
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
            f"ERROR: {e}",
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

        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error": str(e),
            "message": "SMTP test failed. Check the Render logs."
        }, 500


# =========================================================
# REGISTER — STEP 1
# ENTER EMAIL
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
        # Validate email
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
        # Check existing account
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
        # Generate OTP
        # -------------------------------------------------

        otp = generate_otp()

        # -------------------------------------------------
        # Store registration information
        # -------------------------------------------------

        session["registration_email"] = email

        session["registration_otp"] = hash_otp(
            otp
        )

        session["registration_otp_expires"] = (
            datetime.utcnow()
            + timedelta(
                minutes=current_app.config[
                    "OTP_EXPIRY_MINUTES"
                ]
            )
        ).isoformat()

        session["registration_otp_attempts"] = 0

        # -------------------------------------------------
        # Send OTP
        # -------------------------------------------------

        try:

            send_otp_email(
                email,
                otp
            )

        except Exception as e:

            print(
                "=" * 70,
                flush=True
            )

            print(
                "DOC AI EMAIL ERROR",
                flush=True
            )

            print(
                "PURPOSE: Registration OTP",
                flush=True
            )

            print(
                f"ERROR TYPE: {type(e).__name__}",
                flush=True
            )

            print(
                f"ERROR: {e}",
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
                "❌ Unable to send verification email. Please check your email configuration.",
                "danger"
            )

            return redirect(
                url_for("auth.register")
            )

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

    if request.method == "POST":

        entered_otp = request.form.get(
            "otp",
            ""
        ).strip()

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

    otp = generate_otp()

    session["registration_otp"] = hash_otp(
        otp
    )

    session["registration_otp_expires"] = (
        datetime.utcnow()
        + timedelta(
            minutes=current_app.config[
                "OTP_EXPIRY_MINUTES"
            ]
        )
    ).isoformat()

    session["registration_otp_attempts"] = 0

    try:

        send_otp_email(
            email,
            otp
        )

    except Exception as e:

        print(
            "=" * 70,
            flush=True
        )

        print(
            "DOC AI EMAIL ERROR",
            flush=True
        )

        print(
            "PURPOSE: Resend Registration OTP",
            flush=True
        )

        print(
            f"ERROR TYPE: {type(e).__name__}",
            flush=True
        )

        print(
            f"ERROR: {e}",
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
# NAME + PASSWORD
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

        if not name:

            flash(
                "Please enter your name.",
                "danger"
            )

            return redirect(
                url_for("auth.complete_registration")
            )

        if len(password) < 8:

            flash(
                "Password must contain at least 8 characters.",
                "danger"
            )

            return redirect(
                url_for("auth.complete_registration")
            )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("auth.complete_registration")
            )

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

        hashed_password = generate_password_hash(
            password
        )

        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            role="user"
        )

        db.session.add(
            new_user
        )

        db.session.commit()

        session.pop(
            "registration_email",
            None
        )

        session.pop(
            "registration_verified",
            None
        )

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

        otp = generate_otp()

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
                minutes=current_app.config[
                    "OTP_EXPIRY_MINUTES"
                ]
            )
        ).isoformat()

        session[
            "password_reset_otp_attempts"
        ] = 0

        session.pop(
            "password_reset_verified",
            None
        )

        try:

            msg = Message(
                subject="DOC AI — Password Reset Code",
                sender=current_app.config[
                    "MAIL_USERNAME"
                ],
                recipients=[email]
            )

            msg.body = f"""
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

            mail.send(
                msg
            )

        except Exception as e:

            print(
                "=" * 70,
                flush=True
            )

            print(
                "DOC AI EMAIL ERROR",
                flush=True
            )

            print(
                "PURPOSE: Password Reset OTP",
                flush=True
            )

            print(
                f"ERROR TYPE: {type(e).__name__}",
                flush=True
            )

            print(
                f"ERROR: {e}",
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

    if request.method == "POST":

        otp = request.form.get(
            "otp",
            ""
        ).strip()

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

    if not email or not verified:

        flash(
            "❌ Please verify your email first.",
            "danger"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

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

        user.password = generate_password_hash(
            password
        )

        db.session.commit()

        session.pop(
            "password_reset_email",
            None
        )

        session.pop(
            "password_reset_verified",
            None
        )

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

        if not email or not password:

            flash(
                "Please enter your email and password.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

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

            if len(new_password) < 8:

                flash(
                    "⚠ New password must contain at least 8 characters.",
                    "danger"
                )

                return redirect(
                    url_for("auth.settings")
                )

            if new_password != confirm_password:

                flash(
                    "⚠ New passwords do not match.",
                    "danger"
                )

                return redirect(
                    url_for("auth.settings")
                )

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

            current_user.password = generate_password_hash(
                new_password
            )

            db.session.commit()

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

            db.session.commit()

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
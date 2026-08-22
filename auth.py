import secrets
import hashlib

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
# REGISTER — STEP 1
# ENTER EMAIL
# =========================================================

@auth.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    # -----------------------------------------------------
    # Already logged in
    # -----------------------------------------------------

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

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

        # -------------------------------------------------
        # Basic email validation
        # -------------------------------------------------

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

            import traceback

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

            # -------------------------------------------------
            # Clear OTP data
            # -------------------------------------------------

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

        # -------------------------------------------------
        # OTP sent successfully
        # -------------------------------------------------

        flash(
            "📧 Verification code sent to your email.",
            "success"
        )

        return redirect(
            url_for("auth.verify_otp")
        )

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

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
    # Check registration session
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
    # Check expiry
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
    # OTP expired
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
    # POST — Verify OTP
    # -----------------------------------------------------

    if request.method == "POST":

        entered_otp = request.form.get(
            "otp",
            ""
        ).strip()

        # -------------------------------------------------
        # Validate OTP format
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
        # Attempt limit
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
        # Hash entered OTP
        # -------------------------------------------------

        entered_hash = hash_otp(
            entered_otp
        )

        # -------------------------------------------------
        # Secure comparison
        # -------------------------------------------------

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
        # OTP VERIFIED
        # -------------------------------------------------

        session[
            "registration_verified"
        ] = True

        # -------------------------------------------------
        # OTP cannot be reused
        # -------------------------------------------------

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

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Check session
    # -----------------------------------------------------

    if not email:

        flash(
            "Registration session expired.",
            "danger"
        )

        return redirect(
            url_for("auth.register")
        )

    # -----------------------------------------------------
    # Check existing account
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
    # Generate new OTP
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Send OTP
    # -----------------------------------------------------

    try:

        send_otp_email(
            email,
            otp
        )

    except Exception as e:

        import traceback

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

    # -----------------------------------------------------
    # Success
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Must verify email
    # -----------------------------------------------------

    if not email or not verified:

        flash(
            "Please verify your email first.",
            "danger"
        )

        return redirect(
            url_for("auth.register")
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

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
        # Validate name
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
        # Password length
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
        # Confirm password
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
        # Double-check account
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
        # Hash password
        # -------------------------------------------------

        hashed_password = generate_password_hash(
            password
        )

        # -------------------------------------------------
        # Create user
        # -------------------------------------------------

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

        # -------------------------------------------------
        # Clear registration session
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
        # Welcome
        # -------------------------------------------------

        flash(
            f"🎉 Welcome to DOC AI, {name}! Your account has been created successfully.",
            "success"
        )

        return redirect(
            url_for("auth.login")
        )

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    return render_template(
        "complete_registration.html",
        email=email
    )


# =========================================================
# FORGOT PASSWORD — STEP 1
# ENTER EMAIL
# =========================================================

@auth.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    # -----------------------------------------------------
    # Already logged in
    # -----------------------------------------------------

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

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
        # Find user
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
        # Generate OTP
        # -------------------------------------------------

        otp = generate_otp()

        # -------------------------------------------------
        # Store reset information
        # -------------------------------------------------

        session["password_reset_email"] = email

        session["password_reset_otp"] = hash_otp(
            otp
        )

        session["password_reset_otp_expires"] = (
            datetime.utcnow()
            + timedelta(
                minutes=current_app.config[
                    "OTP_EXPIRY_MINUTES"
                ]
            )
        ).isoformat()

        session["password_reset_otp_attempts"] = 0

        session.pop(
            "password_reset_verified",
            None
        )

        # -------------------------------------------------
        # Send reset OTP
        # -------------------------------------------------

        try:

            msg = Message(
                subject="DOC AI — Password Reset Code",
                sender=current_app.config["MAIL_USERNAME"],
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

            mail.send(msg)

        except Exception as e:

            import traceback

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

            # -------------------------------------------------
            # Clear reset OTP
            # -------------------------------------------------

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
        # Success
        # -------------------------------------------------

        flash(
            "📧 Password reset code sent to your email.",
            "success"
        )

        return redirect(
            url_for("auth.verify_reset_otp")
        )

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

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
    # Check session
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
    # Parse expiry
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
    # Check expiry
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
        # Validate OTP
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
        # Attempt limit
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
        # Compare OTP
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
        # OTP VERIFIED
        # -------------------------------------------------

        session[
            "password_reset_verified"
        ] = True

        # -------------------------------------------------
        # OTP cannot be reused
        # -------------------------------------------------

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

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    return render_template(
        "verify_reset_otp.html",
        email=email
    )


# =========================================================
# FORGOT PASSWORD — STEP 3
# CREATE NEW PASSWORD
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
    # Security check
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
        # Validate
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
        # Find user
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
        # Change password
        # -------------------------------------------------

        user.password = generate_password_hash(
            password
        )

        db.session.commit()

        # -------------------------------------------------
        # Clear reset session
        # -------------------------------------------------

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

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Already logged in
    # -----------------------------------------------------

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

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
        # Validate
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
        # Find user
        # -------------------------------------------------

        user = User.query.filter_by(
            email=email
        ).first()

        # -------------------------------------------------
        # User doesn't exist
        # -------------------------------------------------

        if not user:

            flash(
                "❌ No DOC AI account exists with this email.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        # -------------------------------------------------
        # Check password
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
        # Login
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

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

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
            # Verify current password
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
            # New password length
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
            # Confirm password
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
            # Prevent same password
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
            # Save password
            # -------------------------------------------------

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

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    return render_template(
        "settings.html",
        user=current_user
    )
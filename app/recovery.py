"""Password recovery using short-lived, password-bound signed tokens.

SMTP is optional for development, but must be configured for delivery. The reset
request endpoint always returns the same public response to prevent account
enumeration. Tokens are invalidated when the account password changes.
"""
import hashlib
import hmac
import os
import smtplib
from email.message import EmailMessage
from urllib.parse import urljoin

from flask import Blueprint, abort, current_app, flash, redirect, request, url_for
from flask_login import current_user
from flask_limiter import Limiter
from flask_wtf.csrf import generate_csrf
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from markupsafe import escape
from werkzeug.security import generate_password_hash

from .extensions import db, limiter
from .models import User
from . import PAGE

bp = Blueprint("recovery", __name__)
TOKEN_MAX_AGE_SECONDS = 30 * 60


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-recovery-v1")


def _credential_fingerprint(password_hash):
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(secret, password_hash.encode("utf-8"), hashlib.sha256).hexdigest()


def _token_for(user):
    # Store only a keyed fingerprint, never the actual password hash, in the URL.
    return _serializer().dumps({"uid": user.id, "credential_fingerprint": _credential_fingerprint(user.password_hash)})


def _user_from_token(token):
    try:
        data = _serializer().loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("uid"), int):
        return None
    user = db.session.get(User, data["uid"])
    if not user or not user.is_active or not hmac.compare_digest(data.get("credential_fingerprint", ""), _credential_fingerprint(user.password_hash)):
        return None
    return user


def _send_reset_email(user, token):
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender:
        current_app.logger.warning("Password recovery email is not configured; no email was sent.")
        return False

    base_url = os.getenv("APP_BASE_URL", "").strip()
    if not base_url:
        current_app.logger.error("APP_BASE_URL must be configured before password recovery email can be sent.")
        return False
    reset_url = urljoin(base_url.rstrip("/") + "/", url_for("recovery.reset_password", token=token).lstrip("/"))
    message = EmailMessage()
    message["Subject"] = "Reset your Liberia Business OS password"
    message["From"] = sender
    message["To"] = user.email
    message.set_content(
        "A password reset was requested for your Liberia Business OS account.\n\n"
        f"Use this link within 30 minutes: {reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    port = int(os.getenv("SMTP_PORT", "465" if os.getenv("SMTP_USE_SSL", "").lower() == "true" else "587"))
    use_ssl = os.getenv("SMTP_USE_SSL", "").lower() == "true"
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                if username:
                    server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls()
                if username:
                    server.login(username, password)
                server.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError):
        current_app.logger.exception("Password recovery email delivery failed.")
        return False
    return True


def _page(title, body):
    from flask import render_template_string
    return render_template_string(PAGE, title=title, body=body)


@bp.route("/auth/password-reset", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def request_password_reset():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()[:254]
        user = User.query.filter_by(email=email, is_active=True).first() if email else None
        if user:
            _send_reset_email(user, _token_for(user))
        flash("If an active account matches that email and email delivery is configured, a password reset link will be sent.", "success")
        return redirect(url_for("recovery.request_password_reset"))
    token_field = escape(generate_csrf())
    body = (
        '<section class="panel"><h1>Reset your password</h1>'
        '<p>Enter the email address associated with your account. If the account exists, we will send a time-limited reset link.</p>'
        '<form method="post"><input type="hidden" name="csrf_token" value="' + str(token_field) + '">'
        '<label for="email">Email address</label><input id="email" name="email" type="email" maxlength="254" autocomplete="email" required>'
        '<button class="button" type="submit">Send reset link</button></form>'
        '<p><a href="/auth/login">Return to sign in</a></p></section>'
    )
    return _page("Reset password", body)


@bp.route("/auth/password-reset/<token>", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    user = _user_from_token(token)
    if not user:
        abort(400, description="This password reset link is invalid or has expired.")
    if request.method == "POST":
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")
        if len(password) < 12 or len(password) > 128:
            flash("Choose a password between 12 and 128 characters.", "warning")
        elif password != confirmation:
            flash("The passwords do not match.", "warning")
        else:
            user.set_password(password)
            db.session.commit()
            flash("Your password has been reset. Please sign in.", "success")
            return redirect(url_for("main.login"))
    token_field = escape(generate_csrf())
    body = (
        '<section class="panel"><h1>Choose a new password</h1>'
        '<p>Use at least 12 characters. This link expires after 30 minutes and cannot be reused after a password change.</p>'
        '<form method="post"><input type="hidden" name="csrf_token" value="' + str(token_field) + '">'
        '<label for="password">New password</label><input id="password" name="password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required>'
        '<label for="confirm_password">Confirm password</label><input id="confirm_password" name="confirm_password" type="password" minlength="12" maxlength="128" autocomplete="new-password" required>'
        '<button class="button" type="submit">Update password</button></form></section>'
    )
    return _page("Choose new password", body)

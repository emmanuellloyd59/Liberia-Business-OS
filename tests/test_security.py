"""Security regression tests for browser form submissions and production settings."""
import re


def test_registration_rejects_post_without_csrf_token(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    response = client.post(
        "/auth/register",
        data={
            "full_name": "CSRF Test Owner",
            "email": "csrf-owner@example.com",
            "password": "Strong-test-password-123",
        },
    )
    assert response.status_code == 400
    assert b"csrf-owner@example.com" not in response.data


def test_registration_accepts_valid_csrf_token(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    page = client.get("/auth/register")
    assert page.status_code == 200
    match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page.data)
    assert match, "Registration form must render a CSRF token"

    response = client.post(
        "/auth/register",
        data={
            "csrf_token": match.group(1).decode(),
            "full_name": "CSRF Test Owner",
            "email": "csrf-valid@example.com",
            "password": "Strong-test-password-123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Your applications" in response.data


def test_production_enables_secure_session_cookies():
    from app import create_app

    app = create_app(
        "production",
        {
            "SECRET_KEY": "configured-test-secret",
            "SQLALCHEMY_DATABASE_URI": (
                "postgresql+psycopg://test:test@localhost/test"
            ),
            "RATELIMIT_STORAGE_URI": "redis://localhost:6379/0",
        },
    )
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

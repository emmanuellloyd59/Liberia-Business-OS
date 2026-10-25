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



def test_csrf_protected_registration_application_and_relogin_flow(client, app):
    """Exercise the complete browser flow with CSRF enabled, using test DB only."""
    app.config["WTF_CSRF_ENABLED"] = True

    registration_page = client.get("/auth/register")
    assert registration_page.status_code == 200
    token_match = re.search(
        rb'name="csrf_token"[^>]*value="([^"]+)"',
        registration_page.data,
    )
    assert token_match, "Registration page must expose a CSRF token"

    registration = client.post(
        "/auth/register",
        data={
            "csrf_token": token_match.group(1).decode(),
            "full_name": "End-to-End Test Owner",
            "email": "end-to-end-owner@example.com",
            "password": "Strong-test-password-123",
        },
        follow_redirects=True,
    )
    assert registration.status_code == 200
    assert b"Your applications" in registration.data

    application_page = client.get("/applications/new")
    assert application_page.status_code == 200
    token_match = re.search(
        rb'name="csrf_token"[^>]*value="([^"]+)"',
        application_page.data,
    )
    assert token_match, "Application page must expose a CSRF token"

    application = client.post(
        "/applications/new",
        data={
            "csrf_token": token_match.group(1).decode(),
            "business_name": "CSRF Verified Test Business",
            "business_type": "Retail",
            "county": "Montserrado",
            "description": "Test-only application for end-to-end verification",
        },
        follow_redirects=True,
    )
    assert application.status_code == 200
    assert b"CSRF Verified Test Business" in application.data

    # Sign out with the CSRF token rendered in the authenticated navigation.
    token_match = re.search(
        rb'name="csrf_token" value="([^"]+)"',
        application.data,
    )
    assert token_match, "Authenticated page must expose a logout CSRF token"
    logout = client.post(
        "/auth/logout",
        data={"csrf_token": token_match.group(1).decode()},
        follow_redirects=True,
    )
    assert logout.status_code == 200

    login_page = client.get("/auth/login")
    assert login_page.status_code == 200
    token_match = re.search(
        rb'name="csrf_token"[^>]*value="([^"]+)"',
        login_page.data,
    )
    assert token_match, "Login page must expose a CSRF token"
    login = client.post(
        "/auth/login",
        data={
            "csrf_token": token_match.group(1).decode(),
            "email": "end-to-end-owner@example.com",
            "password": "Strong-test-password-123",
        },
        follow_redirects=True,
    )
    assert login.status_code == 200
    assert b"CSRF Verified Test Business" in login.data

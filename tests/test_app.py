from app.models import User, BusinessApplication
from app.extensions import db


def register(client, email="owner@example.com", full_name="Test Owner"):
    return client.post(
        "/auth/register",
        data={"full_name": full_name, "email": email, "password": "Strong-test-password-123"},
        follow_redirects=True,
    )


def test_home_health(client):
    assert client.get("/").status_code == 200
    response = client.get("/health")
    assert response.status_code == 200 and response.json["status"] == "ok"


def test_health_reports_database_unavailable(client, app, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    def database_unavailable(*_args, **_kwargs):
        raise SQLAlchemyError("simulated database outage")

    with app.app_context():
        monkeypatch.setattr(db.engine, "connect", database_unavailable)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json["status"] == "unavailable"
    assert "simulated database outage" not in response.get_data(as_text=True)


def test_registration_and_owner_application(client, app):
    response = register(client)
    assert response.status_code == 200 and b"Your applications" in response.data
    response = client.post(
        "/applications/new",
        data={"business_name": "Monrovia Test Traders", "business_type": "Retail", "county": "Montserrado", "description": "Test application"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="owner@example.com").one()
        item = BusinessApplication.query.filter_by(owner_id=user.id).one()
        assert item.status == "pending" and item.business_name == "Monrovia Test Traders"


def test_password_hashing(app):
    with app.app_context():
        user = User(email="hash@example.com", full_name="Hash Test")
        user.set_password("another-strong-password")
        assert user.password_hash != "another-strong-password"
        assert user.check_password("another-strong-password")
        assert not user.check_password("wrong-password")


def test_non_admin_denied_admin_queue(client):
    register(client)
    assert client.get("/admin/applications").status_code == 403


def test_directory_only_shows_approved(client):
    register(client)
    client.post(
        "/applications/new",
        data={"business_name": "Pending Traders", "business_type": "Retail", "county": "Montserrado", "description": "Not public yet"},
    )
    response = client.get("/directory")
    assert b"Pending Traders" not in response.data


def test_duplicate_email_does_not_create_second_account(client, app):
    register(client)
    client.post("/auth/logout", follow_redirects=True)
    response = register(client)
    assert b"already exists" in response.data
    with app.app_context():
        assert User.query.filter_by(email="owner@example.com").count() == 1


def test_owner_cannot_see_another_owners_application(client):
    register(client, "one@example.com", "Owner One")
    client.post(
        "/applications/new",
        data={"business_name": "Private Owner One Shop", "business_type": "Retail", "county": "Montserrado", "description": "private details"},
    )
    client.post("/auth/logout", follow_redirects=True)
    register(client, "two@example.com", "Owner Two")
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Private Owner One Shop" not in response.data
    assert b"private details" not in response.data


def test_admin_can_approve_application_and_only_approved_is_public(client, app):
    register(client)
    client.post(
        "/applications/new",
        data={"business_name": "Approval Test Shop", "business_type": "Retail", "county": "Montserrado", "description": "Public after approval"},
    )
    client.post("/auth/logout", follow_redirects=True)
    with app.app_context():
        admin = User(email="admin@example.com", full_name="Test Admin", role="admin")
        admin.set_password("Admin-test-password-123")
        db.session.add(admin)
        db.session.commit()
    login = client.post(
        "/auth/login",
        data={"email": "admin@example.com", "password": "Admin-test-password-123"},
        follow_redirects=True,
    )
    assert login.status_code == 200
    listing = client.get("/admin/applications")
    assert listing.status_code == 200 and b"Approval Test Shop" in listing.data
    with app.app_context():
        item = BusinessApplication.query.filter_by(business_name="Approval Test Shop").one()
        application_id = item.id
    response = client.post(
        f"/admin/applications/{application_id}/review",
        data={"status": "approved", "review_notes": "Verified"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Approval Test Shop" in client.get("/directory").data
    # A second submission must not overwrite an already recorded decision.
    client.post(
        f"/admin/applications/{application_id}/review",
        data={"status": "rejected", "review_notes": "Attempted overwrite"},
        follow_redirects=True,
    )
    with app.app_context():
        item = db.session.get(BusinessApplication, application_id)
        assert item.status == "approved"
        assert item.review_notes == "Verified"


def test_inactive_user_cannot_log_in(client, app):
    with app.app_context():
        user = User(email="inactive@example.com", full_name="Inactive User", is_active=False)
        user.set_password("Strong-test-password-123")
        db.session.add(user)
        db.session.commit()
    response = client.post(
        "/auth/login",
        data={"email": "inactive@example.com", "password": "Strong-test-password-123"},
        follow_redirects=True,
    )
    assert b"Email or password is incorrect" in response.data
    assert client.get("/dashboard").status_code == 302


def test_user_supplied_html_is_escaped(client):
    register(client)
    client.post(
        "/applications/new",
        data={"business_name": "<script>alert(1)</script>", "business_type": "Retail", "county": "Montserrado", "description": "<img src=x onerror=alert(1)>"},
    )
    response = client.get("/dashboard")
    assert b"<script>alert(1)</script>" not in response.data
    assert b"<img src=x onerror=alert(1)>" not in response.data


def test_security_headers_are_present(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_create_admin_rejects_invalid_email(app, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "not-an-email")
    result = app.test_cli_runner().invoke(args=["create-admin"])
    assert result.exit_code == 0
    assert "valid administrator email address" in result.output
    with app.app_context():
        assert User.query.filter_by(role="admin").count() == 0


def test_create_admin_normalizes_email_and_hashes_password(app, monkeypatch):
    import getpass

    monkeypatch.setattr("builtins.input", lambda _prompt: "Admin@Example.com")
    monkeypatch.setattr(getpass, "getpass", lambda _prompt: "Very-Strong-Admin-Password-123")
    result = app.test_cli_runner().invoke(args=["create-admin"])
    assert result.exit_code == 0
    assert "Administrator created." in result.output
    with app.app_context():
        admin = User.query.filter_by(email="admin@example.com").one()
        assert admin.role == "admin"
        assert admin.check_password("Very-Strong-Admin-Password-123")


def test_production_rejects_sqlite_database():
    import pytest
    from app import create_app

    with pytest.raises(RuntimeError, match="Production requires a PostgreSQL"):
        create_app(
            "production",
            {
                "SECRET_KEY": "configured-test-secret",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
            },
        )
def test_production_rejects_in_memory_rate_limit_storage():
    import pytest
    from app import create_app

    with pytest.raises(RuntimeError, match="shared Redis-compatible RATELIMIT_STORAGE_URI"):
        create_app(
            "production",
            {
                "SECRET_KEY": "configured-test-secret",
                "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://test:test@localhost/test",
                "RATELIMIT_STORAGE_URI": "memory://",
            },
        )


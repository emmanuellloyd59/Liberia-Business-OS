from app.models import User, BusinessApplication, AuditEvent
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



def test_database_rejects_unsupported_user_role(app):
    import pytest
    from sqlalchemy.exc import IntegrityError
    with app.app_context():
        db.session.add(User(email='invalid-role@example.com', full_name='Invalid Role', password_hash='test-hash', role='superuser'))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

def test_database_rejects_unsupported_application_status(app):
    import pytest
    from sqlalchemy.exc import IntegrityError
    with app.app_context():
        user = User(email='status-owner@example.com', full_name='Status Owner')
        user.set_password('Strong-test-password-123')
        db.session.add(user)
        db.session.flush()
        db.session.add(BusinessApplication(owner_id=user.id, business_name='Invalid Status Shop', business_type='Retail', county='Montserrado', status='published'))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_admin_review_writes_atomic_audit_event(client, app):
    register(client, "audit-owner@example.com", "Audit Owner")
    client.post("/applications/new", data={"business_name": "Audit Trail Shop", "business_type": "Retail", "county": "Montserrado", "description": "Audit test"})
    client.post("/auth/logout", follow_redirects=True)
    with app.app_context():
        admin = User(email="audit-admin@example.com", full_name="Audit Admin", role="admin")
        admin.set_password("Admin-audit-password-123")
        db.session.add(admin)
        db.session.commit()
        application_id = BusinessApplication.query.filter_by(business_name="Audit Trail Shop").one().id
    client.post("/auth/login", data={"email": "audit-admin@example.com", "password": "Admin-audit-password-123"}, follow_redirects=True)
    response = client.post("/admin/applications/" + str(application_id) + "/review", data={"status": "approved", "review_notes": "Ownership verified"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        event = AuditEvent.query.filter_by(application_id=application_id).one()
        assert event.actor_user_id == User.query.filter_by(email="audit-admin@example.com").one().id
        assert event.event_type == "application_reviewed"
        assert event.previous_status == "pending"
        assert event.new_status == "approved"
        assert event.notes == "Ownership verified"


def test_directory_search_filters_and_never_exposes_pending_applications(client, app):
    with app.app_context():
        owner = User(email="directory-owner@example.com", full_name="Directory Owner")
        owner.set_password("Strong-test-password-123")
        db.session.add(owner)
        db.session.flush()
        db.session.add_all([
            BusinessApplication(
                owner_id=owner.id, business_name="Monrovia Fresh Foods",
                business_type="Agriculture", county="Montserrado",
                description="Fresh produce", status="approved",
            ),
            BusinessApplication(
                owner_id=owner.id, business_name="Bong Farm Supplies",
                business_type="Agriculture", county="Bong",
                description="Farm tools", status="approved",
            ),
            BusinessApplication(
                owner_id=owner.id, business_name="Hidden Pending Foods",
                business_type="Agriculture", county="Montserrado",
                description="Not public", status="pending",
            ),
        ])
        db.session.commit()

    response = client.get("/directory?q=Fresh&county=Montserrado&type=Agriculture")
    assert response.status_code == 200
    assert b"Monrovia Fresh Foods" in response.data
    assert b"Bong Farm Supplies" not in response.data
    assert b"Hidden Pending Foods" not in response.data

    response = client.get("/directory?county=Not-A-County")
    assert response.status_code == 200
    assert b"Monrovia Fresh Foods" in response.data
    assert b"Bong Farm Supplies" in response.data
    assert b"Hidden Pending Foods" not in response.data


def test_directory_paginates_approved_businesses(client, app):
    with app.app_context():
        owner = User(email="pagination-owner@example.com", full_name="Pagination Owner")
        owner.set_password("Strong-test-password-123")
        db.session.add(owner)
        db.session.flush()
        db.session.add_all([
            BusinessApplication(
                owner_id=owner.id,
                business_name=f"Approved Shop {number:02d}",
                business_type="Retail",
                county="Montserrado",
                description="Approved test listing",
                status="approved",
            )
            for number in range(30)
        ])
        db.session.commit()

    first_page = client.get("/directory")
    assert first_page.status_code == 200
    assert b"Page 1 of 2" in first_page.data
    assert b"Approved Shop 00" in first_page.data
    assert b"Approved Shop 24" in first_page.data
    assert b"Approved Shop 29" not in first_page.data

    second_page = client.get("/directory?page=2")
    assert second_page.status_code == 200
    assert b"Page 2 of 2" in second_page.data
    assert b"Approved Shop 29" in second_page.data



def test_owner_can_edit_only_their_own_pending_application(client, app):
    register(client, "profile-owner@example.com", "Profile Owner")
    client.post(
        "/applications/new",
        data={"business_name": "Original Shop", "business_type": "Retail",
              "county": "Montserrado", "description": "Original description"},
    )
    with app.app_context():
        item = BusinessApplication.query.filter_by(business_name="Original Shop").one()
        application_id = item.id
    response = client.post(
        f"/applications/{application_id}/edit",
        data={"business_name": "Updated Shop", "business_type": "Wholesale",
              "county": "Bong", "description": "Updated description", "submit": "Submit application"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Updated Shop" in response.data
    with app.app_context():
        item = db.session.get(BusinessApplication, application_id)
        assert item.business_name == "Updated Shop"
        assert item.business_type == "Wholesale"
        assert item.county == "Bong"
        assert item.status == "pending"


def test_owner_cannot_edit_another_owners_application(client, app):
    register(client, "profile-one@example.com", "Profile One")
    client.post(
        "/applications/new",
        data={"business_name": "Private Shop", "business_type": "Retail",
              "county": "Montserrado", "description": "Private details"},
    )
    with app.app_context():
        application_id = BusinessApplication.query.filter_by(business_name="Private Shop").one().id
    client.post("/auth/logout", follow_redirects=True)
    register(client, "profile-two@example.com", "Profile Two")
    assert client.get(f"/applications/{application_id}/edit").status_code == 404
    client.post(
        f"/applications/{application_id}/edit",
        data={"business_name": "Hijacked Shop", "business_type": "Retail",
              "county": "Nimba", "description": "tampered"},
    )
    with app.app_context():
        item = db.session.get(BusinessApplication, application_id)
        assert item.business_name == "Private Shop"
        assert item.description == "Private details"


def test_reviewed_application_cannot_be_edited(client, app):
    register(client, "reviewed-owner@example.com", "Reviewed Owner")
    client.post(
        "/applications/new",
        data={"business_name": "Reviewed Shop", "business_type": "Retail",
              "county": "Montserrado", "description": "Before review"},
    )
    with app.app_context():
        item = BusinessApplication.query.filter_by(business_name="Reviewed Shop").one()
        item.status = "approved"
        application_id = item.id
        db.session.commit()
    response = client.post(
        f"/applications/{application_id}/edit",
        data={"business_name": "Changed After Approval", "business_type": "Retail",
              "county": "Montserrado", "description": "tampered"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        item = db.session.get(BusinessApplication, application_id)
        assert item.business_name == "Reviewed Shop"
        assert item.status == "approved"


def test_public_profile_only_resolves_approved_businesses(client, app):
    register(client, "public-profile@example.com", "Public Profile Owner")
    client.post(
        "/applications/new",
        data={"business_name": "Public Profile Shop", "business_type": "Retail",
              "county": "Montserrado", "description": "Public profile text"},
    )
    with app.app_context():
        item = BusinessApplication.query.filter_by(business_name="Public Profile Shop").one()
        application_id = item.id
    assert client.get(f"/directory/{application_id}").status_code == 404
    client.post("/auth/logout", follow_redirects=True)
    with app.app_context():
        item = db.session.get(BusinessApplication, application_id)
        item.status = "approved"
        db.session.commit()
    response = client.get(f"/directory/{application_id}")
    assert response.status_code == 200
    assert b"Public Profile Shop" in response.data
    assert b"Public profile text" in response.data


def test_invalid_business_edit_does_not_change_record(client, app):
    register(client, "invalid-edit@example.com", "Invalid Edit Owner")
    client.post(
        "/applications/new",
        data={"business_name": "Valid Shop", "business_type": "Retail",
              "county": "Montserrado", "description": "Valid"},
    )
    with app.app_context():
        application_id = BusinessApplication.query.filter_by(business_name="Valid Shop").one().id
    response = client.post(
        f"/applications/{application_id}/edit",
        data={"business_name": "", "business_type": "Retail",
              "county": "Montserrado", "description": "Attempted invalid edit"},
    )
    assert response.status_code == 200
    with app.app_context():
        item = db.session.get(BusinessApplication, application_id)
        assert item.business_name == "Valid Shop"
        assert item.description == "Valid"



def test_application_submission_is_recorded_in_audit_trail(client, app):
    register(client, "submission-audit@example.com", "Submission Audit Owner")
    response = client.post(
        "/applications/new",
        data={
            "business_name": "Audit Submission Shop",
            "business_type": "Retail",
            "county": "Montserrado",
            "description": "Submitted for audit coverage",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        item = BusinessApplication.query.filter_by(
            business_name="Audit Submission Shop"
        ).one()
        event = AuditEvent.query.filter_by(
            application_id=item.id, event_type="application_submitted"
        ).one()
        actor = User.query.filter_by(email="submission-audit@example.com").one()
        assert event.actor_user_id == actor.id
        assert event.previous_status == "none"
        assert event.new_status == "pending"
        assert event.notes == "Business application submitted."


def test_owner_application_edit_is_recorded_in_audit_trail(client, app):
    register(client, "edit-audit@example.com", "Edit Audit Owner")
    client.post(
        "/applications/new",
        data={
            "business_name": "Audit Edit Shop",
            "business_type": "Retail",
            "county": "Montserrado",
            "description": "Before edit",
        },
    )
    with app.app_context():
        item = BusinessApplication.query.filter_by(
            business_name="Audit Edit Shop"
        ).one()
        application_id = item.id
    response = client.post(
        f"/applications/{application_id}/edit",
        data={
            "business_name": "Audit Edit Shop Updated",
            "business_type": "Retail",
            "county": "Bong",
            "description": "After edit",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        item = db.session.get(BusinessApplication, application_id)
        events = AuditEvent.query.filter_by(
            application_id=application_id
        ).order_by(AuditEvent.id.asc()).all()
        assert item.business_name == "Audit Edit Shop Updated"
        assert [event.event_type for event in events] == [
            "application_submitted", "application_updated"
        ]
        assert events[1].actor_user_id == item.owner_id
        assert events[1].previous_status == "pending"
        assert events[1].new_status == "pending"
        assert events[1].notes == "Owner updated business application details."

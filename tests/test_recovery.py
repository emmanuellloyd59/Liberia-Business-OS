from app.extensions import db
from app.models import User


def _create_user(app, email="recover@example.com"):
    with app.app_context():
        user = User(email=email, full_name="Recovery Test User")
        user.set_password("Original-strong-password-123")
        db.session.add(user)
        db.session.commit()
        return user.id


def test_password_reset_request_is_generic_for_known_and_unknown_accounts(client, app, monkeypatch):
    _create_user(app)
    sent = []
    monkeypatch.setattr("app.recovery._send_reset_email", lambda user, token: sent.append((user.email, token)) or True)

    known = client.post("/auth/password-reset", data={"email": "recover@example.com"}, follow_redirects=True)
    unknown = client.post("/auth/password-reset", data={"email": "missing@example.com"}, follow_redirects=True)

    assert known.status_code == unknown.status_code == 200
    assert b"If an active account matches that email" in known.data
    assert b"If an active account matches that email" in unknown.data
    assert len(sent) == 1
    assert sent[0][0] == "recover@example.com"
    assert sent[0][1] not in known.get_data(as_text=True)


def test_password_reset_changes_password_and_invalidates_token(client, app, monkeypatch):
    user_id = _create_user(app)
    sent = []
    monkeypatch.setattr("app.recovery._send_reset_email", lambda user, token: sent.append(token) or True)
    client.post("/auth/password-reset", data={"email": "recover@example.com"})
    assert len(sent) == 1
    token = sent[0]

    response = client.post(
        f"/auth/password-reset/{token}",
        data={"password": "Brand-new-strong-password-456", "confirm_password": "Brand-new-strong-password-456"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Your password has been reset" in response.data
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.check_password("Brand-new-strong-password-456")
        assert not user.check_password("Original-strong-password-123")

    # Tokens are bound to the prior password hash, so a successful reset makes
    # the same link unusable even before its 30-minute expiry.
    assert client.get(f"/auth/password-reset/{token}").status_code == 400


def test_password_reset_rejects_short_or_mismatched_passwords(client, app, monkeypatch):
    _create_user(app)
    sent = []
    monkeypatch.setattr("app.recovery._send_reset_email", lambda user, token: sent.append(token) or True)
    client.post("/auth/password-reset", data={"email": "recover@example.com"})
    token = sent[0]

    short = client.post(
        f"/auth/password-reset/{token}",
        data={"password": "short", "confirm_password": "short"},
        follow_redirects=True,
    )
    assert short.status_code == 200
    assert b"between 12 and 128 characters" in short.data

    mismatch = client.post(
        f"/auth/password-reset/{token}",
        data={"password": "Brand-new-strong-password-456", "confirm_password": "Different-strong-password-789"},
        follow_redirects=True,
    )
    assert mismatch.status_code == 200
    assert b"passwords do not match" in mismatch.data
    with app.app_context():
        user = User.query.filter_by(email="recover@example.com").one()
        assert user.check_password("Original-strong-password-123")


def test_password_reset_rejects_invalid_token(client):
    assert client.get("/auth/password-reset/not-a-valid-token").status_code == 400


def test_sign_in_page_links_to_password_recovery(client):
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert b'href="/auth/password-reset"' in response.data

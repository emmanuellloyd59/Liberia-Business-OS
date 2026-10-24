import os
import pytest
from app import create_app
from app.extensions import db
@pytest.fixture()
def app():
    database_url=os.getenv("TEST_DATABASE_URL", "sqlite://")
    app=create_app("testing",{"SECRET_KEY":"test-only-secret","SQLALCHEMY_DATABASE_URI":database_url,"WTF_CSRF_ENABLED":False})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
@pytest.fixture()
def client(app): return app.test_client()

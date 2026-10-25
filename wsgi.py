"""WSGI entry point for production deployments."""
import os

from flask_migrate import upgrade

from app import create_app

app = create_app()

# The Render service's dashboard start command is managed independently of
# render.yaml. Apply versioned, forward-only Alembic migrations here so a
# deployment cannot accept requests against an uninitialized PostgreSQL schema.
# If migration fails, fail startup rather than serving a broken application.
if os.getenv("FLASK_CONFIG", "development") == "production":
    with app.app_context():
        upgrade(directory="migrations")

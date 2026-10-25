"""WSGI entry point for production deployments."""
import os

from flask_migrate import upgrade

from app import create_app

app = create_app()

# Render's dashboard start command may differ from render.yaml. Run the
# forward-only Alembic migrations whenever the configured database is
# PostgreSQL, even if FLASK_CONFIG was not explicitly set in the dashboard.
# A failed migration must stop startup rather than serve an unusable app.
database_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
uses_postgresql = database_uri.startswith(
    ("postgresql://", "postgresql+psycopg://", "postgres://")
)
is_production = os.getenv("FLASK_CONFIG", "").strip().lower() == "production"

if is_production or uses_postgresql:
    with app.app_context():
        upgrade(directory="migrations")

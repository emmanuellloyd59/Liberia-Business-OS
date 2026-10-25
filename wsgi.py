"""WSGI entry point for production deployments."""
import logging
import os
from pathlib import Path

from sqlalchemy import inspect
from flask_migrate import upgrade

from app import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("liberia_business_os.startup")

app = create_app()
database_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
uses_postgresql = database_uri.startswith(
    ("postgresql://", "postgresql+psycopg://", "postgres://")
)
is_production = os.getenv("FLASK_CONFIG", "").strip().lower() == "production"

if is_production or uses_postgresql:
    # Resolve the migration directory absolutely; Render's working directory
    # can differ from the repository root depending on service configuration.
    migration_dir = str(Path(__file__).resolve().parent / "migrations")
    with app.app_context():
        logger.info(
            "Database startup: running Alembic migrations (dialect=%s, directory=%s)",
            app.extensions["sqlalchemy"].engine.dialect.name,
            migration_dir,
        )
        upgrade(directory=migration_dir)
        inspector = inspect(app.extensions["sqlalchemy"].engine)
        required_tables = {"user", "business_application", "audit_event", "alembic_version"}
        existing_tables = set(inspector.get_table_names())
        missing_tables = required_tables - existing_tables
        if missing_tables:
            raise RuntimeError(
                "Database migration verification failed; missing tables: "
                + ", ".join(sorted(missing_tables))
            )
        logger.info("Database startup: migrations verified; required tables are present.")

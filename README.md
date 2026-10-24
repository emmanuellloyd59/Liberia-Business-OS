# Liberia Business OS

A Flask platform foundation for business registration applications, administrator review, and discovery of approved businesses across Liberia.

## Included in this first milestone

- Flask application factory and WSGI entry point.
- PostgreSQL-ready SQLAlchemy configuration and Flask-Migrate integration.
- Account registration and login with password hashing and CSRF protection.
- Owner-scoped business applications with pending, approved, and rejected states.
- Administrator-only application review.
- Public directory that displays approved applications only.
- Responsive starter UI, automated tests, GitHub Actions, and Render Blueprint.
- Interactive CLI command to create the first administrator.

This is an early development milestone, not a claim of production certification. Email verification, password recovery, document storage, notifications, payment processing, formal registration integrations, and full audit trails remain future work.

## Local setup

Use Python 3.12 or newer. Create a virtual environment and install dependencies with pip install -r requirements.txt. Copy .env.example to .env, set a unique random SECRET_KEY and your PostgreSQL DATABASE_URL, then export those values in your shell. The app does not automatically load .env.

Initialize the schema once with:
- flask --app wsgi:app db init
- flask --app wsgi:app db migrate -m "Initial schema"
- flask --app wsgi:app db upgrade

Create an administrator using flask --app wsgi:app create-admin, then run flask --app wsgi:app run. For local smoke testing, development defaults to SQLite if DATABASE_URL is unset; production should use PostgreSQL.

## Tests

Install dependencies, then run pytest -q. Tests use an isolated in-memory SQLite database and do not connect to production data.

## Deployment

The render.yaml file describes a Render web service and managed PostgreSQL database. Review the plan and service settings before deploying. Keep secrets out of Git. Database migrations should be a controlled release step after reviewing a backup and migration plan.

## Security notes

- Passwords are stored as Werkzeug password hashes, never plaintext.
- CSRF protection is enabled for form submissions.
- Admin endpoints require an authenticated administrator.
- Dashboard queries are restricted to the signed-in owner's applications.
- Production session cookies require HTTPS.
- Never commit .env files, database dumps, uploaded identity documents, or real user data.

## Next milestones

1. Add audit events and strict application state-transition rules.
2. Add secure document upload/storage with file validation and access controls.
3. Add email verification, account recovery, and rate limiting.
4. Add categories, locations, search filters, and business profile management.
5. Add notification workflows, reports, and operational dashboards.
6. Add PostgreSQL integration tests and deployment smoke checks.

# Liberia Business OS

A Flask platform foundation for business registration applications, administrator review, and discovery of approved businesses across Liberia.

## Included in this first milestone

- Flask application factory and WSGI entry point.
- PostgreSQL-ready SQLAlchemy configuration and committed Flask-Migrate migration.
- Account registration and login with password hashing and CSRF protection.
- Owner-scoped business applications with pending, approved, and rejected states.
- Administrator-only application review.
- Public directory that displays approved applications only.
- Responsive starter UI, automated tests, GitHub Actions, and Render Blueprint.
- CI migration verification against PostgreSQL 16 plus isolated SQLite regression tests.
- Production fail-fast checks for the secret key and PostgreSQL, hardened session handling, response security headers, a request-body size limit, and rate limits on authentication endpoints.
- One-way application review decisions: approved/rejected records cannot be silently overwritten.
- Interactive CLI command to create the first administrator.

This is an early development milestone, not a claim of production certification. Email verification, password recovery, document storage, notifications, payment processing, formal registration integrations, and full audit trails remain future work. Configure `RATELIMIT_STORAGE_URI` to a shared Redis-compatible service in production; the default in-memory backend is intended for local development and is not shared between worker processes.

## Local setup

Use Python 3.12 or newer. Create a virtual environment and install dependencies with pip install -r requirements.txt. Copy .env.example to .env, set a unique random SECRET_KEY and your PostgreSQL DATABASE_URL, then export those values in your shell. The app does not automatically load .env.

Apply the committed schema migration with flask --app wsgi:app db upgrade. Create an administrator using flask --app wsgi:app create-admin, then run flask --app wsgi:app run. For local smoke testing, development defaults to SQLite if DATABASE_URL is unset; production should use PostgreSQL.

## Tests

Install dependencies, then run pytest -q. Application regression tests use an isolated in-memory SQLite database and do not connect to production data. GitHub Actions additionally starts PostgreSQL 16 and verifies the committed Alembic migration against that database on pushes and pull requests.

## Deployment

The render.yaml file describes a Render web service and managed PostgreSQL database. Review the plan and service settings before deploying. Keep secrets out of Git. Run flask --app wsgi:app db upgrade as a controlled release step against the intended database before serving requests, after reviewing a backup and migration plan. Do not automatically reset or downgrade a production database.

## Security notes

- Passwords are stored as Werkzeug password hashes, never plaintext.
- CSRF protection is enabled for form submissions.
- Admin endpoints require an authenticated administrator.
- Dashboard queries are restricted to the signed-in owner's applications.
- Production session cookies require HTTPS.
- Never commit .env files, database dumps, uploaded identity documents, or real user data.

## Next milestones

1. Add persistent audit events for account and administrator actions.
2. Add secure document upload/storage with file validation and access controls.
3. Add email verification, account recovery, and rate limiting.
4. Add categories, locations, search filters, and business profile management.
5. Add notification workflows, reports, and operational dashboards.
6. Add end-to-end PostgreSQL application tests and deployment smoke checks.

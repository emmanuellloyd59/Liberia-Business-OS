# Version 0.3 — Business Management Dashboard

## Release goal

Make the existing registration and review workflow easier to manage without replacing the Flask application or changing the production database architecture.

## Scope

- Give business owners a private overview of their application totals, status counts, and latest audit activity.
- Give administrators a searchable management queue with status and county filters, summary counts, and pagination.
- Preserve owner isolation: owners can see metrics and activity only for their own applications.
- Preserve administrator-only access to management tools and the existing review endpoint.
- Keep user-supplied values escaped and bound query parameters handled by SQLAlchemy.
- Add regression coverage for owner scoping, admin authorization, and management filters.

## Safety constraints

- No database schema changes, migrations, database reset, or production data edits.
- Do not expose pending or rejected applications in the public directory.
- Keep the existing application workflow and audit trail intact.
- Deploy only after CI passes; then verify Render deployment and the public health endpoint.

## Definition of done

- Owner overview loads for authenticated users and shows only their own counts and activity.
- Non-admin users receive HTTP 403 from the administrator overview.
- Admin search/status/county filters return the expected application records.
- Full SQLite/PostgreSQL CI and migration checks pass.
- Deployment is live and /health returns HTTP 200 with status ok.

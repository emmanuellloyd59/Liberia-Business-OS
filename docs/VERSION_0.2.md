# Version 0.2 — Business Profiles and Directory

## Release goal

Build on the existing Flask/PostgreSQL foundation without replacing the application, resetting data, or changing the production database architecture.

## Scope

1. **Business profile management**
   - Allow an authenticated owner to edit only their own business application while it is pending.
   - Keep approved/rejected decisions immutable; profile changes after approval must use a controlled re-verification workflow.
   - Validate all submitted fields server-side and escape user-supplied content on output.
2. **Directory**
   - Preserve public visibility of approved businesses only.
   - Retain county, category/type, and text search filters plus pagination.
   - Add dedicated public profile URLs only for approved records.
3. **Administration**
   - Preserve administrator-only access and one-way review decisions.
   - Record privileged profile and verification changes in an audit trail.
4. **Quality and security**
   - Add tests for owner isolation, cross-owner ID tampering, approved-record edit restrictions, CSRF, invalid values, and directory visibility.
   - Run the full pytest suite and PostgreSQL migration verification in CI.
   - Smoke-test the deployed health endpoint and key routes after a reviewed release.

## Data and deployment safety

- No production database reset, table drop, destructive migration, or data rewrite.
- Any schema change must be additive, reviewed, and backed up before release.
- Do not merge or deploy while required CI checks are failing.
- Keep secrets and real business-owner data out of source control and test fixtures.

## Definition of done

- All existing regression tests pass.
- New owner-isolation and profile workflow tests pass on isolated test data.
- PostgreSQL migration checks pass.
- Directory continues to expose approved businesses only.
- Production health and route smoke checks pass after deployment.
- Release notes document the change and any operational follow-up.

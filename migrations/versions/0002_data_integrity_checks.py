"""Constrain role and application status values at the database layer."""
from alembic import op

revision = "0002_data_integrity_checks"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

def upgrade():
    op.create_check_constraint("ck_user_role_allowed", "user", "role IN ('admin', 'business_owner')")
    op.create_check_constraint("ck_business_application_status_allowed", "business_application", "status IN ('pending', 'approved', 'rejected')")

def downgrade():
    op.drop_constraint("ck_business_application_status_allowed", "business_application", type_="check")
    op.drop_constraint("ck_user_role_allowed", "user", type_="check")

"""Create initial user and business application tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_table(
        "business_application",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("business_name", sa.String(length=180), nullable=False),
        sa.Column("business_type", sa.String(length=100), nullable=False),
        sa.Column("county", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_application_owner_id", "business_application", ["owner_id"], unique=False)
    op.create_index("ix_business_application_status", "business_application", ["status"], unique=False)

def downgrade():
    op.drop_index("ix_business_application_status", table_name="business_application")
    op.drop_index("ix_business_application_owner_id", table_name="business_application")
    op.drop_table("business_application")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")

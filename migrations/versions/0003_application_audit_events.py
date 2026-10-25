"""Record administrator decisions in a persistent audit trail."""
from alembic import op
import sqlalchemy as sa

revision = "0003_application_audit_events"
down_revision = "0002_data_integrity_checks"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("business_application.id"), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("previous_status", sa.String(length=30), nullable=False),
        sa.Column("new_status", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_event_actor_user_id", "audit_event", ["actor_user_id"])
    op.create_index("ix_audit_event_application_id", "audit_event", ["application_id"])

def downgrade():
    op.drop_index("ix_audit_event_application_id", table_name="audit_event")
    op.drop_index("ix_audit_event_actor_user_id", table_name="audit_event")
    op.drop_table("audit_event")

"""Add auditable, user-reviewed material redaction versions.

Revision ID: 0003_demo_redactions
Revises: 0002_mvp2_documents_fact_sources
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_demo_redactions"
down_revision: Union[str, None] = "0002_mvp2_documents_fact_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "redaction_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="detected"),
        sa.Column("redacted_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("analysis_mode", sa.String(length=20), nullable=False, server_default="redacted"),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_redaction_records_case_id", "redaction_records", ["case_id"], unique=False)
    op.create_index("ix_redaction_records_document_id", "redaction_records", ["document_id"], unique=False)
    op.create_index("ix_redaction_records_source_checksum", "redaction_records", ["source_checksum"], unique=False)

    op.create_table(
        "redaction_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("redaction_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("replacement", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False, server_default="full_replace"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("rule_code", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("review_status", sa.String(length=40), nullable=False, server_default="待确认"),
        sa.Column("original_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["redaction_id"], ["redaction_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_redaction_items_redaction_id", "redaction_items", ["redaction_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_redaction_items_redaction_id", table_name="redaction_items")
    op.drop_table("redaction_items")
    op.drop_index("ix_redaction_records_source_checksum", table_name="redaction_records")
    op.drop_index("ix_redaction_records_document_id", table_name="redaction_records")
    op.drop_index("ix_redaction_records_case_id", table_name="redaction_records")
    op.drop_table("redaction_records")

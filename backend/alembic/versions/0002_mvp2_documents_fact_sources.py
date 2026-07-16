"""Extend documents and add fact provenance.

Revision ID: 0002_mvp2_documents_fact_sources
Revises: 0001_baseline
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_mvp2_documents_fact_sources"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ai_outputs") as batch_op:
        batch_op.create_foreign_key(
            "fk_ai_outputs_work_unit_id_work_units",
            "work_units",
            ["work_unit_id"],
            ["id"],
        )
    with op.batch_alter_table("decision_traces") as batch_op:
        batch_op.create_foreign_key(
            "fk_decision_traces_work_unit_id_work_units",
            "work_units",
            ["work_unit_id"],
            ["id"],
        )
    with op.batch_alter_table("legal_memories") as batch_op:
        batch_op.create_foreign_key(
            "fk_legal_memories_source_work_unit_id_work_units",
            "work_units",
            ["source_work_unit_id"],
            ["id"],
        )

    op.add_column(
        "documents",
        sa.Column("original_filename", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "documents",
        sa.Column("mime_type", sa.String(length=150), nullable=False, server_default="application/octet-stream"),
    )
    op.add_column("documents", sa.Column("file_size", sa.BigInteger(), nullable=True))
    op.add_column("documents", sa.Column("checksum", sa.String(length=64), nullable=True))
    op.add_column(
        "documents",
        sa.Column("storage_provider", sa.String(length=40), nullable=False, server_default="legacy_local"),
    )
    op.add_column("documents", sa.Column("storage_key", sa.String(length=512), nullable=True))
    op.add_column(
        "documents",
        sa.Column("processing_status", sa.String(length=40), nullable=False, server_default="uploaded"),
    )
    op.add_column(
        "documents",
        sa.Column("extraction_error", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "documents",
        # SQLite cannot add a column with a non-constant CURRENT_TIMESTAMP
        # default. Existing rows are backfilled below and ORM writes provide
        # the value for new records.
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    documents = sa.table(
        "documents",
        sa.column("filename", sa.String()),
        sa.column("file_type", sa.String()),
        sa.column("raw_text", sa.Text()),
        sa.column("uploaded_at", sa.DateTime()),
        sa.column("original_filename", sa.String()),
        sa.column("mime_type", sa.String()),
        sa.column("storage_provider", sa.String()),
        sa.column("processing_status", sa.String()),
        sa.column("updated_at", sa.DateTime()),
    )
    mime_type = sa.case(
        (sa.func.lower(documents.c.file_type) == "pdf", "application/pdf"),
        (
            sa.func.lower(documents.c.file_type) == "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (sa.func.lower(documents.c.file_type) == "txt", "text/plain"),
        else_="application/octet-stream",
    )
    processing_status = sa.case(
        (sa.func.length(sa.func.trim(sa.func.coalesce(documents.c.raw_text, ""))) > 0, "ready"),
        else_="uploaded",
    )
    op.execute(
        documents.update().values(
            original_filename=documents.c.filename,
            mime_type=mime_type,
            storage_provider="legacy_local",
            processing_status=processing_status,
            updated_at=documents.c.uploaded_at,
        )
    )

    op.create_index("ix_documents_case_id", "documents", ["case_id"], unique=False)
    op.create_index("ix_documents_checksum", "documents", ["checksum"], unique=False)
    op.create_index("ix_documents_processing_status", "documents", ["processing_status"], unique=False)

    op.create_table(
        "fact_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fact_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("paragraph_index", sa.Integer(), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("relation_type", sa.String(length=40), nullable=False, server_default="support"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fact_id"], ["case_facts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fact_sources_fact_id", "fact_sources", ["fact_id"], unique=False)
    op.create_index("ix_fact_sources_document_id", "fact_sources", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fact_sources_document_id", table_name="fact_sources")
    op.drop_index("ix_fact_sources_fact_id", table_name="fact_sources")
    op.drop_table("fact_sources")

    op.drop_index("ix_documents_processing_status", table_name="documents")
    op.drop_index("ix_documents_checksum", table_name="documents")
    op.drop_index("ix_documents_case_id", table_name="documents")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("extraction_error")
        batch_op.drop_column("processing_status")
        batch_op.drop_column("storage_key")
        batch_op.drop_column("storage_provider")
        batch_op.drop_column("checksum")
        batch_op.drop_column("file_size")
        batch_op.drop_column("mime_type")
        batch_op.drop_column("original_filename")

    with op.batch_alter_table("legal_memories") as batch_op:
        batch_op.drop_constraint(
            "fk_legal_memories_source_work_unit_id_work_units",
            type_="foreignkey",
        )
    with op.batch_alter_table("decision_traces") as batch_op:
        batch_op.drop_constraint(
            "fk_decision_traces_work_unit_id_work_units",
            type_="foreignkey",
        )
    with op.batch_alter_table("ai_outputs") as batch_op:
        batch_op.drop_constraint(
            "fk_ai_outputs_work_unit_id_work_units",
            type_="foreignkey",
        )

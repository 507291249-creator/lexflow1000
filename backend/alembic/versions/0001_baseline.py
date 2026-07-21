"""MVP 1 database baseline.

Fresh databases apply this revision normally. Existing MVP 1 databases must be
backed up and stamped at this revision before applying later migrations.

Revision ID: 0001_baseline
Revises: None
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("claimant", sa.String(length=120), nullable=False),
        sa.Column("employer", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_facts", sa.Text(), nullable=False, server_default=""),
        sa.Column("claim_amount", sa.String(length=80), nullable=True),
        sa.Column("case_no", sa.String(length=80), nullable=True),
        sa.Column("case_type", sa.String(length=80), nullable=True),
        sa.Column("stage", sa.String(length=80), nullable=True),
        sa.Column("handler", sa.String(length=120), nullable=True),
        sa.Column("next_follow_up_at", sa.String(length=32), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("workflow_mode", sa.Text(), nullable=False, server_default="standard"),
        sa.Column("fact_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("issue_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cases_id"), "cases", ["id"], unique=False)

    op.create_table(
        "work_units",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_json", sa.Text(), nullable=True),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("ai_output_id", sa.Integer(), nullable=True),
        sa.Column("parent_issue_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("reviewer", sa.String(length=120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_work_units_id"), "work_units", ["id"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=40), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("parsed_json", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_id"), "documents", ["id"], unique=False)

    op.create_table(
        "evidences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("fact_to_prove", sa.Text(), nullable=False),
        sa.Column("source_document", sa.String(length=255), nullable=True),
        sa.Column("strength", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evidences_id"), "evidences", ["id"], unique=False)

    op.create_table(
        "ai_outputs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("output_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.Column("work_unit_id", sa.Integer(), nullable=True),
        sa.Column("review_status", sa.Text(), nullable=False, server_default="待复核"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("fact_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("issue_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("input_snapshot_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_outputs_id"), "ai_outputs", ["id"], unique=False)

    op.create_table(
        "decision_traces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("ai_output_id", sa.Integer(), nullable=True),
        sa.Column("ai_suggestion", sa.Text(), nullable=False),
        sa.Column("human_revision", sa.Text(), nullable=False),
        sa.Column("revision_reason", sa.Text(), nullable=False),
        sa.Column("tags", sa.String(length=255), nullable=True),
        sa.Column("work_unit_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False, server_default="人工修改"),
        sa.Column("object_type", sa.Text(), nullable=False, server_default="AI输出"),
        sa.Column("object_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["ai_output_id"], ["ai_outputs.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_decision_traces_id"), "decision_traces", ["id"], unique=False)

    op.create_table(
        "legal_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("legal_issue", sa.String(length=255), nullable=False),
        sa.Column("rule_summary", sa.Text(), nullable=False),
        sa.Column("decision_pattern", sa.Text(), nullable=False),
        sa.Column("tags", sa.String(length=255), nullable=True),
        sa.Column("source_trace_id", sa.Integer(), nullable=True),
        sa.Column("source_work_unit_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False, server_default="案件经验"),
        sa.Column("status", sa.Text(), nullable=False, server_default="已沉淀"),
        sa.Column("review_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["source_trace_id"], ["decision_traces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_legal_memories_id"), "legal_memories", ["id"], unique=False)

    op.create_table(
        "case_facts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("work_unit_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("ai_fact", sa.Text(), nullable=False),
        sa.Column("human_fact", sa.Text(), nullable=True),
        sa.Column("source_document", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=True),
        sa.Column("confidence", sa.String(length=40), nullable=True),
        sa.Column("fact_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["work_unit_id"], ["work_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_facts_id"), "case_facts", ["id"], unique=False)

    op.create_table(
        "case_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("work_unit_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("analysis_hint", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=True),
        sa.Column("importance", sa.String(length=40), nullable=True),
        sa.Column("related_facts", sa.Text(), nullable=True),
        sa.Column("related_fact_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("issue_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["work_unit_id"], ["work_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_issues_id"), "case_issues", ["id"], unique=False)

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_events_id"), "workflow_events", ["id"], unique=False)

    op.create_table(
        "case_work_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("record_type", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_work_records_id"), "case_work_records", ["id"], unique=False)

    op.create_table(
        "case_todos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("due_date", sa.String(length=32), nullable=True),
        sa.Column("priority", sa.String(length=32), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_todos_id"), "case_todos", ["id"], unique=False)

    op.create_table(
        "case_follow_ups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("follow_up_at", sa.String(length=32), nullable=True),
        sa.Column("stage", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_follow_ups_id"), "case_follow_ups", ["id"], unique=False)


def downgrade() -> None:
    for table in (
        "case_follow_ups",
        "case_todos",
        "case_work_records",
        "workflow_events",
        "case_issues",
        "case_facts",
        "legal_memories",
        "decision_traces",
        "ai_outputs",
        "evidences",
        "documents",
        "work_units",
        "cases",
    ):
        op.drop_table(table)

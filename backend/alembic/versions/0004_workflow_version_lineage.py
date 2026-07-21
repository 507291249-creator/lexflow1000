"""Add workflow version lineage columns.

Revision ID: 0004_workflow_version_lineage
Revises: 0003_demo_redactions
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_workflow_version_lineage"
down_revision: Union[str, None] = "0003_demo_redactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(
            sa.Column("material_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("material_digest", sa.String(length=64), nullable=True))
        batch_op.alter_column(
            "fact_version",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="0",
        )
        batch_op.alter_column(
            "issue_version",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="0",
        )

    with op.batch_alter_table("case_facts") as batch_op:
        batch_op.add_column(
            sa.Column("material_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.alter_column(
            "fact_version",
            existing_type=sa.Integer(),
            existing_nullable=True,
            server_default="0",
        )

    with op.batch_alter_table("case_issues") as batch_op:
        batch_op.add_column(
            sa.Column("fact_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.alter_column(
            "issue_version",
            existing_type=sa.Integer(),
            existing_nullable=True,
            server_default="0",
        )

    with op.batch_alter_table("ai_outputs") as batch_op:
        batch_op.add_column(
            sa.Column("material_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.alter_column(
            "fact_version",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="0",
        )
        batch_op.alter_column(
            "issue_version",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="0",
        )

    cases = sa.table(
        "cases",
        sa.column("id", sa.Integer()),
        sa.column("material_version", sa.Integer()),
        sa.column("fact_version", sa.Integer()),
        sa.column("issue_version", sa.Integer()),
    )
    case_facts = sa.table(
        "case_facts",
        sa.column("case_id", sa.Integer()),
        sa.column("material_version", sa.Integer()),
        sa.column("fact_version", sa.Integer()),
    )
    case_issues = sa.table(
        "case_issues",
        sa.column("case_id", sa.Integer()),
        sa.column("fact_version", sa.Integer()),
        sa.column("issue_version", sa.Integer()),
    )
    ai_outputs = sa.table(
        "ai_outputs",
        sa.column("case_id", sa.Integer()),
        sa.column("material_version", sa.Integer()),
        sa.column("fact_version", sa.Integer()),
        sa.column("issue_version", sa.Integer()),
    )

    op.execute(
        cases.update().values(
            material_version=1,
            fact_version=sa.func.coalesce(cases.c.fact_version, 0),
            issue_version=sa.func.coalesce(cases.c.issue_version, 0),
        )
    )
    op.execute(
        case_facts.update().values(
            material_version=sa.select(cases.c.material_version)
            .where(cases.c.id == case_facts.c.case_id)
            .scalar_subquery(),
            fact_version=sa.func.coalesce(case_facts.c.fact_version, 0),
        )
    )
    op.execute(
        case_issues.update().values(
            fact_version=sa.select(cases.c.fact_version)
            .where(cases.c.id == case_issues.c.case_id)
            .scalar_subquery(),
            issue_version=sa.func.coalesce(case_issues.c.issue_version, 0),
        )
    )
    op.execute(
        ai_outputs.update().values(
            material_version=sa.select(cases.c.material_version)
            .where(cases.c.id == ai_outputs.c.case_id)
            .scalar_subquery(),
            fact_version=sa.func.coalesce(ai_outputs.c.fact_version, 0),
            issue_version=sa.func.coalesce(ai_outputs.c.issue_version, 0),
        )
    )

    with op.batch_alter_table("case_facts") as batch_op:
        batch_op.alter_column(
            "fact_version",
            existing_type=sa.Integer(),
            existing_nullable=True,
            existing_server_default="0",
            nullable=False,
        )

    with op.batch_alter_table("case_issues") as batch_op:
        batch_op.alter_column(
            "issue_version",
            existing_type=sa.Integer(),
            existing_nullable=True,
            existing_server_default="0",
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_outputs") as batch_op:
        batch_op.alter_column(
            "issue_version",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="1",
        )
        batch_op.alter_column(
            "fact_version",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="1",
        )
        batch_op.drop_column("material_version")

    with op.batch_alter_table("case_issues") as batch_op:
        batch_op.alter_column(
            "issue_version",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="1",
            nullable=True,
        )
        batch_op.drop_column("fact_version")

    with op.batch_alter_table("case_facts") as batch_op:
        batch_op.alter_column(
            "fact_version",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="1",
            nullable=True,
        )
        batch_op.drop_column("material_version")

    with op.batch_alter_table("cases") as batch_op:
        batch_op.alter_column(
            "issue_version",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="1",
        )
        batch_op.alter_column(
            "fact_version",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="1",
        )
        batch_op.drop_column("material_digest")
        batch_op.drop_column("material_version")

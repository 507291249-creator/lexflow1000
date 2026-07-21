"""Add report version lineage columns.

Revision ID: 0006_report_version_lineage
Revises: 0005_analysis_version_lineage
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_report_version_lineage"
down_revision: Union[str, None] = "0005_analysis_version_lineage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(
            sa.Column("report_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("report_digest", sa.String(length=64), nullable=True))

    with op.batch_alter_table("ai_outputs") as batch_op:
        batch_op.add_column(
            sa.Column("report_version", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_outputs") as batch_op:
        batch_op.drop_column("report_version")

    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("report_digest")
        batch_op.drop_column("report_version")

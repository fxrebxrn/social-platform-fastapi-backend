"""fix user timestamp

Revision ID: f3aebbe2e666
Revises: cd537303e347
Create Date: 2026-04-06 13:02:00.506885

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f3aebbe2e666'
down_revision: Union[str, Sequence[str], None] = 'cd537303e347'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=True,
    )
    op.alter_column(
        "users",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=True,
    )
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=True,
    )

"""Add Spotify OAuth user identity fields.

Revision ID: 0002_users_oauth_identity
Revises: 0001_baseline
Create Date: 2026-07-18 10:07:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_users_oauth_identity"
down_revision: str | Sequence[str] | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add identity metadata and a unique Spotify id index."""
    op.add_column(
        "users",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=True))

    op.execute("UPDATE users SET created_at = connected_at WHERE created_at IS NULL")
    op.execute(
        "UPDATE users SET is_admin = CASE WHEN id = 1 THEN 1 ELSE 0 END "
        "WHERE is_admin IS NULL",
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.alter_column(
            "is_admin",
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        )
        batch_op.create_index("ix_users_spotify_id", ["spotify_id"], unique=True)


def downgrade() -> None:
    """Remove OAuth identity metadata."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_spotify_id")
        batch_op.drop_column("is_admin")
        batch_op.drop_column("created_at")

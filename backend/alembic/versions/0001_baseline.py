"""Create baseline schema.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-18 09:22:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import alembic.op as op
import sqlalchemy as sa

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all current application tables."""
    op.create_table(
        "tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String(length=512), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spotify_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=True),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("product", sa.String(length=32), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "taste_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "curate_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_json", sa.Text(), nullable=False),
        sa.Column("playlist_brief", sa.Text(), nullable=True),
        sa.Column("proposed_tracks_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("spotify_playlist_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "discover_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playlist_id", sa.String(length=64), nullable=True),
        sa.Column("playlist_name", sa.String(length=256), nullable=False),
        sa.Column("tracks_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cleanup_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playlist_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "playlist_scan_cache",
        sa.Column("playlist_id", sa.String(length=64), nullable=False),
        sa.Column("scan_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("playlist_id"),
    )
    op.create_table(
        "playlist_list_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("playlists_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "spotify_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_timestamps_json", sa.Text(), nullable=False),
        sa.Column("rate_limited_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "advisor_presets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "advisor_schedule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("cron", sa.String(length=64), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("notify_email", sa.Boolean(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(length=32), nullable=True),
        sa.Column("last_run_summary", sa.Text(), nullable=True),
        sa.Column("last_job_id", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "advisor_schedule_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop all baseline application tables."""
    op.drop_table("advisor_schedule_runs")
    op.drop_table("advisor_schedule")
    op.drop_table("advisor_presets")
    op.drop_table("spotify_usage")
    op.drop_table("playlist_list_cache")
    op.drop_table("playlist_scan_cache")
    op.drop_table("cleanup_runs")
    op.drop_table("discover_runs")
    op.drop_table("curate_sessions")
    op.drop_table("taste_profiles")
    op.drop_table("users")
    op.drop_table("tokens")

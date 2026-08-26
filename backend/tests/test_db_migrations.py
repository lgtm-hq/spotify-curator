"""Tests for database migrations and SQLite connection setup."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest
from alembic.command import upgrade
from assertpy import assert_that
from sqlalchemy import create_engine, inspect, text


def _database_url(database_path: Path) -> str:
    """Return a SQLite URL for a temporary database file."""
    return f"sqlite:///{database_path}"


def _load_db_module(
    monkeypatch: pytest.MonkeyPatch,
    database_path: Path,
) -> ModuleType:
    """Load app.db with a temporary database URL."""
    monkeypatch.setenv("DATABASE_URL", _database_url(database_path))

    import app.db as db_module
    from app.config import get_settings

    get_settings.cache_clear()
    return importlib.reload(db_module)


def _expected_columns(db_module: ModuleType) -> dict[str, set[str]]:
    """Return expected table columns from SQLAlchemy metadata."""
    return {
        table_name: {column.name for column in table.columns}
        for table_name, table in db_module.Base.metadata.tables.items()
    }


def test_init_db_runs_alembic_upgrade_for_fresh_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init_db creates the complete baseline schema."""
    database_path = tmp_path / "fresh.db"
    db_module = _load_db_module(
        monkeypatch=monkeypatch,
        database_path=database_path,
    )

    try:
        db_module.init_db()
        inspector_engine = create_engine(_database_url(database_path))
        try:
            inspector = inspect(inspector_engine)
            actual_tables = set(inspector.get_table_names())
            expected_columns = _expected_columns(db_module)
            actual_columns = {
                table_name: {
                    column["name"] for column in inspector.get_columns(table_name)
                }
                for table_name in expected_columns
            }

            assert_that("alembic_version" in actual_tables).is_true()
            assert_that(actual_columns).is_equal_to(expected_columns)
            assert_that(
                {
                    index["name"]: index["unique"]
                    for index in inspector.get_indexes("users")
                },
            ).contains_entry({"ix_users_spotify_id": 1})
        finally:
            inspector_engine.dispose()
    finally:
        db_module.engine.dispose()


def test_users_oauth_identity_migration_backfills_legacy_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify legacy singleton user data upgrades to an admin identity."""
    database_path = tmp_path / "legacy.db"
    db_module = _load_db_module(
        monkeypatch=monkeypatch,
        database_path=database_path,
    )
    connected_at = "2026-07-18 10:07:00"

    try:
        upgrade(db_module._alembic_config(), "0001_baseline")
        with db_module.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, spotify_id, display_name, email, image_url, product, "
                    "connected_at) "
                    "VALUES "
                    "(:id, :spotify_id, :display_name, :email, :image_url, "
                    ":product, :connected_at)",
                ),
                {
                    "id": 1,
                    "spotify_id": "legacy-spotify-id",
                    "display_name": "Legacy User",
                    "email": "legacy@example.com",
                    "image_url": "https://example.com/avatar.jpg",
                    "product": "premium",
                    "connected_at": connected_at,
                },
            )

        upgrade(db_module._alembic_config(), "head")

        with db_module.engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT spotify_id, is_admin, created_at, connected_at "
                        "FROM users WHERE id = 1",
                    ),
                )
                .mappings()
                .one()
            )

        inspector_engine = create_engine(_database_url(database_path))
        try:
            inspector = inspect(inspector_engine)
            indexes = {
                index["name"]: index["unique"]
                for index in inspector.get_indexes("users")
            }
        finally:
            inspector_engine.dispose()

        assert_that(row["spotify_id"]).is_equal_to("legacy-spotify-id")
        assert_that(row["is_admin"]).is_equal_to(1)
        assert_that(row["created_at"]).is_equal_to(row["connected_at"])
        assert_that(indexes).contains_entry({"ix_users_spotify_id": 1})
    finally:
        db_module.engine.dispose()


def test_sqlite_connections_use_wal_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify SQLite engine connections use WAL journal mode."""
    db_module = _load_db_module(
        monkeypatch=monkeypatch,
        database_path=tmp_path / "wal.db",
    )

    try:
        with db_module.engine.connect() as connection:
            journal_mode = connection.exec_driver_sql(
                "PRAGMA journal_mode"
            ).scalar_one()

        assert_that(journal_mode).is_equal_to("wal")
    finally:
        db_module.engine.dispose()

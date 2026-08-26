"""Shared pytest fixtures for backend API tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.router import get_current_user, get_db
from app.db import Base
from app.main import create_app


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Create an isolated in-memory SQLite engine."""
    database_engine = create_engine(
        url="sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=database_engine)
    try:
        yield database_engine
    finally:
        Base.metadata.drop_all(bind=database_engine)
        database_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Yield a database session bound to the test engine."""
    testing_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    db_session = testing_session_local()
    try:
        yield db_session
    finally:
        db_session.close()


@pytest.fixture
def app(session: Session) -> Iterator[FastAPI]:
    """Create a FastAPI app with test database overrides."""
    test_app = create_app()

    def override_get_db() -> Iterator[Session]:
        """Yield the current test database session."""
        yield session

    test_app.dependency_overrides[get_db] = override_get_db
    try:
        yield test_app
    finally:
        test_app.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Yield an anonymous TestClient."""
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()


@pytest.fixture
def authenticated_client(app: FastAPI) -> Iterator[TestClient]:
    """Yield a TestClient with authentication overridden."""

    def override_get_current_user() -> str:
        """Return a stable authenticated test user."""
        return "test-user"

    app.dependency_overrides[get_current_user] = override_get_current_user
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.pop(get_current_user, None)

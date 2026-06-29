from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import session as db_session
from app.db.base import Base
from app.main import app

# Import all models so their tables register on Base.metadata before create_all.
# 共享层模型 + 工具层模型（bank_journal）。
from app.models import audit, company, file, user  # noqa: F401
from app.tools.bank_journal import models  # noqa: F401  bank_journal 工具模型


def _create_test_engine():
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = _create_test_engine()
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_session.get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client_with_db() -> Generator[tuple[TestClient, Session], None, None]:
    """Yields (test_client, db_session) sharing the same in-memory SQLite engine.

    Use when a test needs to query the DB directly after an API call to assert
    on persisted rows (e.g., verifying no orphan BankTransaction rows exist).
    """
    engine = _create_test_engine()
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_session.get_db] = override_get_db
    probe_db = test_session_local()
    try:
        with TestClient(app) as test_client:
            yield test_client, probe_db
    finally:
        probe_db.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()

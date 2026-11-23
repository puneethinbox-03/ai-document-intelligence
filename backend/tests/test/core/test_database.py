
from unittest.mock import MagicMock

from sqlalchemy import text

from app.core import database


def test_database_connection():
    """Verify that PostgreSQL accepts SQLAlchemy connections."""

    with database.engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar_one()

    assert result == 1


def test_session_local_creation():
    """Verify that the session factory creates a working session."""

    session = database.SessionLocal()

    try:
        assert session.is_active is True

        result = session.execute(text("SELECT 1")).scalar_one()

        assert result == 1

    finally:
        session.close()


def test_get_db_yields_session_and_closes_it(monkeypatch):
    """Verify that the dependency yields a session and closes it."""

    mock_session = MagicMock()
    monkeypatch.setattr(
        database,
        "SessionLocal",
        lambda: mock_session,
    )

    dependency = database.get_db()

    try:
        session = next(dependency)

        assert session is mock_session
        mock_session.close.assert_not_called()

    finally:
        dependency.close()

    mock_session.close.assert_called_once()


def test_get_db_closes_session_after_exception(monkeypatch):
    """Verify cleanup when request processing raises an exception."""

    mock_session = MagicMock()
    monkeypatch.setattr(
        database,
        "SessionLocal",
        lambda: mock_session,
    )

    dependency = database.get_db()
    session = next(dependency)

    assert session is mock_session

    try:
        dependency.throw(RuntimeError("Simulated request failure"))
    except RuntimeError:
        pass

    mock_session.close.assert_called_once()

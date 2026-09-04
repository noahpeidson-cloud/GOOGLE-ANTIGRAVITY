"""
conftest.py - Pytest fixtures and environment isolation for quick_share_ai_loop tests.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
import database_sink


@pytest.fixture(autouse=True)
def reset_database_sink_state(monkeypatch):
    """
    Ensures clean state and resets the singleton connection pool before and after every test.
    """
    # Set default valid mock environment variables
    monkeypatch.setenv("PG_HOST", "127.0.0.1")
    monkeypatch.setenv("PG_PORT", "5432")
    monkeypatch.setenv("PG_USER", "postgres")
    monkeypatch.setenv("PG_PASSWORD", "test_secure_password")
    monkeypatch.setenv("PG_DB", "media_analytics")
    monkeypatch.setenv("PG_SSLMODE", "prefer")
    monkeypatch.setenv("PG_MIN_CONN", "1")
    monkeypatch.setenv("PG_MAX_CONN", "10")
    monkeypatch.setenv("PG_CONNECT_TIMEOUT", "10")

    # Reset singleton pool in database_sink
    database_sink._CONNECTION_POOL = None

    yield

    # Clean up singleton pool after test
    if database_sink._CONNECTION_POOL is not None:
        try:
            database_sink._CONNECTION_POOL.closeall()
        except Exception:
            pass
        database_sink._CONNECTION_POOL = None


@pytest.fixture
def mock_pg_pool():
    """
    Provides a pre-configured mock ThreadedConnectionPool, Connection, and Cursor.
    """
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()

    mock_pool.closed = False
    mock_pool.getconn.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.cursor.return_value.__exit__.return_value = None

    return {
        "pool": mock_pool,
        "conn": mock_conn,
        "cur": mock_cur,
    }

"""
Pytest configuration and test fixtures for local_daemon.
Strict adherence to Rule R16 (Absolute imports only).
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure local_daemon root is on sys.path for absolute imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DAEMON_ROOT = os.path.dirname(CURRENT_DIR)
if DAEMON_ROOT not in sys.path:
    sys.path.insert(0, DAEMON_ROOT)

from main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Synchronous test client for FastAPI endpoints."""
    with TestClient(app) as test_client:
        yield test_client

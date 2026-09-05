"""
Global pytest configuration and flat fixtures adhering to R2 Zero-Discretion Mandate:
- Zero shared state across tests.
- No nested fixtures.
- Explicit path resolution for R16 absolute imports.
"""

import os
import sys
from pathlib import Path
import pytest

# Ensure project root is in sys.path for absolute imports (R16)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Isolate temp root to project directory to avoid Windows AppData/Temp symlink PermissionErrors
LOCAL_TEMP = PROJECT_ROOT / ".pytest_temp"
LOCAL_TEMP.mkdir(parents=True, exist_ok=True)
os.environ["PYTEST_DEBUG_TEMPROOT"] = str(LOCAL_TEMP)

TARGET_NOTEBOOK_ID = "4b52cc67-9f81-4e85-a024-5f06756991ab"
TARGET_NOTEBOOK_TITLE = "Dual-Loop Control and Agentic Orchestration in Cognitive Architectures"
EXPECTED_SOURCE_COUNT = 61
EXPECTED_NOTE_COUNT = 1
EXPECTED_NOTE_TITLE = "The Multi-Model Orchestration and AI Handoff Framework"


@pytest.fixture
def target_notebook_id() -> str:
    """Returns the immutable target notebook UUID."""
    return TARGET_NOTEBOOK_ID


@pytest.fixture
def sample_valid_source_dict() -> dict:
    """Returns an isolated dictionary representing a single valid source."""
    return {
        "id": "7b7c692f-9bac-4a94-be71-b76010be5686",
        "title": "11 Top Open-Source LLMs for 2026 and Their Uses - DataCamp",
        "source_type": "unknown",
        "url": "https://www.datacamp.com/blog/top-open-source-llms",
        "char_count": 51151,
        "content": "Comprehensive guide to top open source LLMs...",
        "status": "success",
        "error": None,
    }


@pytest.fixture
def sample_valid_note_dict() -> dict:
    """Returns an isolated dictionary representing a single valid note."""
    return {
        "id": "eff2cf19-844e-4af7-aad8-601d7d0fbf13",
        "title": EXPECTED_NOTE_TITLE,
        "content": "Based on your research library, I have formulated a highly optimized...",
        "preview": "Based on your research library...",
    }

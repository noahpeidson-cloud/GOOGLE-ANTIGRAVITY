"""
Universal Workspace Context & Path Resolver for Google Antigravity.
Dynamically resolves paths relative to the active workspace root without hardcoding drive letters.
"""

import os
from pathlib import Path
from typing import Optional
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda dotenv_path=None: False

def get_workspace_root() -> Path:
    """
    Returns the resolved Path of the active Antigravity workspace root.
    Prioritizes WORKSPACE_ROOT env var, then searches upwards from this file.
    """
    env_root = os.getenv("WORKSPACE_ROOT")
    if env_root and os.path.exists(env_root):
        return Path(env_root).resolve()

    current = Path(__file__).resolve().parent
    candidate = None
    for parent in [current] + list(current.parents):
        if (parent / ".agents").exists() or (parent / "GEMINI.md").exists() or (parent / ".git").exists():
            candidate = parent
    if candidate is not None:
        return candidate

    return Path.cwd().resolve()


# Initialize environment from workspace root .env if present
_WORKSPACE_ROOT = get_workspace_root()
_ENV_PATH = _WORKSPACE_ROOT / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH)
else:
    load_dotenv()


def resolve_path(relative_or_absolute_path: str) -> Path:
    """
    Safely resolves a path relative to the workspace root if it is not already an existing absolute path.
    """
    p = Path(relative_or_absolute_path)
    if p.is_absolute() and p.exists():
        return p.resolve()
    
    clean_path = relative_or_absolute_path.lstrip("\\/")
    return (_WORKSPACE_ROOT / clean_path).resolve()


def get_storage_path(subsystem: str, filename: str) -> Path:
    """
    Returns a resolved path in the canonical storage directory (e.g., storage/telemetry/agent_telemetry.db).
    Ensures parent directories are created automatically.
    """
    target_dir = _WORKSPACE_ROOT / "storage" / subsystem
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / filename


# Standard canonical paths
WORKSPACE_ROOT: Path = _WORKSPACE_ROOT
STORAGE_DIR: Path = _WORKSPACE_ROOT / "storage"
AGENTS_DIR: Path = _WORKSPACE_ROOT / ".agents"
APPS_DIR: Path = _WORKSPACE_ROOT / "apps"
CONTENT_CREATION_DIR: Path = _WORKSPACE_ROOT / "content_creation"
SPORTS_CARDS_DIR: Path = _WORKSPACE_ROOT / "sports_cards"
INFRASTRUCTURE_DIR: Path = _WORKSPACE_ROOT / "infrastructure"

# Default isolated database paths
DEFAULT_TELEMETRY_DB: str = str(get_storage_path("telemetry", "agent_telemetry.db"))
DEFAULT_QUEUE_DB: str = str(get_storage_path("queue", "event_queue.db"))
DEFAULT_MEDIA_CATALOG_DB: str = str(get_storage_path("media", "media_catalog.db"))
DEFAULT_PORTFOLIO_DB: str = str(get_storage_path("cards", "portfolio.db"))

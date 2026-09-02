"""
Pytest configuration for tests/ directory.
Strict adherence to Rule R16 (Absolute imports).
"""

import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
DAEMON_DIR = REPO_ROOT / "local_daemon"

for p in [str(REPO_ROOT), str(CURRENT_DIR), str(DAEMON_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

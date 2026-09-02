"""
browser_master.subagents
========================
Specialized subagent configurations for browser automation.
"""

from browser_master.subagents.browser_worker import (
    create_browser_worker_config,
    BROWSER_WORKER_INSTRUCTIONS,
    WORKER_DEFAULT_TOOLS,
)
from browser_master.subagents.extractor import (
    create_extractor_config,
    EXTRACTOR_INSTRUCTIONS,
    EXTRACTOR_DEFAULT_TOOLS,
)

__all__ = [
    "create_browser_worker_config",
    "BROWSER_WORKER_INSTRUCTIONS",
    "WORKER_DEFAULT_TOOLS",
    "create_extractor_config",
    "EXTRACTOR_INSTRUCTIONS",
    "EXTRACTOR_DEFAULT_TOOLS",
]

"""Configuration thresholds, paths, ports, and token patterns."""

from typing import List

# Default thresholds
CONTEXT_ROT_THRESHOLD_HOURS: float = 24.0
PROMPT_FATIGUE_MAX_LINES: int = 100
MONITORED_PORTS: List[int] = [3000, 8000, 8501]
WATCHDOG_MAX_ITERATIONS: int = 3
DEFAULT_K_CLUSTERS: int = 3
BUSY_TIMEOUT_MS: int = 5000
DEFAULT_DB_PATH: str = "health_telemetry.db"

# Whitelisted filenames that should not be flagged as context rot or dead artifacts
WHITELISTED_FILENAMES: List[str] = [
    "PROJECT.md",
    "GEMINI.md",
    "README.md",
    "BRIEFING.md",
    "ORIGINAL_REQUEST.md",
]

# Blacklisted placeholder token regex patterns
BLACKLIST_TOKEN_PATTERNS: List[str] = [
    r"your_token_here",
    r"YOUR_API_KEY_HERE",
    r"your_api_key_here",
    r"YOUR_TOKEN_HERE",
    r"your-api-key-here",
    r"your-secret-key-here",
    r"placeholder_key",
    r"sk-[a-zA-Z0-9]{20,}",
    r"INSERT_API_KEY_HERE",
    r"CHANGE_ME",
]

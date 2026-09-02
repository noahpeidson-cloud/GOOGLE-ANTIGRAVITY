"""
Configuration constants, thresholds, whitelists, and seed definitions
for Antigravity Daily Health Scanner & ML Optimization Daemon.
"""

import os
from pathlib import Path
import re
from typing import Any, Dict, List, Set, Union

try:
    from models import DetectorType, Severity
except ImportError:
    from proposed_models import DetectorType, Severity


# ==============================================================================
# 1. Scanner & Threshold Constants
# ==============================================================================

# Context rot threshold: markdown planning artifacts older than 24 hours
CONTEXT_ROT_HOURS: float = 24.0

# Prompt fatigue threshold: GEMINI.md line count maximum allowed before bloat alert
PROMPT_FATIGUE_MAX_LINES: int = 100

# Estimated character ceiling for static system manifests (~2000 tokens)
PROMPT_FATIGUE_MAX_CHARACTERS: int = 8000

# Monitored network ports prone to unmonitored daemon collisions (WinError 10048)
MONITORED_PORTS: List[int] = [3000, 8000, 8501]

# Port probe connection timeout in seconds
PORT_PROBE_TIMEOUT: float = 0.5
PORT_PROBE_HOST: str = "127.0.0.1"

# Maximum subagent iterations to prevent watchdog runaway
MAX_SUBAGENT_ITERATIONS: int = 3

# ML Clustering & Optimization Parameters
DEFAULT_K_MEANS_CLUSTERS: int = 3
DEFAULT_SEMANTIC_ENTROPY_THRESHOLD: float = 0.5
K_MEANS_MAX_ITERATIONS: int = 100
K_MEANS_TOLERANCE: float = 1e-4

# Default SQLite database path for telemetry store
DEFAULT_DB_PATH: str = "health_telemetry.db"

# Default report output directory
DEFAULT_REPORTS_DIR: str = "reports"


# ==============================================================================
# 2. Whitelist & Protected Files (DLP Safe Guard)
# ==============================================================================

# Essential project and agent communication files that MUST NEVER be flagged as context rot
PROTECTED_WHITELIST_FILENAMES: Set[str] = {
    "PROJECT.md",
    "GEMINI.md",
    "README.md",
    "BRIEFING.md",
    "BRIEFING_ARCHIVE.md",
    "DISPATCH.md",
    "progress.md",
    "ORIGINAL_REQUEST.md",
    "TEST_READY.md",
    "TEST_INFRA.md",
    "task.md",
}

# Directories completely excluded from scanning
EXCLUDED_SCAN_DIRS: Set[str] = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
}

# Planning keywords indicating temporary or proposal artifacts prone to context rot
CONTEXT_ROT_TARGET_KEYWORDS: List[str] = [
    "proposal",
    "ideas",
    "blueprint",
    "plan",
    "notes",
    "draft",
    "scratch",
    "temp",
    "todo",
]


# ==============================================================================
# 3. Secret Zero Blacklist Tokens & Regex Patterns
# ==============================================================================

# Explicit placeholder tokens that must trigger a CRITICAL Secret Zero anomaly
SECRET_PLACEHOLDER_TOKENS: List[str] = [
    "your_token_here",
    "your_api_key_here",
    "your_secret_here",
    "your_key_here",
    "YOUR_API_KEY",
    "YOUR_SECRET",
    "YOUR_TOKEN",
    "INSERT_KEY_HERE",
    "INSERT_TOKEN_HERE",
    "TODO_KEY",
    "changeme",
    "placeholder",
]

# Target file patterns scanned for Secret Zero
SECRET_SCAN_EXTENSIONS: Set[str] = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".pickle",
    ".json",
    ".yaml",
    ".yml",
}

# Secret Zero Regex Patterns
SECRET_REGEX_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "placeholder_assignment",
        "pattern": re.compile(
            r'(?i)(?:api[_-]?key|secret|token|password|auth|jwt|credential)\s*[:=]\s*["\']?(your[_-]?(?:token|api[_-]?key|secret|key)[_-]?here|insert[_-]?key|changeme|placeholder|xxx+)["\']?'
        ),
        "severity": Severity.CRITICAL,
        "description": "Unresolved placeholder secret token detected in configuration assignment.",
    },
    {
        "name": "generic_placeholder",
        "pattern": re.compile(
            r'(?i)\b(your_token_here|your_api_key_here|your_secret_here|INSERT_KEY_HERE)\b'
        ),
        "severity": Severity.CRITICAL,
        "description": "Standard placeholder string found in configuration file.",
    },
    {
        "name": "openai_api_key",
        "pattern": re.compile(r'\bsk-[a-zA-Z0-9]{20,}\b'),
        "severity": Severity.CRITICAL,
        "description": "Exposed OpenAI API key format detected.",
    },
    {
        "name": "google_api_key",
        "pattern": re.compile(r'\bAIza[0-9A-Za-z-_]{35}\b'),
        "severity": Severity.CRITICAL,
        "description": "Exposed Google API key format detected.",
    },
    {
        "name": "github_pat",
        "pattern": re.compile(r'\bghp_[a-zA-Z0-9]{36}\b'),
        "severity": Severity.HIGH,
        "description": "Exposed GitHub Personal Access Token detected.",
    },
]


# ==============================================================================
# 4. Workspace Track Boundaries & Ecosystem Pollution
# ==============================================================================

WORKSPACE_TRACKS: Dict[str, str] = {
    "TRACK_1": "sports_cards",
    "TRACK_2": "content_creation",
    "TRACK_3": "apps",
    "TRACK_4": "travel_and_life",
}

DISABLED_PLUGIN_SUFFIX: str = ".disabled"


# ==============================================================================
# 5. August 23/24 Historical Failure Lifelines Seed Data
# ==============================================================================

HISTORICAL_LIFELINES_SEED_DATA: List[Dict[str, Any]] = [
    {
        "lifeline_id": "HL-001-GHOST-DAEMONS",
        "detector_type": DetectorType.GHOST_DAEMONS,
        "target_path": "ports:3000,8000,8501",
        "severity": Severity.CRITICAL,
        "description": "Ghost Daemons: Unmonitored Next.js/Uvicorn tasks causing socket collisions (WinError 10048).",
        "failure_pattern": "WinError 10048: Only one usage of each socket address is normally permitted",
        "root_cause": "Orphaned background dev servers holding local TCP sockets open without watchdog management.",
        "remediation_strategy": "List active tasks via manage_task, identify unmanaged PID/port holders, and request HITL task termination.",
        "raw_details": {
            "monitored_ports": MONITORED_PORTS,
            "error_code": "WinError 10048",
            "session_date": "2026-08-23/24",
            "impact": "Blocked subagents from binding local development servers",
        },
    },
    {
        "lifeline_id": "HL-002-CONTEXT-ROT",
        "detector_type": DetectorType.CONTEXT_ROT,
        "target_path": "planning_artifacts/*.md",
        "severity": Severity.HIGH,
        "description": "Context Rot: Planning artifacts older than 24 hours diluting the context window.",
        "failure_pattern": "Stale proposal/blueprint/draft markdown files remaining in active working context > 24 hours.",
        "root_cause": "Ephemeral planning files left in workspace root instead of moving to .archive (L2 cache).",
        "remediation_strategy": "Propose non-destructive archiving of stale planning markdown files to .archive/ folder.",
        "raw_details": {
            "threshold_hours": CONTEXT_ROT_HOURS,
            "session_date": "2026-08-23/24",
            "impact": "Context window dilution causing LLM attention degradation and token cost inflation",
        },
    },
    {
        "lifeline_id": "HL-003-ECOSYSTEM-POLLUTION",
        "detector_type": DetectorType.ECOSYSTEM_POLLUTION,
        "target_path": ".gemini/config/plugins/*.disabled",
        "severity": Severity.MEDIUM,
        "description": "Ecosystem Pollution: Unused .disabled plugin directories confusing the crawler.",
        "failure_pattern": "Dormant .disabled directories scanned by subagents causing crawler confusion and context waste.",
        "root_cause": "Disabled plugin directories retaining full tool schemas and skill descriptions without active registration.",
        "remediation_strategy": "Identify and report .disabled plugin folders for user-confirmed archival or exclusion.",
        "raw_details": {
            "target_suffix": DISABLED_PLUGIN_SUFFIX,
            "session_date": "2026-08-23/24",
            "impact": "Crawler tool-schema confusion and hallucinated tool invocations",
        },
    },
    {
        "lifeline_id": "HL-004-SECRET-ZERO",
        "detector_type": DetectorType.SECRET_ZERO,
        "target_path": ".env",
        "severity": Severity.CRITICAL,
        "description": "Secret Zero: Unresolved placeholder tokens (your_token_here) in .env files.",
        "failure_pattern": "Placeholder credentials (your_token_here, YOUR_API_KEY) passed to client SDKs causing runtime auth failures.",
        "root_cause": "Template .env files copied into workspace without real credentials populated.",
        "remediation_strategy": "Flag placeholder tokens, halt automated execution, and prompt user for credential provisioning.",
        "raw_details": {
            "placeholder_token": "your_token_here",
            "session_date": "2026-08-23/24",
            "impact": "Runtime 401 Unauthorized API rejections and execution lockups",
        },
    },
    {
        "lifeline_id": "HL-005-PROMPT-FATIGUE",
        "detector_type": DetectorType.PROMPT_FATIGUE,
        "target_path": "GEMINI.md",
        "severity": Severity.HIGH,
        "description": "Prompt Fatigue: Hardcoded procedural rules bloating the GEMINI.md manifest (>100 lines).",
        "failure_pattern": "GEMINI.md manifest exceeding 100 lines causing instruction dilution and context bloat.",
        "root_cause": "Procedural domain workflows embedded directly in static steering prompt instead of dynamic skill files.",
        "remediation_strategy": "Refactor procedural rules into modular .agents/skills/ and keep GEMINI.md under 100 lines.",
        "raw_details": {
            "max_lines_threshold": PROMPT_FATIGUE_MAX_LINES,
            "session_date": "2026-08-23/24",
            "impact": "Rule drift and instruction forgetting across multi-agent handoffs",
        },
    },
]


# ==============================================================================
# 6. Helper Utilities
# ==============================================================================

def is_path_whitelisted(file_path: Union[str, Path]) -> bool:
    """
    Check if a given file path or file name matches protected whitelist rules.
    Protected files must never be flagged as context rot.
    """
    p = Path(file_path)
    filename = p.name
    
    # Exact filename match
    if filename in PROTECTED_WHITELIST_FILENAMES:
        return True
        
    # Pattern matches (e.g. BRIEFING_*.md or DISPATCH.md)
    if filename.startswith("BRIEFING") and filename.endswith(".md"):
        return True
        
    return False


def is_directory_excluded(dir_path: Union[str, Path]) -> bool:
    """Check if directory name should be skipped during file tree walks."""
    p = Path(dir_path)
    for part in p.parts:
        if part in EXCLUDED_SCAN_DIRS:
            return True
    return False

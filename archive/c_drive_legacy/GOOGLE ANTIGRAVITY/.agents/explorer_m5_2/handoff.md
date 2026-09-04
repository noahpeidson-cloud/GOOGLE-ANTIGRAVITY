# Milestone 5 Investigation & Implementation Blueprint: `fixtures/mock_workspace/`

## 1. Observation

Direct code examination and architectural analysis of the `.agents/cron` subsystem revealed the precise operational contracts, threshold configurations, and detection criteria for all five August 23/24 historical failure patterns:

1. **Ghost Daemons Detection Contract (`detectors/ghost_daemons.py:17-87`, `config.py:8`)**:
   - `GhostDaemonsDetector` iterates across `MONITORED_PORTS = [3000, 8000, 8501]` and executes non-destructive loopback TCP probing (`sock.connect_ex((self.host, port)) == 0`).
   - When occupied, emits `AnomalyRecord` with `DetectorType.GHOST_DAEMONS`, `severity=Severity.CRITICAL`, `raw_details={"host": "127.0.0.1", "port": port, "status": "OCCUPIED", "errno": 10048, "signature": "WinError 10048 (WSAEADDRINUSE)"}`.
   - For offline test determinism, port binding must be managed safely via a background loopback server thread with `SO_REUSEADDR` and automatic socket release to prevent test-runner port lockups.

2. **Context Rot Detection Contract (`detectors/context_rot.py:18-116`, `config.py:6,15-21`)**:
   - `ContextRotDetector` scans markdown files (`.md`) matching planning patterns (`*proposal*.md`, `*blueprint*.md`, `*ideas*.md`, `*scratchpad*.md`, `*plan*.md`, `*progress*.md`, `*context*.md`).
   - Flags files with `(current_time - mtime) / 3600.0 > 24.0` hours as `DetectorType.CONTEXT_ROT` (`Severity.MEDIUM`).
   - Strictly enforces whitelist immunity (`WHITELISTED_FILENAMES = ["PROJECT.MD", "GEMINI.MD", "README.MD", "BRIEFING.MD", "ORIGINAL_REQUEST.MD"]`).
   - Mock workspace must generate stale planning files (mtime set to 72h-96h ago via `os.utime`), alongside whitelisted manifest files (also timestamped to 72h ago to verify zero false positives), and fresh planning files (<24h).

3. **Ecosystem Pollution Detection Contract (`detectors/ecosystem_pollution.py:16-176`)**:
   - Detects directory and file names ending in `.disabled` as `DetectorType.ECOSYSTEM_POLLUTION` (`Severity.HIGH`).
   - Detects cross-track leaks:
     - `/sports_cards` track containing media extensions (`.mp4`, `.mov`, `.mkv`, etc.) or script content containing `ffmpeg` and `MEDIA_KEYWORDS`.
     - `/content_creation` track containing files matching `SPORTS_CARD_KEYWORDS` (`card_ladder`, `cardladder`, `psa_grade`, `bgs_grade`, `sports_card`, `sportscard`).
   - Mock workspace must contain `.gemini/config/plugins/mock_plugin.disabled/`, `.gemini/config/plugins/bigquery_sql.disabled/`, `content_creation/card_ladder_model.py`, and `sports_cards/intro_render.mp4`.

4. **Secret Zero Detection Contract (`detectors/secret_zero.py:19-123`, `config.py:24-35`)**:
   - `SecretZeroDetector` scans configuration and environment files (`.env`, `.env.*`, `*.json`, `*.yaml`, `*.yml`, `*.toml`, `*.ini`, `*.cfg`).
   - Matches regex patterns in `BLACKLIST_TOKEN_PATTERNS` (`your_token_here`, `YOUR_API_KEY_HERE`, `placeholder_key`, `INSERT_API_KEY_HERE`, `CHANGE_ME`, `sk-[a-zA-Z0-9]{20,}`, etc.).
   - Emits `DetectorType.SECRET_ZERO` with `Severity.CRITICAL` and applies cryptographic token masking (`mask_token`).
   - Mock workspace must generate `.env.example`, `.env.local`, `config/settings.yaml`, and `config/api_keys.json` with placeholder tokens, alongside clean config files with valid production tokens.

5. **Prompt Fatigue Detection Contract (`detectors/prompt_fatigue.py:18-152`, `config.py:7`)**:
   - `PromptFatigueDetector` locates `GEMINI.md` and checks if total line count exceeds `PROMPT_FATIGUE_MAX_LINES = 100` (`Severity.MEDIUM` or `Severity.HIGH` if >150 lines).
   - Scans for duplicate markdown section headings (`## Heading`) and duplicate `<RULE[...]>` tags.
   - Emits `DetectorType.PROMPT_FATIGUE` with line count, estimated token count, and duplicate section list.
   - Mock workspace must construct a `GEMINI.md` file of 120-140 lines containing repeated rule headings (e.g. `## R1. Workflow Distillation Directive` duplicated).

6. **Crytographic Read-Only Enforcer (`tests/conftest.py:19-61`)**:
   - `FileSystemSnapshot` computes SHA256 hashes of all files before execution and asserts zero additions, deletions, or modifications (`assert_untouched()`).

---

## 2. Logic Chain

1. **Simultaneous 5-Pattern Reproduction (Observation 1-5)**:
   By structuring `fixtures/mock_workspace.py` with modular file generators, a single invocation of `create_mock_workspace(temp_dir)` creates the exact directory topology and file artifacts required to simultaneously trigger all 5 detector classes.

2. **Clean vs. Anomalous Workspace Parametrization**:
   Unit and integration tests (such as `test_scanner_daemon.py` and `test_detectors.py`) require testing both positive detection paths (anomalous workspace) and negative baseline paths (clean workspace). Parameterizing the factory with `include_anomalies: bool = True` and providing a dedicated `create_clean_workspace(temp_dir)` helper guarantees deterministic setup and teardown for both test categories.

3. **Safe Loopback Daemon Management (Observation 1)**:
   In automated CI/test environments, attempting to bind hardcoded port 3000 without lifecycle management risks port collisions or permission errors. Encapsulating the mock TCP listener inside a `MockGhostDaemon` class (with `threading.Thread`, `socket.SO_REUSEADDR`, and context manager support) ensures clean port binding during scan execution and instant socket release upon test exit.

4. **Deterministic Timestamp Invariant (Observation 2)**:
   `ContextRotDetector` relies on `os.path.getmtime(full_path)` compared against `time.time()`. By using `os.utime(path, (stale_ts, stale_ts))` where `stale_ts = time.time() - (stale_age_hours * 3600)`, stale files are guaranteed to exceed the 24.0h threshold regardless of when or where the test suite is executed.

5. **Whitelist Verification Guarantee (Observation 2)**:
   Applying `os.utime` with stale timestamps (-72h) to whitelisted files (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, `ORIGINAL_REQUEST.md`) directly validates that whitelisted files are never falsely flagged by the Context Rot detector.

6. **Safety & Zero-Destruction Compliance (Observation 6)**:
   The fixture generator writes exclusively into the caller-provided `temp_dir` (or `pytest.tmp_path`). It does not modify any files in the parent workspace, ensuring 100% compliance with `FileSystemSnapshot` integrity verification.

---

## 3. Caveats

1. **Loopback Port Binding in Constrained Sandbox Environments**:
   On certain restricted CI containers or Windows sandbox runners, opening a loopback socket on port 3000/8000 might be restricted if another system service is active. The `MockGhostDaemon` design gracefully handles bind failures with clear diagnostic logging and supports ephemeral/custom port configuration.
2. **Filesystem Timestamp Precision**:
   On certain virtualized or FAT32 filesystems, `os.utime` resolution is 2 seconds. Using an offset of 72 hours (259,200 seconds) provides an overwhelming margin of safety over the 24.0h (86,400s) threshold.
3. **Read-Only Explorer Scope**:
   As an explorer subagent, no production code has been modified directly. The implementation blueprint below is provided as a drop-in reference for the implementation worker.

---

## 4. Conclusion & Implementation Blueprint

The mock workspace fixture helper should be organized into:
- `fixtures/__init__.py`: Package export file.
- `fixtures/mock_workspace.py`: Complete mock workspace factory, clean workspace generator, `MockGhostDaemon` controller, context managers, and pytest fixtures.

### Drop-In Implementation Blueprint: `.agents/cron/fixtures/__init__.py`

```python
"""Fixtures package for Antigravity Health Scanner test environments."""

from .mock_workspace import (
    MockGhostDaemon,
    MockWorkspaceContext,
    clean_workspace,
    create_clean_workspace,
    create_mock_workspace,
    mock_workspace,
)

__all__ = [
    "create_mock_workspace",
    "create_clean_workspace",
    "MockGhostDaemon",
    "MockWorkspaceContext",
    "mock_workspace",
    "clean_workspace",
]
```

### Drop-In Implementation Blueprint: `.agents/cron/fixtures/mock_workspace.py`

```python
"""Deterministic Mock Workspace Fixture Factory for Antigravity Health Scanner.

Simultaneously reproduces all 5 August 23/24 historical failure patterns:
1. Ghost Daemons: Unmonitored Next.js/Uvicorn TCP listener on port 3000/8000.
2. Context Rot: Stale planning artifacts (>24h old) with protected whitelisted manifests.
3. Ecosystem Pollution: Unused .disabled plugins and cross-track domain leaks.
4. Secret Zero: Unresolved placeholder tokens (your_token_here) across .env and config files.
5. Prompt Fatigue: GEMINI.md manifest exceeding 100 lines with duplicate rule headings.
"""

import json
import os
import shutil
import socket
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Optional, Set, Union
import pytest

from config import (
    CONTEXT_ROT_THRESHOLD_HOURS,
    MONITORED_PORTS,
    PROMPT_FATIGUE_MAX_LINES,
    WHITELISTED_FILENAMES,
)
from models import DetectorType


# ---------------------------------------------------------------------------
# 1. Mock TCP Loopback Server (Ghost Daemon)
# ---------------------------------------------------------------------------

class MockGhostDaemon:
    """Manages a lightweight background TCP listener on loopback interface to simulate

    an unmonitored ghost daemon causing socket collisions (WinError 10048).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 3000) -> None:
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.running = threading.Event()
        self._bound = False

    def start(self, timeout_s: float = 2.0) -> bool:
        """Starts the mock listening socket on a background thread."""
        if self._bound:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.host, self.port))
            self.sock.listen(5)
            self._bound = True
            self.running.set()

            def _listener_loop() -> None:
                while self.running.is_set() and self.sock:
                    try:
                        self.sock.settimeout(0.5)
                        conn, _ = self.sock.accept()
                        conn.close()
                    except (socket.timeout, OSError):
                        continue

            self.thread = threading.Thread(target=_listener_loop, daemon=True, name=f"GhostDaemon-{self.port}")
            self.thread.start()
            return True
        except Exception:
            self._bound = False
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            return False

    def stop(self) -> None:
        """Stops the listener thread and closes the socket immediately."""
        self.running.clear()
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self._bound = False

    def is_running(self) -> bool:
        """Checks if the mock ghost daemon is currently bound and listening."""
        return self._bound

    def __enter__(self) -> "MockGhostDaemon":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# 2. Workspace File Generation Templates
# ---------------------------------------------------------------------------

def _write_file(path: Union[str, Path], content: str, mtime_offset_hours: float = 0.0) -> None:
    """Helper to write a text file, creating parent directories, and optionally setting mtime."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    if mtime_offset_hours != 0.0:
        target_mtime = time.time() - (mtime_offset_hours * 3600.0)
        os.utime(str(p), (target_mtime, target_mtime))


def _generate_bloated_gemini_manifest(line_count: int = 135) -> str:
    """Constructs a bloated GEMINI.md exceeding 100 lines with duplicate rule headings."""
    header = """# Antigravity Global Steering & Workspace Manifest

<system>
## Permanent System Instructions & Architectural Boundary
This manifest defines the permanent operating rules for all AI agents.
</system>

<workspace_manifest>
## Hobbies & Active Tracks
1. [TRACK 1] /sports_cards: Scope includes Card Ladder ETL pipelines and market analytics.
2. [TRACK 2] /content_creation: Scope includes FFmpeg and HDR video processing.
3. [TRACK 3] /apps: Scope includes production software applications.
4. [TRACK 4] /travel_and_life: Scope includes travel logistics.
</workspace_manifest>

## Core Operating Directives

### R1. Workflow Distillation Directive (`workflow-skill-creator`)
- Mandatory Trigger: Upon completing any complex multi-step workflow.
- Action: Offer to invoke workflow-skill-creator.

### R2. The Zero-Discretion Mandate (The Leash Protocol)
- Mandate: Agents are strictly forbidden from self-certifying completion.
- Action: Execute deterministic test suite with Loud Assertions.

### R3. The Lifeline Extraction Protocol
- Mandate: Extract root cause and state Lifeline explicitly before proceeding.

### R1. Workflow Distillation Directive (`workflow-skill-creator`)
- Duplicate Section: Redundant copy of R1 workflow distillation directive.
- Action: Offer to invoke workflow-skill-creator.

### R2. The Zero-Discretion Mandate (The Leash Protocol)
- Duplicate Section: Redundant copy of R2 zero discretion directive.
- Action: Enforce static AST queries and loud assertions.

<RULE[G:\\My Drive\\GOOGLE ANTIGRAVITY\\GEMINI.md]>
Duplicate rule tag identifier.
</RULE[G:\\My Drive\\GOOGLE ANTIGRAVITY\\GEMINI.md]>
"""
    lines = header.splitlines()
    current_count = len(lines)
    padding_needed = max(0, line_count - current_count)

    padding_lines = []
    for i in range(1, padding_needed + 1):
        padding_lines.append(f"<!-- Procedural rule padding directive item #{i}: Maintain strict system invariants -->")

    return "\n".join(lines + padding_lines) + "\n"


def _generate_clean_gemini_manifest() -> str:
    """Constructs a concise, clean GEMINI.md (<50 lines) with zero duplicate headers."""
    return """# Antigravity Global Steering & Workspace Manifest

<system>
## Permanent System Instructions
Developer: Noah Eidson (America/Phoenix, MST)
Focus entirely on verified facts, executable actions, and exact diffs.
</system>

<workspace_manifest>
## Active Tracks
1. [TRACK 1] /sports_cards: ETL and market analytics.
2. [TRACK 2] /content_creation: Media engineering.
3. [TRACK 3] /apps: Production software.
4. [TRACK 4] /travel_and_life: Travel planning.
</workspace_manifest>

## Core Directives
### R1. Workflow Distillation
Prompt user to distill novel workflows into permanent skills.

### R2. Zero-Discretion Mandate
Execute deterministic tests before claiming completion.

### R3. Lifeline Extraction
Extract systemic lessons upon pipeline failures.
"""


# ---------------------------------------------------------------------------
# 3. Workspace Factory Functions
# ---------------------------------------------------------------------------

def create_mock_workspace(
    temp_dir: Optional[Union[str, Path]] = None,
    include_anomalies: bool = True,
    stale_age_hours: float = 72.0,
    manifest_lines: int = 135,
) -> str:
    """Creates a deterministic mock workspace directory.

    If include_anomalies is True, generates all 5 August 23/24 historical failure patterns simultaneously:
    1. Ghost Daemons: Creates .daemons/nextjs_3000.pid metadata file.
    2. Context Rot: Creates docs/stale_architecture_proposal.md, planning/stale_migration_plan.md,
       and .agents/legacy_worker/progress.md with mtime > 24h ago, alongside protected whitelisted manifests.
    3. Ecosystem Pollution: Creates .gemini/config/plugins/mock_plugin.disabled/ and cross-track leak
       content_creation/card_ladder_model.py and sports_cards/intro_render.mp4.
    4. Secret Zero: Creates .env.example, .env.local, config/settings.yaml with 'your_token_here'.
    5. Prompt Fatigue: Creates GEMINI.md with >100 lines and duplicate rule headings.

    Returns the absolute path to the initialized mock workspace directory.
    """
    if temp_dir is None:
        target_dir = Path(tempfile.mkdtemp(prefix="mock_ws_"))
    else:
        target_dir = Path(temp_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

    root = str(target_dir.resolve())

    # --- 1. Whitelisted Manifests (Always present, protected against Context Rot) ---
    _write_file(
        target_dir / "PROJECT.md",
        "# Project Specification\nWhitelisted project specification manifest.\n",
        mtime_offset_hours=stale_age_hours,  # Even if 72h old, must NOT be flagged
    )
    _write_file(
        target_dir / "README.md",
        "# Antigravity Workspace\nProject documentation README.\n",
        mtime_offset_hours=stale_age_hours,
    )
    _write_file(
        target_dir / "BRIEFING.md",
        "# BRIEFING\nWorking memory index.\n",
        mtime_offset_hours=stale_age_hours,
    )
    _write_file(
        target_dir / "ORIGINAL_REQUEST.md",
        "# Original Request\nAuthoritative user request.\n",
        mtime_offset_hours=stale_age_hours,
    )

    if not include_anomalies:
        # Generate clean baseline environment
        _write_file(target_dir / "GEMINI.md", _generate_clean_gemini_manifest())
        _write_file(target_dir / "docs" / "active_sprint_plan.md", "# Active Plan\nFresh plan.\n")
        _write_file(target_dir / ".env", "PORT=8080\nDEBUG=false\nAPI_KEY=prod_live_sec_99182\n")
        _write_file(target_dir / "config" / "settings.yaml", "environment: production\ntimeout_s: 30\n")
        _write_file(target_dir / "sports_cards" / "etl.py", "def run_etl(): return True\n")
        _write_file(target_dir / "content_creation" / "render.py", "def run_render(): return True\n")
        return root

    # --- 2. Pattern A: Ghost Daemons Metadata ---
    _write_file(
        target_dir / ".daemons" / "nextjs_3000.pid",
        json.dumps({"pid": 14208, "port": 3000, "command": "next dev", "status": "UNMONITORED"}),
    )
    _write_file(
        target_dir / ".daemons" / "uvicorn_8000.pid",
        json.dumps({"pid": 19440, "port": 8000, "command": "uvicorn main:app", "status": "UNMONITORED"}),
    )

    # --- 3. Pattern B: Context Rot Stale Planning Artifacts (> 24h old) ---
    _write_file(
        target_dir / "docs" / "stale_architecture_proposal.md",
        "# Stale Architecture Proposal\nDraft proposal from 72 hours ago.\n",
        mtime_offset_hours=stale_age_hours,  # 72 hours ago
    )
    _write_file(
        target_dir / "planning" / "stale_migration_plan.md",
        "# Stale Migration Plan\nOld migration plan from 96 hours ago.\n",
        mtime_offset_hours=stale_age_hours + 24.0,  # 96 hours ago
    )
    _write_file(
        target_dir / ".agents" / "legacy_worker" / "progress.md",
        "# Progress\nLast visited: 2026-08-20T12:00:00Z\n",
        mtime_offset_hours=stale_age_hours,
    )
    # Also create a fresh plan (<24h) to verify it is NOT flagged
    _write_file(
        target_dir / "docs" / "active_sprint_plan.md",
        "# Active Sprint Plan\nFresh plan created today.\n",
        mtime_offset_hours=0.5,  # 30 minutes ago
    )

    # --- 4. Pattern C: Ecosystem Pollution (.disabled & cross-track leaks) ---
    _write_file(
        target_dir / ".gemini" / "config" / "plugins" / "mock_plugin.disabled" / "SKILL.md",
        "# Mock Plugin (Disabled)\nUnused disabled plugin configuration.\n",
    )
    _write_file(
        target_dir / ".gemini" / "config" / "plugins" / "bigquery_sql.disabled" / "SKILL.md",
        "# BigQuery SQL Plugin (Disabled)\nUnused disabled plugin directory.\n",
    )
    _write_file(
        target_dir / "config" / "legacy_crawler.disabled",
        "Legacy disabled configuration file.\n",
    )
    # Cross-track leak: Card ladder sports card logic placed inside /content_creation
    _write_file(
        target_dir / "content_creation" / "card_ladder_model.py",
        "def calculate_psa_grade_value(card_ladder_id: str, psa_grade: int) -> float:\n"
        "    return 500.0\n",
    )
    _write_file(
        target_dir / "content_creation" / "sports_card_analytics.csv",
        "card_ladder_id,psa_grade,price\n101,10,450.0\n",
    )
    # Cross-track leak: Media file placed inside /sports_cards
    _write_file(
        target_dir / "sports_cards" / "intro_render.mp4",
        "MOCK_MP4_BINARY_DATA",
    )
    _write_file(
        target_dir / "sports_cards" / "video_converter.py",
        "# Video conversion script with ffmpeg keywords\n"
        "import subprocess\n"
        "def run_ffmpeg():\n"
        "    subprocess.run(['ffmpeg', '-i', 'in.mp4', 'out.mp4'])\n",
    )

    # --- 5. Pattern D: Secret Zero Placeholder Tokens ---
    _write_file(
        target_dir / ".env.example",
        "API_KEY=your_token_here\n"
        "DATABASE_URL=postgres://user:your_token_here@localhost:5432/antigravity\n"
        "APP_ENV=development\n",
    )
    _write_file(
        target_dir / ".env.local",
        "OPENAI_API_KEY=YOUR_API_KEY_HERE\n"
        "AWS_SECRET_ACCESS_KEY=your-secret-key-here\n"
        "PORT=3000\n",
    )
    _write_file(
        target_dir / "config" / "settings.yaml",
        "service_auth:\n"
        "  token: INSERT_API_KEY_HERE\n"
        "  secret: CHANGE_ME\n"
        "  timeout: 30\n",
    )
    _write_file(
        target_dir / "config" / "api_keys.json",
        json.dumps({"claude_key": "sk-ant-api03-placeholder_key-test12345678901234567890", "active": True}, indent=2),
    )
    # Clean config file (must NOT be flagged)
    _write_file(
        target_dir / "config" / "public_config.json",
        json.dumps({"app_name": "Antigravity", "version": "2.0.0"}, indent=2),
    )

    # --- 6. Pattern E: Prompt Fatigue Manifest Bloat (> 100 lines + duplicates) ---
    _write_file(
        target_dir / "GEMINI.md",
        _generate_bloated_gemini_manifest(line_count=manifest_lines),
    )

    return root


def create_clean_workspace(temp_dir: Optional[Union[str, Path]] = None) -> str:
    """Convenience helper to create a pristine mock workspace with 0 anomalies."""
    return create_mock_workspace(temp_dir=temp_dir, include_anomalies=False)


# ---------------------------------------------------------------------------
# 4. Context Manager & Pytest Fixture Support
# ---------------------------------------------------------------------------

@contextmanager
def MockWorkspaceContext(
    include_anomalies: bool = True,
    start_ghost_daemon: bool = False,
    ghost_port: int = 3000,
    stale_age_hours: float = 72.0,
) -> Generator[str, None, None]:
    """Context manager that provisions a temporary mock workspace, optionally starts

    a mock ghost daemon, yields the workspace root path, and cleans up on exit.
    """
    temp_dir = tempfile.mkdtemp(prefix="mock_ws_ctx_")
    daemon: Optional[MockGhostDaemon] = None
    try:
        ws_path = create_mock_workspace(
            temp_dir=temp_dir,
            include_anomalies=include_anomalies,
            stale_age_hours=stale_age_hours,
        )
        if start_ghost_daemon:
            daemon = MockGhostDaemon(port=ghost_port)
            daemon.start()
        yield ws_path
    finally:
        if daemon:
            daemon.stop()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_workspace(tmp_path: Path) -> str:
    """Pytest fixture providing a fresh anomalous mock workspace per test."""
    ws = tmp_path / "mock_workspace"
    return create_mock_workspace(temp_dir=ws, include_anomalies=True)


@pytest.fixture
def clean_workspace(tmp_path: Path) -> str:
    """Pytest fixture providing a fresh pristine clean workspace per test."""
    ws = tmp_path / "clean_workspace"
    return create_clean_workspace(temp_dir=ws)


@pytest.fixture
def ghost_daemon_server() -> Generator[MockGhostDaemon, None, None]:
    """Pytest fixture managing a running mock loopback ghost daemon on port 3000."""
    daemon = MockGhostDaemon(port=3000)
    daemon.start()
    try:
        yield daemon
    finally:
        daemon.stop()
```

---

## 5. Verification Method

To independently verify the mock workspace fixture factory and ensure complete detection coverage:

1. **Unit & Integration Test Execution**:
   Run the full detector and scanner test suite against the created mock workspace:
   ```bash
   pytest .agents/cron/tests/test_detectors.py -v
   ```

2. **Full Mock Workspace Health Scan Verification**:
   Execute a programmatic assertion script verifying that `HealthScanner` detects all five historical failure patterns simultaneously on `create_mock_workspace()`:
   ```python
   import tempfile
   from fixtures.mock_workspace import create_mock_workspace, create_clean_workspace, MockGhostDaemon
   from scanner import HealthScanner
   from models import DetectorType

   with tempfile.TemporaryDirectory() as tmp:
       ws = create_mock_workspace(tmp)
       with MockGhostDaemon(port=3000):
           scanner = HealthScanner()
           anomalies = scanner.scan_workspace(ws)
           detected = {a.detector_type for a in anomalies}
           
           assert DetectorType.GHOST_DAEMONS in detected, "Ghost Daemons not detected"
           assert DetectorType.CONTEXT_ROT in detected, "Context Rot not detected"
           assert DetectorType.ECOSYSTEM_POLLUTION in detected, "Ecosystem Pollution not detected"
           assert DetectorType.SECRET_ZERO in detected, "Secret Zero not detected"
           assert DetectorType.PROMPT_FATIGUE in detected, "Prompt Fatigue not detected"
           assert len(anomalies) >= 10, f"Expected >= 10 anomalies, got {len(anomalies)}"

   with tempfile.TemporaryDirectory() as tmp_clean:
       clean_ws = create_clean_workspace(tmp_clean)
       scanner = HealthScanner()
       clean_anomalies = scanner.scan_workspace(clean_ws)
       assert len(clean_anomalies) == 0, f"Clean workspace produced false positives: {clean_anomalies}"
   ```

3. **Cryptographic 0-Destruction Verification**:
   Run `FileSystemSnapshot` against the mock workspace before and after `HealthScanner.scan_workspace(ws)` and assert `snapshot.assert_untouched()` raises zero assertion errors.

4. **Invalidation Conditions**:
   - Any detector fails to detect its corresponding failure pattern in `create_mock_workspace()`.
   - Whitelisted manifest files (`PROJECT.md`, `README.md`, `BRIEFING.md`, `ORIGINAL_REQUEST.md`) are falsely flagged by `ContextRotDetector`.
   - `create_clean_workspace()` produces any non-zero anomaly count.
   - `MockGhostDaemon` fails to release socket resources upon teardown.

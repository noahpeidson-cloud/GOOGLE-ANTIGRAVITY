"""Deterministic Mock Workspace Factory reproducing all 5 August 23/24 historical failure patterns."""

import os
import socket
import threading
import time
from typing import Optional


class MockDaemonListener:
    """Lightweight loopback TCP server socket listener for simulating ghost daemons.

    Runs in a background thread and cleans up safely on exit.
    """

    def __init__(self, port: int = 3000, host: str = "127.0.0.1") -> None:
        self.port = port
        self.host = host
        self.server_sock: Optional[socket.socket] = None
        self._is_running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> int:
        """Binds and listens on host:port, returning the bound port."""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_sock.bind((self.host, self.port))
        except OSError:
            # If default port is unavailable, bind to ephemeral port
            self.server_sock.bind((self.host, 0))
            self.port = self.server_sock.getsockname()[1]

        self.server_sock.listen(5)
        self._is_running = True

        def _accept_loop() -> None:
            while self._is_running and self.server_sock:
                try:
                    self.server_sock.settimeout(0.5)
                    client, _ = self.server_sock.accept()
                    client.close()
                except (socket.timeout, OSError):
                    continue

        self._thread = threading.Thread(target=_accept_loop, daemon=True)
        self._thread.start()
        return self.port

    def stop(self) -> None:
        """Safely stops the listener and closes the server socket."""
        self._is_running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def __enter__(self) -> "MockDaemonListener":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


def create_mock_workspace(temp_dir: str) -> str:
    """Creates a deterministic mock Antigravity workspace inside temp_dir reproducing

    all 5 August 23/24 historical failure patterns simultaneously:
    1. Ghost Daemons: Creates mock daemon PID/port metadata file.
    2. Context Rot: Creates docs/stale_architecture_proposal.md with mtime > 24h ago (72h),
       alongside whitelisted manifests (PROJECT.md, GEMINI.md, README.md, BRIEFING.md).
    3. Ecosystem Pollution: Creates .gemini/config/plugins/mock_plugin.disabled/ and cross-track
       leak content_creation/sports_cards/card_ladder_model.py.
    4. Secret Zero: Creates .env.example / .env.local with placeholder tokens (API_KEY=your_token_here).
    5. Prompt Fatigue: Creates bloated GEMINI.md (>100 lines) with duplicate rule headings.

    Returns:
        Absolute path to the initialized mock workspace directory.
    """
    ws_root = os.path.abspath(temp_dir)
    os.makedirs(ws_root, exist_ok=True)

    current_time = time.time()
    stale_mtime = current_time - (72.0 * 3600.0)  # 72 hours ago

    # =========================================================================
    # Pattern 1: Ghost Daemons (PID / Port configuration)
    # =========================================================================
    daemons_dir = os.path.join(ws_root, ".daemons")
    os.makedirs(daemons_dir, exist_ok=True)
    with open(os.path.join(daemons_dir, "ghost_server_3000.pid"), "w", encoding="utf-8") as f:
        f.write("PID=10048\nPORT=3000\nDAEMON=nextjs_dev_server\nSTATUS=UNMONITORED\n")
    with open(os.path.join(daemons_dir, "ghost_server_8000.pid"), "w", encoding="utf-8") as f:
        f.write("PID=10049\nPORT=8000\nDAEMON=uvicorn_api_server\nSTATUS=UNMONITORED\n")

    # =========================================================================
    # Pattern 2: Context Rot (Stale planning files + Whitelisted manifests)
    # =========================================================================
    docs_dir = os.path.join(ws_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    # 2a. Stale planning artifact (>24h stale)
    stale_proposal_path = os.path.join(docs_dir, "stale_architecture_proposal.md")
    with open(stale_proposal_path, "w", encoding="utf-8") as f:
        f.write(
            "# Stale Architecture Proposal (August 23 2026)\n\n"
            "This architecture proposal is older than 24 hours and represents unarchived planning notes.\n"
            "- Step 1: Draft proposal notes\n"
            "- Step 2: Implement preliminary prototypes\n"
        )
    os.utime(stale_proposal_path, (stale_mtime, stale_mtime))

    # Also an older scratchpad in .agents/
    agents_dir = os.path.join(ws_root, ".agents", "worker_old")
    os.makedirs(agents_dir, exist_ok=True)
    stale_scratchpad_path = os.path.join(agents_dir, "scratchpad.md")
    with open(stale_scratchpad_path, "w", encoding="utf-8") as f:
        f.write("# Old Scratchpad Notes\n- Task 1: pending\n- Task 2: obsolete\n")
    os.utime(stale_scratchpad_path, (stale_mtime, stale_mtime))

    # 2b. Whitelisted manifests (Protected from rot deletion)
    with open(os.path.join(ws_root, "PROJECT.md"), "w", encoding="utf-8") as f:
        f.write(
            "# Project Specification\n\n"
            "## Architecture\nAntigravity Health Scanner daemon.\n"
        )
    with open(os.path.join(ws_root, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Workspace Readme\nProduction Antigravity environment.\n")
    with open(os.path.join(ws_root, "BRIEFING.md"), "w", encoding="utf-8") as f:
        f.write("# BRIEFING\n## 🔒 My Identity\n- Archetype: worker\n")

    # =========================================================================
    # Pattern 3: Ecosystem Pollution (.disabled plugins & cross-track leaks)
    # =========================================================================
    # 3a. .disabled plugin directory
    disabled_plugin_dir = os.path.join(
        ws_root, ".gemini", "config", "plugins", "mock_plugin.disabled"
    )
    os.makedirs(disabled_plugin_dir, exist_ok=True)
    with open(os.path.join(disabled_plugin_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(
            "---\nname: mock-plugin-disabled\ndescription: Disabled mock plugin for crawler tests.\n---\n"
            "# Mock Plugin Disabled\nThis plugin is disabled.\n"
        )

    # 3b. Cross-track leak: sports_cards placed in content_creation
    content_creation_dir = os.path.join(ws_root, "content_creation")
    os.makedirs(content_creation_dir, exist_ok=True)
    cross_track_cards_dir = os.path.join(content_creation_dir, "sports_cards")
    os.makedirs(cross_track_cards_dir, exist_ok=True)

    with open(
        os.path.join(cross_track_cards_dir, "card_ladder_model.py"), "w", encoding="utf-8"
    ) as f:
        f.write(
            '"""Card Ladder ETL pricing and PSA grading model leaked into content_creation."""\n'
            "def calculate_card_ladder_psa_value(card_id: str, psa_grade: int) -> float:\n"
            '    """Sports cards analytics calculation."""\n'
            "    return float(psa_grade * 150.0)\n"
        )

    # Direct card_ladder file in content_creation root
    with open(
        os.path.join(content_creation_dir, "card_ladder_export.py"), "w", encoding="utf-8"
    ) as f:
        f.write('"""Sports card ladder market export script."""\nSPORTS_CARD_PSA_GRADE = 10\n')

    # =========================================================================
    # Pattern 4: Secret Zero (.env files with placeholder keys)
    # =========================================================================
    with open(os.path.join(ws_root, ".env"), "w", encoding="utf-8") as f:
        f.write(
            "# Environment Configuration\n"
            "ENVIRONMENT=development\n"
            "PORT=3000\n"
            "API_KEY=your_token_here\n"
            "GEMINI_API_KEY=YOUR_API_KEY_HERE\n"
        )
    with open(os.path.join(ws_root, ".env.example"), "w", encoding="utf-8") as f:
        f.write("API_KEY=your_token_here\nDATABASE_URL=sqlite:///production.db\n")
    with open(os.path.join(ws_root, ".env.local"), "w", encoding="utf-8") as f:
        f.write("SECRET_KEY=YOUR_TOKEN_HERE\nSERVICE_ACCOUNT_TOKEN=your-secret-key-here\n")

    # =========================================================================
    # Pattern 5: Prompt Fatigue (GEMINI.md > 100 lines with duplicate rule headings)
    # =========================================================================
    gemini_lines = [
        "# Antigravity Global Steering & Workspace Manifest",
        "",
        "<system>",
        "## Permanent System Instructions & Architectural Boundary",
        "Developer: Noah Eidson (America/Phoenix, MST)",
        "Identity: Technical builder, automation architect, Builder-First mindset.",
        "</system>",
        "",
        "<workspace_manifest>",
        "## Hobbies & Active Tracks",
        "1. [TRACK 1] /sports_cards: Card Ladder ETL pipelines.",
        "2. [TRACK 2] /content_creation: Media engineering, FFmpeg.",
        "3. [TRACK 3] /apps: Production software applications.",
        "4. [TRACK 4] /travel_and_life: Travel logistics.",
        "</workspace_manifest>",
        "",
        "## Core Operating Directives",
        "",
        "## R1. Workflow Distillation Directive",
        "Upon completing complex workflows, distill into permanent skills.",
        "",
        "## R2. The Zero-Discretion Mandate",
        "Agents are forbidden from self-certifying subjective completion.",
        "",
        "## R3. The Lifeline Extraction Protocol",
        "Extract root cause lessons on failures.",
        "",
    ]

    # Add procedural rule sections to exceed 100 lines
    for i in range(1, 35):
        gemini_lines.extend(
            [
                f"### Procedural Guideline Section {i}",
                f"- Directive {i}.1: Enforce deterministic guardrail {i}.",
                f"- Directive {i}.2: Log telemetry event {i} to SQLite store.",
                f"- Directive {i}.3: Validate invariant {i} with loud assertions.",
                "",
            ]
        )

    # Insert duplicate rule headings to trigger duplicate section detector
    gemini_lines.extend(
        [
            "## R1. Workflow Distillation Directive",
            "Duplicate rule section: Workflow distillation instructions repeated.",
            "",
            "## R2. The Zero-Discretion Mandate",
            "Duplicate rule section: Zero discretion instructions repeated.",
            "",
        ]
    )

    with open(os.path.join(ws_root, "GEMINI.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(gemini_lines) + "\n")

    return ws_root

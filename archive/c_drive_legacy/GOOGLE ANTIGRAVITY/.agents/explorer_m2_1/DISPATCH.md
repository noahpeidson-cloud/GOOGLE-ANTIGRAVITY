## 2026-08-25T05:26:44Z
You are explorer_m2_1.
Your working directory is: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m2_1
The authoritative user request is at: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md
The project specification is at: g:\My Drive\GOOGLE ANTIGRAVITY\PROJECT.md
The target project directory is: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron

Task:
Investigate and design `detectors/base.py`, `detectors/ghost_daemons.py`, and `detectors/context_rot.py` for Milestone 2:
1. `detectors/base.py`: Abstract `BaseDetector` class with abstract method `scan(self, workspace_root: str) -> List[AnomalyRecord]`.
2. `detectors/ghost_daemons.py`:
   - Non-destructively probes target ports (3000, 8000, 8501) via loopback connection probing (`socket.socket`).
   - Identifies port collisions with `WinError 10048` signature / unmonitored background tasks.
   - Emits `AnomalyRecord` with `DetectorType.GHOST_DAEMONS`, `Severity.HIGH`, and raw metadata (port, pid, process name, error code).
   - Strictly 0 process termination (`taskkill`, `kill` forbidden).
3. `detectors/context_rot.py`:
   - Recursively walks workspace to find `.md` planning artifacts (`*proposal*.md`, `*blueprint*.md`, `*ideas*.md`, `*scratchpad*.md`, `*plan*.md`).
   - Checks `os.path.getmtime(path)` against `CONTEXT_ROT_THRESHOLD_HOURS = 24.0`.
   - Strictly whitelists protected files (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, `ORIGINAL_REQUEST.md`).
   - Emits `AnomalyRecord` with `DetectorType.CONTEXT_ROT`, `Severity.MEDIUM`, age in hours, and proposed action `MOVE_TO_ARCHIVE`.
4. Write full specification and implementation blueprints to `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m2_1\handoff.md`.
Update `progress.md` as you work. Send a message to parent when complete. Do not write implementation code directly.

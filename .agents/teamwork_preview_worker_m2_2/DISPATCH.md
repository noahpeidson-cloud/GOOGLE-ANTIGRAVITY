## 2026-09-04T23:45:00Z
You are teamwork_preview_worker_m2_2.
Your working directory is: d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m2_2
Project root: d:\GOOGLE ANTIGRAVITY

MANDATORY FIRST STEP: Read the user's latest request in:
d:\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md (specifically check the section at timestamp 2026-09-04T23:34:50Z).

INPUT SOURCES TO CONSULT:
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_1\handoff.md` and `analysis.md`
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_2\handoff.md` and `analysis.md`
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_3\handoff.md` and `analysis.md`
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_6\handoff.md`

YOUR EXCLUSIVE WRITE OWNERSHIP:
You own and must implement the following standalone, modular, research-validated Python tools in `d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault`:
1. `davinci_automation/resolve_timeline_builder.py`
   - Cross-platform DaVinci Resolve Studio scripting API discovery (`fusionscript`).
   - Frame-accurate subclip timeline insertion with exact integer frame rounding (`round(time * fps)`).
   - Non-destructive 4K media pool bin creation, timeline versioning, and export settings (disabling optimized media, ScaleToFill).
   - Single-worker concurrency serialization lock warning.
2. `davinci_automation/http_range_video_streamer.py`
   - Production-grade FastAPI HTTP 206 Partial Content byte-range video streaming endpoint (64KB chunks, `Content-Range`, `Accept-Ranges`).
   - Single-job async subprocess supervisor with `asyncio.Lock()` mutex, HTTP 409 conflict handling, ring-buffered stdout/stderr deque, and graceful cancellation (`terminate()` -> 3.0s -> `kill()`).
3. `ingestion_hardware/samsung_adb_ingestor.py`
   - Headless wireless ADB mDNS discovery and connection manager with exponential backoff and jitter.
   - Samsung One UI 6+ Auto Blocker bypass (`settings put global rampart_auto_enabled_switch_enabled 0`).
   - Atomic `.part` file pulling with on-device Linux `sha256sum` cross-airgap verification and cryptographic quarantine.
4. `ingestion_hardware/win32_three_tier_file_locker.py`
   - 3-tier Windows file lock detector: Tier 1 extension filtering (`.part`, `.tmp`), Tier 2 Win32 exclusive handle check (`win32file.CreateFile` with `dwShareMode=0` and Error 5 read-only fallback), Tier 3 byte-size growth debounce check.
5. `ingestion_hardware/canonical_filename_normalizer.py`
   - Canonical filename syntax enforcement: NFKD Unicode decomposition, DJ Latin transliteration (`Ø -> O`, `æ -> ae`, `ß -> ss`), stripping illegal OS characters.
   - `DirectoryHealthGuard`: Automated 50-item folder capacity partitioning to prevent NTFS directory enumeration degradation.

MANDATORY INTEGRITY & FRONTMATTER REQUIREMENT:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

EVERY SINGLE FILE MUST begin with a formatted docstring or YAML frontmatter containing:
- Name: The tool or concept name.
- Context Mapping: Point of reference tying this concept back to its original use case or pipeline.
- Strengths: Why this specific concept was deemed valuable and research-validated.
- Weaknesses: Flaws, limitations, or reasons why the original surrounding architecture failed.
- Implementation Instructions: How to safely use this logic in future builds.

ZERO-MODIFICATION GUARANTEE:
You are STRICTLY FORBIDDEN from deleting or modifying any existing files outside `d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault`. All your output must be written exclusively to your assigned target files in `d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault`.

DELIVERABLES:
1. Write the 5 complete, standalone Python files with full frontmatter docstrings.
2. Verify Python syntax (`python -m py_compile ...` via run_command) on all authored files.
3. Update progress.md in your working directory.
4. Write handoff.md in your working directory with verification commands and results.
5. Send completion message to orchestrator.

## 2026-08-27T10:06:03Z

You are Explorer 2 for Milestone 1 of baptism_of_music_brain.
Your working directory is C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_explorer_2

MANDATORY FIRST STEPS:
1. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\ORIGINAL_REQUEST.md
2. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\PROJECT.md

Scope:
Investigate and design:
1. `src/watcher/file_locker.py`: 3-tier Windows file lock detector:
   - Tier 1: Temporary extension filter (`.tmp`, `.part`, `.crdownload`).
   - Tier 2: Native Win32 exclusive file handle test using `win32file.CreateFile` (with fallback to `open(..., 'rb')` if pywin32 is mock/unavailable).
   - Tier 3: Size stability debounce (checking file size across 1.0s interval).
2. `src/watcher/ingest_watcher.py`: Ingestion directory watcher utilizing `watchdog` / `watchfiles` with background polling fallback, event debouncing, and seamless handoff to pipeline on lock release.

Write your investigation and implementation plan to C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_explorer_2\plan.md and handoff.md, then notify parent.

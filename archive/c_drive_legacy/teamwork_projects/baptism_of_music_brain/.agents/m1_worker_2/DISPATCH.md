## 2026-08-27T10:18:34Z

You are the Remediation Worker for Milestone 1 of baptism_of_music_brain.
Your working directory is C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_worker_2

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY FIRST STEPS:
1. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\ORIGINAL_REQUEST.md
2. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\PROJECT.md
3. Read Reviewer feedback:
   - C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_reviewer_1\handoff.md
   - C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_reviewer_2\handoff.md

Tasks:
1. In `src/watcher/file_locker.py`:
   - Export convenience wrapper `is_file_locked(path, debounce_interval_sec=1.0) -> bool`:
     Evaluates `check_file_lock(path, debounce_interval_sec)` and returns `result.is_locked`.
   - Export convenience wrapper `wait_until_unlocked(path, timeout_sec=60.0, poll_interval_sec=1.0, debounce_interval_sec=1.0) -> bool`:
     Evaluates `wait_until_file_unlocked(...)` and returns `result.is_ready`.
   - In `test_exclusive_handle`: Handle read-only files properly. Attempt `win32con.GENERIC_READ | win32con.GENERIC_WRITE` with `dwShareMode=0`. If it fails with `ERROR_ACCESS_DENIED` (code 5) due to file read-only attribute, retry with `win32con.GENERIC_READ` and `dwShareMode=0` to ensure read-only camera / SD card footage is not falsely flagged as locked. In fallback mode, fallback to `open(p, 'rb')` if read-only attribute prevents `r+b`.
2. Run `pytest -v tests/tier1_feature/ tests/tier2_boundary/test_boundary_locking.py` and ensure all 8 previously-skipped Tier 2 locking tests now execute and pass 100%.
3. Write your handoff report at C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m1_worker_2\handoff.md and notify parent.

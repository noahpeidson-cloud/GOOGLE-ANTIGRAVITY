# Dispatch Instructions: Worker Remediation Patch

## Mission
Apply the targeted fixes identified by Reviewer 2, Challenger 1, and Challenger 2 to `d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor\`:

1. **`client.py` (lines 261 & 427)**:
   Update error string checking so Google's upstream `API error (code 5): NOT_FOUND` is correctly detected:
   ```python
   if "not found" in err_msg.lower() or "not_found" in err_msg.lower() or "code 5" in err_msg.lower():
       raise NotebookNotFoundError(f"Notebook '{notebook_id}' not found: {err_msg}")
   ```

2. **`extractor.py` (line 333)**:
   Change `NotebookNotFoundError` exit code from `2` to `1` so missing/invalid notebooks exit with standard failure code 1:
   ```python
   except client.NotebookNotFoundError as e:
       sys.stderr.write(f"\nERROR: {e}\n")
       sys.exit(1)
   ```

3. **`extractor.py` (Default output safety)**:
   Ensure that when `--dry-run` is active and `--output` was not explicitly supplied, the output defaults to `extracted_notebook_data_dryrun.json` to prevent accidental clobbering of the full 61-source deliverable.

4. **`tests/test_extractor_dry.py` & `tests/test_extractor_full.py`**:
   - Update `test_extractor_full.py` to use `--transport mcp` (which runs in ~57s vs >210s direct) and increase timeout to `300` seconds so network fluctuations don't cause spurious timeouts.
   - Update `test_extractor_dry.py` timeout to `120` seconds.

5. **Regenerate the Deliverable**:
   Run full live extraction for notebook `4b52cc67-9f81-4e85-a024-5f06756991ab` into `extracted_notebook_data.json`:
   ```powershell
   python extractor.py --notebook-id 4b52cc67-9f81-4e85-a024-5f06756991ab --output extracted_notebook_data.json --transport mcp
   ```
   Verify that `extracted_notebook_data.json` contains exactly 61 sources, 1 note, and size > 2.2 MB.

6. **Run Full Pytest Suite**:
   Run `python -m pytest` across all tests (including `tests/test_challenger_adversarial.py`).
   Assert 100% pass rate with 0 failures and 0 timeouts.

## 2026-09-04T20:10:08Z
You are teamwork_preview_worker operating in:
Working directory: d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m1_patch
Target Workspace: d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY FIRST STEP:
Read d:\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md under header `## Follow-up — 2026-09-04T19:09:20Z` and read your task description in d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m1_patch\DISPATCH.md.
Also read `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_orchestrator_4\GATE_STATUS.md`.

YOUR MISSION:
Apply the targeted remediation fixes to resolve the 4 defects discovered during the gate review:

1. `client.py` (lines 261 & 427):
   Update error string checking to recognize Google's upstream error `API error (code 5): NOT_FOUND`:
   ```python
   if "not found" in err_msg.lower() or "not_found" in err_msg.lower() or "code 5" in err_msg.lower():
       raise NotebookNotFoundError(f"Notebook '{notebook_id}' not found: {err_msg}")
   ```

2. `extractor.py` (line 333):
   Update `NotebookNotFoundError` exit code from `2` to `1` so missing or invalid notebook IDs exit with code 1.

3. `extractor.py` (Default output safety):
   When `--dry-run` is active and `--output` was not explicitly supplied by the user, default to `extracted_notebook_data_dryrun.json` to prevent accidental clobbering of the full 61-source deliverable.

4. `tests/test_extractor_dry.py` & `tests/test_extractor_full.py`:
   - In `test_extractor_full.py`, change the subprocess invocation to use `"--transport", "mcp"` (which runs in ~57s instead of >210s) and set `timeout=300`.
   - In `test_extractor_dry.py`, set `timeout=120`.

5. Regenerate the Deliverable:
   Run the full live extraction to ensure `extracted_notebook_data.json` contains all 61 sources + 1 note:
   ```powershell
   python extractor.py --notebook-id 4b52cc67-9f81-4e85-a024-5f06756991ab --output extracted_notebook_data.json --transport mcp
   ```
   Verify that `extracted_notebook_data.json` has `len(sources) == 61`, `len(notes) == 1`, file size > 2.2 MB.

6. Run the Full Pytest Suite:
   Run `python -m pytest` across all test files (including `tests/test_challenger_adversarial.py`).
   Verify all tests pass with 100% success rate, 0 failures, 0 timeouts.

DELIVERABLE:
Write your complete handoff report to:
`d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m1_patch\handoff.md`
Follow the Handoff Protocol (Observation, Logic Chain, Caveats, Conclusion, Verification Method).
When finished, send a message to parent (cb86c11d-e5b4-4cd3-b3be-d050fdfdc098) with a concise summary.

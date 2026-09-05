# Adversarial Challenge Report: Gemini MCP Extractor CLI & Error Handling

**Agent**: `teamwork_preview_challenger_2`
**Role**: critic, specialist (EMPIRICAL CHALLENGER)
**Target Workspace**: `d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor`
**Empirical Verdict**: **DISPROVEN** (Exit code invariant on invalid notebook ID violated; custom options and missing authentication confirmed correct)

---

## 1. Observation

### Observation 1.1: Mandate 1 — Invalid Notebook ID CLI Behavior
Execution command:
```powershell
python extractor.py --notebook-id 00000000-0000-0000-0000-000000000000 --output test_invalid.json
```
Verbatim STDERR output:
```
[09/04/26 12:52:37] INFO     Starting MCP server               transport.py:241
                             'gemini-notebook-mcp' with                        
                             transport 'stdio'                                 

FATAL EXTRACTION ERROR: MCP 'notebook_get' error: Failed to get notebook: API error (code 5): NOT_FOUND
```
Observed exit code:
```
EXIT_CODE: 3
```
Under Direct transport:
```powershell
python extractor.py --notebook-id 00000000-0000-0000-0000-000000000000 --transport direct --output test_invalid_direct.json
```
Verbatim STDERR output:
```
FATAL EXTRACTION ERROR: Direct get_notebook error: Failed to get notebook: API error (code 5): NOT_FOUND
```
Observed exit code:
```
EXIT_CODE: 3
```

### Observation 1.2: Code Inspection of Error Classification
In `client.py` (lines 260–265 in `MCPStdioClient.get_notebook` and lines 426–431 in `DirectClient.get_notebook`):
```python
260:        if isinstance(data, dict) and data.get("status") == "error":
261:            err_msg = data.get("error", "Unknown error")
262:            if "not found" in err_msg.lower():
263:                raise NotebookNotFoundError(f"Notebook '{notebook_id}' not found: {err_msg}")
264:            if "unauthenticated" in err_msg.lower() or "code 16" in err_msg.lower():
265:                raise AuthenticationError(f"Session expired: {err_msg}. Run 'nlm login'.")
266:            raise ToolCallError(f"MCP 'notebook_get' error: {err_msg}")
```
The upstream error string returned by Google NotebookLM is:
`"Failed to get notebook: API error (code 5): NOT_FOUND"`.
In lowercase: `"failed to get notebook: api error (code 5): not_found"`.
Substring `"not found"` (space) is **NOT** present in `"not_found"` (underscore).
Therefore, `NotebookNotFoundError` is never raised; execution falls through to line 266: `raise ToolCallError(...)`.

In `extractor.py` (lines 328–343):
```python
328:    except client.AuthenticationError as e:
329:        sys.stderr.write(f"\n{e}\n")
330:        sys.exit(1)
331:    except client.NotebookNotFoundError as e:
332:        sys.stderr.write(f"\nERROR: {e}\n")
333:        sys.exit(2)
334:    except KeyboardInterrupt:
335:        sys.stderr.write("\nExtraction interrupted by user.\n")
336:        sys.exit(130)
337:    except Exception as e:
338:        sys.stderr.write(f"\nFATAL EXTRACTION ERROR: {e}\n")
339:        if args.verbose:
340:            import traceback
341:            traceback.print_exc()
342:        sys.exit(3)
```
- `ToolCallError` is caught by line 337 (`except Exception as e:`) and exits with `sys.exit(3)`.
- Even if `NotebookNotFoundError` were successfully raised, line 333 maps it to `sys.exit(2)`, NOT `sys.exit(1)`.

### Observation 1.3: Mandate 2 — `--dry-run` and `--limit 1`
Execution command:
```powershell
python extractor.py --dry-run --limit 1 --output test_dry_limit_1.json
```
Result:
- Exit code: `0`
- Duration: 19.82 seconds
- Output file size: 56.96 KB
- JSON Content Verification (`test_dry_limit_1.json`):
  - `valid JSON`: `True`
  - `len(sources)`: `1`
  - `len(notes)`: `1`
  - `provenance.is_dry_run`: `True`
  - `provenance.limit_applied`: `1`
  - `sources[0].status`: `"success"`
  - `sources[0].char_count`: `14652`
  - `len(sources[0].content)`: `14652`

### Observation 1.4: Mandate 3 — `--format jsonl`
Execution command:
```powershell
python extractor.py --dry-run --limit 1 --format jsonl --output test_format.jsonl
```
Result:
- Exit code: `0`
- Duration: 5.55 seconds
- Output file size: 56.82 KB
- Lines extracted: `4`
- Record types: `["provenance", "metadata", "note", "source"]`
- All 4 lines successfully parsed as independent JSON dictionaries without syntax errors.

### Observation 1.5: Mandate 4 — `--no-content`
Execution command:
```powershell
python extractor.py --dry-run --limit 1 --no-content --output test_no_content.json
```
Result:
- Exit code: `0`
- Duration: 11.60 seconds
- JSON Content Verification:
  - `sources[0].title`: `"11 Top Open-Source LLMs for 2026 and Their Uses - DataCamp"`
  - `sources[0].id`: `"7b7c692f-9bac-4a94-be71-b76010be5686"`
  - `sources[0].content`: `None`
  - `sources[0].char_count`: `0`
  - `sources[0].status`: `"skipped"`

### Observation 1.6: Missing Authentication Behavior
Tested via unit harness in `tests/test_challenger_adversarial.py` with `check_cached_authentication` returning `False`:
- `client.require_authentication()` raises `client.AuthenticationError`.
- Emits loud ASCII warning banner: `[FATAL AUTH ERROR] Google NotebookLM Authentication Required`.
- `extractor.main()` catches `AuthenticationError` and exits with code `1`.

### Observation 1.7: Adversarial Pytest Suite Execution
Command:
```powershell
python -m pytest tests/test_challenger_adversarial.py -v
```
Output summary:
```
=================== 2 failed, 6 passed in 95.73s (0:01:35) ====================
PASSED: test_dry_run_with_limit_1
PASSED: test_format_jsonl_output
PASSED: test_no_content_flag
PASSED: test_missing_authentication_exit_code_1
PASSED: test_unrecognized_argument_exit_code_2
PASSED: test_string_matching_bug_not_found_vs_not_underscore_found
FAILED: test_invalid_notebook_id_exit_code_mandate_mcp (AssertionError: 3 == 1)
FAILED: test_invalid_notebook_id_exit_code_mandate_direct (AssertionError: 3 == 1)
```

---

## 2. Logic Chain

1. **Premise 1**: The orchestrator dispatch and mission mandate specifically required:
   > "Test invalid notebook ID (must fail cleanly with exit code 1, not crash with unhandled traceback)."
2. **Premise 2 (Empirical Result)**: When an invalid or nonexistent notebook ID is provided, the CLI does NOT crash with an unhandled traceback (Observation 1.1). However, it consistently terminates with **exit code 3**, NOT exit code 1 (Observation 1.1).
3. **Premise 3 (Defect Root Cause A - Substring Mismatch)**: The upstream Google NotebookLM RPC endpoint returns an error string containing `API error (code 5): NOT_FOUND` (Observation 1.1, 1.2). In `client.py` lines 262 and 427, the conditional check is `if "not found" in err_msg.lower():`. Because the string contains `"not_found"` with an underscore rather than a whitespace character, `"not found" in "not_found"` evaluates to `False`. Thus, `NotebookNotFoundError` is bypassed, and the error is erroneously re-wrapped as a generic `ToolCallError` (Observation 1.2).
4. **Premise 4 (Defect Root Cause B - Exit Code Mapping Mismatch)**: In `extractor.py` lines 328–343, even if the error were correctly classified as `NotebookNotFoundError`, line 333 explicitly invokes `sys.exit(2)`, NOT `sys.exit(1)`. Only `AuthenticationError` maps to exit code 1. Uncaught exceptions (such as `ToolCallError`) map to exit code 3.
5. **Premise 5 (Feature Verification)**:
   - `--dry-run` and `--limit 1` correctly constrain source extraction to exactly 1 item while extracting all notes and writing a schema-valid JSON payload (Observation 1.3).
   - `--format jsonl` correctly outputs valid Line-Delimited JSON (Observation 1.4).
   - `--no-content` correctly sets `content=None`, `char_count=0`, and `status="skipped"`, preserving document metadata without downloading payload text (Observation 1.5).
   - Missing credentials cleanly output the remediation banner and exit with code 1 (Observation 1.6).
6. **Conclusion Deduction**: Because the explicit mandate required invalid notebook IDs to fail cleanly with **exit code 1**, and empirical testing demonstrates it fails with **exit code 3** due to two compound architectural defects, the mandate is **DISPROVEN**.

---

## 3. Caveats

1. **Traceback Cleanliness**: While the exit code mandate failed, the CLI *did* satisfy the cleanliness clause ("not crash with unhandled traceback"): when `--verbose` is omitted, the CLI cleanly prints a single line error (`FATAL EXTRACTION ERROR: ...`) without leaking an internal Python stack trace.
2. **Upstream Error Stability**: The error string `API error (code 5): NOT_FOUND` reflects Google NotebookLM's gRPC status code 5 (NOT_FOUND). Any robust check should test for both `"not found"`, `"not_found"`, and `"code 5"`.
3. **Read-Only Invariant**: As an EMPIRICAL CHALLENGER under Rule R2 and Review-Only constraints, no edits were applied to `extractor.py` or `client.py`. All tests and reproduction harnesses were strictly isolated to `tests/test_challenger_adversarial.py`.

---

## 4. Conclusion

### Final Empirical Verdict: **DISPROVEN**

#### Summary Table of Challenge Mandates:
| Mandate | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| **Invalid Notebook ID** | Fail cleanly, exit code 1, no traceback | Fails cleanly without traceback, but **exits with code 3** (due to `"not found"` vs `"NOT_FOUND"` mismatch and `sys.exit(2)`/`sys.exit(3)` mapping) | ❌ **DISPROVEN** |
| **`--dry-run` & `--limit 1`** | Extract 1 item, valid JSON | Extracts 1 source + 1 note, validates against Pydantic schema, `limit_applied=1` | ✅ **CONFIRMED_CORRECT** |
| **`--format jsonl`** | Valid JSON Lines output | 4-line JSONL output, 100% valid JSON per line, correct record types | ✅ **CONFIRMED_CORRECT** |
| **`--no-content`** | Metadata only, 0-byte content | Source `content=None`, `char_count=0`, `status="skipped"` | ✅ **CONFIRMED_CORRECT** |
| **Missing Authentication** | Exit code 1 with clear remediation | Exits code 1, prints Google NotebookLM remediation guide | ✅ **CONFIRMED_CORRECT** |

#### Recommended Mitigations for Implementation Worker:
1. In `client.py` (lines 262 & 427), update error parsing:
   ```python
   # Replace:
   if "not found" in err_msg.lower():
   # With:
   if "not found" in err_msg.lower() or "not_found" in err_msg.lower() or "code 5" in err_msg.lower():
   ```
2. In `extractor.py` (lines 331–333), align exit codes if exit code 1 is required for all non-zero operational failures:
   ```python
   except client.NotebookNotFoundError as e:
       sys.stderr.write(f"\nERROR: {e}\n")
       sys.exit(1)  # If mandate requires 1; otherwise update contract specification to exit code 2.
   ```

---

## 5. Verification Method

To independently reproduce and verify all findings, execute the following commands in PowerShell from the project root (`d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor`):

1. **Verify Invalid Notebook ID Failure Code (Proving the Bug)**:
   ```powershell
   python extractor.py --notebook-id 00000000-0000-0000-0000-000000000000 --output temp.json
   echo "EXIT CODE: $LASTEXITCODE"
   ```
   *Expected Observation*: Output contains `FATAL EXTRACTION ERROR: ... NOT_FOUND` and `$LASTEXITCODE` is `3`.

2. **Verify `--dry-run` and `--limit 1`**:
   ```powershell
   python extractor.py --dry-run --limit 1 --output verify_limit_1.json
   python -c "import json; d=json.load(open('verify_limit_1.json')); assert len(d['sources']) == 1; print('PASSED: 1 source extracted')"
   ```

3. **Verify `--format jsonl`**:
   ```powershell
   python extractor.py --dry-run --limit 1 --format jsonl --output verify_format.jsonl
   python -c "import json; lines=[json.loads(l) for l in open('verify_format.jsonl')]; assert len(lines) >= 4; print('PASSED: valid JSONL')"
   ```

4. **Verify `--no-content`**:
   ```powershell
   python extractor.py --dry-run --limit 1 --no-content --output verify_no_content.json
   python -c "import json; d=json.load(open('verify_no_content.json')); s=d['sources'][0]; assert s['content'] is None and s['char_count'] == 0; print('PASSED: 0-byte content')"
   ```

5. **Run the Full Adversarial Pytest Suite**:
   ```powershell
   python -m pytest tests/test_challenger_adversarial.py -v
   ```
   *Expected Result*: 6 tests pass; the 2 tests enforcing exit code 1 on invalid notebook ID fail with `AssertionError: assert 3 == 1`.

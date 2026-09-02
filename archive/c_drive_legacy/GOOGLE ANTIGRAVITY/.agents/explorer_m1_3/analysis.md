# Architectural Analysis: Safety AST Guardrails & Test Infrastructure (Milestone 1)

## Executive Summary
This document defines the comprehensive architecture and implementation blueprint for **Milestone 1 AST Safety Guardrails & Test Infrastructure** for the Antigravity Daily Health Scanner & ML Optimization Daemon.

The core deliverables investigated and specified herein are:
1. `safety_guardrails.py`: A high-precision static AST analysis engine (`SafetyASTVisitor`, `scan_file`, `scan_directory`, `assert_safe_codebase`) that provides mathematical verification that destructive file deletions (`os.remove`, `shutil.rmtree`, `Path.unlink`), task terminations (`taskkill`, `os.kill`, `psutil.kill`), destructive SQL (`DROP TABLE`, `TRUNCATE`), and dynamic execution (`eval`, `exec`) are 100% absent from production code.
2. `conftest.py`: Cryptographic test isolation and verification fixtures, headlined by `FileSystemSnapshot` (SHA-256 pre/post state hash verification), `isolated_workspace` (temporary mock filesystem directory hierarchy), `mock_db` (in-memory/temp SQLite store with seeded historical lifelines), and `sample_anomalies`.
3. `tests/test_safety_ast.py`: A rigorous unit test suite enforcing Loud Assertions (zero shared state) to verify 0 violations on clean code and immediate, loud exceptions on synthetic destructive traps.

---

## 1. System Architecture & Requirements Mapping

### 1.1 Requirements Matrix
| Requirement Source | Target Component | Specification |
|---|---|---|
| `ORIGINAL_REQUEST.md` §Acceptance Criteria | `safety_guardrails.py` | Static AST check verifying destructive commands (`os.remove`, `shutil.rmtree`, `taskkill`) are entirely absent from automated execution paths. |
| `ORIGINAL_REQUEST.md` §R3 (HITL Data Loss Prevention) | `safety_guardrails.py`, `conftest.py` | 100% read-only analytical execution. Zero autonomous deletions or task kills. Cryptographic proof via `FileSystemSnapshot`. |
| `accidental-data-loss-prevention` Skill | `safety_guardrails.py` | Block raw SQL `DROP TABLE/VIEW/SCHEMA/DATABASE`, `TRUNCATE`, and OS file deletions. |
| `PROJECT.md` §Milestone 1 | `tests/test_safety_ast.py` | Complete AST test suite verifying static guardrails and failure traps. |
| `PROJECT.md` §Interface Contracts | `conftest.py` | Reusable fixtures for `isolated_workspace`, `mock_db`, `FileSystemSnapshot`, and `sample_anomalies`. |

---

## 2. Component Design: `safety_guardrails.py`

### 2.1 Prohibited Operation Taxonomy
The static analyzer classifies destructive violations into 4 distinct categories:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Safety Violation Rules                          │
├───────────────────┬────────────────────────────────────────────────────┤
│ Category          │ Prohibited Targets                                 │
├───────────────────┼────────────────────────────────────────────────────┤
│ FILE_DELETION     │ os.remove, os.unlink, os.rmdir, os.removedirs,      │
│                   │ shutil.rmtree, pathlib.Path.unlink, Path.rmdir     │
├───────────────────┼────────────────────────────────────────────────────┤
│ PROCESS_KILL      │ os.kill, os.killpg, psutil.Process.kill,           │
│                   │ psutil.Process.terminate, signal.SIGKILL,          │
│                   │ signal.SIGTERM, subprocess calling taskkill/pkill  │
├───────────────────┼────────────────────────────────────────────────────┤
│ SQL_DESTRUCTION   │ DROP TABLE, DROP DATABASE, DROP VIEW, DROP SCHEMA, │
│                   │ TRUNCATE TABLE, TRUNCATE, ALTER TABLE ... DROP     │
├───────────────────┼────────────────────────────────────────────────────┤
│ DYNAMIC_EXECUTION │ eval(), exec(), __import__(), globals() mutation   │
└───────────────────┴────────────────────────────────────────────────────┘
```

### 2.2 AST Visitor Architecture (`SafetyASTVisitor`)
The visitor extends `ast.NodeVisitor` and inspects:
1. `ast.Call`:
   - Inspects `node.func`:
     - **Direct Name Calls**: `eval()`, `exec()`, `kill()`, `remove()`, `rmtree()`, `unlink()`.
     - **Attribute Calls**:
       - `os.remove`, `os.unlink`, `os.rmdir`, `os.removedirs`, `os.kill`, `os.killpg`, `os.system`, `os.popen`
       - `shutil.rmtree`, `shutil.move`
       - `*.unlink()`, `*.rmdir()` (invoked on Path instances)
       - `*.kill()`, `*.terminate()` (invoked on Process instances)
       - `subprocess.run()`, `subprocess.Popen()`, `subprocess.call()`, `subprocess.check_call()`, `subprocess.check_output()`
   - Inspects Subprocess Arguments:
     - Scans `node.args` and `node.keywords` for command strings or list elements matching `taskkill`, `pkill`, `kill`, `del`, `rm`, `powershell Stop-Process`.
   - Inspects Database Execute Calls:
     - For `cursor.execute(...)`, `conn.execute(...)`, `db.execute(...)`, scans SQL query string arguments for destructive SQL keywords.
2. `ast.Import`:
   - Flags imports of dangerous or prohibited modules if forbidden, e.g., `import signal` (which has no legitimate read-only scanner purpose).
3. `ast.ImportFrom`:
   - Tracks imported names from modules:
     - `from os import remove, unlink, rmdir, removedirs, kill, killpg, system, popen`
     - `from shutil import rmtree`
     - `from signal import ...`
     - `from psutil import ...`
4. `ast.Constant` / `ast.Str`:
   - Scans string literals across all code files for unparameterized raw SQL destruction statements (`DROP TABLE`, `TRUNCATE TABLE`, `DROP DATABASE`).

### 2.3 False-Positive Prevention Mechanics
A critical requirement in AST analysis is preventing false positives on harmless standard library patterns:
- `list.remove(x)`: Differentiated from `os.remove` by verifying that the attribute target is not `os` and `remove` was not imported from `os`.
- `dict.pop(key)`: Allowed.
- `str.replace(...)`: Allowed.
- `SELECT / INSERT / UPDATE` SQL: Allowed.
- `sqlite3.connect()` / `conn.rollback()`: Allowed.

### 2.4 Data Models & Public API
```python
from dataclasses import dataclass
from typing import List, Optional, Union
from pathlib import Path
import ast
import re

class SafetyViolationError(Exception):
    """Raised when static AST safety guardrails detect prohibited operations."""
    pass

@dataclass(frozen=True)
class SafetyViolation:
    rule_id: str             # e.g., "RULE_FILE_DELETION", "RULE_PROCESS_KILL"
    violation_type: str      # e.g., "os.remove", "raw_sql_drop", "eval"
    file_path: str
    line_number: int
    col_offset: int
    node_content: str
    message: str

@dataclass
class SafetyAuditSummary:
    is_safe: bool
    total_files_scanned: int
    total_lines_scanned: int
    violations: List[SafetyViolation]

def scan_source(source_code: str, file_path: str = "<memory>") -> List[SafetyViolation]:
    """Parses and checks a single Python source string."""
    ...

def scan_file(file_path: Union[str, Path]) -> List[SafetyViolation]:
    """Parses and checks a single Python file on disk."""
    ...

def scan_directory(directory_path: Union[str, Path], exclude_patterns: Optional[List[str]] = None) -> SafetyAuditSummary:
    """Recursively scans all .py files in a target directory."""
    ...

def assert_safe_codebase(directory_path: Union[str, Path]) -> SafetyAuditSummary:
    """Scans directory and loudly raises SafetyViolationError if any violation exists."""
    ...
```

---

## 3. Component Design: `conftest.py`

### 3.1 `FileSystemSnapshot` Cryptographic Guardrail
To provide mathematical certainty of non-destructive behavior during live or mock test execution, `conftest.py` introduces `FileSystemSnapshot`:

```python
import hashlib
from pathlib import Path
from typing import Dict, Set, Tuple

class FileSystemSnapshot:
    def __init__(self, root_dir: Path, file_hashes: Dict[str, str]):
        self.root_dir = root_dir.resolve()
        self.file_hashes = file_hashes  # relative_path -> sha256_hex

    @classmethod
    def capture(cls, root_dir: Union[str, Path]) -> "FileSystemSnapshot":
        root = Path(root_dir).resolve()
        hashes: Dict[str, str] = {}
        for path in root.rglob("*"):
            if path.is_file():
                rel_path = path.relative_to(root).as_posix()
                hashes[rel_path] = cls._hash_file(path)
        return cls(root, hashes)

    @staticmethod
    def _hash_file(file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def diff(self, current_root: Optional[Union[str, Path]] = None) -> Tuple[Set[str], Set[str], Set[str]]:
        """Returns (deleted_files, added_files, modified_files)."""
        target_root = Path(current_root).resolve() if current_root else self.root_dir
        current_hashes: Dict[str, str] = {}
        for path in target_root.rglob("*"):
            if path.is_file():
                rel_path = path.relative_to(target_root).as_posix()
                current_hashes[rel_path] = self._hash_file(path)

        old_keys = set(self.file_hashes.keys())
        new_keys = set(current_hashes.keys())

        deleted = old_keys - new_keys
        added = new_keys - old_keys
        modified = {k for k in (old_keys & new_keys) if self.file_hashes[k] != current_hashes[k]}

        return deleted, added, modified

    def assert_untouched(self, allowed_new_files: Optional[Set[str]] = None) -> None:
        """Loudly asserts that zero files were deleted or modified."""
        deleted, added, modified = self.diff()
        unexpected_added = added - (allowed_new_files or set())

        errors = []
        if deleted:
            errors.append(f"UNAUTHORIZED DELETIONS ({len(deleted)} files): {sorted(deleted)}")
        if modified:
            errors.append(f"UNAUTHORIZED MODIFICATIONS ({len(modified)} files): {sorted(modified)}")
        if unexpected_added:
            errors.append(f"UNEXPECTED CREATIONS ({len(unexpected_added)} files): {sorted(unexpected_added)}")

        if errors:
            raise AssertionError(f"FileSystemSnapshot Violation!\n" + "\n".join(errors))
```

### 3.2 `isolated_workspace` Fixture
Creates a standard sandbox directory replicating the Antigravity structure in `tmp_path`:
- `.agents/rules/`
- `.agents/skills/`
- `sports_cards/`
- `content_creation/`
- `apps/`
- `travel_and_life/`
- Standard manifest files: `GEMINI.md`, `PROJECT.md`, `.env`.

### 3.3 `mock_db` Fixture
Initializes an isolated SQLite database using `database.init_db()` and `database.seed_historical_lifelines()`, verifying transaction safety and schema correctness.

### 3.4 `sample_anomalies` Fixture
Supplies 5 canonical `AnomalyRecord` instances:
1. `GHOST_DAEMONS`: Port 3000 socket collision (`WinError 10048`).
2. `CONTEXT_ROT`: `.agents/plan_20260820.md` (>24 hours old).
3. `ECOSYSTEM_POLLUTION`: `.agents/plugins/legacy_tool.disabled`.
4. `SECRET_ZERO`: `.env` with `API_KEY=your_token_here`.
5. `PROMPT_FATIGUE`: `GEMINI.md` with 142 lines (>100 line limit).

---

## 4. Component Design: `tests/test_safety_ast.py`

### 4.1 Test Structure & Cases
The unit test file contains 13 focused test cases:
1. `test_clean_codebase_zero_violations`: Scans all Python files in `cron/` to verify zero violations.
2. `test_detect_os_remove_and_unlink`: Traps `os.remove("foo.txt")`, `os.unlink("bar.txt")`, `os.rmdir("dir")`, `os.removedirs("dir/sub")`.
3. `test_detect_shutil_rmtree`: Traps `shutil.rmtree("path")`.
4. `test_detect_pathlib_unlink`: Traps `Path("foo.txt").unlink()` and `path_obj.rmdir()`.
5. `test_detect_from_imports`: Traps `from os import remove`, `from shutil import rmtree`, `from os import unlink`.
6. `test_detect_process_kill_os`: Traps `os.kill(pid, 9)` and `os.killpg(pgid, 15)`.
7. `test_detect_process_kill_psutil`: Traps `psutil.Process(pid).kill()` and `psutil.Process(pid).terminate()`.
8. `test_detect_subprocess_taskkill_and_pkill`: Traps `subprocess.run(["taskkill", "/F", "/PID", "123"])`, `subprocess.Popen(["pkill", "-f", "node"])`, `subprocess.call("kill -9 123", shell=True)`.
9. `test_detect_forbidden_signal_import`: Traps `import signal` and `from signal import SIGKILL`.
10. `test_detect_raw_sql_destruction`: Traps `cursor.execute("DROP TABLE anomalies")`, `conn.execute("TRUNCATE TABLE scan_sessions")`, `db.execute("DROP DATABASE telemetry")`, and multiline string constants containing destructive SQL.
11. `test_detect_eval_and_exec`: Traps `eval("code")`, `exec("code")`, `__import__("os")`.
12. `test_benign_code_allowed`: Verifies that safe constructs (`os.walk`, `os.path.exists`, `Path.read_text`, `list.remove`, `dict.pop`, `SELECT` queries, `dataclasses`) produce 0 violations.
13. `test_assert_safe_codebase_loud_exception`: Verifies that `assert_safe_codebase` raises `SafetyViolationError` with clear diagnostics when a violation is present.

---

## 5. Verification Plan & Test Execution Strategy
- Execution Command: `python -m pytest g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_safety_ast.py -v`
- Pass Condition: All 13 tests PASS with 0 failures and 0 warnings.

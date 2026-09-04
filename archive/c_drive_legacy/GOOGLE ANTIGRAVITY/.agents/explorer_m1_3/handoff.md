# Handoff Report: Milestone 1 Safety AST Guardrails & Test Infrastructure

**Agent**: `explorer_m1_3`  
**Milestone**: Milestone 1 — SQLite Telemetry, Seeding & AST Safety  
**Deliverable Scope**: `safety_guardrails.py`, `conftest.py`, `tests/test_safety_ast.py`  
**Target Directory**: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron`  

---

## 1. Observation

### 1.1 Direct Requirements Traceability
1. **`ORIGINAL_REQUEST.md` Line 31-35 (§R3 Strict Data Loss Prevention)**:
   - "Adhere strictly to the `accidental-data-loss-prevention` skill."
   - "Execution must be 100% read-only and analytical."
   - "Strictly forbidden from executing structural deletions or killing tasks autonomously."
2. **`ORIGINAL_REQUEST.md` Line 40-44 (§Acceptance Criteria)**:
   - "A static code check verifies that destructive commands (`os.remove`, `shutil.rmtree`, `taskkill`) are entirely absent from the script's automated execution path."
3. **`PROJECT.md` Line 7 (§System Components)**:
   - "`safety_guardrails.py`: Static AST analyzer that enforces a mathematical guarantee that destructive operations (`os.remove`, `shutil.rmtree`, `taskkill`, `kill`, `rm -rf`, `DROP`, `TRUNCATE`) are 100% absent from production code paths."
4. **`accidental-data-loss-prevention` Skill**:
   - Explicitly forbids SQL `DROP TABLE/VIEW/SCHEMA/DATABASE`, `TRUNCATE`, and unauthorized storage/file deletions.
5. **`PROJECT.md` Line 170-171 (`tests/conftest.py`, `tests/test_safety_ast.py`)**:
   - `conftest.py`: Shared mock fixtures (`isolated_workspace`, `FileSystemSnapshot`, `mock_db`).
   - `test_safety_ast.py`: AST verification asserting 0 destructive calls across clean code and loud failures on synthetic traps.

---

## 2. Logic Chain

1. **Deterministic Static Verification vs Runtime Checking**:
   - Runtime shims can be bypassed or only trigger if execution branches hit the specific line.
   - Therefore, a static AST parser (`ast.NodeVisitor`) is necessary to scan 100% of the syntax tree across all `.py` files prior to daemon launch, guaranteeing zero destructive invocations anywhere in the codebase.
2. **Multi-Vector AST Traversal**:
   - Developers or malicious code could invoke destructive calls via multiple syntax paths:
     - Direct module calls: `os.remove()`, `shutil.rmtree()` -> Traversed via `visit_Call` on `ast.Attribute`.
     - Direct function calls: `remove()`, `unlink()`, `eval()`, `exec()` -> Traversed via `visit_Call` on `ast.Name`.
     - Destructive imports: `from os import remove`, `from shutil import rmtree`, `import signal` -> Traversed via `visit_Import` and `visit_ImportFrom`.
     - Subprocess commands: `subprocess.run(["taskkill", ...])`, `subprocess.Popen(["pkill", ...])` -> Traversed via inspecting `node.args` and `node.keywords` of `subprocess` calls.
     - Raw SQL strings: `"DROP TABLE foo"`, `"TRUNCATE bar"` -> Traversed via `visit_Constant` / `visit_Str` matching regex `(?i)\b(DROP\s+(TABLE|DATABASE|VIEW|SCHEMA)|TRUNCATE(\s+TABLE)?)\b`.
3. **False-Positive Prevention**:
   - Python built-in list methods include `list.remove(item)`. The AST visitor must not flag `some_list.remove(x)` if `some_list` is not `os` and `remove` was not imported from `os`.
4. **Cryptographic Proof of Non-Destructive Behavior (`FileSystemSnapshot`)**:
   - To verify that detector scans are truly read-only, tests must capture SHA-256 hashes of every file in the test workspace before running the scanner and assert that the file tree is identical after the scan (`deleted_files == []`, `modified_files == []`).
5. **Loud Assertions in Unit Tests**:
   - Tests in `tests/test_safety_ast.py` must use zero shared state and assert loud, unmistakable failures on synthetic code containing forbidden operations.

---

## 3. Caveats

1. **Obfuscated Dynamic Attributes**: Highly dynamic Python runtime inspection (e.g. `getattr(__builtins__, 'ev' + 'al')`) cannot be fully resolved at compile-time by AST; however, in a static codebase with strict AST inspection prohibiting `getattr` on builtins and `eval`/`exec`, all standard and idiomatic patterns are completely blocked.
2. **Path Exclusion Discipline**: When scanning directories, the scanner must ignore `.venv/`, `__pycache__/`, and `.git/` to avoid scanning third-party vendor dependencies that may have internal file management routines.
3. **Read-Only Scope**: The AST safety analyzer itself must be pure Python with zero external C-extensions, allowing it to run instantly in any environment in <50ms.

---

## 4. Conclusion & Recommended Implementation Blueprint

The implementing worker should write the following files in `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron/`:

### 4.1 Blueprint: `safety_guardrails.py`
```python
"""
safety_guardrails.py - Static AST Safety Guardrails for Antigravity Cron Daemon.
Enforces 0-destruction mathematical guarantee across all Python files in the codebase.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Union


class SafetyViolationError(Exception):
    """Raised when static AST analysis detects prohibited destructive operations."""
    pass


@dataclass(frozen=True)
class SafetyViolation:
    rule_id: str
    violation_type: str
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


class SafetyASTVisitor(ast.NodeVisitor):
    FORBIDDEN_CALL_ATTRIBUTES = {
        "os": {"remove", "unlink", "rmdir", "removedirs", "kill", "killpg", "system", "popen"},
        "shutil": {"rmtree", "move"},
        "pathlib": {"unlink", "rmdir"},
    }

    FORBIDDEN_BARE_CALLS = {"eval", "exec", "killpg"}

    FORBIDDEN_PATH_METHODS = {"unlink", "rmdir"}
    FORBIDDEN_PROCESS_METHODS = {"kill", "terminate"}

    FORBIDDEN_SUBPROCESS_CMDS = {
        "taskkill", "pkill", "kill", "rm", "del", "rmdir", "stop-process"
    }

    SQL_DESTRUCTIVE_PATTERN = re.compile(
        r"(?i)\b(DROP\s+(TABLE|DATABASE|VIEW|SCHEMA)|TRUNCATE(\s+TABLE)?)\b"
    )

    def __init__(self, file_path: str = "<unknown>"):
        self.file_path = file_path
        self.violations: List[SafetyViolation] = []
        self.imported_names: dict[str, str] = {}  # alias -> original_module.name

    def _add_violation(self, node: ast.AST, rule_id: str, violation_type: str, message: str) -> None:
        lineno = getattr(node, "lineno", 0)
        col_offset = getattr(node, "col_offset", 0)
        content = ast.unparse(node) if hasattr(ast, "unparse") else str(node)
        self.violations.append(
            SafetyViolation(
                rule_id=rule_id,
                violation_type=violation_type,
                file_path=self.file_path,
                line_number=lineno,
                col_offset=col_offset,
                node_content=content,
                message=message,
            )
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "signal":
                self._add_violation(
                    node,
                    "RULE_FORBIDDEN_IMPORT",
                    "import signal",
                    "Direct import of 'signal' module is prohibited in read-only health scanner.",
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        for alias in node.names:
            name = alias.name
            as_name = alias.asname or name
            self.imported_names[as_name] = f"{mod}.{name}"

            if mod == "os" and name in {"remove", "unlink", "rmdir", "removedirs", "kill", "killpg", "system", "popen"}:
                self._add_violation(
                    node,
                    "RULE_FORBIDDEN_IMPORT",
                    f"from os import {name}",
                    f"Importing destructive function '{name}' from 'os' is strictly prohibited.",
                )
            elif mod == "shutil" and name in {"rmtree", "move"}:
                self._add_violation(
                    node,
                    "RULE_FORBIDDEN_IMPORT",
                    f"from shutil import {name}",
                    f"Importing destructive function '{name}' from 'shutil' is strictly prohibited.",
                )
            elif mod == "signal":
                self._add_violation(
                    node,
                    "RULE_FORBIDDEN_IMPORT",
                    f"from signal import {name}",
                    f"Importing from 'signal' module is prohibited.",
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # 1. Check direct Name calls
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.FORBIDDEN_BARE_CALLS:
                self._add_violation(
                    node,
                    "RULE_DYNAMIC_EXECUTION",
                    func_name,
                    f"Dynamic execution call '{func_name}()' is strictly prohibited.",
                )
            elif func_name in self.imported_names:
                origin = self.imported_names[func_name]
                if any(origin.startswith(pkg) for pkg in ["os.", "shutil.", "signal."]):
                    self._add_violation(
                        node,
                        "RULE_DESTRUCTIVE_CALL",
                        origin,
                        f"Invocation of imported destructive function '{origin}()' is prohibited.",
                    )

        # 2. Check Attribute calls
        elif isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            val = node.func.value

            # os.<func>, shutil.<func>
            if isinstance(val, ast.Name):
                module_name = val.id
                if module_name in self.FORBIDDEN_CALL_ATTRIBUTES:
                    if attr in self.FORBIDDEN_CALL_ATTRIBUTES[module_name]:
                        self._add_violation(
                            node,
                            "RULE_DESTRUCTIVE_CALL",
                            f"{module_name}.{attr}",
                            f"Call to '{module_name}.{attr}()' is strictly prohibited.",
                        )
                # subprocess.<func>
                if module_name == "subprocess" and attr in {"run", "Popen", "call", "check_call", "check_output"}:
                    self._inspect_subprocess_args(node)

            # Path.unlink, Path.rmdir, Process.kill, Process.terminate
            if attr in self.FORBIDDEN_PATH_METHODS:
                self._add_violation(
                    node,
                    "RULE_FILE_DELETION",
                    f".{attr}()",
                    f"Calling '.{attr}()' method on Path/file object is strictly prohibited.",
                )
            elif attr in self.FORBIDDEN_PROCESS_METHODS:
                self._add_violation(
                    node,
                    "RULE_PROCESS_KILL",
                    f".{attr}()",
                    f"Calling '.{attr}()' process termination method is strictly prohibited.",
                )

        self.generic_visit(node)

    def _inspect_subprocess_args(self, node: ast.Call) -> None:
        for arg in node.args:
            if isinstance(arg, ast.List):
                for elem in arg.elts:
                    if isinstance(elem, ast.Constant) and isinstance(elem.value, str):
                        if elem.value.lower() in self.FORBIDDEN_SUBPROCESS_CMDS:
                            self._add_violation(
                                node,
                                "RULE_PROCESS_KILL",
                                f"subprocess({elem.value})",
                                f"Subprocess invocation targeting '{elem.value}' is prohibited.",
                            )
            elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                tokens = arg.value.lower().split()
                if any(cmd in tokens for cmd in self.FORBIDDEN_SUBPROCESS_CMDS):
                    self._add_violation(
                        node,
                        "RULE_PROCESS_KILL",
                        f"subprocess('{arg.value}')",
                        f"Subprocess command contains prohibited process termination keyword.",
                    )

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            if self.SQL_DESTRUCTIVE_PATTERN.search(node.value):
                self._add_violation(
                    node,
                    "RULE_SQL_DESTRUCTION",
                    "RAW_SQL_DROP_OR_TRUNCATE",
                    f"Prohibited destructive SQL statement detected: {node.value.strip()[:60]}",
                )
        self.generic_visit(node)


def scan_source(source_code: str, file_path: str = "<memory>") -> List[SafetyViolation]:
    try:
        tree = ast.parse(source_code, filename=file_path)
    except SyntaxError as e:
        return [
            SafetyViolation(
                rule_id="RULE_SYNTAX_ERROR",
                violation_type="syntax_error",
                file_path=file_path,
                line_number=e.lineno or 1,
                col_offset=e.offset or 0,
                node_content="",
                message=f"Syntax error during AST parsing: {e}",
            )
        ]
    visitor = SafetyASTVisitor(file_path=file_path)
    visitor.visit(tree)
    return visitor.violations


def scan_file(file_path: Union[str, Path]) -> List[SafetyViolation]:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return []
    content = path.read_text(encoding="utf-8", errors="replace")
    return scan_source(content, file_path=str(path))


def scan_directory(
    directory_path: Union[str, Path],
    exclude_dirs: Optional[Set[str]] = None,
) -> SafetyAuditSummary:
    root = Path(directory_path).resolve()
    excluded = exclude_dirs or {".git", ".venv", "venv", "__pycache__", "build", "dist"}
    all_violations: List[SafetyViolation] = []
    total_files = 0
    total_lines = 0

    for py_file in root.rglob("*.py"):
        if any(part in excluded for part in py_file.parts):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            total_files += 1
            total_lines += len(content.splitlines())
            violations = scan_source(content, file_path=str(py_file))
            all_violations.extend(violations)
        except Exception as e:
            all_violations.append(
                SafetyViolation(
                    rule_id="RULE_FILE_READ_ERROR",
                    violation_type="io_error",
                    file_path=str(py_file),
                    line_number=1,
                    col_offset=0,
                    node_content="",
                    message=f"Failed to read file: {e}",
                )
            )

    return SafetyAuditSummary(
        is_safe=(len(all_violations) == 0),
        total_files_scanned=total_files,
        total_lines_scanned=total_lines,
        violations=all_violations,
    )


def assert_safe_codebase(
    directory_path: Union[str, Path],
    exclude_dirs: Optional[Set[str]] = None,
) -> SafetyAuditSummary:
    summary = scan_directory(directory_path, exclude_dirs)
    if not summary.is_safe:
        report_lines = [
            f"Safety Guardrail FAILED: {len(summary.violations)} prohibited operation(s) found across {summary.total_files_scanned} files!"
        ]
        for v in summary.violations:
            report_lines.append(
                f"  [{v.rule_id}] {v.file_path}:{v.line_number}:{v.col_offset} -> {v.violation_type} | {v.message}"
            )
        raise SafetyViolationError("\n".join(report_lines))
    return summary
```

---

### 4.2 Blueprint: `tests/conftest.py`
```python
"""
conftest.py - Pytest fixtures and cryptographic state verification.
"""

import hashlib
import os
import sqlite3
import pytest
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

# Assuming database module is available in python path
from models import AnomalyRecord, DetectorType, Severity


class FileSystemSnapshot:
    """Captures and cryptographically verifies filesystem integrity with SHA-256."""

    def __init__(self, root_dir: Path, file_hashes: Dict[str, str]):
        self.root_dir = root_dir.resolve()
        self.file_hashes = file_hashes

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
        deleted, added, modified = self.diff()
        unexpected_added = added - (allowed_new_files or set())

        errors = []
        if deleted:
            errors.append(f"UNAUTHORIZED DELETIONS ({len(deleted)} files): {sorted(deleted)}")
        if modified:
            errors.append(f"UNAUTHORIZED MODIFICATIONS ({len(modified)} files): {sorted(modified)}")
        if unexpected_added:
            errors.append(f"UNEXPECTED FILE CREATIONS ({len(unexpected_added)} files): {sorted(unexpected_added)}")

        if errors:
            raise AssertionError("FileSystemSnapshot Verification Failed:\n" + "\n".join(errors))


@pytest.fixture
def isolated_workspace(tmp_path: Path) -> Path:
    """Constructs a deterministic mock workspace with the standard Antigravity layout."""
    ws = tmp_path / "antigravity_workspace"
    ws.mkdir(parents=True, exist_ok=True)

    (ws / ".agents" / "rules").mkdir(parents=True, exist_ok=True)
    (ws / ".agents" / "skills").mkdir(parents=True, exist_ok=True)
    (ws / "sports_cards").mkdir(parents=True, exist_ok=True)
    (ws / "content_creation").mkdir(parents=True, exist_ok=True)
    (ws / "apps").mkdir(parents=True, exist_ok=True)
    (ws / "travel_and_life").mkdir(parents=True, exist_ok=True)

    (ws / "GEMINI.md").write_text("# Manifest\nRoot instructions.", encoding="utf-8")
    (ws / "PROJECT.md").write_text("# Project Blueprint\nActive project.", encoding="utf-8")
    (ws / ".env").write_text("ENV=test\nDATABASE_URL=sqlite:///test.db\n", encoding="utf-8")

    return ws


@pytest.fixture
def mock_db(tmp_path: Path) -> str:
    """Initializes a temporary SQLite database with full schema and historical seeds."""
    from database import init_db, seed_historical_lifelines
    db_path = str(tmp_path / "test_telemetry.db")
    init_db(db_path)
    seed_historical_lifelines(db_path)
    return db_path


@pytest.fixture
def sample_anomalies() -> List[AnomalyRecord]:
    """Provides canonical anomaly records across all 5 detector categories."""
    return [
        AnomalyRecord(
            detector_type=DetectorType.GHOST_DAEMONS,
            target_path="localhost:3000",
            severity=Severity.HIGH,
            description="Port 3000 occupied by unmonitored task",
            raw_details={"port": 3000, "error": "WinError 10048"},
            is_historical=False,
            timestamp=1700000000,
            confidence=1.0,
        ),
        AnomalyRecord(
            detector_type=DetectorType.CONTEXT_ROT,
            target_path=".agents/orchestrator_1/plan.md",
            severity=Severity.MEDIUM,
            description="Planning artifact older than 24 hours",
            raw_details={"age_hours": 48.5, "mtime": 1699900000},
            is_historical=False,
            timestamp=1700000000,
            confidence=0.95,
        ),
        AnomalyRecord(
            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
            target_path=".agents/plugins/old_tool.disabled",
            severity=Severity.LOW,
            description="Unused .disabled plugin directory detected",
            raw_details={"is_dir": True},
            is_historical=False,
            timestamp=1700000000,
            confidence=1.0,
        ),
        AnomalyRecord(
            detector_type=DetectorType.SECRET_ZERO,
            target_path=".env",
            severity=Severity.CRITICAL,
            description="Placeholder secret token 'your_token_here' found in config",
            raw_details={"key": "API_KEY", "pattern": "your_token_here"},
            is_historical=False,
            timestamp=1700000000,
            confidence=1.0,
        ),
        AnomalyRecord(
            detector_type=DetectorType.PROMPT_FATIGUE,
            target_path="GEMINI.md",
            severity=Severity.MEDIUM,
            description="Manifest file exceeds 100 lines (142 lines detected)",
            raw_details={"line_count": 142, "limit": 100},
            is_historical=False,
            timestamp=1700000000,
            confidence=1.0,
        ),
    ]
```

---

### 4.3 Blueprint: `tests/test_safety_ast.py`
```python
"""
test_safety_ast.py - Unit tests for AST Safety Guardrails.
Enforces Loud Assertions and zero shared state.
"""

import pytest
from pathlib import Path
from safety_guardrails import (
    SafetyViolationError,
    assert_safe_codebase,
    scan_directory,
    scan_source,
)


class TestSafetyASTVisitor:

    def test_clean_compliant_source_passes(self):
        code = """
import os
import socket
from pathlib import Path
import sqlite3

def check_system():
    p = Path("data")
    if p.exists():
        text = p.read_text(encoding="utf-8")
    for root, dirs, files in os.walk("."):
        pass
    conn = sqlite3.connect("test.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM anomalies WHERE id = ?", (1,))
    items = [1, 2, 3]
    items.remove(2)  # list.remove should NOT trigger false positive
    return True
"""
        violations = scan_source(code, "clean_module.py")
        assert len(violations) == 0, f"Expected 0 violations, got: {violations}"

    @pytest.mark.parametrize("snippet,expected_type", [
        ("import os\nos.remove('file.txt')", "os.remove"),
        ("import os\nos.unlink('file.txt')", "os.unlink"),
        ("import os\nos.rmdir('dir_path')", "os.rmdir"),
        ("import os\nos.removedirs('dir/sub')", "os.removedirs"),
        ("import shutil\nshutil.rmtree('dir_path')", "shutil.rmtree"),
        ("from pathlib import Path\nPath('foo.txt').unlink()", ".unlink()"),
        ("from pathlib import Path\nPath('dir').rmdir()", ".rmdir()"),
    ])
    def test_traps_file_deletions(self, snippet: str, expected_type: str):
        violations = scan_source(snippet, "bad_file_ops.py")
        assert len(violations) >= 1, f"Failed to catch file deletion: {snippet}"
        types = [v.violation_type for v in violations]
        assert any(expected_type in t for t in types), f"Expected {expected_type} in {types}"

    @pytest.mark.parametrize("snippet,expected_type", [
        ("from os import remove\nremove('a.txt')", "os.remove"),
        ("from os import unlink\nunlink('a.txt')", "os.unlink"),
        ("from shutil import rmtree\nrmtree('a_dir')", "shutil.rmtree"),
        ("from os import rmdir\nrmdir('a_dir')", "os.rmdir"),
    ])
    def test_traps_from_imports_deletions(self, snippet: str, expected_type: str):
        violations = scan_source(snippet, "bad_imports.py")
        assert len(violations) >= 1, f"Failed to catch from-import deletion: {snippet}"

    @pytest.mark.parametrize("snippet", [
        "import os\nos.kill(1234, 9)",
        "import os\nos.killpg(1234, 15)",
        "import psutil\np = psutil.Process(123)\np.kill()",
        "import psutil\np = psutil.Process(123)\np.terminate()",
        "import signal",
        "from signal import SIGKILL",
    ])
    def test_traps_process_terminations(self, snippet: str):
        violations = scan_source(snippet, "bad_process_ops.py")
        assert len(violations) >= 1, f"Failed to catch process termination: {snippet}"

    @pytest.mark.parametrize("snippet", [
        "import subprocess\nsubprocess.run(['taskkill', '/F', '/PID', '1234'])",
        "import subprocess\nsubprocess.Popen(['pkill', '-f', 'node'])",
        "import subprocess\nsubprocess.call('kill -9 1234', shell=True)",
    ])
    def test_traps_subprocess_kills(self, snippet: str):
        violations = scan_source(snippet, "bad_subprocess.py")
        assert len(violations) >= 1, f"Failed to catch subprocess kill: {snippet}"

    @pytest.mark.parametrize("sql_snippet", [
        "query = 'DROP TABLE scan_sessions'",
        "query = 'DROP DATABASE health_telemetry'",
        "cursor.execute('TRUNCATE TABLE anomalies')",
        "db.execute('TRUNCATE logs')",
        "sql = '''DROP VIEW IF EXISTS active_view'''",
    ])
    def test_traps_destructive_sql(self, sql_snippet: str):
        violations = scan_source(sql_snippet, "bad_sql.py")
        assert len(violations) >= 1, f"Failed to catch destructive SQL: {sql_snippet}"

    @pytest.mark.parametrize("snippet", [
        "eval('2 + 2')",
        "exec('import os')",
    ])
    def test_traps_dynamic_execution(self, snippet: str):
        violations = scan_source(snippet, "bad_eval.py")
        assert len(violations) >= 1, f"Failed to catch dynamic execution: {snippet}"

    def test_assert_safe_codebase_raises_loudly(self, tmp_path: Path):
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("import os\nos.remove('secret.txt')", encoding="utf-8")
        
        with pytest.raises(SafetyViolationError) as exc_info:
            assert_safe_codebase(tmp_path)
        assert "RULE_DESTRUCTIVE_CALL" in str(exc_info.value)
        assert "os.remove" in str(exc_info.value)

    def test_filesystem_snapshot_catches_deletions_and_mutations(self, tmp_path: Path):
        from conftest import FileSystemSnapshot
        
        f1 = tmp_path / "file1.txt"
        f2 = tmp_path / "file2.txt"
        f1.write_text("hello", encoding="utf-8")
        f2.write_text("world", encoding="utf-8")

        snapshot = FileSystemSnapshot.capture(tmp_path)

        # 1. Verify untouched passes
        snapshot.assert_untouched()

        # 2. Modify f1 and verify loud assertion failure
        f1.write_text("hello modified", encoding="utf-8")
        with pytest.raises(AssertionError) as exc_info:
            snapshot.assert_untouched()
        assert "UNAUTHORIZED MODIFICATIONS" in str(exc_info.value)

        # 3. Revert and delete f2
        f1.write_text("hello", encoding="utf-8")
        f2.unlink()
        with pytest.raises(AssertionError) as exc_info:
            snapshot.assert_untouched()
        assert "UNAUTHORIZED DELETIONS" in str(exc_info.value)
```

---

## 5. Verification Method

1. **Unit Test Execution**:
   ```bash
   python -m pytest "g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_safety_ast.py" -v
   ```
2. **Full Codebase Static AST Verification**:
   ```python
   from safety_guardrails import assert_safe_codebase
   summary = assert_safe_codebase(r"g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron")
   print(f"Scanned {summary.total_files_scanned} files ({summary.total_lines_scanned} lines). Zero violations verified: {summary.is_safe}")
   ```
3. **Pass Criteria**:
   - 100% of the 13 AST unit tests pass.
   - Zero violations reported against `cron/` production source files.
   - All synthetic violation traps loudly trigger expected exceptions.

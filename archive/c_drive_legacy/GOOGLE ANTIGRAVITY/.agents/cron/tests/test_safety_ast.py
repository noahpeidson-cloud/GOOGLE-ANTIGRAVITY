"""Unit tests for AST static safety guardrails and codebase assertion."""

import os
from pathlib import Path
import pytest

from safety_guardrails import (
    SafetyViolationError,
    assert_safe_codebase,
    scan_code_for_safety,
)


def test_ast_detects_os_remove() -> None:
    """1. Test that os.remove calls are statically detected."""
    code = """
import os
def delete_file(path):
    os.remove(path)
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("os.remove" in v for v in violations)


def test_ast_detects_os_unlink() -> None:
    """2. Test that os.unlink calls are statically detected."""
    code = """
import os
def purge_link(path):
    os.unlink(path)
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("os.unlink" in v for v in violations)


def test_ast_detects_os_rmdir() -> None:
    """3. Test that os.rmdir calls are statically detected."""
    code = """
import os
def cleanup_dir(d):
    os.rmdir(d)
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("os.rmdir" in v for v in violations)


def test_ast_detects_shutil_rmtree() -> None:
    """4. Test that shutil.rmtree calls are statically detected."""
    code = """
import shutil
def purge_tree(folder):
    shutil.rmtree(folder)
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("shutil.rmtree" in v for v in violations)


def test_ast_detects_os_kill() -> None:
    """5. Test that os.kill calls are statically detected."""
    code = """
import os, signal
def kill_process(pid):
    os.kill(pid, signal.SIGTERM)
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("os.kill" in v for v in violations)


def test_ast_detects_subprocess_taskkill() -> None:
    """6. Test that subprocess taskkill invocations are statically detected."""
    code = """
import subprocess
def terminate_task(pid):
    subprocess.run(["taskkill", "/F", "/PID", str(pid)])
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("taskkill" in v for v in violations)


def test_ast_detects_subprocess_pkill() -> None:
    """7. Test that subprocess pkill invocations are statically detected."""
    code = """
import subprocess
def kill_daemon(name):
    subprocess.Popen(["pkill", "-f", name])
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("pkill" in v for v in violations)


def test_ast_detects_eval() -> None:
    """8. Test that eval invocations are statically detected."""
    code = """
def compute_expression(expr):
    return eval(expr)
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("eval" in v for v in violations)


def test_ast_detects_exec() -> None:
    """9. Test that exec invocations are statically detected."""
    code = """
def run_dynamic(code_str):
    exec(code_str)
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("exec" in v for v in violations)


def test_ast_detects_drop_table_sql() -> None:
    """10. Test that DROP TABLE SQL executions are statically detected."""
    code = """
import sqlite3
def drop_telemetry(conn):
    cursor = conn.cursor()
    cursor.execute("DROP TABLE anomalies;")
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("DROP TABLE" in v for v in violations)


def test_ast_detects_truncate_sql() -> None:
    """11. Test that TRUNCATE SQL executions are statically detected."""
    code = """
def reset_sessions(conn):
    conn.execute("TRUNCATE TABLE scan_sessions;")
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("TRUNCATE" in v for v in violations)


def test_ast_detects_module_alias_os_remove() -> None:
    """12. Test that aliased imports like 'import os as my_os' are tracked and flagged."""
    code = """
import os as my_os
def delete_file(path):
    my_os.remove(path)
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("os.remove" in v for v in violations)


def test_ast_detects_function_alias_from_os_remove() -> None:
    """13. Test that imported function aliases like 'from os import remove as rm' are flagged."""
    code = """
from os import remove as rm
def delete_file(path):
    rm(path)
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 1
    assert any("os.remove" in v for v in violations)


def test_ast_detects_pathlib_unlink_and_rmdir() -> None:
    """14. Test that .unlink() and .rmdir() method calls on Path objects are flagged."""
    code = """
from pathlib import Path
def purge_path(p: Path):
    p.unlink()
    p.rmdir()
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 2
    assert any(".unlink()" in v for v in violations)
    assert any(".rmdir()" in v for v in violations)


def test_ast_detects_os_additional_destructive_ops() -> None:
    """15. Test that os.removedirs, os.truncate, os.ftruncate, os.popen, os.spawn* are flagged."""
    code = """
import os
def dangerous_ops():
    os.removedirs("/tmp/test")
    os.truncate("file.txt", 0)
    os.ftruncate(1, 0)
    os.popen("taskkill /F /PID 123")
    os.spawnl(os.P_WAIT, "/bin/sh")
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 5
    assert any("os.removedirs" in v for v in violations)
    assert any("os.truncate" in v for v in violations)
    assert any("os.ftruncate" in v for v in violations)
    assert any("os.popen" in v for v in violations)
    assert any("os.spawnl" in v for v in violations)


def test_ast_detects_importlib_and_dunder_import() -> None:
    """16. Test that __import__ and importlib.import_module are flagged."""
    code = """
import importlib
def sneaky_imports():
    m1 = __import__("os")
    m2 = importlib.import_module("shutil")
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 2
    assert any("__import__" in v for v in violations)
    assert any("import_module" in v for v in violations)


def test_ast_detects_getattr_destructive_access() -> None:
    """17. Test that getattr(..., "remove") or getattr(..., "unlink") are flagged."""
    code = """
import os
def get_dangerous(mod):
    fn = getattr(mod, "remove")
    fn2 = getattr(mod, "rmtree")
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 2
    assert any("remove" in v for v in violations)
    assert any("rmtree" in v for v in violations)


def test_ast_detects_keyword_arguments_in_subprocess_and_sql() -> None:
    """18. Test that keyword arguments like args=... and sql=... are inspected."""
    code = """
import subprocess
import sqlite3

def run_kw(conn):
    subprocess.run(args=["taskkill", "/F", "/PID", "999"])
    conn.execute(sql="DROP TABLE audit_log;")
"""
    violations = scan_code_for_safety(code)
    assert len(violations) >= 2
    assert any("taskkill" in v for v in violations)
    assert any("DROP TABLE" in v for v in violations)


def test_ast_allows_sql_string_literals_without_false_positives() -> None:
    """19. Test that SELECT queries containing 'TRUNCATE' or 'DROP TABLE' in string literals are not falsely flagged."""
    code = """
import sqlite3

def query_audit_logs(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT session_id, message FROM logs WHERE action = 'TRUNCATE' AND details LIKE '%DROP TABLE%'")
    rows = cursor.fetchall()
    return rows
"""
    violations = scan_code_for_safety(code)
    assert len(violations) == 0, f"Expected 0 violations on safe SQL literal query, found: {violations}"


def test_ast_allows_user_defined_functions_named_remove() -> None:
    """20. Test that user-defined helper functions named remove or unlink are not falsely flagged."""
    code = """
def remove(item, item_list):
    return [x for x in item_list if x != item]

def unlink(node):
    return node.data

def safe_workflow():
    data = [1, 2, 3]
    filtered = remove(2, data)
    return filtered
"""
    violations = scan_code_for_safety(code)
    assert len(violations) == 0, f"Expected 0 violations on user-defined functions, found: {violations}"


def test_ast_allows_safe_operations() -> None:
    """21. Test that legitimate read-only and constructive operations produce zero violations."""
    code = """
import os
import json
import sqlite3
import math

def read_telemetry(db_path, config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT session_id, duration_ms FROM scan_sessions WHERE duration_ms > ?", (10.0,))
    rows = cursor.fetchall()
    conn.close()
    
    total_sqrt = math.sqrt(len(rows))
    return total_sqrt, data
"""
    violations = scan_code_for_safety(code)
    assert len(violations) == 0, f"Expected 0 violations on safe code, found: {violations}"


def test_assert_safe_codebase_on_clean_dir() -> None:
    """22. Test assert_safe_codebase passes cleanly on the .agents/cron codebase."""
    cron_dir = Path(__file__).resolve().parent.parent
    assert_safe_codebase(
        target_dir=str(cron_dir),
        exclude_dirs=["tests", "__pycache__", ".pytest_cache"],
    )


def test_assert_safe_codebase_fails_on_dirty_file(tmp_path: Path) -> None:
    """23. Extra Loud Assertion: Verify assert_safe_codebase raises SafetyViolationError when a dirty file exists."""
    dirty_file = tmp_path / "unsafe_script.py"
    dirty_file.write_text("import shutil\nshutil.rmtree('/tmp/dir')", encoding="utf-8")

    with pytest.raises(SafetyViolationError, match="Static AST Safety check failed"):
        assert_safe_codebase(str(tmp_path))


def test_file_system_snapshot_untouched(tmp_path: Path) -> None:
    """24. Extra Loud Assertion: Verify FileSystemSnapshot passes when files remain untouched."""
    try:
        from conftest import FileSystemSnapshot
    except ImportError:
        try:
            from .conftest import FileSystemSnapshot
        except ImportError:
            import importlib.util
            conftest_path = Path(__file__).parent / "conftest.py"
            spec = importlib.util.spec_from_file_location("conftest_module", conftest_path)
            conftest_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(conftest_module)
            FileSystemSnapshot = conftest_module.FileSystemSnapshot

    f1 = tmp_path / "file1.txt"
    f1.write_text("hello world", encoding="utf-8")
    sub = tmp_path / "subdir"
    sub.mkdir()
    f2 = sub / "file2.txt"
    f2.write_text("immutable content", encoding="utf-8")

    snapshot = FileSystemSnapshot(str(tmp_path))
    snapshot.assert_untouched()


def test_file_system_snapshot_detects_mutation(tmp_path: Path) -> None:
    """25. Extra Loud Assertion: Verify FileSystemSnapshot fails loudly if files are modified, added, or deleted."""
    try:
        from conftest import FileSystemSnapshot
    except ImportError:
        try:
            from .conftest import FileSystemSnapshot
        except ImportError:
            import importlib.util
            conftest_path = Path(__file__).parent / "conftest.py"
            spec = importlib.util.spec_from_file_location("conftest_module", conftest_path)
            conftest_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(conftest_module)
            FileSystemSnapshot = conftest_module.FileSystemSnapshot

    f1 = tmp_path / "file1.txt"
    f1.write_text("original content", encoding="utf-8")

    snapshot = FileSystemSnapshot(str(tmp_path))

    # Mutate file
    f1.write_text("tampered content", encoding="utf-8")
    with pytest.raises(AssertionError, match="FileSystem modification violation"):
        snapshot.assert_untouched()

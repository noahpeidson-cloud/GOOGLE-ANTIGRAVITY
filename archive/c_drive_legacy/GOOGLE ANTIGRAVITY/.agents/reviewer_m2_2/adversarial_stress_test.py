"""Adversarial stress test suite for AST static safety guardrails."""

import sys
from pathlib import Path
import pytest

cron_dir = Path(__file__).resolve().parent.parent / "cron"
if str(cron_dir) not in sys.path:
    sys.path.insert(0, str(cron_dir))

from safety_guardrails import (
    SafetyViolationError,
    assert_safe_codebase,
    scan_code_for_safety,
)


def test_adversarial_aliasing_variations():
    """Stress test aliasing combinations."""
    cases = [
        ("import os as my_custom_os; my_custom_os.remove('foo')", "os.remove"),
        ("import os as o; o.unlink('foo')", "os.unlink"),
        ("import shutil as s; s.rmtree('foo')", "shutil.rmtree"),
        ("from os import remove as delete_me; delete_me('foo')", "os.remove"),
        ("from os import unlink as unl; unl('foo')", "os.unlink"),
        ("from shutil import rmtree as nukedir; nukedir('foo')", "shutil.rmtree"),
        ("from signal import pthread_kill as pkill_fn; pkill_fn(1, 2)", "signal.pthread_kill"),
    ]
    for code, expected_match in cases:
        violations = scan_code_for_safety(code)
        assert len(violations) >= 1, f"Failed to detect: {code}"
        assert any(expected_match in v for v in violations), f"Expected {expected_match} in {violations}"


def test_adversarial_pathlib_variations():
    """Stress test Path.unlink and Path.rmdir across various AST patterns."""
    cases = [
        "from pathlib import Path; p = Path('foo'); p.unlink()",
        "import pathlib; pathlib.Path('foo').unlink()",
        "Path('foo').resolve().parent.unlink()",
        "def cleanup(target_path): target_path.rmdir()",
        "x.unlink(missing_ok=True)",
    ]
    for code in cases:
        violations = scan_code_for_safety(code)
        assert len(violations) >= 1, f"Failed to detect Path destruction in: {code}"


def test_adversarial_subprocess_variations():
    """Stress test subprocess commands with various argument structures."""
    cases = [
        "import subprocess; subprocess.run(['taskkill', '/F', '/PID', '1234'])",
        "import subprocess; subprocess.Popen(['pkill', '-f', 'node'])",
        "import subprocess; subprocess.call('kill -9 123', shell=True)",
        "import subprocess; subprocess.check_output(['rm', '-rf', '/tmp/foo'])",
        "import subprocess; subprocess.run(args=['taskkill', '/PID', '10'])",
        "import subprocess; subprocess.run(command=['rm', '-rf', 'dir'])",
        "import subprocess; subprocess.run(cmd='del /f /q C:\\temp', shell=True)",
        "import os; os.system('taskkill /f /im node.exe')",
        "import os; os.system('rmdir /s /q testdir')",
    ]
    for code in cases:
        violations = scan_code_for_safety(code)
        assert len(violations) >= 1, f"Failed to detect destructive command in: {code}"


def test_adversarial_sql_variations():
    """Stress test SQL parsing with case insensitivity, whitespace, and literal stripping."""
    dangerous_sql = [
        "conn.execute('DROP TABLE anomalies')",
        "conn.execute('drop table if exists telemetry;')",
        "conn.execute('  DROP   TABLE   users  ')",
        "conn.execute('''DROP\nTABLE\nlogs;''')",
        "conn.execute('DROP DATABASE analytics')",
        "conn.execute('DROP SCHEMA public')",
        "conn.execute('DROP VIEW active_view')",
        "conn.execute('TRUNCATE TABLE sessions')",
        "conn.execute('truncate sessions')",
        "conn.execute(sql='DROP TABLE temp')",
        "cursor.executemany(operation='DROP TABLE foo', seq_of_params=[])",
        "cursor.executescript('DROP TABLE bar;')",
    ]
    for code in dangerous_sql:
        violations = scan_code_for_safety(code)
        assert len(violations) >= 1, f"Failed to detect dangerous SQL in: {code}"

    safe_sql = [
        "conn.execute('SELECT * FROM logs WHERE query = \"DROP TABLE\";')",
        "conn.execute(\"INSERT INTO audit VALUES ('TRUNCATE TABLE users');\")",
        "conn.execute('SELECT col1 FROM t WHERE note LIKE \"%DROP VIEW%\";')",
        "conn.execute('SELECT count(*) FROM dropped_records;')",
        "conn.execute('SELECT * FROM table_truncates;')",
    ]
    for code in safe_sql:
        violations = scan_code_for_safety(code)
        assert len(violations) == 0, f"False positive on safe SQL: {code} -> {violations}"


def test_adversarial_evasion_attempts():
    """Stress test evasion techniques like getattr, dynamic imports, eval, exec."""
    evasions = [
        ("eval('os.remove(\"x\")')", "eval"),
        ("exec('import shutil; shutil.rmtree(\"x\")')", "exec"),
        ("__import__('os').remove('x')", "__import__"),
        ("import importlib; m = importlib.import_module('os')", "importlib.import_module"),
        ("getattr(os, 'remove')('x')", "getattr"),
        ("getattr(shutil, 'rmtree')('x')", "getattr"),
    ]
    for code, expected_tag in evasions:
        violations = scan_code_for_safety(code)
        assert len(violations) >= 1, f"Failed to catch evasion: {code}"


def test_adversarial_user_defined_helpers_are_safe():
    """Verify that safe user functions and methods don't cause false positives."""
    safe_code = """
class DataPipeline:
    def execute(self, query):
        return query.upper()

    def remove_item(self, lst, item):
        return [x for x in lst if x != item]

def process():
    p = DataPipeline()
    res = p.execute("SELECT 1 FROM dual")
    cleaned = p.remove_item([1, 2, 3], 2)
    return res, cleaned
"""
    violations = scan_code_for_safety(safe_code)
    assert len(violations) == 0, f"False positive on safe user code: {violations}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

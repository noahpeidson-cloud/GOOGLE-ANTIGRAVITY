"""Adversarial stress test suite for Milestone 1 components.
Run by reviewer_m1_2 to evaluate robustness, error handling, edge cases, and AST visitor.
"""

import ast
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

# Add cron dir to sys.path
CRON_DIR = Path(__file__).resolve().parent.parent / "cron"
sys.path.insert(0, str(CRON_DIR))

from database import (
    get_anomalies_for_session,
    get_db_connection,
    get_historical_drift,
    get_historical_lifelines,
    get_session,
    get_textual_gradients_for_session,
    init_db,
    log_scan_session,
    seed_historical_lifelines,
)
from models import AnomalyRecord, DetectorType, OptimizationReport, RedTeamAuditResult, RedTeamVerdict, Severity
from safety_guardrails import (
    SafetyASTVisitor,
    SafetyViolationError,
    assert_safe_codebase,
    scan_code_for_safety,
)

def test_foreign_key_enforcement():
    print("[TEST] Foreign Key Enforcement...")
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "fk.db")
        init_db(db)
        conn = get_db_connection(db)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO anomalies (session_id, detector_type, target_path, severity, description, raw_details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("nonexistent_session", "SECRET_ZERO", "dummy", "LOW", "test", "{}", 123456),
                )
            assert False, "Failed: FK violation did not raise IntegrityError"
        except sqlite3.IntegrityError:
            print("  -> Passed: FK constraint prevented orphaned anomaly insertion")
        finally:
            conn.close()

def test_ast_safety_variations():
    print("[TEST] AST Safety Guardrails Edge Cases...")
    
    # 1. Alias import os.remove as my_remove
    code_alias = """
from os import remove as my_remove
def test():
    my_remove("foo.txt")
"""
    # Let's see if this is detected
    v_alias = scan_code_for_safety(code_alias)
    print(f"  -> Alias 'from os import remove as my_remove': {len(v_alias)} violations: {v_alias}")

    # 2. Path.unlink
    code_pathlib = """
from pathlib import Path
def test():
    Path("foo.txt").unlink()
"""
    v_pathlib = scan_code_for_safety(code_pathlib)
    print(f"  -> Path('foo').unlink(): {len(v_pathlib)} violations: {v_pathlib}")

    # 3. os.system with taskkill
    code_ossystem = """
import os
def test():
    os.system("taskkill /F /IM node.exe")
"""
    v_ossystem = scan_code_for_safety(code_ossystem)
    print(f"  -> os.system('taskkill ...'): {len(v_ossystem)} violations: {v_ossystem}")
    assert len(v_ossystem) >= 1, "Failed to detect os.system taskkill"

    # 4. Multiline DROP TABLE
    code_sql = """
def test(conn):
    conn.execute('''
        DROP
        TABLE
        sessions
    ''')
"""
    v_sql = scan_code_for_safety(code_sql)
    print(f"  -> Multiline DROP TABLE: {len(v_sql)} violations: {v_sql}")

    # 5. String concatenation / f-string SQL
    code_fstr_sql = """
def test(conn, tbl):
    conn.execute(f"DROP TABLE {tbl}")
"""
    v_fstr = scan_code_for_safety(code_fstr_sql)
    print(f"  -> f-string DROP TABLE: {len(v_fstr)} violations: {v_fstr}")

def test_json_deserialization_resilience():
    print("[TEST] JSON Deserialization Resilience in database.py...")
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "corrupt_raw.db")
        init_db(db)
        conn = get_db_connection(db)
        with conn:
            conn.execute("INSERT INTO scan_sessions (session_id, timestamp, duration_ms, total_anomalies) VALUES ('s1', 100, 1.0, 1)")
            # Insert invalid JSON into raw_details
            conn.execute("INSERT INTO anomalies (session_id, detector_type, target_path, severity, description, raw_details, timestamp) VALUES ('s1', 'SECRET_ZERO', 'p', 'LOW', 'd', 'NOT_VALID_JSON{', 100)")
        conn.close()

        records = get_anomalies_for_session("s1", db)
        assert len(records) == 1
        assert records[0].raw_details == {"raw": "NOT_VALID_JSON{"}, f"Unexpected fallback raw_details: {records[0].raw_details}"
        print("  -> Passed: Invalid JSON in raw_details handled gracefully with fallback dictionary")

def test_huge_payload_and_special_chars():
    print("[TEST] Huge Payloads and Special Characters...")
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "special.db")
        init_db(db)
        
        # Test with unicode, quotes, newlines, null characters
        special_str = "Unicode: 🚀 \u2603 Quotes: ' \" ` \\ / \n \t \r"
        huge_details = {"key_" + str(i): "value_" * 50 for i in range(100)}
        anom = AnomalyRecord(
            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
            target_path=special_str,
            severity=Severity.HIGH,
            description=special_str,
            raw_details=huge_details,
            confidence=0.99999,
        )
        
        log_scan_session("s_special", [anom], ["Gradient: " + special_str], 12.34, db)
        
        retrieved_anoms = get_anomalies_for_session("s_special", db)
        assert len(retrieved_anoms) == 1
        assert retrieved_anoms[0].target_path == special_str
        assert retrieved_anoms[0].description == special_str
        assert retrieved_anoms[0].raw_details == huge_details
        
        retrieved_grads = get_textual_gradients_for_session("s_special", db)
        assert len(retrieved_grads) == 1
        assert retrieved_grads[0] == "Gradient: " + special_str
        print("  -> Passed: Handled large JSON dicts and extreme unicode/special characters without loss")

def main():
    test_foreign_key_enforcement()
    test_ast_safety_variations()
    test_json_deserialization_resilience()
    test_huge_payload_and_special_chars()
    print("\nAll adversarial tests completed.")

if __name__ == "__main__":
    main()

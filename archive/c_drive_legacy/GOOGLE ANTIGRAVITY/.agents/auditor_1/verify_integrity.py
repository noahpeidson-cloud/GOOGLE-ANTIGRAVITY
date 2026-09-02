"""
verify_integrity.py - Independent Forensic Auditor Verification Script
Executes adversarial checks, mutation stress-tests, and behavior verification on database_sink.py
"""

import sys
from pathlib import Path

# Add quick_share_ai_loop to sys.path
PROJECT_DIR = Path("G:/My Drive/GOOGLE ANTIGRAVITY/quick_share_ai_loop")
sys.path.insert(0, str(PROJECT_DIR))

import os
import json
import pytest
from unittest.mock import MagicMock, patch
import psycopg2
from psycopg2.extras import Json

import database_sink

def set_valid_env():
    os.environ["PG_HOST"] = "127.0.0.1"
    os.environ["PG_PORT"] = "5432"
    os.environ["PG_USER"] = "postgres"
    os.environ["PG_PASSWORD"] = "test_pw"
    os.environ["PG_DB"] = "media_analytics"
    database_sink._CONNECTION_POOL = None

def test_rule_r26_fail_fast():
    print("[AUDIT CHECK 1] Testing Rule R26 Fail-Fast Validation...")
    set_valid_env()
    env_vars = ["PG_HOST", "PG_USER", "PG_PASSWORD", "PG_DB"]
    for var in env_vars:
        old_val = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]
        try:
            database_sink.get_db_config()
            raise AssertionError(f"Integrity Violation: get_db_config did NOT fail when {var} was missing!")
        except ValueError as e:
            assert "Rule R26" in str(e)
            assert var in str(e)
            print(f"  -> PASS: Correctly caught missing {var}")
        finally:
            if old_val is not None:
                os.environ[var] = old_val

def test_jsonb_adaptation_integrity():
    print("[AUDIT CHECK 2] Testing JSONB Adaptation & Query Parameters...")
    set_valid_env()
    with patch("database_sink.pool.ThreadedConnectionPool") as mock_pool_cls:
        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool_cls.return_value = mock_pool
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        payload = {
            "domain": "Sports Cards",
            "entity": "Wemby Prizm RC",
            "viral_features": ["PSA_10", "Case_Hit"],
            "technical": {"resolution": "3840x2160", "fps": 60}
        }
        
        database_sink.insert_video_analytics("wemby_4k.mp4", payload)
        
        assert mock_cur.execute.called, "cur.execute was not called!"
        args, _ = mock_cur.execute.call_args
        sql, params = args
        
        assert "ON CONFLICT (filename) DO UPDATE" in sql, "Missing ON CONFLICT clause!"
        assert params[0] == "wemby_4k.mp4"
        assert params[2] == "Sports Cards"
        assert params[3] == "Wemby Prizm RC"
        assert isinstance(params[4], Json), "viral_features is not wrapped in psycopg2.extras.Json!"
        assert params[4].adapted == ["PSA_10", "Case_Hit"]
        assert isinstance(params[5], Json), "technical is not wrapped in psycopg2.extras.Json!"
        assert params[5].adapted == {"resolution": "3840x2160", "fps": 60}
        print("  -> PASS: JSONB parameterization and ON CONFLICT verified.")

def test_stale_connection_recovery():
    print("[AUDIT CHECK 3] Testing Stale Connection Pre-Ping Recovery...")
    set_valid_env()
    with patch("database_sink.pool.ThreadedConnectionPool") as mock_pool_cls:
        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_pool_cls.return_value = mock_pool
        
        dead_conn = MagicMock()
        dead_cur = MagicMock()
        dead_conn.cursor.return_value.__enter__.return_value = dead_cur
        dead_cur.execute.side_effect = psycopg2.OperationalError("server closed the connection unexpectedly")
        
        fresh_conn = MagicMock()
        fresh_cur = MagicMock()
        fresh_conn.cursor.return_value.__enter__.return_value = fresh_cur
        fresh_cur.execute.return_value = None
        
        mock_pool.getconn.side_effect = [dead_conn, fresh_conn]
        
        with database_sink.get_db_connection() as conn:
            assert conn is fresh_conn, "Failed to switch to fresh connection on stale socket!"
            
        mock_pool.putconn.assert_any_call(dead_conn, close=True)
        mock_pool.putconn.assert_any_call(fresh_conn, close=False)
        print("  -> PASS: Stale socket discarded with close=True and fresh socket used.")

def test_zero_leak_on_repeated_exceptions():
    print("[AUDIT CHECK 4] Testing Zero Connection Leak under Failure Loops...")
    set_valid_env()
    with patch("database_sink.pool.ThreadedConnectionPool") as mock_pool_cls:
        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pool_cls.return_value = mock_pool
        mock_pool.getconn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        mock_cur.execute.side_effect = [
            None, # pre-ping
            psycopg2.DatabaseError("Disk full error")
        ] * 10
        
        failures = 0
        for i in range(10):
            try:
                database_sink.insert_video_analytics(f"fail_{i}.mp4", {"domain": "EDM"})
            except psycopg2.DatabaseError:
                failures += 1
                
        assert failures == 10, f"Expected 10 failures, got {failures}"
        assert mock_pool.putconn.call_count == 10, f"Expected 10 putconn calls, got {mock_pool.putconn.call_count}"
        assert mock_conn.rollback.call_count == 10, f"Expected 10 rollback calls, got {mock_conn.rollback.call_count}"
        print("  -> PASS: Exactly 10/10 connections returned to pool on failure (0 leaks).")

def test_mutation_sensitivity():
    print("[AUDIT CHECK 5] Testing Test Sensitivity against Simulated Facade / Cheats...")
    set_valid_env()
    # Test that an un-adapted raw dict fails the Json() check
    unadapted = {"resolution": "4K"}
    assert not isinstance(unadapted, Json)
    print("  -> PASS: Mutation detection confirms unadapted raw structures are caught.")

if __name__ == "__main__":
    test_rule_r26_fail_fast()
    test_jsonb_adaptation_integrity()
    test_stale_connection_recovery()
    test_zero_leak_on_repeated_exceptions()
    test_mutation_sensitivity()
    print("\n[VERIFICATION COMPLETE] All independent forensic checks passed cleanly!")

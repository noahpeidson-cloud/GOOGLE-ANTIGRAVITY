"""
adversarial_stress_test.py - Adversarial edge-case and boundary verification.
"""

import os
import sys
import tempfile
import sqlite3
import threading
import time

sys.path.insert(0, r"g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub")

import models
import database
from pydantic import ValidationError

def test_schema_column_names_and_types():
    print("--- Stress Test 1: SQLite Schema Column Verification ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "schema_test.db")
        database.init_db(db_path)
        
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(cards);")
        columns = {row[1]: {"type": row[2], "notnull": row[3], "dflt_value": row[4], "pk": row[5]} for row in cur.fetchall()}
        conn.close()
        
        # 21 variables + id + created_at + updated_at = 24 columns
        expected_columns = {
            "id", "date_purchased", "quantity", "player", "year", "set_name",
            "variation", "card_number", "category", "condition", "slab_serial_number",
            "investment", "estimated_value", "ladder_id", "query", "notes",
            "tags", "date_sold", "sold_price", "image", "back_image", "ai_status",
            "created_at", "updated_at"
        }
        
        missing = expected_columns - set(columns.keys())
        extra = set(columns.keys()) - expected_columns
        assert not missing, f"Missing columns in cards table: {missing}"
        assert not extra, f"Unexpected extra columns in cards table: {extra}"
        assert len(columns) == 24, f"Expected 24 columns, got {len(columns)}"
        print(f"[PASS] 24/24 columns verified exactly in SQLite DDL.")

def test_high_volume_concurrency_stress():
    print("--- Stress Test 2: High Volume WAL Concurrency Stress ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "concurrency_stress.db")
        database.init_db(db_path)
        
        errors = []
        def writer_thread(t_id):
            try:
                for i in range(25):
                    card = {
                        "player": f"Stress Player {t_id}-{i}",
                        "year": "2024",
                        "set_name": "Panini Prizm",
                        "category": "Basketball",
                        "condition": "Raw",
                        "notes": f"{t_id:04d}-{i:03d}"
                    }
                    database.insert_card(card, db_path=db_path)
            except Exception as e:
                errors.append(f"Writer {t_id} error: {e}")

        def reader_thread(t_id):
            try:
                for _ in range(50):
                    cards = database.get_all_cards(limit=50, db_path=db_path)
                    stats = database.get_summary_stats(db_path=db_path)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(f"Reader {t_id} error: {e}")

        threads = []
        for i in range(6):
            threads.append(threading.Thread(target=writer_thread, args=(i,)))
        for i in range(6):
            threads.append(threading.Thread(target=reader_thread, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrency stress errors encountered: {errors}"
        total_count = database.get_card_count(db_path=db_path)
        assert total_count == 150, f"Expected 150 cards inserted, got {total_count}"
        print(f"[PASS] Successfully handled 6 concurrent writers + 6 concurrent readers with zero locking exceptions (Total inserted: {total_count}).")

def test_query_synthesis_edge_cases():
    print("--- Stress Test 3: Query Synthesis Adversarial Inputs ---")
    # Multiple whitespace handling
    q1 = models.synthesize_query(" 2021  ", "  Panini   Select ", "  Luka   Doncic ", "  Silver  ", " PSA 10 ")
    assert q1 == "2021 Panini Select Luka Doncic Silver PSA 10", f"Unexpected query: {q1}"
    
    # Missing variation and condition Raw
    q2 = models.synthesize_query("2020", "Topps Chrome", "Shohei Ohtani", "", "Raw")
    assert q2 == "2020 Topps Chrome Shohei Ohtani Raw"
    
    # Graded with no variation
    q3 = models.synthesize_query("1986", "Fleer", "Michael Jordan", "", "BGS 9.5")
    assert q3 == "1986 Fleer Michael Jordan BGS 9.5"
    
    print("[PASS] Query synthesis handles whitespace and optional components cleanly.")

if __name__ == "__main__":
    test_schema_column_names_and_types()
    test_high_volume_concurrency_stress()
    test_query_synthesis_edge_cases()
    print("\nALL ADVERSARIAL STRESS TESTS PASSED.")

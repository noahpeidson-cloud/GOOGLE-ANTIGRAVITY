"""
forensic_verify.py - Independent forensic verification script for Milestone 1.
Tests for hardcoded results, facade implementations, SQLite constraint enforcement,
real disk persistence, schema edge cases, and Pydantic validation integrity.
"""

import os
import sys
import tempfile
import sqlite3
import re
import inspect

# Add target code directory to sys.path
sys.path.insert(0, r"g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub")

import models
import database
from pydantic import ValidationError

def test_ast_and_source_integrity():
    print("--- Check 1: Static Code & Facade Inspection ---")
    # Verify no mock libraries imported in production code
    models_src = inspect.getsource(models)
    db_src = inspect.getsource(database)
    
    assert "unittest.mock" not in models_src, "unittest.mock found in models.py"
    assert "unittest.mock" not in db_src, "unittest.mock found in database.py"
    assert "MagicMock" not in models_src, "MagicMock found in models.py"
    assert "MagicMock" not in db_src, "MagicMock found in database.py"
    
    # Check that database functions are not trivial stubs (e.g. returning constant literals)
    for func_name in [
        "init_db", "insert_card", "insert_cards_batch", "get_card_by_id",
        "get_all_cards", "update_card", "update_card_status", "delete_card",
        "get_cards_for_export", "get_summary_stats", "get_next_child_id",
        "clear_staging_table", "get_card_count", "check_circuit_breaker",
        "capture_card_from_api"
    ]:
        assert hasattr(database, func_name), f"database.py missing function: {func_name}"
        func = getattr(database, func_name)
        lines = inspect.getsourcelines(func)[0]
        assert len(lines) >= 5, f"Function {func_name} appears to be a stub (only {len(lines)} lines)"
    
    print("[PASS] Check 1 Passed: No mock imports or stub functions found.")

def test_sqlite_ddl_and_raw_constraints():
    print("--- Check 2: SQLite DDL Constraint Enforcement (Bypassing Python/Pydantic) ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "forensic_test.db")
        database.init_db(db_path)
        
        # Verify database file was physically created
        assert os.path.exists(db_path), "Database file was not created on disk"
        assert os.path.getsize(db_path) > 0, "Database file is empty"
        
        # Test 1: Raw condition with non-empty slab serial number via raw SQL
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        passed_invalid = False
        try:
            cur.execute("""
            INSERT INTO cards (
                date_purchased, quantity, player, year, set_name, variation, card_number,
                category, condition, slab_serial_number, investment, estimated_value,
                ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
            ) VALUES (
                '08/24/2026', 1, 'Fake Player', '2024', 'Fake Set', '', '1',
                'Basketball', 'Raw', 'SLAB12345', 10.0, 20.0,
                '', '2024 Fake Set Fake Player Raw', '', '', '', NULL, '', '', 'CLEARED'
            );
            """)
            conn.commit()
            passed_invalid = True
        except sqlite3.IntegrityError:
            pass # Expected
        assert not passed_invalid, "SQLite failed to reject Raw card with slab serial number!"

        # Test 2: Raw card with negative exclusion in query
        passed_invalid = False
        try:
            cur.execute("""
            INSERT INTO cards (
                date_purchased, quantity, player, year, set_name, variation, card_number,
                category, condition, slab_serial_number, investment, estimated_value,
                ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
            ) VALUES (
                '08/24/2026', 1, 'Fake Player', '2024', 'Fake Set', '', '1',
                'Basketball', 'Raw', '', 10.0, 20.0,
                '', '2024 Fake Set Fake Player Raw -BGS', '', '', '', NULL, '', '', 'CLEARED'
            );
            """)
            conn.commit()
            passed_invalid = True
        except sqlite3.IntegrityError:
            pass # Expected
        assert not passed_invalid, "SQLite failed to reject Raw card with negative exclusion -BGS in query!"

        # Test 3: Invalid category
        passed_invalid = False
        try:
            cur.execute("""
            INSERT INTO cards (
                date_purchased, quantity, player, year, set_name, variation, card_number,
                category, condition, slab_serial_number, investment, estimated_value,
                ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
            ) VALUES (
                '08/24/2026', 1, 'Fake Player', '2024', 'Fake Set', '', '1',
                'UnsupportedCategory', 'Raw', '', 10.0, 20.0,
                '', 'Query', '', '', '', NULL, '', '', 'CLEARED'
            );
            """)
            conn.commit()
            passed_invalid = True
        except sqlite3.IntegrityError:
            pass
        assert not passed_invalid, "SQLite failed to reject card with invalid category!"

        # Test 4: Invalid 3-digit year
        passed_invalid = False
        try:
            cur.execute("""
            INSERT INTO cards (
                date_purchased, quantity, player, year, set_name, variation, card_number,
                category, condition, slab_serial_number, investment, estimated_value,
                ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
            ) VALUES (
                '08/24/2026', 1, 'Fake Player', '999', 'Fake Set', '', '1',
                'Basketball', 'Raw', '', 10.0, 20.0,
                '', 'Query', '', '', '', NULL, '', '', 'CLEARED'
            );
            """)
            conn.commit()
            passed_invalid = True
        except sqlite3.IntegrityError:
            pass
        assert not passed_invalid, "SQLite failed to reject card with 3-digit year!"

        conn.close()
    print("[PASS] Check 2 Passed: SQLite DDL constraints natively and strictly enforced.")

def test_genuine_pydantic_validation():
    print("--- Check 3: Pydantic v2 Genuine Validation & Field Normalization ---")
    # Date normalization
    c1 = models.CardRecord(
        player="LeBron James",
        year="2003",
        set_name="Topps Chrome",
        category=models.CardCategory.BASKETBALL,
        date_purchased="2023-05-12",
    )
    assert c1.date_purchased == "05/12/2023", f"Expected 05/12/2023, got {c1.date_purchased}"
    
    # Query auto-synthesis with variation and condition
    c2 = models.CardRecord(
        player="Kobe Bryant",
        year="1996",
        set_name="Topps Chrome",
        variation="Refractor",
        category=models.CardCategory.BASKETBALL,
        condition="PSA 10",
        slab_serial_number="12345678"
    )
    assert c2.query == "1996 Topps Chrome Kobe Bryant Refractor PSA 10"
    
    # Leading zero string preservation
    c3 = models.CardRecord(
        player="Aaron Judge",
        year="2017",
        set_name="Topps",
        card_number="007",
        category=models.CardCategory.BASEBALL,
    )
    assert c3.card_number == "007"
    assert type(c3.card_number) is str
    
    # Negative exclusion detection in Pydantic
    try:
        models.CardRecord(
            player="Test",
            year="2020",
            set_name="Set",
            category=models.CardCategory.BASEBALL,
            condition="Raw",
            query="2020 Set Test Raw -PSA"
        )
        assert False, "Pydantic failed to reject -PSA on Raw card"
    except ValidationError:
        pass
    
    print("[PASS] Check 3 Passed: Pydantic models execute genuine validation and synthesis.")

def test_crud_persistence_cycle():
    print("--- Check 4: Full Database CRUD and Physical Persistence Cycle ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "persist_test.db")
        database.init_db(db_path)
        
        card_payload = {
            "player": "Wander Franco",
            "year": "2022",
            "set_name": "Topps Series 1",
            "variation": "Gold /2022",
            "card_number": "215",
            "category": "Baseball",
            "condition": "PSA 9",
            "slab_serial_number": "59201948",
            "investment": 40.0,
            "estimated_value": 75.0,
            "notes": "1001-101",
        }
        
        # Insert
        card_id = database.insert_card(card_payload, db_path=db_path)
        assert card_id == 1
        
        # Read
        retrieved = database.get_card_by_id(1, db_path=db_path)
        assert retrieved is not None
        assert retrieved["player"] == "Wander Franco"
        assert retrieved["variation"] == "Gold /2022"
        assert retrieved["query"] == "2022 Topps Series 1 Wander Franco Gold /2022 PSA 9"
        
        # Update
        database.update_card(1, {"variation": "Gold Mint /2022", "estimated_value": 90.0}, db_path=db_path)
        updated = database.get_card_by_id(1, db_path=db_path)
        assert updated["variation"] == "Gold Mint /2022"
        assert updated["estimated_value"] == 90.0
        assert updated["query"] == "2022 Topps Series 1 Wander Franco Gold Mint /2022 PSA 9"
        
        # Summary Stats
        stats = database.get_summary_stats(db_path)
        assert stats["total_cards"] == 1
        assert stats["total_investment"] == 40.0
        assert stats["total_estimated_value"] == 90.0
        assert stats["count_by_category"]["Baseball"] == 1
        
        # Delete
        assert database.delete_card(1, db_path=db_path) is True
        assert database.get_card_by_id(1, db_path=db_path) is None
        assert database.get_card_count(db_path) == 0

    print("[PASS] Check 4 Passed: CRUD operations genuinely manipulate SQLite records.")

if __name__ == "__main__":
    test_ast_and_source_integrity()
    test_sqlite_ddl_and_raw_constraints()
    test_genuine_pydantic_validation()
    test_crud_persistence_cycle()
    print("\nALL 4 FORENSIC CHECKS PASSED: VERDICT CLEAN")

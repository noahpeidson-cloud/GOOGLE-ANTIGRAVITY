"""
tests/test_adversarial_m1.py - Empirical Adversarial & Fuzzing Test Suite for Milestone 1.
Challenger Agent: teamwork_preview_challenger (M1)

Covers:
1. Category validation fuzzing & injection attacks (22 valid enums, invalid strings, SQL injections, Unicode, casing).
2. Condition formatting edge cases ('PSA-10', 'raw', 'bgs 9.5', negative exclusions on Raw).
3. Slab cert number injection attacks on Raw condition cards (cross-field validation, DB CHECK constraints).
4. Card number string boundary tests ('000', '007', '04', 'RC-001', 'NNO', '0', '0000000000', preservation across CRUD).
5. High-concurrency race condition harness (50+ threads, concurrent reads, writes, updates, batching, WAL integrity).
6. SQL injection resistance on search and filter parameters.
7. Extreme values and boundary validation (negative values, year formats, empty required fields).
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Any
import pytest
from pydantic import ValidationError

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import (
    CardRecord,
    CardCategory,
    AIStatus,
    CardUpdate,
    CardCaptureRequest,
    CardBatchCreate,
    synthesize_query,
    format_notes,
    VALID_CATEGORIES,
    CATEGORY_MAP,
)
from database import (
    init_db,
    insert_card,
    insert_cards_batch,
    get_card_by_id,
    get_all_cards,
    list_cards,
    update_card,
    update_card_status,
    delete_card,
    get_cards_for_export,
    get_summary_stats,
    get_next_child_id,
    clear_staging_table,
    get_card_count,
    check_circuit_breaker,
    capture_card_from_api,
    get_db_connection,
)


@pytest.fixture
def adv_db_path(tmp_path):
    """Provides an isolated database instance for adversarial tests."""
    db_file = str(tmp_path / "adversarial_portfolio.db")
    init_db(db_file)
    return db_file


# ============================================================================
# Category 1: Invalid Category Injection Fuzzing & DB Constraint Enforcement
# ============================================================================

class TestAdversarialCategoryInjection:

    @pytest.mark.parametrize("invalid_category", [
        "Cricket",
        "Badminton",
        "Table Tennis",
        "TCG",
        "Sports",
        "Other",
        "Custom",
        "Basket ball",
        "Basketball1",
        "Basketball 2",
        "Base_ball",
        "Soccer!",
        "Pokemon\x00",
        "🏀",
        "Soccer\u200b",
        "' OR '1'='1",
        "'; DROP TABLE cards; --",
        "Football; SELECT * FROM cards",
        "DragonBall",
        "MagicTheGathering",
        "Yugioh!",
        "Flesh & Blood!",
        "",
        "   ",
        "123",
        "None",
    ])
    def test_pydantic_rejects_invalid_category_fuzzing(self, invalid_category):
        """Pydantic CardRecord must strictly reject any category outside the 22 valid enums."""
        with pytest.raises((ValidationError, ValueError)):
            CardRecord(
                player="Test Athlete",
                year="2024",
                set_name="Panini Prizm",
                category=invalid_category,
            )

    def test_all_22_valid_categories_accepted(self):
        """All 22 specified categories must be strictly accepted."""
        expected_22 = [
            "Basketball", "Baseball", "Football", "Hockey", "Soccer", "Tennis",
            "Wrestling", "Racing", "Golf", "Boxing", "UFC/MMA", "Pokemon",
            "Magic", "Metazoo", "Yugioh", "Fortnite", "Dragonballz",
            "Entertainment", "Swimming", "Softball", "PopCulture", "Flesh and Blood"
        ]
        assert len(expected_22) == 22
        assert len(VALID_CATEGORIES) == 22
        assert set(expected_22) == VALID_CATEGORIES

        for cat in expected_22:
            card = CardRecord(
                player="Test Player",
                year="2024",
                set_name="Test Set",
                category=cat,
            )
            assert card.category == cat

    def test_category_normalization_aliases(self):
        """Case insensitivity and aliases must correctly normalize to canonical title case."""
        alias_test_cases = [
            ("basketball", "Basketball"),
            ("BASEBALL", "Baseball"),
            ("football", "Football"),
            ("hockey", "Hockey"),
            ("soccer", "Soccer"),
            ("tennis", "Tennis"),
            ("wrestling", "Wrestling"),
            ("racing", "Racing"),
            ("golf", "Golf"),
            ("boxing", "Boxing"),
            ("ufc", "UFC/MMA"),
            ("mma", "UFC/MMA"),
            ("ufc/mma", "UFC/MMA"),
            ("UFC", "UFC/MMA"),
            ("pokemon", "Pokemon"),
            ("POKEMON", "Pokemon"),
            ("magic", "Magic"),
            ("metazoo", "Metazoo"),
            ("yugioh", "Yugioh"),
            ("fortnite", "Fortnite"),
            ("dragonballz", "Dragonballz"),
            ("dragon ball z", "Dragonballz"),
            ("dragonball z", "Dragonballz"),
            ("entertainment", "Entertainment"),
            ("swimming", "Swimming"),
            ("softball", "Softball"),
            ("popculture", "PopCulture"),
            ("pop culture", "PopCulture"),
            ("flesh and blood", "Flesh and Blood"),
            ("flesh & blood", "Flesh and Blood"),
            (" basketball ", "Basketball"),
            ("  Pokemon   ", "Pokemon"),
        ]
        for raw_cat, expected in alias_test_cases:
            card = CardRecord(
                player="Test Player",
                year="2024",
                set_name="Test Set",
                category=raw_cat,
            )
            assert card.category == expected

    @pytest.mark.parametrize("malicious_sql", [
        "' OR 1=1 --",
        "'; DROP TABLE cards; --",
        "' UNION SELECT * FROM cards --",
        "Baseball', 'Raw', '12345'); --",
    ])
    def test_direct_sqlite_check_constraint_rejects_category_injection(self, adv_db_path, malicious_sql):
        """SQLite table DDL CHECK constraint must abort direct SQL injection bypassing Pydantic."""
        with get_db_connection(adv_db_path) as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("""
                INSERT INTO cards (
                    date_purchased, quantity, player, year, set_name, variation, card_number,
                    category, condition, slab_serial_number, investment, estimated_value,
                    ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                ) VALUES (
                    '08/24/2026', 1, 'Injected Player', '2024', 'Test Set', '', '1',
                    ?, 'Raw', '', 0.0, 0.0, '', 'Query', '', '', '', NULL, '', '', 'CLEARED'
                );
                """, (malicious_sql,))


# ============================================================================
# Category 2: Condition Formatting Fuzzing & Negative Exclusion Hardening
# ============================================================================

class TestAdversarialConditionFormatting:

    @pytest.mark.parametrize("hyphenated_condition", [
        "PSA-10",
        "PSA-9",
        "PSA-8.5",
        "BGS-9.5",
        "BGS-10",
        "BGS-9",
        "SGC-10",
        "SGC-9.5",
        "CGC-9.5",
        "CGC-10",
        "CSG-9",
        "BVG-8.5",
        "Raw-Mint",
    ])
    def test_graded_conditions_with_hyphens_strictly_rejected(self, hyphenated_condition):
        """Hyphenated condition strings (e.g. PSA-10) must be rejected with explicit error message."""
        with pytest.raises(ValidationError, match="must not contain hyphens"):
            CardRecord(
                player="Test Player",
                year="2024",
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
                condition=hyphenated_condition,
                slab_serial_number="99887766",
            )

    @pytest.mark.parametrize("raw_alias,expected", [
        ("raw", "Raw"),
        ("RAW", "Raw"),
        ("Raw", "Raw"),
        (" raw ", "Raw"),
        ("ungraded", "Raw"),
        ("UNGRADED", "Raw"),
        (" Ungraded ", "Raw"),
        ("", "Raw"),
    ])
    def test_raw_condition_normalization(self, raw_alias, expected):
        """All variations of raw/ungraded/blank condition must normalize strictly to 'Raw'."""
        card = CardRecord(
            player="Test Player",
            year="2024",
            set_name="Panini Prizm",
            category=CardCategory.BASKETBALL,
            condition=raw_alias,
        )
        assert card.condition == expected

    @pytest.mark.parametrize("valid_graded", [
        "PSA 10",
        "PSA 9",
        "PSA 8.5",
        "BGS 9.5",
        "BGS 10",
        "BGS 9",
        "SGC 10",
        "SGC 9.5",
        "CGC 10",
        "CGC 9.5",
        "CSG 9.5",
        "BVG 8",
        "bgs 9.5",
        "psa 10",
    ])
    def test_valid_graded_conditions_accepted(self, valid_graded):
        """Valid non-hyphenated graded conditions are accepted."""
        card = CardRecord(
            player="Test Player",
            year="2024",
            set_name="Panini Prizm",
            category=CardCategory.BASKETBALL,
            condition=valid_graded,
            slab_serial_number="12345678",
        )
        assert card.condition == valid_graded.strip()

    @pytest.mark.parametrize("forbidden_query_term", [
        "-BGS",
        "-SGC",
        "-PSA",
        "-CGC",
        "-CSG",
        "-BVG",
        "-bgs",
        "-psa",
    ])
    def test_negative_exclusions_on_raw_rejected_pydantic_and_sql(self, adv_db_path, forbidden_query_term):
        """Negative exclusion terms (-BGS, -SGC, etc.) on Raw condition cards are forbidden."""
        # 1. Test Pydantic validation rejection
        with pytest.raises(ValidationError, match="Negative exclusions are forbidden"):
            CardRecord(
                player="Luka Doncic",
                year="2020",
                set_name="Prizm",
                category=CardCategory.BASKETBALL,
                condition="Raw",
                query=f"2020 Prizm Luka Doncic Raw {forbidden_query_term}",
            )

        # 2. Test direct SQLite CHECK constraint rejection
        with get_db_connection(adv_db_path) as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("""
                INSERT INTO cards (
                    date_purchased, quantity, player, year, set_name, variation, card_number,
                    category, condition, slab_serial_number, investment, estimated_value,
                    ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                ) VALUES (
                    '08/24/2026', 1, 'Luka Doncic', '2020', 'Prizm', '', '1',
                    'Basketball', 'Raw', '', 0.0, 0.0,
                    '', ?, '', '', '', NULL, '', '', 'CLEARED'
                );
                """, (f"2020 Prizm Luka Doncic Raw {forbidden_query_term.upper()}",))


# ============================================================================
# Category 3: Slab Serial Number Injection Attacks on Raw Cards
# ============================================================================

class TestAdversarialSlabCertOnRaw:

    @pytest.mark.parametrize("raw_condition_variant", ["Raw", "raw", "RAW", "ungraded", "UNGRADED"])
    def test_pydantic_rejects_slab_serial_on_raw(self, raw_condition_variant):
        """CardRecord must raise ValidationError if condition is Raw and slab_serial_number is non-empty."""
        with pytest.raises(ValidationError, match="Slab serial number must be blank for 'Raw'"):
            CardRecord(
                player="Shohei Ohtani",
                year="2023",
                set_name="Topps Chrome",
                category=CardCategory.BASEBALL,
                condition=raw_condition_variant,
                slab_serial_number="84729104",
            )

    def test_raw_with_whitespace_slab_serial_normalizes_to_empty(self):
        """Whitespace-only slab serial number on Raw card is cleaned to empty string and passes."""
        card = CardRecord(
            player="Shohei Ohtani",
            year="2023",
            set_name="Topps Chrome",
            category=CardCategory.BASEBALL,
            condition="Raw",
            slab_serial_number="   ",
        )
        assert card.slab_serial_number == ""

    def test_direct_sqlite_check_constraint_rejects_raw_with_slab_serial(self, adv_db_path):
        """SQLite table constraint check_raw_no_slab must reject direct INSERT of Raw card with slab serial."""
        with get_db_connection(adv_db_path) as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("""
                INSERT INTO cards (
                    date_purchased, quantity, player, year, set_name, variation, card_number,
                    category, condition, slab_serial_number, investment, estimated_value,
                    ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                ) VALUES (
                    '08/24/2026', 1, 'Ohtani', '2023', 'Topps Chrome', '', '7',
                    'Baseball', 'Raw', '84729104', 10.0, 20.0,
                    '', '2023 Topps Chrome Ohtani Raw', '', '', '', NULL, '', '', 'CLEARED'
                );
                """)

    def test_update_card_rejects_mutating_to_raw_while_keeping_slab_serial(self, adv_db_path):
        """Updating a graded card with slab_serial to Raw condition without clearing slab serial must fail."""
        # 1. Insert valid graded card
        card_id = insert_card({
            "player": "Luka Doncic",
            "year": "2018",
            "set_name": "Panini Prizm",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "12345678",
        }, db_path=adv_db_path)

        # 2. Attempt to update condition to Raw without blanking slab_serial_number
        with pytest.raises(ValidationError):
            update_card(card_id, {"condition": "Raw"}, db_path=adv_db_path)

        # Verify card is unchanged and still PSA 10
        card = get_card_by_id(card_id, db_path=adv_db_path)
        assert card["condition"] == "PSA 10"
        assert card["slab_serial_number"] == "12345678"

        # 3. Proper update: clearing slab_serial_number along with condition='Raw' succeeds
        success = update_card(card_id, {"condition": "Raw", "slab_serial_number": ""}, db_path=adv_db_path)
        assert success is True
        updated = get_card_by_id(card_id, db_path=adv_db_path)
        assert updated["condition"] == "Raw"
        assert updated["slab_serial_number"] == ""


# ============================================================================
# Category 4: Card Number String Boundary Conditions & Zero-Preservation
# ============================================================================

class TestAdversarialCardNumberFidelity:

    @pytest.mark.parametrize("card_num_str", [
        "000",
        "007",
        "04",
        "001",
        "0000000000",
        "RC-001",
        "NNO",
        "0",
        "#24",
        "1/1",
        "001/100",
        "SP-04",
        "U-100",
        "A-1",
        "###",
        "0042",
        "99999999999999999999",
    ])
    def test_card_number_preserves_exact_string_and_leading_zeros(self, adv_db_path, card_num_str):
        """Card numbers with leading zeroes, dashes, and letters must preserve exact representation across CRUD."""
        # 1. Pydantic Model
        record = CardRecord(
            player="Test Player",
            year="2024",
            set_name="Topps Chrome",
            category=CardCategory.BASEBALL,
            card_number=card_num_str,
        )
        assert record.card_number == card_num_str
        assert isinstance(record.card_number, str)

        # 2. Database Insert
        card_id = insert_card(record.model_dump(), db_path=adv_db_path)

        # 3. Database Retrieve by ID
        fetched = get_card_by_id(card_id, db_path=adv_db_path)
        assert fetched["card_number"] == card_num_str
        assert isinstance(fetched["card_number"], str)

        # 4. Database Filter/List
        all_cards = get_all_cards(db_path=adv_db_path, limit=100)
        matching = [c for c in all_cards if c["id"] == card_id]
        assert len(matching) == 1
        assert matching[0]["card_number"] == card_num_str

        # 5. Export retrieval
        export_cards = get_cards_for_export(status_filter="ALL", db_path=adv_db_path)
        matching_exp = [c for c in export_cards if c["id"] == card_id]
        assert len(matching_exp) == 1
        assert matching_exp[0]["card_number"] == card_num_str

    def test_integer_and_float_coercion_to_string(self):
        """Numeric card numbers passed as int or float are converted cleanly to strings."""
        c1 = CardRecord(
            player="Test",
            year="2024",
            set_name="Set",
            category=CardCategory.BASEBALL,
            card_number=7,
        )
        assert c1.card_number == "7"

        c2 = CardRecord(
            player="Test",
            year="2024",
            set_name="Set",
            category=CardCategory.BASEBALL,
            card_number=0,
        )
        assert c2.card_number == "0"


# ============================================================================
# Category 5: Multi-Threaded High-Concurrency & Race Condition Stress Harness
# ============================================================================

class TestAdversarialConcurrencyAndWAL:

    def test_heavy_concurrent_read_write_update_delete(self, adv_db_path):
        """
        Executes 50 concurrent threads (20 writers, 15 readers, 10 updaters, 5 deleters)
        performing over 1,500 operations under SQLite WAL mode to test race conditions and locking.
        """
        thread_errors: list[str] = []
        inserted_ids: list[int] = []
        ids_lock = threading.Lock()

        stop_signal = threading.Event()

        def writer_worker(worker_id: int):
            try:
                for i in range(25):
                    if stop_signal.is_set():
                        break
                    card_dict = {
                        "player": f"Concurrency Player W{worker_id}_{i}",
                        "year": "2024",
                        "set_name": "Topps Concurrency",
                        "card_number": f"{i:04d}",
                        "category": "Baseball",
                        "condition": "Raw",
                        "investment": float(i * 5),
                        "estimated_value": float(i * 10),
                        "notes": f"9000-{worker_id:03d}",
                    }
                    new_id = insert_card(card_dict, db_path=adv_db_path)
                    with ids_lock:
                        inserted_ids.append(new_id)
            except Exception as e:
                thread_errors.append(f"Writer {worker_id} error: {e}")

        def reader_worker(worker_id: int):
            try:
                for _ in range(30):
                    if stop_signal.is_set():
                        break
                    get_all_cards(limit=50, db_path=adv_db_path)
                    get_summary_stats(db_path=adv_db_path)
                    get_next_child_id(9000, db_path=adv_db_path)
            except Exception as e:
                thread_errors.append(f"Reader {worker_id} error: {e}")

        def updater_worker(worker_id: int):
            try:
                for _ in range(20):
                    if stop_signal.is_set():
                        break
                    with ids_lock:
                        target_id = inserted_ids[len(inserted_ids) // 2] if inserted_ids else None
                    if target_id:
                        update_card(target_id, {"estimated_value": 999.99}, db_path=adv_db_path)
                        update_card_status(target_id, "REVIEW VARIATION", db_path=adv_db_path)
            except Exception as e:
                thread_errors.append(f"Updater {worker_id} error: {e}")

        def deleter_worker(worker_id: int):
            try:
                for _ in range(10):
                    if stop_signal.is_set():
                        break
                    with ids_lock:
                        target_id = inserted_ids.pop(0) if len(inserted_ids) > 100 else None
                    if target_id:
                        delete_card(target_id, db_path=adv_db_path)
            except Exception as e:
                thread_errors.append(f"Deleter {worker_id} error: {e}")

        threads: list[threading.Thread] = []

        # 20 Writers
        for w in range(20):
            threads.append(threading.Thread(target=writer_worker, args=(w,)))
        # 15 Readers
        for r in range(15):
            threads.append(threading.Thread(target=reader_worker, args=(r,)))
        # 10 Updaters
        for u in range(10):
            threads.append(threading.Thread(target=updater_worker, args=(u,)))
        # 5 Deleters
        for d in range(5):
            threads.append(threading.Thread(target=deleter_worker, args=(d,)))

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=30.0)

        assert len(thread_errors) == 0, f"Thread execution errors found: {thread_errors}"

        # Run integrity check on SQLite database
        with get_db_connection(adv_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            integrity_result = cursor.fetchone()[0]
            assert integrity_result == "ok", f"Database corrupted: {integrity_result}"

    def test_concurrent_child_id_generation(self, adv_db_path):
        """Tests race conditions when multiple threads generate child IDs for the same parent."""
        errors = []

        def worker(idx: int):
            try:
                for _ in range(10):
                    next_id = get_next_child_id(8888, db_path=adv_db_path)
                    notes_str = format_notes(8888, next_id)
                    insert_card({
                        "player": f"Child Player {idx}",
                        "year": "2024",
                        "set_name": "Set",
                        "category": "Hockey",
                        "notes": notes_str,
                    }, db_path=adv_db_path)
            except Exception as e:
                errors.append(f"Child ID worker error: {e}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during child ID generation: {errors}"
        count = get_card_count(adv_db_path)
        assert count == 50


# ============================================================================
# Category 6: SQL Injection Resistance & Fuzzing Search Filters
# ============================================================================

class TestAdversarialSQLInjectionResistance:

    @pytest.mark.parametrize("malicious_search", [
        "' OR '1'='1",
        "'; DROP TABLE cards; --",
        "1' UNION SELECT * FROM cards --",
        "'' OR 1=1 --",
        "admin'--",
        "/**/OR/**/1=1",
        "' OR ''='",
        "1; ATTACH DATABASE 'malicious.db' AS mal;",
    ])
    def test_search_and_filter_sql_injection_safety(self, adv_db_path, malicious_search):
        """get_all_cards must use parameterized queries and resist SQL injection without throwing syntax errors."""
        # Insert a benign card
        insert_card({
            "player": "Benign Athlete",
            "year": "2024",
            "set_name": "Topps Clean",
            "category": "Baseball",
        }, db_path=adv_db_path)

        # 1. Search filter injection
        results = get_all_cards(search_query=malicious_search, db_path=adv_db_path)
        assert isinstance(results, list)

        # 2. Category filter injection
        cat_results = get_all_cards(category_filter=malicious_search, db_path=adv_db_path)
        assert isinstance(cat_results, list)

        # 3. Status filter injection
        status_results = get_all_cards(status_filter=malicious_search, db_path=adv_db_path)
        assert isinstance(status_results, list)

        # Verify cards table is intact
        assert get_card_count(adv_db_path) == 1

    @pytest.mark.parametrize("invalid_order_by", [
        "id; DROP TABLE cards;",
        "player ASC; DELETE FROM cards;",
        "CASE WHEN (1=1) THEN id ELSE player END",
        "id DESC, (SELECT count(*) FROM cards)",
        "non_existent_column",
    ])
    def test_order_by_injection_fallback_safety(self, adv_db_path, invalid_order_by):
        """get_all_cards must safely whitelist order_by and fall back to 'id DESC' on invalid input."""
        results = get_all_cards(order_by=invalid_order_by, db_path=adv_db_path)
        assert isinstance(results, list)


# ============================================================================
# Category 7: Boundary Conditions & Negative Value Invariant Tests
# ============================================================================

class TestAdversarialBoundaryConditions:

    def test_negative_investment_and_value_rejected(self, adv_db_path):
        """Negative investment or estimated_value must be rejected by Pydantic and SQLite."""
        with pytest.raises(ValidationError):
            CardRecord(
                player="Test",
                year="2024",
                set_name="Set",
                category=CardCategory.BASEBALL,
                investment=-5.00,
            )

        with pytest.raises(ValidationError):
            CardRecord(
                player="Test",
                year="2024",
                set_name="Set",
                category=CardCategory.BASEBALL,
                estimated_value=-0.01,
            )

        with pytest.raises(ValidationError):
            CardRecord(
                player="Test",
                year="2024",
                set_name="Set",
                category=CardCategory.BASEBALL,
                sold_price=-10.00,
            )

    @pytest.mark.parametrize("invalid_year", [
        "24",
        "202",
        "20245",
        "ABCD",
        "YYYY",
        "2024-2025-2026",
        "",
        "    ",
    ])
    def test_invalid_year_formats_rejected(self, invalid_year):
        """Year must strictly be 4-digit YYYY format or multi-year season string (YYYY-YY)."""
        with pytest.raises(ValidationError):
            CardRecord(
                player="Test",
                year=invalid_year,
                set_name="Set",
                category=CardCategory.BASEBALL,
            )

    @pytest.mark.parametrize("empty_field", ["", "   ", None])
    def test_blank_player_or_set_rejected(self, empty_field):
        """Player and set_name cannot be blank or whitespace-only."""
        with pytest.raises(ValidationError):
            CardRecord(
                player=empty_field,
                year="2024",
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
            )

        with pytest.raises(ValidationError):
            CardRecord(
                player="Luka Doncic",
                year="2024",
                set_name=empty_field,
                category=CardCategory.BASKETBALL,
            )

    def test_circuit_breaker_exact_boundaries(self, adv_db_path):
        """Tests circuit breaker threshold at 499, 500, 501 items."""
        cards_499 = [
            {"player": f"Athlete {i}", "year": "2024", "set_name": "Set", "category": "Soccer"}
            for i in range(499)
        ]
        insert_cards_batch(cards_499, adv_db_path)

        cb_499 = check_circuit_breaker(adv_db_path, threshold=500)
        assert cb_499["total_staged"] == 499
        assert cb_499["circuit_breaker_tripped"] is False

        # Add 1 card to reach 500
        insert_card({"player": "Athlete 500", "year": "2024", "set_name": "Set", "category": "Soccer"}, db_path=adv_db_path)
        cb_500 = check_circuit_breaker(adv_db_path, threshold=500)
        assert cb_500["total_staged"] == 500
        assert cb_500["circuit_breaker_tripped"] is True

        # Add 1 card to exceed threshold (501)
        insert_card({"player": "Athlete 501", "year": "2024", "set_name": "Set", "category": "Soccer"}, db_path=adv_db_path)
        cb_501 = check_circuit_breaker(adv_db_path, threshold=500)
        assert cb_501["total_staged"] == 501
        assert cb_501["circuit_breaker_tripped"] is True

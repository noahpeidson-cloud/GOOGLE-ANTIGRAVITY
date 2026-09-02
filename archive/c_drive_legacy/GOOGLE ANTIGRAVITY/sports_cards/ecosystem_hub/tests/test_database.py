"""
tests/test_database.py - Deterministic test suite for Milestone 1.
Tests Pydantic v2 schemas, SQLite DDL constraints, WAL mode, CRUD methods, and concurrency.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any
import pytest
from pydantic import ValidationError

import sys
# Ensure parent directory of tests is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import (
    CardRecord,
    CardCategory,
    AIStatus,
    CardUpdate,
    CardCaptureRequest,
    CardBatchCreate,
    synthesize_query,
    calculate_query,
    format_notes,
    VALID_CATEGORIES,
)
from database import (
    init_db,
    insert_card,
    get_card_by_id,
    get_card,
    get_all_cards,
    list_cards,
    update_card,
    update_card_status,
    delete_card,
    insert_cards_batch,
    bulk_insert_cards,
    get_cards_for_export,
    get_summary_stats,
    get_next_child_id,
    clear_staging_table,
    get_card_count,
    get_staging_count,
    check_circuit_breaker,
    capture_card_from_api,
    get_db_connection,
)


@pytest.fixture
def test_db_path(tmp_path):
    """Provides a fresh isolated SQLite database path for each test."""
    db_file = str(tmp_path / "test_portfolio.db")
    init_db(db_file)
    return db_file


@pytest.fixture
def sample_card_dict() -> dict[str, Any]:
    """Provides a valid 21-variable dictionary."""
    return {
        "date_purchased": "08/24/2026",
        "quantity": 1,
        "player": "Shohei Ohtani",
        "year": "2023",
        "set_name": "Topps Chrome",
        "variation": "Refractor",
        "card_number": "007",
        "category": "Baseball",
        "condition": "PSA 10",
        "slab_serial_number": "84729104",
        "investment": 150.00,
        "estimated_value": 320.00,
        "ladder_id": "LAD-12345",
        "query": "",
        "notes": "8492-105",
        "tags": "pc, ohtani, mvp",
        "date_sold": "",
        "sold_price": None,
        "image": "https://example.com/front.jpg",
        "back_image": "https://example.com/back.jpg",
        "ai_status": "CLEARED",
    }


# ============================================================================
# Tier 1: Pydantic Model & Validation Tests
# ============================================================================

class TestPydanticModels:

    def test_valid_raw_card_minimal(self):
        """Validates creation with only mandatory fields."""
        card = CardRecord(
            player="Victor Wembanyama",
            year="2023",
            set_name="Panini Prizm",
            category=CardCategory.BASKETBALL,
        )
        assert card.player == "Victor Wembanyama"
        assert card.year == "2023"
        assert card.set_name == "Panini Prizm"
        assert card.category == "Basketball"
        assert card.condition == "Raw"
        assert card.quantity == 1
        assert card.investment == 0.0
        assert card.estimated_value == 0.0
        assert card.slab_serial_number == ""
        assert card.ai_status == "CLEARED"
        assert card.query == "2023 Panini Prizm Victor Wembanyama Raw"

    def test_valid_graded_card(self, sample_card_dict):
        """Validates creation of a graded card with auto-synthesized query."""
        card = CardRecord(**sample_card_dict)
        assert card.player == "Shohei Ohtani"
        assert card.condition == "PSA 10"
        assert card.slab_serial_number == "84729104"
        assert card.query == "2023 Topps Chrome Shohei Ohtani Refractor PSA 10"

    def test_all_22_categories_valid(self):
        """Tests that every one of the 22 permitted categories is valid."""
        categories = [
            "Basketball", "Baseball", "Football", "Hockey", "Soccer", "Tennis",
            "Wrestling", "Racing", "Golf", "Boxing", "UFC/MMA", "Pokemon",
            "Magic", "Metazoo", "Yugioh", "Fortnite", "Dragonballz",
            "Entertainment", "Swimming", "Softball", "PopCulture", "Flesh and Blood"
        ]
        assert len(categories) == 22
        assert len(VALID_CATEGORIES) == 22

        for cat in categories:
            card = CardRecord(
                player="Athlete",
                year="2024",
                set_name="Set",
                category=cat,
            )
            assert card.category == cat

    def test_category_case_insensitivity_and_aliases(self):
        """Tests case normalization and common aliases for categories."""
        aliases = {
            "basketball": "Basketball",
            "pokemon": "Pokemon",
            "ufc": "UFC/MMA",
            "mma": "UFC/MMA",
            "pop culture": "PopCulture",
            "popculture": "PopCulture",
            "dragon ball z": "Dragonballz",
            "flesh & blood": "Flesh and Blood",
        }
        for alias, expected in aliases.items():
            card = CardRecord(
                player="Test",
                year="2024",
                set_name="Set",
                category=alias,
            )
            assert card.category == expected

    def test_invalid_category_raises_error(self):
        """Tests that categories outside the 22 permitted list raise ValidationError."""
        for invalid in ["Cricket", "Badminton", "TCG", "Other", "Sports"]:
            with pytest.raises(ValidationError):
                CardRecord(
                    player="Test",
                    year="2024",
                    set_name="Set",
                    category=invalid,
                )

    def test_raw_card_with_slab_serial_rejected(self):
        """Verifies that Raw condition cards cannot have a slab serial number."""
        with pytest.raises(ValidationError, match="Slab serial number must be blank"):
            CardRecord(
                player="Luka Doncic",
                year="2018",
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
                condition="Raw",
                slab_serial_number="12345678",
            )

    def test_graded_card_with_hyphen_rejected(self):
        """Verifies that hyphenated graded condition (e.g. PSA-10) is rejected."""
        with pytest.raises(ValidationError, match="must not contain hyphens"):
            CardRecord(
                player="Luka Doncic",
                year="2018",
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
                condition="PSA-10",
                slab_serial_number="12345678",
            )

    def test_leading_zero_card_number_preservation(self):
        """Verifies that leading zeros and alphanumeric card numbers are preserved as strings."""
        test_numbers = ["007", "04/102", "000", "001", "RC-05", "NNO", "#24", "1/1"]
        for num in test_numbers:
            card = CardRecord(
                player="Test",
                year="2024",
                set_name="Set",
                category=CardCategory.BASEBALL,
                card_number=num,
            )
            assert card.card_number == num
            assert isinstance(card.card_number, str)

        # Integer input coerced to string with leading characters intact
        card_from_int = CardRecord(
            player="Test",
            year="2024",
            set_name="Set",
            category=CardCategory.BASEBALL,
            card_number=7,
        )
        assert card_from_int.card_number == "7"

    def test_multi_year_normalization(self):
        """Verifies multi-year strings like '2020-21' are normalized to 4-digit '2020'."""
        card = CardRecord(
            player="Test",
            year="2020-21",
            set_name="Set",
            category=CardCategory.BASKETBALL,
        )
        assert card.year == "2020"

    def test_date_normalization(self):
        """Verifies ISO and unpadded dates normalize to MM/DD/YYYY."""
        card1 = CardRecord(
            player="Test",
            year="2024",
            set_name="Set",
            category=CardCategory.BASEBALL,
            date_purchased="2026-08-24",
        )
        assert card1.date_purchased == "08/24/2026"

        card2 = CardRecord(
            player="Test",
            year="2024",
            set_name="Set",
            category=CardCategory.BASEBALL,
            date_purchased="8/4/2026",
        )
        assert card2.date_purchased == "08/04/2026"

    def test_negative_exclusion_prohibited_on_raw(self):
        """Verifies negative exclusion search queries (-BGS, -SGC) on Raw cards raise error."""
        with pytest.raises(ValidationError, match="Negative exclusions are forbidden"):
            CardRecord(
                player="Test",
                year="2024",
                set_name="Set",
                category=CardCategory.BASEBALL,
                condition="Raw",
                query="2024 Set Test Raw -BGS -SGC",
            )

    def test_variation_auto_flags_ai_status(self):
        """Verifies that non-empty variation auto-flags status to REVIEW VARIATION."""
        card = CardRecord(
            player="Caitlin Clark",
            year="2024",
            set_name="Panini Instant",
            variation="Base Parallel",
            category=CardCategory.BASKETBALL,
        )
        assert card.ai_status == AIStatus.REVIEW_VARIATION

    def test_unicode_and_special_character_preservation(self):
        """Verifies Unicode diacritics and Asian characters are preserved byte-for-byte."""
        names = [
            "Ronald Acuña Jr.",
            "Luka Dončić",
            "Alexis Lafrenière",
            "Shohei Ohtani (大谷 翔平)",
            "Karl-Anthony Towns",
            "De'Aaron Fox",
        ]
        for name in names:
            card = CardRecord(
                player=name,
                year="2024",
                set_name="Topps Chrome",
                category=CardCategory.BASEBALL,
            )
            assert card.player == name

    def test_format_notes_formatting_and_validation(self):
        """Verifies format_notes produces [Parent_Image_ID]-[Child_Card_ID]."""
        assert format_notes(8492, 105) == "8492-105"
        assert format_notes("8492", "101") == "8492-101"
        assert format_notes(42, 5) == "0042-005"
        assert format_notes("8492-105", "") == "8492-105"

        with pytest.raises(ValueError):
            format_notes("invalid", "105")

        with pytest.raises(ValueError):
            format_notes(-5, 10)

    def test_calculate_query_variations(self):
        """Verifies calculate_query output formats."""
        q1 = calculate_query("2020", "Panini Prizm", "Luka Doncic", "Silver Prizm", "PSA 10")
        assert q1 == "2020 Panini Prizm Luka Doncic Silver Prizm PSA 10"

        q2 = calculate_query(2019, "Topps Chrome", "Ronald Acuna Jr.", "", "Raw")
        assert q2 == "2019 Topps Chrome Ronald Acuna Jr. Raw"

        q3 = calculate_query("1999", "Pokemon Base Set", "Charizard", "1st Edition Holo", "BGS 9.5")
        assert q3 == "1999 Pokemon Base Set Charizard 1st Edition Holo BGS 9.5"


# ============================================================================
# Tier 2: SQLite DDL Constraints & WAL Configuration Tests
# ============================================================================

class TestSQLiteConstraints:

    def test_init_db_creates_tables_and_indexes(self, test_db_path):
        """Verifies table cards and all indexes are created."""
        with get_db_connection(test_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cards';")
            assert cursor.fetchone() is not None

            cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
            indexes = [r[0] for r in cursor.fetchall()]
            assert "idx_cards_ai_status" in indexes
            assert "idx_cards_category" in indexes
            assert "idx_cards_player" in indexes
            assert "idx_cards_year_set" in indexes
            assert "idx_cards_notes" in indexes
            assert "idx_cards_query" in indexes

    def test_wal_journal_mode(self, test_db_path):
        """Verifies WAL journal mode is enabled on the database."""
        with get_db_connection(test_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal"

    def test_db_rejects_raw_with_slab_serial(self, test_db_path):
        """Verifies SQLite CHECK constraint check_raw_no_slab."""
        with get_db_connection(test_db_path) as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("""
                INSERT INTO cards (
                    date_purchased, quantity, player, year, set_name, variation, card_number,
                    category, condition, slab_serial_number, investment, estimated_value,
                    ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                ) VALUES (
                    '08/24/2026', 1, 'Luka Doncic', '2020', 'Panini Prizm', '', '75',
                    'Basketball', 'Raw', '12345678', 10.0, 20.0,
                    '', '2020 Panini Prizm Luka Doncic Raw', '8492-101', '', '', NULL, '', '', 'CLEARED'
                );
                """)

    def test_db_rejects_invalid_category(self, test_db_path):
        """Verifies SQLite CHECK constraint on category."""
        with get_db_connection(test_db_path) as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("""
                INSERT INTO cards (
                    date_purchased, quantity, player, year, set_name, variation, card_number,
                    category, condition, slab_serial_number, investment, estimated_value,
                    ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                ) VALUES (
                    '08/24/2026', 1, 'Player', '2020', 'Set', '', '1',
                    'Badminton', 'Raw', '', 0.0, 0.0,
                    '', 'Query', '', '', '', NULL, '', '', 'CLEARED'
                );
                """)

    def test_db_rejects_negative_quantity_or_investment(self, test_db_path):
        """Verifies SQLite CHECK constraint on quantity and investment."""
        with get_db_connection(test_db_path) as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("""
                INSERT INTO cards (
                    date_purchased, quantity, player, year, set_name, variation, card_number,
                    category, condition, slab_serial_number, investment, estimated_value,
                    ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                ) VALUES (
                    '08/24/2026', 0, 'Player', '2020', 'Set', '', '1',
                    'Baseball', 'Raw', '', 0.0, 0.0,
                    '', 'Query', '', '', '', NULL, '', '', 'CLEARED'
                );
                """)

    def test_db_rejects_raw_negative_query_exclusions(self, test_db_path):
        """Verifies SQLite CHECK constraint check_raw_no_negative_exclusions."""
        with get_db_connection(test_db_path) as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("""
                INSERT INTO cards (
                    date_purchased, quantity, player, year, set_name, variation, card_number,
                    category, condition, slab_serial_number, investment, estimated_value,
                    ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                ) VALUES (
                    '08/24/2026', 1, 'Player', '2020', 'Set', '', '1',
                    'Baseball', 'Raw', '', 0.0, 0.0,
                    '', '2020 Set Player Raw -BGS', '', '', '', NULL, '', '', 'CLEARED'
                );
                """)

    def test_db_rejects_invalid_ai_status(self, test_db_path):
        """Verifies SQLite CHECK constraint on ai_status."""
        with get_db_connection(test_db_path) as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("""
                INSERT INTO cards (
                    date_purchased, quantity, player, year, set_name, variation, card_number,
                    category, condition, slab_serial_number, investment, estimated_value,
                    ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                ) VALUES (
                    '08/24/2026', 1, 'Player', '2020', 'Set', '', '1',
                    'Baseball', 'Raw', '', 0.0, 0.0,
                    '', 'Query', '', '', '', NULL, '', '', 'INVALID_STATUS'
                );
                """)


# ============================================================================
# Tier 3: Database CRUD Operations Tests
# ============================================================================

class TestDatabaseCRUD:

    def test_insert_and_get_card_by_id(self, test_db_path, sample_card_dict):
        """Verifies inserting a card and retrieving all 21 variables."""
        card_id = insert_card(sample_card_dict, db_path=test_db_path)
        assert card_id == 1

        card = get_card_by_id(card_id, db_path=test_db_path)
        assert card is not None
        assert card["id"] == 1
        assert card["player"] == "Shohei Ohtani"
        assert card["card_number"] == "007"
        assert card["condition"] == "PSA 10"
        assert card["slab_serial_number"] == "84729104"
        assert card["investment"] == 150.00
        assert card["estimated_value"] == 320.00
        assert card["notes"] == "8492-105"
        assert card["query"] == "2023 Topps Chrome Shohei Ohtani Refractor PSA 10"
        assert card["ai_status"] == "REVIEW VARIATION"

    def test_flexible_argument_orders(self, test_db_path, sample_card_dict):
        """Verifies functions support (card, db_path) and (db_path, card)."""
        id1 = insert_card(sample_card_dict, test_db_path)
        id2 = insert_card(test_db_path, sample_card_dict)
        assert id1 == 1
        assert id2 == 2

        card1 = get_card_by_id(test_db_path, id1)
        card2 = get_card_by_id(id2, test_db_path)
        assert card1 is not None
        assert card2 is not None

    def test_update_card_and_query_resynthesis(self, test_db_path, sample_card_dict):
        """Verifies update_card modifies fields and re-synthesizes query."""
        card_id = insert_card(sample_card_dict, test_db_path)

        # Update player name and variation
        success = update_card(
            card_id,
            {"player": "Shohei Ohtani (MVP)", "variation": "Gold Refractor /50", "estimated_value": 850.00},
            db_path=test_db_path
        )
        assert success is True

        updated = get_card(card_id, db_path=test_db_path)
        assert updated["player"] == "Shohei Ohtani (MVP)"
        assert updated["variation"] == "Gold Refractor /50"
        assert updated["estimated_value"] == 850.00
        assert updated["query"] == "2023 Topps Chrome Shohei Ohtani (MVP) Gold Refractor /50 PSA 10"

    def test_update_card_status(self, test_db_path, sample_card_dict):
        """Verifies update_card_status modifies ai_status."""
        card_id = insert_card(sample_card_dict, test_db_path)
        assert update_card_status(card_id, "REVIEW VARIATION", test_db_path) is True

        card = get_card(card_id, test_db_path)
        assert card["ai_status"] == "REVIEW VARIATION"

    def test_delete_card(self, test_db_path, sample_card_dict):
        """Verifies deleting a card."""
        card_id = insert_card(sample_card_dict, test_db_path)
        assert delete_card(card_id, test_db_path) is True
        assert get_card(card_id, test_db_path) is None
        assert delete_card(card_id, test_db_path) is False

    def test_list_cards_and_filtering(self, test_db_path):
        """Verifies list_cards / get_all_cards with various filters."""
        c1 = {"player": "Luka Doncic", "year": "2020", "set_name": "Prizm", "category": "Basketball", "condition": "PSA 10", "slab_serial_number": "111", "ai_status": "CLEARED"}
        c2 = {"player": "Michael Jordan", "year": "1986", "set_name": "Fleer", "category": "Basketball", "condition": "Raw", "ai_status": "REVIEW VARIATION"}
        c3 = {"player": "Shohei Ohtani", "year": "2018", "set_name": "Bowman", "category": "Baseball", "condition": "Raw", "ai_status": "CLEARED"}
        insert_cards_batch([c1, c2, c3], test_db_path)

        # Filter by category
        bball = list_cards(test_db_path, filters={"category": "Basketball"})
        assert len(bball) == 2

        # Filter by status
        cleared = list_cards(test_db_path, filters={"ai_status": "CLEARED"})
        assert len(cleared) == 2

        # Search by player keyword
        jordan = list_cards(test_db_path, filters={"search": "Jordan"})
        assert len(jordan) == 1
        assert jordan[0]["player"] == "Michael Jordan"

    def test_get_cards_for_export(self, test_db_path):
        """Verifies get_cards_for_export filters by status and orders by id ASC."""
        c1 = {"player": "Card 1", "year": "2020", "set_name": "Set", "category": "Baseball", "ai_status": "CLEARED"}
        c2 = {"player": "Card 2", "year": "2020", "set_name": "Set", "category": "Baseball", "ai_status": "REVIEW VARIATION"}
        c3 = {"player": "Card 3", "year": "2020", "set_name": "Set", "category": "Baseball", "ai_status": "CLEARED"}
        insert_cards_batch([c1, c2, c3], test_db_path)

        export_cleared = get_cards_for_export(status_filter="CLEARED", db_path=test_db_path)
        assert len(export_cleared) == 2
        assert export_cleared[0]["id"] < export_cleared[1]["id"]
        assert export_cleared[0]["player"] == "Card 1"
        assert export_cleared[1]["player"] == "Card 3"

        export_all = get_cards_for_export(status_filter="ALL", db_path=test_db_path)
        assert len(export_all) == 3

    def test_get_summary_stats(self, test_db_path):
        """Verifies get_summary_stats aggregates totals accurately."""
        c1 = {"player": "Card 1", "year": "2020", "set_name": "Set", "category": "Basketball", "investment": 100.00, "estimated_value": 250.00, "ai_status": "CLEARED"}
        c2 = {"player": "Card 2", "year": "2020", "set_name": "Set", "category": "Pokemon", "investment": 50.00, "estimated_value": 150.00, "ai_status": "REVIEW VARIATION"}
        insert_cards_batch([c1, c2], test_db_path)

        stats = get_summary_stats(test_db_path)
        assert stats["total_cards"] == 2
        assert stats["total_investment"] == 150.00
        assert stats["total_estimated_value"] == 400.00
        assert stats["count_by_category"] == {"Basketball": 1, "Pokemon": 1}
        assert stats["count_by_ai_status"] == {"CLEARED": 1, "REVIEW VARIATION": 1}

    def test_get_next_child_id(self, test_db_path):
        """Verifies get_next_child_id increments for parent image notes."""
        # Initial call for parent 8492
        assert get_next_child_id(8492, test_db_path) == 101

        # Insert cards with notes 8492-101 and 8492-102
        c1 = {"player": "C1", "year": "2020", "set_name": "S", "category": "Baseball", "notes": "8492-101"}
        c2 = {"player": "C2", "year": "2020", "set_name": "S", "category": "Baseball", "notes": "8492-102"}
        c3 = {"player": "C3", "year": "2020", "set_name": "S", "category": "Baseball", "notes": "8493-101"}
        insert_cards_batch([c1, c2, c3], test_db_path)

        assert get_next_child_id(8492, test_db_path) == 103
        assert get_next_child_id(8493, test_db_path) == 102
        assert get_next_child_id(8494, test_db_path) == 101

    def test_clear_staging_table(self, test_db_path, sample_card_dict):
        """Verifies clear_staging_table empties the cards table."""
        insert_card(sample_card_dict, test_db_path)
        assert get_staging_count(test_db_path) == 1
        deleted = clear_staging_table(test_db_path)
        assert deleted == 1
        assert get_staging_count(test_db_path) == 0


# ============================================================================
# Tier 4: Batch, Concurrency, and Circuit Breaker Tests
# ============================================================================

class TestBatchAndConcurrency:

    def test_insert_cards_batch_atomic_success(self, test_db_path):
        """Verifies batch insertion of 25 cards in single transaction."""
        batch = [
            {
                "player": f"Player {i}",
                "year": "2024",
                "set_name": "Topps Series 1",
                "card_number": f"{i:03d}",
                "category": "Baseball",
                "condition": "Raw",
            }
            for i in range(1, 26)
        ]
        ids = bulk_insert_cards(test_db_path, batch)
        assert len(ids) == 25
        assert get_card_count(test_db_path) == 25

    def test_insert_cards_batch_atomic_rollback_on_failure(self, test_db_path):
        """Verifies that invalid card in batch rolls back all items."""
        batch = [
            {"player": "Valid Player", "year": "2024", "set_name": "Set", "category": "Baseball"},
            {"player": "Invalid Player", "year": "2024", "set_name": "Set", "category": "InvalidCategory"},
        ]
        with pytest.raises(ValidationError):
            insert_cards_batch(batch, test_db_path)

        assert get_card_count(test_db_path) == 0

    def test_batch_insert_chunking_over_500(self, test_db_path):
        """Verifies inserting 600 cards chunks into sub-batches of 500 without failure."""
        batch = [
            {
                "player": f"Bulk Athlete {i}",
                "year": "2024",
                "set_name": "Mass Set",
                "card_number": f"{i:04d}",
                "category": "Hockey",
                "condition": "Raw",
            }
            for i in range(1, 601)
        ]
        ids = insert_cards_batch(batch, test_db_path, chunk_size=500)
        assert len(ids) == 600
        assert get_card_count(test_db_path) == 600

    def test_circuit_breaker_check(self, test_db_path):
        """Verifies check_circuit_breaker reports staging count and tripped boolean."""
        cb_empty = check_circuit_breaker(test_db_path, threshold=500)
        assert cb_empty["total_staged"] == 0
        assert cb_empty["circuit_breaker_tripped"] is False

        # Insert 500 cards
        batch = [
            {"player": f"P {i}", "year": "2024", "set_name": "S", "category": "Soccer"}
            for i in range(500)
        ]
        insert_cards_batch(batch, test_db_path)

        cb_full = check_circuit_breaker(test_db_path, threshold=500)
        assert cb_full["total_staged"] == 500
        assert cb_full["circuit_breaker_tripped"] is True

    def test_api_capture_card(self, test_db_path):
        """Verifies capture_card_from_api executes end-to-end API payload ingestion."""
        payload = {
            "player": "Erling Haaland",
            "year": "2020",
            "set_name": "Topps Chrome Bundesliga",
            "variation": "Refractor",
            "card_number": "001",
            "category": "Soccer",
            "condition": "PSA 10",
            "slab_serial_number": "9918234",
            "investment": 200.0,
            "estimated_value": 450.0,
            "notes": "8492-101",
        }
        res = capture_card_from_api(payload, db_path=test_db_path)
        assert res["status"] == "success"
        assert res["card_id"] == 1
        assert "Erling Haaland" in res["query"]
        assert res["notes"] == "8492-101"

    def test_sqlite_wal_multi_threaded_concurrency(self, test_db_path):
        """Verifies multi-threaded concurrency with concurrent readers and writers under WAL mode."""
        errors = []

        def writer_task(worker_id: int):
            try:
                for i in range(10):
                    card = {
                        "player": f"Worker {worker_id} Player {i}",
                        "year": "2024",
                        "set_name": "Panini Select",
                        "category": "Football",
                        "condition": "Raw",
                        "notes": f"1000-{worker_id:03d}",
                    }
                    insert_card(card, test_db_path)
            except Exception as e:
                errors.append(f"Writer error: {e}")

        def reader_task():
            try:
                for _ in range(20):
                    get_all_cards(limit=100, db_path=test_db_path)
            except Exception as e:
                errors.append(f"Reader error: {e}")

        threads = []
        for w in range(4):
            threads.append(threading.Thread(target=writer_task, args=(w,)))
        for _ in range(4):
            threads.append(threading.Thread(target=reader_task))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrency errors: {errors}"
        assert get_card_count(test_db_path) == 40


# ============================================================================
# Tier 5: Mock Fixture Integration Tests
# ============================================================================

class TestMockFixtures:

    def test_load_and_insert_mock_fixtures_json(self, test_db_path):
        """Verifies that mock_card_data.json can be loaded and batch-inserted with 100% validity."""
        fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "mock_card_data.json")
        assert os.path.exists(fixture_path), f"Fixture not found at {fixture_path}"

        with open(fixture_path, "r", encoding="utf-8") as f:
            cards = json.load(f)

        assert len(cards) >= 10, f"Expected at least 10 cards in fixture, found {len(cards)}"

        ids = insert_cards_batch(cards, test_db_path)
        assert len(ids) == len(cards)
        assert get_card_count(test_db_path) == len(cards)

        # Spot check first card
        c1 = get_card_by_id(ids[0], test_db_path)
        assert c1["player"] == "Luka Dončić"
        assert c1["category"] == "Basketball"
        assert c1["card_number"] == "75"

        # Spot check card with leading zero
        c2 = get_card_by_id(ids[1], test_db_path)
        assert c2["player"] == "Ronald Acuña Jr."
        assert c2["card_number"] == "001"

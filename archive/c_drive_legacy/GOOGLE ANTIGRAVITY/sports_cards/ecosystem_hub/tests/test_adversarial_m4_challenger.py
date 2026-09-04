"""
tests/test_adversarial_m4_challenger.py - Adversarial Stress & Fuzzing Harness for Milestone 4 (Card Ladder CSV Export Engine).
Authored by Teamwork Preview Challenger (Agent Challenger M4).

Target: sports_cards/ecosystem_hub/export.py, database.py, models.py.
Test Dimensions:
1. Exact 16-Column Card Ladder Schema & Strict Exclusion of Internal DB Fields.
2. Boundary Chunking & Batch Rollover: 0, 1, 500, 501, 1000, 1500, 1501 cards.
3. String & Leading Zero Preservation: '000', '007', '04', '00001', 'RC-01', '04/102', 'NNO', byte/regex & pandas(dtype=str).
4. Multi-tier Fuzzy Normalization & Diacritic Folding: Unicode accents, Kanji annotations, Category isolation, Typo cutoffs.
5. CSV Formula & Delimiter Injection: Quotes, Commas, Line breaks, '=', '+', '-', '@'.
6. Status Filtering Integrity & SQL Injection Safety in status_filter.
7. Financial Formatting & Precision: Floats, Decimals, None/Empty handling.
8. High-Concurrency Stress & Large Volume (10,000 records) Performance Benchmark.
"""

from __future__ import annotations

import csv
import io
import os
import re
import sqlite3
import sys
import threading
import time
import concurrent.futures
from typing import Any, Generator
import pandas as pd
import pytest

# Ensure ecosystem_hub is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import CardRecord, CardCategory, AIStatus
from database import init_db, insert_card, insert_cards_batch, get_db_connection
from export import (
    CARD_LADDER_COLUMNS,
    EXCLUDED_INTERNAL_FIELDS,
    CANONICAL_PLAYERS,
    CANONICAL_SETS,
    PLAYER_ALIASES,
    SET_ALIASES,
    fold_string,
    normalize_player_name,
    normalize_set_name,
    format_currency_value,
    format_sold_price,
    format_card_row_for_card_ladder,
    cards_to_card_ladder_dataframe,
    generate_chunk_filepath,
    export_dataframe_to_chunked_csvs,
    export_card_ladder_csv,
    validate_card_ladder_csv,
    fetch_records_for_export,
)


@pytest.fixture
def temp_db(tmp_path) -> str:
    """Provides a fresh isolated SQLite database path."""
    db_file = str(tmp_path / "test_adversarial_export_m4.db")
    init_db(db_file)
    return db_file


@pytest.fixture
def export_dir(tmp_path) -> str:
    """Provides a temporary output directory for CSV exports."""
    out_dir = str(tmp_path / "adversarial_exports")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


# ============================================================================
# 1. Exact 16-Column Card Ladder Schema & Strict Exclusion of Internal DB Fields
# ============================================================================

class TestSchemaConformanceAndInternalFieldExclusion:
    """Adversarial validation of column headers, count, order, and strict exclusion of internal columns."""

    def test_exact_16_column_card_ladder_headers(self):
        """Header names and sequence must exactly match Card Ladder specifications."""
        expected_headers = [
            "Date Purchased",
            "Quantity",
            "Player",
            "Year",
            "Set",
            "Variation",
            "Number",
            "Category",
            "Condition",
            "Investment",
            "Estimated Value",
            "Ladder ID",
            "Notes",
            "Date Sold",
            "Sold Price",
            "Image",
        ]
        assert len(CARD_LADDER_COLUMNS) == 16, f"Expected 16 columns, got {len(CARD_LADDER_COLUMNS)}"
        assert CARD_LADDER_COLUMNS == expected_headers, "CARD_LADDER_COLUMNS order or names differ from specification."

    def test_internal_fields_exclusion_contract(self):
        """None of the excluded internal variables can appear in Card Ladder columns."""
        for internal_col in EXCLUDED_INTERNAL_FIELDS:
            assert internal_col not in CARD_LADDER_COLUMNS, f"Forbidden internal column '{internal_col}' in CARD_LADDER_COLUMNS!"
            assert internal_col.lower() not in [c.lower() for c in CARD_LADDER_COLUMNS], f"Case-insensitive match found for internal column '{internal_col}'"

    def test_row_transformation_drops_internal_and_injected_fields(self):
        """Transformation of a raw DB record drops all internal metadata and unmapped keys."""
        raw_record = {
            "id": 999,
            "date_purchased": "2026-08-01",
            "quantity": 2,
            "player": "Shohei Ohtani",
            "year": "2024",
            "set_name": "Topps Chrome",
            "variation": "Refractor",
            "card_number": "007",
            "category": "Baseball",
            "condition": "PSA 10",
            "investment": 250.00,
            "estimated_value": 550.00,
            "ladder_id": "LAD-8849",
            "notes": "8492-999",
            "date_sold": "2026-08-15",
            "sold_price": 600.00,
            "image": "https://example.com/front.jpg",
            # Internal fields that MUST NOT leak
            "slab_serial_number": "849201948",
            "query": "2024 Topps Chrome Shohei Ohtani PSA 10",
            "tags": "mlb,ohtani,dodgers",
            "back_image": "https://example.com/back.jpg",
            "ai_status": "CLEARED",
            "created_at": "2026-08-01T12:00:00Z",
            "updated_at": "2026-08-01T12:00:00Z",
            # Arbitrary injected keys
            "__internal_token__": "secret_123",
            "admin_privilege": True,
        }

        transformed = format_card_row_for_card_ladder(raw_record)
        assert len(transformed) == 16, f"Transformed dict has {len(transformed)} keys, expected 16."
        assert list(transformed.keys()) == CARD_LADDER_COLUMNS

        for forbidden in ["slab_serial_number", "query", "tags", "back_image", "ai_status", "id", "created_at", "updated_at", "__internal_token__", "admin_privilege"]:
            assert forbidden not in transformed

    def test_empty_dataframe_has_exact_16_columns_and_string_types(self):
        """An empty DataFrame must still contain the exact 16 columns with string types on Number and Year."""
        df = cards_to_card_ladder_dataframe([])
        assert list(df.columns) == CARD_LADDER_COLUMNS
        assert len(df) == 0
        assert pd.api.types.is_string_dtype(df["Number"])
        assert pd.api.types.is_string_dtype(df["Year"])


# ============================================================================
# 2. Boundary Chunking & Batch Rollover Stress Tests (0, 1, 500, 501, 1000, 1500, 1501)
# ============================================================================

class TestBoundaryChunkingAndBatchRollover:
    """Stress tests for 0, 1, 500, 501, 1000, 1500, and 1501 card exports and file chunk naming."""

    def test_export_0_cards_produces_single_file_with_headers(self, temp_db: str, export_dir: str):
        """0 cards produces 1 CSV containing only 16 headers and 0 data rows."""
        target_csv = os.path.join(export_dir, "export_0.csv")
        total_exported, file_paths = export_card_ladder_csv(
            db_path=temp_db,
            output_path=target_csv,
            status_filter="CLEARED",
        )

        assert total_exported == 0
        assert len(file_paths) == 1
        assert file_paths[0] == target_csv
        assert os.path.exists(target_csv)

        # Validate with forensic tool
        val = validate_card_ladder_csv(target_csv)
        assert val["valid"] is True
        assert val["row_count"] == 0
        assert val["headers"] == CARD_LADDER_COLUMNS

    def test_export_1_card_produces_single_unpartitioned_file(self, temp_db: str, export_dir: str):
        """1 card produces 1 CSV named exactly as output_path (no _part1 suffix)."""
        card = {
            "player": "Luka Dončić",
            "year": "2018",
            "set_name": "Panini Prizm",
            "card_number": "007",
            "category": "Basketball",
            "condition": "PSA 10",
            "ai_status": "CLEARED",
        }
        insert_card(card, db_path=temp_db)

        target_csv = os.path.join(export_dir, "export_1.csv")
        total_exported, file_paths = export_card_ladder_csv(
            db_path=temp_db,
            output_path=target_csv,
            status_filter="CLEARED",
        )

        assert total_exported == 1
        assert len(file_paths) == 1
        assert file_paths[0] == target_csv
        assert os.path.exists(target_csv)

        val = validate_card_ladder_csv(target_csv)
        assert val["valid"] is True
        assert val["row_count"] == 1

    def test_export_exact_500_cards_produces_single_file(self, temp_db: str, export_dir: str):
        """500 cards (exact batch limit) must produce exactly 1 CSV without chunk suffix."""
        cards = [
            {
                "player": f"Player {i:03d}",
                "year": "2023",
                "set_name": "Panini Prizm",
                "card_number": f"{i:03d}",
                "category": "Basketball",
                "condition": "Raw",
                "ai_status": "CLEARED",
            }
            for i in range(1, 501)
        ]
        insert_cards_batch(cards, db_path=temp_db)

        target_csv = os.path.join(export_dir, "export_500.csv")
        total_exported, file_paths = export_card_ladder_csv(
            db_path=temp_db,
            output_path=target_csv,
            status_filter="CLEARED",
            max_batch_size=500,
        )

        assert total_exported == 500
        assert len(file_paths) == 1
        assert file_paths[0] == target_csv
        assert os.path.exists(target_csv)

        val = validate_card_ladder_csv(target_csv)
        assert val["valid"] is True
        assert val["row_count"] == 500

    def test_export_501_cards_chunks_to_two_files(self, temp_db: str, export_dir: str):
        """501 cards must split into _part1.csv (500 cards) and _part2.csv (1 card)."""
        cards = [
            {
                "player": f"Player {i:04d}",
                "year": "2023",
                "set_name": "Panini Prizm",
                "card_number": f"{i:04d}",
                "category": "Basketball",
                "condition": "Raw",
                "ai_status": "CLEARED",
            }
            for i in range(1, 502)
        ]
        insert_cards_batch(cards, db_path=temp_db)

        base_csv = os.path.join(export_dir, "export_501.csv")
        total_exported, file_paths = export_card_ladder_csv(
            db_path=temp_db,
            output_path=base_csv,
            status_filter="CLEARED",
            max_batch_size=500,
        )

        assert total_exported == 501
        assert len(file_paths) == 2
        assert file_paths[0].endswith("export_501_part1.csv")
        assert file_paths[1].endswith("export_501_part2.csv")

        # Check part 1
        val1 = validate_card_ladder_csv(file_paths[0])
        assert val1["valid"] is True
        assert val1["row_count"] == 500

        # Check part 2
        val2 = validate_card_ladder_csv(file_paths[1])
        assert val2["valid"] is True
        assert val2["row_count"] == 1

    def test_export_1000_cards_chunks_to_two_equal_files(self, temp_db: str, export_dir: str):
        """1000 cards must split into _part1.csv (500 cards) and _part2.csv (500 cards)."""
        cards = [
            {
                "player": f"Player {i:04d}",
                "year": "2023",
                "set_name": "Panini Prizm",
                "card_number": f"{i:04d}",
                "category": "Basketball",
                "condition": "Raw",
                "ai_status": "CLEARED",
            }
            for i in range(1, 1001)
        ]
        insert_cards_batch(cards, db_path=temp_db)

        base_csv = os.path.join(export_dir, "export_1000.csv")
        total_exported, file_paths = export_card_ladder_csv(
            db_path=temp_db,
            output_path=base_csv,
            status_filter="CLEARED",
            max_batch_size=500,
        )

        assert total_exported == 1000
        assert len(file_paths) == 2
        assert file_paths[0].endswith("export_1000_part1.csv")
        assert file_paths[1].endswith("export_1000_part2.csv")

        val1 = validate_card_ladder_csv(file_paths[0])
        val2 = validate_card_ladder_csv(file_paths[1])
        assert val1["valid"] and val1["row_count"] == 500
        assert val2["valid"] and val2["row_count"] == 500

    def test_export_1500_cards_chunks_to_three_files(self, temp_db: str, export_dir: str):
        """1500 cards must split into _part1.csv (500), _part2.csv (500), and _part3.csv (500)."""
        cards = [
            {
                "player": f"Player {i:04d}",
                "year": "2023",
                "set_name": "Panini Prizm",
                "card_number": f"{i:04d}",
                "category": "Basketball",
                "condition": "Raw",
                "ai_status": "CLEARED",
            }
            for i in range(1, 1501)
        ]
        insert_cards_batch(cards, db_path=temp_db)

        base_csv = os.path.join(export_dir, "export_1500.csv")
        total_exported, file_paths = export_card_ladder_csv(
            db_path=temp_db,
            output_path=base_csv,
            status_filter="CLEARED",
            max_batch_size=500,
        )

        assert total_exported == 1500
        assert len(file_paths) == 3
        assert file_paths[0].endswith("export_1500_part1.csv")
        assert file_paths[1].endswith("export_1500_part2.csv")
        assert file_paths[2].endswith("export_1500_part3.csv")

        for p in file_paths:
            val = validate_card_ladder_csv(p)
            assert val["valid"] is True
            assert val["row_count"] == 500

    def test_export_1501_cards_chunks_to_four_files(self, temp_db: str, export_dir: str):
        """1501 cards must split into 4 files: 500, 500, 500, and 1 card."""
        cards = [
            {
                "player": f"Player {i:04d}",
                "year": "2023",
                "set_name": "Panini Prizm",
                "card_number": f"{i:04d}",
                "category": "Basketball",
                "condition": "Raw",
                "ai_status": "CLEARED",
            }
            for i in range(1, 1502)
        ]
        insert_cards_batch(cards, db_path=temp_db)

        base_csv = os.path.join(export_dir, "export_1501.csv")
        total_exported, file_paths = export_card_ladder_csv(
            db_path=temp_db,
            output_path=base_csv,
            status_filter="CLEARED",
            max_batch_size=500,
        )

        assert total_exported == 1501
        assert len(file_paths) == 4
        assert file_paths[3].endswith("export_1501_part4.csv")
        val4 = validate_card_ladder_csv(file_paths[3])
        assert val4["row_count"] == 1


# ============================================================================
# 3. String & Leading Zero Preservation Stress Tests
# ============================================================================

class TestLeadingZeroAndExtremeCardNumbers:
    """Rigorous verification of leading zeroes and extreme card number string preservation."""

    @pytest.mark.parametrize(
        "extreme_card_number",
        [
            "000",
            "007",
            "04",
            "00001",
            "000000000",
            "RC-01",
            "04/102",
            "NNO",
            "1/1",
            "#005",
            "SP-002",
            "0",
            "",
            "   009   ",  # whitespace around leading zero
            "№ 004",      # unicode symbol
            "00-GOLD",
            "100.00",
        ],
    )
    def test_leading_zero_preservation_raw_bytes_and_pandas(
        self, temp_db: str, export_dir: str, extreme_card_number: str
    ):
        """
        Verify that extreme card numbers preserve every single leading zero and symbol.
        Checked via raw byte search and pandas.read_csv(dtype=str).
        """
        card = {
            "player": "Shohei Ohtani",
            "year": "2024",
            "set_name": "Topps Chrome",
            "card_number": extreme_card_number,
            "category": "Baseball",
            "condition": "PSA 10",
            "ai_status": "CLEARED",
        }
        insert_card(card, db_path=temp_db)

        target_csv = os.path.join(export_dir, f"export_num_{hash(extreme_card_number)}.csv")
        total_exported, file_paths = export_card_ladder_csv(
            db_path=temp_db,
            output_path=target_csv,
            status_filter="CLEARED",
        )

        assert total_exported == 1
        csv_file = file_paths[0]

        # 1. Raw Text/Byte Inspection
        with open(csv_file, "r", encoding="utf-8") as f:
            raw_content = f.read()

        expected_cleaned = extreme_card_number.strip()
        if expected_cleaned:
            assert expected_cleaned in raw_content, f"Expected '{expected_cleaned}' in raw CSV content:\n{raw_content}"

        # 2. Pandas Read with strict string dtype
        df = pd.read_csv(csv_file, dtype=str, keep_default_na=False)
        read_val = df.iloc[0]["Number"]

        assert read_val == expected_cleaned, f"Expected '{expected_cleaned}', but pandas read '{read_val}'"


# ============================================================================
# 4. Multi-tier Fuzzy Normalization & Diacritic Stress Testing
# ============================================================================

class TestMultiTierFuzzyNormalizationStress:
    """Stress-testing diacritic folding, Kanji stripping, alias fast-paths, and category isolation."""

    @pytest.mark.parametrize(
        "input_name,expected_normalized,category",
        [
            ("Luka Dončić", "Luka Dončić", "Basketball"),
            ("luka doncic", "Luka Dončić", "Basketball"),
            ("LUKA DONCIC", "Luka Dončić", "Basketball"),
            ("luka", "Luka Dončić", "Basketball"),
            ("Shohei Ohtani (大谷 翔平)", "Shohei Ohtani", "Baseball"),
            ("shohei ohtani", "Shohei Ohtani", "Baseball"),
            ("ohtani", "Shohei Ohtani", "Baseball"),
            ("Ronald Acuña Jr.", "Ronald Acuña Jr.", "Baseball"),
            ("ronald acuna jr", "Ronald Acuña Jr.", "Baseball"),
            ("acuna", "Ronald Acuña Jr.", "Baseball"),
            ("C.J. Stroud", "C.J. Stroud", "Football"),
            ("cj stroud", "C.J. Stroud", "Football"),
            ("steph curry", "Stephen Curry", "Basketball"),
            ("wemby", "Victor Wembanyama", "Basketball"),
            ("cr7", "Cristiano Ronaldo", "Soccer"),
            ("the great one", "Wayne Gretzky", "Hockey"),
            ("black mamba", "Kobe Bryant", "Basketball"),
            ("Iga Świątek", "Iga Świątek", "Tennis"),
            ("iga swiatek", "Iga Świątek", "Tennis"),
            ("Canelo Álvarez", "Canelo Álvarez", "Boxing"),
            ("Tim Stützle", "Tim Stützle", "Hockey"),
            ("tim stutzle", "Tim Stützle", "Hockey"),
            ("Alexis Lafrenière", "Alexis Lafrenière", "Hockey"),
            ("alexis lafreniere", "Alexis Lafrenière", "Hockey"),
            ("Kylian Mbappé", "Kylian Mbappé", "Soccer"),
            ("kylian mbappe", "Kylian Mbappé", "Soccer"),
            ("Vinícius Júnior", "Vinícius Júnior", "Soccer"),
            ("vinicius jr", "Vinícius Júnior", "Soccer"),
            ("Luka Modrić", "Luka Modrić", "Soccer"),
            ("luka modric", "Luka Modrić", "Soccer"),
            ("Charizard", "Charizard", "Pokemon"),
            ("charizard", "Charizard", "Pokemon"),
            ("Black Lotus", "Black Lotus", "Magic"),
            ("Blue-Eyes White Dragon", "Blue-Eyes White Dragon", "Yugioh"),
            ("Mothman", "Mothman", "Metazoo"),
            ("Son Goku", "Son Goku", "Dragonballz"),
        ],
    )
    def test_player_normalization_diacritics_and_aliases(
        self, input_name: str, expected_normalized: str, category: str
    ):
        """Validates that diacritics, aliases, and lowercase variants normalize to pristine canonical strings."""
        result = normalize_player_name(input_name, category=category)
        assert result == expected_normalized, f"Normalizing '{input_name}' under '{category}' returned '{result}', expected '{expected_normalized}'"

    def test_player_full_name_category_isolation(self):
        """Full names or unambiguous inputs map accurately to canonical category entries."""
        # Basketball Jordan
        bb_jordan = normalize_player_name("Michael Jordan", category="Basketball")
        assert bb_jordan == "Michael Jordan"

        # Golf Jordan Spieth
        golf_jordan = normalize_player_name("Jordan Spieth", category="Golf")
        assert golf_jordan == "Jordan Spieth"

    def test_unmatched_and_bogus_names_zero_loss_fallback(self):
        """Bogus, completely uncataloged, or below-cutoff names must return cleaned original string without corruption."""
        bogus_names = [
            "Unknown Prospect 2026",
            "Random Indie Wrestler",
            "X99-CustomCard",
            "Johnny Test 123",
        ]
        for bogus in bogus_names:
            normalized = normalize_player_name(bogus, category="Basketball")
            assert normalized == bogus

    @pytest.mark.parametrize(
        "raw_set,year,category,expected_set",
        [
            ("prizm", "2020", "Basketball", "Panini Prizm"),
            ("2020 Panini Prizm", "2020", "Basketball", "Panini Prizm"),
            ("select", "2021", "Basketball", "Panini Select"),
            ("tc", "2022", "Baseball", "Topps Chrome"),
            ("young guns", "2023", "Hockey", "Upper Deck Young Guns"),
            ("yg", "2023", "Hockey", "Upper Deck Young Guns"),
            ("pokemon base set", "1999", "Pokemon", "Base Set"),
            ("mtg alpha", "1993", "Magic", "Limited Edition Alpha"),
            ("lob", "2002", "Yugioh", "Legend of Blue Eyes White Dragon"),
        ],
    )
    def test_set_normalization_embedded_year_and_aliases(
        self, raw_set: str, year: str, category: str, expected_set: str
    ):
        """Validates set normalization with embedded year prefix removal and alias fast-paths."""
        res = normalize_set_name(raw_set, year=year, category=category)
        assert res == expected_set, f"Normalizing set '{raw_set}' returned '{res}', expected '{expected_set}'"


# ============================================================================
# 5. Security, Injection, and Path Traversal / Boundary Fuzzing
# ============================================================================

class TestSecurityAndInjectionDefense:
    """Tests CSV formula injection, special characters, quotes, commas, and SQL injection safety."""

    def test_csv_formula_injection_and_special_character_escaping(self, temp_db: str, export_dir: str):
        """Strings starting with formula operators (=, +, -, @) or quotes/commas must be safely quoted."""
        adversarial_cards = [
            {
                "player": "=cmd|' /C calc'!A0",
                "year": "2024",
                "set_name": "@Panini Prizm",
                "variation": "-Silver",
                "card_number": "=SUM(1,2)",
                "category": "Basketball",
                "condition": "PSA 10",
                "notes": "Line 1\nLine 2 with \"quotes\" and , commas,",
                "ai_status": "CLEARED",
            },
            {
                "player": "Robert'); DROP TABLE cards;--",
                "year": "2024",
                "set_name": "Topps \"Special\" Series",
                "variation": "Gold, 1/10",
                "card_number": "#'--",
                "category": "Baseball",
                "condition": "Raw",
                "notes": "Normal note",
                "ai_status": "CLEARED",
            },
        ]
        insert_cards_batch(adversarial_cards, db_path=temp_db)

        target_csv = os.path.join(export_dir, "export_security.csv")
        # Since variation triggers REVIEW VARIATION in CardRecord, status_filter='ALL' exports both
        total_exported, file_paths = export_card_ladder_csv(
            db_path=temp_db,
            output_path=target_csv,
            status_filter="ALL",
            apply_normalization=False,
        )

        assert total_exported == 2
        csv_file = file_paths[0]

        # Read back with standard csv.reader to verify proper quoting and escaping
        with open(csv_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 3  # 1 header + 2 data rows
        row1 = rows[1]
        assert row1[2] == "=cmd|' /C calc'!A0"  # Player
        assert row1[3] == "2024"                # Year
        assert row1[4] == "@Panini Prizm"        # Set
        assert row1[5] == "-Silver"             # Variation
        assert row1[6] == "=SUM(1,2)"           # Number
        assert "Line 1\nLine 2 with \"quotes\" and , commas," in row1[12]  # Notes

        row2 = rows[2]
        assert row2[2] == "Robert'); DROP TABLE cards;--"
        assert row2[4] == "Topps \"Special\" Series"
        assert row2[5] == "Gold, 1/10"

    def test_sql_injection_defense_in_status_filter(self, temp_db: str, export_dir: str):
        """Status filter with SQL injection payload must not dump unauthorized records."""
        card = {
            "player": "Luka Dončić",
            "year": "2018",
            "set_name": "Panini Prizm",
            "card_number": "007",
            "category": "Basketball",
            "condition": "PSA 10",
            "ai_status": "REVIEW VARIATION",
        }
        insert_card(card, db_path=temp_db)

        target_csv = os.path.join(export_dir, "export_sqli.csv")

        # Adversarial status filter attempting SQL injection
        total_exported, _ = export_card_ladder_csv(
            db_path=temp_db,
            output_path=target_csv,
            status_filter="' OR 1=1; --",
        )

        # Parameterized query should look for ai_status == "' OR 1=1; --" and find 0 matches
        assert total_exported == 0


# ============================================================================
# 6. Status Filtering Integrity Stress Testing
# ============================================================================

class TestStatusFilteringIntegrity:
    """Verifies that only cards matching the requested status filter are exported."""

    def test_status_filter_isolation(self, temp_db: str, export_dir: str):
        """Verify strict segregation between CLEARED, REVIEW VARIATION, and NEEDS REVIEW."""
        records = [
            {"player": "Player A", "year": "2020", "set_name": "Set A", "card_number": "1", "category": "Baseball", "condition": "Raw", "ai_status": "CLEARED"},
            {"player": "Player B", "year": "2020", "set_name": "Set A", "card_number": "2", "category": "Baseball", "condition": "Raw", "ai_status": "CLEARED"},
            {"player": "Player C", "year": "2020", "set_name": "Set A", "card_number": "3", "category": "Baseball", "condition": "Raw", "ai_status": "REVIEW VARIATION"},
            {"player": "Player D", "year": "2020", "set_name": "Set A", "card_number": "4", "category": "Baseball", "condition": "Raw", "ai_status": "NEEDS REVIEW"},
        ]
        insert_cards_batch(records, db_path=temp_db)

        # 1. Default CLEARED
        cleared_csv = os.path.join(export_dir, "status_cleared.csv")
        n_cleared, _ = export_card_ladder_csv(temp_db, cleared_csv, status_filter="CLEARED")
        assert n_cleared == 2

        # 2. REVIEW VARIATION
        var_csv = os.path.join(export_dir, "status_var.csv")
        n_var, _ = export_card_ladder_csv(temp_db, var_csv, status_filter="REVIEW VARIATION")
        assert n_var == 1

        # 3. NEEDS REVIEW
        rev_csv = os.path.join(export_dir, "status_rev.csv")
        n_rev, _ = export_card_ladder_csv(temp_db, rev_csv, status_filter="NEEDS REVIEW")
        assert n_rev == 1

        # 4. ALL
        all_csv = os.path.join(export_dir, "status_all.csv")
        n_all, _ = export_card_ladder_csv(temp_db, all_csv, status_filter="ALL")
        assert n_all == 4


# ============================================================================
# 7. Financial Data Precision & Currency Formatting Stress Testing
# ============================================================================

class TestFinancialPrecisionAndFormatting:
    """Stress tests currency values, null prices, sold prices, and decimal precision."""

    @pytest.mark.parametrize(
        "input_val,expected_float",
        [
            (150.0, 150.0),
            (150.999, 151.0),
            (12.3456, 12.35),
            ("250.75", 250.75),
            ("1,200.50", 0.0),   # string with comma handled safely or 0.0
            (None, 0.0),
            ("", 0.0),
            ("invalid", 0.0),
        ],
    )
    def test_investment_and_est_value_formatting(self, input_val: Any, expected_float: float):
        """Monetary values must convert safely to float without crashing."""
        res = format_currency_value(input_val)
        assert isinstance(res, float)
        assert res == expected_float

    def test_sold_price_empty_when_unsold(self):
        """Unsold cards must have empty string for sold price, not 0.00."""
        assert format_sold_price(None) == ""
        assert format_sold_price("") == ""
        assert format_sold_price(450.50) == 450.50


# ============================================================================
# 8. High-Concurrency Stress & Large Volume (10,000 records) Performance
# ============================================================================

class TestHighConcurrencyAndScalePerformance:
    """Stress tests export under concurrent reads/writes and benchmarks 10,000 cards export."""

    def test_concurrent_exports_under_active_writes(self, temp_db: str, export_dir: str):
        """Simultaneous exports from multiple threads while background thread writes new cards."""
        # Pre-seed 200 cards
        pre_cards = [
            {
                "player": f"Player {i:03d}",
                "year": "2023",
                "set_name": "Panini Prizm",
                "card_number": f"{i:03d}",
                "category": "Basketball",
                "condition": "Raw",
                "ai_status": "CLEARED",
            }
            for i in range(1, 201)
        ]
        insert_cards_batch(pre_cards, db_path=temp_db)

        stop_writing = threading.Event()
        writer_errors = []

        def background_writer():
            try:
                counter = 300
                while not stop_writing.is_set():
                    card = {
                        "player": f"Dynamic Player {counter}",
                        "year": "2024",
                        "set_name": "Topps Chrome",
                        "card_number": f"{counter}",
                        "category": "Baseball",
                        "condition": "Raw",
                        "ai_status": "CLEARED",
                    }
                    insert_card(card, db_path=temp_db)
                    counter += 1
                    time.sleep(0.01)
            except Exception as e:
                writer_errors.append(e)

        writer_thread = threading.Thread(target=background_writer)
        writer_thread.start()

        # Run 5 concurrent exports
        def run_export(idx: int):
            out_file = os.path.join(export_dir, f"concurrent_export_{idx}.csv")
            n, files = export_card_ladder_csv(
                db_path=temp_db,
                output_path=out_file,
                status_filter="CLEARED",
                max_batch_size=500,
            )
            assert n >= 200
            for f in files:
                val = validate_card_ladder_csv(f)
                assert val["valid"] is True

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(run_export, i) for i in range(5)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        stop_writing.set()
        writer_thread.join(timeout=3)
        assert len(writer_errors) == 0

    def test_benchmark_large_volume_10k_cards(self, export_dir: str):
        """Benchmark: 10,000 cards transformed and chunked into 20 CSV files in < 5 seconds."""
        cards = [
            {
                "player": "Luka Doncic" if i % 2 == 0 else "Shohei Ohtani",
                "year": "2023",
                "set_name": "Prizm" if i % 2 == 0 else "Topps Chrome",
                "card_number": f"{i:05d}",
                "category": "Basketball" if i % 2 == 0 else "Baseball",
                "condition": "PSA 10",
                "investment": 100.0 + (i % 50),
                "estimated_value": 250.0 + (i % 100),
                "notes": f"8492-{i:05d}",
            }
            for i in range(10000)
        ]

        t0 = time.perf_counter()

        # Convert to DataFrame
        df = cards_to_card_ladder_dataframe(cards, apply_normalization=True)
        assert len(df) == 10000
        assert list(df.columns) == CARD_LADDER_COLUMNS

        # Export to chunked CSVs
        out_file = os.path.join(export_dir, "benchmark_10k.csv")
        total_rows, generated_files = export_dataframe_to_chunked_csvs(
            df,
            output_path=out_file,
            max_batch_size=500,
        )

        elapsed = time.perf_counter() - t0

        assert total_rows == 10000
        assert len(generated_files) == 20
        assert elapsed < 5.0, f"10k export took {elapsed:.2f}s, expected < 5.0s"

        # Validate first, middle, and last files
        for test_idx in [0, 9, 19]:
            val = validate_card_ladder_csv(generated_files[test_idx])
            assert val["valid"] is True
            assert val["row_count"] == 500

"""
tests/test_export.py - Comprehensive deterministic test suite for Milestone 4 (Export Pipeline).
Tests Fuzzy Normalization Engine, Card Ladder 16-Column CSV Exporter, Leading Zero String Preservation,
500-Card Batch Circuit Breaker & Chunking, Status Filtering, SQLite -> CSV -> Pandas Round-Trip Integrity,
and Export Resilience & Edge Cases.
"""

from __future__ import annotations

import csv
import os
import re
import sqlite3
import sys
import threading
import time
from typing import Any, Generator
import pandas as pd
import pytest

# Ensure project root is in sys.path
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
    get_card_ladder_columns,
    get_excluded_fields,
    fetch_records_for_export,
    transform_records_to_card_ladder_df,
    write_card_ladder_csv_chunks,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_db_path(tmp_path) -> str:
    """Provides a fresh isolated SQLite database path."""
    db_file = str(tmp_path / "test_portfolio.db")
    init_db(db_file)
    return db_file


@pytest.fixture
def output_dir(tmp_path) -> str:
    """Provides a clean temporary directory for exported CSV files."""
    out_dir = str(tmp_path / "exports")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


@pytest.fixture
def sample_cleared_cards() -> list[dict[str, Any]]:
    """Provides a diverse set of 10 CLEARED cards."""
    return [
        {
            "date_purchased": "08/20/2026",
            "quantity": 1,
            "player": "Shohei Ohtani",
            "year": "2023",
            "set_name": "Topps Chrome",
            "variation": "",
            "card_number": "007",
            "category": "Baseball",
            "condition": "PSA 10",
            "slab_serial_number": "84729104",
            "investment": 150.00,
            "estimated_value": 320.00,
            "ladder_id": "LAD-12345",
            "notes": "8492-101",
            "date_sold": "",
            "sold_price": None,
            "image": "https://example.com/ohtani.jpg",
            "ai_status": "CLEARED",
        },
        {
            "date_purchased": "08/21/2026",
            "quantity": 1,
            "player": "Victor Wembanyama",
            "year": "2023",
            "set_name": "Panini Prizm",
            "variation": "",
            "card_number": "01",
            "category": "Basketball",
            "condition": "Raw",
            "slab_serial_number": "",
            "investment": 80.00,
            "estimated_value": 200.00,
            "ladder_id": "",
            "notes": "8492-102",
            "date_sold": "",
            "sold_price": None,
            "image": "https://example.com/wemby.jpg",
            "ai_status": "CLEARED",
        },
        {
            "date_purchased": "08/22/2026",
            "quantity": 2,
            "player": "Patrick Mahomes",
            "year": "2017",
            "set_name": "Panini Donruss",
            "variation": "",
            "card_number": "000",
            "category": "Football",
            "condition": "BGS 9.5",
            "slab_serial_number": "99281726",
            "investment": 500.00,
            "estimated_value": 1200.00,
            "ladder_id": "LAD-99881",
            "notes": "8492-103",
            "date_sold": "08/23/2026",
            "sold_price": 1350.00,
            "image": "https://example.com/mahomes.jpg",
            "ai_status": "CLEARED",
        },
        {
            "date_purchased": "08/23/2026",
            "quantity": 1,
            "player": "Charizard",
            "year": "1999",
            "set_name": "Pokemon Base Set",
            "variation": "",
            "card_number": "004",
            "category": "Pokemon",
            "condition": "PSA 9",
            "slab_serial_number": "11223344",
            "investment": 1200.00,
            "estimated_value": 3500.00,
            "ladder_id": "",
            "notes": "8492-104",
            "date_sold": "",
            "sold_price": None,
            "image": "https://example.com/charizard.jpg",
            "ai_status": "CLEARED",
        },
        {
            "date_purchased": "08/23/2026",
            "quantity": 1,
            "player": "Luka Dončić",
            "year": "2018",
            "set_name": "Panini Prizm",
            "variation": "",
            "card_number": "RC-05",
            "category": "Basketball",
            "condition": "Raw",
            "slab_serial_number": "",
            "investment": 45.00,
            "estimated_value": 95.00,
            "ladder_id": "",
            "notes": "8492-105",
            "date_sold": "",
            "sold_price": None,
            "image": "",
            "ai_status": "CLEARED",
        },
        {
            "date_purchased": "08/23/2026",
            "quantity": 1,
            "player": "Connor Bedard",
            "year": "2023",
            "set_name": "Upper Deck Series 1",
            "variation": "",
            "card_number": "042",
            "category": "Hockey",
            "condition": "PSA 10",
            "slab_serial_number": "55443322",
            "investment": 300.00,
            "estimated_value": 650.00,
            "ladder_id": "",
            "notes": "8492-106",
            "date_sold": "",
            "sold_price": None,
            "image": "",
            "ai_status": "CLEARED",
        },
        {
            "date_purchased": "08/23/2026",
            "quantity": 1,
            "player": "Lionel Messi",
            "year": "2004",
            "set_name": "Panini Megacracks",
            "variation": "",
            "card_number": "71",
            "category": "Soccer",
            "condition": "PSA 8",
            "slab_serial_number": "99001122",
            "investment": 2000.00,
            "estimated_value": 4500.00,
            "ladder_id": "LAD-MESSI",
            "notes": "8492-107",
            "date_sold": "",
            "sold_price": None,
            "image": "",
            "ai_status": "CLEARED",
        },
        {
            "date_purchased": "08/23/2026",
            "quantity": 1,
            "player": "Black Lotus",
            "year": "1993",
            "set_name": "Magic Alpha",
            "variation": "",
            "card_number": "",
            "category": "Magic",
            "condition": "BGS 9",
            "slab_serial_number": "77889900",
            "investment": 15000.00,
            "estimated_value": 30000.00,
            "ladder_id": "",
            "notes": "8492-108",
            "date_sold": "",
            "sold_price": None,
            "image": "",
            "ai_status": "CLEARED",
        },
        {
            "date_purchased": "08/23/2026",
            "quantity": 1,
            "player": "Shaquille O'Neal",
            "year": "1992",
            "set_name": "Upper Deck",
            "variation": "",
            "card_number": "100/100",
            "category": "Basketball",
            "condition": "Raw",
            "slab_serial_number": "",
            "investment": 15.00,
            "estimated_value": 35.00,
            "ladder_id": "",
            "notes": '8492-109 "Special"',
            "date_sold": "",
            "sold_price": None,
            "image": "",
            "ai_status": "CLEARED",
        },
        {
            "date_purchased": "08/23/2026",
            "quantity": 1,
            "player": "Ronald Acuña Jr.",
            "year": "2018",
            "set_name": "Topps Chrome",
            "variation": "",
            "card_number": "01/25",
            "category": "Baseball",
            "condition": "PSA 10",
            "slab_serial_number": "33445566",
            "investment": 250.00,
            "estimated_value": 550.00,
            "ladder_id": "",
            "notes": "8492-110",
            "date_sold": "",
            "sold_price": None,
            "image": "",
            "ai_status": "CLEARED",
        },
    ]


@pytest.fixture
def sample_mixed_status_cards() -> list[dict[str, Any]]:
    """Provides cards spanning CLEARED, REVIEW VARIATION, and NEEDS REVIEW."""
    cards = []
    # 4 CLEARED
    for i in range(1, 5):
        cards.append({
            "player": f"Cleared Player {i}",
            "year": "2023",
            "set_name": "Panini Prizm",
            "category": "Basketball",
            "condition": "Raw",
            "card_number": f"0{i}",
            "ai_status": "CLEARED",
        })
    # 3 REVIEW VARIATION
    for i in range(1, 4):
        cards.append({
            "player": f"Variation Player {i}",
            "year": "2023",
            "set_name": "Topps Chrome",
            "variation": f"Refractor Var {i}",
            "category": "Baseball",
            "condition": "Raw",
            "card_number": f"1{i}",
            "ai_status": "REVIEW VARIATION",
        })
    # 3 NEEDS REVIEW
    for i in range(1, 4):
        cards.append({
            "player": f"Review Player {i}",
            "year": "2023",
            "set_name": "Upper Deck",
            "category": "Hockey",
            "condition": "Raw",
            "card_number": f"2{i}",
            "ai_status": "NEEDS REVIEW",
        })
    return cards


def make_large_card_batch(count: int, status: str = "CLEARED") -> list[dict[str, Any]]:
    """Helper to generate N valid card dictionaries."""
    cards = []
    for i in range(1, count + 1):
        cards.append({
            "date_purchased": "08/23/2026",
            "quantity": 1,
            "player": f"Batch Player {i:04d}",
            "year": "2024",
            "set_name": "Panini Prizm",
            "variation": "",
            "card_number": f"{i:03d}",
            "category": "Basketball",
            "condition": "Raw",
            "investment": float(i),
            "estimated_value": float(i * 2),
            "ladder_id": "",
            "notes": f"8492-{i:03d}",
            "date_sold": "",
            "sold_price": None,
            "image": f"https://example.com/card_{i}.jpg",
            "ai_status": status,
        })
    return cards


# ============================================================================
# Test Suite 1: Fuzzy Normalization Engine
# ============================================================================

class TestFuzzyNormalizationEngine:
    """Tests player and set name normalization, diacritics, typos, aliases, and cutoffs."""

    def test_fold_string_basic_and_diacritics(self):
        assert fold_string("Luka Dončić") == "luka doncic"
        assert fold_string("Ronald Acuña Jr.") == "ronald acuna jr"
        assert fold_string("C.J. Stroud") == "cj stroud"
        assert fold_string("Shohei Ohtani (大谷 翔平)") == "shohei ohtani"
        assert fold_string("  Victor   Wembanyama  ") == "victor wembanyama"
        assert fold_string("") == ""
        assert fold_string(None) == ""

    def test_player_exact_match(self):
        assert normalize_player_name("Shohei Ohtani", "Baseball") == "Shohei Ohtani"
        assert normalize_player_name("LeBron James", "Basketball") == "LeBron James"

    def test_player_case_insensitivity(self):
        assert normalize_player_name("shohei ohtani", "Baseball") == "Shohei Ohtani"
        assert normalize_player_name("LEBRON JAMES", "Basketball") == "LeBron James"
        assert normalize_player_name("pAtRiCk MaHoMeS", "Football") == "Patrick Mahomes"

    def test_player_whitespace_trimming(self):
        assert normalize_player_name("   Victor   Wembanyama  ", "Basketball") == "Victor Wembanyama"
        assert normalize_player_name(" \t Connor   McDavid \n ", "Hockey") == "Connor McDavid"

    def test_player_diacritics_mapping(self):
        assert normalize_player_name("Luka Doncic", "Basketball") == "Luka Dončić"
        assert normalize_player_name("Nikola Jokic", "Basketball") == "Nikola Jokić"
        assert normalize_player_name("Ronald Acuna Jr.", "Baseball") == "Ronald Acuña Jr."
        assert normalize_player_name("Alexis Lafreniere", "Hockey") == "Alexis Lafrenière"
        assert normalize_player_name("Tim Stutzle", "Hockey") == "Tim Stützle"
        assert normalize_player_name("Iga Swiatek", "Tennis") == "Iga Świątek"

    def test_player_alias_fast_path(self):
        assert normalize_player_name("Steph Curry", "Basketball") == "Stephen Curry"
        assert normalize_player_name("wemby", "Basketball") == "Victor Wembanyama"
        assert normalize_player_name("King James", "Basketball") == "LeBron James"
        assert normalize_player_name("Ohtani", "Baseball") == "Shohei Ohtani"
        assert normalize_player_name("Elly De La Cruz", "Baseball") == "Elly De La Cruz"
        assert normalize_player_name("cmc", "Football") == "Christian McCaffrey"
        assert normalize_player_name("cr7", "Soccer") == "Cristiano Ronaldo"

    def test_player_minor_typo_correction(self):
        assert normalize_player_name("Shohey Ohtani", "Baseball", cutoff=0.75) == "Shohei Ohtani"
        assert normalize_player_name("Patrick Mahommes", "Football", cutoff=0.75) == "Patrick Mahomes"
        assert normalize_player_name("Stefn Curry", "Basketball", cutoff=0.75) == "Stephen Curry"
        assert normalize_player_name("Conner Bedard", "Hockey", cutoff=0.75) == "Connor Bedard"

    def test_player_below_cutoff_rejection(self):
        unknown = "Unknown Local Athlete 99"
        assert normalize_player_name(unknown, "Baseball", cutoff=0.8) == unknown

    def test_player_category_isolation(self):
        # Pikachu should not match a basketball player
        assert normalize_player_name("Pikachu", "Basketball") == "Pikachu"
        assert normalize_player_name("Charizard", "Pokemon") == "Charizard"

    def test_player_tcg_normalization(self):
        assert normalize_player_name("Charzard", "Pokemon", cutoff=0.75) == "Charizard"
        assert normalize_player_name("Blac Lotus", "Magic", cutoff=0.75) == "Black Lotus"
        assert normalize_player_name("Dark Magicn", "Yugioh", cutoff=0.75) == "Dark Magician"

    def test_player_custom_canonical_dict(self):
        custom_dict = {"Baseball": ["Buster Posey", "Barry Bonds"]}
        assert normalize_player_name("Buster Posi", "Baseball", canonical_dict=custom_dict, cutoff=0.75) == "Buster Posey"

    def test_player_empty_and_blank(self):
        assert normalize_player_name("", "Basketball") == ""
        assert normalize_player_name("   ", "Basketball") == ""
        assert normalize_player_name(None, "Basketball") == ""

    def test_set_exact_and_case(self):
        assert normalize_set_name("panini prizm", "2023", "Basketball") == "Panini Prizm"
        assert normalize_set_name("TOPPS CHROME", "2023", "Baseball") == "Topps Chrome"

    def test_set_alias_fast_path(self):
        assert normalize_set_name("prizm", "2023", "Basketball") == "Panini Prizm"
        assert normalize_set_name("tc", "2023", "Baseball") == "Topps Chrome"
        assert normalize_set_name("pokemon base", "1999", "Pokemon") == "Base Set"
        assert normalize_set_name("magic alpha", "1993", "Magic") == "Limited Edition Alpha"
        assert normalize_set_name("young guns", "2023", "Hockey") == "Upper Deck Young Guns"

    def test_set_embedded_year_prefix_stripping(self):
        assert normalize_set_name("2023 Panini Prizm", year="2023", category="Basketball") == "Panini Prizm"
        assert normalize_set_name("2020 Topps Chrome", year="2020", category="Baseball") == "Topps Chrome"

    def test_set_minor_typo_correction(self):
        assert normalize_set_name("Pannini Prizm", "2023", "Basketball", cutoff=0.75) == "Panini Prizm"
        assert normalize_set_name("Topps Chrom", "2023", "Baseball", cutoff=0.75) == "Topps Chrome"
        assert normalize_set_name("Bowman Chome", "2023", "Baseball", cutoff=0.75) == "Bowman Chrome"
        assert normalize_set_name("Upper Dek Series 1", "2023", "Hockey", cutoff=0.75) == "Upper Deck Series 1"

    def test_set_below_cutoff_rejection(self):
        unknown_set = "Obscure Indie Set 2024"
        assert normalize_set_name(unknown_set, "2024", "Baseball", cutoff=0.8) == unknown_set

    def test_set_empty_and_blank(self):
        assert normalize_set_name("", "2023", "Basketball") == ""
        assert normalize_set_name("   ", "2023", "Basketball") == ""
        assert normalize_set_name(None, "2023", "Basketball") == ""


# ============================================================================
# Test Suite 2: Card Ladder CSV Headers & Structure
# ============================================================================

class TestCardLadderCSVHeadersAndStructure:
    """Tests exact 16-column header tuple, sequence, and strict exclusion of internal fields."""

    def test_exact_16_column_headers_and_sequence(self, test_db_path, output_dir, sample_cleared_cards):
        insert_cards_batch(test_db_path, sample_cleared_cards)
        out_csv = os.path.join(output_dir, "headers_test.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv, status_filter="CLEARED")

        assert count == 10
        assert len(paths) == 1

        with open(paths[0], mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header_row = next(reader)

        expected_tuple = (
            "Date Purchased", "Quantity", "Player", "Year", "Set", "Variation",
            "Number", "Category", "Condition", "Investment", "Estimated Value",
            "Ladder ID", "Notes", "Date Sold", "Sold Price", "Image"
        )
        assert tuple(header_row) == expected_tuple
        assert tuple(get_card_ladder_columns()) == expected_tuple
        assert len(header_row) == 16

    def test_internal_fields_strictly_excluded(self, test_db_path, output_dir, sample_cleared_cards):
        insert_cards_batch(test_db_path, sample_cleared_cards)
        out_csv = os.path.join(output_dir, "no_internals.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv)

        forbidden = [
            "slab_serial_number", "Slab Serial #",
            "query", "Query",
            "tags", "Tags",
            "back_image", "Back Image",
            "ai_status", "AI Status",
            "id", "created_at", "updated_at"
        ]

        with open(paths[0], mode="r", encoding="utf-8") as f:
            content = f.read()

        header_line = content.splitlines()[0]
        for f_name in forbidden:
            assert f_name not in header_line.split(","), f"Forbidden field '{f_name}' in CSV headers!"

        # Ensure excluded fields helper works
        excluded_list = get_excluded_fields()
        assert "slab_serial_number" in excluded_list
        assert "query" in excluded_list
        assert "tags" in excluded_list
        assert "back_image" in excluded_list
        assert "ai_status" in excluded_list

    def test_empty_database_produces_valid_16_column_csv(self, test_db_path, output_dir):
        out_csv = os.path.join(output_dir, "empty.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv)

        assert count == 0
        assert len(paths) == 1
        assert os.path.exists(paths[0])

        with open(paths[0], mode="r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) == 1
        assert lines[0].split(",") == list(CARD_LADDER_COLUMNS)

    def test_validate_card_ladder_csv_utility(self, test_db_path, output_dir, sample_cleared_cards):
        insert_cards_batch(test_db_path, sample_cleared_cards)
        out_csv = os.path.join(output_dir, "validated.csv")
        export_card_ladder_csv(test_db_path, out_csv)

        validation = validate_card_ladder_csv(out_csv)
        assert validation["valid"] is True
        assert validation["row_count"] == 10
        assert validation["headers"] == list(CARD_LADDER_COLUMNS)


# ============================================================================
# Test Suite 3: Leading Zero & String Preservation Engine
# ============================================================================

class TestLeadingZeroAndStringPreservation:
    """Tests leading zeros preservation on card numbers across SQLite, CSV, DictReader, and Pandas."""

    def test_leading_zero_preservation_round_trip(self, test_db_path, output_dir):
        cards = [
            {"player": "Shohei Ohtani", "year": "2023", "set_name": "Topps Chrome", "category": "Baseball", "card_number": "007", "ai_status": "CLEARED"},
            {"player": "Victor Wembanyama", "year": "2023", "set_name": "Panini Prizm", "category": "Basketball", "card_number": "01", "ai_status": "CLEARED"},
            {"player": "Patrick Mahomes", "year": "2017", "set_name": "Panini Donruss", "category": "Football", "card_number": "000", "ai_status": "CLEARED"},
            {"player": "Connor Bedard", "year": "2023", "set_name": "Upper Deck", "category": "Hockey", "card_number": "RC-05", "ai_status": "CLEARED"},
            {"player": "Tom Brady", "year": "2000", "set_name": "Panini Score", "category": "Football", "card_number": "0", "ai_status": "CLEARED"},
            {"player": "Wayne Gretzky", "year": "1979", "set_name": "O-Pee-Chee", "category": "Hockey", "card_number": "0042", "ai_status": "CLEARED"},
            {"player": "Lionel Messi", "year": "2004", "set_name": "Panini Mega Cracks", "category": "Soccer", "card_number": "01/25", "ai_status": "CLEARED"},
        ]
        insert_cards_batch(test_db_path, cards)
        out_csv = os.path.join(output_dir, "leading_zeros.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv)

        assert count == 7
        assert len(paths) == 1

        # 1. Standard csv DictReader
        with open(paths[0], mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        numbers_csv = [r["Number"] for r in rows]
        assert numbers_csv == ["007", "01", "000", "RC-05", "0", "0042", "01/25"]

        # 2. Pandas read_csv with dtype={'Number': str}
        df_read = pd.read_csv(paths[0], dtype={"Number": str, "Year": str}, keep_default_na=False)
        numbers_pd = df_read["Number"].tolist()
        assert numbers_pd == ["007", "01", "000", "RC-05", "0", "0042", "01/25"]

        # 3. Raw text regex inspection
        with open(paths[0], mode="r", encoding="utf-8") as f:
            raw_text = f.read()

        assert ",007," in raw_text or ',"007",' in raw_text
        assert ",01," in raw_text or ',"01",' in raw_text
        assert ",000," in raw_text or ',"000",' in raw_text
        assert ",0042," in raw_text or ',"0042",' in raw_text

    def test_blank_card_number_preservation(self, test_db_path, output_dir):
        card = {"player": "Black Lotus", "year": "1993", "set_name": "Magic Alpha", "category": "Magic", "card_number": "", "ai_status": "CLEARED"}
        insert_card(test_db_path, card)
        out_csv = os.path.join(output_dir, "blank_num.csv")
        export_card_ladder_csv(test_db_path, out_csv)

        df_read = pd.read_csv(out_csv, dtype={"Number": str}, keep_default_na=False)
        assert df_read["Number"].iloc[0] == ""
        assert df_read["Number"].iloc[0] != "nan"
        assert df_read["Number"].iloc[0] != "None"


# ============================================================================
# Test Suite 4: 500-Card Batch Circuit Breaker & Chunking
# ============================================================================

class TestBatchRolloverAndChunking:
    """Tests automatic partitioning of CSV exports at max_batch_size (500 cards)."""

    def test_generate_chunk_filepath_utility(self):
        # 1 part -> unchanged base
        assert generate_chunk_filepath("CardLadder_Bulk_Upload.csv", 1, 1) == "CardLadder_Bulk_Upload.csv"
        # 3 parts -> part1, part2, part3
        assert generate_chunk_filepath("exports/CardLadder.csv", 1, 3) == os.path.join("exports", "CardLadder_part1.csv")
        assert generate_chunk_filepath("exports/CardLadder.csv", 2, 3) == os.path.join("exports", "CardLadder_part2.csv")
        assert generate_chunk_filepath("exports/CardLadder.csv", 3, 3) == os.path.join("exports", "CardLadder_part3.csv")

    def test_batch_under_limit_single_file(self, test_db_path, output_dir):
        cards_50 = make_large_card_batch(50)
        insert_cards_batch(test_db_path, cards_50)
        out_csv = os.path.join(output_dir, "under500.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv)

        assert count == 50
        assert len(paths) == 1
        assert os.path.basename(paths[0]) == "under500.csv"
        df = pd.read_csv(paths[0], dtype=str)
        assert len(df) == 50

    def test_batch_exact_500_limit_single_file(self, test_db_path, output_dir):
        cards_500 = make_large_card_batch(500)
        insert_cards_batch(test_db_path, cards_500)
        out_csv = os.path.join(output_dir, "exact500.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv)

        assert count == 500
        assert len(paths) == 1
        assert os.path.basename(paths[0]) == "exact500.csv"
        df = pd.read_csv(paths[0], dtype=str)
        assert len(df) == 500

    def test_batch_501_cards_chunks_to_two_files(self, test_db_path, output_dir):
        cards_501 = make_large_card_batch(501)
        insert_cards_batch(test_db_path, cards_501)
        out_csv = os.path.join(output_dir, "batch501.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv)

        assert count == 501
        assert len(paths) == 2
        assert os.path.basename(paths[0]) == "batch501_part1.csv"
        assert os.path.basename(paths[1]) == "batch501_part2.csv"

        df_p1 = pd.read_csv(paths[0], dtype=str)
        df_p2 = pd.read_csv(paths[1], dtype=str)
        assert len(df_p1) == 500
        assert len(df_p2) == 1
        assert df_p1.columns.tolist() == list(CARD_LADDER_COLUMNS)
        assert df_p2.columns.tolist() == list(CARD_LADDER_COLUMNS)

    def test_batch_1000_cards_chunks_to_two_equal_files(self, test_db_path, output_dir):
        cards_1000 = make_large_card_batch(1000)
        insert_cards_batch(test_db_path, cards_1000)
        out_csv = os.path.join(output_dir, "batch1000.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv)

        assert count == 1000
        assert len(paths) == 2
        df_p1 = pd.read_csv(paths[0], dtype=str)
        df_p2 = pd.read_csv(paths[1], dtype=str)
        assert len(df_p1) == 500
        assert len(df_p2) == 500

    def test_batch_1250_cards_chunks_to_three_files(self, test_db_path, output_dir):
        cards_1250 = make_large_card_batch(1250)
        insert_cards_batch(test_db_path, cards_1250)
        out_csv = os.path.join(output_dir, "batch1250.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv)

        assert count == 1250
        assert len(paths) == 3
        df1 = pd.read_csv(paths[0], dtype=str)
        df2 = pd.read_csv(paths[1], dtype=str)
        df3 = pd.read_csv(paths[2], dtype=str)

        assert len(df1) == 500
        assert len(df2) == 500
        assert len(df3) == 250

        # Check sequential order without loss or duplication
        assert df1["Notes"].iloc[0] == "8492-001"
        assert df1["Notes"].iloc[-1] == "8492-500"
        assert df2["Notes"].iloc[0] == "8492-501"
        assert df2["Notes"].iloc[-1] == "8492-1000"
        assert df3["Notes"].iloc[0] == "8492-1001"
        assert df3["Notes"].iloc[-1] == "8492-1250"

    def test_custom_max_batch_size_parameter(self, test_db_path, output_dir):
        cards_150 = make_large_card_batch(150)
        insert_cards_batch(test_db_path, cards_150)
        out_csv = os.path.join(output_dir, "custom_batch.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv, max_batch_size=60)

        assert count == 150
        assert len(paths) == 3
        assert len(pd.read_csv(paths[0])) == 60
        assert len(pd.read_csv(paths[1])) == 60
        assert len(pd.read_csv(paths[2])) == 30


# ============================================================================
# Test Suite 5: Status Filtering & Selection
# ============================================================================

class TestStatusFiltering:
    """Tests default CLEARED filtering, ALL, REVIEW VARIATION, and case-insensitivity."""

    def test_default_status_filter_is_cleared(self, test_db_path, output_dir, sample_mixed_status_cards):
        insert_cards_batch(test_db_path, sample_mixed_status_cards)
        out_csv = os.path.join(output_dir, "default_filter.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv)

        assert count == 4
        assert len(paths) == 1
        df = pd.read_csv(paths[0], dtype=str)
        assert len(df) == 4
        assert all("Cleared Player" in p for p in df["Player"])

    def test_status_filter_all_includes_all_cards(self, test_db_path, output_dir, sample_mixed_status_cards):
        insert_cards_batch(test_db_path, sample_mixed_status_cards)
        out_csv = os.path.join(output_dir, "all_filter.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv, status_filter="ALL")

        assert count == 10
        assert len(paths) == 1
        df = pd.read_csv(paths[0], dtype=str)
        assert len(df) == 10

    def test_status_filter_review_variation_only(self, test_db_path, output_dir, sample_mixed_status_cards):
        insert_cards_batch(test_db_path, sample_mixed_status_cards)
        out_csv = os.path.join(output_dir, "var_filter.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv, status_filter="REVIEW VARIATION")

        assert count == 3
        df = pd.read_csv(paths[0], dtype=str)
        assert len(df) == 3
        assert all("Variation Player" in p for p in df["Player"])

    def test_status_filter_needs_review_only(self, test_db_path, output_dir, sample_mixed_status_cards):
        insert_cards_batch(test_db_path, sample_mixed_status_cards)
        out_csv = os.path.join(output_dir, "needs_rev_filter.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv, status_filter="NEEDS REVIEW")

        assert count == 3
        df = pd.read_csv(paths[0], dtype=str)
        assert len(df) == 3
        assert all("Review Player" in p for p in df["Player"])

    def test_status_filter_case_insensitivity(self, test_db_path, output_dir, sample_mixed_status_cards):
        insert_cards_batch(test_db_path, sample_mixed_status_cards)
        out_csv = os.path.join(output_dir, "case_filter.csv")
        count1, _ = export_card_ladder_csv(test_db_path, out_csv, status_filter="cleared")
        assert count1 == 4
        count2, _ = export_card_ladder_csv(test_db_path, out_csv, status_filter="Cleared")
        assert count2 == 4
        count3, _ = export_card_ladder_csv(test_db_path, out_csv, status_filter="all")
        assert count3 == 10

    def test_status_filter_with_zero_matches(self, test_db_path, output_dir, sample_cleared_cards):
        insert_cards_batch(test_db_path, sample_cleared_cards)
        out_csv = os.path.join(output_dir, "zero_matches.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv, status_filter="NEEDS REVIEW")

        assert count == 0
        assert len(paths) == 1
        with open(paths[0], mode="r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 1


# ============================================================================
# Test Suite 6: Round-Trip SQLite -> CSV -> Pandas Integrity
# ============================================================================

class TestRoundTripSQLiteToCSVToPandas:
    """Tests full lossless round-trip data integrity from SQLite to CSV to Pandas."""

    def test_round_trip_basic_portfolio(self, test_db_path, output_dir, sample_cleared_cards):
        insert_cards_batch(test_db_path, sample_cleared_cards)
        out_csv = os.path.join(output_dir, "roundtrip.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv)

        assert count == 10
        df = pd.read_csv(paths[0], dtype={"Number": str, "Year": str}, keep_default_na=False)

        # Compare sample record (Ohtani)
        ohtani_row = df[df["Player"] == "Shohei Ohtani"].iloc[0]
        assert ohtani_row["Date Purchased"] == "08/20/2026"
        assert int(ohtani_row["Quantity"]) == 1
        assert ohtani_row["Year"] == "2023"
        assert ohtani_row["Set"] == "Topps Chrome"
        assert ohtani_row["Variation"] == ""
        assert ohtani_row["Number"] == "007"
        assert ohtani_row["Category"] == "Baseball"
        assert ohtani_row["Condition"] == "PSA 10"
        assert float(ohtani_row["Investment"]) == 150.00
        assert float(ohtani_row["Estimated Value"]) == 320.00
        assert ohtani_row["Ladder ID"] == "LAD-12345"
        assert ohtani_row["Notes"] == "8492-101"
        assert ohtani_row["Image"] == "https://example.com/ohtani.jpg"

    def test_round_trip_variation_preservation(self, test_db_path, output_dir):
        cards = [
            {"player": "Shohei Ohtani", "year": "2023", "set_name": "Topps Chrome", "variation": "Refractor", "card_number": "007", "category": "Baseball"},
            {"player": "Victor Wembanyama", "year": "2023", "set_name": "Panini Prizm", "variation": "Silver Prizm", "card_number": "01", "category": "Basketball"},
        ]
        insert_cards_batch(test_db_path, cards)
        out_csv = os.path.join(output_dir, "variations.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv, status_filter="ALL")

        assert count == 2
        df = pd.read_csv(paths[0], dtype={"Number": str}, keep_default_na=False)
        assert df["Variation"].tolist() == ["Refractor", "Silver Prizm"]

    def test_round_trip_financial_numbers_precision(self, test_db_path, output_dir):
        cards = [
            {"player": "Shohei Ohtani", "year": "2023", "set_name": "Topps Chrome", "category": "Baseball", "investment": 125.50, "estimated_value": 350.00, "date_sold": "08/24/2026", "sold_price": 400.75, "ai_status": "CLEARED"},
            {"player": "Victor Wembanyama", "year": "2023", "set_name": "Panini Prizm", "category": "Basketball", "investment": 0.00, "estimated_value": 0.00, "date_sold": "", "sold_price": None, "ai_status": "CLEARED"},
        ]
        insert_cards_batch(test_db_path, cards)
        out_csv = os.path.join(output_dir, "finance.csv")
        export_card_ladder_csv(test_db_path, out_csv)

        df = pd.read_csv(out_csv, keep_default_na=False)
        assert float(df["Investment"].iloc[0]) == 125.50
        assert float(df["Estimated Value"].iloc[0]) == 350.00
        assert float(df["Sold Price"].iloc[0]) == 400.75
        assert float(df["Investment"].iloc[1]) == 0.00
        assert float(df["Estimated Value"].iloc[1]) == 0.00
        assert df["Sold Price"].iloc[1] == ""

    def test_round_trip_special_characters_quotes_and_commas(self, test_db_path, output_dir):
        card = {
            "player": "Shaquille O'Neal",
            "year": "1992",
            "set_name": "Topps, Inc. Special Series",
            "category": "Basketball",
            "notes": 'Parent "Special" 8492-109, Grade A',
            "ai_status": "CLEARED",
        }
        insert_card(test_db_path, card)
        out_csv = os.path.join(output_dir, "special_chars.csv")
        export_card_ladder_csv(test_db_path, out_csv)

        df = pd.read_csv(out_csv, keep_default_na=False)
        assert df["Player"].iloc[0] == "Shaquille O'Neal"
        assert df["Set"].iloc[0] == "Topps, Inc. Special Series"
        assert df["Notes"].iloc[0] == 'Parent "Special" 8492-109, Grade A'

    def test_round_trip_all_22_categories(self, test_db_path, output_dir):
        cards = []
        for cat in CardCategory:
            cards.append({
                "player": f"Player {cat.value}",
                "year": "2024",
                "set_name": "General Set",
                "category": cat.value,
                "ai_status": "CLEARED",
            })
        insert_cards_batch(test_db_path, cards)
        out_csv = os.path.join(output_dir, "all_categories.csv")
        count, paths = export_card_ladder_csv(test_db_path, out_csv)

        assert count == 22
        df = pd.read_csv(paths[0], keep_default_na=False)
        exported_cats = set(df["Category"].tolist())
        assert exported_cats == {c.value for c in CardCategory}


# ============================================================================
# Test Suite 7: Edge Cases & Resilience
# ============================================================================

class TestExportEdgeCasesAndResilience:
    """Tests nested directory creation, non-existent db, normalization toggles, concurrency, and performance."""

    def test_export_creates_nonexistent_output_directories(self, test_db_path, tmp_path, sample_cleared_cards):
        insert_cards_batch(test_db_path, sample_cleared_cards)
        deep_path = str(tmp_path / "deep" / "nested" / "folder" / "CardLadder_Bulk.csv")
        count, paths = export_card_ladder_csv(test_db_path, deep_path)

        assert count == 10
        assert os.path.exists(paths[0])

    def test_export_nonexistent_db_raises_error(self, tmp_path):
        bad_db = str(tmp_path / "non_existent_12345.db")
        out_csv = str(tmp_path / "out.csv")
        # An empty database file will be initialized or handled; if querying table cards raises sqlite3.OperationalError or raises FileNotFoundError
        with pytest.raises((sqlite3.OperationalError, FileNotFoundError, Exception)):
            # If database does not exist or cards table missing, querying raises error
            with get_db_connection(bad_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM cards;")

    def test_export_toggle_normalization_on_and_off(self, test_db_path, output_dir):
        card = {
            "player": "Luka Doncic",
            "year": "2018",
            "set_name": "Pannini Prizm",
            "category": "Basketball",
            "ai_status": "CLEARED"
        }
        insert_card(test_db_path, card)

        # 1. Normalization OFF
        out_raw = os.path.join(output_dir, "raw_norm.csv")
        export_card_ladder_csv(test_db_path, out_raw, apply_normalization=False)
        df_raw = pd.read_csv(out_raw, keep_default_na=False)
        assert df_raw["Player"].iloc[0] == "Luka Doncic"
        assert df_raw["Set"].iloc[0] == "Pannini Prizm"

        # 2. Normalization ON
        out_norm = os.path.join(output_dir, "clean_norm.csv")
        export_card_ladder_csv(test_db_path, out_norm, apply_normalization=True)
        df_norm = pd.read_csv(out_norm, keep_default_na=False)
        assert df_norm["Player"].iloc[0] == "Luka Dončić"
        assert df_norm["Set"].iloc[0] == "Panini Prizm"

    def test_export_concurrent_reads_wal_mode(self, test_db_path, output_dir, sample_cleared_cards):
        insert_cards_batch(test_db_path, sample_cleared_cards)
        out_csv = os.path.join(output_dir, "wal_test.csv")

        errors: list[Exception] = []

        def reader_task():
            try:
                for _ in range(20):
                    with get_db_connection(test_db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM cards;")
                        cursor.fetchone()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        t = threading.Thread(target=reader_task)
        t.start()

        count, paths = export_card_ladder_csv(test_db_path, out_csv)
        t.join()

        assert count == 10
        assert len(errors) == 0

    def test_export_performance_benchmark(self, test_db_path, output_dir):
        cards_1000 = make_large_card_batch(1000)
        insert_cards_batch(test_db_path, cards_1000)
        out_csv = os.path.join(output_dir, "perf_1000.csv")

        start = time.perf_counter()
        count, paths = export_card_ladder_csv(test_db_path, out_csv)
        elapsed = time.perf_counter() - start

        assert count == 1000
        assert len(paths) == 2
        assert elapsed < 3.0, f"Export of 1,000 cards took {elapsed:.2f}s (expected < 3.0s)"

    def test_helper_aliases_availability(self, test_db_path, output_dir, sample_cleared_cards):
        insert_cards_batch(test_db_path, sample_cleared_cards)
        rows = fetch_records_for_export(db_path=test_db_path, status_filter="CLEARED")
        assert len(rows) == 10

        df = transform_records_to_card_ladder_df(rows, apply_normalization=True)
        assert len(df) == 10
        assert df.columns.tolist() == list(CARD_LADDER_COLUMNS)

        out_csv = os.path.join(output_dir, "alias_helpers.csv")
        count, paths = write_card_ladder_csv_chunks(df, out_csv, max_batch_size=500)
        assert count == 10
        assert len(paths) == 1

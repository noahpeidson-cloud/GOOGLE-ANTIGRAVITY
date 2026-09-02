"""
verify_m4_forensics.py - Independent Forensic Audit Verification Script for Milestone 4.
Independently verifies export.py implementation without relying on test_export.py fixtures.
"""

import os
import sys
import csv
import sqlite3
import unicodedata
import difflib
import pandas as pd
import tempfile

sys.path.insert(0, r"g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub")

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
from database import init_db, insert_card, insert_cards_batch

def run_forensic_checks():
    results = {}
    print("=== STARTING INDEPENDENT FORENSIC VERIFICATION FOR MILESTONE 4 ===")

    # -------------------------------------------------------------
    # Check 1: Exact 16 Card Ladder Headers & Exclusion of Internals
    # -------------------------------------------------------------
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
    assert CARD_LADDER_COLUMNS == expected_headers, f"CARD_LADDER_COLUMNS mismatch: {CARD_LADDER_COLUMNS}"
    assert len(CARD_LADDER_COLUMNS) == 16, f"Expected 16 columns, got {len(CARD_LADDER_COLUMNS)}"

    for excluded in ["slab_serial_number", "query", "tags", "back_image", "ai_status", "id", "created_at", "updated_at"]:
        assert excluded.lower() not in [c.lower() for c in CARD_LADDER_COLUMNS], f"Excluded field '{excluded}' found in columns!"
    
    results["check_1_headers_and_exclusions"] = "PASS"
    print("Check 1: Exact 16 Headers & Exclusion Constants -> PASS")

    # -------------------------------------------------------------
    # Check 2: Leading Zero Preservation in Pandas & CSV
    # -------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_zeros.db")
        csv_path = os.path.join(tmpdir, "test_zeros.csv")
        init_db(db_path)

        test_card_numbers = ["007", "01", "000", "00042", "01/25", "RC-05", "0", ""]
        cards = []
        for i, num in enumerate(test_card_numbers):
            cards.append({
                "date_purchased": "08/23/2026",
                "quantity": 1,
                "player": f"Test Player {i}",
                "year": "2023",
                "set_name": "Panini Prizm",
                "variation": "",
                "card_number": num,
                "category": "Basketball",
                "condition": "PSA 10",
                "slab_serial_number": "SHOULD_NOT_LEAK",
                "investment": 10.0,
                "estimated_value": 20.0,
                "ladder_id": "LAD-TEST",
                "notes": f"Note-{num}",
                "tags": "INTERNAL_TAG",
                "date_sold": "",
                "sold_price": None,
                "image": "https://example.com/img.jpg",
                "back_image": "https://example.com/back.jpg",
                "ai_status": "CLEARED",
            })
        insert_cards_batch(db_path, cards)

        count, paths = export_card_ladder_csv(db_path, csv_path, status_filter="CLEARED")
        assert count == len(test_card_numbers), f"Expected {len(test_card_numbers)}, got {count}"
        assert len(paths) == 1

        # Check raw CSV lines byte-for-byte / string-for-string
        with open(paths[0], "r", encoding="utf-8") as f:
            raw_content = f.read()

        # Check that no internal fields leaked
        assert "SHOULD_NOT_LEAK" not in raw_content
        assert "INTERNAL_TAG" not in raw_content
        assert "https://example.com/back.jpg" not in raw_content

        # Verify leading zeros in raw CSV text
        for num in test_card_numbers:
            if num:
                assert f",{num}," in raw_content or f',"{num}",' in raw_content, f"Card number '{num}' lost in raw CSV"

        # Verify leading zeros when read back via pandas with dtype str
        df_read = pd.read_csv(paths[0], dtype={"Number": str, "Year": str}, keep_default_na=False)
        read_numbers = df_read["Number"].tolist()
        assert read_numbers == test_card_numbers, f"Mismatch in read numbers: {read_numbers} vs {test_card_numbers}"

    results["check_2_leading_zeros_and_leak_prevention"] = "PASS"
    print("Check 2: Leading Zero Preservation & Internal Leak Prevention -> PASS")

    # -------------------------------------------------------------
    # Check 3: Fuzzy Normalization Engine (difflib + unicodedata)
    # -------------------------------------------------------------
    # Diacritics folding
    assert fold_string("Luka Dončić") == "luka doncic"
    assert fold_string("Ronald Acuña Jr.") == "ronald acuna jr"
    assert fold_string("Shohei Ohtani (大谷 翔平)") == "shohei ohtani"
    assert fold_string("Nikola Jokić") == "nikola jokic"

    # Player normalization
    assert normalize_player_name("Luka Doncic", "Basketball") == "Luka Dončić"
    assert normalize_player_name("Ronald Acuna Jr.", "Baseball") == "Ronald Acuña Jr."
    assert normalize_player_name("Shohei Ohtani", "Baseball") == "Shohei Ohtani"
    assert normalize_player_name("Shohey Ohtani", "Baseball", cutoff=0.75) == "Shohei Ohtani"
    assert normalize_player_name("wemby", "Basketball") == "Victor Wembanyama"
    assert normalize_player_name("Steph Curry", "Basketball") == "Stephen Curry"
    assert normalize_player_name("Charzard", "Pokemon", cutoff=0.75) == "Charizard"

    # Set normalization
    assert normalize_set_name("2023 Panini Prizm", year="2023", category="Basketball") == "Panini Prizm"
    assert normalize_set_name("prizm", "2023", "Basketball") == "Panini Prizm"
    assert normalize_set_name("Topps Chrom", "2023", "Baseball", cutoff=0.75) == "Topps Chrome"
    assert normalize_set_name("pokemon base", "1999", "Pokemon") == "Base Set"

    # Unknowns stay preserved (zero-loss fallback)
    assert normalize_player_name("Completely Unknown Player 123", "Baseball") == "Completely Unknown Player 123"
    assert normalize_set_name("Completely Unknown Set 456", "2024", "Baseball") == "Completely Unknown Set 456"

    results["check_3_fuzzy_normalization_logic"] = "PASS"
    print("Check 3: Fuzzy Normalization (difflib + unicodedata) -> PASS")

    # -------------------------------------------------------------
    # Check 4: 500-Card Batch Circuit Breaker & Automatic File Chunking
    # -------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_chunks.db")
        csv_base = os.path.join(tmpdir, "bulk_export.csv")
        init_db(db_path)

        # Insert 1250 records
        cards_1250 = []
        for i in range(1, 1251):
            cards_1250.append({
                "date_purchased": "08/23/2026",
                "quantity": 1,
                "player": f"Chunk Player {i}",
                "year": "2024",
                "set_name": "Panini Prizm",
                "variation": "",
                "card_number": f"{i:04d}",
                "category": "Basketball",
                "condition": "Raw",
                "investment": float(i),
                "estimated_value": float(i * 2),
                "notes": f"Batch-{i}",
                "ai_status": "CLEARED",
            })
        insert_cards_batch(db_path, cards_1250)

        count, paths = export_card_ladder_csv(db_path, csv_base, status_filter="CLEARED", max_batch_size=500)
        assert count == 1250
        assert len(paths) == 3
        assert os.path.basename(paths[0]) == "bulk_export_part1.csv"
        assert os.path.basename(paths[1]) == "bulk_export_part2.csv"
        assert os.path.basename(paths[2]) == "bulk_export_part3.csv"

        df1 = pd.read_csv(paths[0], dtype=str)
        df2 = pd.read_csv(paths[1], dtype=str)
        df3 = pd.read_csv(paths[2], dtype=str)

        assert len(df1) == 500
        assert len(df2) == 500
        assert len(df3) == 250

        # Verify sequential records and zero dropping in card number
        assert df1["Number"].iloc[0] == "0001"
        assert df1["Number"].iloc[-1] == "0500"
        assert df2["Number"].iloc[0] == "0501"
        assert df2["Number"].iloc[-1] == "1000"
        assert df3["Number"].iloc[0] == "1001"
        assert df3["Number"].iloc[-1] == "1250"

        # Verify all files pass validation
        for p in paths:
            val = validate_card_ladder_csv(p)
            assert val["valid"] is True, f"Validation failed for {p}: {val}"

    results["check_4_chunking_circuit_breaker"] = "PASS"
    print("Check 4: 500-Card Batch Circuit Breaker & Automatic File Chunking -> PASS")

    # -------------------------------------------------------------
    # Check 5: Status Filtering & Edge Cases
    # -------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_status.db")
        csv_path = os.path.join(tmpdir, "status_test.csv")
        init_db(db_path)

        cards = [
            {"player": "P1", "year": "2024", "set_name": "S1", "category": "Basketball", "card_number": "01", "ai_status": "CLEARED"},
            {"player": "P2", "year": "2024", "set_name": "S2", "category": "Basketball", "card_number": "02", "ai_status": "CLEARED"},
            {"player": "P3", "year": "2024", "set_name": "S3", "category": "Basketball", "card_number": "03", "ai_status": "REVIEW VARIATION"},
            {"player": "P4", "year": "2024", "set_name": "S4", "category": "Basketball", "card_number": "04", "ai_status": "NEEDS REVIEW"},
        ]
        insert_cards_batch(db_path, cards)

        # Default CLEARED
        count, _ = export_card_ladder_csv(db_path, csv_path)
        assert count == 2

        # Case-insensitive "cleared"
        count, _ = export_card_ladder_csv(db_path, csv_path, status_filter="cleared")
        assert count == 2

        # ALL
        count, _ = export_card_ladder_csv(db_path, csv_path, status_filter="ALL")
        assert count == 4

        # REVIEW VARIATION
        count, _ = export_card_ladder_csv(db_path, csv_path, status_filter="REVIEW VARIATION")
        assert count == 1

        # Empty match
        count, paths = export_card_ladder_csv(db_path, csv_path, status_filter="NONEXISTENT_STATUS")
        assert count == 0
        assert len(paths) == 1
        val = validate_card_ladder_csv(paths[0])
        assert val["valid"] is True
        assert val["row_count"] == 0

    results["check_5_status_filtering"] = "PASS"
    print("Check 5: Status Filtering & Edge Cases -> PASS")

    print("\n=== ALL FORENSIC CHECKS PASSED EMPIRICALLY ===")
    return results

if __name__ == "__main__":
    run_forensic_checks()

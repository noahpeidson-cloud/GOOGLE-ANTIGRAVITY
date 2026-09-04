"""
test_adversarial_m4.py - Adversarial Stress & Chaos Test Suite for Milestone 4 (Export Pipeline).
Author: Forensic Auditor
"""

import os
import sys
import csv
import tempfile
import sqlite3
import pandas as pd
import pytest

sys.path.insert(0, r"g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub")

from export import (
    CARD_LADDER_COLUMNS,
    EXCLUDED_INTERNAL_FIELDS,
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

def run_adversarial_tests():
    print("=== STARTING ADVERSARIAL STRESS & INTEGRITY SUITE FOR MILESTONE 4 ===")

    # 1. SQL Injection attempt via status_filter
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "sqli.db")
        csv_path = os.path.join(tmpdir, "sqli.csv")
        init_db(db_path)

        insert_cards_batch(db_path, [
            {"player": "P1", "year": "2024", "set_name": "S1", "category": "Basketball", "ai_status": "CLEARED"},
            {"player": "P2", "year": "2024", "set_name": "S2", "category": "Basketball", "ai_status": "NEEDS REVIEW"},
        ])

        # Attempt SQL injection: "' OR '1'='1"
        count, paths = export_card_ladder_csv(db_path, csv_path, status_filter="' OR '1'='1")
        # Parameterized query should treat this as a literal string, returning 0 records
        assert count == 0, f"SQL injection vulnerability detected! Returned count {count}"
        print("Adversarial Check 1: SQL Injection in status_filter parameterized -> PASS")

    # 2. Embedded quotes, commas, newlines, tabs in notes and player fields
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "escapes.db")
        csv_path = os.path.join(tmpdir, "escapes.csv")
        init_db(db_path)

        weird_notes = 'Line 1\nLine 2\r\nLine 3, with "Quotes" and commas, and \t tabs.'
        insert_card(db_path, {
            "player": 'Shaquille "Shaq" O\'Neal',
            "year": "1992",
            "set_name": "Upper Deck, Special Ed.",
            "variation": 'Gold "Refractor" \n Special',
            "card_number": "0001/0100",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "99988877",
            "investment": 1234.56,
            "estimated_value": 7890.12,
            "notes": weird_notes,
            "ai_status": "CLEARED",
        })

        count, paths = export_card_ladder_csv(db_path, csv_path, status_filter="ALL")
        assert count == 1
        val = validate_card_ladder_csv(paths[0])
        assert val["valid"] is True

        # Read back via pandas and verify lossless parsing
        df = pd.read_csv(paths[0], dtype={"Number": str}, keep_default_na=False)
        assert df["Number"].iloc[0] == "0001/0100"
        assert df["Player"].iloc[0] == "Shaquille O'Neal"
        assert df["Notes"].iloc[0] == weird_notes
        print("Adversarial Check 2: Complex CSV escaping and multi-line fields -> PASS")

    # 3. Boundary batch partitioning (exact 499, 500, 501, 1000, 1001)
    with tempfile.TemporaryDirectory() as tmpdir:
        for n_cards in [0, 1, 499, 500, 501, 1000, 1001]:
            db_path = os.path.join(tmpdir, f"batch_{n_cards}.db")
            csv_path = os.path.join(tmpdir, f"batch_{n_cards}.csv")
            init_db(db_path)

            if n_cards > 0:
                batch = []
                for i in range(1, n_cards + 1):
                    batch.append({
                        "player": f"Player {i}",
                        "year": "2024",
                        "set_name": "Prizm",
                        "category": "Basketball",
                        "card_number": f"{i:05d}",
                        "ai_status": "CLEARED",
                    })
                insert_cards_batch(db_path, batch)

            count, paths = export_card_ladder_csv(db_path, csv_path, max_batch_size=500)
            assert count == n_cards

            if n_cards == 0:
                assert len(paths) == 1
                val = validate_card_ladder_csv(paths[0])
                assert val["valid"] is True
                assert val["row_count"] == 0
            elif n_cards <= 500:
                assert len(paths) == 1
                assert paths[0] == csv_path
                val = validate_card_ladder_csv(paths[0])
                assert val["valid"] is True
                assert val["row_count"] == n_cards
            elif n_cards == 501:
                assert len(paths) == 2
                assert os.path.basename(paths[0]) == f"batch_{n_cards}_part1.csv"
                assert os.path.basename(paths[1]) == f"batch_{n_cards}_part2.csv"
                assert len(pd.read_csv(paths[0])) == 500
                assert len(pd.read_csv(paths[1])) == 1
            elif n_cards == 1000:
                assert len(paths) == 2
                assert len(pd.read_csv(paths[0])) == 500
                assert len(pd.read_csv(paths[1])) == 500
            elif n_cards == 1001:
                assert len(paths) == 3
                assert len(pd.read_csv(paths[0])) == 500
                assert len(pd.read_csv(paths[1])) == 500
                assert len(pd.read_csv(paths[2])) == 1

        print("Adversarial Check 3: Boundary batch partitioning (0, 1, 499, 500, 501, 1000, 1001) -> PASS")

    # 4. Diacritics and multilingual player name edge cases
    test_names = [
        ("Luka Dončić", "Luka Dončić"),
        ("luka doncic", "Luka Dončić"),
        ("LUKA DONČIĆ", "Luka Dončić"),
        ("Nikola Jokić", "Nikola Jokić"),
        ("nikola jokic", "Nikola Jokić"),
        ("Ronald Acuña Jr.", "Ronald Acuña Jr."),
        ("ronald acuna jr", "Ronald Acuña Jr."),
        ("Iga Świątek", "Iga Świątek"),
        ("iga swiatek", "Iga Świątek"),
        ("Tim Stützle", "Tim Stützle"),
        ("tim stutzle", "Tim Stützle"),
        ("Alexis Lafrenière", "Alexis Lafrenière"),
        ("alexis lafreniere", "Alexis Lafrenière"),
        ("Shohei Ohtani (大谷 翔平)", "Shohei Ohtani"),
    ]
    for raw, expected in test_names:
        res = normalize_player_name(raw)
        assert res == expected, f"Diacritic normalization failed for '{raw}': got '{res}', expected '{expected}'"
    print("Adversarial Check 4: Diacritics and multilingual player name folding -> PASS")

    # 5. Verify that internal fields NEVER leak in headers or data
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "leak_test.db")
        csv_path = os.path.join(tmpdir, "leak_test.csv")
        init_db(db_path)

        secret_val = "SECRET_TAG_DO_NOT_EXPOSE_998877"
        insert_card(db_path, {
            "player": "Test Player",
            "year": "2024",
            "set_name": "Panini Prizm",
            "category": "Basketball",
            "tags": secret_val,
            "back_image": "https://example.com/secret_back_image.png",
            "ai_status": "CLEARED",
        })

        count, paths = export_card_ladder_csv(db_path, csv_path)
        with open(paths[0], "r", encoding="utf-8") as f:
            raw = f.read()

        assert secret_val not in raw, "Internal tag leaked into Card Ladder CSV!"
        assert "secret_back_image" not in raw, "Back image leaked into Card Ladder CSV!"
        print("Adversarial Check 5: Zero leakage of internal fields -> PASS")

    print("\n=== ALL ADVERSARIAL STRESS CHECKS PASSED EMPIRICALLY ===")

if __name__ == "__main__":
    run_adversarial_tests()

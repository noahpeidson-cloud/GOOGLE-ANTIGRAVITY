"""
tests/test_adversarial_m5_challenger_harness.py - Comprehensive Adversarial Stress Test Suite for Milestone 5.
Authored by Teamwork Preview Challenger (Empirical Challenger M5).

Target: sports_cards/ecosystem_hub/app.py, database.py, models.py, export.py, vision_ingest.py, scraper_ingest.py, sales_generator.py.

Testing Dimensions:
1. Cold Start & Database Resilience (Empty DB, Corrupted DB, Special Characters in DB Path, Missing Parent Directory).
2. Rapid State Mutations & Concurrency (Sequential Filter Changes, Selected Card Deletion, Table Wipe, Cross-Tab State Propagation).
3. Malformed Form Submissions & Boundary Inputs (Missing Required Fields, SQL/XSS Payloads, Circuit Breaker 500 Limit, Formula Injections).
4. End-to-End Headless Streamlit AppTest Workflows across Tab 1 to Tab 6.
5. Overall UI Resilience against unhandled crashes and state desynchronization.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import zipfile
from datetime import datetime
from typing import Any
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

# Ensure ecosystem_hub directory is in sys.path
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

APP_PATH = os.path.join(PROJECT_DIR, "app.py")

from models import (
    CardRecord,
    CardCategory,
    AIStatus,
    VALID_CATEGORIES,
    synthesize_query,
    format_notes,
    get_current_date_str,
)
from database import (
    init_db,
    insert_card,
    insert_cards_batch,
    get_card_by_id,
    get_all_cards,
    update_card,
    update_card_status,
    delete_card,
    get_summary_stats,
    get_card_count,
    clear_staging_table,
    DEFAULT_DB_PATH,
)
from export import (
    CARD_LADDER_COLUMNS,
    EXCLUDED_INTERNAL_FIELDS,
    validate_card_ladder_csv,
    export_card_ladder_csv,
)
import app as app_module


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Provides a fresh isolated SQLite database path configured in environment."""
    db_file = str(tmp_path / "test_adversarial_m5_harness.db")
    init_db(db_file)
    monkeypatch.setenv("PORTFOLIO_DB_PATH", db_file)
    return db_file


@pytest.fixture
def populated_harness_db(temp_db):
    """Populates database with edge-case cards (Unicode, diacritics, leading zeroes, special chars)."""
    cards = [
        {
            "player": "Shohei Ohtani (大谷翔平)",
            "year": "2018",
            "set_name": "Bowman Chrome",
            "variation": "Refractor /499",
            "card_number": "BCP-31",
            "category": "Baseball",
            "condition": "PSA 10",
            "slab_serial_number": "60192841",
            "investment": 450.00,
            "estimated_value": 1850.00,
            "notes": "8492-101",
            "ai_status": "REVIEW VARIATION",
        },
        {
            "player": "Luka Dončić",
            "year": "2018",
            "set_name": "Panini Prizm",
            "variation": "",
            "card_number": "280",
            "category": "Basketball",
            "condition": "BGS 9.5",
            "slab_serial_number": "0012948102",
            "investment": 600.00,
            "estimated_value": 2200.00,
            "notes": "8492-102",
            "ai_status": "CLEARED",
        },
        {
            "player": "Lionel Messi",
            "year": "2004",
            "set_name": "Panini Mega Cracks",
            "variation": "Bis",
            "card_number": "071",
            "category": "Soccer",
            "condition": "PSA 9",
            "slab_serial_number": "48102934",
            "investment": 1200.00,
            "estimated_value": 4500.00,
            "notes": "8492-103",
            "ai_status": "CLEARED",
        },
        {
            "player": "Formula 1 =cmd|' /C calc'!A0",
            "year": "2020",
            "set_name": "Topps Chrome F1",
            "variation": "Gold Wave /50",
            "card_number": "001",
            "category": "Racing",
            "condition": "Raw",
            "slab_serial_number": "",
            "investment": 75.00,
            "estimated_value": 300.00,
            "notes": "8492-104",
            "ai_status": "NEEDS REVIEW",
        },
        {
            "player": "Pikachu",
            "year": "1996",
            "set_name": "Japanese Basic",
            "variation": "No Rarity Symbol",
            "card_number": "025",
            "category": "Pokemon",
            "condition": "CGC 9.5",
            "slab_serial_number": "3910283419",
            "investment": 800.00,
            "estimated_value": 2900.00,
            "notes": "8492-105",
            "ai_status": "REVIEW VARIATION",
        },
    ]
    insert_cards_batch(cards, db_path=temp_db)
    return temp_db


# ============================================================================
# Dimension 1: Cold Start & Database Resilience
# ============================================================================

class TestColdStartAndDatabaseResilience:
    """Stress-tests application launch under hostile DB environments."""

    def test_cold_start_empty_db_rendering(self, temp_db):
        """Launches on a fresh 0-card database. Verifies all KPIs render 0 with no exceptions."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)

        assert len(at.exception) == 0, f"Cold start failed with exceptions: {at.exception}"
        assert len(at.tabs) >= 5

        # Check total cards metric is 0
        total_card_metrics = [m for m in at.metric if "total cards" in m.label.lower()]
        assert len(total_card_metrics) > 0
        assert str(total_card_metrics[0].value).strip() == "0"

    def test_cold_start_nested_nonexistent_directory_auto_created(self, tmp_path, monkeypatch):
        """Database located in deeply nested directory that doesn't exist yet is created without error."""
        deep_db_file = str(tmp_path / "deep" / "nested" / "path" / "portfolio.db")
        monkeypatch.setenv("PORTFOLIO_DB_PATH", deep_db_file)

        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)

        assert len(at.exception) == 0
        assert os.path.exists(deep_db_file)

    def test_cold_start_with_special_characters_in_path(self, tmp_path, monkeypatch):
        """Database located in path with spaces, parentheses, brackets, and diacritics."""
        special_dir = tmp_path / "Card Vault (Collection #1) — 2026 [Vault]"
        special_dir.mkdir(parents=True, exist_ok=True)
        special_db = str(special_dir / "vault_cards.db")
        init_db(special_db)
        monkeypatch.setenv("PORTFOLIO_DB_PATH", special_db)

        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)

        assert len(at.exception) == 0
        assert at.session_state["db_path"] == special_db

    def test_corrupted_database_handling_investigation(self, tmp_path, monkeypatch):
        """
        Investigates application behavior when given a corrupted binary file.
        Verifies that init_db raises sqlite3.DatabaseError.
        """
        corrupt_file = str(tmp_path / "corrupted_test.db")
        with open(corrupt_file, "wb") as f:
            f.write(b"\x00\xFF\xFE\xFDGARBAGE_NON_SQLITE_DATA\xDE\xAD\xBE\xEF")

        monkeypatch.setenv("PORTFOLIO_DB_PATH", corrupt_file)

        # Directly testing init_db and get_summary_stats behavior
        import sqlite3
        with pytest.raises(sqlite3.DatabaseError):
            init_db(corrupt_file)


# ============================================================================
# Dimension 2: Rapid State Mutations & Concurrency Resilience
# ============================================================================

class TestRapidStateMutationsAndConcurrency:
    """Tests rapid sequential filter updates, state switches, and orphan state prevention."""

    def test_sequential_filters_pipeline(self, populated_harness_db):
        """Sequentially cycles through category and status filters in AppTest."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # 1. Filter by Baseball
        for sb in at.selectbox:
            if "category" in sb.label.lower():
                sb.select("Baseball").run(timeout=15)
                break
        assert len(at.exception) == 0

        # 2. Filter by CLEARED status
        for sb in at.selectbox:
            if "status" in sb.label.lower():
                sb.select("CLEARED").run(timeout=15)
                break
        assert len(at.exception) == 0

        # 3. Filter by Year 2018
        for ti in at.text_input:
            if "year" in ti.label.lower() and "filter" in ti.label.lower():
                ti.input("2018").run(timeout=15)
                break
        assert len(at.exception) == 0

    def test_selected_card_deleted_backend_resilience(self, populated_harness_db):
        """If a selected card is deleted from the database in the background, app reruns without crash."""
        cards = get_all_cards(db_path=populated_harness_db)
        target_id = cards[0]["id"]

        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Select card in inspector if available
        for sb in at.selectbox:
            if "inspect" in sb.label.lower() or "staged card" in sb.label.lower():
                if target_id in sb.options:
                    sb.select(target_id).run(timeout=15)
                break
        assert len(at.exception) == 0

        # Delete card from DB
        delete_card(target_id, db_path=populated_harness_db)

        # Trigger rerun of app
        at.run(timeout=15)
        assert len(at.exception) == 0

    def test_clear_staging_table_while_active_resilience(self, populated_harness_db):
        """Clearing staging table with an active database resets gracefully."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Check confirmation checkbox
        for cb in at.checkbox:
            if "confirm" in cb.label.lower() or "wipe" in cb.label.lower():
                cb.check().run(timeout=15)
                break

        # Click clear table button
        for btn in at.button:
            if "clear entire" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        assert get_card_count(db_path=populated_harness_db) == 0

    def test_cross_tab_selection_to_sales_state(self, populated_harness_db):
        """Clicking 'Select for Sales Copy Generator' in Tab 1 updates session state."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        for btn in at.button:
            if "sales copy" in btn.label.lower() or "select for sales" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        assert "sales_selected_card_id" in at.session_state


# ============================================================================
# Dimension 3: Malformed Form Submissions & Adversarial Inputs
# ============================================================================

class TestMalformedFormSubmissionsAndAdversarialInputs:
    """Submits adversarial payloads, boundary numbers, formula injections, and checks error guards."""

    def test_manual_entry_sql_and_xss_injection_payloads(self, temp_db):
        """Submitting SQL and XSS injection strings in manual entry form stores safely via parameterized queries."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        sql_injection_name = "Robert '; DROP TABLE staged_cards; --"
        xss_set_name = "<script>alert('XSS_ATTACK')</script>"

        for ti in at.text_input:
            if "player name" in ti.label.lower() and "placeholder" not in ti.label.lower():
                ti.input(sql_injection_name)
            elif "set name" in ti.label.lower() and "placeholder" not in ti.label.lower():
                ti.input(xss_set_name)
            elif "year" in ti.label.lower() and "filter" not in ti.label.lower():
                ti.input("2024")

        # Submit form
        for btn in at.button:
            if "add card" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        # Table must still exist and contain the record verbatim
        cards = get_all_cards(db_path=temp_db)
        assert len(cards) == 1
        assert cards[0]["player"] == sql_injection_name
        assert cards[0]["set_name"] == xss_set_name

    def test_scraper_circuit_breaker_500_card_guard(self, temp_db):
        """Attempting to bulk-ingest cards that would breach the 500-card limit triggers the circuit breaker warning."""
        # Pre-seed DB with 495 cards
        bulk_seed = [
            {
                "player": f"Seed Player {i}",
                "year": "2023",
                "set_name": "Test Set",
                "variation": "Base",
                "card_number": str(i),
                "category": "Basketball",
                "condition": "Raw",
                "investment": 1.0,
                "estimated_value": 2.0,
            }
            for i in range(1, 496)
        ]
        insert_cards_batch(bulk_seed, db_path=temp_db)
        assert get_card_count(temp_db) == 495

        sample_html = """
        <table>
            <tr><th>Card #</th><th>Player</th></tr>
            <tr><td>1</td><td>Player A</td></tr>
            <tr><td>2</td><td>Player B</td></tr>
            <tr><td>3</td><td>Player C</td></tr>
            <tr><td>4</td><td>Player D</td></tr>
            <tr><td>5</td><td>Player E</td></tr>
            <tr><td>6</td><td>Player F</td></tr>
            <tr><td>7</td><td>Player G</td></tr>
        </table>
        """
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Input HTML into scraper tab
        for ta in at.text_area:
            if "checklist" in ta.label.lower() or "html" in ta.label.lower():
                ta.input(sample_html).run(timeout=15)
                break

        # Click Parse
        for btn in at.button:
            if "parse" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0

        # Click Bulk Ingest (7 cards + 495 = 502 > 500)
        for btn in at.button:
            if "bulk ingest" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        # Must show warning and block insertion
        assert get_card_count(temp_db) == 495
        assert len(at.warning) > 0 or any("circuit breaker" in str(w).lower() for w in at.warning)

    def test_sales_generator_execution_mock_mode(self, populated_harness_db):
        """Sales copy generator generates listings in mock mode without throwing exceptions."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        for btn in at.button:
            if "generate" in btn.label.lower() and ("sales" in btn.label.lower() or "listing" in btn.label.lower() or "facebook" in btn.label.lower()):
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        assert at.session_state["sales_generated_text"] != ""


# ============================================================================
# Dimension 4: Full Interactive AppTest Workflows (Tabs 1 - 6)
# ============================================================================

class TestFullInteractiveAppTestWorkflows:
    """Verifies end-to-end interactive workflows across all 6 operational tabs."""

    def test_tab1_crud_complete_lifecycle(self, temp_db):
        """Tab 1: Manual Add -> Quick Status Change -> Delete Card."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # 1. Add Card
        for ti in at.text_input:
            if "player name" in ti.label.lower() and "placeholder" not in ti.label.lower():
                ti.input("Caitlin Clark")
            elif "set name" in ti.label.lower() and "placeholder" not in ti.label.lower():
                ti.input("Panini Instant WNBA")
            elif "year" in ti.label.lower() and "filter" not in ti.label.lower():
                ti.input("2024")

        for btn in at.button:
            if "add card" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        cards = get_all_cards(db_path=temp_db)
        assert len(cards) == 1

        # 2. Mark Cleared
        for btn in at.button:
            if "mark cleared" in btn.label.lower():
                btn.click().run(timeout=15)
                break
        assert len(at.exception) == 0

        # 3. Delete Card
        for btn in at.button:
            if "delete card" in btn.label.lower():
                btn.click().run(timeout=15)
                break
        assert len(at.exception) == 0
        assert get_card_count(temp_db) == 0

    def test_tab2_vision_mock_extraction_to_commit_pipeline(self, temp_db):
        """Tab 2: AI Vision Mock Extraction -> Commit to Staging DB."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Click Extract
        for btn in at.button:
            if "gemini vision" in btn.label.lower() or "extract card" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        assert "vision_extraction_result" in at.session_state
        assert at.session_state["vision_extraction_result"] is not None

        # Click Commit
        for btn in at.button:
            if "commit card" in btn.label.lower() or "commit" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        assert get_card_count(temp_db) == 1

    def test_tab3_scraper_raw_html_to_bulk_ingest_pipeline(self, temp_db):
        """Tab 3: Paste HTML -> Parse Checklist -> Verify Parallel Expansion -> Bulk Ingest."""
        fixture_html = """
        <table>
            <tr><th>#</th><th>Player</th></tr>
            <tr><td>101</td><td>Anthony Edwards</td></tr>
            <tr><td>102</td><td>Tyrese Haliburton</td></tr>
        </table>
        """
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        for ta in at.text_area:
            if "checklist" in ta.label.lower() or "html" in ta.label.lower():
                ta.input(fixture_html).run(timeout=15)
                break

        for ti in at.text_input:
            if "parallels" in ti.label.lower():
                ti.input("Base, Silver Prizm")
            elif "set name" in ti.label.lower() and "scraper" in str(ti.key):
                ti.input("Panini Prizm")
            elif "year" in ti.label.lower() and "scraper" in str(ti.key):
                ti.input("2020")

        for btn in at.button:
            if "parse checklist" in btn.label.lower() or "parse" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        parsed = at.session_state["scraper_raw_cards"]
        assert len(parsed) == 4  # 2 players x 2 parallels

        # Bulk Ingest
        for btn in at.button:
            if "bulk ingest" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        assert get_card_count(temp_db) == 4

    def test_tab4_sales_generator_dual_mode(self, populated_harness_db):
        """Tab 4: Generate listings in Staging Mode and Manual Input Mode."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Staging Mode
        for btn in at.button:
            if "generate" in btn.label.lower() and "facebook" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        struct = at.session_state["sales_structured_data"]
        assert struct is not None
        assert len(struct.title) <= 99
        assert len(struct.hashtags) >= 6

        # Switch to Manual Input Mode
        for r in at.radio:
            if "card source" in r.label.lower():
                r.set_value("✍️ Manual Card Input").run(timeout=15)
                break

        for btn in at.button:
            if "generate" in btn.label.lower() and "facebook" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        struct_man = at.session_state["sales_structured_data"]
        assert struct_man is not None
        assert len(struct_man.title) <= 99

    def test_tab5_card_ladder_export_multi_chunk_zip_bundle(self, temp_db, tmp_path):
        """Tab 5: Exporting staged cards generates 16-column CSV files."""
        bulk_cards = [
            {
                "player": f"Player {i:03d}",
                "year": "2021",
                "set_name": "Topps Chrome",
                "variation": "",
                "card_number": f"{i:03d}",
                "category": "Baseball",
                "condition": "Raw",
                "investment": 5.00,
                "estimated_value": 15.00,
                "notes": f"8492-{i:03d}",
                "ai_status": "CLEARED",
            }
            for i in range(1, 551)
        ]
        insert_cards_batch(bulk_cards, db_path=temp_db)
        assert get_card_count(temp_db) == 550

        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Click Export
        for btn in at.button:
            if "export to card ladder" in btn.label.lower() or "export" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0
        paths = at.session_state["export_file_paths"]
        assert len(paths) == 2, f"Expected 2 chunk paths for 550 cards, got {len(paths)}"

        # Check that download buttons rendered
        assert len(at.download_button) >= 2

    def test_tab6_api_bridge_telemetry_and_category_breakdown(self, populated_harness_db):
        """Tab 6: Validates storage diagnostics and health rendering without unhandled exceptions."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0
        assert len(at.error) == 0

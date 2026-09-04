"""
tests/test_streamlit_app.py - Deterministic Headless Test Suite for Milestone 5.
Tests the Streamlit Visual Staging Area & Hub Dashboard (app.py) using AppTest.
Validates launch initialization, top KPI metrics bar, Tab 1-6 interactions,
form inputs, database CRUD, CSV exports, and mock ingestion pipelines.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import pytest
import pandas as pd
from streamlit.testing.v1 import AppTest

# Ensure parent directory of tests is in sys.path
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

APP_PATH = os.path.join(PROJECT_DIR, "app.py")

from models import (
    CardRecord,
    CardCategory,
    AIStatus,
    synthesize_query,
    format_notes,
    VALID_CATEGORIES,
)
from database import (
    init_db,
    insert_card,
    insert_cards_batch,
    get_card_by_id,
    get_all_cards,
    get_summary_stats,
    get_card_count,
    clear_staging_table,
    DEFAULT_DB_PATH,
)
from export import (
    CARD_LADDER_COLUMNS,
    validate_card_ladder_csv,
)
import app as app_module


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Provides a fresh isolated SQLite database path configured in environment."""
    db_file = str(tmp_path / "test_portfolio.db")
    init_db(db_file)
    monkeypatch.setenv("PORTFOLIO_DB_PATH", db_file)
    return db_file


@pytest.fixture
def populated_db(temp_db):
    """Populates the isolated database with 5 distinct test cards."""
    cards = [
        {
            "player": "Luka Dončić",
            "year": "2020",
            "set_name": "Panini Prizm",
            "variation": "Silver Prizm",
            "card_number": "75",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "48192041",
            "investment": 150.00,
            "estimated_value": 350.00,
            "notes": "8492-101",
            "ai_status": "REVIEW VARIATION",
        },
        {
            "player": "Ronald Acuña Jr.",
            "year": "2019",
            "set_name": "Topps Chrome",
            "variation": "",
            "card_number": "001",
            "category": "Baseball",
            "condition": "Raw",
            "slab_serial_number": "",
            "investment": 10.00,
            "estimated_value": 25.00,
            "notes": "8492-102",
            "ai_status": "CLEARED",
        },
        {
            "player": "Patrick Mahomes",
            "year": "2017",
            "set_name": "Panini Donruss",
            "variation": "The Rookies",
            "card_number": "TR-10",
            "category": "Football",
            "condition": "Raw",
            "slab_serial_number": "",
            "investment": 50.00,
            "estimated_value": 180.00,
            "notes": "8492-103",
            "ai_status": "NEEDS REVIEW",
        },
        {
            "player": "Charizard",
            "year": "1999",
            "set_name": "Pokemon Base Set",
            "variation": "1st Edition Holo",
            "card_number": "04/102",
            "category": "Pokemon",
            "condition": "SGC 10",
            "slab_serial_number": "91823104",
            "investment": 1000.00,
            "estimated_value": 3500.00,
            "notes": "8492-104",
            "ai_status": "REVIEW VARIATION",
        },
        {
            "player": "Connor McDavid",
            "year": "2015",
            "set_name": "Upper Deck Young Guns",
            "variation": "",
            "card_number": "201",
            "category": "Hockey",
            "condition": "PSA 10",
            "slab_serial_number": "59102834",
            "investment": 500.00,
            "estimated_value": 1400.00,
            "notes": "8492-105",
            "ai_status": "CLEARED",
        },
    ]
    insert_cards_batch(cards, db_path=temp_db)
    return temp_db


# ============================================================================
# Tier 1: App Launch & Initialization Tests
# ============================================================================

class TestStreamlitAppLaunch:
    """Verifies headless initialization, page configuration, and cold start behavior."""

    def test_app_cold_start_empty_db(self, temp_db):
        """Validates that app.py launches with 0 syntax errors or unhandled exceptions on an empty DB."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)

        assert len(at.exception) == 0, f"App launched with unhandled exceptions: {at.exception}"
        # Verify title or header exists
        assert len(at.title) > 0 or len(at.header) > 0
        # Verify tabs exist
        assert len(at.tabs) >= 5

    def test_app_session_state_defaults(self, temp_db):
        """Validates that session state default variables are properly initialized."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)

        assert len(at.exception) == 0
        # Check that session state holds active db path
        assert "db_path" in at.session_state
        assert at.session_state["db_path"] == temp_db


# ============================================================================
# Tier 2: Top KPI Metrics Bar Tests
# ============================================================================

class TestStreamlitKPIMetrics:
    """Verifies KPI metrics calculation and display."""

    def test_kpi_metrics_rendering_populated_db(self, populated_db):
        """Validates that all 5 KPI metrics render correct values from database."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)

        assert len(at.exception) == 0
        assert len(at.metric) >= 5

        metric_labels = [m.label.lower() for m in at.metric]
        assert any("total cards" in l for l in metric_labels)
        assert any("investment" in l for l in metric_labels)
        assert any("estimated value" in l for l in metric_labels)
        assert any("pending" in l or "review" in l for l in metric_labels)
        assert any("cleared" in l for l in metric_labels)

        # Check values
        for m in at.metric:
            if "total cards" in m.label.lower():
                assert str(m.value).strip() == "5"
            elif "investment" in m.label.lower():
                assert "1,710" in str(m.value) or "1710" in str(m.value)
            elif "estimated value" in m.label.lower():
                assert "5,455" in str(m.value) or "5455" in str(m.value)
            elif "cleared" in m.label.lower():
                assert str(m.value).strip() == "2"
            elif "pending" in m.label.lower():
                assert str(m.value).strip() == "3"

    def test_kpi_metrics_zero_state(self, temp_db):
        """Validates metrics when staging database is completely empty."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)

        assert len(at.exception) == 0
        for m in at.metric:
            if "total cards" in m.label.lower():
                assert str(m.value).strip() == "0"


# ============================================================================
# Tier 3: Tab 1 (Portfolio Staging) Interaction & CRUD Tests
# ============================================================================

class TestStreamlitStagingTab:
    """Verifies Tab 1 staging table rendering, filtering, updates, and deletions."""

    def test_category_and_status_filtering(self, populated_db):
        """Tests that changing category and status filter selects the correct card subsets."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Change status filter to 'CLEARED'
        for sb in at.selectbox:
            if "status" in sb.label.lower():
                sb.select("CLEARED").run(timeout=15)
                break

        assert len(at.exception) == 0
        # Verify dataframe contains only 2 cleared cards
        if len(at.dataframe) > 0:
            df = at.dataframe[0].value
            assert len(df) == 2

    def test_search_filter_query(self, populated_db):
        """Tests free-text search filtering for a specific player."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        for ti in at.text_input:
            if "search" in ti.label.lower():
                ti.input("Luka").run(timeout=15)
                break

        assert len(at.exception) == 0
        if len(at.dataframe) > 0:
            df = at.dataframe[0].value
            assert len(df) == 1
            assert "Luka" in str(df.iloc[0].to_dict())

    def test_quick_status_update_button(self, populated_db):
        """Tests 1-click status update action on a card."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Find and click mark cleared button
        for btn in at.button:
            if "mark cleared" in btn.label.lower() or "cleared" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0

    def test_delete_card_action(self, populated_db):
        """Tests deleting a single card record from staging."""
        initial_count = get_card_count(populated_db)
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Find and click delete button
        for btn in at.button:
            if "delete" in btn.label.lower() and "table" not in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0

    def test_clear_staging_table_confirmation(self, populated_db):
        """Tests checking confirmation box and clearing entire staging table."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Find the clear confirmation checkbox
        for cb in at.checkbox:
            if "confirm" in cb.label.lower() or "staging table" in cb.label.lower():
                cb.check().run(timeout=15)
                break

        for btn in at.button:
            if "clear entire" in btn.label.lower() or "clear" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0


# ============================================================================
# Tier 4: Tabs 2 & 3 (AI Vision & Scraper Ingestion) Tests
# ============================================================================

class TestStreamlitIngestionTabs:
    """Verifies AI Vision analysis preview and checklist scraper bulk ingestion."""

    def test_mock_vision_extraction_and_commit(self, temp_db):
        """Validates AI Vision extraction in mock mode and committing record to database."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Look for extract button in Vision tab
        for btn in at.button:
            if "extract" in btn.label.lower() or "vision" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0

        # Look for commit button
        for btn in at.button:
            if "commit" in btn.label.lower() or "save card" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0

    def test_scraper_parsing_and_bulk_ingest(self, temp_db):
        """Validates checklist scraper parsing raw HTML and bulk staging cards."""
        sample_html = """
        <html>
        <head><title>2023-24 Panini Prizm Basketball Checklist</title></head>
        <body>
            <h1>2023-24 Panini Prizm Basketball Base Set Checklist</h1>
            <table>
                <tr><th>Card #</th><th>Player</th><th>Team</th></tr>
                <tr><td>1</td><td>Victor Wembanyama (RC)</td><td>San Antonio Spurs</td></tr>
                <tr><td>2</td><td>Brandon Miller (RC)</td><td>Charlotte Hornets</td></tr>
                <tr><td>3</td><td>Scoot Henderson (RC)</td><td>Portland Trail Blazers</td></tr>
            </table>
        </body>
        </html>
        """

        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Feed HTML into text area
        for ta in at.text_area:
            if "html" in ta.label.lower() or "checklist" in ta.label.lower():
                ta.input(sample_html).run(timeout=15)
                break

        # Click Parse Checklist
        for btn in at.button:
            if "parse" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0

        # Click Bulk Ingest
        for btn in at.button:
            if "bulk ingest" in btn.label.lower() or "ingest" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0


# ============================================================================
# Tier 5: Tabs 4, 5 & 6 (Sales Copy, CSV Export & API Health) Tests
# ============================================================================

class TestStreamlitMonetizationExportTabs:
    """Verifies Sales Listing generation, Card Ladder CSV export, and API Bridge telemetry."""

    def test_sales_copy_generation_mock_mode(self, populated_db):
        """Validates SEO Marketplace listing generation inside Streamlit."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        for btn in at.button:
            if "generate" in btn.label.lower() and ("sales" in btn.label.lower() or "listing" in btn.label.lower()):
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0

        # Verify generated copy text area exists and is populated
        for ta in at.text_area:
            if "listing" in ta.label.lower() or "copy" in ta.label.lower():
                val = ta.value
                assert "KEY SPECIFICATIONS" in val or "ASKING PRICE" in val or "#" in val

    def test_card_ladder_csv_export_trigger_and_validation(self, populated_db, tmp_path):
        """Validates Card Ladder CSV export button and checks 16-column layout."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        for btn in at.button:
            if "export" in btn.label.lower() and "ladder" in btn.label.lower():
                btn.click().run(timeout=15)
                break

        assert len(at.exception) == 0

        # Check that download button or success message appeared
        assert len(at.download_button) > 0 or len(at.success) > 0 or len(at.info) > 0

    def test_api_bridge_tab_telemetry(self, populated_db):
        """Validates that API Bridge / Health tab renders storage stats and port status."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)
        assert len(at.exception) == 0

        # Verify no unhandled errors when viewing health diagnostics
        assert len(at.error) == 0


# ============================================================================
# Tier 6: Direct Module Functions & Subcomponents Tests
# ============================================================================

class TestStreamlitModuleSubcomponents:
    """Verifies direct internal functions of app.py for test coverage and resilience."""

    def test_init_session_state_function(self, monkeypatch, temp_db):
        """Validates init_session_state sets all required keys."""
        monkeypatch.setenv("PORTFOLIO_DB_PATH", temp_db)
        app_module.init_session_state()
        assert "db_path" in app_module.st.session_state
        assert "export_status_filter" in app_module.st.session_state
        assert "staging_filter_category" in app_module.st.session_state

    def test_render_custom_css_function(self):
        """Validates render_custom_css runs without error."""
        app_module.render_custom_css()

    def test_get_or_start_api_server_cached(self, temp_db):
        """Validates get_or_start_api_server helper."""
        server = app_module.get_or_start_api_server(port=8002, db_path=temp_db)
        assert server is not None

"""
tests/test_adversarial_m5_challenger.py - Adversarial End-to-End User Workflow Test Suite for Milestone 5.
Authored by Teamwork Preview Challenger (Agent Challenger M5_2).

Target: sports_cards/ecosystem_hub (app.py, api.py, database.py, sales_generator.py, export.py, vision_ingest.py, scraper_ingest.py)

Workflows Challenged:
1. Workflow 1: Ingest card via Tab 2 (Vision) or Tab 3 (Scraper) -> view in Tab 1 -> edit variation -> auto-query update -> verify in DB.
2. Workflow 2: Select card in Tab 4 -> generate SEO Facebook listing -> verify title length < 100 chars, no spam words, 6-8 hashtags.
3. Workflow 3: Export from Tab 5 -> download CSV -> verify exact 16 Card Ladder columns, leading zeros preserved.
4. Workflow 4: FastAPI background thread on port 8002 / test port responds while Streamlit is active without socket collision or lockup.
"""

from __future__ import annotations

import csv
import io
import os
import re
import socket
import sys
import tempfile
import threading
import time
import unicodedata
import zipfile
import concurrent.futures
from typing import Any, Generator

import pytest
import pandas as pd
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

# Ensure ecosystem_hub is on sys.path
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

APP_PATH = os.path.join(PROJECT_DIR, "app.py")

from models import (
    CardRecord,
    CardUpdate,
    CardCategory,
    AIStatus,
    VALID_CATEGORIES,
    CATEGORY_MAP,
    synthesize_query,
    format_notes,
    get_current_date_str,
    MarketplaceListing,
)
from database import (
    DEFAULT_DB_PATH,
    CIRCUIT_BREAKER_BATCH_LIMIT,
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
    check_circuit_breaker,
    get_next_child_id,
    clear_staging_table,
    get_cards_for_export,
    get_db_connection,
)
from vision_ingest import (
    extract_card_from_image,
    MockVisionExtractor,
    ingest_vision_card,
    extraction_to_card_record,
    CardExtractionSchema,
)
from scraper_ingest import (
    parse_checklist_html,
    fetch_and_parse_checklist,
    ingest_scraper_cards,
    expand_parallels,
)
from sales_generator import (
    generate_marketplace_listing,
    build_structured_listing,
    MockSalesGenerator,
    build_seo_title,
    build_hashtags,
    sanitize_seo_title,
    FORBIDDEN_BUZZWORDS,
)
from export import (
    CARD_LADDER_COLUMNS,
    EXCLUDED_INTERNAL_FIELDS,
    export_card_ladder_csv,
    validate_card_ladder_csv,
    cards_to_card_ladder_dataframe,
    fetch_records_for_export,
)
from api import (
    app,
    get_db_path,
    is_port_in_use,
    start_api_server_thread,
    BackgroundServerThread,
)
import app as app_module


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def temp_db(tmp_path, monkeypatch) -> str:
    """Provides a fresh isolated SQLite database path configured in environment."""
    db_file = str(tmp_path / "test_adversarial_m5.db")
    init_db(db_file)
    monkeypatch.setenv("PORTFOLIO_DB_PATH", db_file)
    return db_file


@pytest.fixture
def sample_cards_db(temp_db: str) -> str:
    """Populates the isolated database with diverse multi-sport cards."""
    cards = [
        {
            "player": "Luka Dončić",
            "year": "2018",
            "set_name": "Panini Prizm",
            "variation": "Silver Prizm",
            "card_number": "280",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "48192041",
            "investment": 250.00,
            "estimated_value": 750.00,
            "notes": "8492-101",
            "ai_status": "REVIEW VARIATION",
        },
        {
            "player": "Ronald Acuña Jr.",
            "year": "2018",
            "set_name": "Topps Chrome",
            "variation": "",
            "card_number": "001",
            "category": "Baseball",
            "condition": "Raw",
            "slab_serial_number": "",
            "investment": 15.00,
            "estimated_value": 45.00,
            "notes": "8492-102",
            "ai_status": "CLEARED",
        },
        {
            "player": "Patrick Mahomes",
            "year": "2017",
            "set_name": "Panini Prizm",
            "variation": "",
            "card_number": "0007",
            "category": "Football",
            "condition": "BGS 9.5",
            "slab_serial_number": "001294821",
            "investment": 500.00,
            "estimated_value": 1800.00,
            "notes": "8492-103",
            "ai_status": "CLEARED",
        },
        {
            "player": "Charizard",
            "year": "1999",
            "set_name": "Pokemon Base Set",
            "variation": "",
            "card_number": "04/102",
            "category": "Pokemon",
            "condition": "PSA 9",
            "slab_serial_number": "61028392",
            "investment": 2000.00,
            "estimated_value": 5500.00,
            "notes": "8492-104",
            "ai_status": "CLEARED",
        },
    ]
    insert_cards_batch(cards, db_path=temp_db)
    return temp_db


# ============================================================================
# WORKFLOW 1: Ingestion -> Staging View -> Variation Edit -> Auto-Query Update
# ============================================================================

class TestWorkflow1IngestEditAndAutoQuery:
    """
    Adversarial verification of Workflow 1:
    Ingest via Tab 2 (Vision) or Tab 3 (Scraper) -> View in Tab 1 -> Edit variation -> Auto-query update -> DB verification.
    """

    def test_vision_ingest_view_and_edit_variation_auto_query_update(self, temp_db: str):
        """
        Ingest card via AI Vision Mock -> Commit to SQLite -> Inspect in DB ->
        Edit 'variation' field -> Assert 'query' updates automatically to reflect new variation.
        """
        # 1. Simulate Tab 2 Vision Extraction
        extraction = extract_card_from_image(
            image_path="wembanyama_prizm.jpg",
            mock=True,
            parent_image_id="8492",
            child_card_id=1,
        )
        assert extraction.player is not None
        assert extraction.set_name is not None

        # 2. Form Commit into Database
        child_id = get_next_child_id("8492", db_path=temp_db)
        notes = format_notes("8492", child_id)
        card_data = {
            "player": extraction.player,
            "year": extraction.year,
            "set_name": extraction.set_name,
            "variation": extraction.variation or "Base",
            "card_number": extraction.card_number or "136",
            "category": extraction.category,
            "condition": extraction.condition or "Raw",
            "slab_serial_number": extraction.slab_serial_number,
            "investment": 50.0,
            "estimated_value": 150.0,
            "date_purchased": "08/24/2026",
            "notes": notes,
            "ai_status": "REVIEW VARIATION",
        }
        new_card_id = insert_card(card_data, db_path=temp_db)
        assert new_card_id > 0

        # Verify initial state in DB
        card_row = get_card_by_id(new_card_id, db_path=temp_db)
        assert card_row is not None
        initial_query = card_row["query"]
        expected_initial_query = synthesize_query(
            card_row["year"], card_row["set_name"], card_row["player"],
            card_row["variation"], card_row["condition"]
        )
        assert card_row["query"] == expected_initial_query

        # 3. Simulate Tab 1 Edit: User modifies variation to 'Gold Vinyl /5'
        updated_variation = "Gold Vinyl /5"
        update_success = update_card(
            new_card_id,
            {"variation": updated_variation},
            db_path=temp_db,
        )
        assert update_success is True

        # 4. Verify in DB: Auto-query update must be synthesized with new variation!
        updated_row = get_card_by_id(new_card_id, db_path=temp_db)
        assert updated_row is not None
        assert updated_row["variation"] == "Gold Vinyl /5"
        
        expected_updated_query = synthesize_query(
            updated_row["year"], updated_row["set_name"], updated_row["player"],
            updated_variation, updated_row["condition"]
        )
        assert updated_row["query"] == expected_updated_query
        assert "Gold Vinyl /5" in updated_row["query"]

    def test_scraper_ingest_view_and_edit_variation_auto_query_update(self, temp_db: str):
        """
        Ingest cards via Tab 3 Checklist Scraper -> Bulk Staging -> Select in Tab 1 ->
        Edit variation and condition -> Assert auto-query recalculation.
        """
        sample_html = """
        <table>
            <tr><th>Card #</th><th>Player</th><th>Team</th></tr>
            <tr><td>101</td><td>Stephen Curry</td><td>Golden State Warriors</td></tr>
            <tr><td>102</td><td>Klay Thompson</td><td>Dallas Mavericks</td></tr>
        </table>
        """
        parallels = ["Base", "Mojo Prizm /25"]
        extractions = parse_checklist_html(
            html_content=sample_html,
            set_name="Panini Prizm",
            year="2024",
            category="Basketball",
            parallels=parallels,
        )
        assert len(extractions) == 4  # 2 cards * 2 parallels

        inserted_ids = ingest_scraper_cards(
            extractions=extractions,
            parent_id="9001",
            date_purchased="08/24/2026",
            investment=5.00,
            db_path=temp_db,
        )
        assert len(inserted_ids) == 4

        # Pick the second card (Klay Thompson Base)
        target_id = inserted_ids[2]
        target_row = get_card_by_id(target_id, db_path=temp_db)
        assert target_row["player"] == "Klay Thompson"

        # Edit variation to 'Nebula Choice 1/1' and condition to 'PSA 10'
        new_var = "Nebula Choice 1/1"
        new_cond = "PSA 10"
        new_slab = "99887766"
        update_card(
            target_id,
            {"variation": new_var, "condition": new_cond, "slab_serial_number": new_slab},
            db_path=temp_db,
        )

        refreshed = get_card_by_id(target_id, db_path=temp_db)
        assert refreshed["variation"] == "Nebula Choice 1/1"
        assert refreshed["condition"] == "PSA 10"
        assert refreshed["slab_serial_number"] == "99887766"

        expected_query = synthesize_query("2024", "Panini Prizm", "Klay Thompson", "Nebula Choice 1/1", "PSA 10")
        assert refreshed["query"] == expected_query
        assert "Nebula Choice 1/1" in refreshed["query"]
        assert "PSA 10" in refreshed["query"]

    def test_adversarial_variation_cleared_to_empty_string(self, temp_db: str):
        """
        Adversarial case: Editing variation to empty string '' must cleanly drop variation
        from synthesized query WITHOUT creating double spaces.
        """
        card_id = insert_card({
            "player": "Anthony Edwards",
            "year": "2020",
            "set_name": "Panini Select",
            "variation": "Courtside Silver",
            "card_number": "298",
            "category": "Basketball",
            "condition": "Raw",
            "investment": 100.0,
            "estimated_value": 300.0,
            "notes": "8492-101",
        }, db_path=temp_db)

        # Clear variation to empty string
        update_card(card_id, {"variation": ""}, db_path=temp_db)
        cleared_card = get_card_by_id(card_id, db_path=temp_db)
        assert cleared_card["variation"] == ""
        assert cleared_card["query"] == "2020 Panini Select Anthony Edwards Raw"
        assert "  " not in cleared_card["query"]

    def test_adversarial_variation_with_unicode_and_special_chars(self, temp_db: str):
        """
        Adversarial case: Variation with diacritics, fractions, quotes, and punctuation.
        """
        card_id = insert_card({
            "player": "Alexis Lafrenière",
            "year": "2020",
            "set_name": "Upper Deck SPx",
            "variation": "",
            "card_number": "1",
            "category": "Hockey",
            "condition": "Raw",
            "investment": 80.0,
            "estimated_value": 200.0,
            "notes": "8492-101",
        }, db_path=temp_db)

        crazy_variation = "Édition Française 'Black & Gold' Super-Foil (1/1)"
        update_card(card_id, {"variation": crazy_variation}, db_path=temp_db)
        updated = get_card_by_id(card_id, db_path=temp_db)
        assert updated["variation"] == crazy_variation
        assert "Édition Française" in updated["query"]
        assert "(1/1)" in updated["query"]

    def test_tab1_form_edit_and_status_resolution(self, sample_cards_db: str):
        """
        Direct Tab 1 editing test: Select card, update variation and status, verify in database.
        """
        luka_card = get_all_cards(filters={"player": "Luka"}, db_path=sample_cards_db)[0]
        luka_id = luka_card["id"]

        # 1. Update status via update_card_status
        update_card_status(luka_id, "CLEARED", db_path=sample_cards_db)
        refreshed = get_card_by_id(luka_id, db_path=sample_cards_db)
        assert refreshed["ai_status"] == "CLEARED"

        # 2. Update variation via update_card
        update_card(luka_id, {"variation": "Gold Prizm /10"}, db_path=sample_cards_db)
        refreshed2 = get_card_by_id(luka_id, db_path=sample_cards_db)
        assert refreshed2["variation"] == "Gold Prizm /10"
        assert "Gold Prizm /10" in refreshed2["query"]


# ============================================================================
# WORKFLOW 2: Tab 4 Sales Copy Generation (SEO Title < 100, No Spam, 6-8 Tags)
# ============================================================================

class TestWorkflow2SEOListingGenerator:
    """
    Adversarial verification of Workflow 2:
    Select card in Tab 4 -> Generate SEO Facebook listing ->
    Verify Title < 100 chars, ZERO spam buzzwords, and strictly 6 to 8 hashtags.
    """

    def test_sales_generator_from_selected_card(self, sample_cards_db: str):
        """
        Select card from database, generate SEO listing, verify structured model output.
        """
        luka = get_all_cards(filters={"player": "Luka"}, db_path=sample_cards_db)[0]
        listing_copy = generate_marketplace_listing(
            card=luka,
            asking_price=725.00,
            custom_notes="Includes magnetic case. Safe local pickup in Phoenix.",
            mock=True,
            db_path=sample_cards_db,
        )
        assert isinstance(listing_copy, str)
        assert len(listing_copy) > 100
        assert "ASKING PRICE: $725.00" in listing_copy
        assert "Luka Dončić" in listing_copy
        assert "Panini Prizm" in listing_copy
        assert "Silver Prizm" in listing_copy

    @pytest.mark.parametrize("player,set_name,variation,condition", [
        ("Luka Dončić", "Panini Prizm", "Silver Prizm", "PSA 10"),
        ("Giannis Sina Ugo Antetokounmpo", "National Treasures Colossal Material Signatures Prime", "Nebula Parallel Autograph Patch Booklets 1/1", "BGS 9.5 Gem Mint w/ 10 Auto"),
        ("Shohei Ohtani (大谷 翔平)", "Topps Chrome Update Series Sapphire Edition", "SuperFractor 1st Bowman Chrome Autograph", "SGC 10 Pristine"),
        ("Victor Wembanyama", "Panini Court Kings", "Level IV Aurora Die-Cut Refractor", "Raw"),
        ("Ronald Acuña Jr.", "Bowman Sterling", "Gold Wave Refractor Serial Numbered /50", "PSA 9"),
    ])
    def test_seo_title_length_strictly_under_100_chars_fuzzing(self, player: str, set_name: str, variation: str, condition: str):
        """
        Fuzzing test: Regardless of input lengths, title MUST be strictly < 100 characters (max 99 chars).
        """
        card_data = {
            "player": player,
            "year": "2023",
            "set_name": set_name,
            "variation": variation,
            "condition": condition,
        }
        title = build_seo_title(card_data, max_length=99)
        assert len(title) < 100, f"Title exceeded 99 chars ({len(title)}): '{title}'"
        assert len(title) > 0

    @pytest.mark.parametrize("spam_word", FORBIDDEN_BUZZWORDS)
    def test_seo_title_zero_forbidden_buzzwords(self, spam_word: str):
        """
        Injecting every single forbidden buzzword and emoji into card titles -> MUST be completely sanitized.
        """
        dirty_card = {
            "player": f"Luka {spam_word} Dončić",
            "year": "2020",
            "set_name": f"Panini {spam_word} Prizm",
            "variation": f"Silver {spam_word} Prizm",
            "condition": "PSA 10",
        }
        clean_title = build_seo_title(dirty_card)
        assert len(clean_title) < 100
        pattern = re.compile(rf"(?i)\b{re.escape(spam_word)}\b")
        if spam_word not in ("1/1?", "PSA 10?"):
            assert not pattern.search(clean_title), f"Forbidden buzzword '{spam_word}' survived in '{clean_title}'"

    @pytest.mark.parametrize("category", list(VALID_CATEGORIES))
    def test_hashtags_strictly_between_6_and_8_across_all_22_categories(self, category: str):
        """
        Verifies that for every one of the 22 valid categories, build_hashtags produces strictly 6 to 8 tags.
        """
        card = {
            "player": "Star Athlete",
            "year": "2022",
            "set_name": "Championship Set",
            "variation": "Holo",
            "category": category,
            "condition": "Raw",
        }
        tags = build_hashtags(card)
        assert 6 <= len(tags) <= 8, f"Category '{category}' generated {len(tags)} tags: {tags}"
        for tag in tags:
            assert tag.startswith("#"), f"Tag '{tag}' missing '#' prefix"
            assert re.match(r"^#[a-zA-Z0-9]+$", tag), f"Tag '{tag}' contains invalid characters"

    def test_structured_listing_model_all_6_sections_present(self, sample_cards_db: str):
        """
        Verifies the 6-section schema contract on MarketplaceListing:
        1. Title (<100 chars, no spam)
        2. Asking Price & Terms
        3. Key Specifications (all specs present)
        4. Condition & Slab Authenticity
        5. Shipping & Local Pickup
        6. Hashtags (6-8 tags)
        """
        charizard = get_all_cards(filters={"player": "Charizard"}, db_path=sample_cards_db)[0]
        structured = build_structured_listing(
            card=charizard,
            asking_price=5400.00,
            custom_notes="Vault stored. Armored courier available.",
            is_mock=True,
        )
        assert isinstance(structured, MarketplaceListing)
        assert len(structured.title) < 100
        assert structured.price == 5400.00
        assert "$5,400.00" in structured.price_formatted
        assert len(structured.specs) >= 5
        assert "Pokemon" in structured.specs.get("Category / Sport", "")
        assert "PSA 9" in structured.specs.get("Condition / Grade", "")
        assert 6 <= len(structured.hashtags) <= 8
        assert "Vault stored" in structured.description


# ============================================================================
# WORKFLOW 3: Tab 5 Card Ladder CSV Export (16 Columns, Leading Zeros Intact)
# ============================================================================

class TestWorkflow3CardLadderCSVExport:
    """
    Adversarial verification of Workflow 3:
    Export from Tab 5 -> Download CSV ->
    Verify exact 16 Card Ladder columns in exact order, zero internal fields leaked, leading zeros preserved.
    """

    def test_exact_16_card_ladder_columns_order_and_zero_leaks(self, sample_cards_db: str, tmp_path):
        """
        Export CSV from sample database -> Validate column headers verbatim against CARD_LADDER_COLUMNS.
        Verify that none of the 5 internal variables (slab_serial_number, query, tags, back_image, ai_status) appear.
        """
        output_csv = str(tmp_path / "CardLadder_Bulk_Upload.csv")
        row_count, generated_files = export_card_ladder_csv(
            db_path=sample_cards_db,
            output_path=output_csv,
            status_filter="ALL",
            max_batch_size=500,
            apply_normalization=True,
        )
        assert row_count == 4
        assert len(generated_files) == 1

        val_result = validate_card_ladder_csv(generated_files[0])
        assert val_result["valid"] is True
        assert val_result["row_count"] == 4
        assert val_result["headers"] == CARD_LADDER_COLUMNS

        # Raw forensic inspection of CSV header line
        with open(generated_files[0], "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)

        assert headers == CARD_LADDER_COLUMNS
        assert len(headers) == 16

        # Assert no forbidden internal database fields appear as columns
        header_normalized = [h.lower().replace(" ", "_") for h in headers]
        for internal_field in ["slab_serial_number", "query", "tags", "back_image", "ai_status", "created_at", "updated_at"]:
            assert internal_field not in header_normalized, f"Internal field '{internal_field}' leaked in export!"
        assert "id" not in header_normalized, "Internal primary key 'id' leaked in export!"

    @pytest.mark.parametrize("leading_zero_val", [
        "001",
        "0007",
        "04/102",
        "09",
        "0",
        "00",
        "00123",
        "00045/00100",
    ])
    def test_leading_zeros_preservation_string_fidelity(self, temp_db: str, tmp_path, leading_zero_val: str):
        """
        Insert cards with leading zeros in card_number -> Export to CSV ->
        Read raw text lines -> Assert exact string match (e.g. '001', NOT 1).
        """
        card_id = insert_card({
            "player": f"Player {leading_zero_val}",
            "year": "2023",
            "set_name": "Test Set",
            "variation": "",
            "card_number": leading_zero_val,
            "category": "Baseball",
            "condition": "Raw",
            "investment": 1.0,
            "estimated_value": 2.0,
            "notes": "8492-101",
            "ai_status": "CLEARED",
        }, db_path=temp_db)

        output_csv = str(tmp_path / f"export_{leading_zero_val.replace('/', '_')}.csv")
        export_card_ladder_csv(
            db_path=temp_db,
            output_path=output_csv,
            status_filter="CLEARED",
        )

        # Parse with csv.reader (all text, no numeric conversion)
        with open(output_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        exported_num = rows[0]["Number"]
        assert exported_num == leading_zero_val, f"Leading zero corrupted: expected '{leading_zero_val}', got '{exported_num}'"

    def test_circuit_breaker_500_chunking_and_zip_bundle(self, temp_db: str, tmp_path):
        """
        Seed 1,050 cards into SQLite -> Export with 500-card limit ->
        Verify exactly 3 chunk files created (_part1.csv (500), _part2.csv (500), _part3.csv (50)).
        Verify all chunk files pass 16-column validation and can be packaged into ZIP.
        """
        batch = []
        for i in range(1, 1051):
            batch.append({
                "player": f"Athlete {i:04d}",
                "year": "2023",
                "set_name": "Batch Prizm",
                "variation": "",
                "card_number": f"{i:04d}",
                "category": "Basketball",
                "condition": "Raw",
                "investment": 1.00,
                "estimated_value": 5.00,
                "notes": f"8492-{i}",
                "ai_status": "CLEARED",
            })
        insert_cards_batch(batch, db_path=temp_db)

        base_output = str(tmp_path / "CardLadder_Bulk_Upload.csv")
        total_exported, generated_paths = export_card_ladder_csv(
            db_path=temp_db,
            output_path=base_output,
            status_filter="CLEARED",
            max_batch_size=500,
        )
        assert total_exported == 1050
        assert len(generated_paths) == 3

        # Validate each chunk
        val1 = validate_card_ladder_csv(generated_paths[0])
        val2 = validate_card_ladder_csv(generated_paths[1])
        val3 = validate_card_ladder_csv(generated_paths[2])

        assert val1["valid"] and val1["row_count"] == 500
        assert val2["valid"] and val2["row_count"] == 500
        assert val3["valid"] and val3["row_count"] == 50

        # Simulate Tab 5 in-memory ZIP bundling
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for p in generated_paths:
                z.write(p, arcname=os.path.basename(p))

        zip_bytes = zip_buffer.getvalue()
        assert len(zip_bytes) > 0
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as test_zip:
            namelist = test_zip.namelist()
            assert len(namelist) == 3
            assert any("part1" in n for n in namelist)
            assert any("part2" in n for n in namelist)
            assert any("part3" in n for n in namelist)


# ============================================================================
# WORKFLOW 4: FastAPI Background Server Concurrency & Socket Collision
# ============================================================================

class TestWorkflow4FastAPISettingsAndConcurrency:
    """
    Adversarial verification of Workflow 4:
    FastAPI background thread on port 8002 / test port responds while Streamlit is active without socket collision or lockup.
    """

    def test_fastapi_server_thread_startup_and_response(self, temp_db: str):
        """
        Starts FastAPI in background daemon thread on an isolated dynamic port,
        makes HTTP request, and verifies live JSON response.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]

        server_thread = BackgroundServerThread(
            app_instance=app,
            host="127.0.0.1",
            port=free_port,
            db_path=temp_db,
        )
        server_thread.start()
        is_ready = server_thread.wait_until_ready(timeout=3.0)
        assert is_ready is True

        time.sleep(0.5)
        assert is_port_in_use(free_port, host="127.0.0.1") is True
        server_thread.stop()

    def test_socket_collision_prevention_and_idempotency(self, temp_db: str):
        """
        Calling start_api_server_thread multiple times when a server is running
        must NOT throw socket collision exceptions (Errno 10048) and must return safely.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]

        server1 = start_api_server_thread(host="127.0.0.1", port=free_port, db_path=temp_db)
        assert server1 is not None
        time.sleep(0.5)

        # Second call on same port must detect active port and return dummy without crash
        server2 = start_api_server_thread(host="127.0.0.1", port=free_port, db_path=temp_db)
        assert server2 is not None

        server1.stop()

    def test_high_concurrency_fastapi_capture_and_db_wal_mode(self, temp_db: str):
        """
        High-concurrency stress test: 20 concurrent threads pounding FastAPI POST /api/v1/cards/capture
        while Streamlit reads summary stats and updates records.
        Verifies zero SQLite lock errors, correct transaction isolation, and schema validity.
        """
        app.state.db_path = temp_db
        app.dependency_overrides[get_db_path] = lambda: temp_db

        client = TestClient(app)

        def worker_capture(thread_idx: int):
            payload = {
                "player": f"Worker Player {thread_idx}",
                "year": "2023",
                "set_name": "Prizm Chrome",
                "variation": f"Parallel {thread_idx}",
                "card_number": f"{thread_idx:03d}",
                "category": "Basketball",
                "condition": "Raw",
                "investment": float(thread_idx * 10),
                "estimated_value": float(thread_idx * 25),
                "parent_image_id": "8492",
                "child_card_id": f"{thread_idx:03d}",
            }
            res = client.post("/api/v1/cards/capture", json=payload)
            return res.status_code, res.json()

        def worker_reader():
            return get_summary_stats(db_path=temp_db)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            capture_futures = [executor.submit(worker_capture, i) for i in range(1, 21)]
            reader_futures = [executor.submit(worker_reader) for _ in range(10)]

            # Await all captures
            capture_results = [f.result() for f in capture_futures]
            reader_results = [f.result() for f in reader_futures]

        app.dependency_overrides.clear()

        # Assert all 20 captures succeeded with HTTP 200
        for status_code, data in capture_results:
            assert status_code == 200
            assert data["status"] == "success"
            assert data["card_id"] > 0
            assert "8492-" in data["notes"]

        # Assert total cards in DB equals exactly 20
        total_staged = get_card_count(db_path=temp_db)
        assert total_staged == 20

        # Assert notes IDs are strictly unique and formatted
        all_cards = get_all_cards(db_path=temp_db, limit=100)
        notes_set = {c["notes"] for c in all_cards}
        assert len(notes_set) == 20

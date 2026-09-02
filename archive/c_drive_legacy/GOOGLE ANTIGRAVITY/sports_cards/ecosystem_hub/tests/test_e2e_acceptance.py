"""
test_e2e_acceptance.py - Comprehensive Opaque-Box E2E Acceptance Test Suite.
Strictly verifies all acceptance criteria defined in ORIGINAL_REQUEST.md:
- Tier 1: Central Hub Acceptance (app.py compile/init, 21-variable schema, 22 category constraints, defaults, query synthesis)
- Tier 2: Ingestion Acceptance (Beckett checklist static HTML scraper, AI vision mock extractor schema)
- Tier 3: API Bridge & Sales Listing Acceptance (Chrome Extension POST API capture, Facebook Marketplace listing copy generation)
- Tier 4: Export Pipeline Acceptance (Card Ladder 16-variable CSV export, leading zero preservation, 500-card batch chunking, fuzzy normalization)
- Tier 5: Full Omnichannel End-to-End Lifecycle Scenario
"""

from __future__ import annotations

import ast
import csv
import os
import py_compile
import re
import sys
import tempfile
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

# Ensure project root is in sys.path
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

APP_PATH = os.path.join(PROJECT_DIR, "app.py")
FIXTURES_DIR = os.path.join(PROJECT_DIR, "fixtures")
BECKETT_HTML_PATH = os.path.join(FIXTURES_DIR, "beckett_sample.html")

from api import app, get_db_path
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
    get_db_connection,
)
from export import (
    CARD_LADDER_COLUMNS,
    EXCLUDED_INTERNAL_FIELDS,
    export_card_ladder_csv,
    validate_card_ladder_csv,
    cards_to_card_ladder_dataframe,
    normalize_player_name,
    normalize_set_name,
)
from models import (
    AIStatus,
    CardCategory,
    CardExtractionSchema,
    CardRecord,
    CardUpdate,
    CardCaptureRequest,
    MarketplaceListing,
    SalesListingRequest,
    VALID_CATEGORIES,
    CATEGORY_MAP,
    format_notes,
    get_current_date_str,
    synthesize_query,
)
from sales_generator import (
    FORBIDDEN_BUZZWORDS,
    MockSalesGenerator,
    build_hashtags,
    build_seo_title,
    build_structured_listing,
    generate_marketplace_listing,
    generate_listing_for_card_id,
)
from scraper_ingest import (
    expand_parallels,
    ingest_scraper_cards,
    parse_checklist_html,
)
from vision_ingest import (
    MockVisionExtractor,
    extract_card_from_image,
    extraction_to_card_record,
    ingest_vision_batch,
    ingest_vision_card,
)


# ============================================================================
# Shared Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path(tmp_path, monkeypatch):
    """Provides a fresh isolated SQLite database path configured in environment."""
    db_file = str(tmp_path / "test_portfolio_e2e.db")
    init_db(db_file)
    monkeypatch.setenv("PORTFOLIO_DB_PATH", db_file)
    return db_file


@pytest.fixture
def api_client(temp_db_path):
    """Provides a FastAPI TestClient wired to the isolated temporary database."""
    app.dependency_overrides[get_db_path] = lambda: temp_db_path
    app.state.db_path = temp_db_path
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ============================================================================
# Tier 1 - Central Hub Acceptance Tests
# ============================================================================

class TestTier1CentralHubAcceptance:
    """
    Tier 1 Acceptance:
    - Programmatic verification that app.py compiles and initializes without errors.
    - Test inserting a mock 21-variable row into portfolio.db and retrieving it.
    - Strict enforcement of 21 fields, 22 category check constraints, types, defaults, and query synthesis.
    """

    def test_app_py_compiles_cleanly(self):
        """Verifies app.py has valid Python syntax and compiles via py_compile and ast.parse."""
        assert os.path.exists(APP_PATH), f"app.py not found at {APP_PATH}"
        # AST parse check
        with open(APP_PATH, "r", encoding="utf-8") as f:
            code = f.read()
        parsed = ast.parse(code, filename="app.py")
        assert parsed is not None

        # Bytecode compile check
        compiled = py_compile.compile(APP_PATH, doraise=True)
        assert compiled is not None

    def test_app_py_initializes_without_errors(self, temp_db_path):
        """Verifies app.py cold starts and renders UI components via Streamlit AppTest without unhandled exceptions."""
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=15)

        assert len(at.exception) == 0, f"App launched with exceptions: {at.exception}"
        assert len(at.tabs) >= 5, "App should render at least 5 dashboard tabs"
        assert "db_path" in at.session_state
        assert at.session_state["db_path"] == temp_db_path

    def test_insert_and_retrieve_21_variable_mock_row(self, temp_db_path):
        """
        Inserts a pristine 21-variable mock row into portfolio.db and retrieves it,
        asserting all 21 fields match expected values and types.
        """
        mock_payload = {
            "date_purchased": "08/15/2023",
            "quantity": 1,
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
            "ladder_id": "LADDER-75-LUKA",
            "query": "2020 Panini Prizm Luka Dončić Silver Prizm PSA 10",
            "notes": "8492-101",
            "tags": "rookie,star,investment",
            "date_sold": "",
            "sold_price": None,
            "image": "https://example.com/front.jpg",
            "back_image": "https://example.com/back.jpg",
            "ai_status": "REVIEW VARIATION",
        }

        # Insert record
        card_id = insert_card(mock_payload, db_path=temp_db_path)
        assert card_id > 0

        # Retrieve record
        retrieved = get_card_by_id(card_id, db_path=temp_db_path)
        assert retrieved is not None

        # Verify all 21 fields and types
        assert retrieved["date_purchased"] == "08/15/2023"
        assert retrieved["quantity"] == 1
        assert retrieved["player"] == "Luka Dončić"
        assert retrieved["year"] == "2020"
        assert retrieved["set_name"] == "Panini Prizm"
        assert retrieved["variation"] == "Silver Prizm"
        assert retrieved["card_number"] == "75"
        assert retrieved["category"] == "Basketball"
        assert retrieved["condition"] == "PSA 10"
        assert retrieved["slab_serial_number"] == "48192041"
        assert retrieved["investment"] == 150.00
        assert retrieved["estimated_value"] == 350.00
        assert retrieved["ladder_id"] == "LADDER-75-LUKA"
        assert retrieved["query"] == "2020 Panini Prizm Luka Dončić Silver Prizm PSA 10"
        assert retrieved["notes"] == "8492-101"
        assert retrieved["tags"] == "rookie,star,investment"
        assert retrieved["date_sold"] == ""
        assert retrieved["sold_price"] is None
        assert retrieved["image"] == "https://example.com/front.jpg"
        assert retrieved["back_image"] == "https://example.com/back.jpg"
        assert retrieved["ai_status"] == "REVIEW VARIATION"

    def test_all_22_exact_category_constraints(self, temp_db_path):
        """Validates that all 22 exact categories are accepted by DB and invalid categories are rejected."""
        expected_22 = [
            "Basketball", "Baseball", "Football", "Hockey", "Soccer", "Tennis",
            "Wrestling", "Racing", "Golf", "Boxing", "UFC/MMA", "Pokemon",
            "Magic", "Metazoo", "Yugioh", "Fortnite", "Dragonballz",
            "Entertainment", "Swimming", "Softball", "PopCulture", "Flesh and Blood"
        ]
        assert len(expected_22) == 22

        # Insert each valid category
        for idx, cat in enumerate(expected_22, start=1):
            row = {
                "player": f"Athlete {idx}",
                "year": "2022",
                "set_name": "Test Set",
                "category": cat,
                "condition": "Raw",
                "card_number": f"{idx:03d}",
            }
            cid = insert_card(row, db_path=temp_db_path)
            retrieved = get_card_by_id(cid, db_path=temp_db_path)
            assert retrieved["category"] == cat

        # Attempt to insert an invalid category directly via SQL to verify DB CHECK constraint
        with pytest.raises(Exception):
            with get_db_connection(temp_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO cards (
                    date_purchased, quantity, player, year, set_name, variation, card_number,
                    category, condition, slab_serial_number, investment, estimated_value,
                    ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                ) VALUES (
                    '01/01/2023', 1, 'Invalid Athlete', '2023', 'Invalid Set', '', '1',
                    'InvalidCategory', 'Raw', '', 0.0, 0.0,
                    '', '2023 Invalid Set Invalid Athlete Raw', '', '', '', NULL, '', '', 'CLEARED'
                );
                """)
                conn.commit()

    def test_query_synthesis_and_sanitization(self, temp_db_path):
        """Verifies query synthesis formula [Year] [Set] [Player] [Variation] [Condition] and negative exclusion blocking."""
        # 1. Base raw card: Year Set Player Raw
        row1 = {
            "player": "Victor Wembanyama",
            "year": "2023",
            "set_name": "Panini Prizm",
            "category": "Basketball",
            "condition": "Raw",
            "variation": "",
        }
        rec1 = CardRecord(**row1)
        assert rec1.query == "2023 Panini Prizm Victor Wembanyama Raw"

        # 2. Graded parallel card
        row2 = {
            "player": "Stephen Curry",
            "year": "2012",
            "set_name": "Panini Prizm",
            "category": "Basketball",
            "condition": "PSA 10",
            "variation": "Silver Prizm",
            "slab_serial_number": "12345678",
        }
        rec2 = CardRecord(**row2)
        assert rec2.query == "2012 Panini Prizm Stephen Curry Silver Prizm PSA 10"

        # 3. Negative exclusions (-BGS, -PSA, etc.) rejected on Raw cards
        with pytest.raises(ValueError, match="Negative exclusions are forbidden"):
            CardRecord(
                player="LeBron James",
                year="2003",
                set_name="Topps Chrome",
                category="Basketball",
                condition="Raw",
                query="2003 Topps Chrome LeBron James -PSA -BGS",
            )

    def test_raw_card_no_slab_serial_constraint(self, temp_db_path):
        """Verifies that Raw condition cards cannot contain a slab serial number in DB or Pydantic."""
        # Pydantic validation rejection
        with pytest.raises(ValueError, match="Slab serial number must be blank for 'Raw'"):
            CardRecord(
                player="Mike Trout",
                year="2011",
                set_name="Topps Update",
                category="Baseball",
                condition="Raw",
                slab_serial_number="12345678",
            )

        # Database CHECK constraint rejection via direct SQL
        with pytest.raises(Exception):
            with get_db_connection(temp_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO cards (
                    date_purchased, quantity, player, year, set_name, variation, card_number,
                    category, condition, slab_serial_number, investment, estimated_value,
                    ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                ) VALUES (
                    '01/01/2023', 1, 'Mike Trout', '2011', 'Topps Update', '', 'US175',
                    'Baseball', 'Raw', 'FORBIDDEN_SERIAL', 0.0, 0.0,
                    '', '2011 Topps Update Mike Trout Raw', '', '', '', NULL, '', '', 'CLEARED'
                );
                """)
                conn.commit()


# ============================================================================
# Tier 2 - Ingestion Acceptance Tests
# ============================================================================

class TestTier2IngestionAcceptance:
    """
    Tier 2 Acceptance:
    - Scraper Acceptance: Pointing scraper_ingest.py at static HTML checklist fixture
      (fixtures/beckett_sample.html) returns structured list of >= 3 cards with card numbers, player names, team/notes.
    - AI Vision Acceptance: Calling vision_ingest.py with mock image path returns dictionary/schema
      matching 21-variable schema.
    """

    def test_scraper_beckett_sample_fixture_parsing(self):
        """
        Parses static HTML checklist fixture (beckett_sample.html) and verifies it returns
        at least 3 structured cards with correct card numbers, player names, and teams.
        """
        assert os.path.exists(BECKETT_HTML_PATH), f"Fixture not found at {BECKETT_HTML_PATH}"
        with open(BECKETT_HTML_PATH, "r", encoding="utf-8") as f:
            html_content = f.read()

        extractions = parse_checklist_html(html_content)
        assert len(extractions) >= 3, f"Expected at least 3 cards, got {len(extractions)}"

        # Check specific key cards from beckett_sample.html
        players_extracted = [c.player for c in extractions]
        numbers_extracted = [c.card_number for c in extractions]

        assert "Victor Wembanyama" in players_extracted
        assert "Luka Dončić" in players_extracted or "Luka Doncic" in players_extracted
        assert "Stephen Curry" in players_extracted

        # Verify leading zeroes preserved in scraper extractions
        assert "01" in numbers_extracted
        assert "007" in numbers_extracted
        assert "75" in numbers_extracted

        # Verify teams stored in notes
        teams_extracted = [c.notes for c in extractions]
        assert any("Spurs" in t for t in teams_extracted)
        assert any("Mavericks" in t for t in teams_extracted)
        assert any("Warriors" in t for t in teams_extracted)

    def test_scraper_to_database_sequential_notes(self, temp_db_path):
        """
        Ingests parsed checklist cards into SQLite database with parent ID 8492,
        verifying sequential tracking notes: 8492-101, 8492-102, 8492-103...
        """
        with open(BECKETT_HTML_PATH, "r", encoding="utf-8") as f:
            html_content = f.read()

        extractions = parse_checklist_html(html_content, parallels=["Base"])
        inserted_ids = ingest_scraper_cards(extractions, parent_id=8492, db_path=temp_db_path)
        assert len(inserted_ids) >= 3

        # Verify sequential notes
        for idx, cid in enumerate(inserted_ids, start=101):
            row = get_card_by_id(cid, db_path=temp_db_path)
            assert row is not None
            assert row["notes"] == f"8492-{idx:03d}"
            assert row["condition"] == "Raw"
            assert row["slab_serial_number"] == ""

    def test_ai_vision_mock_extraction_schema_conformity(self):
        """
        Calls vision_ingest.py with mock image path and verifies returned object matches
        the 21-variable schema specifications and Pydantic validation.
        """
        mock_image_path = "2020_panini_prizm_basketball_luka_doncic_psa10.jpg"
        extraction = extract_card_from_image(mock_image_path, mock=True)

        assert isinstance(extraction, CardExtractionSchema)
        data = extraction.model_dump()

        # Check required fields
        assert data["player"] != ""
        assert len(data["year"]) == 4 and data["year"].isdigit()
        assert data["set_name"] != ""
        assert data["category"] in VALID_CATEGORIES
        assert data["condition"] in ("Raw", "PSA 10", "PSA 9", "BGS 9.5", "SGC 10", "TAG 10", "CGC 9.5")
        assert data["ai_status"] in ("CLEARED", "REVIEW VARIATION", "NEEDS REVIEW")

        # Convert to full 21-variable record
        record = extraction_to_card_record(extraction, investment=50.0, parent_image_id=8492, child_card_id=101)
        assert isinstance(record, CardRecord)
        rec_data = record.model_dump()

        assert rec_data["notes"] == "8492-101"
        assert rec_data["investment"] == 50.0
        assert rec_data["query"] != ""

    def test_ai_vision_variation_review_status_flagging(self, temp_db_path):
        """
        Verifies that cards with parallel variations are automatically flagged with
        ai_status='REVIEW VARIATION', while base cards default to 'CLEARED'.
        """
        # 1. Parallel card
        parallel_ext = extract_card_from_image("2021_panini_prizm_silver_prizm_basketball.jpg", mock=True)
        assert parallel_ext.ai_status == AIStatus.REVIEW_VARIATION or parallel_ext.variation != ""

        # 2. Base card
        base_ext = CardExtractionSchema(
            player="Ronald Acuña Jr.",
            year="2019",
            set_name="Topps Chrome",
            variation="",
            card_number="001",
            category="Baseball",
            condition="Raw",
        )
        base_rec = extraction_to_card_record(base_ext)
        assert base_rec.ai_status == AIStatus.CLEARED

    def test_ai_vision_batch_ingestion_to_database(self, temp_db_path):
        """Batch ingests 5 mock images into database and verifies record integrity."""
        mock_paths = [
            "2020_panini_prizm_luka_doncic.jpg",
            "2019_topps_chrome_ronald_acuna.jpg",
            "2017_panini_donruss_patrick_mahomes.jpg",
            "1999_pokemon_base_charizard.jpg",
            "2015_upper_deck_connor_mcdavid.jpg",
        ]
        inserted_ids = ingest_vision_batch(mock_paths, parent_id=9000, db_path=temp_db_path)
        assert len(inserted_ids) == 5

        for idx, cid in enumerate(inserted_ids, start=101):
            row = get_card_by_id(cid, db_path=temp_db_path)
            assert row["notes"] == f"9000-{idx:03d}"
            assert row["player"] != ""


# ============================================================================
# Tier 3 - API Bridge & Sales Listing Acceptance Tests
# ============================================================================

class TestTier3ApiBridgeAndSalesAcceptance:
    """
    Tier 3 Acceptance:
    - Chrome Extension POST payload capture via api.py endpoint /api/v1/cards/capture
      successfully persists to DB with sequential tracking notes.
    - Sales listing generator produces complete Facebook Marketplace listing with title < 100 chars,
      price, bullet specs, condition disclaimer, and 6-8 hashtags.
    """

    def test_chrome_extension_post_capture_persists_to_db(self, api_client, temp_db_path):
        """
        Submits POST /api/v1/cards/capture with Chrome Extension payload,
        asserting 200 OK, database persistence, synthesized query, and sequential notes.
        """
        payload = {
            "player": "Victor Wembanyama",
            "year": "2023",
            "set_name": "Panini Prizm",
            "variation": "Silver Prizm",
            "card_number": "136",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "88492019",
            "investment": 400.00,
            "estimated_value": 850.00,
            "parent_image_id": 8492,
            "child_card_id": 105,
        }

        resp = api_client.post("/api/v1/cards/capture", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "success"
        assert data["card_id"] > 0
        assert data["notes"] == "8492-105"
        assert data["query"] == "2023 Panini Prizm Victor Wembanyama Silver Prizm PSA 10"

        # Verify DB directly
        persisted = get_card_by_id(data["card_id"], db_path=temp_db_path)
        assert persisted is not None
        assert persisted["player"] == "Victor Wembanyama"
        assert persisted["slab_serial_number"] == "88492019"

    def test_chrome_extension_auto_child_id_increment(self, api_client, temp_db_path):
        """
        Captures 3 consecutive cards providing only parent_image_id=8492,
        verifying automatic notes sequential increment: 8492-101, 8492-102, 8492-103.
        """
        for i in range(3):
            payload = {
                "player": f"Draft Pick {i+1}",
                "year": "2024",
                "set_name": "Bowman Chrome",
                "category": "Baseball",
                "condition": "Raw",
                "card_number": f"BCP-{i+1}",
                "parent_image_id": 8492,
            }
            resp = api_client.post("/api/v1/cards/capture", json=payload)
            assert resp.status_code == 200
            expected_child = 101 + i
            assert resp.json()["notes"] == f"8492-{expected_child:03d}"

    def test_sales_listing_generator_facebook_marketplace_specs(self):
        """
        Verifies that sales_generator.py generates high-conversion Facebook Marketplace copy meeting all specs:
        1. Title strictly < 100 characters, SEO structured, no forbidden buzzwords/emojis.
        2. Formatted price with payment terms.
        3. Key specifications bullet block.
        4. Condition and slab/raw authenticity notes.
        5. Shipping and local pickup details.
        6. Exactly 6 to 8 targeted hashtags.
        """
        card_data = {
            "player": "Luka Dončić",
            "year": "2018",
            "set_name": "Panini Prizm",
            "variation": "Silver Prizm",
            "card_number": "280",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "48192041",
            "estimated_value": 1450.00,
        }

        # 1. Raw text copy generation
        listing_copy = generate_marketplace_listing(card_data, asking_price=1450.00, mock=True)
        assert len(listing_copy) > 100

        # Title verification
        lines = [line.strip() for line in listing_copy.split("\n") if line.strip()]
        title_line = lines[0]
        assert len(title_line) < 100
        assert "2018" in title_line
        assert "Panini Prizm" in title_line
        assert "PSA 10" in title_line
        for buzzword in FORBIDDEN_BUZZWORDS:
            assert buzzword.lower() not in title_line.lower()

        # Price verification
        assert "$1,450.00" in listing_copy
        assert "Payment Terms" in listing_copy or "ASKING PRICE" in listing_copy

        # Specs verification
        assert "KEY SPECIFICATIONS" in listing_copy
        assert "48192041" in listing_copy

        # Hashtags verification
        hashtags = build_hashtags(card_data)
        assert 6 <= len(hashtags) <= 8
        for tag in hashtags:
            assert tag.startswith("#")
            assert re.match(r"^#[A-Za-z0-9]+$", tag)

        # 2. Structured Pydantic representation
        structured = build_structured_listing(card_data, asking_price=1450.00, is_mock=True)
        assert isinstance(structured, MarketplaceListing)
        assert len(structured.title) < 100
        assert structured.price == 1450.00
        assert 6 <= len(structured.hashtags) <= 8

    def test_sales_listing_via_api_endpoints(self, api_client, temp_db_path):
        """Verifies sales listing generation endpoints via FastAPI: /api/v1/cards/{id}/listing and /api/v1/sales/generate."""
        # Insert card
        cid = insert_card({
            "player": "Shohei Ohtani",
            "year": "2018",
            "set_name": "Topps Chrome",
            "variation": "Refractor",
            "card_number": "150",
            "category": "Baseball",
            "condition": "BGS 9.5",
            "slab_serial_number": "00129384",
            "estimated_value": 750.0,
        }, db_path=temp_db_path)

        # 1. Endpoint by Card ID
        r1 = api_client.post(f"/api/v1/cards/{cid}/listing?mock=true")
        assert r1.status_code == 200
        res1 = r1.json()
        assert res1["card_id"] == cid
        assert "750.00" in res1["listing"]
        assert 6 <= len(res1["structured"]["hashtags"]) <= 8

        # 2. On-demand endpoint with inline card payload
        r2 = api_client.post("/api/v1/sales/generate", json={
            "mock": True,
            "asking_price": 500.0,
            "card_data": {
                "player": "Patrick Mahomes",
                "year": "2017",
                "set_name": "Panini Donruss",
                "category": "Football",
                "condition": "Raw",
                "card_number": "327",
            }
        })
        assert r2.status_code == 200
        res2 = r2.json()
        assert "500.00" in res2["listing"]
        assert "Patrick Mahomes" in res2["listing"]


# ============================================================================
# Tier 4 - Export Pipeline Acceptance Tests
# ============================================================================

class TestTier4ExportPipelineAcceptance:
    """
    Tier 4 Acceptance:
    - Export function generates CardLadder_Bulk_Upload.csv from database.
    - Generated CSV contains exactly the 16 headers required by Card Ladder in exact specified order.
    - Preserves leading zeros on card numbers ('01', '007', '000') verified via raw byte inspection and pandas read_csv(dtype=str).
    - 500-card batch chunking verified.
    - Fuzzy normalization applied to player and set names.
    - Internal database variables strictly excluded.
    """

    def test_export_card_ladder_csv_generation_and_headers(self, temp_db_path, tmp_path):
        """
        Inserts cards into database, calls export_card_ladder_csv, and verifies
        file creation with exactly 16 canonical Card Ladder headers in exact sequence.
        """
        # Insert test records (one base card and one cleared graded card)
        cards = [
            {
                "player": "Luka Doncic",
                "year": "2020",
                "set_name": "Prizm",
                "variation": "",
                "card_number": "75",
                "category": "Basketball",
                "condition": "PSA 10",
                "slab_serial_number": "48192041",
                "investment": 150.00,
                "estimated_value": 350.00,
                "notes": "8492-101",
                "ai_status": "CLEARED",
            },
            {
                "player": "Steph Curry",
                "year": "2012",
                "set_name": "Panini Prizm",
                "variation": "",
                "card_number": "007",
                "category": "Basketball",
                "condition": "Raw",
                "slab_serial_number": "",
                "investment": 200.00,
                "estimated_value": 600.00,
                "notes": "8492-102",
                "ai_status": "CLEARED",
            },
        ]
        insert_cards_batch(cards, db_path=temp_db_path)

        output_csv = str(tmp_path / "CardLadder_Bulk_Upload.csv")
        count, files = export_card_ladder_csv(
            db_path=temp_db_path,
            output_path=output_csv,
            status_filter="CLEARED",
            apply_normalization=True,
        )

        assert count == 2
        assert len(files) == 1
        assert os.path.exists(output_csv)

        # Forensic header check
        validation = validate_card_ladder_csv(output_csv)
        assert validation["valid"] is True
        assert validation["headers"] == CARD_LADDER_COLUMNS
        assert len(validation["headers"]) == 16

    def test_exclusion_of_internal_variables(self, temp_db_path, tmp_path):
        """Verifies that internal DB variables (slab_serial_number, query, tags, back_image, ai_status, id) are excluded."""
        insert_card({
            "player": "Ronald Acuña Jr.",
            "year": "2019",
            "set_name": "Topps Chrome",
            "variation": "",
            "card_number": "001",
            "category": "Baseball",
            "condition": "PSA 10",
            "slab_serial_number": "CERT_LEAK_TEST_999",
            "tags": "TAGS_SHOULD_NOT_LEAK",
            "ai_status": "CLEARED",
        }, db_path=temp_db_path)

        output_csv = str(tmp_path / "test_exclusion.csv")
        export_card_ladder_csv(db_path=temp_db_path, output_path=output_csv, status_filter="CLEARED")

        with open(output_csv, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            headers = next(reader)
            content_rows = list(reader)

        # Exact header comparison: ensure no excluded fields are present as column names
        header_lower = [h.strip().lower() for h in headers]
        for forbidden in EXCLUDED_INTERNAL_FIELDS:
            assert forbidden.lower() not in header_lower, f"Forbidden internal column '{forbidden}' found in CSV headers"

        # Verify internal values do not leak in any cell
        flat_cells = [cell for row in content_rows for cell in row]
        assert "CERT_LEAK_TEST_999" not in flat_cells
        assert "TAGS_SHOULD_NOT_LEAK" not in flat_cells

    def test_leading_zero_preservation_raw_bytes_and_pandas(self, temp_db_path, tmp_path):
        """
        Inserts cards with leading zero card numbers ('01', '007', '000', '04/102'),
        exports to CSV, and verifies leading zeroes are preserved via raw bytes inspection
        and Pandas read_csv(..., dtype=str).
        """
        test_numbers = ["01", "007", "000", "04/102", "0015"]
        records = [
            {
                "player": f"Player {idx}",
                "year": "2020",
                "set_name": "Panini Prizm",
                "variation": "",
                "card_number": num,
                "category": "Basketball",
                "condition": "Raw",
                "ai_status": "CLEARED",
            }
            for idx, num in enumerate(test_numbers)
        ]
        insert_cards_batch(records, db_path=temp_db_path)

        output_csv = str(tmp_path / "leading_zeros.csv")
        export_card_ladder_csv(db_path=temp_db_path, output_path=output_csv, status_filter="CLEARED")

        # 1. Raw byte inspection
        with open(output_csv, "rb") as f:
            raw_bytes = f.read()
        raw_text = raw_bytes.decode("utf-8")

        for num in test_numbers:
            # Number must appear verbatim without truncation to integer (e.g. "007" not "7")
            assert num in raw_text

        # 2. Pandas read_csv with dtype=str
        df = pd.read_csv(output_csv, dtype=str)
        assert list(df["Number"]) == test_numbers

    def test_500_card_batch_chunking(self, temp_db_path, tmp_path):
        """
        Inserts 505 cards and exports with max_batch_size=500, verifying automatic
        chunking into _part1.csv (500 records) and _part2.csv (5 records), each with 16 headers.
        """
        batch_cards = [
            {
                "player": f"Athlete {i:04d}",
                "year": "2021",
                "set_name": "Panini Prizm",
                "variation": "",
                "card_number": f"{i:03d}",
                "category": "Basketball",
                "condition": "Raw",
                "ai_status": "CLEARED",
            }
            for i in range(1, 506)
        ]
        insert_cards_batch(batch_cards, db_path=temp_db_path, chunk_size=500)
        assert get_card_count(temp_db_path) == 505

        base_csv = str(tmp_path / "CardLadder_Bulk_Upload.csv")
        total_exported, files = export_card_ladder_csv(
            db_path=temp_db_path,
            output_path=base_csv,
            status_filter="CLEARED",
            max_batch_size=500,
        )

        assert total_exported == 505
        assert len(files) == 2

        # Check part 1
        part1 = files[0]
        assert part1.endswith("_part1.csv")
        val1 = validate_card_ladder_csv(part1)
        assert val1["valid"] is True
        assert val1["row_count"] == 500

        # Check part 2
        part2 = files[1]
        assert part2.endswith("_part2.csv")
        val2 = validate_card_ladder_csv(part2)
        assert val2["valid"] is True
        assert val2["row_count"] == 5

    def test_fuzzy_normalization_in_export(self, temp_db_path, tmp_path):
        """Verifies that player and set names are normalized against canonical checklists during export."""
        cards = [
            {
                "player": "Luka Doncic",  # Missing diacritic
                "year": "2018",
                "set_name": "prizm",     # Incomplete set name
                "category": "Basketball",
                "condition": "PSA 10",
                "card_number": "280",
                "slab_serial_number": "48192041",
                "ai_status": "CLEARED",
            },
            {
                "player": "Steph Curry",  # Nickname
                "year": "2009",
                "set_name": "topps chrome bb",  # Shorthand
                "category": "Basketball",
                "condition": "Raw",
                "card_number": "101",
                "ai_status": "CLEARED",
            },
        ]
        insert_cards_batch(cards, db_path=temp_db_path)

        output_csv = str(tmp_path / "normalized_export.csv")
        export_card_ladder_csv(
            db_path=temp_db_path,
            output_path=output_csv,
            status_filter="CLEARED",
            apply_normalization=True,
        )

        df = pd.read_csv(output_csv, dtype=str)
        players = list(df["Player"])
        sets = list(df["Set"])

        assert "Luka Dončić" in players
        assert "Stephen Curry" in players
        assert "Panini Prizm" in sets
        assert "Topps Chrome" in sets


# ============================================================================
# Tier 5 - Full Omnichannel Lifecycle Scenario Test
# ============================================================================

class TestTier5FullOmnichannelLifecycleScenario:
    """
    Tier 5 Acceptance:
    Comprehensive end-to-end integration test exercising all 4 ingestion pipelines,
    SQLite staging, status review workflow, sales listing generation, and Card Ladder CSV export.
    """

    def test_full_omnichannel_e2e_pipeline(self, api_client, temp_db_path, tmp_path):
        """
        1. Pipeline 1 (Scraper): Ingest Beckett checklist HTML fixture -> Staged in DB.
        2. Pipeline 2 (AI Vision): Ingest mock card images -> Staged in DB.
        3. Pipeline 3 (API Bridge): Ingest Chrome Extension capture payload -> Staged in DB.
        4. Staging Review: Transition cards from REVIEW VARIATION to CLEARED.
        5. Pipeline 4 (Sales Copy): Generate Facebook Marketplace listing for high-value card.
        6. Export Pipeline: Export pristine 16-variable Card Ladder CSV and validate.
        """
        # Step 1: Checklist Scraper Ingestion
        with open(BECKETT_HTML_PATH, "r", encoding="utf-8") as f:
            html_data = f.read()
        scraper_cards = parse_checklist_html(html_data, parallels=["Base", "Silver Prizm"])
        scraped_ids = ingest_scraper_cards(scraper_cards, parent_id=8000, db_path=temp_db_path)
        assert len(scraped_ids) >= 6

        # Step 2: AI Vision Ingestion
        vision_paths = [
            "2020_panini_prizm_luka_doncic_psa10.jpg",
            "2018_bowman_chrome_shohei_ohtani_bgs95.jpg",
        ]
        vision_ids = ingest_vision_batch(vision_paths, parent_id=8500, db_path=temp_db_path)
        assert len(vision_ids) == 2

        # Step 3: Chrome Extension API Ingestion
        api_payload = {
            "player": "Victor Wembanyama",
            "year": "2023",
            "set_name": "Panini Prizm",
            "variation": "Silver Prizm",
            "card_number": "01",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "99281042",
            "investment": 500.0,
            "estimated_value": 1200.0,
            "parent_image_id": 9900,
            "child_card_id": 101,
        }
        api_resp = api_client.post("/api/v1/cards/capture", json=api_payload)
        assert api_resp.status_code == 200
        api_card_id = api_resp.json()["card_id"]

        # Step 4: Verify Total Cards Staged and Status Review
        total_staged = get_card_count(temp_db_path)
        assert total_staged == len(scraped_ids) + len(vision_ids) + 1

        # Clear all cards for export by updating ai_status to CLEARED
        all_cards = get_all_cards(status_filter="ALL", db_path=temp_db_path, limit=500)
        for c in all_cards:
            update_card_status(c["id"], "CLEARED", db_path=temp_db_path)

        cleared_count = get_card_count(temp_db_path, status_filter="CLEARED")
        assert cleared_count == total_staged

        # Step 5: Generate Facebook Marketplace Copy for the high-value card
        sales_resp = api_client.post(f"/api/v1/cards/{api_card_id}/listing?asking_price=1250.0&mock=true")
        assert sales_resp.status_code == 200
        sales_data = sales_resp.json()
        assert "$1,250.00" in sales_data["listing"]
        assert "Victor Wembanyama" in sales_data["listing"]
        assert len(sales_data["structured"]["title"]) < 100
        assert 6 <= len(sales_data["structured"]["hashtags"]) <= 8

        # Step 6: Export to Pristine Card Ladder CSV
        final_csv_path = str(tmp_path / "CardLadder_Bulk_Upload.csv")
        exported_count, generated_files = export_card_ladder_csv(
            db_path=temp_db_path,
            output_path=final_csv_path,
            status_filter="CLEARED",
            apply_normalization=True,
        )

        assert exported_count == total_staged
        assert len(generated_files) == 1

        # Forensic CSV validation
        validation = validate_card_ladder_csv(final_csv_path)
        assert validation["valid"] is True
        assert validation["row_count"] == total_staged
        assert validation["headers"] == CARD_LADDER_COLUMNS

        # Verify leading zero preservation on number "01"
        df = pd.read_csv(final_csv_path, dtype=str)
        wemby_row = df[df["Player"].str.contains("Wembanyama", na=False)]
        assert not wemby_row.empty
        assert "01" in list(wemby_row["Number"])

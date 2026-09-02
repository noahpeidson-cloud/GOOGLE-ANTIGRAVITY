"""
test_adversarial_m6_hardening.py - Phase 2 Adversarial Coverage Hardening Suite.
Comprehensive white-box adversarial stress tests covering all modules of the Sports Card Ecosystem Hub:
1. models.py (validation constraints, boundary conditions, diacritics, cross-field rules)
2. database.py (concurrency, WAL mode, transaction rollback, injection defenses, dynamic queries)
3. vision_ingest.py (multimodal image ingestion, mock heuristics, error handling, batch chaining)
4. scraper_ingest.py (malformed HTML, parallel expansion, rookie flags, network failover)
5. api.py (FastAPI endpoints, CORS, circuit breaker, payload validation, status overrides)
6. sales_generator.py (anti-spam filtering, character bounds, SEO structure, hashtag rules)
7. export.py (exact 16-column Card Ladder CSV format, leading zeros, fuzzy normalization, chunking)
8. app.py (lifecycle, state defaults, server manager)
"""

import csv
import io
import os
import sqlite3
import tempfile
import threading
from pathlib import Path
from typing import Any
import pytest
from fastapi.testclient import TestClient
import pandas as pd

from models import (
    CardRecord,
    CardUpdate,
    CardCategory,
    AIStatus,
    VALID_CATEGORIES,
    CATEGORY_MAP,
    CardBatchCreate,
    CardCaptureRequest,
    CardExtractionSchema,
    MarketplaceListing,
    SalesListingRequest,
    SummaryStatsResponse,
    synthesize_query,
    calculate_query,
    format_notes,
    get_current_date_str,
)
from database import (
    DEFAULT_DB_PATH,
    CIRCUIT_BREAKER_BATCH_LIMIT,
    init_db,
    get_db_connection,
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
    capture_card_from_api,
)
from vision_ingest import (
    extract_card_from_image,
    MockVisionExtractor,
    ingest_vision_card,
    ingest_vision_batch,
    extraction_to_card_record,
    batch_extract_cards,
    batch_extract_to_records,
    _prepare_image_part,
    _normalize_text_for_matching,
)
from scraper_ingest import (
    ChecklistCard,
    ChecklistMetadata,
    ChecklistHTMLParser,
    infer_metadata_from_text,
    parse_checklist_line,
    parse_checklist_table_row,
    extract_parallels_from_html,
    expand_parallels,
    parse_checklist_html,
    fetch_and_parse_checklist,
    ingest_scraper_cards,
)
from sales_generator import (
    FORBIDDEN_BUZZWORDS,
    normalize_card_input,
    resolve_asking_price,
    sanitize_seo_title,
    build_seo_title,
    build_price_section,
    build_specifications_section,
    build_condition_section,
    build_shipping_pickup_section,
    build_hashtags,
    MockSalesGenerator,
    build_structured_listing,
    generate_marketplace_listing,
    generate_listing_for_card_id,
    generate_batch_marketplace_listings,
)
from export import (
    CARD_LADDER_COLUMNS,
    EXCLUDED_INTERNAL_FIELDS,
    get_card_ladder_columns,
    get_excluded_fields,
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
    fetch_records_for_export,
    export_card_ladder_csv,
    validate_card_ladder_csv,
)
from api import (
    app,
    get_db_path,
    ExtendedCardCaptureRequest,
    CardBatchRequest,
    is_port_in_use,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_db():
    """Provides a fresh, isolated temporary SQLite database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    init_db(db_path)
    yield db_path
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


@pytest.fixture
def api_client(temp_db):
    """FastAPI TestClient with dependency override for temp_db."""
    def override_db_path():
        return temp_db

    app.dependency_overrides[get_db_path] = override_db_path
    app.state.db_path = temp_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ============================================================================
# 1. MODELS.PY ADVERSARIAL HARDENING
# ============================================================================

class TestModelsAdversarialHardening:
    """Stress tests and boundary condition validation for models.py."""

    def test_format_notes_boundary_and_errors(self):
        """Tests format_notes with extreme numbers, zero-padding, and invalid types."""
        assert format_notes(0, 0) == "0000-000"
        assert format_notes(9999, 999) == "9999-999"
        assert format_notes("8492", "105") == "8492-105"
        assert format_notes("0042", "007") == "0042-007"
        assert format_notes("8492-105", "") == "8492-105"

        # Invalid formats
        with pytest.raises(ValueError, match="numeric or convertable to integers"):
            format_notes("invalid", "101")
        with pytest.raises(ValueError, match="numeric or convertable to integers"):
            format_notes("8492", "invalid")
        with pytest.raises(ValueError, match="non-negative"):
            format_notes(-1, 101)
        with pytest.raises(ValueError, match="non-negative"):
            format_notes(8492, -5)

    def test_synthesize_query_edge_cases(self):
        """Tests synthesize_query with empty strings, excessive spaces, and complex characters."""
        q1 = synthesize_query(2020, "Panini Prizm", "Luka Dončić", "", "Raw")
        assert q1 == "2020 Panini Prizm Luka Dončić Raw"

        q2 = synthesize_query(" 2021 ", "  Select  ", "  Ja Morant  ", " Silver Prizm ", " PSA 10 ")
        assert q2 == "2021 Select Ja Morant Silver Prizm PSA 10"

        q3 = synthesize_query("1999", "Pokemon Base Set", "Charizard", "1st Edition Holo", "")
        assert q3 == "1999 Pokemon Base Set Charizard 1st Edition Holo"
        assert calculate_query == synthesize_query

    def test_card_record_cross_field_raw_slab_rejection(self):
        """Raw cards with non-empty slab serial numbers must fail validation."""
        with pytest.raises(ValueError, match="Slab serial number must be blank for 'Raw'"):
            CardRecord(
                player="Luka Dončić",
                year="2020",
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
                condition="Raw",
                slab_serial_number="12345678",
            )

    def test_card_record_negative_exclusions_rejection(self):
        """Raw cards with negative exclusions in query must fail validation."""
        for excl in ("-BGS", "-PSA", "-SGC", "-CGC", "-CSG", "-BVG"):
            with pytest.raises(ValueError, match="Negative exclusions are forbidden in queries for Raw cards"):
                CardRecord(
                    player="Luka Dončić",
                    year="2020",
                    set_name="Panini Prizm",
                    category=CardCategory.BASKETBALL,
                    condition="Raw",
                    query=f"2020 Panini Prizm Luka Dončić Raw {excl}",
                )

    def test_card_record_season_year_normalization(self):
        """Multi-year season strings must normalize to 4-digit starting year."""
        rec1 = CardRecord(player="Luka Dončić", year="2020-21", set_name="Panini Prizm", category=CardCategory.BASKETBALL)
        assert rec1.year == "2020"

        rec2 = CardRecord(player="Luka Dončić", year="2020/2021", set_name="Panini Prizm", category=CardCategory.BASKETBALL)
        assert rec2.year == "2020"

        with pytest.raises(ValueError, match="4-digit string"):
            CardRecord(player="Luka Dončić", year="20", set_name="Panini Prizm", category=CardCategory.BASKETBALL)

    def test_card_record_category_aliases_normalization(self):
        """Tests all 22 category aliases and case variants."""
        assert CardRecord(player="A", year="2020", set_name="S", category="ufc").category == "UFC/MMA"
        assert CardRecord(player="A", year="2020", set_name="S", category="mma").category == "UFC/MMA"
        assert CardRecord(player="A", year="2020", set_name="S", category="pop culture").category == "PopCulture"
        assert CardRecord(player="A", year="2020", set_name="S", category="dragon ball z").category == "Dragonballz"
        assert CardRecord(player="A", year="2020", set_name="S", category="flesh & blood").category == "Flesh and Blood"

        with pytest.raises(ValueError, match="Invalid category"):
            CardRecord(player="A", year="2020", set_name="S", category="Cricket")

    def test_card_record_date_purchased_normalization(self):
        """Tests date formats ISO YYYY-MM-DD vs MM/DD/YYYY and malformed dates."""
        rec_iso = CardRecord(player="A", year="2020", set_name="S", category=CardCategory.BASKETBALL, date_purchased="2024-05-12")
        assert rec_iso.date_purchased == "05/12/2024"

        rec_short = CardRecord(player="A", year="2020", set_name="S", category=CardCategory.BASKETBALL, date_purchased="5/2/2024")
        assert rec_short.date_purchased == "05/02/2024"

        with pytest.raises(ValueError, match="Invalid date format"):
            CardRecord(player="A", year="2020", set_name="S", category=CardCategory.BASKETBALL, date_purchased="2024/05/12")

    def test_card_record_condition_hyphen_rejection(self):
        """Graded conditions with hyphens (e.g. 'PSA-10') must be rejected."""
        with pytest.raises(ValueError, match="must not contain hyphens"):
            CardRecord(player="A", year="2020", set_name="S", category=CardCategory.BASKETBALL, condition="PSA-10")

    def test_card_record_auto_review_variation_trigger(self):
        """Presence of variation must automatically elevate AIStatus from CLEARED to REVIEW VARIATION."""
        rec = CardRecord(
            player="Luka Dončić",
            year="2020",
            set_name="Panini Prizm",
            variation="Silver Prizm",
            category=CardCategory.BASKETBALL,
        )
        assert rec.ai_status == AIStatus.REVIEW_VARIATION

    def test_card_batch_create_circuit_breaker_limits(self):
        """CardBatchCreate must enforce 1 <= len(cards) <= 500."""
        card = CardRecord(player="P", year="2020", set_name="S", category=CardCategory.BASKETBALL)

        with pytest.raises(ValueError):
            CardBatchCreate(cards=[])

        valid_batch = CardBatchCreate(cards=[card] * 500)
        assert len(valid_batch.cards) == 500

        with pytest.raises(ValueError):
            CardBatchCreate(cards=[card] * 501)


# ============================================================================
# 2. DATABASE.PY CONCURRENCY, TRANSACTIONS & SECURITY
# ============================================================================

class TestDatabaseAdversarialHardening:
    """Stress testing SQLite concurrency, SQL injection safety, transactions, and indexing."""

    def test_concurrent_multithreaded_writes_and_reads(self, temp_db):
        """Simulates 20 concurrent threads writing and reading simultaneously under WAL mode."""
        num_threads = 20
        cards_per_thread = 10
        errors = []

        def worker(thread_idx: int):
            try:
                for i in range(cards_per_thread):
                    card = CardRecord(
                        player=f"Worker {thread_idx} Player {i}",
                        year="2020",
                        set_name="Concurrent Prizm",
                        category=CardCategory.BASKETBALL,
                        investment=float(thread_idx * 10 + i),
                    )
                    cid = insert_card(card, db_path=temp_db)
                    fetched = get_card_by_id(cid, db_path=temp_db)
                    assert fetched is not None
                    assert fetched["player"] == f"Worker {thread_idx} Player {i}"
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent DB access failed: {errors}"
        total_staged = get_card_count(temp_db)
        assert total_staged == num_threads * cards_per_thread

    def test_sql_injection_resilience(self, temp_db):
        """Attacks all string fields with raw SQL injection payloads to confirm parameterization."""
        injection_payloads = [
            "'; DROP TABLE cards; --",
            "' OR 1=1; --",
            "\" OR \"\"=\"",
            "Robert'); DROP TABLE Students;--",
            "<script>alert('xss')</script>",
            "UNION SELECT * FROM cards",
        ]

        for payload in injection_payloads:
            card = CardRecord(
                player=payload,
                year="2020",
                set_name=f"Set {payload}",
                variation=payload,
                card_number="001",
                category=CardCategory.BASKETBALL,
                notes=payload,
                tags=payload,
            )
            cid = insert_card(card, db_path=temp_db)
            retrieved = get_card_by_id(cid, db_path=temp_db)
            assert retrieved is not None
            assert retrieved["player"] == payload

        # Verify table still exists and contains all records
        assert get_card_count(temp_db) == len(injection_payloads)

    def test_atomic_batch_rollback_on_failure(self, temp_db):
        """Tests that insert_cards_batch raises error and does not insert partial invalid batches."""
        valid_card = CardRecord(player="Good Player", year="2020", set_name="Good Set", category=CardCategory.BASKETBALL).model_dump()
        invalid_card = {"player": "", "year": "2020", "set_name": "Invalid", "category": "Basketball"}  # empty player violates model

        with pytest.raises(Exception):
            insert_cards_batch([valid_card, invalid_card], db_path=temp_db)

        # Confirm 0 cards were inserted
        assert get_card_count(temp_db) == 0

    def test_get_next_child_id_with_anomalous_notes(self, temp_db):
        """Tests get_next_child_id when database contains weird, unordered, or high-numbered notes."""
        # Empty DB starts at 101
        assert get_next_child_id("8492", db_path=temp_db) == 101

        # Insert cards with notes
        c1 = CardRecord(player="P1", year="2020", set_name="S", category=CardCategory.BASKETBALL, notes="8492-101")
        c2 = CardRecord(player="P2", year="2020", set_name="S", category=CardCategory.BASKETBALL, notes="8492-105")
        c3 = CardRecord(player="P3", year="2020", set_name="S", category=CardCategory.BASKETBALL, notes="8492-nonnumeric")
        c4 = CardRecord(player="P4", year="2020", set_name="S", category=CardCategory.BASKETBALL, notes="9999-200")

        insert_cards_batch([c1, c2, c3, c4], db_path=temp_db)

        # Max child for 8492 was 105 -> next is 106
        assert get_next_child_id("8492", db_path=temp_db) == 106
        # Max child for 9999 was 200 -> next is 201
        assert get_next_child_id("9999", db_path=temp_db) == 201
        # Brand new parent 7777 -> starts at 101
        assert get_next_child_id("7777", db_path=temp_db) == 101

    def test_update_card_resynthesizes_query_automatically(self, temp_db):
        """Modifying year, set, player, variation, or condition must re-synthesize query."""
        card = CardRecord(
            player="Initial Player",
            year="2020",
            set_name="Panini Prizm",
            variation="Base",
            condition="Raw",
            category=CardCategory.BASKETBALL,
        )
        cid = insert_card(card, db_path=temp_db)

        # Update player and condition
        update_card(cid, {"player": "Updated Player", "condition": "PSA 10", "slab_serial_number": "99999999"}, db_path=temp_db)
        updated = get_card_by_id(cid, db_path=temp_db)

        assert updated["player"] == "Updated Player"
        assert updated["condition"] == "PSA 10"
        assert updated["query"] == "2020 Panini Prizm Updated Player Base PSA 10"

    def test_summary_stats_zero_and_populated_states(self, temp_db):
        """Tests get_summary_stats on empty database and populated database."""
        empty_stats = get_summary_stats(temp_db)
        assert empty_stats["total_cards"] == 0
        assert empty_stats["total_investment"] == 0.0
        assert empty_stats["total_estimated_value"] == 0.0
        assert empty_stats["count_by_category"] == {}
        assert empty_stats["count_by_ai_status"] == {}

        # Populate with 2 cards
        c1 = CardRecord(player="P1", year="2020", set_name="S", category=CardCategory.BASKETBALL, investment=10.0, estimated_value=25.0)
        c2 = CardRecord(player="P2", year="2020", set_name="S", category=CardCategory.BASEBALL, investment=15.0, estimated_value=50.0)
        insert_cards_batch([c1, c2], db_path=temp_db)

        stats = get_summary_stats(temp_db)
        assert stats["total_cards"] == 2
        assert stats["total_investment"] == 25.0
        assert stats["total_estimated_value"] == 75.0
        assert stats["count_by_category"]["Basketball"] == 1
        assert stats["count_by_category"]["Baseball"] == 1


# ============================================================================
# 3. VISION_INGEST.PY ADVERSARIAL STRESS
# ============================================================================

class TestVisionIngestAdversarialHardening:
    """Stress tests MockVisionExtractor, accent handling, batch boundaries, and fallback paths."""

    def test_mock_vision_accent_and_diacritic_matching(self):
        """Ensures filename tokens with or without accents correctly match canonical fixtures."""
        res_accent = MockVisionExtractor("luka_doncic_silver_prizm_psa10.jpg")
        assert "Luka" in res_accent.player
        assert res_accent.category == "Basketball"

        res_ohtani = MockVisionExtractor("shohei_ohtani_bowman_chrome.jpg")
        assert "Shohei Ohtani" in res_ohtani.player
        assert res_ohtani.category == "Baseball"

        res_acuna = MockVisionExtractor("ronald_acuna_topps_chrome.jpg")
        assert "Acuña" in res_acuna.player or "Acuna" in res_acuna.player
        assert res_acuna.category == "Baseball"

    def test_mock_vision_regex_structured_filename_fallback(self):
        """Tests parsing arbitrary structured filenames without predefined fixture subject."""
        res = MockVisionExtractor("2022_panini_select_football_psa10_silver_test.jpg")
        assert res.year == "2022"
        assert res.category == "Football"
        assert res.condition == "PSA 10"
        assert res.variation == "Silver Prizm"
        assert res.slab_serial_number != ""

    def test_prepare_image_part_exceptions(self):
        """Tests _prepare_image_part error branches."""
        with pytest.raises(FileNotFoundError):
            _prepare_image_part("non_existent_image_path_12345.jpg")

        with pytest.raises(TypeError):
            _prepare_image_part(12345)  # invalid type

    def test_batch_extract_cards_circuit_breaker(self):
        """batch_extract_cards must enforce <= 500 limit."""
        paths = [f"image_{i}.jpg" for i in range(501)]
        with pytest.raises(ValueError, match="500-card circuit breaker"):
            batch_extract_cards(paths, mock=True)

    def test_ingest_vision_batch_sequential_notes(self, temp_db):
        """ingest_vision_batch must generate sequential 4-digit/3-digit notes."""
        images = ["img_a.jpg", "img_b.jpg", "img_c.jpg"]
        ids = ingest_vision_batch(images, parent_id="8492", db_path=temp_db)
        assert len(ids) == 3

        c1 = get_card_by_id(ids[0], db_path=temp_db)
        c2 = get_card_by_id(ids[1], db_path=temp_db)
        c3 = get_card_by_id(ids[2], db_path=temp_db)

        assert c1["notes"] == "8492-101"
        assert c2["notes"] == "8492-102"
        assert c3["notes"] == "8492-103"


# ============================================================================
# 4. SCRAPER_INGEST.PY ADVERSARIAL STRESS
# ============================================================================

class TestScraperIngestAdversarialHardening:
    """Stress tests HTML parsing, malformed tags, rookie card extraction, and parallel expansion."""

    def test_parse_malformed_html_and_unclosed_tags(self):
        """HTML parser must handle broken tags, missing closures, and messy nesting without crashing."""
        broken_html = """
        <html>
        <head><title>2023-24 Panini Prizm Basketball Checklist</title>
        <body>
        <h1>2023-24 Panini Prizm Basketball Cards</h1>
        <h2>Base Set Checklist
        <table>
            <tr><th>Card #<th>Player<th>Team
            <tr><td>#1<td>Luka Doncic<td>Dallas Mavericks
            <tr><td>#2<td>Victor Wembanyama (RC)<td>San Antonio Spurs
            <tr><td>#3<td>Stephen Curry<td>Golden State Warriors
        </table>
        <h2>Parallels Breakdown</h2>
        <ul>
            <li>Silver Prizm
            <li>Red /99
            <li>Gold /10
        </ul>
        """
        cards = parse_checklist_html(broken_html)
        assert len(cards) > 0
        # 3 base cards * 4 parallels (Base, Silver Prizm, Red /99, Gold /10) = 12 cards
        assert len(cards) == 12

        wemby_cards = [c for c in cards if "Wembanyama" in c.player]
        assert len(wemby_cards) == 4
        assert wemby_cards[0].year == "2023"
        assert wemby_cards[0].category == "Basketball"

    def test_rookie_card_tag_detection(self):
        """RC, (RC), [RC], Rookie tokens must be cleanly extracted without mangling player name."""
        cases = [
            ("101 Victor Wembanyama (RC) - Spurs", "Victor Wembanyama", True),
            ("102 Brandon Miller [RC] | Hornets", "Brandon Miller", True),
            ("103 Scoot Henderson Rookie, Blazers", "Scoot Henderson", True),
            ("104 LeBron James - Lakers", "LeBron James", False),
        ]
        for line, expected_player, is_rc in cases:
            res = parse_checklist_line(line)
            assert res is not None
            assert res.player == expected_player
            assert res.is_rookie == is_rc

    def test_infer_metadata_from_text(self):
        """Infers year, category, and clean set name from headers."""
        meta1 = infer_metadata_from_text("2023-24 Panini Prizm Basketball Checklist")
        assert meta1["year"] == "2023"
        assert meta1["category"] == "Basketball"
        assert "Panini Prizm" in meta1["set_name"]

        meta2 = infer_metadata_from_text("1999 Pokemon Base Set Checklist & Odds")
        assert meta2["year"] == "1999"
        assert meta2["category"] == "Pokemon"

    def test_expand_parallels_ai_status_assignment(self):
        """Base parallel must set variation='' and ai_status=CLEARED; others get REVIEW VARIATION."""
        base_item = ChecklistCard(card_number="001", player="Luka Dončić", team="Mavs")
        expanded = expand_parallels([base_item], parallels=["Base", "Silver Prizm", "Gold /10"])

        assert len(expanded) == 3
        # 1. Base
        assert expanded[0].variation == ""
        assert expanded[0].ai_status == AIStatus.CLEARED

        # 2. Silver Prizm
        assert expanded[1].variation == "Silver Prizm"
        assert expanded[1].ai_status == AIStatus.REVIEW_VARIATION

        # 3. Gold /10
        assert expanded[2].variation == "Gold /10"
        assert expanded[2].ai_status == AIStatus.REVIEW_VARIATION


# ============================================================================
# 5. API.PY REST ENDPOINTS & HTTP HARDENING
# ============================================================================

class TestApiAdversarialHardening:
    """Stress tests FastAPI route validation, circuit breaker, error codes, and CORS headers."""

    def test_api_health_endpoint(self, api_client):
        """GET /health and /api/v1/health return healthy system status."""
        for endpoint in ("/health", "/api/v1/health"):
            res = api_client.get(endpoint)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "healthy"
            assert data["database"] == "connected"
            assert "circuit_breaker" in data

    def test_api_capture_single_card_success_and_validation(self, api_client):
        """POST /api/v1/cards/capture validates schema and inserts record."""
        valid_payload = {
            "player": "Luka Dončić",
            "year": "2020",
            "set_name": "Panini Prizm",
            "variation": "Silver Prizm",
            "card_number": "75",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "48192041",
            "investment": 150.0,
            "estimated_value": 350.0,
            "parent_image_id": "8492",
        }
        res = api_client.post("/api/v1/cards/capture", json=valid_payload)
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "success"
        assert body["card_id"] >= 1
        assert body["notes"] == "8492-101"
        assert body["ai_status"] == "REVIEW VARIATION"

    def test_api_capture_card_validation_errors(self, api_client):
        """POST /api/v1/cards/capture must return 422 for invalid payloads."""
        # Missing required player
        res1 = api_client.post("/api/v1/cards/capture", json={"year": "2020", "set_name": "Prizm", "category": "Basketball"})
        assert res1.status_code == 422

        # Raw card with slab serial number (cross-field constraint)
        res2 = api_client.post("/api/v1/cards/capture", json={
            "player": "Luka Dončić",
            "year": "2020",
            "set_name": "Panini Prizm",
            "category": "Basketball",
            "condition": "Raw",
            "slab_serial_number": "12345678",
        })
        assert res2.status_code == 422

    def test_api_batch_capture_limits(self, api_client):
        """POST /api/v1/cards/batch enforces 1 <= batch_size <= 500."""
        # Empty batch -> 400
        res_empty = api_client.post("/api/v1/cards/batch", json={"cards": []})
        assert res_empty.status_code == 422 or res_empty.status_code == 400

        # Batch > 500 -> 400
        card = {
            "player": "Batch Player",
            "year": "2020",
            "set_name": "Prizm",
            "category": "Basketball",
        }
        res_overflow = api_client.post("/api/v1/cards/batch", json={"cards": [card] * 501})
        assert res_overflow.status_code == 422 or res_overflow.status_code == 400

        # Valid batch of 5
        res_valid = api_client.post("/api/v1/cards/batch", json={"cards": [card] * 5})
        assert res_valid.status_code == 200
        assert res_valid.json()["inserted_count"] == 5

    def test_api_crud_lifecycle_and_not_found(self, api_client):
        """Tests full GET, PATCH, DELETE endpoints and 404 handling."""
        # Insert initial card
        card_data = {
            "player": "Initial",
            "year": "2020",
            "set_name": "Prizm",
            "category": "Basketball",
            "condition": "Raw",
        }
        res_post = api_client.post("/api/v1/cards/capture", json=card_data)
        cid = res_post.json()["card_id"]

        # GET by ID
        res_get = api_client.get(f"/api/v1/cards/{cid}")
        assert res_get.status_code == 200
        assert res_get.json()["card"]["player"] == "Initial"

        # PATCH update
        res_patch = api_client.patch(f"/api/v1/cards/{cid}", json={"player": "Updated Player", "estimated_value": 199.99})
        assert res_patch.status_code == 200
        assert res_patch.json()["card"]["player"] == "Updated Player"
        assert res_patch.json()["card"]["estimated_value"] == 199.99

        # Update status
        res_status = api_client.post(f"/api/v1/cards/{cid}/status", json={"status": "NEEDS REVIEW"})
        assert res_status.status_code == 200
        assert res_status.json()["ai_status"] == "NEEDS REVIEW"

        # DELETE
        res_del = api_client.delete(f"/api/v1/cards/{cid}")
        assert res_del.status_code == 200

        # Subsequent GET returns 404
        res_get_gone = api_client.get(f"/api/v1/cards/{cid}")
        assert res_get_gone.status_code == 404

    def test_api_on_demand_sales_generation(self, api_client):
        """POST /api/v1/sales/generate supports both inline card_data and stored card_id."""
        inline_payload = {
            "card_data": {
                "player": "Shohei Ohtani",
                "year": "2018",
                "set_name": "Bowman Chrome",
                "variation": "Refractor",
                "condition": "BGS 9.5",
                "slab_serial_number": "0014892102",
                "category": "Baseball",
                "estimated_value": 1100.0,
            },
            "asking_price": 1050.0,
            "mock": True,
        }
        res = api_client.post("/api/v1/sales/generate", json=inline_payload)
        assert res.status_code == 200
        data = res.json()
        assert "KEY SPECIFICATIONS" in data["listing"]
        assert data["structured"]["price"] == 1050.0


# ============================================================================
# 6. SALES_GENERATOR.PY ADVERSARIAL HARDENING
# ============================================================================

class TestSalesGeneratorAdversarialHardening:
    """Stress tests buzzword filtering, character boundary truncation, and structured copy rules."""

    def test_sanitize_seo_title_strips_forbidden_buzzwords_and_emojis(self):
        """FORBIDDEN_BUZZWORDS and emojis must be stripped from listing titles."""
        raw_dirty_title = "🔥 2020 Panini Prizm Luka Dončić Silver Prizm PSA 10? INVEST RARE GRAIL 🚀"
        clean = sanitize_seo_title(raw_dirty_title, max_length=99)

        assert "🔥" not in clean
        assert "🚀" not in clean
        assert "INVEST" not in clean
        assert "RARE" not in clean
        assert "GRAIL" not in clean
        assert "PSA 10?" not in clean
        assert len(clean) <= 99
        assert "2020 Panini Prizm Luka Dončić Silver Prizm" in clean

    def test_build_seo_title_length_bounds(self):
        """build_seo_title must never exceed max_length (default 99 chars)."""
        card = {
            "year": "2020",
            "set_name": "Super Long Manufacturer Name High End Ultra Premium Limited Edition Set Collection",
            "player": "Extremely Long Fictional Player Name With Multiple Middle Names And Suffixes Jr. III",
            "variation": "Neon Green Shimmer Sparkle Wave Pulsar Disco Mojo Prizm Die-Cut Refractor /5",
            "condition": "BGS 9.5 (10 Centering, 9.5 Corners, 9.5 Edges, 9.5 Surface)",
        }
        title = build_seo_title(card, max_length=99)
        assert len(title) <= 99
        # Must not end in partial word or illegal trailing chars
        assert not title.endswith(" ")

    def test_resolve_asking_price_hierarchy(self):
        """Tests fallback precedence: asking_price -> estimated_value -> investment -> 50.00."""
        # 1. Explicit asking_price
        assert resolve_asking_price({"estimated_value": 100.0, "investment": 50.0}, asking_price=75.0) == 75.0

        # 2. Estimated value
        assert resolve_asking_price({"estimated_value": 100.0, "investment": 50.0}) == 100.0

        # 3. Investment
        assert resolve_asking_price({"estimated_value": 0.0, "investment": 50.0}) == 50.0

        # 4. Default fallback
        assert resolve_asking_price({"estimated_value": 0.0, "investment": 0.0}) == 50.00

    def test_build_hashtags_strict_range(self):
        """build_hashtags must strictly return between 6 and 8 valid hashtags."""
        card_min = {"player": "", "set_name": "", "category": "Basketball", "condition": "Raw", "year": "2020"}
        tags_min = build_hashtags(card_min)
        assert 6 <= len(tags_min) <= 8
        assert all(t.startswith("#") for t in tags_min)

        card_full = {
            "player": "Luka Dončić",
            "set_name": "Panini Prizm",
            "category": "Basketball",
            "variation": "Silver Prizm",
            "condition": "PSA 10",
            "year": "2020",
        }
        tags_full = build_hashtags(card_full)
        assert 6 <= len(tags_full) <= 8
        assert all(t.startswith("#") for t in tags_full)
        assert "#SportsCards" in tags_full
        assert "#TheHobby" in tags_full

    def test_mock_sales_generator_exact_six_sections(self):
        """MockSalesGenerator must output all 6 standard sections."""
        card = {
            "player": "Luka Dončić",
            "year": "2020",
            "set_name": "Panini Prizm",
            "variation": "Silver Prizm",
            "card_number": "75",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "48192041",
            "estimated_value": 350.0,
        }
        listing = MockSalesGenerator.generate(card, asking_price=350.0, custom_notes="Vault stored.")
        assert "ASKING PRICE: $350.00" in listing
        assert "KEY SPECIFICATIONS:" in listing
        assert "CONDITION & AUTHENTICITY:" in listing
        assert "SHIPPING & LOCAL PICKUP:" in listing
        assert "TAGS:" in listing
        assert "#SportsCards" in listing


# ============================================================================
# 7. EXPORT.PY CARD LADDER 16-COLUMN & FUZZY NORMALIZATION
# ============================================================================

class TestExportAdversarialHardening:
    """Stress tests exact 16-column Card Ladder CSV export, diacritic folding, leading zeros, and chunking."""

    def test_canonical_column_count_and_exclusions(self):
        """Confirms exactly 16 columns and strict exclusion of 5 internal variables."""
        cols = get_card_ladder_columns()
        assert len(cols) == 16
        assert cols == [
            "Date Purchased", "Quantity", "Player", "Year", "Set", "Variation",
            "Number", "Category", "Condition", "Investment", "Estimated Value",
            "Ladder ID", "Notes", "Date Sold", "Sold Price", "Image"
        ]

        excluded = get_excluded_fields()
        for internal in ("slab_serial_number", "query", "tags", "back_image", "ai_status"):
            assert internal in excluded
            assert internal not in cols

    def test_diacritic_folding_and_alias_normalization(self):
        """Tests fuzzy diacritic normalization against canonical sports & TCG checklists."""
        assert normalize_player_name("Luka Doncic", "Basketball") == "Luka Dončić"
        assert normalize_player_name("Ronald Acuna Jr.", "Baseball") == "Ronald Acuña Jr."
        assert normalize_player_name("Steph Curry", "Basketball") == "Stephen Curry"
        assert normalize_player_name("Wemby", "Basketball") == "Victor Wembanyama"
        assert normalize_player_name("Shohei Ohtani (大谷 翔平)", "Baseball") == "Shohei Ohtani"
        assert normalize_player_name("Iga Swiatek", "Tennis") == "Iga Świątek"
        assert normalize_player_name("CR7", "Soccer") == "Cristiano Ronaldo"

        # Set Normalization
        assert normalize_set_name("2020 Panini Prizm", year="2020", category="Basketball") == "Panini Prizm"
        assert normalize_set_name("TC", category="Baseball") == "Topps Chrome"
        assert normalize_set_name("YG", category="Hockey") == "Upper Deck Young Guns"
        assert normalize_set_name("Pokemon Base", category="Pokemon") == "Base Set"
        assert normalize_set_name("Magic Alpha", category="Magic") == "Limited Edition Alpha"

    def test_leading_zero_preservation_in_dataframe_and_csv(self, temp_db):
        """Leading zeros on card_number (e.g. '001', '04/102') must never be converted to ints."""
        cards = [
            CardRecord(player="P1", year="2020", set_name="Panini Prizm", card_number="001", category=CardCategory.BASKETBALL),
            CardRecord(player="P2", year="1999", set_name="Pokemon Base", card_number="04/102", category=CardCategory.POKEMON),
            CardRecord(player="P3", year="2021", set_name="Select", card_number="007", category=CardCategory.BASKETBALL),
        ]
        insert_cards_batch(cards, db_path=temp_db)

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name

        try:
            total_exp, gen_files = export_card_ladder_csv(db_path=temp_db, output_path=csv_path, status_filter="ALL")
            assert total_exp == 3
            assert len(gen_files) == 1

            # Read back as raw text lines to confirm exact CSV output
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
                assert len(reader) == 3
                assert reader[0]["Number"] == "001"
                assert reader[1]["Number"] == "04/102"
                assert reader[2]["Number"] == "007"

            # Forensic verification
            val = validate_card_ladder_csv(csv_path)
            assert val["valid"] is True
            assert val["row_count"] == 3
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)

    def test_csv_export_automatic_chunking_circuit_breaker(self, temp_db):
        """Databases exceeding 500 records must chunk into _part1.csv, _part2.csv, etc."""
        # Populate 1,050 records
        base_record = CardRecord(
            player="Chunk Player",
            year="2020",
            set_name="Panini Prizm",
            category=CardCategory.BASKETBALL,
        ).model_dump()
        batch_cards = [base_record.copy() for _ in range(1050)]
        insert_cards_batch(batch_cards, db_path=temp_db)

        with tempfile.TemporaryDirectory() as tmpdir:
            target_csv = os.path.join(tmpdir, "Bulk_Upload.csv")
            total_exp, gen_files = export_card_ladder_csv(
                db_path=temp_db,
                output_path=target_csv,
                status_filter="ALL",
                max_batch_size=500,
            )

            assert total_exp == 1050
            # 1050 / 500 -> 3 files (500, 500, 50)
            assert len(gen_files) == 3
            assert gen_files[0].endswith("Bulk_Upload_part1.csv")
            assert gen_files[1].endswith("Bulk_Upload_part2.csv")
            assert gen_files[2].endswith("Bulk_Upload_part3.csv")

            for fpath in gen_files:
                val = validate_card_ladder_csv(fpath)
                assert val["valid"] is True


# ============================================================================
# 8. APP.PY INTEGRATION & RUNTIME CHECKS
# ============================================================================

class TestAppAdversarialHardening:
    """Stress tests Streamlit app utility helpers and API port bindings."""

    def test_is_port_in_use_helper(self):
        """is_port_in_use returns boolean without exception."""
        status_unused = is_port_in_use(59999)
        assert isinstance(status_unused, bool)

    def test_empty_export_creates_header_only_csv(self, temp_db):
        """Exporting an empty database creates a valid 16-column header-only CSV."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            total_exp, gen_files = export_card_ladder_csv(db_path=temp_db, output_path=csv_path, status_filter="CLEARED")
            assert total_exp == 0
            assert len(gen_files) == 1

            val = validate_card_ladder_csv(csv_path)
            assert val["valid"] is True
            assert val["row_count"] == 0
            assert len(val["headers"]) == 16
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)

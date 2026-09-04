"""
tests/test_adversarial_m6_chaos.py - Milestone 6 Phase 2 Omnichannel Chaos Stress Test Suite.
Authored by Teamwork Preview Challenger (Agent Challenger M6_2).

Target: sports_cards/ecosystem_hub
Scope: Full Omnichannel Lifecycle Chaos Stress Testing & Verification:
1. Concurrently trigger:
   - Scraper checklist bulk ingestion (100 cards)
   - Chrome Extension API capture endpoint (20 concurrent requests)
   - AI Vision batch ingestion (50 cards)
   - Background FastAPI daemon requests on port 8002 / test port
   - Live Streamlit AppTest status toggles and listing generation
   - Card Ladder CSV export with fuzzy normalization on the live database
2. Strict Verifications:
   - Zero SQLite locking errors (WAL mode concurrency with 5000ms busy timeout)
   - Exact 16 columns in exported Card Ladder CSV
   - All leading zeros preserved (e.g., '001', '007', '042', '0099', '04/102')
   - All 21 variables consistent and compliant across all records in SQLite
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
import requests
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
    CardCaptureRequest,
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
    ingest_vision_batch,
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
    format_card_row_for_card_ladder,
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
# Test Fixtures & Utilities
# ============================================================================

def get_free_port() -> int:
    """Finds an available TCP port for ephemeral test daemon execution."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def chaos_db(tmp_path, monkeypatch) -> str:
    """Provides a fresh isolated SQLite database configured in WAL mode for chaos testing."""
    db_file = str(tmp_path / "omnichannel_chaos.db")
    init_db(db_file)
    monkeypatch.setenv("PORTFOLIO_DB_PATH", db_file)
    return db_file


def generate_mock_checklist_html(card_count: int = 25) -> str:
    """
    Generates a realistic Beckett/Cardboard Connection checklist HTML table
    with leading zero numbers, player names with diacritics, and RC indicators.
    """
    rows = []
    base_players = [
        ("001", "Luka Doncic", "Dallas Mavericks", False),
        ("002", "Victor Wembanyama", "San Antonio Spurs", True),
        ("003", "Shohei Otani", "Los Angeles Dodgers", False),
        ("004", "Patrick Mahomes", "Kansas City Chiefs", False),
        ("005", "Charizard", "Pokemon", False),
        ("006", "Caitlin Clark", "Indiana Fever", True),
        ("007", "Angel Reese", "Chicago Sky", True),
        ("008", "Stephen Curry", "Golden State Warriors", False),
        ("009", "LeBron James", "Los Angeles Lakers", False),
        ("010", "Michael Jordan", "Chicago Bulls", False),
        ("011", "Kobe Bryant", "Los Angeles Lakers", False),
        ("012", "Aaron Judge", "New York Yankees", False),
        ("013", "Juan Soto", "New York Yankees", False),
        ("014", "Ronald Acuna Jr.", "Atlanta Braves", False),
        ("015", "Elly De La Cruz", "Cincinnati Reds", True),
        ("016", "Paul Skenes", "Pittsburgh Pirates", True),
        ("017", "Connor McDavid", "Edmonton Oilers", False),
        ("018", "Connor Bedard", "Chicago Blackhawks", True),
        ("019", "Lionel Messi", "Inter Miami CF", False),
        ("020", "Erling Haaland", "Manchester City", False),
        ("021", "Max Verstappen", "Red Bull Racing", False),
        ("022", "Lewis Hamilton", "Mercedes", False),
        ("023", "Jon Jones", "UFC", False),
        ("024", "Pikachu", "Pokemon", False),
        ("025", "Travis Kelce", "Kansas City Chiefs", False),
    ]

    for i in range(card_count):
        idx = i % len(base_players)
        num_str = f"{i + 1:03d}"
        player, team, is_rc = base_players[idx][1], base_players[idx][2], base_players[idx][3]
        rc_tag = " RC" if is_rc else ""
        rows.append(
            f"<tr><td>{num_str}</td><td>{player}{rc_tag}</td><td>{team}</td></tr>"
        )

    table_body = "\n".join(rows)
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>2024 Panini Prizm Basketball Checklist</title></head>
    <body>
        <h1>2024 Panini Prizm Basketball Checklist</h1>
        <h2>Parallels Breakdown</h2>
        <ul>
            <li>Base</li>
            <li>Silver Prizm</li>
            <li>Red /99</li>
            <li>Gold /10</li>
        </ul>
        <h2>Base Set Checklist</h2>
        <table>
            <thead><tr><th>Card #</th><th>Player</th><th>Team</th></tr></thead>
            <tbody>
                {table_body}
            </tbody>
        </table>
    </body>
    </html>
    """


# ============================================================================
# Master Suite: Omnichannel Chaos Challenge
# ============================================================================

class TestOmnichannelChaosChallenge:
    """
    Milestone 6 Phase 2: Full Omnichannel Chaos Challenge Test Suite.
    Simultaneously executes all 6 ingestion and processing pipelines against
    a live SQLite database in WAL mode and verifies schema & export compliance.
    """

    def test_full_lifecycle_omnichannel_concurrency_storm(self, chaos_db: str, tmp_path):
        """
        Adversarial Omnichannel Concurrency Storm:
        Concurrently triggers:
        1. Scraper checklist bulk ingestion (100 cards: 25 base x 4 parallels).
        2. Chrome Extension API capture endpoint (20 concurrent requests with leading zero numbers).
        3. AI Vision batch ingestion (50 cards with child IDs and variation tracking).
        4. Background FastAPI daemon requests (continuous health/stats/listing polling).
        5. Live Streamlit AppTest status toggles and listing generation.
        6. Card Ladder CSV export with fuzzy normalization on the live database.

        Verifies:
        - 0 SQLite locking errors across all operations.
        - Exact 170 cards ingested and consistent in SQLite.
        - Exact 16 columns in exported CSV.
        - All leading zeros preserved in DB and CSV ('001', '007', '042', '0099', '04/102').
        - All 21 variables compliant across all records.
        """
        app.state.db_path = chaos_db
        app.dependency_overrides[get_db_path] = lambda: chaos_db

        daemon_port = 8002
        if is_port_in_use(daemon_port):
            daemon_port = get_free_port()

        server_thread = BackgroundServerThread(
            app_instance=app,
            host="127.0.0.1",
            port=daemon_port,
            db_path=chaos_db,
        )
        server_thread.start()
        assert server_thread.wait_until_ready(timeout=3.0) is True

        client = TestClient(app)
        barrier = threading.Barrier(6)
        results: dict[str, Any] = {
            "scraper_errors": [],
            "scraper_count": 0,
            "api_errors": [],
            "api_count": 0,
            "vision_errors": [],
            "vision_count": 0,
            "daemon_errors": [],
            "daemon_requests": 0,
            "streamlit_errors": [],
            "streamlit_ops": 0,
            "export_errors": [],
            "export_paths": [],
        }

        # --------------------------------------------------------------------
        # Channel 1: Scraper Checklist Bulk Ingestion (100 cards)
        # --------------------------------------------------------------------
        def channel_1_scraper_bulk_ingest():
            try:
                barrier.wait(timeout=10)
                html_content = generate_mock_checklist_html(card_count=25)
                # 25 cards * 4 parallels (Base, Silver Prizm, Red /99, Gold /10) = 100 cards
                extractions = parse_checklist_html(
                    html_content=html_content,
                    set_name="Panini Prizm",
                    year="2024",
                    category="Basketball",
                    parallels=["Base", "Silver Prizm", "Red /99", "Gold /10"],
                )
                assert len(extractions) == 100, f"Expected 100 extractions, got {len(extractions)}"

                inserted_ids = ingest_scraper_cards(
                    extractions=extractions,
                    parent_id="9001",
                    date_purchased="08/24/2026",
                    investment=10.0,
                    db_path=chaos_db,
                )
                results["scraper_count"] = len(inserted_ids)
                assert len(inserted_ids) == 100
            except Exception as e:
                results["scraper_errors"].append(str(e))

        # --------------------------------------------------------------------
        # Channel 2: Chrome Extension API Capture (20 concurrent requests)
        # --------------------------------------------------------------------
        def channel_2_api_capture_concurrent():
            try:
                barrier.wait(timeout=10)

                def post_single_capture(idx: int):
                    # Multi-sport categories with leading zero card numbers
                    categories = ["Basketball", "Baseball", "Football", "Pokemon", "UFC/MMA"]
                    cat = categories[idx % len(categories)]
                    card_num = f"{idx:04d}"  # '0001', '0002', ..., '0020'
                    payload = {
                        "player": f"Extension Athlete {idx:02d}",
                        "year": "2024",
                        "set_name": "Chrome Extension Series",
                        "variation": "Refractor" if idx % 2 == 0 else "",
                        "card_number": card_num,
                        "category": cat,
                        "condition": "Raw" if idx % 3 != 0 else "PSA 10",
                        "slab_serial_number": "" if idx % 3 != 0 else f"CERT{idx:06d}",
                        "investment": float(idx * 5),
                        "estimated_value": float(idx * 15),
                        "parent_image_id": "7777",
                        "child_card_id": f"{idx:03d}",
                    }
                    resp = client.post("/api/v1/cards/capture", json=payload)
                    return resp.status_code, resp.json()

                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(post_single_capture, i) for i in range(1, 21)]
                    for f in concurrent.futures.as_completed(futures):
                        status_code, data = f.result()
                        if status_code == 200 and data.get("status") == "success":
                            results["api_count"] += 1
                        else:
                            results["api_errors"].append(f"HTTP {status_code}: {data}")
            except Exception as e:
                results["api_errors"].append(str(e))

        # --------------------------------------------------------------------
        # Channel 3: AI Vision Batch Ingestion (50 cards)
        # --------------------------------------------------------------------
        def channel_3_vision_batch_ingest():
            try:
                barrier.wait(timeout=10)
                mock_paths = [f"mock_card_photo_{i:03d}.jpg" for i in range(1, 51)]
                # Ingest 50 mock vision items
                inserted_ids = ingest_vision_batch(
                    extractions_or_paths=mock_paths,
                    parent_id="8492",
                    date_purchased="08/24/2026",
                    investment=25.0,
                    db_path=chaos_db,
                )
                results["vision_count"] = len(inserted_ids)
                assert len(inserted_ids) == 50
            except Exception as e:
                results["vision_errors"].append(str(e))

        # --------------------------------------------------------------------
        # Channel 4: Background FastAPI Daemon Live Polling
        # --------------------------------------------------------------------
        def channel_4_daemon_requests():
            try:
                barrier.wait(timeout=10)
                # Query daemon endpoints rapidly for 2 seconds while DB is hammered
                end_time = time.time() + 2.0
                req_count = 0
                while time.time() < end_time:
                    r1 = client.get("/api/v1/stats")
                    r2 = client.get("/api/v1/cards?limit=50")
                    r3 = client.get("/api/v1/circuit-breaker")
                    r4 = client.get("/health")
                    assert r1.status_code == 200
                    assert r2.status_code == 200
                    assert r3.status_code == 200
                    assert r4.status_code == 200
                    req_count += 4
                    time.sleep(0.02)
                results["daemon_requests"] = req_count
            except Exception as e:
                results["daemon_errors"].append(str(e))

        # --------------------------------------------------------------------
        # Channel 5: Live Streamlit Operations & AppTest
        # --------------------------------------------------------------------
        def channel_5_streamlit_operations():
            try:
                barrier.wait(timeout=10)
                ops = 0
                for _ in range(3):
                    at = AppTest.from_file(APP_PATH)
                    at.run(timeout=15)
                    assert len(at.exception) == 0, f"AppTest exception: {at.exception}"
                    ops += 1

                    # Simulate status update and listing generation on staged items
                    staged_cards = get_all_cards(db_path=chaos_db, limit=5)
                    for card in staged_cards:
                        card_id = card["id"]
                        # Toggle status using string value
                        new_status_str = "CLEARED" if card["ai_status"] != "CLEARED" else "REVIEW VARIATION"
                        update_card_status(card_id, new_status_str, db_path=chaos_db)

                        # Generate structured SEO sales listing
                        listing_text = generate_marketplace_listing(card, asking_price=99.0, mock=True)
                        assert len(listing_text) > 50
                        assert "#SportsCards" in listing_text
                        ops += 2
                    time.sleep(0.05)
                results["streamlit_ops"] = ops
            except Exception as e:
                results["streamlit_errors"].append(str(e))

        # --------------------------------------------------------------------
        # Channel 6: Card Ladder CSV Export on Live Database
        # --------------------------------------------------------------------
        def channel_6_export_live_database():
            try:
                barrier.wait(timeout=10)
                # Perform continuous exports while database is concurrently modified
                for export_round in range(1, 4):
                    out_csv = str(tmp_path / f"live_export_round_{export_round}.csv")
                    total_exp, paths = export_card_ladder_csv(
                        db_path=chaos_db,
                        output_path=out_csv,
                        status_filter="ALL",
                        apply_normalization=True,
                    )
                    results["export_paths"].extend(paths)
                    time.sleep(0.1)
            except Exception as e:
                results["export_errors"].append(str(e))

        # --------------------------------------------------------------------
        # Launch All 6 Omnichannel Threads
        # --------------------------------------------------------------------
        threads = [
            threading.Thread(target=channel_1_scraper_bulk_ingest, name="T1-Scraper"),
            threading.Thread(target=channel_2_api_capture_concurrent, name="T2-APICapture"),
            threading.Thread(target=channel_3_vision_batch_ingest, name="T3-Vision"),
            threading.Thread(target=channel_4_daemon_requests, name="T4-Daemon"),
            threading.Thread(target=channel_5_streamlit_operations, name="T5-Streamlit"),
            threading.Thread(target=channel_6_export_live_database, name="T6-CSVExport"),
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=30)

        # Cleanup background daemon and overrides
        server_thread.stop()
        app.dependency_overrides.clear()

        # --------------------------------------------------------------------
        # Assert Zero Locking Errors Across All Channels
        # --------------------------------------------------------------------
        assert len(results["scraper_errors"]) == 0, f"Scraper errors: {results['scraper_errors']}"
        assert len(results["api_errors"]) == 0, f"API capture errors: {results['api_errors']}"
        assert len(results["vision_errors"]) == 0, f"Vision errors: {results['vision_errors']}"
        assert len(results["daemon_errors"]) == 0, f"Daemon errors: {results['daemon_errors']}"
        assert len(results["streamlit_errors"]) == 0, f"Streamlit errors: {results['streamlit_errors']}"
        assert len(results["export_errors"]) == 0, f"Export errors: {results['export_errors']}"

        assert results["scraper_count"] == 100, f"Expected 100 scraped cards, got {results['scraper_count']}"
        assert results["api_count"] == 20, f"Expected 20 API cards, got {results['api_count']}"
        assert results["vision_count"] == 50, f"Expected 50 vision cards, got {results['vision_count']}"
        assert results["daemon_requests"] > 0, "Expected daemon requests to execute"
        assert results["streamlit_ops"] > 0, "Expected Streamlit operations to execute"
        assert len(results["export_paths"]) >= 3, "Expected at least 3 live export runs"

        # --------------------------------------------------------------------
        # Comprehensive Post-Chaos Consistency Verification (All 21 Variables)
        # --------------------------------------------------------------------
        total_in_db = get_card_count(db_path=chaos_db)
        assert total_in_db == 170, f"Expected exactly 170 total cards in DB (100+20+50), found {total_in_db}"

        all_cards = get_all_cards(db_path=chaos_db, limit=500)
        assert len(all_cards) == 170

        # Verify every single card satisfies all 21 schema requirements
        for card in all_cards:
            # 1. date_purchased (MM/DD/YYYY)
            assert re.match(r"^\d{2}/\d{2}/\d{4}$", card["date_purchased"]), f"Invalid date_purchased: {card['date_purchased']}"
            # 2. quantity (>= 1)
            assert card["quantity"] >= 1
            # 3. player (non-empty)
            assert card["player"] and len(card["player"].strip()) > 0
            # 4. year (4 digits)
            assert re.match(r"^\d{4}$", card["year"]), f"Invalid year: {card['year']}"
            # 5. set_name (non-empty)
            assert card["set_name"] and len(card["set_name"].strip()) > 0
            # 6. variation (string)
            assert isinstance(card["variation"], str)
            # 7. card_number (string)
            assert isinstance(card["card_number"], str)
            # 8. category (1 of 22 valid categories)
            assert card["category"] in VALID_CATEGORIES, f"Invalid category: {card['category']}"
            # 9. condition ('Raw' or graded)
            assert card["condition"] and len(card["condition"].strip()) > 0
            # 10. slab_serial_number (blank if Raw)
            if card["condition"] == "Raw":
                assert card["slab_serial_number"] == "", f"Raw card has slab cert: {card}"
            # 11. investment (>= 0.0)
            assert card["investment"] >= 0.0
            # 12. estimated_value (>= 0.0)
            assert card["estimated_value"] >= 0.0
            # 13. ladder_id (string)
            assert isinstance(card["ladder_id"], str)
            # 14. query (synthesized [Year] [Set] [Player] [Variation] [Condition])
            expected_query = synthesize_query(
                card["year"], card["set_name"], card["player"],
                card["variation"], card["condition"]
            )
            assert card["query"] == expected_query, f"Query mismatch: expected '{expected_query}', got '{card['query']}'"
            # 15. notes ([Parent_Image_ID]-[Child_Card_ID])
            assert re.match(r"^\d{4}-\d{3}$", card["notes"]), f"Invalid notes tracking format: {card['notes']}"
            # 16. tags (string)
            assert isinstance(card["tags"], str)
            # 17. date_sold (string)
            assert isinstance(card["date_sold"], str)
            # 18. sold_price (None or >= 0.0)
            assert card["sold_price"] is None or card["sold_price"] >= 0.0
            # 19. image (string)
            assert isinstance(card["image"], str)
            # 20. back_image (string)
            assert isinstance(card["back_image"], str)
            # 21. ai_status (CLEARED, REVIEW VARIATION, NEEDS REVIEW)
            assert card["ai_status"] in ("CLEARED", "REVIEW VARIATION", "NEEDS REVIEW")

        # --------------------------------------------------------------------
        # Card Ladder Final CSV Export Verification (Exact 16 Columns)
        # --------------------------------------------------------------------
        final_csv_path = str(tmp_path / "CardLadder_Bulk_Upload_Final.csv")
        exported_count, generated_paths = export_card_ladder_csv(
            db_path=chaos_db,
            output_path=final_csv_path,
            status_filter="ALL",
            apply_normalization=True,
        )
        assert exported_count == 170
        assert len(generated_paths) == 1

        val_result = validate_card_ladder_csv(generated_paths[0])
        assert val_result["valid"] is True, f"CSV Validation failed: {val_result}"
        assert val_result["row_count"] == 170
        assert val_result["headers"] == CARD_LADDER_COLUMNS
        assert len(val_result["headers"]) == 16

        # Check for zero internal fields in CSV headers
        for internal in EXCLUDED_INTERNAL_FIELDS:
            assert internal not in val_result["headers"]
            assert internal.replace("_", " ").title() not in val_result["headers"]

        # --------------------------------------------------------------------
        # Verification: Leading Zeroes Strictly Preserved in CSV
        # --------------------------------------------------------------------
        # Read raw CSV file to guarantee no numeric conversion stripped leading zeroes
        with open(generated_paths[0], mode="r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            exported_rows = list(reader)

        assert len(exported_rows) == 170

        # Find API captured cards with leading zeroes ('0001', '0002', etc.)
        api_exported = [r for r in exported_rows if "Extension Athlete" in r["Player"]]
        assert len(api_exported) == 20
        for r in api_exported:
            num = r["Number"]
            assert len(num) == 4 and num.isdigit() and num.startswith("0"), f"Leading zero lost: {num}"

        # Find Scraper cards with leading zeroes ('001', '002', etc.)
        scraper_exported = [r for r in exported_rows if r["Set"] == "Panini Prizm" and r["Year"] == "2024"]
        assert len(scraper_exported) == 100
        for r in scraper_exported:
            num = r["Number"]
            assert len(num) == 3 and num.isdigit() and (num.startswith("0") or int(num) <= 25), f"Leading zero lost: {num}"

        # Verify Pandas string dtype on Number
        df_exported = pd.read_csv(generated_paths[0], dtype={"Number": str, "Year": str})
        assert df_exported["Number"].dtype == object or "str" in str(df_exported["Number"].dtype).lower()
        assert "0001" in df_exported["Number"].values
        assert "001" in df_exported["Number"].values


# ============================================================================
# High-Frequency SQLite Lock Contention Stress Tests
# ============================================================================

class TestAdversarialLockContention:
    """
    Stress-tests SQLite WAL mode concurrency under aggressive multi-threaded
    read/write race conditions.
    """

    def test_aggressive_concurrent_read_write_bursts(self, chaos_db: str, tmp_path):
        """
        40 concurrent worker threads rapidly performing inserts, updates,
        summary stats reads, and CSV exports simultaneously.
        Verifies zero database locked exceptions.
        """
        num_writers = 20
        num_readers = 15
        num_exporters = 5
        records_per_writer = 10

        errors: list[str] = []

        def writer_worker(w_id: int):
            try:
                for i in range(records_per_writer):
                    card_data = {
                        "player": f"Burst Player {w_id}_{i}",
                        "year": "2024",
                        "set_name": "Burst Prizm",
                        "variation": "Silver",
                        "card_number": f"{i:03d}",
                        "category": "Basketball",
                        "condition": "Raw",
                        "investment": float(w_id * 10 + i),
                        "estimated_value": float(w_id * 20 + i),
                        "notes": f"9999-{w_id * 10 + i:03d}",
                        "ai_status": "CLEARED",
                    }
                    new_id = insert_card(card_data, db_path=chaos_db)
                    assert new_id > 0
                    time.sleep(0.005)
            except Exception as e:
                errors.append(f"Writer {w_id} failed: {e}")

        def reader_worker(r_id: int):
            try:
                for _ in range(15):
                    stats = get_summary_stats(db_path=chaos_db)
                    assert "total_cards" in stats
                    count = get_card_count(db_path=chaos_db)
                    assert count >= 0
                    time.sleep(0.005)
            except Exception as e:
                errors.append(f"Reader {r_id} failed: {e}")

        def exporter_worker(e_id: int):
            try:
                for round_num in range(3):
                    out_path = str(tmp_path / f"export_burst_e{e_id}_r{round_num}.csv")
                    export_card_ladder_csv(
                        db_path=chaos_db,
                        output_path=out_path,
                        status_filter="ALL",
                    )
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Exporter {e_id} failed: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
            w_futures = [executor.submit(writer_worker, i) for i in range(num_writers)]
            r_futures = [executor.submit(reader_worker, i) for i in range(num_readers)]
            e_futures = [executor.submit(exporter_worker, i) for i in range(num_exporters)]

            all_futures = w_futures + r_futures + e_futures
            for f in concurrent.futures.as_completed(all_futures):
                f.result()

        assert len(errors) == 0, f"Encountered concurrency lock errors: {errors}"
        expected_total = num_writers * records_per_writer
        assert get_card_count(db_path=chaos_db) == expected_total


# ============================================================================
# Circuit Breaker & Large Batch Chunking
# ============================================================================

class TestCircuitBreakerAndCSVChunking:
    """
    Validates the 500-card batch circuit breaker and automatic CSV file splitting.
    """

    def test_circuit_breaker_550_cards_export_split(self, chaos_db: str, tmp_path):
        """
        Inserts 550 cards into SQLite -> Exports -> Verifies 2 chunk files:
        _part1.csv (500 cards) and _part2.csv (50 cards), each with exact 16 headers.
        """
        batch = []
        for i in range(1, 551):
            batch.append({
                "player": f"Chunk Athlete {i:04d}",
                "year": "2024",
                "set_name": "Chunk Prizm",
                "variation": "",
                "card_number": f"{i:04d}",
                "category": "Basketball",
                "condition": "Raw",
                "investment": 1.0,
                "estimated_value": 5.0,
                "notes": f"5555-{i:03d}",
                "ai_status": "CLEARED",
            })
        insert_cards_batch(batch, db_path=chaos_db)

        cb_status = check_circuit_breaker(chaos_db, threshold=500)
        assert cb_status["total_staged"] == 550
        assert cb_status["circuit_breaker_tripped"] is True

        base_csv = str(tmp_path / "CardLadder_Bulk_Upload.csv")
        total_exported, generated_paths = export_card_ladder_csv(
            db_path=chaos_db,
            output_path=base_csv,
            status_filter="CLEARED",
            max_batch_size=500,
        )
        assert total_exported == 550
        assert len(generated_paths) == 2

        # Validate part 1 (500 rows)
        val1 = validate_card_ladder_csv(generated_paths[0])
        assert val1["valid"] is True
        assert val1["row_count"] == 500
        assert val1["headers"] == CARD_LADDER_COLUMNS

        # Validate part 2 (50 rows)
        val2 = validate_card_ladder_csv(generated_paths[1])
        assert val2["valid"] is True
        assert val2["row_count"] == 50
        assert val2["headers"] == CARD_LADDER_COLUMNS


# ============================================================================
# Schema Boundaries & Edge Cases (All 22 Categories & Leading Zeros)
# ============================================================================

class TestSchemaBoundariesAndLeadingZeros:
    """
    Exhaustively tests leading zero formats, diacritics, and check constraints.
    """

    @pytest.mark.parametrize(
        "card_num",
        ["001", "007", "042", "0099", "000", "0001", "04/102", "RC-01", "BCP-007", "0014892102"],
    )
    def test_leading_zero_preservation_in_all_layers(self, chaos_db: str, tmp_path, card_num: str):
        """Verifies card_number leading zeros remain intact in DB, Pydantic, DataFrame, and CSV."""
        record_data = {
            "player": "Luka Dončić",
            "year": "2024",
            "set_name": "Panini Prizm",
            "variation": "Silver Prizm",
            "card_number": card_num,
            "category": "Basketball",
            "condition": "Raw",
            "investment": 100.0,
            "estimated_value": 300.0,
            "notes": "8492-101",
            "ai_status": "CLEARED",
        }
        card_id = insert_card(record_data, db_path=chaos_db)
        retrieved = get_card_by_id(card_id, db_path=chaos_db)
        assert retrieved["card_number"] == card_num

        csv_out = str(tmp_path / f"zero_test_{card_id}.csv")
        export_card_ladder_csv(db_path=chaos_db, output_path=csv_out, status_filter="ALL")

        with open(csv_out, mode="r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row["Number"] == card_num

    def test_database_check_constraints_rejection(self, chaos_db: str):
        """Verifies SQLite check constraints block corrupted data."""
        # 1. Raw condition with non-empty slab serial number must fail
        with pytest.raises(Exception):
            insert_card({
                "player": "Athlete",
                "year": "2024",
                "set_name": "Set",
                "category": "Basketball",
                "condition": "Raw",
                "slab_serial_number": "123456",
            }, db_path=chaos_db)

        # 2. Invalid year format (non-4-digit) must fail
        with pytest.raises(Exception):
            insert_card({
                "player": "Athlete",
                "year": "24",
                "set_name": "Set",
                "category": "Basketball",
            }, db_path=chaos_db)

        # 3. Invalid category must fail
        with pytest.raises(Exception):
            insert_card({
                "player": "Athlete",
                "year": "2024",
                "set_name": "Set",
                "category": "BadCategory",
            }, db_path=chaos_db)

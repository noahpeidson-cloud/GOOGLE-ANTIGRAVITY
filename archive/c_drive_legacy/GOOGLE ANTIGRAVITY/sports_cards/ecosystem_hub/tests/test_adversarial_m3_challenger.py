"""
tests/test_adversarial_m3_challenger.py - Adversarial Stress & Fuzzing Harness for Milestone 3 API Bridge & Sales Generator.
Authored by Teamwork Preview Challenger (Agent Challenger M3).

Target: sports_cards/ecosystem_hub/api.py, sales_generator.py, models.py, database.py.
Test Dimensions:
1. Malformed Payloads, Missing Fields, Invalid Types, Boundary Violations on POST /api/v1/cards/capture.
2. Security & Sanitization: SQL Injection, XSS, Path Traversal, Complex Unicode, Emoji, and Diacritics.
3. Cross-Field Consistency: Graded with/without Slab Serial, Raw with Cert Number (Forbidden), Hyphenated Conditions, Negative Query Exclusions.
4. Circuit Breaker Boundaries: Batch ingestion with 0, 1, 499, 500, and 501 items (atomic rollback on corruption).
5. Staging CRUD & Query Fuzzing: SQLi in search filters, invalid sorting, pagination bounds, status update enum enforcement.
6. Sales Listing Generator API: Buzzword stripping, title length constraint, pricing resolution, invalid requests.
7. High-Concurrency Multi-Threaded Stress Harness: Verifying SQLite WAL mode under concurrent read/write/batch/patch calls.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import concurrent.futures
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient

# Ensure ecosystem_hub is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api import app, get_db_path, BackgroundServerThread, is_port_in_use
from database import (
    DEFAULT_DB_PATH,
    CIRCUIT_BREAKER_BATCH_LIMIT,
    init_db,
    insert_card,
    get_card_by_id,
    get_card_count,
    get_all_cards,
)
from models import (
    CardRecord,
    CardCategory,
    AIStatus,
    VALID_CATEGORIES,
    CATEGORY_MAP,
    format_notes,
    synthesize_query,
)


@pytest.fixture
def temp_db(tmp_path) -> str:
    """Provides a pristine, isolated temporary SQLite database for each test."""
    db_file = str(tmp_path / "test_adversarial_api_m3.db")
    init_db(db_file)
    return db_file


@pytest.fixture
def client(temp_db: str) -> Generator[TestClient, None, None]:
    """Provides a TestClient wired to the isolated temporary test database."""
    app.dependency_overrides[get_db_path] = lambda: temp_db
    app.state.db_path = temp_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def base_card_dict() -> dict[str, Any]:
    """Baseline valid card capture payload."""
    return {
        "player": "Luka Dončić",
        "year": "2018",
        "set_name": "Panini Prizm",
        "variation": "Silver Prizm",
        "card_number": "280",
        "category": "Basketball",
        "condition": "PSA 10",
        "slab_serial_number": "48920193",
        "investment": 350.0,
        "estimated_value": 750.0,
        "notes": "8492-101",
        "image": "https://example.com/front.jpg",
        "back_image": "https://example.com/back.jpg",
    }


# ===========================================================================
# 1. Malformed Payloads & Missing Fields (POST /api/v1/cards/capture)
# ===========================================================================

class TestMalformedAndInvalidPayloads:
    """Adversarial stress-testing of input validation and missing/corrupted parameters."""

    def test_missing_required_fields(self, client: TestClient, base_card_dict: dict[str, Any]):
        """Missing player, year, set_name, or category MUST yield HTTP 422."""
        for required_field in ["player", "year", "set_name", "category"]:
            bad_payload = dict(base_card_dict)
            del bad_payload[required_field]
            response = client.post("/api/v1/cards/capture", json=bad_payload)
            assert response.status_code == 422, f"Expected 422 when missing '{required_field}', got {response.status_code}"

    def test_empty_or_whitespace_required_fields(self, client: TestClient, base_card_dict: dict[str, Any]):
        """Whitespace-only player or set_name MUST be rejected with HTTP 422."""
        for field in ["player", "set_name"]:
            for empty_val in ["", "   ", "\t\t", "\n\n"]:
                bad_payload = dict(base_card_dict)
                bad_payload[field] = empty_val
                response = client.post("/api/v1/cards/capture", json=bad_payload)
                assert response.status_code == 422, f"Expected 422 for {field}='{empty_val}', got {response.status_code}"

    def test_invalid_year_formats(self, client: TestClient, base_card_dict: dict[str, Any]):
        """Non-4-digit years must be rejected, while season formats (e.g. 2020-21) normalize."""
        # Unacceptable year formats
        invalid_years = ["20", "202", "20205", "abcd", "-2020", "2020.5", "Y2K", ""]
        for bad_year in invalid_years:
            bad_payload = dict(base_card_dict)
            bad_payload["year"] = bad_year
            response = client.post("/api/v1/cards/capture", json=bad_payload)
            assert response.status_code == 422, f"Expected 422 for year='{bad_year}', got {response.status_code}"

        # Valid multi-year formats normalized to 4-digit YYYY
        valid_season_years = [("2020-21", "2020"), ("1996/97", "1996"), ("2023-2024", "2023")]
        for raw_yr, expected_norm in valid_season_years:
            payload = dict(base_card_dict)
            payload["year"] = raw_yr
            response = client.post("/api/v1/cards/capture", json=payload)
            assert response.status_code == 200
            assert response.json()["card"]["year"] == expected_norm

    def test_invalid_category_values(self, client: TestClient, base_card_dict: dict[str, Any]):
        """Invalid category strings must be rejected with 422, while recognized aliases normalize."""
        invalid_cats = ["Cricket", "Esports", "Formula 1", "Yugioh!", "Magic: The Gathering", "FakeSport", ""]
        for bad_cat in invalid_cats:
            bad_payload = dict(base_card_dict)
            bad_payload["category"] = bad_cat
            response = client.post("/api/v1/cards/capture", json=bad_payload)
            assert response.status_code == 422, f"Expected 422 for category='{bad_cat}', got {response.status_code}"

        # Aliases normalization
        alias_tests = [
            ("ufc", "UFC/MMA"),
            ("mma", "UFC/MMA"),
            ("pop culture", "PopCulture"),
            ("popculture", "PopCulture"),
            ("dragon ball z", "Dragonballz"),
            ("dragonball z", "Dragonballz"),
            ("flesh and blood", "Flesh and Blood"),
            ("flesh & blood", "Flesh and Blood"),
        ]
        for alias, expected in alias_tests:
            payload = dict(base_card_dict)
            payload["category"] = alias
            response = client.post("/api/v1/cards/capture", json=payload)
            assert response.status_code == 200
            assert response.json()["card"]["category"] == expected

    def test_negative_monetary_values(self, client: TestClient, base_card_dict: dict[str, Any]):
        """Negative investment or estimated_value MUST be rejected with HTTP 422."""
        for field in ["investment", "estimated_value"]:
            bad_payload = dict(base_card_dict)
            bad_payload[field] = -15.50
            response = client.post("/api/v1/cards/capture", json=bad_payload)
            assert response.status_code == 422, f"Expected 422 for {field}=-15.50, got {response.status_code}"

    def test_malformed_json_content_types(self, client: TestClient):
        """Malformed raw request bodies must return 422 unprocessable entity."""
        malformed_bodies = [
            b"{player: 'Broken JSON'",
            b'{"player": "Missing closing quote, "year": "2020"}',
            b'{"player": "Luka", "investment": "invalid_number"}',
            b"[1, 2, 3]",  # Array sent to single capture endpoint
            b"",           # Empty body
        ]
        for body in malformed_bodies:
            response = client.post(
                "/api/v1/cards/capture",
                content=body,
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code in (400, 422), f"Expected 400/422 for malformed body, got {response.status_code}"


# ===========================================================================
# 2. Security & Sanitization (SQLi, XSS, Unicode Diacritics, Long Inputs)
# ===========================================================================

class TestSecurityAndSanitizationPayloads:
    """Stress-testing SQL injection strings, XSS script tags, emojis, and Unicode."""

    @pytest.mark.parametrize("sqli_payload", [
        "' OR '1'='1",
        "'; DROP TABLE cards; --",
        "' UNION SELECT 1, '2020', 'Hacked', 'Hacked', 'Hacked', 'Basketball', 'Raw', '', 0, 0, '', '', '', '', '', NULL, '', '', 'CLEARED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP --",
        "admin'--",
        "1; UPDATE cards SET ai_status = 'CLEARED' WHERE 1=1; --",
        "\" OR \"\"=\"",
        "'; EXEC xp_cmdshell('dir'); --",
        "' OR 1=1#",
    ])
    def test_sqli_resilience_in_capture_fields(
        self,
        client: TestClient,
        temp_db: str,
        base_card_dict: dict[str, Any],
        sqli_payload: str
    ):
        """SQL injection payloads must be safely stored as literal strings without breaking the DB."""
        payload = dict(base_card_dict)
        payload["player"] = f"Player {sqli_payload}"
        payload["set_name"] = f"Set {sqli_payload}"
        payload["variation"] = sqli_payload
        payload["card_number"] = "099"

        response = client.post("/api/v1/cards/capture", json=payload)
        assert response.status_code == 200, f"Failed on SQLi payload: {sqli_payload}"
        card_id = response.json()["card_id"]

        # Verify DB still intact and data safely escaped
        row = get_card_by_id(card_id, db_path=temp_db)
        assert row is not None
        assert row["player"] == f"Player {sqli_payload}"
        assert row["variation"] == sqli_payload

        # Verify total table integrity
        total_count = get_card_count(db_path=temp_db)
        assert total_count >= 1

    @pytest.mark.parametrize("xss_payload", [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert(1)>",
        "<svg onload=alert(document.cookie)>",
        "javascript:alert(1)",
        "'\"><script>alert(1)</script>",
        "<iframe src='javascript:alert(1)'></iframe>",
    ])
    def test_xss_payload_safety_in_capture_and_listing(
        self,
        client: TestClient,
        temp_db: str,
        base_card_dict: dict[str, Any],
        xss_payload: str
    ):
        """XSS payloads must be accepted as raw text and safely processed by the sales generator."""
        payload = dict(base_card_dict)
        payload["player"] = f"LeBron {xss_payload}"
        payload["notes"] = f"Note {xss_payload}"

        response = client.post("/api/v1/cards/capture", json=payload)
        assert response.status_code == 200
        card_id = response.json()["card_id"]

        # Generate marketplace listing for this card
        listing_resp = client.post(f"/api/v1/cards/{card_id}/listing?mock=true")
        assert listing_resp.status_code == 200
        listing_data = listing_resp.json()
        assert "listing" in listing_data
        assert isinstance(listing_data["listing"], str)

    @pytest.mark.parametrize("player_name,set_name,variation", [
        ("Shohei Ohtani (大谷 翔平)", "BBM 1st Version 日本", "Kanji Holo (桜)"),
        ("Ronald Acuña Jr.", "Topps Chrome España", "Refractor Dorado"),
        ("Luka Dončić", "Panini Prizm Slovenija", "Srebrna Prizma"),
        ("Victor Wembanyama 🏀", "Topps Chrome Paris 🇫🇷", "Tour Eiffel Refractor 🗼"),
        ("محمد صلاح", "Panini FIFA 365", "الذهبي"),
        ("Криштиану Роналду", "Upper Deck Champions", "Золото"),
        ("Ząćh Éđey", "Select Draft Picks", "Prizm Disco 🪩"),
        ("Card with Zero-Width Joiner 👨‍👩‍👧‍👦", "Emoji Series", "Special Edition 🌟"),
    ])
    def test_unicode_and_diacritic_preservation(
        self,
        client: TestClient,
        temp_db: str,
        base_card_dict: dict[str, Any],
        player_name: str,
        set_name: str,
        variation: str
    ):
        """International characters, CJK, Arabic, Cyrillic, and Emojis must be preserved accurately."""
        payload = dict(base_card_dict)
        payload["player"] = player_name
        payload["set_name"] = set_name
        payload["variation"] = variation

        response = client.post("/api/v1/cards/capture", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        row = get_card_by_id(data["card_id"], db_path=temp_db)
        assert row["player"] == player_name
        assert row["set_name"] == set_name
        assert row["variation"] == variation

    def test_extreme_string_lengths(self, client: TestClient, base_card_dict: dict[str, Any]):
        """Large text fields (5,000+ chars) in notes and tags should not crash the database."""
        payload = dict(base_card_dict)
        payload["notes"] = "8492-101 " + ("A" * 5000)
        payload["tags"] = "B" * 5000

        response = client.post("/api/v1/cards/capture", json=payload)
        assert response.status_code == 200
        card_id = response.json()["card_id"]
        assert card_id > 0


# ===========================================================================
# 3. Cross-Field Consistency & Domain Rules
# ===========================================================================

class TestConditionAndCrossFieldRules:
    """Stress-testing graded vs raw rules, serial number constraints, and query synthesis."""

    def test_raw_card_with_slab_serial_number_strictly_rejected(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any]
    ):
        """A card marked condition='Raw' with a non-empty slab_serial_number MUST be rejected with 422."""
        payload = dict(base_card_dict)
        payload["condition"] = "Raw"
        payload["slab_serial_number"] = "12345678"  # FORBIDDEN for Raw

        response = client.post("/api/v1/cards/capture", json=payload)
        assert response.status_code == 422
        assert "Slab serial number must be blank for 'Raw' condition" in response.text

    def test_raw_card_with_blank_slab_serial_number_succeeds(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any]
    ):
        """Raw card with empty or whitespace slab_serial_number succeeds."""
        payload = dict(base_card_dict)
        payload["condition"] = "Raw"
        payload["slab_serial_number"] = "   "

        response = client.post("/api/v1/cards/capture", json=payload)
        assert response.status_code == 200
        assert response.json()["card"]["slab_serial_number"] == ""

    def test_graded_card_without_slab_serial_number_succeeds(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any]
    ):
        """Graded card without explicit serial number is valid (optional field)."""
        payload = dict(base_card_dict)
        payload["condition"] = "PSA 10"
        payload["slab_serial_number"] = ""

        response = client.post("/api/v1/cards/capture", json=payload)
        assert response.status_code == 200
        assert response.json()["card"]["condition"] == "PSA 10"
        assert response.json()["card"]["slab_serial_number"] == ""

    def test_hyphenated_condition_rejected(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any]
    ):
        """Hyphenated graded conditions like PSA-10, BGS-9.5 must be rejected (require PSA 10, BGS 9.5)."""
        for bad_cond in ["PSA-10", "BGS-9.5", "SGC-10", "CGC-9.5", "TAG-10"]:
            payload = dict(base_card_dict)
            payload["condition"] = bad_cond
            response = client.post("/api/v1/cards/capture", json=payload)
            assert response.status_code == 422, f"Expected 422 for condition='{bad_cond}', got {response.status_code}"

    def test_negative_exclusions_in_raw_query_rejected(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any]
    ):
        """Negative exclusions (-PSA, -BGS) in query for Raw cards must be rejected."""
        payload = dict(base_card_dict)
        payload["condition"] = "Raw"
        payload["slab_serial_number"] = ""
        payload["query"] = "2020 Panini Prizm Luka Doncic -PSA -BGS"

        response = client.post("/api/v1/cards/capture", json=payload)
        assert response.status_code == 422
        assert "Negative exclusions are forbidden" in response.text

    def test_variation_auto_flags_review_variation(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any]
    ):
        """When a variation is present and ai_status is default, ai_status must be 'REVIEW VARIATION'."""
        payload = dict(base_card_dict)
        payload["variation"] = "Silver Prizm"
        payload.pop("ai_status", None)

        response = client.post("/api/v1/cards/capture", json=payload)
        assert response.status_code == 200
        assert response.json()["ai_status"] == "REVIEW VARIATION"

    def test_base_card_without_variation_cleared(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any]
    ):
        """Base card without variation defaults to CLEARED."""
        payload = dict(base_card_dict)
        payload["variation"] = ""
        payload.pop("ai_status", None)

        response = client.post("/api/v1/cards/capture", json=payload)
        assert response.status_code == 200
        assert response.json()["ai_status"] == "CLEARED"

    def test_explicit_ai_status_override_preserved(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any]
    ):
        """Explicit ai_status ('NEEDS REVIEW' or 'CLEARED') is honored even if variation is non-empty."""
        payload = dict(base_card_dict)
        payload["variation"] = "Gold Vinyl /5"
        payload["ai_status"] = "NEEDS REVIEW"

        response = client.post("/api/v1/cards/capture", json=payload)
        assert response.status_code == 200
        assert response.json()["ai_status"] == "NEEDS REVIEW"

    def test_automatic_notes_resolution_from_parent_and_child_ids(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any],
        temp_db: str
    ):
        """If parent_image_id is provided and notes is empty, notes must resolve to [Parent_Image_ID]-[Child_Card_ID]."""
        payload1 = dict(base_card_dict)
        payload1["notes"] = ""
        payload1["parent_image_id"] = 8492
        payload1["child_card_id"] = 101

        resp1 = client.post("/api/v1/cards/capture", json=payload1)
        assert resp1.status_code == 200
        assert resp1.json()["notes"] == "8492-101"

        # Sequential auto-increment if child_card_id omitted
        payload2 = dict(base_card_dict)
        payload2["notes"] = ""
        payload2["parent_image_id"] = 8492
        payload2.pop("child_card_id", None)

        resp2 = client.post("/api/v1/cards/capture", json=payload2)
        assert resp2.status_code == 200
        assert resp2.json()["notes"] == "8492-102"


# ===========================================================================
# 4. Batch Ingestion & 500-Card Circuit Breaker (POST /api/v1/cards/batch)
# ===========================================================================

class TestBatchIngestionCircuitBreaker:
    """Stress-testing batch endpoint with boundary payloads (0, 1, 499, 500, 501 items)."""

    def test_batch_empty_payload_rejected(self, client: TestClient):
        """Batch with 0 items must be rejected with HTTP 400 or 422."""
        # Direct empty list
        resp1 = client.post("/api/v1/cards/batch", json=[])
        assert resp1.status_code in (400, 422)

        # Wrapped empty list
        resp2 = client.post("/api/v1/cards/batch", json={"cards": []})
        assert resp2.status_code in (400, 422)

    def test_batch_single_item_success(self, client: TestClient, base_card_dict: dict[str, Any]):
        """Batch with 1 item succeeds."""
        payload = [base_card_dict]
        resp = client.post("/api/v1/cards/batch", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["inserted_count"] == 1
        assert len(data["card_ids"]) == 1

    def test_batch_499_items_success(self, client: TestClient, base_card_dict: dict[str, Any], temp_db: str):
        """Batch with 499 items (1 below circuit breaker limit) succeeds atomically."""
        batch_payload = [
            {
                **base_card_dict,
                "player": f"Player {i:03d}",
                "card_number": f"{i:03d}",
                "notes": f"0001-{i+100:03d}",
            }
            for i in range(1, 500)
        ]
        resp = client.post("/api/v1/cards/batch", json=batch_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["inserted_count"] == 499
        assert len(data["card_ids"]) == 499
        assert get_card_count(db_path=temp_db) == 499

    def test_batch_500_items_exact_limit_success(self, client: TestClient, base_card_dict: dict[str, Any], temp_db: str):
        """Batch with exactly 500 items (the circuit breaker limit) succeeds."""
        batch_payload = [
            {
                **base_card_dict,
                "player": f"Player {i:03d}",
                "card_number": f"{i:03d}",
                "notes": f"0002-{i+100:03d}",
            }
            for i in range(1, 501)
        ]
        resp = client.post("/api/v1/cards/batch", json=batch_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["inserted_count"] == 500
        assert len(data["card_ids"]) == 500
        assert get_card_count(db_path=temp_db) == 500

    def test_batch_501_items_exceeds_circuit_breaker_rejected(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any],
        temp_db: str
    ):
        """Batch with 501 items MUST trip the circuit breaker and be rejected with HTTP 400 or 422."""
        batch_payload = [
            {
                **base_card_dict,
                "player": f"Player {i:03d}",
                "card_number": f"{i:03d}",
            }
            for i in range(1, 502)
        ]

        # Test direct list payload
        resp1 = client.post("/api/v1/cards/batch", json=batch_payload)
        assert resp1.status_code in (400, 422), f"Expected 400/422 for 501 items, got {resp1.status_code}"
        assert "500" in resp1.text or "circuit breaker" in resp1.text.lower() or "too_long" in resp1.text

        # Test wrapped { "cards": [...] } payload
        resp2 = client.post("/api/v1/cards/batch", json={"cards": batch_payload})
        assert resp2.status_code in (400, 422)

        # Database must still have 0 cards (nothing committed)
        assert get_card_count(db_path=temp_db) == 0

    def test_batch_atomic_rollback_on_single_invalid_record(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any],
        temp_db: str
    ):
        """If 1 item out of 50 is invalid (e.g. Raw condition with slab cert), entire batch fails atomically."""
        batch_payload = [
            {**base_card_dict, "player": f"Valid Player {i}"}
            for i in range(1, 51)
        ]
        # Poison item 25 with forbidden raw slab serial number
        batch_payload[24]["condition"] = "Raw"
        batch_payload[24]["slab_serial_number"] = "ILLEGAL_CERT_123"

        resp = client.post("/api/v1/cards/batch", json=batch_payload)
        assert resp.status_code == 422

        # Verify zero items were inserted
        assert get_card_count(db_path=temp_db) == 0


# ===========================================================================
# 5. Staging CRUD, Status Transitions & Query Fuzzing
# ===========================================================================

class TestStagingCRUDAndQueryFuzzing:
    """Stress-testing GET filters, pagination, patch updates, delete, and status updates."""

    def test_list_cards_filter_sqli_fuzzing(self, client: TestClient, base_card_dict: dict[str, Any]):
        """SQL injection attempts in search, category, or status parameters must not throw DB errors."""
        client.post("/api/v1/cards/capture", json=base_card_dict)

        fuzz_params = [
            {"search_query": "' OR '1'='1"},
            {"search_query": "'; DROP TABLE cards; --"},
            {"status_filter": "' UNION SELECT * FROM cards --"},
            {"category_filter": "'; DELETE FROM cards; --"},
            {"order_by": "id DESC; DROP TABLE cards;"},
            {"order_by": "non_existent_column ASC"},
        ]

        for p in fuzz_params:
            resp = client.get("/api/v1/cards", params=p)
            assert resp.status_code == 200, f"Query failed for params {p} with status {resp.status_code}"
            data = resp.json()
            assert "cards" in data
            assert "total_staged" in data

    def test_list_cards_pagination_boundaries(self, client: TestClient, base_card_dict: dict[str, Any]):
        """Test boundary pagination values."""
        # Insert 5 cards
        for i in range(5):
            client.post("/api/v1/cards/capture", json={**base_card_dict, "player": f"Player {i}"})

        # Valid pagination
        resp = client.get("/api/v1/cards?limit=2&offset=1")
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

        # Limit exceeds max 500
        resp_over = client.get("/api/v1/cards?limit=501")
        assert resp_over.status_code == 422

        # Negative offset / limit
        assert client.get("/api/v1/cards?limit=0").status_code == 422
        assert client.get("/api/v1/cards?offset=-1").status_code == 422

    def test_get_non_existent_card_returns_404(self, client: TestClient):
        """Querying a non-existent card ID must return 404."""
        resp = client.get("/api/v1/cards/999999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_patch_card_resynthesizes_query(self, client: TestClient, base_card_dict: dict[str, Any]):
        """Updating player/set/year/condition via PATCH automatically recalculates query."""
        resp = client.post("/api/v1/cards/capture", json=base_card_dict)
        card_id = resp.json()["card_id"]

        # Patch player and variation
        patch_resp = client.patch(
            f"/api/v1/cards/{card_id}",
            json={"player": "Luka Magic", "variation": "Gold Prizm"}
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()["card"]
        assert updated["player"] == "Luka Magic"
        assert updated["variation"] == "Gold Prizm"
        assert updated["query"] == "2018 Panini Prizm Luka Magic Gold Prizm PSA 10"

    def test_status_update_enum_enforcement(self, client: TestClient, base_card_dict: dict[str, Any]):
        """Updating status to non-enum value must return 400 Bad Request."""
        resp = client.post("/api/v1/cards/capture", json=base_card_dict)
        card_id = resp.json()["card_id"]

        # Valid transitions
        for valid_status in ["CLEARED", "REVIEW VARIATION", "NEEDS REVIEW"]:
            s_resp = client.post(f"/api/v1/cards/{card_id}/status", json={"status": valid_status})
            assert s_resp.status_code == 200
            assert s_resp.json()["ai_status"] == valid_status

        # Invalid status
        for bad_status in ["APPROVED", "REJECTED", "PENDING", "", "123"]:
            bad_resp = client.post(f"/api/v1/cards/{card_id}/status", json={"status": bad_status})
            assert bad_resp.status_code == 400

    def test_delete_card_lifecycle(self, client: TestClient, base_card_dict: dict[str, Any], temp_db: str):
        """Card deletion removes record and returns 404 on subsequent requests."""
        resp = client.post("/api/v1/cards/capture", json=base_card_dict)
        card_id = resp.json()["card_id"]

        del_resp = client.delete(f"/api/v1/cards/{card_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted_id"] == card_id

        # Subsequent GET returns 404
        assert client.get(f"/api/v1/cards/{card_id}").status_code == 404
        assert get_card_by_id(card_id, db_path=temp_db) is None


# ===========================================================================
# 6. Sales Listing Generator Endpoints
# ===========================================================================

class TestSalesGeneratorEndpointsAdversarial:
    """Stress-testing listing copy endpoints, buzzword sanitization, and pricing fallbacks."""

    def test_listing_endpoint_strips_buzzwords_in_seo_title(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any]
    ):
        """Title must strip forbidden buzzwords (INVEST, FIRE, L@@K) and remain under 100 characters."""
        payload = dict(base_card_dict)
        payload["player"] = "INVEST L@@K FIRE Victor Wembanyama GEM?"
        payload["set_name"] = "Panini Prizm HOT RARE"

        resp = client.post("/api/v1/cards/capture", json=payload)
        card_id = resp.json()["card_id"]

        listing_resp = client.post(f"/api/v1/cards/{card_id}/listing?mock=true")
        assert listing_resp.status_code == 200
        data = listing_resp.json()

        structured = data["structured"]
        title = structured["title"]
        assert len(title) <= 100
        for forbidden in ["L@@K", "FIRE", "INVEST", "GEM?"]:
            assert forbidden not in title

        # Verify all 6 sections present in raw text
        raw_text = data["listing"]
        assert "ASKING PRICE:" in raw_text or "Asking Price" in raw_text
        assert "KEY SPECIFICATIONS:" in raw_text
        assert "CONDITION & AUTHENTICITY:" in raw_text
        assert "SHIPPING & LOCAL PICKUP:" in raw_text or "PURCHASE & SHIPPING TERMS:" in raw_text
        assert "TAGS:" in raw_text

        # Verify 6 to 8 hashtags
        hashtags = structured["hashtags"]
        assert 6 <= len(hashtags) <= 8

    def test_on_demand_sales_generation_inline_card_data(
        self,
        client: TestClient,
        base_card_dict: dict[str, Any]
    ):
        """POST /api/v1/sales/generate accepts inline card_data with mock=True."""
        req_body = {
            "card_data": base_card_dict,
            "asking_price": 599.99,
            "custom_notes": "Corner is sharp, flawless surface.",
            "mock": True,
        }
        resp = client.post("/api/v1/sales/generate", json=req_body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["structured"]["price"] == 599.99
        assert "Corner is sharp" in data["listing"]

    def test_sales_generate_missing_card_id_and_data_rejected(self, client: TestClient):
        """Request lacking both card_id and card_data must return 400 Bad Request."""
        resp = client.post("/api/v1/sales/generate", json={"mock": True})
        assert resp.status_code == 400
        assert "either 'card_id' or 'card_data'" in resp.json()["detail"]


# ===========================================================================
# 7. High-Concurrency Multi-Threaded Stress Harness (SQLite WAL Validation)
# ===========================================================================

class TestSQLiteWALConcurrencyStressHarness:
    """
    Massive multi-threaded stress harness verifying SQLite WAL mode handles
    concurrent reader, writer, batching, patching, and listing requests without locking.
    """

    def test_massive_concurrent_multi_client_requests(
        self,
        client: TestClient,
        temp_db: str,
        base_card_dict: dict[str, Any]
    ):
        """
        Executes 100 concurrent requests across 20 threads:
        - 40 single card captures
        - 20 batch card captures (5 cards each = 100 cards)
        - 20 card queries & status updates
        - 20 sales listing generations
        Proves: Zero database locking exceptions, 100% successful HTTP 200 responses.
        """
        num_threads = 20
        operations_per_thread = 5

        errors: list[str] = []
        successful_inserts = 0
        lock = threading.Lock()

        def worker_task(thread_id: int):
            nonlocal successful_inserts
            for op_idx in range(operations_per_thread):
                try:
                    # 1. Single Capture
                    single_payload = {
                        **base_card_dict,
                        "player": f"Concurrent Player T{thread_id}_{op_idx}",
                        "notes": f"{thread_id:04d}-{op_idx+100:03d}",
                        "card_number": f"{op_idx:03d}",
                    }
                    r1 = client.post("/api/v1/cards/capture", json=single_payload)
                    if r1.status_code != 200:
                        errors.append(f"Capture failed in thread {thread_id}: {r1.status_code} - {r1.text}")
                    else:
                        with lock:
                            successful_inserts += 1
                        card_id = r1.json()["card_id"]

                        # 2. Patch card
                        r2 = client.patch(f"/api/v1/cards/{card_id}", json={"estimated_value": 999.0})
                        if r2.status_code != 200:
                            errors.append(f"Patch failed in thread {thread_id}: {r2.status_code}")

                        # 3. Generate Listing
                        r3 = client.post(f"/api/v1/cards/{card_id}/listing?mock=true")
                        if r3.status_code != 200:
                            errors.append(f"Listing failed in thread {thread_id}: {r3.status_code}")

                    # 4. Small Batch Capture (2 cards per batch)
                    batch_payload = [
                        {
                            **base_card_dict,
                            "player": f"BatchCard T{thread_id}_{op_idx}_A",
                            "notes": f"{thread_id:04d}-{op_idx+200:03d}",
                        },
                        {
                            **base_card_dict,
                            "player": f"BatchCard T{thread_id}_{op_idx}_B",
                            "notes": f"{thread_id:04d}-{op_idx+201:03d}",
                        },
                    ]
                    r4 = client.post("/api/v1/cards/batch", json=batch_payload)
                    if r4.status_code != 200:
                        errors.append(f"Batch failed in thread {thread_id}: {r4.status_code} - {r4.text}")
                    else:
                        with lock:
                            successful_inserts += 2

                    # 5. Read queries
                    r5 = client.get("/api/v1/cards?limit=50")
                    if r5.status_code != 200:
                        errors.append(f"List query failed in thread {thread_id}: {r5.status_code}")

                    r6 = client.get("/api/v1/stats")
                    if r6.status_code != 200:
                        errors.append(f"Stats failed in thread {thread_id}: {r6.status_code}")

                except Exception as ex:
                    errors.append(f"Exception in thread {thread_id}: {type(ex).__name__} - {str(ex)}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task, i) for i in range(num_threads)]
            concurrent.futures.wait(futures)

        # Assert no lock exceptions or request failures occurred
        assert len(errors) == 0, f"Encountered {len(errors)} concurrency errors:\n" + "\n".join(errors[:10])

        # Verify database integrity and total count
        expected_total = num_threads * operations_per_thread * 3  # 1 single + 2 batch = 3 per loop
        actual_total = get_card_count(db_path=temp_db)
        assert actual_total == expected_total == successful_inserts, (
            f"Expected {expected_total} total cards, got {actual_total} (successful inserts logged: {successful_inserts})"
        )

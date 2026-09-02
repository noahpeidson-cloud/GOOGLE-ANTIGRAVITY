"""
test_api_bridge.py - Deterministic Test Suite for FastAPI Ingestion API Bridge.
Validates Chrome Extension capture endpoint, batch processing, circuit breaker limits,
CORS headers, health status, CRUD staging operations, and cross-field error handling.
"""

import os
import tempfile
import pytest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient

from api import app, get_db_path, is_port_in_use, BackgroundServerThread
from database import init_db, get_card_by_id, get_card_count


@pytest.fixture
def temp_db():
    """Provides an isolated, clean temporary SQLite database for each test."""
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
def client(temp_db):
    """Provides a FastAPI TestClient wired to the isolated temporary test database."""
    app.dependency_overrides[get_db_path] = lambda: temp_db
    app.state.db_path = temp_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_card_payload():
    """Standard valid card payload from Chrome extension."""
    return {
        "player": "Anthony Edwards",
        "year": "2020",
        "set_name": "Panini Prizm",
        "variation": "Silver Prizm",
        "card_number": "258",
        "category": "Basketball",
        "condition": "Raw",
        "slab_serial_number": "",
        "investment": 150.0,
        "estimated_value": 275.0,
        "notes": "8492-101",
        "image": "https://example.com/front.jpg",
        "back_image": "https://example.com/back.jpg"
    }


# ===========================================================================
# Tier 1: Health & System Connectivity Tests
# ===========================================================================

class TestHealthEndpoint:
    """Validates /api/v1/health and /health endpoints and database connectivity status."""

    def test_health_endpoint_healthy(self, client, temp_db):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["database_path"] == temp_db
        assert data["total_cards"] == 0
        assert data["circuit_breaker"]["circuit_breaker_tripped"] is False
        assert data["circuit_breaker"]["total_staged"] == 0

    def test_health_root_alias(self, client, temp_db):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["total_cards"] == 0

    def test_health_endpoint_after_insert(self, client, sample_card_payload):
        client.post("/api/v1/cards/capture", json=sample_card_payload)
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["total_cards"] == 1
        assert data["total_investment"] == 150.0
        assert data["total_estimated_value"] == 275.0

    def test_health_endpoint_db_failure(self, client):
        app.dependency_overrides[get_db_path] = lambda: "Z:\\non_existent_folder_xyz\\portfolio.db"
        response = client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"


# ===========================================================================
# Tier 2: Single Card Capture Ingestion Tests
# ===========================================================================

class TestSingleCardCapture:
    """Validates POST /api/v1/cards/capture single item ingestion and constraints."""

    def test_capture_single_card_success(self, client, sample_card_payload, temp_db):
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["card_id"] == 1
        assert data["query"] == "2020 Panini Prizm Anthony Edwards Silver Prizm Raw"
        assert data["notes"] == "8492-101"
        assert data["ai_status"] == "REVIEW VARIATION"
        assert "card" in data
        assert data["card"]["player"] == "Anthony Edwards"

        row = get_card_by_id(1, db_path=temp_db)
        assert row is not None
        assert row["player"] == "Anthony Edwards"
        assert row["card_number"] == "258"

    def test_capture_preserves_leading_zeros(self, client, sample_card_payload, temp_db):
        sample_card_payload["card_number"] = "007"
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 200
        row = get_card_by_id(response.json()["card_id"], db_path=temp_db)
        assert row["card_number"] == "007"

    def test_capture_category_normalization_aliases(self, client, sample_card_payload, temp_db):
        sample_card_payload["category"] = "ufc"
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 200
        row = get_card_by_id(response.json()["card_id"], db_path=temp_db)
        assert row["category"] == "UFC/MMA"

        sample_card_payload["category"] = "pop culture"
        response2 = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response2.status_code == 200
        row2 = get_card_by_id(response2.json()["card_id"], db_path=temp_db)
        assert row2["category"] == "PopCulture"

    def test_capture_raw_condition_with_slab_serial_rejected(self, client, sample_card_payload):
        sample_card_payload["condition"] = "Raw"
        sample_card_payload["slab_serial_number"] = "12345678"
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 422
        assert "Slab serial number must be blank for 'Raw'" in response.text

    def test_capture_graded_condition_allows_slab_serial(self, client, sample_card_payload, temp_db):
        sample_card_payload["condition"] = "PSA 10"
        sample_card_payload["slab_serial_number"] = "98765432"
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 200
        row = get_card_by_id(response.json()["card_id"], db_path=temp_db)
        assert row["condition"] == "PSA 10"
        assert row["slab_serial_number"] == "98765432"

    def test_capture_invalid_category_rejected(self, client, sample_card_payload):
        sample_card_payload["category"] = "CoinCollecting"
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 422
        assert "Invalid category" in response.text

    def test_capture_invalid_year_rejected(self, client, sample_card_payload):
        sample_card_payload["year"] = "twenty-twenty"
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 422

    def test_capture_auto_flag_variation_review(self, client, sample_card_payload):
        sample_card_payload["variation"] = "Gold Vinyl /5"
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 200
        assert response.json()["ai_status"] == "REVIEW VARIATION"

    def test_capture_base_card_cleared_status(self, client, sample_card_payload):
        sample_card_payload["variation"] = ""
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 200
        assert response.json()["ai_status"] == "CLEARED"

    def test_capture_auto_note_resolution_with_parent_child_id(self, client, sample_card_payload):
        sample_card_payload["notes"] = ""
        sample_card_payload["parent_image_id"] = 42
        sample_card_payload["child_card_id"] = 105
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 200
        assert response.json()["notes"] == "0042-105"

    def test_capture_auto_note_resolution_sequential_child(self, client, sample_card_payload):
        sample_card_payload["notes"] = ""
        sample_card_payload["parent_image_id"] = 8492
        sample_card_payload.pop("child_card_id", None)
        response1 = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response1.status_code == 200
        assert response1.json()["notes"] == "8492-101"

        response2 = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response2.status_code == 200
        assert response2.json()["notes"] == "8492-102"


# ===========================================================================
# Tier 3: Batch Capture & Circuit Breaker Tests
# ===========================================================================

class TestBatchCardCapture:
    """Validates POST /api/v1/cards/batch multi-record ingestion."""

    def test_batch_capture_wrapped_object_success(self, client, sample_card_payload, temp_db):
        cards = []
        for i in range(5):
            c = dict(sample_card_payload)
            c["player"] = f"Player {i+1}"
            cards.append(c)

        response = client.post("/api/v1/cards/batch", json={"cards": cards})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["inserted_count"] == 5
        assert len(data["card_ids"]) == 5
        assert get_card_count(temp_db) == 5

    def test_batch_capture_raw_list_success(self, client, sample_card_payload, temp_db):
        cards = []
        for i in range(3):
            c = dict(sample_card_payload)
            c["player"] = f"List Player {i+1}"
            cards.append(c)

        response = client.post("/api/v1/cards/batch", json=cards)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["inserted_count"] == 3
        assert get_card_count(temp_db) == 3

    def test_batch_empty_rejected(self, client):
        response = client.post("/api/v1/cards/batch", json={"cards": []})
        assert response.status_code in (400, 422)

    def test_batch_circuit_breaker_over_500_rejected(self, client, sample_card_payload):
        cards = [dict(sample_card_payload) for _ in range(501)]
        response = client.post("/api/v1/cards/batch", json={"cards": cards})
        assert response.status_code in (400, 422)
        assert "500" in response.text or "too_long" in response.text or "at most" in response.text or "exceeds" in response.text

    def test_batch_atomic_rollback_on_invalid_record(self, client, sample_card_payload, temp_db):
        card1 = dict(sample_card_payload)
        card2_invalid = dict(sample_card_payload)
        card2_invalid["category"] = "InvalidCategoryXYZ"

        response = client.post("/api/v1/cards/batch", json={"cards": [card1, card2_invalid]})
        assert response.status_code == 422
        assert get_card_count(temp_db) == 0


# ===========================================================================
# Tier 4: Staging CRUD & Query Endpoints
# ===========================================================================

class TestStagingCRUD:
    """Validates list, get, patch, delete, status update, and stats endpoints."""

    def test_list_cards_and_filtering(self, client, sample_card_payload):
        c1 = dict(sample_card_payload, player="Luka Doncic", category="Basketball", variation="Silver")
        c2 = dict(sample_card_payload, player="Shohei Ohtani", category="Baseball", variation="")
        c3 = dict(sample_card_payload, player="Patrick Mahomes", category="Football", variation="")
        client.post("/api/v1/cards/capture", json=c1)
        client.post("/api/v1/cards/capture", json=c2)
        client.post("/api/v1/cards/capture", json=c3)

        resp = client.get("/api/v1/cards")
        assert resp.status_code == 200
        assert resp.json()["count"] == 3

        resp_cat = client.get("/api/v1/cards?category_filter=Baseball")
        assert resp_cat.status_code == 200
        assert resp_cat.json()["count"] == 1
        assert resp_cat.json()["cards"][0]["player"] == "Shohei Ohtani"

        resp_status = client.get("/api/v1/cards?status_filter=REVIEW VARIATION")
        assert resp_status.status_code == 200
        assert resp_status.json()["count"] == 1
        assert resp_status.json()["cards"][0]["player"] == "Luka Doncic"

        resp_search = client.get("/api/v1/cards?search_query=Mahomes")
        assert resp_search.status_code == 200
        assert resp_search.json()["count"] == 1
        assert resp_search.json()["cards"][0]["player"] == "Patrick Mahomes"

    def test_get_card_by_id_and_404(self, client, sample_card_payload):
        create_resp = client.post("/api/v1/cards/capture", json=sample_card_payload)
        card_id = create_resp.json()["card_id"]

        get_resp = client.get(f"/api/v1/cards/{card_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["card"]["id"] == card_id

        get_404 = client.get("/api/v1/cards/99999")
        assert get_404.status_code == 404

    def test_patch_card_and_query_resynthesis(self, client, sample_card_payload):
        create_resp = client.post("/api/v1/cards/capture", json=sample_card_payload)
        card_id = create_resp.json()["card_id"]

        patch_resp = client.patch(
            f"/api/v1/cards/{card_id}",
            json={"player": "Anthony Edwards Jr.", "estimated_value": 350.0}
        )
        assert patch_resp.status_code == 200
        card = patch_resp.json()["card"]
        assert card["player"] == "Anthony Edwards Jr."
        assert card["estimated_value"] == 350.0
        assert "Anthony Edwards Jr." in card["query"]

        patch_404 = client.patch("/api/v1/cards/99999", json={"player": "Ghost"})
        assert patch_404.status_code == 404

    def test_delete_card(self, client, sample_card_payload):
        create_resp = client.post("/api/v1/cards/capture", json=sample_card_payload)
        card_id = create_resp.json()["card_id"]

        del_resp = client.delete(f"/api/v1/cards/{card_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted_id"] == card_id

        assert client.get(f"/api/v1/cards/{card_id}").status_code == 404
        assert client.delete(f"/api/v1/cards/{card_id}").status_code == 404

    def test_update_card_status(self, client, sample_card_payload):
        create_resp = client.post("/api/v1/cards/capture", json=sample_card_payload)
        card_id = create_resp.json()["card_id"]

        status_resp = client.post(f"/api/v1/cards/{card_id}/status", json={"status": "CLEARED"})
        assert status_resp.status_code == 200
        assert status_resp.json()["ai_status"] == "CLEARED"

        bad_status = client.post(f"/api/v1/cards/{card_id}/status", json={"status": "INVALID_STATUS_CODE"})
        assert bad_status.status_code == 400

    def test_stats_and_circuit_breaker_endpoints(self, client, sample_card_payload):
        client.post("/api/v1/cards/capture", json=sample_card_payload)

        stats_resp = client.get("/api/v1/stats")
        assert stats_resp.status_code == 200
        assert stats_resp.json()["stats"]["total_cards"] == 1

        cb_resp = client.get("/api/v1/circuit-breaker")
        assert cb_resp.status_code == 200
        assert cb_resp.json()["circuit_breaker"]["total_staged"] == 1
        assert cb_resp.json()["circuit_breaker"]["circuit_breaker_tripped"] is False

    def test_clear_staging_endpoint(self, client, sample_card_payload, temp_db):
        client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert get_card_count(temp_db) == 1

        clear_resp = client.post("/api/v1/cards/staging/clear")
        assert clear_resp.status_code == 200
        assert clear_resp.json()["deleted_count"] == 1
        assert get_card_count(temp_db) == 0


# ===========================================================================
# Tier 5: Sales Generator & Monetization Integration
# ===========================================================================

class TestSalesGeneratorEndpoints:
    """Validates Facebook Marketplace copy generation endpoints."""

    def test_card_id_listing_generation(self, client, sample_card_payload):
        create_resp = client.post("/api/v1/cards/capture", json=sample_card_payload)
        card_id = create_resp.json()["card_id"]

        resp = client.post(f"/api/v1/cards/{card_id}/listing?asking_price=299.99&mock=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["card_id"] == card_id
        assert "299.99" in data["listing"]
        assert "KEY SPECIFICATIONS" in data["listing"]
        assert len(data["structured"]["hashtags"]) >= 6

    def test_on_demand_sales_generate_with_card_id(self, client, sample_card_payload):
        create_resp = client.post("/api/v1/cards/capture", json=sample_card_payload)
        card_id = create_resp.json()["card_id"]

        payload = {
            "card_id": card_id,
            "asking_price": 310.0,
            "mock": True,
            "custom_notes": "Mint condition"
        }
        resp = client.post("/api/v1/sales/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "310.00" in data["listing"]

    def test_on_demand_sales_generate_with_card_data(self, client, sample_card_payload):
        payload = {
            "card_data": sample_card_payload,
            "asking_price": 280.0,
            "mock": True
        }
        resp = client.post("/api/v1/sales/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "280.00" in data["listing"]


# ===========================================================================
# Tier 6: CORS & Concurrency Utilities
# ===========================================================================

class TestCORSAndRunner:
    """Validates CORS configurations and background server runner."""

    def test_cors_headers_chrome_extension(self, client):
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "chrome-extension://abcdefghijklmnop",
                "Access-Control-Request-Method": "GET"
            }
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_port_in_use_checker(self):
        assert isinstance(is_port_in_use(59999), bool)

    def test_background_server_thread_lifecycle(self, temp_db):
        server = BackgroundServerThread(app, host="127.0.0.1", port=8002, db_path=temp_db)
        assert server.daemon is True
        assert server.port == 8002

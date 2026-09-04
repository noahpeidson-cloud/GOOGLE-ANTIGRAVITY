"""
test_e2e_m3.py - End-to-End Integration and Stress Test Suite for Milestone 3.
Tests golden path Chrome Extension ingestion -> SQLite -> Sales copy generation,
concurrent multi-threaded stress testing in SQLite WAL mode, and server runner lifecycle.
"""

import os
import tempfile
import concurrent.futures
import pytest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient

from api import app, get_db_path, start_api_server_thread, is_port_in_use
from database import init_db, get_card_by_id, get_card_count, insert_cards_batch
from models import CardRecord


@pytest.fixture
def temp_db():
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
    app.dependency_overrides[get_db_path] = lambda: temp_db
    app.state.db_path = temp_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestE2EGoldenPath:
    """Tests complete lifecycle: Capture -> SQLite Staging -> Marketplace Listing."""

    def test_full_lifecycle_graded_card(self, client, temp_db):
        capture_payload = {
            "player": "Luka Doncic",
            "year": "2018",
            "set_name": "Panini Prizm",
            "variation": "Silver Prizm",
            "card_number": "280",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "48192041",
            "investment": 750.0,
            "estimated_value": 1400.0,
            "parent_image_id": 8492,
            "child_card_id": 105,
        }

        # 1. Ingest via API
        resp = client.post("/api/v1/cards/capture", json=capture_payload)
        assert resp.status_code == 200
        data = resp.json()
        card_id = data["card_id"]
        assert data["notes"] == "8492-105"
        assert data["query"] == "2018 Panini Prizm Luka Doncic Silver Prizm PSA 10"

        # 2. Verify Database Record
        db_row = get_card_by_id(card_id, db_path=temp_db)
        assert db_row is not None
        assert db_row["player"] == "Luka Doncic"
        assert db_row["condition"] == "PSA 10"
        assert db_row["slab_serial_number"] == "48192041"

        # 3. Generate Sales Copy
        listing_resp = client.post(f"/api/v1/cards/{card_id}/listing?asking_price=1450.0&mock=true")
        assert listing_resp.status_code == 200
        listing_data = listing_resp.json()
        listing_text = listing_data["listing"]

        assert "?? ASKING PRICE: $1,450.00" in listing_text
        assert "48192041" in listing_text
        assert "PSA 10" in listing_text
        assert 6 <= len(listing_data["structured"]["hashtags"]) <= 8


class TestE2EMultiThreadedConcurrency:
    """Stress tests concurrent reads, writes, and sales generation under SQLite WAL mode."""

    def test_concurrent_api_operations(self, client, temp_db):
        num_threads = 20
        num_cards_per_thread = 5

        def worker_task(thread_id: int):
            for i in range(num_cards_per_thread):
                payload = {
                    "player": f"Worker {thread_id} Athlete {i}",
                    "year": "2021",
                    "set_name": "Topps Chrome",
                    "variation": f"Refractor {i}",
                    "card_number": f"{i:03d}",
                    "category": "Baseball",
                    "condition": "Raw",
                    "investment": 20.0 + i,
                    "estimated_value": 50.0 + i,
                    "parent_image_id": 9000 + thread_id,
                }
                r = client.post("/api/v1/cards/capture", json=payload)
                assert r.status_code == 200
                cid = r.json()["card_id"]

                # Concurrently generate listing
                list_r = client.post(f"/api/v1/cards/{cid}/listing?mock=true")
                assert list_r.status_code == 200

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task, tid) for tid in range(num_threads)]
            for fut in concurrent.futures.as_completed(futures):
                fut.result()

        total_cards = get_card_count(temp_db)
        assert total_cards == num_threads * num_cards_per_thread


class TestServerRunnerPortLifecycle:
    """Validates server runner socket check and lifecycle helpers."""

    def test_port_helper_lifecycle(self, temp_db):
        # Verify port check is callable and returns bool
        port_open = is_port_in_use(58888)
        assert isinstance(port_open, bool)

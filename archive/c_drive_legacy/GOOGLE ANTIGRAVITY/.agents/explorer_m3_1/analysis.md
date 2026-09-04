# Technical Exploration & Architecture Analysis: API Bridge (`api.py`) & Tests (`test_api_bridge.py`)

**Milestone**: Milestone 3 - API Bridge & Sales Listing Generator  
**Agent**: `teamwork_preview_explorer` (`explorer_m3_1`)  
**Working Directory**: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m3_1`  
**Target Code Directory**: `g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub`  
**Parent Conversation ID**: `0c586af6-e90b-4330-8029-7be97c7c607c`  

---

## 1. Executive Summary

This document provides the complete architectural design, API specifications, and deterministic test blueprint for the **API Bridge module (`api.py`)** and its test suite (**`tests/test_api_bridge.py`**).

The API Bridge enables real-time ingestion from external clients—primarily a Chrome Extension capturing eBay/MySlabs listings—as well as comprehensive staging management for the central ecosystem hub. It interfaces directly with the SQLite engine (`database.py`) and schema validators (`models.py`), enforcing the 21-variable standard, query calculation, category normalization, automatic `[Parent_Image_ID]-[Child_Card_ID]` tracking note generation, 500-card batch circuit breaker controls, and cross-origin resource sharing (CORS) for `chrome-extension://*` and local environments.

---

## 2. Environment & Dependency Survey

1. **Python Environment**:
   - Python 3.13 on Windows x64.
   - `fastapi` version 0.141.1 installed and operational.
   - `httpx` version 0.28.1 installed and operational (for `fastapi.testclient.TestClient`).
   - `pydantic` version 2.13.4 installed and operational.
   - `uvicorn` installed and operational.
   - `pytest` suite: 475 existing tests pass for Milestones 1 and 2.

2. **Existing Domain Codebase**:
   - `models.py`:
     - `CardRecord`: Master 21-variable schema enforcing category constraints (22 categories), year validation, raw vs graded slab rules (`slab_serial_number == ""` for Raw), query calculation (`synthesize_query`), and auto-review flags (`variation != ""` $\rightarrow$ `REVIEW VARIATION`).
     - `CardCaptureRequest`: Standard ingestion schema.
     - `CardBatchCreate`: Batch model with 500-card circuit breaker.
     - `CardUpdate`: Partial update schema.
     - `format_notes(parent_image_id, child_card_id)`: Formats `0000-000` tracking string.
   - `database.py`:
     - SQLite WAL mode connection pool (`get_db_connection`).
     - `insert_card`, `insert_cards_batch`, `get_card_by_id`, `get_all_cards`, `update_card`, `update_card_status`, `delete_card`.
     - `get_summary_stats`, `check_circuit_breaker`, `get_next_child_id`, `clear_staging_table`.
     - `capture_card_from_api(payload, db_path)`.

---

## 3. Architecture Specification for `api.py`

### 3.1 Application Lifespan & Dependency Injection

- **Database Path Resolution**:
  ```python
  def get_db_path() -> str:
      """Returns active SQLite database path, supporting environment override or app dependency overrides."""
      return os.environ.get("PORTFOLIO_DB_PATH", DEFAULT_DB_PATH)
  ```
  This allows tests to inject isolated temporary SQLite databases seamlessly via `app.dependency_overrides[get_db_path] = lambda: temp_db_path`.

- **Lifespan Startup**:
  Initializes database schema and indexes on application boot using `init_db(get_db_path())`.

### 3.2 CORS Middleware Configuration

- Chrome Extensions run from origins formatted like `chrome-extension://<extension_id>`.
- Local frontends run from `http://localhost:<port>` or `http://127.0.0.1:<port>`.
- Starlette `CORSMiddleware` regex configuration:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origin_regex=r"^(chrome-extension://.*|http://(localhost|127\.0\.0\.1)(:\d+)?)$",
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```

### 3.3 Extended Ingestion Request Schema

To accommodate Chrome Extension payloads that supply `parent_image_id` and optional `child_card_id`, `api.py` introduces `ExtendedCardCaptureRequest`:

```python
class ExtendedCardCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="allow", use_enum_values=True, str_strip_whitespace=True)

    player: str = Field(..., min_length=1, description="Player or character name")
    year: str = Field(..., min_length=4, description="4-digit year (YYYY)")
    set_name: str = Field(..., min_length=1, description="Set manufacturer and line")
    variation: str = Field(default="", description="Parallel/foil variation")
    card_number: str = Field(default="", description="Printed card number (preserves leading zeroes)")
    category: str = Field(..., description="Card category (one of 22 valid categories or alias)")
    condition: str = Field(default="Raw", description="'Raw' or graded syntax (e.g. 'PSA 10')")
    slab_serial_number: str = Field(default="", description="Graded certification number")
    investment: float = Field(default=0.0, ge=0.0, description="Purchase cost basis")
    estimated_value: float = Field(default=0.0, ge=0.0, description="Current market comp estimate")
    notes: str = Field(default="", description="Tracking format [Parent_Image_ID]-[Child_Card_ID]")
    parent_image_id: Optional[Union[int, str]] = Field(default=None, description="Optional parent image ID for tracking")
    child_card_id: Optional[Union[int, str]] = Field(default=None, description="Optional child card ID for tracking")
    image: str = Field(default="", description="Front image URL or path")
    back_image: str = Field(default="", description="Back image URL or path")
    date_purchased: Optional[str] = Field(default=None, description="Purchase date (MM/DD/YYYY)")
    tags: str = Field(default="", description="Tags")
    ladder_id: str = Field(default="", description="Card Ladder sync identifier")
    ai_status: Optional[str] = Field(default=None, description="Optional explicit AI status")
```

### 3.4 Ingestion Endpoints Matrix

| HTTP Method | Path | Request Body | Response Body | HTTP Codes | Description |
|---|---|---|---|---|---|
| `POST` | `/api/v1/cards/capture` | `ExtendedCardCaptureRequest` | `CaptureResponse` | 200, 422, 500 | Captures single card, calculates query, formats parent-child tracking notes, persists to SQLite. |
| `POST` | `/api/v1/cards/batch` | `CardBatchRequest` or `list[ExtendedCardCaptureRequest]` | `BatchCaptureResponse` | 200, 400, 422, 500 | Atomically captures up to 500 cards in a single transaction. Enforces circuit breaker limit. |
| `GET` | `/api/v1/health` | None | `HealthResponse` | 200, 503 | Returns database connection state, card count, summary metrics, and circuit breaker status. |
| `GET` | `/api/v1/cards` | Query params (`status_filter`, `category_filter`, `search_query`, `limit`, `offset`, `order_by`) | `dict` (`status`, `count`, `total_staged`, `cards`) | 200, 500 | Queries staged cards with dynamic filtering and pagination. |
| `GET` | `/api/v1/cards/{card_id}` | Path param `card_id` | `dict` (`status`, `card`) | 200, 404 | Retrieves single card by ID. |
| `PATCH` | `/api/v1/cards/{card_id}` | `CardUpdate` | `dict` (`status`, `card`) | 200, 404, 422 | Partial update of card fields with query recalculation. |
| `DELETE` | `/api/v1/cards/{card_id}` | Path param `card_id` | `dict` (`status`, `deleted_id`) | 200, 404 | Deletes single card. |
| `POST` | `/api/v1/cards/{card_id}/status` | `CardStatusUpdateRequest` | `dict` (`status`, `card_id`, `ai_status`) | 200, 400, 404 | Updates `ai_status` (`CLEARED`, `REVIEW VARIATION`, `NEEDS REVIEW`). |
| `GET` | `/api/v1/stats` | None | `dict` (`status`, `stats`) | 200 | Returns portfolio summary metrics. |
| `POST` | `/api/v1/cards/staging/clear` | None | `dict` (`status`, `deleted_count`) | 200 | Deletes all records from the staging table. |

---

## 4. Proposed Production Implementation: `sports_cards/ecosystem_hub/api.py`

```python
"""
api.py - FastAPI Application & Ingestion API Bridge for Sports Card Ecosystem Hub.
Handles incoming card captures from Chrome Extension and external clients,
enforces the 21-variable schema, calculates query and tracking notes,
and provides full CRUD, batch ingestion, and health monitoring endpoints.
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, Path, Body, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from models import (
    CardRecord,
    CardUpdate,
    AIStatus,
    CardCategory,
    CardCaptureRequest,
    format_notes,
    synthesize_query,
)
from database import (
    DEFAULT_DB_PATH,
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
)

# ---------------------------------------------------------------------------
# Configuration & Dependencies
# ---------------------------------------------------------------------------

def get_db_path() -> str:
    """
    Dependency returning the active SQLite database path.
    Supports override via PORTFOLIO_DB_PATH environment variable or FastAPI dependency override.
    """
    return os.environ.get("PORTFOLIO_DB_PATH", DEFAULT_DB_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to ensure database initialization on startup."""
    active_db = get_db_path()
    init_db(active_db)
    yield


# ---------------------------------------------------------------------------
# Extended Pydantic Schemas for API Bridge
# ---------------------------------------------------------------------------

class ExtendedCardCaptureRequest(BaseModel):
    """
    Extended request schema for Chrome Extension capture payloads.
    Permits optional parent_image_id and child_card_id for automatic notes resolution.
    """
    model_config = ConfigDict(extra="allow", use_enum_values=True, str_strip_whitespace=True)

    player: str = Field(..., min_length=1, description="Player or character name")
    year: str = Field(..., min_length=4, description="4-digit year (YYYY)")
    set_name: str = Field(..., min_length=1, description="Set manufacturer and line")
    variation: str = Field(default="", description="Parallel/foil variation")
    card_number: str = Field(default="", description="Printed card number (preserves leading zeroes)")
    category: str = Field(..., description="Card category (one of 22 valid categories or alias)")
    condition: str = Field(default="Raw", description="'Raw' or graded syntax (e.g. 'PSA 10')")
    slab_serial_number: str = Field(default="", description="Graded certification number")
    investment: float = Field(default=0.0, ge=0.0, description="Purchase cost basis")
    estimated_value: float = Field(default=0.0, ge=0.0, description="Current market comp estimate")
    notes: str = Field(default="", description="Tracking format [Parent_Image_ID]-[Child_Card_ID]")
    parent_image_id: Optional[Union[int, str]] = Field(default=None, description="Optional parent image ID for tracking")
    child_card_id: Optional[Union[int, str]] = Field(default=None, description="Optional child card ID for tracking")
    image: str = Field(default="", description="Front image URL or path")
    back_image: str = Field(default="", description="Back image URL or path")
    date_purchased: Optional[str] = Field(default=None, description="Purchase date (MM/DD/YYYY)")
    tags: str = Field(default="", description="Tags")
    ladder_id: str = Field(default="", description="Card Ladder sync identifier")
    ai_status: Optional[str] = Field(default=None, description="Optional explicit AI status")


class CardBatchRequest(BaseModel):
    """Batch ingestion request payload wrapper."""
    cards: list[ExtendedCardCaptureRequest] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of card capture objects (up to 500 items)"
    )


class CardStatusUpdateRequest(BaseModel):
    """Payload for updating AI review status."""
    status: str = Field(..., description="New AI status ('CLEARED', 'REVIEW VARIATION', 'NEEDS REVIEW')")


class CaptureResponse(BaseModel):
    """Standard success response for single card capture."""
    status: str = "success"
    card_id: int
    query: str
    notes: str
    ai_status: str


class BatchCaptureResponse(BaseModel):
    """Standard success response for batch card capture."""
    status: str = "success"
    inserted_count: int
    card_ids: list[int]
    message: str


class HealthResponse(BaseModel):
    """System health and database connectivity response."""
    status: str
    database: str
    database_path: str
    total_cards: int
    total_investment: float
    total_estimated_value: float
    circuit_breaker: dict[str, Any]
    version: str = "1.0.0"


# ---------------------------------------------------------------------------
# FastAPI Application Factory / Setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Sports Card Ecosystem Hub - API Bridge",
    description="FastAPI Bridge for Chrome Extension Ingestion and Staging Management",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS Middleware for Chrome Extension and local environments
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome-extension://.*|http://(localhost|127\.0\.0\.1)(:\d+)?)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper Utilities
# ---------------------------------------------------------------------------

def _prepare_card_record(
    payload: ExtendedCardCaptureRequest | dict[str, Any],
    db_path: str
) -> CardRecord:
    """
    Transforms an incoming capture request into a validated CardRecord.
    Resolves parent/child tracking notes if parent_image_id is supplied and notes is empty.
    """
    data = payload.model_dump() if isinstance(payload, BaseModel) else dict(payload)

    # Resolve tracking notes from parent/child IDs if notes is not explicitly provided
    parent_id = data.pop("parent_image_id", None)
    child_id = data.pop("child_card_id", None)

    if not data.get("notes") and parent_id is not None:
        if child_id is not None and str(child_id).strip():
            data["notes"] = format_notes(parent_id, child_id)
        else:
            next_child = get_next_child_id(parent_id, db_path=db_path)
            data["notes"] = format_notes(parent_id, next_child)

    # Clean None values for optional date_purchased/ai_status
    if data.get("date_purchased") is None:
        data.pop("date_purchased", None)
    if data.get("ai_status") is None:
        data.pop("ai_status", None)

    # CardRecord validator performs cross-field validation, query synthesis, category normalization
    try:
        return CardRecord(**data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Card validation error: {str(e)}"
        ) from e


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="System Health & Database Connectivity"
)
def get_health(db_path: str = Depends(get_db_path)) -> HealthResponse:
    """
    Health status endpoint returning SQLite database connectivity, total cards,
    summary stats, and circuit breaker status.
    """
    try:
        init_db(db_path)
        stats = get_summary_stats(db_path)
        cb = check_circuit_breaker(db_path)
        return HealthResponse(
            status="healthy",
            database="connected",
            database_path=db_path,
            total_cards=stats["total_cards"],
            total_investment=stats["total_investment"],
            total_estimated_value=stats["total_estimated_value"],
            circuit_breaker=cb,
            version="1.0.0",
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "database_path": db_path,
                "error": str(e),
                "version": "1.0.0",
            },
        )


@app.post(
    "/api/v1/cards/capture",
    response_model=CaptureResponse,
    status_code=status.HTTP_200_OK,
    tags=["Ingestion"],
    summary="Capture Single Card from Chrome Extension"
)
def capture_card(
    payload: ExtendedCardCaptureRequest,
    db_path: str = Depends(get_db_path)
) -> CaptureResponse:
    """
    Captures a single card payload from Chrome Extension, validates 21 variables,
    synthesizes query, formats tracking notes, persists to SQLite, and returns record metadata.
    """
    record = _prepare_card_record(payload, db_path=db_path)
    card_id = insert_card(record, db_path=db_path)
    inserted = get_card_by_id(card_id, db_path=db_path)

    if not inserted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve newly inserted card from database"
        )

    return CaptureResponse(
        status="success",
        card_id=card_id,
        query=inserted["query"],
        notes=inserted["notes"],
        ai_status=inserted["ai_status"],
    )


@app.post(
    "/api/v1/cards/batch",
    response_model=BatchCaptureResponse,
    status_code=status.HTTP_200_OK,
    tags=["Ingestion"],
    summary="Batch Capture Cards (up to 500)"
)
def capture_cards_batch(
    payload: Union[CardBatchRequest, list[ExtendedCardCaptureRequest]] = Body(...),
    db_path: str = Depends(get_db_path)
) -> BatchCaptureResponse:
    """
    Batch captures up to 500 cards in an atomic transaction.
    Accepts direct JSON list or wrapped { 'cards': [...] } object.
    Enforces circuit breaker maximum limit of 500 items.
    """
    raw_cards: list[ExtendedCardCaptureRequest] = (
        payload.cards if isinstance(payload, CardBatchRequest) else payload
    )

    if not raw_cards:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch cannot be empty"
        )

    if len(raw_cards) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size ({len(raw_cards)}) exceeds maximum circuit breaker limit of 500 cards"
        )

    # Validate all records before database transaction
    validated_records: list[CardRecord] = []
    for item in raw_cards:
        rec = _prepare_card_record(item, db_path=db_path)
        validated_records.append(rec)

    try:
        inserted_ids = insert_cards_batch(validated_records, db_path=db_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch insertion failed: {str(e)}"
        ) from e

    return BatchCaptureResponse(
        status="success",
        inserted_count=len(inserted_ids),
        card_ids=inserted_ids,
        message=f"Successfully captured {len(inserted_ids)} cards",
    )


@app.get(
    "/api/v1/cards",
    tags=["Staging"],
    summary="Query Staged Cards with Filters"
)
def list_staged_cards(
    status_filter: Optional[str] = Query(None, description="Filter by ai_status (CLEARED, REVIEW VARIATION, NEEDS REVIEW, ALL)"),
    category_filter: Optional[str] = Query(None, description="Filter by category"),
    search_query: Optional[str] = Query(None, description="Free text search"),
    limit: int = Query(500, ge=1, le=500, description="Max cards to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    order_by: str = Query("id DESC", description="Sort ordering"),
    db_path: str = Depends(get_db_path)
) -> dict[str, Any]:
    """Retrieves cards from staging with optional filters and pagination."""
    cards = get_all_cards(
        status_filter=status_filter,
        category_filter=category_filter,
        search_query=search_query,
        limit=limit,
        offset=offset,
        order_by=order_by,
        db_path=db_path
    )
    total_count = get_card_count(db_path=db_path)
    return {
        "status": "success",
        "count": len(cards),
        "total_staged": total_count,
        "cards": cards,
    }


@app.get(
    "/api/v1/cards/{card_id}",
    tags=["Staging"],
    summary="Get Single Card by ID"
)
def get_card_endpoint(
    card_id: int = Path(..., ge=1, description="Integer card ID"),
    db_path: str = Depends(get_db_path)
) -> dict[str, Any]:
    """Retrieves a single card by ID."""
    card = get_card_by_id(card_id, db_path=db_path)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card with ID {card_id} not found"
        )
    return {
        "status": "success",
        "card": card,
    }


@app.patch(
    "/api/v1/cards/{card_id}",
    tags=["Staging"],
    summary="Update Card Fields"
)
def patch_card_endpoint(
    card_id: int = Path(..., ge=1, description="Integer card ID"),
    updates: CardUpdate = Body(..., description="Partial card update fields"),
    db_path: str = Depends(get_db_path)
) -> dict[str, Any]:
    """Updates fields on an existing card record and re-synthesizes query if necessary."""
    try:
        success = update_card(card_id, updates, db_path=db_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid update data: {str(e)}"
        ) from e

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card with ID {card_id} not found"
        )

    updated_card = get_card_by_id(card_id, db_path=db_path)
    return {
        "status": "success",
        "card": updated_card,
    }


@app.delete(
    "/api/v1/cards/{card_id}",
    tags=["Staging"],
    summary="Delete Card"
)
def delete_card_endpoint(
    card_id: int = Path(..., ge=1, description="Integer card ID"),
    db_path: str = Depends(get_db_path)
) -> dict[str, Any]:
    """Deletes a card record from the database."""
    success = delete_card(card_id, db_path=db_path)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card with ID {card_id} not found"
        )
    return {
        "status": "success",
        "deleted_id": card_id,
    }


@app.post(
    "/api/v1/cards/{card_id}/status",
    tags=["Staging"],
    summary="Update AI Review Status"
)
def update_status_endpoint(
    card_id: int = Path(..., ge=1, description="Integer card ID"),
    payload: CardStatusUpdateRequest = Body(...),
    db_path: str = Depends(get_db_path)
) -> dict[str, Any]:
    """Updates the AI review status of a staged card."""
    try:
        valid_status = AIStatus(payload.status).value
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid AI status '{payload.status}'. Must be one of: {[s.value for s in AIStatus]}"
        )

    success = update_card_status(card_id, valid_status, db_path=db_path)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card with ID {card_id} not found"
        )
    return {
        "status": "success",
        "card_id": card_id,
        "ai_status": valid_status,
    }


@app.get(
    "/api/v1/stats",
    tags=["Metrics"],
    summary="Get Aggregated Summary Metrics"
)
def get_stats_endpoint(db_path: str = Depends(get_db_path)) -> dict[str, Any]:
    """Returns aggregated summary metrics across the staged portfolio."""
    stats = get_summary_stats(db_path=db_path)
    return {
        "status": "success",
        "stats": stats,
    }


@app.post(
    "/api/v1/cards/staging/clear",
    tags=["Staging"],
    summary="Clear All Staged Cards"
)
def clear_staging_endpoint(db_path: str = Depends(get_db_path)) -> dict[str, Any]:
    """Clears all records from the cards staging table."""
    deleted_count = clear_staging_table(db_path=db_path)
    return {
        "status": "success",
        "deleted_count": deleted_count,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
```

---

## 5. Proposed Test Suite Implementation: `sports_cards/ecosystem_hub/tests/test_api_bridge.py`

```python
"""
test_api_bridge.py - Deterministic Test Suite for FastAPI Ingestion API Bridge.
Validates Chrome Extension capture endpoint, batch processing, circuit breaker limits,
CORS middleware, health status, CRUD staging operations, and cross-field error handling.
"""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from api import app, get_db_path
from database import init_db, get_card_by_id, get_card_count


@pytest.fixture
def temp_db():
    """Provides an isolated, clean temporary SQLite database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    init_db(db_path)
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client(temp_db):
    """Provides a FastAPI TestClient wired to the isolated temporary test database."""
    app.dependency_overrides[get_db_path] = lambda: temp_db
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
    """Validates /api/v1/health endpoint and database connectivity status."""

    def test_health_endpoint_healthy(self, client, temp_db):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["database_path"] == temp_db
        assert data["total_cards"] == 0
        assert data["circuit_breaker"]["circuit_breaker_tripped"] is False
        assert data["circuit_breaker"]["limit"] == 500

    def test_health_endpoint_after_insert(self, client, sample_card_payload):
        client.post("/api/v1/cards/capture", json=sample_card_payload)
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["total_cards"] == 1
        assert data["total_investment"] == 150.0
        assert data["total_estimated_value"] == 275.0

    def test_health_endpoint_db_failure(self, client):
        # Override with invalid database path
        app.dependency_overrides[get_db_path] = lambda: "Z:\\non_existent_folder_xyz\\portfolio.db"
        response = client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"


# ===========================================================================
# Tier 1 & Tier 2: Single Card Capture Ingestion Tests
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

        # Verify physical persistence in SQLite
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

    def test_capture_category_normalization(self, client, sample_card_payload, temp_db):
        # Alias 'ufc' -> 'UFC/MMA'
        sample_card_payload["category"] = "ufc"
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 200
        row = get_card_by_id(response.json()["card_id"], db_path=temp_db)
        assert row["category"] == "UFC/MMA"

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

    def test_capture_with_parent_and_child_ids(self, client, sample_card_payload, temp_db):
        sample_card_payload["notes"] = ""
        sample_card_payload["parent_image_id"] = 8492
        sample_card_payload["child_card_id"] = 105
        response = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert response.status_code == 200
        assert response.json()["notes"] == "8492-105"

    def test_capture_with_parent_id_only_auto_increments(self, client, sample_card_payload, temp_db):
        sample_card_payload["notes"] = ""
        sample_card_payload["parent_image_id"] = 8492
        del sample_card_payload["child_card_id"]

        r1 = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert r1.status_code == 200
        assert r1.json()["notes"] == "8492-101"

        r2 = client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert r2.status_code == 200
        assert r2.json()["notes"] == "8492-102"


# ===========================================================================
# Tier 2 & Tier 3: Batch Capture & Circuit Breaker Tests
# ===========================================================================

class TestBatchCardCapture:
    """Validates POST /api/v1/cards/batch atomic multi-item ingestion and limits."""

    def test_batch_capture_as_list(self, client, sample_card_payload, temp_db):
        card1 = dict(sample_card_payload, player="Luka Doncic", year="2018")
        card2 = dict(sample_card_payload, player="Trae Young", year="2018")
        response = client.post("/api/v1/cards/batch", json=[card1, card2])
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["inserted_count"] == 2
        assert len(data["card_ids"]) == 2
        assert get_card_count(db_path=temp_db) == 2

    def test_batch_capture_as_wrapped_dict(self, client, sample_card_payload, temp_db):
        card1 = dict(sample_card_payload, player="Victor Wembanyama", year="2023")
        card2 = dict(sample_card_payload, player="Chet Holmgren", year="2022")
        response = client.post("/api/v1/cards/batch", json={"cards": [card1, card2]})
        assert response.status_code == 200
        data = response.json()
        assert data["inserted_count"] == 2
        assert get_card_count(db_path=temp_db) == 2

    def test_batch_capture_empty_rejected(self, client):
        response = client.post("/api/v1/cards/batch", json=[])
        assert response.status_code in (400, 422)

    def test_batch_capture_circuit_breaker_500_exceeded(self, client, sample_card_payload):
        # 501 items exceeds circuit breaker limit
        large_batch = [dict(sample_card_payload, card_number=str(i)) for i in range(501)]
        response = client.post("/api/v1/cards/batch", json=large_batch)
        assert response.status_code in (400, 422)
        assert "exceeds" in response.text.lower() or "500" in response.text

    def test_batch_atomic_rollback_on_invalid_card(self, client, sample_card_payload, temp_db):
        card_valid = dict(sample_card_payload, player="Good Card")
        card_invalid = dict(sample_card_payload, player="Bad Card", condition="Raw", slab_serial_number="ILLEGAL_CERT")
        response = client.post("/api/v1/cards/batch", json=[card_valid, card_invalid])
        assert response.status_code == 422
        # Verify 0 cards inserted due to transaction rollback
        assert get_card_count(db_path=temp_db) == 0


# ===========================================================================
# Tier 1 & Tier 2: CORS Middleware Verification Tests
# ===========================================================================

class TestCorsMiddleware:
    """Validates CORS headers for Chrome Extension and local developer origins."""

    def test_cors_chrome_extension_origin(self, client):
        origin = "chrome-extension://abcdefghijklmnop"
        response = client.get("/api/v1/health", headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_localhost_origin(self, client):
        origin = "http://localhost:3000"
        response = client.get("/api/v1/health", headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_127_0_0_1_origin(self, client):
        origin = "http://127.0.0.1:8501"
        response = client.get("/api/v1/health", headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin

    def test_cors_disallowed_origin(self, client):
        origin = "https://unauthorized-domain.com"
        response = client.get("/api/v1/health", headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") is None

    def test_cors_preflight_options(self, client):
        origin = "chrome-extension://abcdefghijklmnop"
        response = client.options("/api/v1/cards/capture", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin
        assert "POST" in response.headers.get("access-control-allow-methods", "")


# ===========================================================================
# Tier 3: Staging CRUD & Query Endpoints Tests
# ===========================================================================

class TestCardCrudEndpoints:
    """Validates staging table inspection, partial update, status changes, and deletion."""

    def test_get_card_by_id_success(self, client, sample_card_payload):
        create_res = client.post("/api/v1/cards/capture", json=sample_card_payload)
        card_id = create_res.json()["card_id"]

        get_res = client.get(f"/api/v1/cards/{card_id}")
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["status"] == "success"
        assert data["card"]["player"] == "Anthony Edwards"

    def test_get_card_by_id_not_found(self, client):
        response = client.get("/api/v1/cards/99999")
        assert response.status_code == 404

    def test_list_cards_with_filters(self, client, sample_card_payload):
        c1 = dict(sample_card_payload, player="Kobe Bryant", category="Basketball", variation="")
        c2 = dict(sample_card_payload, player="Ken Griffey Jr", category="Baseball", variation="Refractor")
        client.post("/api/v1/cards/capture", json=c1)
        client.post("/api/v1/cards/capture", json=c2)

        # Filter by category
        res_cat = client.get("/api/v1/cards?category_filter=Baseball")
        assert res_cat.status_code == 200
        assert res_cat.json()["count"] == 1
        assert res_cat.json()["cards"][0]["player"] == "Ken Griffey Jr"

        # Filter by status
        res_status = client.get("/api/v1/cards?status_filter=REVIEW VARIATION")
        assert res_status.status_code == 200
        assert res_status.json()["count"] == 1
        assert res_status.json()["cards"][0]["player"] == "Ken Griffey Jr"

        # Free text search
        res_search = client.get("/api/v1/cards?search_query=Kobe")
        assert res_search.status_code == 200
        assert res_search.json()["count"] == 1
        assert res_search.json()["cards"][0]["player"] == "Kobe Bryant"

    def test_patch_card_success(self, client, sample_card_payload):
        create_res = client.post("/api/v1/cards/capture", json=sample_card_payload)
        card_id = create_res.json()["card_id"]

        patch_res = client.patch(f"/api/v1/cards/{card_id}", json={
            "estimated_value": 350.0,
            "variation": "Gold Prizm"
        })
        assert patch_res.status_code == 200
        updated = patch_res.json()["card"]
        assert updated["estimated_value"] == 350.0
        assert updated["variation"] == "Gold Prizm"
        assert "Gold Prizm" in updated["query"]

    def test_patch_card_not_found(self, client):
        patch_res = client.patch("/api/v1/cards/99999", json={"estimated_value": 10.0})
        assert patch_res.status_code == 404

    def test_delete_card_success(self, client, sample_card_payload):
        create_res = client.post("/api/v1/cards/capture", json=sample_card_payload)
        card_id = create_res.json()["card_id"]

        del_res = client.delete(f"/api/v1/cards/{card_id}")
        assert del_res.status_code == 200
        assert del_res.json()["deleted_id"] == card_id

        # Verify 404 on subsequent get
        assert client.get(f"/api/v1/cards/{card_id}").status_code == 404

    def test_delete_card_not_found(self, client):
        assert client.delete("/api/v1/cards/99999").status_code == 404

    def test_update_card_status_success(self, client, sample_card_payload):
        create_res = client.post("/api/v1/cards/capture", json=sample_card_payload)
        card_id = create_res.json()["card_id"]

        status_res = client.post(f"/api/v1/cards/{card_id}/status", json={"status": "CLEARED"})
        assert status_res.status_code == 200
        assert status_res.json()["ai_status"] == "CLEARED"

    def test_update_card_status_invalid(self, client, sample_card_payload):
        create_res = client.post("/api/v1/cards/capture", json=sample_card_payload)
        card_id = create_res.json()["card_id"]

        status_res = client.post(f"/api/v1/cards/{card_id}/status", json={"status": "INVALID_STATUS"})
        assert status_res.status_code == 400

    def test_get_stats_endpoint(self, client, sample_card_payload):
        client.post("/api/v1/cards/capture", json=sample_card_payload)
        stats_res = client.get("/api/v1/stats")
        assert stats_res.status_code == 200
        stats = stats_res.json()["stats"]
        assert stats["total_cards"] == 1
        assert "Basketball" in stats["count_by_category"]

    def test_clear_staging_table_endpoint(self, client, sample_card_payload, temp_db):
        client.post("/api/v1/cards/capture", json=sample_card_payload)
        assert get_card_count(db_path=temp_db) == 1

        clear_res = client.post("/api/v1/cards/staging/clear")
        assert clear_res.status_code == 200
        assert clear_res.json()["deleted_count"] == 1
        assert get_card_count(db_path=temp_db) == 0
```

---

## 6. Verification and Execution Instructions

To independently verify the implementation once written by the implementer agent:

1. **Execute API Bridge Test Suite**:
   ```powershell
   python -m pytest sports_cards/ecosystem_hub/tests/test_api_bridge.py -v
   ```
2. **Execute Full Ecosystem Hub Regression**:
   ```powershell
   python -m pytest sports_cards/ecosystem_hub/tests/ -q
   ```
3. **Verify CORS & Standalone Execution**:
   ```powershell
   python sports_cards/ecosystem_hub/api.py
   ```

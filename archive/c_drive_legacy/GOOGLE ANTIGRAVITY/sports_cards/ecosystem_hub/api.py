"""
api.py - FastAPI Application & Ingestion API Bridge for Sports Card Ecosystem Hub.
Handles incoming card captures from Chrome Extension and external clients,
enforces the 21-variable schema, calculates query and tracking notes,
and provides full CRUD, batch ingestion, sales listing generation,
and concurrent background server execution.
"""

from __future__ import annotations

import os
import socket
import threading
import logging
from typing import Any, Optional, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, Path, Body, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from models import (
    CardRecord,
    CardUpdate,
    AIStatus,
    CardCategory,
    CardCaptureRequest,
    CardBatchCreate,
    MarketplaceListing,
    SalesListingRequest,
    SummaryStatsResponse,
    format_notes,
    synthesize_query,
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
)
from sales_generator import (
    generate_marketplace_listing,
    generate_listing_for_card_id,
    build_structured_listing,
    MockSalesGenerator,
)

logger = logging.getLogger("sports_cards.api")

# ---------------------------------------------------------------------------
# Dependency Injection for Database Path
# ---------------------------------------------------------------------------

def get_db_path(request: Request = None) -> str:
    """
    Dependency returning the active SQLite database path.
    Supports override via app.state.db_path, PORTFOLIO_DB_PATH env var, or FastAPI dependency override.
    """
    if request and hasattr(request.app.state, "db_path") and request.app.state.db_path:
        return request.app.state.db_path
    return os.environ.get("PORTFOLIO_DB_PATH", DEFAULT_DB_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to ensure database schema initialization on startup."""
    active_db = getattr(app.state, "db_path", None) or os.environ.get("PORTFOLIO_DB_PATH", DEFAULT_DB_PATH)
    try:
        init_db(active_db)
    except Exception as e:
        logger.warning(f"Lifespan init_db failed on '{active_db}': {e}")
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
    model_config = ConfigDict(extra="allow")
    cards: list[Union[ExtendedCardCaptureRequest, dict[str, Any]]] = Field(
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
    card: Optional[dict[str, Any]] = None


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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper Utilities
# ---------------------------------------------------------------------------

def _prepare_card_record(
    payload: Union[ExtendedCardCaptureRequest, CardCaptureRequest, dict[str, Any]],
    db_path: str
) -> CardRecord:
    """
    Transforms an incoming capture request into a validated CardRecord.
    Resolves parent/child tracking notes if parent_image_id is supplied and notes is empty.
    """
    if isinstance(payload, BaseModel):
        data = payload.model_dump()
    elif isinstance(payload, dict):
        data = dict(payload)
    else:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid payload type: {type(payload)}"
        )

    parent_id = data.pop("parent_image_id", None)
    child_id = data.pop("child_card_id", None)

    if not data.get("notes") and parent_id is not None:
        if child_id is not None and str(child_id).strip():
            data["notes"] = format_notes(parent_id, child_id)
        else:
            next_child = get_next_child_id(parent_id, db_path=db_path)
            data["notes"] = format_notes(parent_id, next_child)

    if data.get("date_purchased") is None:
        data.pop("date_purchased", None)
    if data.get("ai_status") is None:
        data.pop("ai_status", None)

    try:
        return CardRecord(**data)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Card validation error: {str(e)}"
        ) from e


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="System Health & Database Connectivity"
)
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
        card=inserted,
    )


@app.post(
    "/api/v1/cards/batch",
    response_model=BatchCaptureResponse,
    status_code=status.HTTP_200_OK,
    tags=["Ingestion"],
    summary="Batch Capture Cards (up to 500)"
)
def capture_cards_batch(
    payload: Union[CardBatchRequest, list[Union[ExtendedCardCaptureRequest, dict[str, Any]]]] = Body(...),
    db_path: str = Depends(get_db_path)
) -> BatchCaptureResponse:
    """
    Batch captures up to 500 cards in an atomic transaction.
    Accepts direct JSON list or wrapped { 'cards': [...] } object.
    Enforces circuit breaker maximum limit of 500 items.
    """
    raw_cards: list[Any] = (
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
            status_code=422,
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


@app.post(
    "/api/v1/cards/{card_id}/listing",
    tags=["Monetization"],
    summary="Generate Facebook Marketplace Listing for Card"
)
def generate_card_listing_endpoint(
    card_id: int = Path(..., ge=1, description="Integer card ID"),
    asking_price: Optional[float] = Query(None, ge=0.0, description="Optional custom asking price"),
    custom_notes: Optional[str] = Query("", description="Optional custom condition notes"),
    mock: bool = Query(False, description="Whether to use deterministic mock generator"),
    db_path: str = Depends(get_db_path)
) -> dict[str, Any]:
    """Generates an SEO-optimized listing for a specific card record in staging."""
    card = get_card_by_id(card_id, db_path=db_path)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card with ID {card_id} not found"
        )

    listing_text = generate_marketplace_listing(
        card=card,
        asking_price=asking_price,
        custom_notes=custom_notes or "",
        mock=mock,
        db_path=db_path
    )
    structured = build_structured_listing(
        card=card,
        asking_price=asking_price,
        custom_notes=custom_notes or "",
        card_id=card_id,
        is_mock=mock
    )

    return {
        "status": "success",
        "card_id": card_id,
        "listing": listing_text,
        "structured": structured.model_dump(),
    }


@app.post(
    "/api/v1/sales/generate",
    tags=["Monetization"],
    summary="Generate On-Demand Sales Listing"
)
def generate_sales_listing_endpoint(
    payload: SalesListingRequest = Body(...),
    db_path: str = Depends(get_db_path)
) -> dict[str, Any]:
    """
    On-demand sales listing generation. Accepts either a card_id or inline card_data payload.
    """
    target_card: Optional[Union[dict[str, Any], CardRecord]] = None
    resolved_card_id = payload.card_id

    if payload.card_id is not None:
        target_card = get_card_by_id(payload.card_id, db_path=db_path)
        if target_card is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Card with ID {payload.card_id} not found in database"
            )
    elif payload.card_data is not None:
        if isinstance(payload.card_data, BaseModel):
            target_card = payload.card_data.model_dump()
        else:
            target_card = dict(payload.card_data)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either 'card_id' or 'card_data' in request"
        )

    listing_text = generate_marketplace_listing(
        card=target_card,
        asking_price=payload.asking_price,
        custom_notes=payload.custom_notes or "",
        mock=payload.mock,
        db_path=db_path
    )
    structured = build_structured_listing(
        card=target_card,
        asking_price=payload.asking_price,
        custom_notes=payload.custom_notes or "",
        card_id=resolved_card_id,
        is_mock=payload.mock
    )

    return {
        "status": "success",
        "card_id": resolved_card_id,
        "listing": listing_text,
        "structured": structured.model_dump(),
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


@app.get(
    "/api/v1/circuit-breaker",
    tags=["Metrics"],
    summary="Get Circuit Breaker Status"
)
def get_circuit_breaker_endpoint(db_path: str = Depends(get_db_path)) -> dict[str, Any]:
    """Returns current circuit breaker limit and capacity status."""
    cb = check_circuit_breaker(db_path)
    return {
        "status": "success",
        "circuit_breaker": cb,
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


# ---------------------------------------------------------------------------
# Background Server Runner for Streamlit & Background Execution
# ---------------------------------------------------------------------------

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Checks if a network port is currently open and accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


class BackgroundServerThread(threading.Thread):
    """
    Thread-safe uvicorn background server runner with signal handler bypass for Windows threads.
    """

    def __init__(
        self,
        app_instance: FastAPI = app,
        host: str = "127.0.0.1",
        port: int = 8002,
        db_path: str = DEFAULT_DB_PATH
    ):
        super().__init__(daemon=True, name=f"FastAPIServerThread-{port}")
        self.host = host
        self.port = port
        self.db_path = db_path
        self.app_instance = app_instance
        self.server: Optional[Any] = None
        self._is_ready = threading.Event()

    def run(self):
        import uvicorn
        self.app_instance.state.db_path = self.db_path
        config = uvicorn.Config(
            self.app_instance,
            host=self.host,
            port=self.port,
            log_level="warning",
            loop="asyncio"
        )
        self.server = uvicorn.Server(config=config)
        self.server.install_signal_handlers = lambda: None
        self._is_ready.set()
        self.server.run()

    def stop(self):
        """Signals uvicorn server to terminate."""
        if self.server:
            self.server.should_exit = True

    def wait_until_ready(self, timeout: float = 5.0) -> bool:
        """Blocks until the server thread is active."""
        return self._is_ready.wait(timeout=timeout)


def start_api_server_thread(
    host: str = "127.0.0.1",
    port: int = 8002,
    db_path: str = DEFAULT_DB_PATH
) -> BackgroundServerThread:
    """
    Starts FastAPI bridge in a background daemon thread if not already running on target port.
    Returns the BackgroundServerThread instance.
    """
    if is_port_in_use(port, host=host):
        logger.info(f"Port {port} is already active. Background API server will not start duplicate.")
        dummy = BackgroundServerThread(app, host=host, port=port, db_path=db_path)
        dummy._is_ready.set()
        return dummy

    server_thread = BackgroundServerThread(app, host=host, port=port, db_path=db_path)
    server_thread.start()
    server_thread.wait_until_ready(timeout=2.0)
    return server_thread


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8002, reload=True)

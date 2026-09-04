# Technical Analysis: M3 API Bridge, Sales Generator Integration & Server Runner Strategy

**Target Project**: Sports Card Ecosystem Hub (`sports_cards/ecosystem_hub`)  
**Milestone**: Milestone 3 — API Bridge & Sales Listing Generator  
**Agent**: Explorer M3.3 (`teamwork_preview_explorer`)  
**Date**: 2026-08-24  

---

## 1. Executive Summary & Architectural Context

Milestone 3 bridges the external browser ingestion layer (the Chrome Extension) and the monetization layer (Facebook Marketplace sales copy generation) into the centralized 21-variable SQLite repository (`portfolio.db`).

The scope of this investigation resolves three core architectural objectives:
1. **Component Interaction Design**: Define clean, robust interfaces between `api.py` (FastAPI), `sales_generator.py` (Gemini Copywriter), `database.py` (SQLite WAL Engine), and `models.py` (Pydantic v2 validation layer).
2. **Concurrent Server Runner Strategy**: Formulate a bulletproof execution strategy enabling FastAPI (port 8002) and Streamlit (port 8501) to run concurrently on Windows without thread crashes, port collision errors during Streamlit re-runs, or SQLite locking contention.
3. **End-to-End Integration Test Suite**: Establish a comprehensive, deterministic test harness covering the entire lifecycle from Chrome Extension HTTP payload capture to SQLite persistence to SEO-optimized sales copy generation.

---

## 2. Component Interaction Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CHROME EXTENSION INGESTION                      │
│                  (zero_friction_capture_extension)                     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ HTTP POST /api/v1/cards/capture
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                               api.py                                   │
│  FastAPI Application + CORSMiddleware + RequestValidationError Handler │
│  - Validates payload against CardCaptureRequest                        │
│  - Checks 500-Card Circuit Breaker                                     │
│  - Calls database.capture_card_from_api()                              │
└──────────────────┬──────────────────────────────────┬──────────────────┘
                   │                                  │
      Insert Card  │                                  │ Trigger Listing
                   ▼                                  ▼
┌──────────────────────────────────────┐   ┌─────────────────────────────┐
│             database.py              │   │     sales_generator.py      │
│  SQLite3 (WAL Mode, 5000ms Timeout)  │   │  Gemini 2.5 Flash + Mock    │
│  - Strict Check Constraints          │◄──┤  - Reads DB Card Record     │
│  - Foreign Keys & B-Tree Indexes     │   │  - Title < 100 chars        │
│  - Query Synthesis & AI Status       │   │  - Specs, Terms, 6-8 Tags   │
└──────────────────▲───────────────────┘   └──────────────┬──────────────┘
                   │                                      │
                   │ Schema & Validation                  │
                   └───────────────────┬──────────────────┘
                                       │
                        ┌──────────────┴──────────────┐
                        │          models.py          │
                        │  - CardRecord (21 Vars)     │
                        │  - CardCaptureRequest       │
                        │  - MarketplaceListing       │
                        │  - SalesListingRequest      │
                        │  - CardCategory (22 exact)  │
                        └─────────────────────────────┘
```

### 2.1 Schema & Data Flow Contracts

#### A. Models (`models.py`) Extensions
Existing models in `models.py` (`CardRecord`, `CardCaptureRequest`, `CardUpdate`, `CardBatchCreate`, `AIStatus`, `CardCategory`) provide the foundation. For Milestone 3, the following models must be standardized:

```python
class MarketplaceListing(BaseModel):
    """Structured response model for Facebook Marketplace listing copy."""
    title: str = Field(..., max_length=100, description="SEO title under 100 characters")
    price: float = Field(..., ge=0.0, description="Target asking price")
    price_formatted: str = Field(..., description="Formatted price string e.g. '$350.00 Cash / Zelle'")
    specs: dict[str, str] = Field(default_factory=dict, description="Key-value item specifications")
    description: str = Field(..., description="Condition notes and card highlights")
    terms: str = Field(..., description="Pickup location, payment methods, and return policy")
    hashtags: list[str] = Field(..., min_length=6, max_length=8, description="6 to 8 SEO hashtags")
    raw_text: str = Field(..., description="Complete copy-paste ready text block for FB Marketplace")
    card_id: Optional[int] = Field(default=None, description="Associated database card ID")
    is_mock: bool = Field(default=False, description="True if generated via deterministic offline fallback")


class SalesListingRequest(BaseModel):
    """Request payload for on-demand sales copy generation."""
    card_id: Optional[int] = None
    asking_price: Optional[float] = Field(default=None, ge=0.0)
    custom_notes: Optional[str] = ""
    mock: bool = False
    card_data: Optional[CardCaptureRequest] = None
```

#### B. Database (`database.py`) Integration
`database.py` already includes `capture_card_from_api(payload, db_path)` which converts `CardCaptureRequest` into `CardRecord`, persists it to SQLite, and returns:
```json
{
  "status": "success",
  "card_id": 1,
  "query": "2020 Panini Prizm Luka Dončić Silver Prizm PSA 10",
  "notes": "8492-105",
  "ai_status": "REVIEW VARIATION"
}
```

Key database functions supporting M3:
- `get_card_by_id(card_id, db_path)`: Fetches full card dictionary to populate `sales_generator`.
- `check_circuit_breaker(db_path)`: Evaluates if staging row count >= 500.
- `get_summary_stats(db_path)`: Delivers aggregated metrics to `GET /api/v1/stats`.
- `insert_cards_batch(cards, db_path)`: Processes batch payloads for `POST /api/v1/cards/batch`.

---

### 2.2 FastAPI Application Specification (`api.py`)

`api.py` acts as the ingestion bridge and local API gateway.

#### Router & Endpoint Matrix
| Method | Path | Request Body / Params | Response | Description |
|---|---|---|---|---|
| `GET` | `/health` | None | `{"status": "healthy", "database": "connected", "card_count": int}` | Liveness & health check |
| `POST` | `/api/v1/cards/capture` | `CardCaptureRequest` | `201 Created` / `CaptureResponse` | Primary Chrome Extension ingestion |
| `POST` | `/api/v1/cards/batch` | `CardBatchCreate` | `201 Created` / `BatchResponse` | Bulk ingestion (1-500 cards) |
| `GET` | `/api/v1/cards/{card_id}` | `card_id: int` | `200 OK` / `CardRecord` | Retrieve card by ID (404 if missing) |
| `GET` | `/api/v1/cards` | `status`, `category`, `search`, `limit`, `offset` | `200 OK` / `list[dict]` | Filtered query & pagination |
| `POST` | `/api/v1/cards/{card_id}/listing` | `asking_price: float = None`, `mock: bool = False` | `200 OK` / `MarketplaceListing` | Generate FB sales copy for staged card |
| `POST` | `/api/v1/sales/generate` | `SalesListingRequest` | `200 OK` / `MarketplaceListing` | Ad-hoc listing generation |
| `GET` | `/api/v1/stats` | None | `200 OK` / `SummaryStatsResponse` | Portfolio aggregated metrics |
| `GET` | `/api/v1/circuit-breaker` | None | `200 OK` / `CircuitBreakerStatus` | Staging capacity & breaker flag |

#### CORS & Security Architecture
Chrome Extension content scripts and background service workers make HTTP requests from `chrome-extension://*` origins or `null` origins.
`api.py` must configure FastAPI `CORSMiddleware`:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits all Chrome Extension origins & localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Dependency Injection for Testability
To allow tests to run on isolated temporary SQLite databases without modifying global module state, `api.py` must use a dependency injection helper:
```python
def get_db_path(request: Request) -> str:
    if hasattr(request.app.state, "db_path") and request.app.state.db_path:
        return request.app.state.db_path
    return os.getenv("SPORTS_CARDS_DB_PATH", DEFAULT_DB_PATH)
```
In test fixtures:
```python
client = TestClient(app)
app.state.db_path = str(tmp_path / "test_portfolio.db")
```

---

### 2.3 Sales Listing Generator (`sales_generator.py`)

`sales_generator.py` transforms card attributes into a high-converting Facebook Marketplace listing.

#### Core Rules & Constraints:
1. **Title Length (<100 Chars)**: Facebook Marketplace strictly enforces a 100-character maximum on listing titles. Titles exceeding 100 characters are rejected by Facebook. Format: `[Year] [Set] [Player] [Variation] [Card #] [Condition]` (e.g. `2020 Panini Prizm Luka Doncic Silver Prizm #75 PSA 10` = 54 chars).
2. **Asking Price Resolution**:
   - If explicit `asking_price` is provided, use it.
   - Else if `card.estimated_value > 0`, use `card.estimated_value`.
   - Else if `card.investment > 0`, use `card.investment`.
   - Else default to `0.0`.
3. **Item Specifics Bullets**:
   - Sport/Category, Year, Set, Player, Card Number, Variation, Condition, Slab Cert (or "Raw").
4. **Condition Notes & Mandatory Disclaimers**:
   - **Graded Cards**: Highlight encapsulation, slab clarity, subgrades/grade authenticity.
   - **Raw Cards**: Mandatory disclaimer: *"Card is in raw condition. Please review all high-resolution photos for exact centering, corners, edges, and surface. Sold as-is."*
   - **Prohibited Claims**: Banned from generating deceptive claims such as "PSA 10 candidate", "Gem Mint raw", or false scarcity claims.
5. **Local Pickup & Transaction Terms**:
   - *"Local pickup in safe public location (bank / police department) or tracked shipping in bubble mailer. Cash, Zelle, or Venmo accepted. No trades."*
6. **Hashtags (6 to 8 Tags)**:
   - `#SportsCards #[Category]Cards #[PlayerNameClean] #[SetNameClean] #[GradeClean] #TheHobby #CardCollector #TradingCards`
7. **Deterministic Offline Fallback (`MockSalesGenerator`)**:
   - When `mock=True` or `GEMINI_API_KEY` is not set or network call fails, `MockSalesGenerator` formats the exact same structured schema deterministically with zero latency and 100% reproducible output.

---

## 3. Concurrent Server Runner Strategy (FastAPI + Streamlit)

### 3.1 Architectural Trade-Off Analysis

Running a web dashboard (`Streamlit` on port 8501) and an ingestion API bridge (`FastAPI` on port 8002) locally requires careful concurrency design:

| Strategy | Mechanism | Pros | Cons | Recommendation |
|---|---|---|---|---|
| **Option A: In-Process Thread inside `app.py`** | `threading.Thread` runs `uvicorn.Server` | Single command `streamlit run app.py` starts everything | Streamlit re-executes `app.py` on every user click; signal handlers fail in thread | **Recommended with `@st.cache_resource` and signal shim** |
| **Option B: Independent Standalone Daemons** | Two separate CLI commands (`uvicorn` & `streamlit`) | Total process isolation; standard signal handling | Requires user to manage two terminal processes | **Supported as primary developer workflow** |
| **Option C: Unified CLI Orchestrator (`runner.py`)** | Python script manages both subprocesses | Clean start/stop lifecycle; single terminal command | Slightly more complex CLI wrapper | **Implemented as convenience entrypoint** |

### 3.2 Solving the In-Process Thread Pitfalls

To allow `streamlit run app.py` to auto-boot the FastAPI bridge without crashing, three specific techniques must be implemented:

1. **Port Availability Check & Socket Probe**:
   ```python
   import socket

   def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
       with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
           s.settimeout(0.5)
           return s.connect_ex((host, port)) == 0
   ```

2. **Streamlit Resource Caching (`@st.cache_resource`)**:
   Streamlit re-executes `app.py` top-to-bottom on every UI event. Wrapping the server starter in `@st.cache_resource` ensures the server thread is created **only once** per Streamlit process:
   ```python
   @st.cache_resource
   def start_background_api_bridge(port: int = 8002, db_path: str = "portfolio.db"):
       if not is_port_in_use(port):
           server_thread = BackgroundServerThread(app=api_app, port=port, db_path=db_path)
           server_thread.start()
           return server_thread
       return "ALREADY_ACTIVE"
   ```

3. **Uvicorn Signal Handler Shim**:
   `uvicorn.run()` calls `signal.signal()` which raises `ValueError: signal only works in main thread of the main interpreter` on background threads. To bypass this on Windows, instantiate `uvicorn.Server(config=config)` directly and disable signal handlers:
   ```python
   class BackgroundServerThread(threading.Thread):
       def __init__(self, app, host: str = "127.0.0.1", port: int = 8002, db_path: str = "portfolio.db"):
           super().__init__(daemon=True, name="FastAPIServerThread")
           self.host = host
           self.port = port
           self.db_path = db_path
           self.app = app
           self.server = None

       def run(self):
           self.app.state.db_path = self.db_path
           config = uvicorn.Config(
               self.app,
               host=self.host,
               port=self.port,
               log_level="warning",
               loop="asyncio"
           )
           self.server = uvicorn.Server(config=config)
           self.server.install_signal_handlers = lambda: None  # Bypass thread signal restriction
           self.server.run()

       def stop(self):
           if self.server:
               self.server.should_exit = True
   ```

### 3.3 SQLite WAL Concurrency Guarantees
Because `database.py` enforces:
- `PRAGMA journal_mode = WAL;` (Write-Ahead Logging)
- `PRAGMA busy_timeout = 5000;` (5-second lock retry)
- `PRAGMA synchronous = NORMAL;`

FastAPI writes from incoming Chrome Extension POSTs do NOT block Streamlit dashboard reads, and Streamlit user interactions do NOT block FastAPI writes. Both threads / processes access `portfolio.db` with zero database lock errors.

---

## 4. End-to-End Integration Test Scenarios

The test suite must cover three test files:
- `tests/test_api_bridge.py`
- `tests/test_sales_generator.py`
- `tests/test_e2e_hub.py`

### Scenario Matrix

```
┌────────────────────────────────────────────────────────────────────────┐
│                        INTEGRATION TEST MATRIX                         │
├────┬─────────────────────────────┬───────────────────┬────────────────┤
│ #  │ Scenario                    │ Target Module     │ Expected Result│
├────┼─────────────────────────────┼───────────────────┼────────────────┤
│ 1  │ Golden Path: POST -> DB ->  │ api.py, db,       │ 201 Created -> │
│    │ Sales Listing Generation    │ sales_generator   │ Listing <100ch │
│ 2  │ Raw Card Ingestion & Notes  │ api.py, db,       │ Raw disclaimer │
│    │ Verification                │ sales_generator   │ no slab serial │
│ 3  │ Schema Validation & Defense │ api.py, models    │ 422 Rejected,  │
│    │ Against Invalid Payloads    │                   │ DB unchanged   │
│ 4  │ 500-Card Circuit Breaker    │ api.py, db        │ 429 / 400 when │
│    │ Hard Stop                   │                   │ count >= 500   │
│ 5  │ Multi-Threaded Concurrency  │ api.py, db (WAL)  │ 20 threads,    │
│    │ & Rapid POST / GET Stress   │                   │ 0 lock errors  │
│ 6  │ Gemini SDK Resilience &     │ sales_generator   │ Seamless mock  │
│    │ Offline Mock Fallback       │                   │ fallback       │
└────┴─────────────────────────────┴───────────────────┴────────────────┘
```

### Scenario 1: Golden Path End-to-End Integration
1. **Action**: `POST /api/v1/cards/capture` with valid graded card payload (`2020 Panini Prizm Luka Dončić Silver Prizm #75 PSA 10`, cert `48192041`, est value `350.00`).
2. **Assertions**:
   - HTTP status `201` (or `200`).
   - JSON response contains `status == "success"`, integer `card_id`, `query == "2020 Panini Prizm Luka Dončić Silver Prizm PSA 10"`, `ai_status == "REVIEW VARIATION"`.
3. **Database Verification**:
   - Query `database.get_card_by_id(card_id)` -> record exists, all 21 columns populated.
4. **Sales Copy Verification**:
   - Call `POST /api/v1/cards/{card_id}/listing?asking_price=375.00&mock=true`.
   - Assert `len(title) <= 100`.
   - Assert `price == 375.00`.
   - Assert `specs["Condition"] == "PSA 10"` and `specs["Slab Cert"] == "48192041"`.
   - Assert `len(hashtags) >= 6` and `len(hashtags) <= 8`.
   - Assert `raw_text` contains formatted Title, Price, Bullets, Terms, and Hashtags.

### Scenario 2: Raw Card Capture with Automatic Disclaimers
1. **Action**: `POST /api/v1/cards/capture` with raw card payload (`2018 Topps Chrome Shohei Ohtani #001 Raw`, slab serial `""`).
2. **Assertions**:
   - HTTP status `201`, `ai_status == "CLEARED"`, `query == "2018 Topps Chrome Shohei Ohtani Raw"`.
   - DB record has `slab_serial_number == ""` and `card_number == "001"` (leading zero preserved).
3. **Sales Copy Verification**:
   - Generate listing with `mock=true`.
   - Assert description includes raw condition disclaimer: *"Card is in raw condition..."*.
   - Assert specs does NOT display a graded slab cert.

### Scenario 3: Adversarial Payload Rejection & DB Isolation
1. **Action**: Send malformed payloads to `POST /api/v1/cards/capture`:
   - Missing `player` or `year`.
   - Invalid category (e.g. `"Cricket"`, `"Crypto"`).
   - Hyphenated condition (e.g. `"PSA-10"`).
   - Raw condition with slab serial (e.g. `condition="Raw"`, `slab_serial_number="12345"`).
   - Negative query exclusion on raw card (`"-BGS"`).
2. **Assertions**:
   - FastAPI returns HTTP `422 Unprocessable Entity` or `400 Bad Request`.
   - Error response contains clear validation failure details.
   - Database row count remains 0 (no partial inserts or corrupted state).

### Scenario 4: 500-Card Batch Circuit Breaker Enforcement
1. **Action**: Pre-populate database with 500 cards using `database.insert_cards_batch`.
2. **Action**: Send `POST /api/v1/cards/capture` for card #501.
3. **Assertions**:
   - API returns HTTP `429 Too Many Requests` (or `400 Bad Request`) with message *"500-Card Batch Circuit Breaker Tripped"*.
   - Database card count remains 500.

### Scenario 5: Multi-Threaded Concurrent Read/Write/Generate Stress Test
1. **Action**: Spawn 20 parallel worker threads using `concurrent.futures.ThreadPoolExecutor`:
   - 10 threads POSTing new cards.
   - 5 threads reading card lists and summary stats.
   - 5 threads requesting sales listing generation.
2. **Assertions**:
   - 100% of requests succeed without HTTP 500 errors.
   - Zero `sqlite3.OperationalError: database is locked` exceptions.
   - Final database count matches initial + 10 inserted cards.

### Scenario 6: Gemini SDK Fallback Resilience
1. **Action**: Execute `generate_marketplace_listing`:
   - Case A: `mock=True` -> Deterministic generation.
   - Case B: `mock=False` with `GEMINI_API_KEY=""` -> Graceful fallback to mock, logs warning, returns `is_mock=True`.
   - Case C: Live Gemini API throws network timeout or malformed response -> Catches exception, falls back to deterministic generator without throwing unhandled exceptions.

---

## 5. Implementation Blueprints & File Specifications

### 5.1 Proposed `api.py` Structure
```python
"""
api.py - FastAPI Application for Sports Card Ecosystem Hub.
Provides Chrome Extension API bridge, card query endpoints, and listing generation.
"""

from fastapi import FastAPI, HTTPException, Request, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any

from models import (
    CardRecord,
    CardCaptureRequest,
    CardBatchCreate,
    CardUpdate,
    MarketplaceListing,
    SalesListingRequest,
    SummaryStatsResponse,
)
from database import (
    DEFAULT_DB_PATH,
    CIRCUIT_BREAKER_BATCH_LIMIT,
    init_db,
    insert_card,
    insert_cards_batch,
    get_card_by_id,
    get_all_cards,
    get_summary_stats,
    check_circuit_breaker,
    capture_card_from_api,
)
from sales_generator import generate_marketplace_listing

app = FastAPI(
    title="Sports Card Ecosystem Hub API Bridge",
    version="1.0.0",
    description="FastAPI Bridge for Chrome Extension ingestion and Sales Copy Generation",
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_path(request: Request) -> str:
    if hasattr(request.app.state, "db_path") and request.app.state.db_path:
        return request.app.state.db_path
    return os.getenv("SPORTS_CARDS_DB_PATH", DEFAULT_DB_PATH)

# Endpoints: /health, /api/v1/cards/capture, /api/v1/cards/batch, /api/v1/cards/{id},
# /api/v1/cards, /api/v1/cards/{id}/listing, /api/v1/sales/generate, /api/v1/stats, /api/v1/circuit-breaker
```

### 5.2 Proposed `sales_generator.py` Structure
```python
"""
sales_generator.py - SEO-Optimized Facebook Marketplace Listing Generator.
Uses google.genai SDK with gemini-2.5-flash and deterministic MockSalesGenerator fallback.
"""

import os
import re
import logging
from typing import Optional, Union, Dict, Any
from google import genai
from google.genai import types

from models import CardRecord, MarketplaceListing, SalesListingRequest
from database import DEFAULT_DB_PATH, get_card_by_id

logger = logging.getLogger(__name__)

class MockSalesGenerator:
    """Deterministic fallback generator for offline testing and resilience."""
    @classmethod
    def generate(cls, card_dict: dict, asking_price: float) -> MarketplaceListing:
        ...

def generate_marketplace_listing(
    card: Union[dict, CardRecord, int],
    asking_price: Optional[float] = None,
    custom_notes: Optional[str] = "",
    mock: bool = False,
    db_path: str = DEFAULT_DB_PATH
) -> MarketplaceListing:
    ...
```

### 5.3 Proposed `server_runner.py` / `runner.py`
```python
"""
server_runner.py - Background Daemon Runner for FastAPI & Streamlit Concurrency.
Provides thread-safe, signal-safe server lifecycle management.
"""

import socket
import threading
import uvicorn
import logging

logger = logging.getLogger("hub_runner")

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

class BackgroundServerThread(threading.Thread):
    ...
```

---

## 6. Synthesis & Next Steps
- The architectural design preserves strict compatibility with the existing 475 passing tests from Milestones 1 and 2.
- The implementer can directly execute the blueprints above to implement `api.py`, `sales_generator.py`, `server_runner.py`, and test suites `test_api_bridge.py`, `test_sales_generator.py`, `test_e2e_hub.py`.

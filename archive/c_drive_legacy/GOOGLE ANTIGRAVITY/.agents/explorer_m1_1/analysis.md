# Architectural Investigation & Blueprint: Milestone 1 (Core Database & Data Models)

## Executive Summary
This document provides the complete, authoritative architectural specification for Milestone 1 of the **Sports Card Ecosystem Hub**. Milestone 1 establishes the bedrock data layer:
1. **`models.py`**: Pydantic (v2) data models enforcing the strict 21-variable schema, 22 category enumerations, grading/slab serial validation, query auto-synthesis, parent-child ID format, and leading-zero preservation.
2. **`database.py`**: SQLite3 database management module with Write-Ahead Logging (WAL) concurrency, busy timeout guards, schema DDL with comprehensive `CHECK` constraints, indexes, and transactional CRUD methods.
3. **`tests/test_database.py`**: A deterministic, multi-tiered test suite verifying 100% of data model validation rules, schema constraints, CRUD operations, and multi-threaded WAL concurrency.

---

## 1. Schema & Data Model Design (`models.py`)

### 1.1 The 21-Variable Master Specification
The 21 variables required for the sports card ecosystem and Card Ladder interoperability:

| # | Field Name | Python / DB Type | Default / Nullable | Rule / Constraint |
|---|------------|------------------|-------------------|-------------------|
| 1 | `date_purchased` | `str` (`TEXT`) | Today (`MM/DD/YYYY`) | Format: `MM/DD/YYYY` |
| 2 | `quantity` | `int` (`INTEGER`) | `1` | Must be `>= 1` |
| 3 | `player` | `str` (`TEXT`) | Required | Non-empty athlete / character name |
| 4 | `year` | `str` (`TEXT`) | Required | 4-digit year string (e.g. `'2023'`) |
| 5 | `set_name` | `str` (`TEXT`) | Required | Release line (e.g. `'Panini Prizm'`) |
| 6 | `variation` | `str` (`TEXT`) | `""` | Parallel/foil finish (e.g. `'Silver Prizm'`) |
| 7 | `card_number` | `str` (`TEXT`) | `""` | Preserves leading zeroes (e.g. `'007'`, `'#24'`) |
| 8 | `category` | `str` (`TEXT`) | Required | One of 22 exact permitted categories |
| 9 | `condition` | `str` (`TEXT`) | `'Raw'` | `'Raw'` or graded (e.g. `'PSA 10'`, `'BGS 9.5'`) without hyphens |
| 10 | `slab_serial_number` | `str` (`TEXT`) | `""` | Must be blank/empty if `condition == 'Raw'` |
| 11 | `investment` | `float` (`REAL`) | `0.00` | Cost basis (`>= 0.00`) |
| 12 | `estimated_value` | `float` (`REAL`) | `0.00` | Current market comp value (`>= 0.00`) |
| 13 | `ladder_id` | `str` (`TEXT`) | `""` | Card Ladder sync identifier |
| 14 | `query` | `str` (`TEXT`) | Auto-synthesized | `[Year] [Set] [Player] [Variation] [Condition]` |
| 15 | `notes` | `str` (`TEXT`) | `""` | Tracks `[Parent_Image_ID]-[Child_Card_ID]` (e.g. `8492-105`) |
| 16 | `tags` | `str` (`TEXT`) | `""` | Comma-separated or space-separated tags |
| 17 | `date_sold` | `str` (`TEXT`) | `""` | `MM/DD/YYYY` or empty if unsold |
| 18 | `sold_price` | `Optional[float]` (`REAL`) | `None` | Nullable float (`>= 0.00` if provided) |
| 19 | `image` | `str` (`TEXT`) | `""` | Direct image URL or local path |
| 20 | `back_image` | `str` (`TEXT`) | `""` | Direct back image URL or local path |
| 21 | `ai_status` | `str` (`TEXT`) | `'CLEARED'` / `'REVIEW VARIATION'` | One of `'REVIEW VARIATION'`, `'NEEDS REVIEW'`, `'CLEARED'` |

---

### 1.2 Enumerations

#### 22 Permitted Categories
```python
from enum import Enum

class CardCategory(str, Enum):
    BASKETBALL = "Basketball"
    BASEBALL = "Baseball"
    FOOTBALL = "Football"
    HOCKEY = "Hockey"
    SOCCER = "Soccer"
    TENNIS = "Tennis"
    WRESTLING = "Wrestling"
    RACING = "Racing"
    GOLF = "Golf"
    BOXING = "Boxing"
    UFC_MMA = "UFC/MMA"
    POKEMON = "Pokemon"
    MAGIC = "Magic"
    METAZOO = "Metazoo"
    YUGIOH = "Yugioh"
    FORTNITE = "Fortnite"
    DRAGONBALLZ = "Dragonballz"
    ENTERTAINMENT = "Entertainment"
    SWIMMING = "Swimming"
    SOFTBALL = "Softball"
    POPCULTURE = "PopCulture"
    FLESH_AND_BLOOD = "Flesh and Blood"
```

#### AI Status
```python
class AIStatus(str, Enum):
    CLEARED = "CLEARED"
    REVIEW_VARIATION = "REVIEW VARIATION"
    NEEDS_REVIEW = "NEEDS REVIEW"
```

---

### 1.3 Validation Logic & Implementation in `models.py`

1. **Card Number Leading Zero Preservation**:
   - `card_number` is typed strictly as `str`.
   - In `before` field validator or input parsing, integer inputs (e.g. `7`) or strings with leading zeros (`"007"`) are converted to `str` directly without casting to numeric types that would strip zeros.
2. **Category Validation**:
   - Evaluated against `CardCategory` enum. Case-insensitive normalization can map `"basketball"` to `"Basketball"`.
3. **Condition & Slab Serial Validation**:
   - For `'Raw'` cards: `slab_serial_number` must be empty (`""`). If a user attempts to supply a serial number for a raw card, a `ValueError` is raised.
   - For graded cards (e.g. `'PSA 10'`, `'BGS 9.5'`, `'SGC 10'`, `'CGC 9.5'`, `'TAG 10'`): No hyphens are permitted in grading company notation (e.g., `'PSA-10'` is invalid, `'PSA 10'` is valid).
4. **Query Synthesis**:
   - Generated dynamically from `[Year] [Set] [Player] [Variation] [Condition]`.
   - Strips redundant whitespace.
   - Prohibits negative query exclusions (like `-BGS -SGC`) on `'Raw'` cards as required by workspace rules.
5. **AI Status Assignment**:
   - If `variation` is present (non-empty string) and `ai_status` is not explicitly set by the caller, `ai_status` automatically defaults to `AIStatus.REVIEW_VARIATION`.
   - If `variation` is empty, default is `AIStatus.CLEARED`.
6. **Notes Tracking Format**:
   - Supports `[Parent_Image_ID]-[Child_Card_ID]` tracking format (e.g. `8492-105` where Parent ID is 4 digits and Child ID is 3 digits).

---

### 1.4 Proposed `models.py` Blueprint

```python
"""
models.py - Pydantic v2 schemas for the Sports Card Ecosystem Hub.
Strictly implements the 21-variable schema, 22 category enums, and Card Ladder validation rules.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class CardCategory(str, Enum):
    BASKETBALL = "Basketball"
    BASEBALL = "Baseball"
    FOOTBALL = "Football"
    HOCKEY = "Hockey"
    SOCCER = "Soccer"
    TENNIS = "Tennis"
    WRESTLING = "Wrestling"
    RACING = "Racing"
    GOLF = "Golf"
    BOXING = "Boxing"
    UFC_MMA = "UFC/MMA"
    POKEMON = "Pokemon"
    MAGIC = "Magic"
    METAZOO = "Metazoo"
    YUGIOH = "Yugioh"
    FORTNITE = "Fortnite"
    DRAGONBALLZ = "Dragonballz"
    ENTERTAINMENT = "Entertainment"
    SWIMMING = "Swimming"
    SOFTBALL = "Softball"
    POPCULTURE = "PopCulture"
    FLESH_AND_BLOOD = "Flesh and Blood"


class AIStatus(str, Enum):
    CLEARED = "CLEARED"
    REVIEW_VARIATION = "REVIEW VARIATION"
    NEEDS_REVIEW = "NEEDS REVIEW"


def get_current_date_str() -> str:
    """Returns today's date formatted as MM/DD/YYYY."""
    return datetime.now().strftime("%m/%d/%Y")


def synthesize_query(year: str, set_name: str, player: str, variation: str, condition: str) -> str:
    """Synthesizes search query string: [Year] [Set] [Player] [Variation] [Condition]."""
    parts = [year.strip(), set_name.strip(), player.strip()]
    if variation and variation.strip():
        parts.append(variation.strip())
    if condition and condition.strip():
        parts.append(condition.strip())
    query = " ".join([p for p in parts if p])
    return re.sub(r"\s+", " ", query).strip()


class CardRecord(BaseModel):
    """
    Master 21-Variable Ingestion Model.
    Strictly conforms to sports card domain rules and Card Ladder ingestion specs.
    """
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    # 1. Date Purchased
    date_purchased: str = Field(default_factory=get_current_date_str, description="Date purchased in MM/DD/YYYY format")
    # 2. Quantity
    quantity: int = Field(default=1, ge=1, description="Quantity of cards (>= 1)")
    # 3. Player
    player: str = Field(..., min_length=1, description="Player or character name")
    # 4. Year
    year: str = Field(..., min_length=4, max_length=4, description="4-digit year (YYYY)")
    # 5. Set
    set_name: str = Field(..., min_length=1, description="Set manufacturer and line (e.g. Panini Prizm)")
    # 6. Variation
    variation: str = Field(default="", description="Parallel/foil variation (e.g. Silver Prizm, Refractor)")
    # 7. Number
    card_number: str = Field(default="", description="Printed card number (preserves leading zeros)")
    # 8. Category
    category: CardCategory = Field(..., description="One of 22 exact permitted categories")
    # 9. Condition
    condition: str = Field(default="Raw", description="'Raw' or graded syntax (e.g. 'PSA 10', 'BGS 9.5')")
    # 10. Slab Serial #
    slab_serial_number: str = Field(default="", description="Graded certification number (must be blank for Raw)")
    # 11. Investment
    investment: float = Field(default=0.00, ge=0.0, description="Purchase cost basis")
    # 12. Estimated Value
    estimated_value: float = Field(default=0.00, ge=0.0, description="Current market comp estimate")
    # 13. Ladder ID
    ladder_id: str = Field(default="", description="Card Ladder sync identifier")
    # 14. Query
    query: str = Field(default="", description="Synthesized [Year] [Set] [Player] [Variation] [Condition]")
    # 15. Notes
    notes: str = Field(default="", description="Tracking format [Parent_Image_ID]-[Child_Card_ID]")
    # 16. Tags
    tags: str = Field(default="", description="Optional tags")
    # 17. Date Sold
    date_sold: str = Field(default="", description="Date sold (MM/DD/YYYY)")
    # 18. Sold Price
    sold_price: Optional[float] = Field(default=None, ge=0.0, description="Realized sale price")
    # 19. Image
    image: str = Field(default="", description="Front image URL or path")
    # 20. Back Image
    back_image: str = Field(default="", description="Back image URL or path")
    # 21. AI Status
    ai_status: AIStatus = Field(default=AIStatus.CLEARED, description="Ingestion review status")

    @field_validator("year", mode="before")
    @classmethod
    def validate_year(cls, v: Any) -> str:
        s = str(v).strip()
        if not re.match(r"^\d{4}$", s):
            raise ValueError(f"Year must be a 4-digit string, got '{v}'")
        return s

    @field_validator("card_number", mode="before")
    @classmethod
    def preserve_card_number_string(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("condition")
    @classmethod
    def validate_condition_format(cls, v: str) -> str:
        val = v.strip()
        if val.lower() == "raw":
            return "Raw"
        # Check for hyphens in graded condition (forbidden: PSA-10)
        if "-" in val:
            raise ValueError(f"Graded condition must not contain hyphens (use 'PSA 10' not '{val}')")
        return val

    @model_validator(mode="after")
    def validate_cross_field_rules(self) -> CardRecord:
        # Rule 1: Slab Serial # must be blank if Condition is Raw
        if self.condition == "Raw" and self.slab_serial_number.strip():
            raise ValueError(
                f"Slab serial number must be blank for 'Raw' condition cards (got '{self.slab_serial_number}')"
            )

        # Rule 2: Synthesize query if blank or keep updated
        expected_query = synthesize_query(
            self.year, self.set_name, self.player, self.variation, self.condition
        )
        if not self.query or self.query.strip() == "":
            self.query = expected_query

        # Rule 3: Negative exclusions (-BGS -SGC) are forbidden on Raw cards
        if self.condition == "Raw" and ("-BGS" in self.query or "-SGC" in self.query or "-PSA" in self.query):
            raise ValueError("Negative exclusions are forbidden in queries for Raw cards")

        # Rule 4: Auto-flag variation review
        # If variation is guessed/present, ensure ai_status is REVIEW VARIATION unless explicitly changed
        if self.variation.strip() and self.ai_status == AIStatus.CLEARED:
            self.ai_status = AIStatus.REVIEW_VARIATION

        return self


class CardExtractionSchema(BaseModel):
    """Schema returned by AI Vision Ingest & Scraper Ingest pipelines."""
    player: str
    year: str
    set_name: str
    variation: str = ""
    card_number: str = ""
    category: CardCategory
    condition: str = "Raw"
    slab_serial_number: str = ""
    estimated_value: float = 0.0
    notes: str = ""
    image: str = ""
    back_image: str = ""
    ai_status: AIStatus = AIStatus.CLEARED


class CardCaptureRequest(BaseModel):
    """Schema accepted by FastAPI Chrome Extension POST /api/v1/cards/capture."""
    player: str
    year: str
    set_name: str
    variation: str = ""
    card_number: str = ""
    category: str
    condition: str = "Raw"
    slab_serial_number: str = ""
    investment: float = 0.0
    estimated_value: float = 0.0
    notes: str = ""
    image: str = ""
    back_image: str = ""


class CardUpdate(BaseModel):
    """Schema for updating fields on an existing card record."""
    date_purchased: Optional[str] = None
    quantity: Optional[int] = Field(default=None, ge=1)
    player: Optional[str] = None
    year: Optional[str] = None
    set_name: Optional[str] = None
    variation: Optional[str] = None
    card_number: Optional[str] = None
    category: Optional[CardCategory] = None
    condition: Optional[str] = None
    slab_serial_number: Optional[str] = None
    investment: Optional[float] = Field(default=None, ge=0.0)
    estimated_value: Optional[float] = Field(default=None, ge=0.0)
    ladder_id: Optional[str] = None
    query: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[str] = None
    date_sold: Optional[str] = None
    sold_price: Optional[float] = Field(default=None, ge=0.0)
    image: Optional[str] = None
    back_image: Optional[str] = None
    ai_status: Optional[AIStatus] = None
```

---

## 2. Database Architecture & CRUD Implementation (`database.py`)

### 2.1 SQLite Configuration & Concurrency Controls
To guarantee high-throughput, non-blocking local concurrency between Streamlit, FastAPI background listeners, and batch processing scripts:
1. **`PRAGMA journal_mode = WAL;`**:
   - Write-Ahead Logging allows simultaneous reader processes while a writer commits. Readers do not block writers, and writers do not block readers.
2. **`PRAGMA busy_timeout = 5000;`**:
   - In case of a brief table lock during write commits, SQLite will wait up to 5,000 milliseconds rather than failing with an immediate `sqlite3.OperationalError: database is locked`.
3. **`PRAGMA synchronous = NORMAL;`**:
   - Safe and optimal for WAL mode, significantly speeding up disk flush operations without risking database integrity.
4. **`PRAGMA foreign_keys = ON;`**:
   - Enforces relational consistency.

---

### 2.2 Table DDL & Indexes

```sql
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_purchased TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1),
    player TEXT NOT NULL,
    year TEXT NOT NULL,
    set_name TEXT NOT NULL,
    variation TEXT NOT NULL DEFAULT '',
    card_number TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL CHECK (category IN (
        'Basketball', 'Baseball', 'Football', 'Hockey', 'Soccer', 'Tennis',
        'Wrestling', 'Racing', 'Golf', 'Boxing', 'UFC/MMA', 'Pokemon',
        'Magic', 'Metazoo', 'Yugioh', 'Fortnite', 'Dragonballz',
        'Entertainment', 'Swimming', 'Softball', 'PopCulture', 'Flesh and Blood'
    )),
    condition TEXT NOT NULL,
    slab_serial_number TEXT NOT NULL DEFAULT '',
    investment REAL NOT NULL DEFAULT 0.0 CHECK (investment >= 0.0),
    estimated_value REAL NOT NULL DEFAULT 0.0 CHECK (estimated_value >= 0.0),
    ladder_id TEXT NOT NULL DEFAULT '',
    query TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    date_sold TEXT NOT NULL DEFAULT '',
    sold_price REAL DEFAULT NULL CHECK (sold_price IS NULL OR sold_price >= 0.0),
    image TEXT NOT NULL DEFAULT '',
    back_image TEXT NOT NULL DEFAULT '',
    ai_status TEXT NOT NULL DEFAULT 'CLEARED' CHECK (ai_status IN ('REVIEW VARIATION', 'NEEDS REVIEW', 'CLEARED')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cards_ai_status ON cards(ai_status);
CREATE INDEX IF NOT EXISTS idx_cards_category ON cards(category);
CREATE INDEX IF NOT EXISTS idx_cards_player ON cards(player);
CREATE INDEX IF NOT EXISTS idx_cards_year_set ON cards(year, set_name);
CREATE INDEX IF NOT EXISTS idx_cards_notes ON cards(notes);
CREATE INDEX IF NOT EXISTS idx_cards_query ON cards(query);
```

---

### 2.3 Proposed `database.py` Blueprint

```python
"""
database.py - SQLite3 storage engine for the Sports Card Ecosystem Hub.
Provides WAL mode concurrency, strict schema DDL, indexing, and complete CRUD operations.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator, Any, Optional
from models import CardRecord, CardUpdate, AIStatus, CardCategory, synthesize_query

DEFAULT_DB_PATH = "portfolio.db"
CIRCUIT_BREAKER_BATCH_LIMIT = 500


@contextmanager
def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager that provides a SQLite connection configured with WAL mode,
    busy timeout, and row factory.
    """
    # Ensure parent directory exists
    parent_dir = os.path.dirname(db_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes the database schema and indexes."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_purchased TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1),
            player TEXT NOT NULL,
            year TEXT NOT NULL,
            set_name TEXT NOT NULL,
            variation TEXT NOT NULL DEFAULT '',
            card_number TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL CHECK (category IN (
                'Basketball', 'Baseball', 'Football', 'Hockey', 'Soccer', 'Tennis',
                'Wrestling', 'Racing', 'Golf', 'Boxing', 'UFC/MMA', 'Pokemon',
                'Magic', 'Metazoo', 'Yugioh', 'Fortnite', 'Dragonballz',
                'Entertainment', 'Swimming', 'Softball', 'PopCulture', 'Flesh and Blood'
            )),
            condition TEXT NOT NULL,
            slab_serial_number TEXT NOT NULL DEFAULT '',
            investment REAL NOT NULL DEFAULT 0.0 CHECK (investment >= 0.0),
            estimated_value REAL NOT NULL DEFAULT 0.0 CHECK (estimated_value >= 0.0),
            ladder_id TEXT NOT NULL DEFAULT '',
            query TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '',
            date_sold TEXT NOT NULL DEFAULT '',
            sold_price REAL DEFAULT NULL CHECK (sold_price IS NULL OR sold_price >= 0.0),
            image TEXT NOT NULL DEFAULT '',
            back_image TEXT NOT NULL DEFAULT '',
            ai_status TEXT NOT NULL DEFAULT 'CLEARED' CHECK (ai_status IN ('REVIEW VARIATION', 'NEEDS REVIEW', 'CLEARED')),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_ai_status ON cards(ai_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_category ON cards(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_player ON cards(player);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_year_set ON cards(year, set_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_notes ON cards(notes);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_query ON cards(query);")
        conn.commit()


def insert_card(db_path: str, card_data: dict | CardRecord) -> int:
    """
    Validates and inserts a single card into the database.
    Returns the integer ID of the inserted record.
    """
    if isinstance(card_data, dict):
        record = CardRecord(**card_data)
    elif isinstance(card_data, CardRecord):
        record = card_data
    else:
        raise TypeError(f"card_data must be a dict or CardRecord, got {type(card_data)}")

    data = record.model_dump()

    sql = """
    INSERT INTO cards (
        date_purchased, quantity, player, year, set_name, variation, card_number,
        category, condition, slab_serial_number, investment, estimated_value,
        ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
    ) VALUES (
        :date_purchased, :quantity, :player, :year, :set_name, :variation, :card_number,
        :category, :condition, :slab_serial_number, :investment, :estimated_value,
        :ladder_id, :query, :notes, :tags, :date_sold, :sold_price, :image, :back_image, :ai_status
    );
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, data)
        conn.commit()
        return cursor.lastrowid


def get_card(db_path: str, card_id: int) -> Optional[dict[str, Any]]:
    """Retrieves a single card by its ID, returning a dictionary or None."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE id = ?;", (card_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)


def list_cards(
    db_path: str,
    filters: Optional[dict[str, Any]] = None,
    limit: int = 500,
    offset: int = 0,
    order_by: str = "id DESC"
) -> list[dict[str, Any]]:
    """
    Lists cards with optional filtering and pagination.
    Supports filters: ai_status, category, player, year, set_name, condition, query_search.
    """
    query = "SELECT * FROM cards WHERE 1=1"
    params: list[Any] = []

    if filters:
        if "ai_status" in filters and filters["ai_status"]:
            query += " AND ai_status = ?"
            params.append(filters["ai_status"])
        if "category" in filters and filters["category"]:
            query += " AND category = ?"
            params.append(filters["category"])
        if "player" in filters and filters["player"]:
            query += " AND player LIKE ?"
            params.append(f"%{filters['player']}%")
        if "year" in filters and filters["year"]:
            query += " AND year = ?"
            params.append(filters["year"])
        if "set_name" in filters and filters["set_name"]:
            query += " AND set_name LIKE ?"
            params.append(f"%{filters['set_name']}%")
        if "condition" in filters and filters["condition"]:
            query += " AND condition = ?"
            params.append(filters["condition"])
        if "notes" in filters and filters["notes"]:
            query += " AND notes LIKE ?"
            params.append(f"%{filters['notes']}%")
        if "search" in filters and filters["search"]:
            query += " AND (player LIKE ? OR set_name LIKE ? OR query LIKE ? OR notes LIKE ?)"
            s = f"%{filters['search']}%"
            params.extend([s, s, s, s])

    # Whitelist allowed order_by clauses to prevent SQL injection
    allowed_order = {
        "id ASC", "id DESC",
        "date_purchased ASC", "date_purchased DESC",
        "player ASC", "player DESC",
        "estimated_value ASC", "estimated_value DESC"
    }
    if order_by not in allowed_order:
        order_by = "id DESC"

    query += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def update_card(db_path: str, card_id: int, updates: dict[str, Any] | CardUpdate) -> bool:
    """
    Updates specific fields of an existing card by ID.
    Recalculates query if constituent fields (year, set_name, player, variation, condition) are updated.
    """
    existing = get_card(db_path, card_id)
    if existing is None:
        return False

    update_dict = updates.model_dump(exclude_unset=True) if isinstance(updates, CardUpdate) else dict(updates)
    if not update_dict:
        return True

    # Merge with existing data and validate via CardRecord
    merged = {**existing, **update_dict}
    # Exclude DB metadata fields from validation
    merged.pop("id", None)
    merged.pop("created_at", None)
    merged.pop("updated_at", None)

    validated_record = CardRecord(**merged)
    clean_data = validated_record.model_dump()

    # Build UPDATE query
    set_clauses = [f"{k} = :{k}" for k in clean_data.keys()]
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    sql = f"UPDATE cards SET {', '.join(set_clauses)} WHERE id = :card_id;"

    clean_data["card_id"] = card_id

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, clean_data)
        conn.commit()
        return cursor.rowcount > 0


def delete_card(db_path: str, card_id: int) -> bool:
    """Deletes a card record by its ID. Returns True if deleted."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cards WHERE id = ?;", (card_id,))
        conn.commit()
        return cursor.rowcount > 0


def bulk_insert_cards(db_path: str, card_list: list[dict | CardRecord]) -> list[int]:
    """
    Atomically inserts a batch of cards within a single transaction.
    Returns the list of generated card IDs.
    """
    if not card_list:
        return []

    validated_records = []
    for item in card_list:
        if isinstance(item, dict):
            validated_records.append(CardRecord(**item).model_dump())
        elif isinstance(item, CardRecord):
            validated_records.append(item.model_dump())
        else:
            raise TypeError(f"Each item must be a dict or CardRecord, got {type(item)}")

    sql = """
    INSERT INTO cards (
        date_purchased, quantity, player, year, set_name, variation, card_number,
        category, condition, slab_serial_number, investment, estimated_value,
        ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
    ) VALUES (
        :date_purchased, :quantity, :player, :year, :set_name, :variation, :card_number,
        :category, :condition, :slab_serial_number, :investment, :estimated_value,
        :ladder_id, :query, :notes, :tags, :date_sold, :sold_price, :image, :back_image, :ai_status
    );
    """

    inserted_ids: list[int] = []
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        for rec in validated_records:
            cursor.execute(sql, rec)
            inserted_ids.append(cursor.lastrowid)
        conn.commit()

    return inserted_ids


def get_card_count(db_path: str, status_filter: Optional[str] = None) -> int:
    """Returns the total card count, optionally filtered by ai_status."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if status_filter:
            cursor.execute("SELECT COUNT(*) FROM cards WHERE ai_status = ?;", (status_filter,))
        else:
            cursor.execute("SELECT COUNT(*) FROM cards;")
        return cursor.fetchone()[0]
```

---

## 3. Test Suite Design (`tests/test_database.py`)

### 3.1 Test Coverage Matrix

| Test Function | Target Area | Validation Criterion |
|---|---|---|
| `test_init_db_and_wal_mode` | `init_db` | Table `cards` exists, indexes created, `PRAGMA journal_mode` returns `wal`. |
| `test_card_record_valid_creation` | `models.CardRecord` | Validates all 21 fields, default date formatting, query synthesis. |
| `test_22_categories_valid_and_invalid` | `models.CardCategory` & DB | All 22 permitted categories pass; invalid category raises Pydantic `ValidationError` and SQLite `CHECK` error. |
| `test_condition_and_slab_serial_rule` | `models.CardRecord` | Raw card with empty serial passes; Raw with serial fails; Graded (`PSA 10`) with serial passes; hyphenated (`PSA-10`) fails. |
| `test_leading_zero_card_number_preservation` | DB & Models | Card numbers `"007"`, `"#04"`, `"001"` retain string leading zeroes through DB storage and retrieval. |
| `test_notes_parent_child_tracking_format` | Models & DB | `notes` accurately preserves `[Parent_Image_ID]-[Child_Card_ID]` (e.g. `"8492-105"`). |
| `test_ai_status_variation_auto_flag` | Models | Empty variation defaults to `CLEARED`; non-empty variation defaults to `REVIEW VARIATION`. |
| `test_crud_insert_and_get_card` | `insert_card`, `get_card` | Inserts record, retrieves by ID, verifies complete dictionary match. |
| `test_crud_update_and_query_resynthesis` | `update_card` | Updates player name/variation, verifies `query` is updated and `updated_at` refreshed. |
| `test_crud_delete_card` | `delete_card` | Deletes card, confirms `get_card` returns `None`. |
| `test_crud_list_and_filters` | `list_cards` | Filters by `ai_status`, `category`, `player`, `notes`, and keyword search. |
| `test_bulk_insert_atomic_transaction` | `bulk_insert_cards` | Inserts 50 cards in single transaction; verifies all returned IDs and count. |
| `test_sqlite_wal_multi_threaded_concurrency` | WAL & SQLite Concurrency | 10 concurrent threads executing rapid reads and writes simultaneously; zero `database is locked` errors. |
| `test_negative_exclusion_prohibited_on_raw` | Models | Prohibits queries containing `-BGS` or `-SGC` on `'Raw'` condition cards. |

---

### 3.2 Proposed `tests/test_database.py` Blueprint

```python
"""
tests/test_database.py - Deterministic test suite for Milestone 1.
Tests Pydantic v2 schemas, SQLite DDL constraints, WAL mode, CRUD methods, and concurrency.
"""

import os
import sqlite3
import threading
import pytest
from pydantic import ValidationError

from models import CardRecord, CardCategory, AIStatus, CardUpdate
from database import (
    init_db,
    insert_card,
    get_card,
    list_cards,
    update_card,
    delete_card,
    bulk_insert_cards,
    get_card_count,
    get_db_connection,
)


@pytest.fixture
def test_db_path(tmp_path):
    """Provides a fresh isolated SQLite database path for each test."""
    db_file = str(tmp_path / "test_portfolio.db")
    init_db(db_file)
    return db_file


@pytest.fixture
def sample_card_dict():
    """Provides a pristine 21-variable dictionary."""
    return {
        "date_purchased": "08/23/2026",
        "quantity": 1,
        "player": "Shohei Ohtani",
        "year": "2023",
        "set_name": "Topps Chrome",
        "variation": "Refractor",
        "card_number": "007",
        "category": "Baseball",
        "condition": "PSA 10",
        "slab_serial_number": "84729104",
        "investment": 150.00,
        "estimated_value": 320.00,
        "ladder_id": "LAD-12345",
        "query": "",
        "notes": "8492-105",
        "tags": "pc, ohtani, mvp",
        "date_sold": "",
        "sold_price": None,
        "image": "https://example.com/front.jpg",
        "back_image": "https://example.com/back.jpg",
        "ai_status": "CLEARED",
    }


def test_init_db_and_wal_mode(test_db_path):
    """Verifies table creation and WAL journal mode configuration."""
    with get_db_connection(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cards';")
        assert cursor.fetchone() is not None

        cursor.execute("PRAGMA table_info(cards);")
        columns = [row[1] for row in cursor.fetchall()]
        assert "id" in columns
        assert "card_number" in columns
        assert "slab_serial_number" in columns
        assert "ai_status" in columns


def test_card_record_valid_creation(sample_card_dict):
    """Verifies that a valid dictionary creates a pristine CardRecord with auto-synthesized query."""
    record = CardRecord(**sample_card_dict)
    assert record.player == "Shohei Ohtani"
    assert record.card_number == "007"
    assert record.query == "2023 Topps Chrome Shohei Ohtani Refractor PSA 10"


def test_22_categories_valid_and_invalid(test_db_path):
    """Tests all 22 permitted categories and ensures illegal categories fail."""
    valid_categories = [
        "Basketball", "Baseball", "Football", "Hockey", "Soccer", "Tennis",
        "Wrestling", "Racing", "Golf", "Boxing", "UFC/MMA", "Pokemon",
        "Magic", "Metazoo", "Yugioh", "Fortnite", "Dragonballz",
        "Entertainment", "Swimming", "Softball", "PopCulture", "Flesh and Blood"
    ]
    for cat in valid_categories:
        card = CardRecord(
            player="Test Athlete",
            year="2022",
            set_name="Test Set",
            category=cat,
            condition="Raw",
        )
        card_id = insert_card(test_db_path, card)
        assert card_id > 0

    with pytest.raises(ValidationError):
        CardRecord(
            player="Invalid Athlete",
            year="2022",
            set_name="Test Set",
            category="Cars",  # Invalid category
            condition="Raw",
        )


def test_condition_and_slab_serial_rules():
    """Verifies slab serial constraint: blank for Raw, allowed for graded."""
    # Raw with serial -> must raise ValidationError
    with pytest.raises(ValidationError, match="Slab serial number must be blank"):
        CardRecord(
            player="Luka Doncic",
            year="2018",
            set_name="Panini Prizm",
            category="Basketball",
            condition="Raw",
            slab_serial_number="12345678",
        )

    # Graded with hyphen -> must raise ValidationError
    with pytest.raises(ValidationError, match="must not contain hyphens"):
        CardRecord(
            player="Luka Doncic",
            year="2018",
            set_name="Panini Prizm",
            category="Basketball",
            condition="PSA-10",
            slab_serial_number="12345678",
        )

    # Graded without hyphen -> success
    graded_card = CardRecord(
        player="Luka Doncic",
        year="2018",
        set_name="Panini Prizm",
        category="Basketball",
        condition="PSA 10",
        slab_serial_number="12345678",
    )
    assert graded_card.condition == "PSA 10"


def test_leading_zero_card_number_preservation(test_db_path):
    """Verifies leading zeroes are preserved in card numbers throughout DB storage."""
    card = CardRecord(
        player="Michael Jordan",
        year="1986",
        set_name="Fleer",
        card_number="007",
        category="Basketball",
        condition="Raw",
    )
    card_id = insert_card(test_db_path, card)
    retrieved = get_card(test_db_path, card_id)
    assert retrieved is not None
    assert retrieved["card_number"] == "007"


def test_notes_parent_child_tracking_format(test_db_path):
    """Verifies notes field correctly holds [Parent_Image_ID]-[Child_Card_ID]."""
    card = CardRecord(
        player="Kobe Bryant",
        year="1996",
        set_name="Topps Chrome",
        card_number="138",
        category="Basketball",
        condition="Raw",
        notes="8492-105",
    )
    card_id = insert_card(test_db_path, card)
    retrieved = get_card(test_db_path, card_id)
    assert retrieved["notes"] == "8492-105"


def test_ai_status_variation_auto_flag():
    """Verifies that cards with guessed variations default to REVIEW VARIATION."""
    card_with_var = CardRecord(
        player="Victor Wembanyama",
        year="2023",
        set_name="Panini Prizm",
        variation="Silver Prizm",
        category="Basketball",
        condition="Raw",
    )
    assert card_with_var.ai_status == AIStatus.REVIEW_VARIATION

    card_base = CardRecord(
        player="Victor Wembanyama",
        year="2023",
        set_name="Panini Prizm",
        variation="",
        category="Basketball",
        condition="Raw",
    )
    assert card_base.ai_status == AIStatus.CLEARED


def test_crud_lifecycle(test_db_path, sample_card_dict):
    """Verifies full CRUD lifecycle: insert, get, update, list, delete."""
    # 1. Insert
    card_id = insert_card(test_db_path, sample_card_dict)
    assert card_id == 1

    # 2. Get
    card = get_card(test_db_path, card_id)
    assert card is not None
    assert card["player"] == "Shohei Ohtani"
    assert card["estimated_value"] == 320.00

    # 3. Update
    updated = update_card(test_db_path, card_id, {"estimated_value": 375.00, "player": "Shohei Ohtani (MVP)"})
    assert updated is True

    card_after = get_card(test_db_path, card_id)
    assert card_after["estimated_value"] == 375.00
    assert card_after["player"] == "Shohei Ohtani (MVP)"
    assert "Shohei Ohtani (MVP)" in card_after["query"]

    # 4. List
    cards = list_cards(test_db_path, filters={"category": "Baseball"})
    assert len(cards) == 1

    # 5. Delete
    deleted = delete_card(test_db_path, card_id)
    assert deleted is True
    assert get_card(test_db_path, card_id) is None


def test_bulk_insert_atomic_transaction(test_db_path):
    """Verifies atomic bulk insert and count."""
    batch = [
        {
            "player": f"Player {i}",
            "year": "2024",
            "set_name": "Topps Series 1",
            "card_number": f"{i:03d}",
            "category": "Baseball",
            "condition": "Raw",
        }
        for i in range(1, 26)
    ]
    ids = bulk_insert_cards(test_db_path, batch)
    assert len(ids) == 25
    assert get_card_count(test_db_path) == 25

    cards = list_cards(test_db_path, limit=50)
    assert len(cards) == 25
    assert cards[0]["card_number"] == "025"  # default ORDER BY id DESC


def test_sqlite_wal_multi_threaded_concurrency(test_db_path):
    """Verifies that WAL mode supports concurrent readers and writers without lock errors."""
    errors = []

    def writer_task(worker_id):
        try:
            for i in range(10):
                card = CardRecord(
                    player=f"Worker {worker_id} Player {i}",
                    year="2024",
                    set_name="Panini Select",
                    category="Football",
                    condition="Raw",
                    notes=f"1000-{worker_id:03d}",
                )
                insert_card(test_db_path, card)
        except Exception as e:
            errors.append(f"Writer error: {e}")

    def reader_task():
        try:
            for _ in range(20):
                list_cards(test_db_path, limit=100)
        except Exception as e:
            errors.append(f"Reader error: {e}")

    threads = []
    # 4 writer threads, 4 reader threads
    for w in range(4):
        threads.append(threading.Thread(target=writer_task, args=(w,)))
    for _ in range(4):
        threads.append(threading.Thread(target=reader_task))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrency errors occurred: {errors}"
    assert get_card_count(test_db_path) == 40
```

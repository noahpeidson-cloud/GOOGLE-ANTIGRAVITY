"""
database.py - SQLite3 storage engine for the Sports Card Ecosystem Hub.
Provides WAL mode concurrency, strict schema DDL, indexing, and complete CRUD operations.
"""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Generator, Any, Optional

from models import (
    CardRecord,
    CardUpdate,
    AIStatus,
    CardCategory,
    CardCaptureRequest,
    synthesize_query,
    calculate_query,
    format_notes,
)

DEFAULT_DB_PATH = "portfolio.db"
CIRCUIT_BREAKER_BATCH_LIMIT = 500


@contextmanager
def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager that provides a SQLite connection configured with WAL mode,
    5000ms busy timeout, NORMAL synchronous mode, foreign keys, UTF-8, and sqlite3.Row factory.
    """
    # Ensure parent directory exists if path contains directories
    parent_dir = os.path.dirname(db_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.text_factory = str

    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA encoding = 'UTF-8';")
    cursor.close()

    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes the database schema, check constraints, and performance indexes."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_purchased TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity >= 1),
            player TEXT NOT NULL CHECK(length(trim(player)) > 0),
            year TEXT NOT NULL CHECK(length(year) = 4 AND year GLOB '[0-9][0-9][0-9][0-9]'),
            set_name TEXT NOT NULL CHECK(length(trim(set_name)) > 0),
            variation TEXT NOT NULL DEFAULT '',
            card_number TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL CHECK(category IN (
                'Basketball', 'Baseball', 'Football', 'Hockey', 'Soccer', 'Tennis',
                'Wrestling', 'Racing', 'Golf', 'Boxing', 'UFC/MMA', 'Pokemon',
                'Magic', 'Metazoo', 'Yugioh', 'Fortnite', 'Dragonballz',
                'Entertainment', 'Swimming', 'Softball', 'PopCulture', 'Flesh and Blood'
            )),
            condition TEXT NOT NULL,
            slab_serial_number TEXT NOT NULL DEFAULT '',
            investment REAL NOT NULL DEFAULT 0.0 CHECK(investment >= 0.0),
            estimated_value REAL NOT NULL DEFAULT 0.0 CHECK(estimated_value >= 0.0),
            ladder_id TEXT NOT NULL DEFAULT '',
            query TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '',
            date_sold TEXT NOT NULL DEFAULT '',
            sold_price REAL DEFAULT NULL CHECK(sold_price IS NULL OR sold_price >= 0.0),
            image TEXT NOT NULL DEFAULT '',
            back_image TEXT NOT NULL DEFAULT '',
            ai_status TEXT NOT NULL DEFAULT 'CLEARED' CHECK(ai_status IN ('CLEARED', 'REVIEW VARIATION', 'NEEDS REVIEW')),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT check_raw_no_slab CHECK(
                (condition = 'Raw' AND (slab_serial_number = '' OR slab_serial_number IS NULL))
                OR
                (condition != 'Raw')
            ),
            CONSTRAINT check_raw_no_negative_exclusions CHECK(
                NOT (condition = 'Raw' AND (
                    query LIKE '%-BGS%' OR query LIKE '%-SGC%' OR query LIKE '%-PSA%' OR query LIKE '%-CGC%' OR query LIKE '%-CSG%' OR query LIKE '%-BVG%'
                ))
            )
        );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_ai_status ON cards(ai_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_category ON cards(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_player ON cards(player);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_year_set ON cards(year, set_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_notes ON cards(notes);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_query ON cards(query);")
        conn.commit()


def _resolve_card_and_db_path(arg1: Any, arg2: Any, db_path: Optional[str]) -> tuple[Any, str]:
    """Helper to flexibly support (db_path, card_data) or (card_data, db_path=...)."""
    if isinstance(arg1, str) and (isinstance(arg2, (dict, CardRecord)) or arg2 is not None):
        return arg2, arg1
    actual_db = arg2 if (isinstance(arg2, str) and arg2) else (db_path or DEFAULT_DB_PATH)
    return arg1, actual_db


def insert_card(
    arg1: Any,
    arg2: Any = None,
    db_path: Optional[str] = None
) -> int:
    """
    Validates and inserts a single card into the database.
    Accepts insert_card(card_data, db_path=DEFAULT_DB_PATH) or insert_card(db_path, card_data).
    Returns the integer ID of the inserted record.
    """
    card_data, actual_db = _resolve_card_and_db_path(arg1, arg2, db_path)

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
    with get_db_connection(actual_db) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, data)
        conn.commit()
        return cursor.lastrowid


def insert_cards_batch(
    arg1: Any,
    arg2: Any = None,
    chunk_size: int = CIRCUIT_BREAKER_BATCH_LIMIT,
    db_path: Optional[str] = None
) -> list[int]:
    """
    Atomically inserts a batch of cards in a transaction.
    Accepts insert_cards_batch(cards, db_path=DEFAULT_DB_PATH) or insert_cards_batch(db_path, cards).
    Returns a list of generated integer card IDs.
    """
    if isinstance(arg1, str) and isinstance(arg2, list):
        actual_db = arg1
        card_list = arg2
    elif isinstance(arg1, list):
        card_list = arg1
        actual_db = arg2 if isinstance(arg2, str) else (db_path or DEFAULT_DB_PATH)
    else:
        raise TypeError("Invalid arguments for insert_cards_batch")

    if not card_list:
        return []

    # Validate all records before executing SQL
    validated_records = []
    for item in card_list:
        if isinstance(item, dict):
            validated_records.append(CardRecord(**item).model_dump())
        elif isinstance(item, CardRecord):
            validated_records.append(item.model_dump())
        else:
            raise TypeError(f"Each item in batch must be a dict or CardRecord, got {type(item)}")

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

    # Process in chunks of chunk_size (default 500)
    with get_db_connection(actual_db) as conn:
        cursor = conn.cursor()
        for i in range(0, len(validated_records), chunk_size):
            chunk = validated_records[i : i + chunk_size]
            for rec in chunk:
                cursor.execute(sql, rec)
                inserted_ids.append(cursor.lastrowid)
        conn.commit()

    return inserted_ids


bulk_insert_cards = insert_cards_batch


def get_card_by_id(
    arg1: Any,
    arg2: Any = None,
    db_path: Optional[str] = None
) -> Optional[dict[str, Any]]:
    """
    Retrieves a single card by ID.
    Accepts get_card_by_id(card_id, db_path=DEFAULT_DB_PATH) or get_card_by_id(db_path, card_id).
    """
    if isinstance(arg1, str) and (isinstance(arg2, int) or (isinstance(arg2, str) and arg2.isdigit())):
        actual_db = arg1
        card_id = int(arg2)
    else:
        card_id = int(arg1)
        actual_db = arg2 if isinstance(arg2, str) else (db_path or DEFAULT_DB_PATH)

    with get_db_connection(actual_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE id = ?;", (card_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)


get_card = get_card_by_id


def get_all_cards(
    status_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
    order_by: str = "id DESC",
    db_path: str = DEFAULT_DB_PATH,
    filters: Optional[dict[str, Any]] = None
) -> list[dict[str, Any]]:
    """
    Queries staging records with dynamic filtering and pagination.
    Supports filters dictionary or direct kwargs.
    """
    query = "SELECT * FROM cards WHERE 1=1"
    params: list[Any] = []

    active_filters = dict(filters) if filters else {}
    if status_filter and "ai_status" not in active_filters:
        active_filters["ai_status"] = status_filter
    if category_filter and "category" not in active_filters:
        active_filters["category"] = category_filter
    if search_query and "search" not in active_filters:
        active_filters["search"] = search_query

    if "ai_status" in active_filters and active_filters["ai_status"]:
        if active_filters["ai_status"].upper() != "ALL":
            query += " AND ai_status = ?"
            params.append(active_filters["ai_status"])

    if "category" in active_filters and active_filters["category"]:
        if active_filters["category"].upper() != "ALL":
            query += " AND category = ?"
            params.append(active_filters["category"])

    if "player" in active_filters and active_filters["player"]:
        query += " AND player LIKE ?"
        params.append(f"%{active_filters['player']}%")

    if "year" in active_filters and active_filters["year"]:
        query += " AND year = ?"
        params.append(active_filters["year"])

    if "set_name" in active_filters and active_filters["set_name"]:
        query += " AND set_name LIKE ?"
        params.append(f"%{active_filters['set_name']}%")

    if "condition" in active_filters and active_filters["condition"]:
        query += " AND condition = ?"
        params.append(active_filters["condition"])

    if "notes" in active_filters and active_filters["notes"]:
        query += " AND notes LIKE ?"
        params.append(f"%{active_filters['notes']}%")

    if "search" in active_filters and active_filters["search"]:
        s = f"%{active_filters['search']}%"
        query += " AND (player LIKE ? OR set_name LIKE ? OR query LIKE ? OR notes LIKE ?)"
        params.extend([s, s, s, s])

    allowed_order = {
        "id ASC", "id DESC",
        "date_purchased ASC", "date_purchased DESC",
        "player ASC", "player DESC",
        "estimated_value ASC", "estimated_value DESC",
        "created_at ASC", "created_at DESC"
    }
    if order_by not in allowed_order:
        order_by = "id DESC"

    query += f" ORDER BY {order_by} LIMIT ? OFFSET ?;"
    params.extend([limit, offset])

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def list_cards(
    db_path: str = DEFAULT_DB_PATH,
    filters: Optional[dict[str, Any]] = None,
    limit: int = 500,
    offset: int = 0,
    order_by: str = "id DESC"
) -> list[dict[str, Any]]:
    """Alias for list_cards(db_path, filters=...) matching explorer analysis."""
    return get_all_cards(
        filters=filters,
        limit=limit,
        offset=offset,
        order_by=order_by,
        db_path=db_path
    )


def update_card(
    arg1: Any,
    arg2: Any,
    arg3: Any = None,
    db_path: Optional[str] = None
) -> bool:
    """
    Updates specific fields of an existing card by ID.
    Accepts update_card(card_id, updates, db_path=DEFAULT_DB_PATH) or update_card(db_path, card_id, updates).
    Recalculates 'query' if player, year, set_name, variation, or condition are modified.
    Returns True if updated, False if card_id not found.
    """
    if isinstance(arg1, str) and (isinstance(arg2, int) or (isinstance(arg2, str) and arg2.isdigit())):
        actual_db = arg1
        card_id = int(arg2)
        updates = arg3
    else:
        card_id = int(arg1)
        updates = arg2
        actual_db = arg3 if isinstance(arg3, str) else (db_path or DEFAULT_DB_PATH)

    existing = get_card_by_id(card_id, actual_db)
    if existing is None:
        return False

    update_dict = updates.model_dump(exclude_unset=True) if isinstance(updates, CardUpdate) else dict(updates)
    if not update_dict:
        return True

    # Merge existing and new updates
    merged = {**existing, **update_dict}
    merged.pop("id", None)
    merged.pop("created_at", None)
    merged.pop("updated_at", None)

    # Re-synthesize query if constituent fields are updated and query wasn't explicitly supplied in updates
    query_affecting = {"year", "set_name", "player", "variation", "condition"}
    if query_affecting.intersection(update_dict.keys()) and "query" not in update_dict:
        merged["query"] = synthesize_query(
            merged["year"], merged["set_name"], merged["player"],
            merged.get("variation", ""), merged.get("condition", "Raw")
        )

    # Validate merged state through CardRecord
    validated_record = CardRecord(**merged)
    clean_data = validated_record.model_dump()

    set_clauses = [f"{k} = :{k}" for k in clean_data.keys()]
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    sql = f"UPDATE cards SET {', '.join(set_clauses)} WHERE id = :card_id;"

    clean_data["card_id"] = card_id

    with get_db_connection(actual_db) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, clean_data)
        conn.commit()
        return cursor.rowcount > 0


def update_card_status(
    arg1: Any,
    arg2: Any,
    arg3: Any = None,
    db_path: Optional[str] = None
) -> bool:
    """
    Updates the ai_status of a card ('CLEARED', 'REVIEW VARIATION', 'NEEDS REVIEW').
    Accepts update_card_status(card_id, new_status, db_path=DEFAULT_DB_PATH)
    or update_card_status(db_path, card_id, new_status).
    """
    if isinstance(arg1, str) and (isinstance(arg2, int) or (isinstance(arg2, str) and arg2.isdigit())):
        actual_db = arg1
        card_id = int(arg2)
        new_status = str(arg3)
    else:
        card_id = int(arg1)
        new_status = str(arg2)
        actual_db = arg3 if isinstance(arg3, str) else (db_path or DEFAULT_DB_PATH)

    # Validate status enum
    status_val = AIStatus(new_status).value

    sql = "UPDATE cards SET ai_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;"
    with get_db_connection(actual_db) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (status_val, card_id))
        conn.commit()
        return cursor.rowcount > 0


def delete_card(
    arg1: Any,
    arg2: Any = None,
    db_path: Optional[str] = None
) -> bool:
    """
    Deletes a card record by ID.
    Accepts delete_card(card_id, db_path=DEFAULT_DB_PATH) or delete_card(db_path, card_id).
    """
    if isinstance(arg1, str) and (isinstance(arg2, int) or (isinstance(arg2, str) and arg2.isdigit())):
        actual_db = arg1
        card_id = int(arg2)
    else:
        card_id = int(arg1)
        actual_db = arg2 if isinstance(arg2, str) else (db_path or DEFAULT_DB_PATH)

    with get_db_connection(actual_db) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cards WHERE id = ?;", (card_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_cards_for_export(
    status_filter: str = "CLEARED",
    limit: int = 500,
    db_path: str = DEFAULT_DB_PATH
) -> list[dict[str, Any]]:
    """
    Fetches card records for Card Ladder export, ordered by id ASC.
    If status_filter is 'ALL', retrieves all cards up to limit.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if status_filter.upper() == "ALL":
            cursor.execute("SELECT * FROM cards ORDER BY id ASC LIMIT ?;", (limit,))
        else:
            cursor.execute("SELECT * FROM cards WHERE ai_status = ? ORDER BY id ASC LIMIT ?;", (status_filter, limit))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_summary_stats(db_path: str = DEFAULT_DB_PATH) -> dict[str, Any]:
    """
    Returns aggregated KPIs for the dashboard:
    - total_cards
    - total_investment
    - total_estimated_value
    - count_by_category
    - count_by_ai_status
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Aggregates
        cursor.execute("""
        SELECT 
            COUNT(*) as total_cards,
            COALESCE(SUM(investment), 0.0) as total_investment,
            COALESCE(SUM(estimated_value), 0.0) as total_estimated_value
        FROM cards;
        """)
        agg = cursor.fetchone()
        total_cards = agg["total_cards"] if agg else 0
        total_inv = round(float(agg["total_investment"]), 2) if agg else 0.0
        total_est = round(float(agg["total_estimated_value"]), 2) if agg else 0.0

        # By category
        cursor.execute("SELECT category, COUNT(*) as cnt FROM cards GROUP BY category;")
        count_by_cat = {row["category"]: row["cnt"] for row in cursor.fetchall()}

        # By AI status
        cursor.execute("SELECT ai_status, COUNT(*) as cnt FROM cards GROUP BY ai_status;")
        count_by_status = {row["ai_status"]: row["cnt"] for row in cursor.fetchall()}

        return {
            "total_cards": total_cards,
            "total_investment": total_inv,
            "total_estimated_value": total_est,
            "count_by_category": count_by_cat,
            "count_by_ai_status": count_by_status,
        }


def get_next_child_id(parent_image_id: int | str, db_path: str = DEFAULT_DB_PATH) -> int:
    """
    Queries existing cards for the given parent_image_id (via notes matching 'parent-%').
    Returns the next available 3-digit child ID integer (starts at 101).
    """
    try:
        p_int = int(str(parent_image_id).strip())
        parent_prefix = f"{p_int:04d}"
    except ValueError:
        parent_prefix = str(parent_image_id).strip()

    pattern = f"{parent_prefix}-%"
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT notes FROM cards WHERE notes LIKE ?;", (pattern,))
        rows = cursor.fetchall()

    max_child = 100
    for r in rows:
        note_val = r["notes"]
        if "-" in note_val:
            parts = note_val.split("-")
            if len(parts) >= 2 and parts[1].isdigit():
                child_num = int(parts[1])
                if child_num > max_child:
                    max_child = child_num

    return max_child + 1


def clear_staging_table(db_path: str = DEFAULT_DB_PATH) -> int:
    """Deletes all records from the cards table. Returns number of rows deleted."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cards;")
        deleted = cursor.rowcount
        conn.commit()
        return deleted


def get_card_count(db_path: str = DEFAULT_DB_PATH, status_filter: Optional[str] = None) -> int:
    """Returns the total count of cards in the database, optionally filtered by ai_status."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if status_filter:
            cursor.execute("SELECT COUNT(*) FROM cards WHERE ai_status = ?;", (status_filter,))
        else:
            cursor.execute("SELECT COUNT(*) FROM cards;")
        return cursor.fetchone()[0]


def get_staging_count(db_path: str = DEFAULT_DB_PATH) -> int:
    """Alias for get_card_count(db_path)."""
    return get_card_count(db_path)


def check_circuit_breaker(db_path: str = DEFAULT_DB_PATH, threshold: int = CIRCUIT_BREAKER_BATCH_LIMIT) -> dict[str, Any]:
    """
    Checks if active staging table has reached or exceeded the 500-card batch limit.
    Returns: {"total_staged": count, "circuit_breaker_tripped": count >= threshold}
    """
    count = get_card_count(db_path)
    return {
        "total_staged": count,
        "circuit_breaker_tripped": count >= threshold,
    }


def capture_card_from_api(payload: dict[str, Any], db_path: str = DEFAULT_DB_PATH) -> dict[str, Any]:
    """
    Validates Chrome Extension POST payload, inserts record, and returns standard response:
    {
        "status": "success",
        "card_id": int,
        "query": str,
        "notes": str,
        "ai_status": str
    }
    """
    req = CardCaptureRequest(**payload)
    card_dict = req.model_dump()
    card_id = insert_card(card_dict, db_path=db_path)
    inserted = get_card_by_id(card_id, db_path=db_path)
    return {
        "status": "success",
        "card_id": card_id,
        "query": inserted["query"] if inserted else "",
        "notes": inserted["notes"] if inserted else "",
        "ai_status": inserted["ai_status"] if inserted else "",
    }

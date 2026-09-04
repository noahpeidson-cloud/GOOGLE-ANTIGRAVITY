"""
scraper_ingest.py - Checklist Scraper Ingestion Pipeline for Sports Card Ecosystem Hub.
Parses set checklists from Beckett and Cardboard Connection using standard library html.parser.
Supports table and list layouts, leading zero preservation, rookie flag detection,
parallel expansion, and offline fallback.
"""

from __future__ import annotations

import logging
import os
import re
from html import unescape
from html.parser import HTMLParser
from typing import Any, List, Optional, Union
import requests
from pydantic import BaseModel, Field

from models import (
    AIStatus,
    CardCategory,
    CardExtractionSchema,
    CardRecord,
    CATEGORY_MAP,
    VALID_CATEGORIES,
    format_notes,
    get_current_date_str,
    synthesize_query,
)
from database import (
    DEFAULT_DB_PATH,
    CIRCUIT_BREAKER_BATCH_LIMIT,
    get_next_child_id,
    insert_card,
    insert_cards_batch,
)

logger = logging.getLogger(__name__)


class ChecklistCard(BaseModel):
    """Raw parsed card item from checklist HTML."""
    card_number: str
    player: str
    team: str = ""
    is_rookie: bool = False
    raw_text: str = ""


class ChecklistMetadata(BaseModel):
    """Extracted checklist header metadata."""
    title: str = ""
    set_name: str = ""
    year: str = ""
    category: str = ""
    release_date: str = ""
    parallels: list[str] = []


class ChecklistHTMLParser(HTMLParser):
    """
    Zero-dependency HTML Parser utilizing Python's built-in html.parser.HTMLParser.
    Extracts headers, tables, lists, and parallel metadata from Beckett & Cardboard Connection HTML.
    Supports unclosed HTML tags and streaming auto-flush.
    """
    def __init__(self):
        super().__init__()
        self.title: str = ""
        self.headings: list[tuple[str, str]] = []
        self.tables: list[tuple[str, list[list[str]]]] = []
        self.current_table: list[list[str]] = []
        self.current_row: list[str] = []
        self.current_cell: list[str] = []
        self.list_items: list[tuple[str, str]] = []
        self.current_heading: str = ""

        self._in_tag: Optional[str] = None
        self._in_table: bool = False
        self._in_cell: bool = False
        self._in_li: bool = False
        self._in_heading: bool = False
        self._heading_buf: list[str] = []

    def _flush_cell(self):
        if self._in_cell:
            cell_str = unescape(" ".join("".join(self.current_cell).split()).strip())
            self.current_row.append(cell_str)
            self.current_cell = []
            self._in_cell = False

    def _flush_row(self):
        self._flush_cell()
        if any(cell.strip() for cell in self.current_row):
            self.current_table.append(self.current_row)
        self.current_row = []

    def _flush_table(self):
        self._flush_row()
        if self.current_table:
            self.tables.append((self.current_heading, self.current_table))
        self.current_table = []
        self._in_table = False

    def _flush_li(self):
        if self._in_li:
            li_str = unescape(" ".join("".join(self.current_cell).split()).strip())
            if li_str:
                self.list_items.append((self.current_heading, li_str))
            self.current_cell = []
            self._in_li = False

    def _flush_heading(self):
        if self._in_heading:
            txt = unescape(" ".join("".join(self._heading_buf).split()).strip())
            if self._in_tag == "title":
                self.title = txt
            else:
                self.headings.append((self._in_tag or "h", txt))
                self.current_heading = txt
            self._heading_buf = []
            self._in_heading = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        t = tag.lower()
        if t in ("h1", "h2", "h3", "h4", "h5", "h6", "title"):
            self._flush_heading()
            self._in_heading = True
            self._in_tag = t
            self._heading_buf = []
        elif t in ("table", "tr", "td", "th", "ul", "ol", "li", "p", "div", "section", "article"):
            self._flush_heading()
            if t == "table":
                self._flush_table()
                self._in_table = True
            elif t == "tr":
                if not self._in_table:
                    self._in_table = True
                self._flush_row()
            elif t in ("td", "th"):
                if not self._in_table:
                    self._in_table = True
                self._flush_cell()
                self._in_cell = True
                self.current_cell = []
            elif t == "li":
                self._flush_li()
                self._in_li = True
                self.current_cell = []

    def handle_endtag(self, tag: str):
        t = tag.lower()
        if t in ("h1", "h2", "h3", "h4", "h5", "h6", "title") and self._in_heading:
            self._flush_heading()
        elif t in ("td", "th") and self._in_cell:
            self._flush_cell()
        elif t == "tr":
            self._flush_row()
        elif t == "table" and self._in_table:
            self._flush_table()
        elif t == "li" and self._in_li:
            self._flush_li()

    def handle_data(self, data: str):
        if self._in_heading:
            self._heading_buf.append(data)
        elif self._in_cell or self._in_li:
            self.current_cell.append(data)

    def close(self):
        self._flush_heading()
        self._flush_li()
        self._flush_table()
        super().close()


def infer_metadata_from_text(text: str) -> dict[str, str]:
    """Infers Year, Category, and Set Name from heading/title text."""
    meta = {"year": "", "set_name": "", "category": ""}
    if not text:
        return meta

    unescaped_text = unescape(text)

    # 1. Year extraction (4 digits)
    year_match = re.search(r"\b(19\d{2}|20\d{2})(?:[-\/]\d{2,4})?\b", unescaped_text)
    if year_match:
        meta["year"] = year_match.group(1)

    # 2. Category extraction
    low = unescaped_text.lower()
    matched_cat_term = ""
    for key, cat in CATEGORY_MAP.items():
        if re.search(r"\b" + re.escape(key) + r"\b", low):
            meta["category"] = cat
            matched_cat_term = key
            break
    if not meta["category"]:
        for cat in VALID_CATEGORIES:
            if re.search(r"\b" + re.escape(cat.lower()) + r"\b", low):
                meta["category"] = cat
                matched_cat_term = cat.lower()
                break

    # 3. Set Name extraction
    clean_set = unescaped_text
    if meta["year"]:
        clean_set = re.sub(r"\b" + re.escape(meta["year"]) + r"(?:[-\/]\d{2,4})?\b", "", clean_set)
    if matched_cat_term:
        clean_set = re.sub(r"\b" + re.escape(matched_cat_term) + r"\b", "", clean_set, flags=re.IGNORECASE)
    if meta["category"]:
        clean_set = re.sub(r"\b" + re.escape(meta["category"]) + r"\b", "", clean_set, flags=re.IGNORECASE)

    clean_set = re.sub(
        r"\b(Checklist|Set Info|Boxes|Cards|Odds|Guide|Breakdown|Complete Set|Base Set|Release Date|Details|Team Set Lists)\b",
        "",
        clean_set,
        flags=re.IGNORECASE,
    )
    clean_set = re.sub(r"\s+", " ", clean_set).strip(" ,-:|")
    if clean_set:
        meta["set_name"] = clean_set

    return meta


def _clean_field_and_extract_rc(text: str) -> tuple[str, bool]:
    """Helper to unescape text, extract rookie flag, and clean name without stripping valid punctuation."""
    unescaped = unescape(text)
    is_rc = bool(re.search(r"(?:\((?:RC|Rookie)\)|\[(?:RC|Rookie)\]|\b(?:RC|Rookie)\b)", unescaped, re.IGNORECASE))
    cleaned = re.sub(r"(?:\((?:RC|Rookie)\)|\[(?:RC|Rookie)\]|\b(?:RC|Rookie)\b)", "", unescaped, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(\s*\)|\[\s*\]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,\t\n\r")
    return cleaned, is_rc


def parse_checklist_line(line: str) -> Optional[ChecklistCard]:
    """Parses a single textual line or list item into a ChecklistCard."""
    raw = unescape(line)
    clean = " ".join(raw.split()).strip()
    if not clean:
        return None

    low = clean.lower()
    if low.startswith(("card #", "number", "card number", "base set checklist", "release date", "parallels", "parallels breakdown")):
        return None

    num_match = re.match(r"^(?:#\s*)?([A-Za-z0-9]+(?:[\/\-][A-Za-z0-9]+)*)\s+(.*)$", clean)
    if not num_match:
        split_line = re.split(r"\s{2,}|\t", clean, maxsplit=1)
        if len(split_line) == 2:
            card_num = split_line[0].strip().lstrip("#")
            rest = split_line[1].strip()
        else:
            return None
    else:
        card_num = num_match.group(1).strip()
        rest = num_match.group(2).strip()

    parts = re.split(r"\s+[\-\–\—]\s+|\s*,\s*|\s*\|\s*|\t+", rest, maxsplit=1)
    if len(parts) == 2:
        player_raw, team_raw = parts[0].strip(), parts[1].strip()
    else:
        player_raw = rest.strip()
        team_raw = ""

    player, rc1 = _clean_field_and_extract_rc(player_raw)
    team, rc2 = _clean_field_and_extract_rc(team_raw)
    is_rookie = rc1 or rc2 or bool(re.search(r"\b(?:RC|Rookie)\b", clean, re.IGNORECASE))

    if not card_num or not player:
        return None

    return ChecklistCard(
        card_number=card_num,
        player=player,
        team=team,
        is_rookie=is_rookie,
        raw_text=clean,
    )


def parse_checklist_table_row(row: list[str]) -> Optional[ChecklistCard]:
    """Parses a table row (list of cell strings) into a ChecklistCard."""
    if not row or len(row) < 2:
        return None

    unescaped_row = [unescape(cell.strip()) for cell in row]
    first_cell = unescaped_row[0].lower()
    if first_cell in ("card #", "card no", "card number", "#", "number", "no.", "no", "card", "card / subject"):
        return None

    card_num = unescaped_row[0].lstrip("#").strip()
    player_cell = unescaped_row[1].strip()
    team_cell = unescaped_row[2].strip() if len(unescaped_row) > 2 else ""

    player, rc1 = _clean_field_and_extract_rc(player_cell)
    team, rc2 = _clean_field_and_extract_rc(team_cell)
    is_rookie = rc1 or rc2 or bool(re.search(r"\b(?:RC|Rookie)\b", " ".join(unescaped_row), re.IGNORECASE))

    if not card_num or not player:
        return None

    return ChecklistCard(
        card_number=card_num,
        player=player,
        team=team,
        is_rookie=is_rookie,
        raw_text=" | ".join(unescaped_row),
    )


def extract_parallels_from_html(parser: ChecklistHTMLParser) -> list[str]:
    """Extracts parallel variation names from list items under parallel/variation headings."""
    parallels = []
    for heading, item in parser.list_items:
        h_low = heading.lower()
        if any(keyword in h_low for keyword in ("parallel", "variation", "prizm", "refractor", "colors", "inserts", "breakdown")):
            clean_item = " ".join(item.split()).strip()
            if clean_item and len(clean_item) < 80 and not clean_item.lower().startswith(("card", "base set", "#", "no")):
                parallels.append(clean_item)
    return parallels


def expand_parallels(
    cards: list[Any],
    parallels: Optional[list[str]] = None,
    default_year: str = "2024",
    default_set: str = "Base Set",
    default_category: str = "Basketball",
) -> list[CardExtractionSchema]:
    """
    Expands base checklist cards across a list of parallel variations.
    - If parallel is '' or 'Base', sets variation='' and ai_status=CLEARED.
    - If parallel is non-empty, sets variation=parallel and ai_status=REVIEW VARIATION.
    """
    if not parallels:
        parallels = [""]

    expanded: list[CardExtractionSchema] = []
    for c in cards:
        if isinstance(c, ChecklistCard):
            card_num = c.card_number
            player = c.player
            year = default_year
            set_name = default_set
            cat = default_category
            notes = c.team
        elif isinstance(c, CardExtractionSchema):
            card_num = c.card_number
            player = c.player
            year = c.year
            set_name = c.set_name
            cat = c.category
            notes = c.notes
        else:  # dict
            card_num = str(c.get("card_number", ""))
            player = str(c.get("player", ""))
            year = str(c.get("year", default_year))
            set_name = str(c.get("set_name", default_set))
            cat = str(c.get("category", default_category))
            notes = str(c.get("notes", c.get("team", "")))

        # Normalize category
        cat_val = CATEGORY_MAP.get(str(cat).lower(), str(cat))
        if cat_val not in VALID_CATEGORIES:
            cat_val = CardCategory.BASKETBALL.value

        for p in parallels:
            p_clean = p.strip()
            if p_clean.lower() in ("", "base", "base set"):
                variation_val = ""
                ai_status_val = AIStatus.CLEARED
            else:
                variation_val = p_clean
                ai_status_val = AIStatus.REVIEW_VARIATION

            card_schema = CardExtractionSchema(
                player=player,
                year=year,
                set_name=set_name,
                variation=variation_val,
                card_number=card_num,
                category=cat_val,
                condition="Raw",
                slab_serial_number="",
                estimated_value=0.0,
                notes=notes,
                image="",
                back_image="",
                ai_status=ai_status_val,
            )
            expanded.append(card_schema)

    return expanded


expand_checklist_parallels = expand_parallels


def parse_checklist_html(
    html_content: str,
    set_name: str = "",
    year: str = "",
    category: str = "",
    parallels: Optional[list[str]] = None,
) -> list[CardExtractionSchema]:
    """
    High-level entry point: parses raw HTML content into a list of validated CardExtractionSchema instances.
    """
    if not html_content or not html_content.strip():
        return []

    parser = ChecklistHTMLParser()
    parser.feed(html_content)
    parser.close()

    header_candidate = parser.title or (parser.headings[0][1] if parser.headings else "")
    inferred = infer_metadata_from_text(header_candidate)

    final_year = year or inferred.get("year") or "2024"
    final_set = set_name or inferred.get("set_name") or "Checklist Set"
    final_cat = category or inferred.get("category") or "Basketball"

    raw_cards: list[ChecklistCard] = []
    for heading, table in parser.tables:
        for row in table:
            entry = parse_checklist_table_row(row)
            if entry:
                raw_cards.append(entry)

    if not raw_cards:
        for heading, item in parser.list_items:
            h_low = heading.lower()
            if not any(k in h_low for k in ("parallel", "variation", "prizm", "refractor", "odds", "breakdown")):
                entry = parse_checklist_line(item)
                if entry:
                    raw_cards.append(entry)

    if parallels is None:
        detected_parallels = extract_parallels_from_html(parser)
        if detected_parallels:
            parallels_to_use = ["Base"] + detected_parallels
        else:
            parallels_to_use = ["Base"]
    else:
        parallels_to_use = parallels

    return expand_parallels(raw_cards, parallels_to_use, final_year, final_set, final_cat)


def fetch_checklist_url(url: str, timeout: float = 10.0, headers: Optional[dict[str, str]] = None) -> str:
    """Fetches checklist HTML from remote URL with standard User-Agent."""
    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }
    if headers:
        default_headers.update(headers)

    resp = requests.get(url, headers=default_headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_and_parse_checklist(
    url: str,
    set_name: str = "",
    year: str = "",
    category: str = "",
    parallels: Optional[list[str]] = None,
    fallback_fixture_path: Optional[str] = None,
) -> list[CardExtractionSchema]:
    """
    Fetches checklist HTML from URL and parses it.
    Gracefully falls back to fallback_fixture_path if network fails.
    """
    try:
        html = fetch_checklist_url(url)
    except Exception as e:
        if fallback_fixture_path and os.path.exists(fallback_fixture_path):
            logger.warning(f"Failed to fetch '{url}', falling back to fixture '{fallback_fixture_path}': {e}")
            with open(fallback_fixture_path, "r", encoding="utf-8") as f:
                html = f.read()
        else:
            raise RuntimeError(f"Failed to fetch checklist from '{url}' and no valid fallback fixture: {e}") from e

    return parse_checklist_html(html, set_name=set_name, year=year, category=category, parallels=parallels)


scrape_checklist_url = fetch_and_parse_checklist


def ingest_scraper_cards(
    extractions: list[Union[CardExtractionSchema, dict[str, Any]]],
    parent_id: Optional[Union[int, str]] = None,
    date_purchased: Optional[str] = None,
    investment: float = 0.0,
    db_path: str = DEFAULT_DB_PATH,
    chunk_size: int = CIRCUIT_BREAKER_BATCH_LIMIT,
) -> list[int]:
    """Bridges batch scraper checklist extractions into database with sequential notes."""
    if not extractions:
        return []

    start_child_id = get_next_child_id(parent_id, db_path=db_path) if parent_id is not None else None

    records: list[CardRecord] = []
    for idx, ext in enumerate(extractions):
        current_child = (start_child_id + idx) if start_child_id is not None else None
        data = ext.model_dump() if isinstance(ext, CardExtractionSchema) else dict(ext)

        if parent_id is not None and current_child is not None:
            data["notes"] = format_notes(parent_id, current_child)

        data["investment"] = max(0.0, float(investment))
        if date_purchased:
            data["date_purchased"] = date_purchased

        records.append(CardRecord(**data))

    return insert_cards_batch(records, db_path=db_path, chunk_size=chunk_size)


insert_scraped_checklist_to_db = ingest_scraper_cards
ingest_checklist_to_database = ingest_scraper_cards

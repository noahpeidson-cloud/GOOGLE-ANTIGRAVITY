"""
test_scraper_engine.py - Full production-grade Checklist HTML parser.
"""

from __future__ import annotations

import os
import re
import sys
from html import unescape
from html.parser import HTMLParser
from typing import Any, Optional
from pydantic import BaseModel, Field

# Ensure ecosystem_hub is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sports_cards", "ecosystem_hub")))

from models import (
    CardExtractionSchema,
    CardRecord,
    CardCategory,
    AIStatus,
    synthesize_query,
    CATEGORY_MAP,
    VALID_CATEGORIES,
)


class ChecklistCard(BaseModel):
    """Raw parsed checklist card entry."""
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
    Supports unclosed HTML tags and malformed input (auto-flush on new elements and close()).
    """
    def __init__(self):
        super().__init__()
        self.title: str = ""
        self.headings: list[tuple[str, str]] = [] # (tag, text)
        self.tables: list[tuple[str, list[list[str]]]] = [] # (heading, rows)
        self.current_table: list[list[str]] = []
        self.current_row: list[str] = []
        self.current_cell: list[str] = []
        self.list_items: list[tuple[str, str]] = [] # (heading, text)
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

    # 1. Year extraction (4 digits e.g. 2023 or 2023-24 -> 2023)
    year_match = re.search(r"\b(19\d{2}|20\d{2})(?:[-\/]\d{2,4})?\b", text)
    if year_match:
        meta["year"] = year_match.group(1)

    # 2. Category extraction
    low = text.lower()
    for key, cat in CATEGORY_MAP.items():
        if re.search(r"\b" + re.escape(key) + r"\b", low):
            meta["category"] = cat
            break
    if not meta["category"]:
        for cat in VALID_CATEGORIES:
            if re.search(r"\b" + re.escape(cat.lower()) + r"\b", low):
                meta["category"] = cat
                break

    # 3. Set Name extraction
    clean_set = text
    if meta["year"]:
        clean_set = re.sub(r"\b" + re.escape(meta["year"]) + r"(?:[-\/]\d{2,4})?\b", "", clean_set)
    clean_set = re.sub(
        r"\b(Checklist|Set Info|Boxes|Cards|Odds|Guide|Breakdown|Complete Set|Base Set|Release Date|Details)\b",
        "",
        clean_set,
        flags=re.IGNORECASE,
    )
    clean_set = re.sub(r"\s+", " ", clean_set).strip(" ,-:|")
    if clean_set:
        meta["set_name"] = clean_set

    return meta


def parse_checklist_line(line: str) -> Optional[ChecklistCard]:
    """Parses a single textual line or list item into a ChecklistCard."""
    clean = " ".join(line.split()).strip()
    if not clean:
        return None

    # Filter out header/metadata lines
    low = clean.lower()
    if low.startswith(("card #", "number", "card number", "base set checklist", "release date", "parallels")):
        return None

    # Rookie detection
    is_rookie = bool(re.search(r"\b(?:RC|Rookie|\(RC\)|\[RC\])\b", clean, re.IGNORECASE))

    # Match card number at start: preserves '01', '007', 'RC-1', 'BCP-1', '#24', '04/102', 'NNO'
    num_match = re.match(r"^(?:#\s*)?([A-Za-z0-9]+(?:[\/\-][A-Za-z0-9]+)*)\s+(.*)$", clean)
    if not num_match:
        # Check tab / multiple space separation
        split_line = re.split(r"\s{2,}|\t", clean, maxsplit=1)
        if len(split_line) == 2:
            card_num = split_line[0].strip().lstrip("#")
            rest = split_line[1].strip()
        else:
            return None
    else:
        card_num = num_match.group(1).strip()
        rest = num_match.group(2).strip()

    # Split player and team/notes
    # Delimiters: ' - ', ' – ', ' — ', ' , ', ' | ', '\t'
    parts = re.split(r"\s+[\-\–\—]\s+|\s*,\s*|\s*\|\s*|\t+", rest, maxsplit=1)
    if len(parts) == 2:
        player_raw, team_raw = parts[0].strip(), parts[1].strip()
    else:
        player_raw = rest.strip()
        team_raw = ""

    # Clean RC markers from player and team
    player = re.sub(r"\b(?:RC|Rookie|\(RC\)|\[RC\])\b", "", player_raw, flags=re.IGNORECASE).strip()
    player = re.sub(r"\s+", " ", player).strip(" ,-")
    team = re.sub(r"\b(?:RC|Rookie|\(RC\)|\[RC\])\b", "", team_raw, flags=re.IGNORECASE).strip()
    team = re.sub(r"\s+", " ", team).strip(" ,-")

    if not card_num or not player:
        return None

    return ChecklistCard(
        card_number=card_num,
        player=player,
        team=team,
        is_rookie=is_rookie,
        raw_text=clean
    )


def parse_checklist_table_row(row: list[str]) -> Optional[ChecklistCard]:
    """Parses a table row (list of cell strings) into a ChecklistCard."""
    if not row or len(row) < 2:
        return None

    first_cell = row[0].strip().lower()
    if first_cell in ("card #", "card no", "card number", "#", "number", "no.", "no", "card"):
        return None

    card_num = row[0].strip().lstrip("#")
    player_cell = row[1].strip()
    team_cell = row[2].strip() if len(row) > 2 else ""

    # Check rookie flag across all cells
    full_row_text = " ".join(row)
    is_rookie = bool(re.search(r"\b(?:RC|Rookie|\(RC\)|\[RC\])\b", full_row_text, re.IGNORECASE))

    player = re.sub(r"\b(?:RC|Rookie|\(RC\)|\[RC\])\b", "", player_cell, flags=re.IGNORECASE).strip()
    player = re.sub(r"\s+", " ", player).strip(" ,-")

    team = re.sub(r"\b(?:RC|Rookie|\(RC\)|\[RC\])\b", "", team_cell, flags=re.IGNORECASE).strip()
    team = re.sub(r"\s+", " ", team).strip(" ,-")

    if not card_num or not player:
        return None

    return ChecklistCard(
        card_number=card_num,
        player=player,
        team=team,
        is_rookie=is_rookie,
        raw_text=" | ".join(row)
    )


def extract_parallels_from_html(parser: ChecklistHTMLParser) -> list[str]:
    """Extracts parallel variation names from list items under parallel/variation headings."""
    parallels = []
    for heading, item in parser.list_items:
        h_low = heading.lower()
        if any(keyword in h_low for keyword in ("parallel", "variation", "prizm", "refractor", "colors", "inserts")):
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
    - If parallel is non-empty (e.g. 'Silver Prizm', 'Red /99'), sets variation=parallel and ai_status=REVIEW VARIATION.
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
        else: # dict
            card_num = str(c.get("card_number", ""))
            player = str(c.get("player", ""))
            year = str(c.get("year", default_year))
            set_name = str(c.get("set_name", default_set))
            cat = str(c.get("category", default_category))
            notes = str(c.get("notes", c.get("team", "")))

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
                category=cat,
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
    parser = ChecklistHTMLParser()
    parser.feed(html_content)
    parser.close()

    # Inferred metadata
    header_candidate = parser.title or (parser.headings[0][1] if parser.headings else "")
    inferred = infer_metadata_from_text(header_candidate)

    final_year = year or inferred.get("year") or "2024"
    final_set = set_name or inferred.get("set_name") or "Checklist Set"
    final_cat = category or inferred.get("category") or "Basketball"

    # Extract card entries from tables first
    raw_cards: list[ChecklistCard] = []
    for heading, table in parser.tables:
        for row in table:
            entry = parse_checklist_table_row(row)
            if entry:
                raw_cards.append(entry)

    # If no tables found, extract from list items (excluding parallel lists)
    if not raw_cards:
        for heading, item in parser.list_items:
            h_low = heading.lower()
            if not any(k in h_low for k in ("parallel", "variation", "prizm", "refractor", "odds")):
                entry = parse_checklist_line(item)
                if entry:
                    raw_cards.append(entry)

    # If parallels not explicitly given, check HTML for detected parallels
    if parallels is None:
        detected_parallels = extract_parallels_from_html(parser)
        if detected_parallels:
            # By default include Base + detected parallels
            parallels_to_use = ["Base"] + detected_parallels
        else:
            parallels_to_use = [""]
    else:
        parallels_to_use = parallels

    return expand_parallels(raw_cards, parallels_to_use, final_year, final_set, final_cat)


def run_tests():
    sample_beckett_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>2023-24 Panini Prizm Basketball Checklist, Set Info, Boxes</title>
</head>
<body>
  <div class="entry-header">
    <h1 class="entry-title">2023-24 Panini Prizm Basketball Checklist</h1>
    <p class="release-date">Release Date: February 21, 2024</p>
  </div>

  <div class="parallels-section">
    <h2>Parallels Breakdown</h2>
    <ul class="parallels-list">
      <li>Silver Prizm</li>
      <li>Red Prizm /99</li>
      <li>Blue Prizm /199</li>
      <li>Gold Prizm /10</li>
      <li>Black Prizm 1/1</li>
    </ul>
  </div>

  <div class="checklist-section">
    <h2>Base Set Checklist</h2>
    <table class="checklist-table">
      <thead>
        <tr>
          <th>Card #</th>
          <th>Player / Subject</th>
          <th>Team / Details</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>01</td>
          <td>Victor Wembanyama RC</td>
          <td>San Antonio Spurs</td>
        </tr>
        <tr>
          <td>007</td>
          <td>Luka Dončić</td>
          <td>Dallas Mavericks</td>
        </tr>
        <tr>
          <td>75</td>
          <td>Stephen Curry</td>
          <td>Golden State Warriors</td>
        </tr>
        <tr>
          <td>101</td>
          <td>Scoot Henderson (RC)</td>
          <td>Portland Trail Blazers</td>
        </tr>
        <tr>
          <td>RC-1</td>
          <td>Brandon Miller RC</td>
          <td>Charlotte Hornets</td>
        </tr>
      </tbody>
    </table>
  </div>
</body>
</html>"""

    # Test 1: High level parsing without explicit arguments (auto-inferred)
    cards = parse_checklist_html(sample_beckett_html, parallels=["Base"])
    assert len(cards) == 5, f"Expected 5 base cards, got {len(cards)}"
    
    # Verify card 0 (Victor Wembanyama)
    c0 = cards[0]
    assert c0.card_number == "01", f"Expected '01', got '{c0.card_number}'"
    assert c0.player == "Victor Wembanyama"
    assert c0.year == "2023"
    assert "Panini Prizm" in c0.set_name
    assert c0.category == "Basketball"
    assert c0.variation == ""
    assert c0.ai_status == "CLEARED"

    # Verify card 1 (Luka Doncic - leading zeroes '007')
    c1 = cards[1]
    assert c1.card_number == "007"
    assert c1.player == "Luka Dončić"

    # Verify card 4 (Brandon Miller - prefixed 'RC-1')
    c4 = cards[4]
    assert c4.card_number == "RC-1"
    assert c4.player == "Brandon Miller"

    # Test 2: Parallel Expansion across 3 parallels
    expanded = parse_checklist_html(sample_beckett_html, parallels=["Base", "Silver Prizm", "Gold Prizm /10"])
    assert len(expanded) == 15, f"Expected 5*3=15 cards, got {len(expanded)}"
    
    # Check that Silver Prizm gets REVIEW VARIATION
    silver_cards = [c for c in expanded if c.variation == "Silver Prizm"]
    assert len(silver_cards) == 5
    assert all(c.ai_status == "REVIEW VARIATION" for c in silver_cards)

    # Check that Base cards get CLEARED
    base_cards = [c for c in expanded if c.variation == ""]
    assert len(base_cards) == 5
    assert all(c.ai_status == "CLEARED" for c in base_cards)

    # Test 3: Validate that all generated CardExtractionSchemas convert cleanly to CardRecord
    for c in expanded:
        rec = CardRecord(**c.model_dump())
        assert rec.player
        assert rec.card_number
        assert rec.query == synthesize_query(rec.year, rec.set_name, rec.player, rec.variation, rec.condition)

    print("ALL TEST SUITE CHECKS PASSED IN test_scraper_engine.py!")


if __name__ == "__main__":
    run_tests()


# Architectural Analysis: Checklist Scraper Module (`scraper_ingest.py`), Static Fixtures & Test Suite

**Author**: Explorer Subagent (explorer_m2_2)  
**Milestone**: Milestone 2 - Ingestion Pipelines (AI Vision & Scraper)  
**Target Directory**: `g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub`  
**Date**: 2026-08-24  

---

## 1. Executive Summary

The Checklist Scraper Module (`scraper_ingest.py`) provides automated bulk ingestion of sports and TCG card sets from standard industry checklist sources (Beckett and Cardboard Connection). It parses structured HTML checklists, extracts essential card attributes with strict schema validation, handles parallel variation expansion, and offers zero-dependency offline resilience.

### Key Architectural Highlights
1. **Zero External Parser Dependencies**: Built purely on Python's standard library `html.parser.HTMLParser` with a state-machine parser that handles both table-based checklists (Beckett) and list-based checklists (Cardboard Connection), even in malformed or unclosed HTML trees.
2. **String Number Preservation**: Preserves leading zeroes (`'01'`, `'007'`, `'000'`, `'101'`, `'RC-1'`, `'BCP-1'`, `'04/102'`, `'NNO'`) as strict strings.
3. **Rookie Flag Detection (`RC`)**: Identifies rookie designations (`RC`, `(RC)`, `[RC]`, `Rookie`, `Rookie Card`) and strips markers from athlete names while capturing rookie metadata.
4. **Unicode Fidelity**: Full fidelity preservation for multi-byte Unicode names (`Luka Dončić`, `Ronald Acuña Jr.`, `Alexis Lafrenière`, `Shohei Ohtani (大谷 翔平)`).
5. **Parallel Variation Expansion**: Expands parsed base cards across parallel lists (e.g. `Base`, `Silver Prizm`, `Red /99`, `Gold /10`), auto-setting `ai_status=AIStatus.REVIEW_VARIATION` for non-base variations per Rule 21.
6. **Resilient Network & Offline Fallback**: Wraps `requests.get` with standard timeouts and headers, seamlessly falling back to local static HTML fixtures when offline.

---

## 2. Component Architecture

```
[ Beckett / Cardboard Connection HTML / Static Fixture ]
                         │
                         ▼
        ┌───────────────────────────────────┐
        │       ChecklistHTMLParser         │
        │   (Built-in html.parser.HTMLParser)│
        └─────────────────┬─────────────────┘
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│ Headings &   │  │ Checklist    │  │ Parallels List   │
│ Metadata     │  │ Tables/Lists │  │ Breakdown        │
│ (Year/Set/   │  │ (Number/     │  │ (Silver, Red/99, │
│ Category)    │  │ Player/Team) │  │ Gold/10, etc.)   │
└──────┬───────┘  └──────┬───────┘  └────────┬─────────┘
       │                 │                   │
       └─────────────────┼───────────────────┘
                         │
                         ▼
        ┌───────────────────────────────────┐
        │      Field Extraction Engine      │
        │ - Leading Zero Number Preserver   │
        │ - Rookie Flag (RC) Detector       │
        │ - Name Cleaner & Unicode Handler  │
        └─────────────────┬─────────────────┘
                          │
                          ▼
        ┌───────────────────────────────────┐
        │    Parallel Expansion Engine      │
        │ - Base -> variation='', CLEARED   │
        │ - Parallel -> variation=P,        │
        │   REVIEW VARIATION                │
        └─────────────────┬─────────────────┘
                          │
                          ▼
        ┌───────────────────────────────────┐
        │    List[CardExtractionSchema]     │
        │ (Directly ingestible into DB & UI)│
        └───────────────────────────────────┘
```

---

## 3. Data Models & Extraction Contracts

### 3.1 Data Structures (`scraper_ingest.py`)

```python
class ChecklistCard(BaseModel):
    """Raw extracted card item from checklist HTML."""
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
```

### 3.2 Output Schema Alignment (`models.py`)
Each expanded checklist card produces a valid `CardExtractionSchema` instance:
- `player`: Clean player name (e.g. `'Victor Wembanyama'`)
- `year`: 4-digit year string (e.g. `'2023'`)
- `set_name`: Manufacturer and set line (e.g. `'Panini Prizm'`)
- `variation`: Parallel name (e.g. `''` for Base, `'Silver Prizm'`, `'Red /99'`)
- `card_number`: String preserving leading zeroes (e.g. `'01'`, `'007'`, `'RC-1'`)
- `category`: Permitted 22 category value (e.g. `'Basketball'`)
- `condition`: `'Raw'`
- `slab_serial_number`: `''`
- `estimated_value`: `0.0`
- `notes`: Team or checklist notes (e.g. `'San Antonio Spurs'`)
- `ai_status`: `AIStatus.CLEARED` (if Base) or `AIStatus.REVIEW_VARIATION` (if Parallel)

---

## 4. Extraction Engine Specifications

### 4.1 Card Number Regex & String Preservation
Checklists feature diverse numbering conventions:
- **Numeric with leading zeroes**: `01`, `007`, `000`, `75`, `101`
- **Prefixed/Hyphenated**: `RC-1`, `RC-05`, `BCP-1`, `TR-10`, `LOB-001`
- **Fractional/Set Total**: `04/102`, `1/1`
- **Hash-prefixed**: `#01`, `#75`
- **Unnumbered**: `NNO`, `UCN`

**Regex Rule**:
```python
num_match = re.match(r"^(?:#\s*)?([A-Za-z0-9]+(?:[\/\-][A-Za-z0-9]+)*)\s+(.*)$", clean_line)
```
The number is captured as `match.group(1)` and kept as `str`. Never converted to `int` or `float`.

### 4.2 Rookie Flag (`RC`) Detection
- Regex: `r"\b(?:RC|Rookie|\(RC\)|\[RC\])\b"`
- Stripped from player name string so player is stored cleanly.
- Preserves `is_rookie=True` for metadata tagging.

### 4.3 Metadata Inference
- Year regex: `r"\b(19\d{2}|20\d{2})(?:[-\/]\d{2,4})?\b"`
- Category matching against `CATEGORY_MAP` and `VALID_CATEGORIES` (e.g. "Basketball", "Baseball", "Football", "UFC/MMA", "Pokemon", "Magic").
- Set Name: Strips year and generic terms ("Checklist", "Set Info", "Boxes") to isolate the core brand.

---

## 5. Parallel Expansion Engine

Given `N` parsed checklist cards and a list of `M` parallel variations (e.g. `["Base", "Silver Prizm", "Red /99", "Gold /10"]`):
1. Produces `N * M` cards.
2. For `"Base"` or `""`:
   - `variation = ""`
   - `ai_status = AIStatus.CLEARED`
3. For non-base parallels (e.g. `"Silver Prizm"`):
   - `variation = "Silver Prizm"`
   - `ai_status = AIStatus.REVIEW_VARIATION`
4. Query is synthesized via `synthesize_query(year, set_name, player, variation, condition)` on `CardRecord` conversion.

---

## 6. Proposed Code Implementation

### 6.1 `scraper_ingest.py`
```python
"""
scraper_ingest.py - Checklist Scraper Module for Sports Card Ecosystem Hub.
Parses set checklists from Beckett and Cardboard Connection using standard library html.parser.
Supports table and list layouts, leading zero preservation, rookie flag detection,
parallel expansion, and offline fallback.
"""

from __future__ import annotations

import os
import re
from html import unescape
from html.parser import HTMLParser
from typing import Any, Optional
import requests
from pydantic import BaseModel, Field

from models import (
    CardExtractionSchema,
    CardRecord,
    CardCategory,
    AIStatus,
    CATEGORY_MAP,
    VALID_CATEGORIES,
    synthesize_query,
)


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

    # 1. Year extraction (4 digits)
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

    low = clean.lower()
    if low.startswith(("card #", "number", "card number", "base set checklist", "release date", "parallels")):
        return None

    is_rookie = bool(re.search(r"\b(?:RC|Rookie|\(RC\)|\[RC\])\b", clean, re.IGNORECASE))

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
        raw_text=clean,
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
        raw_text=" | ".join(row),
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
            if not any(k in h_low for k in ("parallel", "variation", "prizm", "refractor", "odds")):
                entry = parse_checklist_line(item)
                if entry:
                    raw_cards.append(entry)

    if parallels is None:
        detected_parallels = extract_parallels_from_html(parser)
        if detected_parallels:
            parallels_to_use = ["Base"] + detected_parallels
        else:
            parallels_to_use = [""]
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
            with open(fallback_fixture_path, "r", encoding="utf-8") as f:
                html = f.read()
        else:
            raise RuntimeError(f"Failed to fetch checklist from '{url}' and no valid fallback fixture: {e}") from e

    return parse_checklist_html(html, set_name=set_name, year=year, category=category, parallels=parallels)
```

---

## 7. Static HTML Fixture (`fixtures/beckett_sample.html`)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>2023-24 Panini Prizm Basketball Checklist, Team Set Lists, Odds</title>
</head>
<body>
  <header class="entry-header">
    <h1 class="entry-title">2023-24 Panini Prizm Basketball Checklist</h1>
    <p class="release-date">Release Date: February 21, 2024</p>
  </header>

  <section class="parallels-section">
    <h2>Parallels Breakdown</h2>
    <ul class="parallels-list">
      <li>Silver Prizm</li>
      <li>Red Prizm /99</li>
      <li>Blue Prizm /199</li>
      <li>Gold Prizm /10</li>
      <li>Black Prizm 1/1</li>
    </ul>
  </section>

  <section class="checklist-section">
    <h2>Base Set Checklist</h2>
    <p>300 cards.</p>
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

    <h2>Rookie Variations Checklist</h2>
    <ul class="checklist-list">
      <li>01 Victor Wembanyama - San Antonio Spurs RC</li>
      <li>02 Scoot Henderson - Portland Trail Blazers RC</li>
      <li>03 Brandon Miller - Charlotte Hornets RC</li>
      <li>04 Amen Thompson - Houston Rockets RC</li>
      <li>05 Ausar Thompson - Detroit Pistons RC</li>
    </ul>
  </section>
</body>
</html>
```

---

## 8. Unit Test Suite Plan (`tests/test_ingest_scraper.py`)

| Tier | Test Class | Focus Areas |
|---|---|---|
| 1 | `TestChecklistHTMLParser` | Table vs List structure parsing, `<title>` / `<h1>` extraction, unclosed tags, malformed HTML resilience. |
| 2 | `TestFieldExtraction` | Card number leading zero preservation (`01`, `007`, `RC-1`, `04/102`), RC detection, athlete name cleanup, Unicode diacritics. |
| 3 | `TestParallelExpansion` | Base variation assignment (`ai_status=CLEARED`), parallel assignment (`ai_status=REVIEW VARIATION`), combinatorial explosion (N x M). |
| 4 | `TestNetworkAndFallback` | `requests.get` timeouts, HTTP error codes, mock network failure, offline fallback to local static fixture. |
| 5 | `TestFixtureAndDatabaseIntegration` | Loading `fixtures/beckett_sample.html`, conversion of parsed schema to `CardRecord`, batch insertion into `portfolio.db`, query validation. |

---

## 9. Conclusion
The proposed architecture provides a clean, zero-dependency, and deterministic checklist ingestion pipeline that seamlessly interfaces with `models.py` and `database.py`.

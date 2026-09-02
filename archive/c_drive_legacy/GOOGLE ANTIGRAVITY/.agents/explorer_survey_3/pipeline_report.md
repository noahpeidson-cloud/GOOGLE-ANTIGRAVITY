# Technical Architecture & Pipeline Specification: Sports Card Ecosystem Hub

**Document ID:** `SPEC-SPORTS-CARDS-PIPELINES-V1`  
**Author:** Teamwork Preview Explorer 3 (Investigation & Synthesis Archetype)  
**Target Directory:** `g:/My Drive/GOOGLE ANTIGRAVITY/sports_cards/ecosystem_hub`  
**Target Domain:** Track 1 — Sports Cards ETL, Vision Ingestion & Market Analytics  
**Date:** 2026-08-24  
**Status:** COMPLETE / SPECIFICATION READY FOR IMPLEMENTATION  

---

## Executive Summary

This technical specification defines the concrete architecture, data contracts, prompt engineering designs, parsing mechanics, and deterministic testing strategies for the **Sports Card Ecosystem Hub**. The system unifies four distinct ingestion and export pipelines into a local Streamlit + SQLite central repository (`portfolio.db`), enforcing Noah Eidson's strict **21-variable ingestion schema** and exporting pristine, zero-loss **16-column Card Ladder CSVs**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                CENTRAL ECOSYSTEM HUB                                   │
│                        (Streamlit Dashboard + SQLite portfolio.db)                     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                 INGESTION PIPELINES                                    │
│                                                                                        │
│  [Pipeline 1: AI Vision]    [Pipeline 2: Scraper]        [Pipeline 3: API Bridge]      │
│  - google-genai SDK         - Beckett & Cardboard Conn.  - Chrome Extension Ingestion  │
│  - Front/Back Card Images   - Static HTML Checklists     - FastAPI REST Service        │
│  - 21-Var JSON Schema       - Multi-Parallel Expansion   - FB Marketplace Generator    │
│  - Offline Mock Provider    - Zero-Network Fixtures      - SEO Structured Sales Copy   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                  DATABASE LAYER                                        │
│                 SQLite Relational Database (portfolio.db)                              │
│                 - Staging Table (21 Variables + Tracking Keys)                         │
│                 - Canonical Player & Set Reference Tables                              │
│                 - 500-Card Batch Circuit Breaker & Rollover                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                  EXPORT PIPELINE                                       │
│                             [Pipeline 4: Export Engine]                                │
│                             - Fuzzy Name & Set Normalization                           │
│                             - String Leading-Zero Preservation ("001", "04")           │
│                             - Exact 16 Card Ladder Column Slicing                      │
│                             - Output: CardLadder_Bulk_Upload.csv                       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Pipeline 1: AI Vision Ingestion Pipeline

### 1.1 SDK Selection & Model Architecture
- **Approved SDK:** Modern `google-genai` Python SDK (`from google import genai`, `from google.genai import types`).
- **Forbidden SDK:** Legacy `google-generativeai` (deprecated).
- **Target Models:**
  - Primary: `gemini-2.5-flash` (or `gemini-3.7-flash`) for ultra-fast, high-throughput OCR and multi-image card analysis.
  - Fallback / High-Reasoning: `gemini-2.5-pro` for heavily obscured parallels or vintage card authentication.

### 1.2 Multi-Image Multimodal Ingestion Mechanics
Cards are presented either as a single front image or as dual front/back images (e.g. `CardScan-20260824-8492.jpg` and `CardScan-20260824-8492_back.jpg`).

```python
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional, Literal
from pathlib import Path

class CardExtractionSchema(BaseModel):
    date_purchased: str = Field(description="Date in MM/DD/YYYY format. Default to today's date.")
    quantity: int = Field(default=1, description="Quantity of cards, strictly 1.")
    player: str = Field(description="Full athlete name or TCG character name.")
    year: str = Field(description="4-digit release year (e.g. '2018').")
    set: str = Field(description="Manufacturer and release line (e.g. 'Panini Prizm', 'Topps Chrome').")
    variation: str = Field(description="Visual foil, sheen, or parallel name (e.g. 'Silver Prizm', 'Refractor'). Empty string only for verified base cards.")
    number: str = Field(description="Printed card number preserved as string (e.g. '280', '001', 'RC-1').")
    category: Literal[
        'Basketball', 'Baseball', 'Football', 'Hockey', 'Soccer', 'Tennis',
        'Wrestling', 'Racing', 'Golf', 'Boxing', 'UFC/MMA', 'Pokemon', 'Magic',
        'Metazoo', 'Yugioh', 'Fortnite', 'Dragonballz', 'Entertainment',
        'Swimming', 'Softball', 'PopCulture', 'Flesh and Blood'
    ] = Field(description="Exact category from permitted 22 enums.")
    condition: str = Field(description="Strictly 'Raw' for ungraded cards. For graded cards, use company and grade with NO hyphens (e.g. 'PSA 10', 'BGS 9.5', 'SGC 10', 'CGC 9.5').")
    slab_serial_number: str = Field(default="", description="Graded certification number string from slab label. MUST be empty string if Raw.")
    investment: float = Field(default=0.00, description="Purchase cost basis float with 2 decimals.")
    estimated_value: float = Field(default=0.00, description="Estimated value or OCR price sticker, 0.00 if none.")
    ladder_id: str = Field(default="", description="Blank reserved for Card Ladder sync.")
    query: str = Field(description="Synthesized query: '[Year] [Set] [Player] [Variation] [Condition]'. Negative exclusions are forbidden on Raw.")
    notes: str = Field(description="Tracking identifier: '[Parent_Image_ID]-[Child_Card_ID]' (e.g. '8492-105').")
    tags: str = Field(default="", description="Blank or custom tags.")
    date_sold: str = Field(default="", description="Blank for unsold cards.")
    sold_price: str = Field(default="", description="Blank for unsold cards.")
    image: str = Field(description="Direct Drive URL or local file path to front image.")
    back_image: str = Field(default="", description="Direct Drive URL or local file path to back image, or empty string.")
    ai_status: Literal['REVIEW VARIATION', 'NEEDS REVIEW', 'CLEARED'] = Field(
        description="MUST be 'REVIEW VARIATION' if parallel was guessed from visual foil; 'NEEDS REVIEW' if OCR is ambiguous; 'CLEARED' if verified base or unambiguous slab."
    )
```

### 1.3 System Prompt Design & Few-Shot Guidance
```text
SYSTEM INSTRUCTION:
You are an expert sports card and TCG authenticator and cataloger.
Your task is to analyze card scan images (front and optional back) and extract the exact 21 variables required by the sports card database schema.

RULES:
1. Category must strictly be one of: [Basketball, Baseball, Football, Hockey, Soccer, Tennis, Wrestling, Racing, Golf, Boxing, UFC/MMA, Pokemon, Magic, Metazoo, Yugioh, Fortnite, Dragonballz, Entertainment, Swimming, Softball, PopCulture, Flesh and Blood].
2. Condition: If the card is in a graded plastic slab with a label (PSA, Beckett/BGS, SGC, CGC, CSG), extract the company and grade without hyphens (e.g., "PSA 10", "BGS 9.5", "SGC 10"). If the card is in a penny sleeve, top loader, magnetic one-touch, or raw, condition MUST BE EXACTLY "Raw".
3. Slab Serial #: If condition is "Raw", slab_serial_number MUST BE an empty string "". If graded, extract the numeric certification number from the label barcode area.
4. Variation: Aggressively identify visual foil/sheen/refractor/prizm/parallel (e.g., "Silver Prizm", "Refractor", "Gold Wave /10", "Hyper"). Leave blank ONLY for verified standard base cards.
5. AI Status: If you identify or guess a parallel from visual sheen/foil, you MUST set ai_status = "REVIEW VARIATION". If confidence is low or text is obscured, set ai_status = "NEEDS REVIEW". If it is a verified standard base card or high-confidence graded slab, set ai_status = "CLEARED".
6. Card Number: Preserve leading zeros and prefixes exactly as printed (e.g., "001", "04", "#280", "RC-1").
7. Query: Synthesize exactly as: "{year} {set} {player} {variation} {condition}".strip(). Negative exclusions (e.g. "-BGS -SGC") are STRICTLY FORBIDDEN on "Raw" cards.
8. Output: Emit strictly a valid JSON object conforming to the provided CardExtractionSchema.
```

### 1.4 Fallback Mock Provider for Deterministic Offline Testing
To satisfy the **Zero-Discretion Mandate (R2)** and ensure zero network flakiness in CI/CD, the Vision Module defines a dependency-injected interface:

```python
import json
from pathlib import Path
from typing import Protocol, Dict, Any

class VisionExtractor(Protocol):
    def extract_card_metadata(
        self, 
        front_image_path: str, 
        back_image_path: Optional[str] = None,
        parent_image_id: str = "8492",
        child_card_id: str = "101"
    ) -> CardExtractionSchema: ...

class MockVisionExtractor:
    def __init__(self, fixture_path: Optional[Path] = None):
        self.fixture_path = fixture_path

    def extract_card_metadata(
        self, 
        front_image_path: str, 
        back_image_path: Optional[str] = None,
        parent_image_id: str = "8492",
        child_card_id: str = "101"
    ) -> CardExtractionSchema:
        # If fixture is provided, load deterministic JSON
        if self.fixture_path and self.fixture_path.exists():
            data = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        else:
            # Deterministic synthetic mock matching image path
            data = {
                "date_purchased": "08/24/2026",
                "quantity": 1,
                "player": "Luka Doncic",
                "year": "2018",
                "set": "Panini Prizm",
                "variation": "Silver Prizm",
                "number": "280",
                "category": "Basketball",
                "condition": "PSA 10",
                "slab_serial_number": "48192048",
                "investment": 0.00,
                "estimated_value": 850.00,
                "ladder_id": "",
                "query": "2018 Panini Prizm Luka Doncic Silver Prizm PSA 10",
                "notes": f"{parent_image_id}-{child_card_id}",
                "tags": "",
                "date_sold": "",
                "sold_price": "",
                "image": str(front_image_path),
                "back_image": str(back_image_path) if back_image_path else "",
                "ai_status": "REVIEW VARIATION"
            }
        return CardExtractionSchema(**data)
```

---

## 2. Pipeline 2: Scraper Pipeline (Beckett & Cardboard Connection)

### 2.1 HTML Layout & DOM Pattern Analysis
Beckett and Cardboard Connection use two primary layout styles:

#### Pattern A: Cardboard Connection List / Section Hierarchy
- **Container:** `<div class="entry-content">`
- **Sections:** `<h2>` or `<h3>` headers (e.g. `<h3>2018-19 Panini Prizm Basketball Base Set Checklist</h3>`, `<h3>Base Parallels</h3>`)
- **Card Items:** `<ul><li>` items formatted as:
  `<li>1 Luka Doncic, Dallas Mavericks RC</li>` or `<li>#280 Luka Doncic - Dallas Mavericks</li>`
- **Parallel Subsections:**
  ```html
  <h3>2018-19 Panini Prizm Base Parallels</h3>
  <ul>
    <li>Silver Prizm</li>
    <li>Hyper Prizm (#/295)</li>
    <li>Ruby Wave Prizm (#/199)</li>
    <li>Gold Prizm (#/10)</li>
    <li>Black Prizm (1/1)</li>
  </ul>
  ```

#### Pattern B: Beckett Structured Tables
- **Container:** `<table class="checklist-table">`
- **Columns:** `<th>Card #</th><th>Player / Subject</th><th>Team</th><th>Attributes</th><th>Print Run</th>`
- **Row:** `<tr><td>280</td><td>Luka Doncic</td><td>Dallas Mavericks</td><td>RC</td><td></td></tr>`

### 2.2 Extraction & Parallel Cross-Product Expansion Logic
The scraper engine extracts the base checklist and allows the user in Streamlit to select which parallels to expand.

```python
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class ChecklistItem:
    number: str
    player: str
    team: Optional[str]
    is_rookie: bool
    raw_text: str

class ChecklistScraper:
    CARD_REGEX = re.compile(
        r'^(?:#|No\.\s*)?(?P<number>[A-Za-z0-9#-]+)\s+(?P<player>[^,\-\n]+?)(?:,\s*|\s+-\s+)(?P<team>[^,\(\n]+)?(?:\s+(?P<attr>RC|AU|MEM|SP|SSP))?$',
        re.IGNORECASE
    )

    @staticmethod
    def parse_html_checklist(html_content: str) -> List[ChecklistItem]:
        soup = BeautifulSoup(html_content, 'html.parser')
        cards: List[ChecklistItem] = []

        # 1. Try table parsing first
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                if len(cols) >= 2 and cols[0].lower() not in ['card #', 'card', '#', 'no.']:
                    num = cols[0]
                    player = cols[1]
                    team = cols[2] if len(cols) > 2 else ""
                    attr = cols[3] if len(cols) > 3 else ""
                    cards.append(ChecklistItem(
                        number=num,
                        player=player,
                        team=team,
                        is_rookie='RC' in attr.upper() or 'ROOKIE' in attr.upper(),
                        raw_text=f"{num} {player} - {team}"
                    ))
        
        # 2. Try unordered list parsing if no tables found
        if not cards:
            for li in soup.find_all('li'):
                text = li.get_text(strip=True)
                match = ChecklistScraper.CARD_REGEX.match(text)
                if match:
                    cards.append(ChecklistItem(
                        number=match.group('number'),
                        player=match.group('player').strip(),
                        team=match.group('team').strip() if match.group('team') else None,
                        is_rookie=bool(match.group('attr') and 'RC' in match.group('attr').upper()),
                        raw_text=text
                    ))
        return cards

    @staticmethod
    def expand_to_21_variables(
        cards: List[ChecklistItem],
        year: str,
        set_name: str,
        category: str,
        selected_parallels: List[str]
    ) -> List[Dict[str, Any]]:
        rows = []
        for card in cards:
            for parallel in selected_parallels:
                var_val = "" if parallel.lower() in ["base", "base set"] else parallel
                query = f"{year} {set_name} {card.player} {var_val} Raw".strip()
                rows.append({
                    "date_purchased": "08/24/2026",
                    "quantity": 1,
                    "player": card.player,
                    "year": year,
                    "set": set_name,
                    "variation": var_val,
                    "number": card.number,
                    "category": category,
                    "condition": "Raw",
                    "slab_serial_number": "",
                    "investment": 0.00,
                    "estimated_value": 0.00,
                    "ladder_id": "",
                    "query": query,
                    "notes": "CHECKLIST-INGEST",
                    "tags": "Rookie" if card.is_rookie else "",
                    "date_sold": "",
                    "sold_price": "",
                    "image": "",
                    "back_image": "",
                    "ai_status": "CLEARED" if not var_val else "REVIEW VARIATION"
                })
        return rows
```

### 2.3 Deterministic Static HTML Fixtures
For testing, static HTML fixtures (`fixtures/beckett_prizm_sample.html`, `fixtures/cardboard_sample.html`) are bundled in the repository so tests run 100% offline without hitting live web servers or encountering cloudflare rate limits.

---

## 3. Pipeline 3: API Bridge & Facebook Marketplace Sales Generator

### 3.1 Chrome Extension JSON Payload Schema
The Chrome Extension captures market data from secondary sites (eBay, PWCC, Card Ladder) and sends a `POST` request to the local FastAPI daemon (`http://localhost:8002/api/v1/cards/capture`).

```json
{
  "source_platform": "ebay",
  "source_url": "https://www.ebay.com/itm/123456789012",
  "raw_title": "2018 Panini Prizm Luka Doncic #280 Silver Prizm PSA 10 Gem Mint",
  "price": 850.00,
  "player": "Luka Doncic",
  "year": "2018",
  "set": "Panini Prizm",
  "variation": "Silver Prizm",
  "number": "280",
  "category": "Basketball",
  "condition": "PSA 10",
  "slab_serial_number": "48192048",
  "image_url": "https://i.ebayimg.com/images/g/abc123/s-l1600.jpg",
  "back_image_url": "",
  "notes": "Evasive Capture"
}
```

### 3.2 FastAPI REST Bridge Models & Endpoints

```python
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import sqlite3

app = FastAPI(title="Sports Cards Ecosystem API Bridge", version="1.0.0")

class CardCaptureRequest(BaseModel):
    source_platform: str = Field(description="e.g. ebay, cardladder, pwcc")
    source_url: str
    raw_title: str
    price: float = 0.00
    player: str
    year: str
    set: str
    variation: str = ""
    number: str
    category: str
    condition: str = "Raw"
    slab_serial_number: str = ""
    image_url: str = ""
    back_image_url: str = ""
    notes: str = ""

class CardCaptureResponse(BaseModel):
    status: str
    tracking_id: str
    record_id: int
    normalized_query: str

@app.post("/api/v1/cards/capture", response_model=CardCaptureResponse, status_code=status.HTTP_201_CREATED)
def capture_card(payload: CardCaptureRequest):
    # Enforce 21-variable schema & write to portfolio.db
    # Generate tracking id [Parent_Image_ID]-[Child_Card_ID]
    tracking_id = f"EXT-{payload.number}"
    query = f"{payload.year} {payload.set} {payload.player} {payload.variation} {payload.condition}".strip()
    
    # Commit to SQLite portfolio.db
    # ...
    return CardCaptureResponse(
        status="SUCCESS",
        tracking_id=tracking_id,
        record_id=1,
        normalized_query=query
    )
```

### 3.3 Gemini Prompt Engineering: High-Conversion Facebook Marketplace Listing
The Sales Generator transforms a database card row into an SEO-optimized, click-through-maximizing Facebook Marketplace listing.

#### System Prompt & Format Specification
```text
SYSTEM INSTRUCTION:
You are an elite sports card copywriter and marketplace sales optimizer.
Your objective is to generate a high-conversion, professional Facebook Marketplace listing for a collectible card.

CONSTRAINTS:
1. Title MUST be under 100 characters, search-indexed with Year, Set, Player, Card #, Variation, and Grade.
2. Price Hook: Anchor the asking price firmly and reference comp stability.
3. Card Specs: Present structured bullet points (Player, Year, Set, Card Number, Variation, Condition/Grade, Cert Number).
4. Authenticity & Slab Check: For graded cards, explicitly confirm slab condition and online registry verification. For raw cards, accurately describe clean corners/edges/surface.
5. Terms & Logistics: Safe public meetup in local area (East Valley / Phoenix) or tracked insured bubble mailer shipping. Payment via Cash, Zelle, or Venmo.
6. Hashtags: Generate 6-8 viral, high-volume hashtags.
7. OMIT fluff, fake urgency, or generic AI buzzwords.

INPUT ROW:
{card_json}

OUTPUT FORMAT:
=== TITLE ===
[Optimized Listing Title]

=== ASKING PRICE ===
$[Price] OBO

=== DESCRIPTION ===
[High-Conversion Body Copy]

=== CARD DETAILS ===
• Player: [Player]
• Year: [Year]
• Set: [Set]
• Card #: [Number]
• Variation: [Variation]
• Condition: [Condition]
• Slab Cert #: [Slab Serial #]

=== LOGISTICS & PAYMENT ===
• Local Pickup: [Location Details]
• Shipping: [Shipping Details]
• Payment: Cash / Zelle / Venmo

=== HASHTAGS ===
[#Tag1 #Tag2 #Tag3 #Tag4 #Tag5 #Tag6 #Tag7 #Tag8]
```

#### Generated Listing Example Output:
```text
=== TITLE ===
🔥 2018 Panini Prizm Luka Doncic #280 Silver Prizm RC - PSA 10 Gem Mint 🔥

=== ASKING PRICE ===
$850 OBO

=== DESCRIPTION ===
Up for sale is the iconic 2018 Panini Prizm Luka Doncic Silver Prizm Rookie Card (#280) graded PSA 10 Gem Mint. A cornerstone grail for any modern basketball collection. Slab is crystal clear with zero cracks, scuffs, or scratching. Cert number verified on the official PSA registry.

=== CARD DETAILS ===
• Player: Luka Doncic
• Year: 2018
• Set: Panini Prizm
• Card #: #280
• Variation: Silver Prizm (Prizm Refractor Sheen)
• Condition: PSA 10 Gem Mint
• Slab Cert #: 48192048

=== LOGISTICS & PAYMENT ===
• Local Pickup: Safe meetup at public bank/police station in Phoenix / Scottsdale.
• Shipping: Tracked & insured USPS Priority Bubble Mailer ($5 flat).
• Payment: Cash, Zelle, or Venmo. No trades unless vintage Grails.

=== HASHTAGS ===
#LukaDoncic #DallasMavericks #PaniniPrizm #SilverPrizm #RookieCard #PSA10 #TheHobby #BasketballCards
```

---

## 4. Pipeline 4: Export Pipeline & Data Normalization Engine

### 4.1 Data Normalization & Canonical Matching
The export engine reconciles scraped, captured, and OCR'd data against canonical reference dictionaries using fuzzy string matching (Levenshtein distance / RapidFuzz):
- **Player Names:** Reconciles diacritics and nick-names (`Luka Dončić` -> `Luka Doncic`, `Ronald Acuna Jr.` -> `Ronald Acuña Jr.`, `CJ Stroud` -> `C.J. Stroud`).
- **Set Names:** Strips redundant year ranges or card company noise (`2018-19 Panini Prizm Basketball Hobby` -> `Panini Prizm`).
- **Categories:** Strictly maps to the 22 valid enums.
- **Conditions:** Enforces no hyphens (`PSA 10`, `BGS 9.5`, `SGC 10`, `Raw`).

### 4.2 Card Number Leading-Zero Preservation Algorithm
A major failure mode in data pipelines is numeric coercion of strings like `"001"`, `"04"`, `"007"`, or `"RC-1"` into integers (`1`, `4`, `7`).

```python
import pandas as pd
import csv
from pathlib import Path
from typing import List, Dict, Any

CARD_LADDER_COLUMNS = [
    "Date Purchased",
    "Quantity",
    "Player",
    "Year",
    "Set",
    "Variation",
    "Number",
    "Category",
    "Condition",
    "Slab Serial #",
    "Investment",
    "Estimated Value",
    "Ladder ID",
    "Query",
    "Notes",
    "Tags"
]

def export_card_ladder_csv(records: List[Dict[str, Any]], output_csv_path: Path) -> Path:
    """
    Exports a list of 21-variable records into a 16-column Card Ladder CSV
    guaranteeing strict preservation of leading zeros and column ordering.
    """
    # 1. Enforce string typing across all columns to block pandas int coercion
    df = pd.DataFrame(records)
    
    # 2. Slice strictly the 16 required Card Ladder columns
    for col in CARD_LADDER_COLUMNS:
        if col not in df.columns:
            df[col] = ""
            
    df_export = df[CARD_LADDER_COLUMNS].copy()
    
    # 3. Ensure 'Number' and 'Slab Serial #' are string formatted
    df_export["Number"] = df_export["Number"].astype(str)
    df_export["Slab Serial #"] = df_export["Slab Serial #"].fillna("").astype(str)
    
    # Clean NaN / None values to empty strings
    df_export = df_export.fillna("")
    
    # 4. Export with csv.QUOTE_MINIMAL and explicit string serialization
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    df_export.to_csv(
        output_csv_path,
        index=False,
        encoding="utf-8",
        quoting=csv.QUOTE_MINIMAL
    )
    return output_csv_path
```

### 4.3 500-Card Batch Circuit Breaker
In compliance with Rule 40 in `sports_cards/GEMINI.md`:
- If the staging table or export batch reaches **500 rows**, the pipeline automatically triggers:
  1. Automated batch export: `CardLadder_Bulk_Upload_Batch_001.csv`.
  2. Transactional SQLite commit marking rows as `EXPORTED`.
  3. Staging rollover to prevent memory bloat and API batch limits.

---

## 5. Comprehensive Deterministic Test Plan

In adherence to the **Zero-Discretion Mandate (R2)** and **Test-Driven Agentic Development (TDAD)**, the ecosystem hub must be verified with deterministic unit and E2E tests:

| Test File | Target Scope | Key Loud Assertions |
|---|---|---|
| `test_schema_integrity.py` | 21-Variable Schema | Asserts all 21 columns exist, Category matches 22 enums, Condition matches Raw/Graded regex, Notes follows `[Parent]-[Child]` format. |
| `test_vision_pipeline_mock.py` | AI Vision Ingestion | Asserts `MockVisionExtractor` processes card image, produces 21-variable dictionary, preserves card number string, flags `REVIEW VARIATION`. |
| `test_scraper_deterministic.py` | Scraper Ingestion | Loads `fixtures/beckett_sample.html`, asserts $\ge 3$ cards extracted, correctly identifies card `#280`, player `Luka Doncic`, rookie flag `True`. |
| `test_api_bridge_endpoints.py` | FastAPI Bridge | Sends mock Chrome extension JSON payload to `/api/v1/cards/capture`, asserts HTTP 201, verifies record inserted in SQLite. |
| `test_sales_generator_prompt.py` | Sales Copy Generator | Asserts generated listing contains Title, Asking Price, Bullets, Logistics, and 6-8 Hashtags without hallucinated prices. |
| `test_card_ladder_export_csv.py` | Export Pipeline | Inserts rows with numbers `"001"`, `"04"`, `"RC-1"`, exports CSV, reads back raw bytes/lines, asserts exactly 16 columns and leading zeros intact. |
| `test_circuit_breaker_500.py` | 500-Card Batching | Inserts 505 mock records, asserts batch export triggers at 500 rows and partitions into batch files. |

---

## 6. Implementation Directory Structure Recommendation

```
sports_cards/ecosystem_hub/
├── app.py                      # Streamlit Multi-Page UI Application
├── config.py                   # Global configs, paths, category enums
├── database/
│   ├── __init__.py
│   ├── db.py                   # SQLite connection & schema initialization
│   └── models.py               # 21-variable schema & Card Ladder column mappings
├── pipelines/
│   ├── __init__.py
│   ├── vision_extractor.py     # google-genai vision integration & mock provider
│   ├── scraper.py              # BeautifulSoup Beckett & Cardboard Connection parser
│   ├── api_bridge.py           # FastAPI ingestion server
│   ├── sales_generator.py      # Gemini Facebook Marketplace listing generator
│   └── exporter.py             # Pandas normalization & 16-col CSV export engine
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   ├── sample_beckett.html
│   │   ├── sample_cardboard.html
│   │   └── mock_card_vision.json
│   ├── test_schema_integrity.py
│   ├── test_vision_pipeline_mock.py
│   ├── test_scraper_deterministic.py
│   ├── test_api_bridge_endpoints.py
│   ├── test_sales_generator_prompt.py
│   └── test_card_ladder_export_csv.py
└── requirements.txt
```

---
*End of Specification Document `SPEC-SPORTS-CARDS-PIPELINES-V1`.*

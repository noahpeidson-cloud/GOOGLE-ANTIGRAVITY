# Milestone 2: AI Vision Ingestion Module (`vision_ingest.py`) Analysis & Specification

**Date**: 2026-08-24  
**Author**: teamwork_preview_explorer  
**Target Module**: `sports_cards/ecosystem_hub/vision_ingest.py`  
**Test Suite**: `sports_cards/ecosystem_hub/tests/test_ingest_vision.py`  
**Integrations**: `models.py`, `database.py`, `fixtures/mock_card_data.json`  

---

## 1. Executive Summary

Milestone 2 requires implementing the AI Vision Ingestion pipeline (`vision_ingest.py`) for the Sports Card Ecosystem Hub. The module inspects trading card photos (front and back), analyzes their visual attributes using Google Gemini Multimodal AI (`gemini-2.5-flash`), and extracts structured metadata conforming strictly to the 21-variable schema defined in `models.py` (`CardExtractionSchema` / `CardRecord`).

To ensure 100% testability and reliability in offline, CI/CD, or keyless environments, the module incorporates a deterministic `MockVisionExtractor` with fixture matching, filename token parsing, and stable hash-based fallback.

---

## 2. Requirements & Interface Matrix

| Component | Specification | Source / Contract |
|---|---|---|
| **AI SDK** | `google.genai` (`from google import genai`, `from google.genai import types`) | `gemini-api-dev` skill, `PROJECT.md` §11 |
| **Model** | `gemini-2.5-flash` | `PROJECT.md` §11, `gemini-api-dev` |
| **Extraction Schema** | Pydantic v2 `CardExtractionSchema` | `models.py` lines 303-320 |
| **Primary Ingestion API** | `extract_card_from_image(image_path, back_image_path=None, mock=False, ...)` | `PROJECT.md` §2 Interface Contracts |
| **Deterministic Mock** | `MockVisionExtractor(image_path, back_image_path=None, ...)` | `ORIGINAL_REQUEST.md` §R2, §67 |
| **Record Conversion** | `extraction_to_card_record(extraction, investment=0.0, ...)` | `models.py` `CardRecord` |
| **Batch Pipeline** | `batch_extract_cards(image_paths, mock=False, ...)` | Circuit breaker limit: 500 cards |
| **Test Suite** | `tests/test_ingest_vision.py` | Pytest, deterministic, 100% offline coverage |

---

## 3. Gemini Multimodal Prompt Engineering & Structured Extraction

### 3.1 System Instruction
```text
You are an expert sports card and trading card authentication and cataloging assistant.
Your task is to analyze card images (front and back) and extract precise catalog information adhering strictly to the required schema.

Rules:
1. Player: Extract the exact player name or character name (e.g., 'Luka Dončić', 'Shohei Ohtani', 'Charizard').
2. Year: Extract the 4-digit release year (e.g., '2020'). If a season range is present (e.g., '2020-21'), extract the first year ('2020').
3. Set Name: Extract manufacturer and product line (e.g., 'Panini Prizm', 'Topps Chrome', 'Upper Deck Young Guns', 'Pokemon Base Set').
4. Card Number: Extract the card number as printed (e.g., '75', '001', 'BCP-1', '04/102'). Preserve leading zeroes. If no number is printed, output 'NNO'.
5. Category: Must be exactly one of the 22 permitted categories: Basketball, Baseball, Football, Hockey, Soccer, Tennis, Wrestling, Racing, Golf, Boxing, UFC/MMA, Pokemon, Magic, Metazoo, Yugioh, Fortnite, Dragonballz, Entertainment, Swimming, Softball, PopCulture, Flesh and Blood.
6. Condition: If the card is encapsulated in a graded slab (PSA, BGS, SGC, CGC, TAG, BVG), extract the grading company and grade without hyphens (e.g., 'PSA 10', 'BGS 9.5', 'SGC 10', 'CGC 9.5', 'TAG 10'). If raw or ungraded, output 'Raw'.
7. Slab Serial Number: If graded, extract the numeric/alphanumeric certification number. If condition is 'Raw', output empty string ''.
8. Variation: Extract parallel, foil, or insert name (e.g., 'Silver Prizm', 'Refractor', '1st Edition Holo', 'Orange Refractor /25'). If standard base card, output ''.
9. AI Status: If a variation is detected, output 'REVIEW VARIATION'. Otherwise 'CLEARED'.
```

### 3.2 Structured Output Configuration in `google.genai`
```python
config = types.GenerateContentConfig(
    system_instruction=VISION_SYSTEM_INSTRUCTION,
    response_mime_type="application/json",
    response_schema=CardExtractionSchema,
    temperature=0.1,
)
```

---

## 4. Proposed Implementation: `vision_ingest.py`

```python
\"\"\"
vision_ingest.py - AI Vision Ingestion Pipeline for Sports Card Ecosystem Hub.
Uses google.genai SDK with gemini-2.5-flash and Pydantic structured output extraction.
Includes deterministic MockVisionExtractor for 100% testability in offline environments.
\"\"\"

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, List, Optional, Union

from google import genai
from google.genai import types

from models import (
    CardCategory,
    CardExtractionSchema,
    CardRecord,
    AIStatus,
    VALID_CATEGORIES,
    CATEGORY_MAP,
    format_notes,
    synthesize_query,
)

logger = logging.getLogger(__name__)

# Default model
DEFAULT_VISION_MODEL = "gemini-2.5-flash"

# System instruction for multimodal card extraction
VISION_SYSTEM_INSTRUCTION = \"\"\"
You are an expert sports card and trading card authentication and cataloging assistant.
Your task is to analyze card images (front and back) and extract precise catalog information adhering strictly to the required schema.

Rules:
1. Player: Extract the exact player name or character name (e.g., 'Luka Dončić', 'Shohei Ohtani', 'Charizard').
2. Year: Extract the 4-digit release year (e.g., '2020'). If a season range is present (e.g., '2020-21'), extract the first year ('2020').
3. Set Name: Extract manufacturer and line (e.g., 'Panini Prizm', 'Topps Chrome', 'Upper Deck Young Guns', 'Pokemon Base Set').
4. Card Number: Extract the card number as printed (e.g., '75', '001', 'BCP-1', '04/102'). Preserve leading zeroes. If no number is printed, output 'NNO' or ''.
5. Category: Must be exactly one of: Basketball, Baseball, Football, Hockey, Soccer, Tennis, Wrestling, Racing, Golf, Boxing, UFC/MMA, Pokemon, Magic, Metazoo, Yugioh, Fortnite, Dragonballz, Entertainment, Swimming, Softball, PopCulture, Flesh and Blood.
6. Condition: If the card is encapsulated in a graded slab (PSA, BGS, SGC, CGC, TAG, BVG), extract the grading company and grade without hyphens (e.g., 'PSA 10', 'BGS 9.5', 'SGC 10', 'CGC 9.5', 'TAG 10'). If raw or ungraded, output 'Raw'.
7. Slab Serial Number: If graded, extract the numeric/alphanumeric certification number. If condition is 'Raw', output empty string ''.
8. Variation: Extract parallel, foil, or insert name (e.g., 'Silver Prizm', 'Refractor', '1st Edition Holo'). If standard base card, output ''.
9. AI Status: If a variation is detected, output 'REVIEW VARIATION'. Otherwise 'CLEARED'.
\"\"\"

# Fixtures database fallback pool
_BUILTIN_FIXTURES = [
    {
        "player": "Luka Dončić",
        "year": "2020",
        "set_name": "Panini Prizm",
        "variation": "Silver Prizm",
        "card_number": "75",
        "category": "Basketball",
        "condition": "PSA 10",
        "slab_serial_number": "48192041",
        "estimated_value": 350.00,
        "ai_status": "REVIEW VARIATION",
    },
    {
        "player": "Ronald Acuña Jr.",
        "year": "2019",
        "set_name": "Topps Chrome",
        "variation": "",
        "card_number": "001",
        "category": "Baseball",
        "condition": "Raw",
        "slab_serial_number": "",
        "estimated_value": 25.00,
        "ai_status": "CLEARED",
    },
    {
        "player": "Shohei Ohtani (大谷 翔平)",
        "year": "2018",
        "set_name": "Bowman Chrome",
        "variation": "Refractor",
        "card_number": "BCP-1",
        "category": "Baseball",
        "condition": "BGS 9.5",
        "slab_serial_number": "0014892102",
        "estimated_value": 1100.00,
        "ai_status": "REVIEW VARIATION",
    },
    {
        "player": "Charizard",
        "year": "1999",
        "set_name": "Pokemon Base Set",
        "variation": "1st Edition Holo",
        "card_number": "04/102",
        "category": "Pokemon",
        "condition": "SGC 10",
        "slab_serial_number": "91823104",
        "estimated_value": 3500.00,
        "ai_status": "REVIEW VARIATION",
    },
    {
        "player": "Patrick Mahomes",
        "year": "2017",
        "set_name": "Panini Donruss",
        "variation": "The Rookies",
        "card_number": "TR-10",
        "category": "Football",
        "condition": "Raw",
        "slab_serial_number": "",
        "estimated_value": 180.00,
        "ai_status": "REVIEW VARIATION",
    },
    {
        "player": "Connor McDavid",
        "year": "2015",
        "set_name": "Upper Deck Young Guns",
        "variation": "",
        "card_number": "201",
        "category": "Hockey",
        "condition": "PSA 10",
        "slab_serial_number": "59102834",
        "estimated_value": 1400.00,
        "ai_status": "CLEARED",
    },
    {
        "player": "Lionel Messi",
        "year": "2004",
        "set_name": "Panini Mega Cracks",
        "variation": "",
        "card_number": "071",
        "category": "Soccer",
        "condition": "PSA 9",
        "slab_serial_number": "72619023",
        "estimated_value": 4500.00,
        "ai_status": "CLEARED",
    },
    {
        "player": "Black Lotus",
        "year": "1993",
        "set_name": "Magic Alpha",
        "variation": "",
        "card_number": "NNO",
        "category": "Magic",
        "condition": "CGC 9.5",
        "slab_serial_number": "10928374",
        "estimated_value": 35000.00,
        "ai_status": "CLEARED",
    },
    {
        "player": "Blue-Eyes White Dragon",
        "year": "2002",
        "set_name": "Legend of Blue Eyes White Dragon",
        "variation": "1st Edition Ultra Rare",
        "card_number": "LOB-001",
        "category": "Yugioh",
        "condition": "PSA 10",
        "slab_serial_number": "61029384",
        "estimated_value": 4200.00,
        "ai_status": "REVIEW VARIATION",
    },
    {
        "player": "Jon Jones",
        "year": "2021",
        "set_name": "Panini Prizm UFC",
        "variation": "Gold Prizm /10",
        "card_number": "007",
        "category": "UFC/MMA",
        "condition": "Raw",
        "slab_serial_number": "",
        "estimated_value": 500.00,
        "ai_status": "REVIEW VARIATION",
    },
    {
        "player": "Max Verstappen",
        "year": "2020",
        "set_name": "Topps Chrome F1",
        "variation": "Orange Refractor /25",
        "card_number": "003",
        "category": "Racing",
        "condition": "TAG 10",
        "slab_serial_number": "TAG-882910",
        "estimated_value": 1500.00,
        "ai_status": "REVIEW VARIATION",
    },
    {
        "player": "Tiger Woods",
        "year": "2001",
        "set_name": "Upper Deck Golf",
        "variation": "",
        "card_number": "001",
        "category": "Golf",
        "condition": "PSA 10",
        "slab_serial_number": "19283746",
        "estimated_value": 650.00,
        "ai_status": "CLEARED",
    },
]


def load_fixture_data() -> list[dict]:
    \"\"\"Loads fixtures from fixtures/mock_card_data.json if present, else builtins.\"\"\"
    fixtures_file = os.path.join(os.path.dirname(__file__), "fixtures", "mock_card_data.json")
    if os.path.exists(fixtures_file):
        try:
            with open(fixtures_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            logger.warning(f"Could not load {fixtures_file}: {e}")
    return _BUILTIN_FIXTURES


def _prepare_image_part(image_input: Union[str, Path, bytes]) -> types.Part:
    \"\"\"Prepares a google.genai types.Part from file path or bytes.\"\"\"
    if isinstance(image_input, (str, Path)):
        file_path = str(image_input)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image file not found: {file_path}")
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "image/jpeg"
        with open(file_path, "rb") as f:
            data = f.read()
        return types.Part.from_bytes(data=data, mime_type=mime_type)
    elif isinstance(image_input, bytes):
        return types.Part.from_bytes(data=image_input, mime_type="image/jpeg")
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")


def MockVisionExtractor(
    image_path: Union[str, Path],
    back_image_path: Optional[Union[str, Path]] = None,
    parent_image_id: Optional[Union[int, str]] = None,
    child_card_id: Optional[Union[int, str]] = None,
) -> CardExtractionSchema:
    \"\"\"
    Deterministic mock extractor for offline testing and CI/CD runs.
    1. Matches fixture keywords in image path if present.
    2. Parses structured filename tokens (e.g. 2020_Panini_Prizm_Luka_Doncic_Silver_PSA_10.jpg).
    3. Hashes image path deterministically to select from rich fixture pool.
    \"\"\"
    img_str = str(image_path)
    back_str = str(back_image_path) if back_image_path else ""
    basename = os.path.splitext(os.path.basename(img_str))[0].lower()

    fixtures = load_fixture_data()

    # Strategy 1: Keyword matching against known players/subjects
    matched_fixture = None
    for fix in fixtures:
        player_clean = fix.get("player", "").lower().split("(")[0].strip()
        player_words = [w for w in player_clean.split() if len(w) > 2]
        if any(w in basename for w in player_words):
            matched_fixture = fix
            break

    # Strategy 2: Structured filename regex parsing (e.g., '2020_Panini_Prizm_Luka_Doncic_Silver_Prizm_PSA_10')
    if not matched_fixture:
        year_match = re.search(r"\b(19\d\d|20\d\d)\b", basename)
        if year_match:
            year_val = year_match.group(1)
            cat_val = "Basketball"
            for cat_k, cat_v in CATEGORY_MAP.items():
                if cat_k in basename:
                    cat_val = cat_v
                    break

            cond_val = "Raw"
            slab_val = ""
            for grader in ("psa", "bgs", "sgc", "cgc", "tag"):
                grader_match = re.search(rf"\b{grader}[_\s\-]?(\d+(?:\.\d+)?)\b", basename)
                if grader_match:
                    cond_val = f"{grader.upper()} {grader_match.group(1)}"
                    slab_val = f"{abs(hash(basename)) % 100000000:08d}"
                    break

            var_val = ""
            if "silver" in basename:
                var_val = "Silver Prizm"
            elif "refractor" in basename:
                var_val = "Refractor"
            elif "holo" in basename:
                var_val = "Holo"

            matched_fixture = {
                "player": "Test Subject",
                "year": year_val,
                "set_name": "Test Set",
                "variation": var_val,
                "card_number": "001",
                "category": cat_val,
                "condition": cond_val,
                "slab_serial_number": slab_val,
                "estimated_value": 100.0,
                "ai_status": "REVIEW VARIATION" if var_val else "CLEARED",
            }

    # Strategy 3: Deterministic hash selection from fixture bank
    if not matched_fixture:
        hash_idx = int(hashlib.md5(img_str.encode("utf-8")).hexdigest(), 16) % len(fixtures)
        matched_fixture = fixtures[hash_idx]

    # Build schema
    raw_category = matched_fixture.get("category", "Basketball")
    category_val = CATEGORY_MAP.get(str(raw_category).lower(), raw_category)
    if category_val not in VALID_CATEGORIES:
        category_val = CardCategory.BASKETBALL.value

    condition_val = matched_fixture.get("condition", "Raw")
    slab_val = matched_fixture.get("slab_serial_number", "")
    if condition_val == "Raw":
        slab_val = ""

    variation_val = matched_fixture.get("variation", "")
    ai_status_val = AIStatus.REVIEW_VARIATION if variation_val else AIStatus.CLEARED

    notes_val = ""
    if parent_image_id is not None and child_card_id is not None:
        notes_val = format_notes(parent_image_id, child_card_id)
    elif matched_fixture.get("notes"):
        notes_val = matched_fixture.get("notes")

    return CardExtractionSchema(
        player=matched_fixture.get("player", "Unknown Player"),
        year=str(matched_fixture.get("year", "2020")),
        set_name=matched_fixture.get("set_name", "Unknown Set"),
        variation=variation_val,
        card_number=str(matched_fixture.get("card_number", "")),
        category=category_val,
        condition=condition_val,
        slab_serial_number=slab_val,
        estimated_value=float(matched_fixture.get("estimated_value", 0.0)),
        notes=notes_val,
        image=img_str,
        back_image=back_str,
        ai_status=ai_status_val,
    )


def extract_card_from_image(
    image_path: Union[str, Path, bytes],
    back_image_path: Optional[Union[str, Path, bytes]] = None,
    mock: bool = False,
    api_key: Optional[str] = None,
    client: Optional[genai.Client] = None,
    model: str = DEFAULT_VISION_MODEL,
    parent_image_id: Optional[Union[int, str]] = None,
    child_card_id: Optional[Union[int, str]] = None,
) -> CardExtractionSchema:
    \"\"\"
    Extracts structured sports card data from front/back card images.
    Uses Google Gemini 2.5 Flash with Pydantic structured output.
    Falls back to deterministic MockVisionExtractor if mock=True or GEMINI_API_KEY is missing.
    \"\"\"
    resolved_api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()

    if mock or (not resolved_api_key and client is None):
        if not mock and not resolved_api_key and client is None:
            logger.warning("GEMINI_API_KEY not found in environment. Falling back to MockVisionExtractor.")
        return MockVisionExtractor(
            image_path=str(image_path) if not isinstance(image_path, bytes) else "raw_bytes.jpg",
            back_image_path=str(back_image_path) if back_image_path and not isinstance(back_image_path, bytes) else None,
            parent_image_id=parent_image_id,
            child_card_id=child_card_id,
        )

    parts: list[Any] = []
    front_part = _prepare_image_part(image_path)
    parts.append(front_part)

    if back_image_path:
        back_part = _prepare_image_part(back_image_path)
        parts.append(back_part)

    parts.append(
        "Analyze the provided sports card image(s) and extract the exact card catalog details into the specified schema."
    )

    if client is None:
        client = genai.Client(api_key=resolved_api_key)

    config = types.GenerateContentConfig(
        system_instruction=VISION_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=CardExtractionSchema,
        temperature=0.1,
    )

    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=config,
    )

    raw_text = response.text
    if not raw_text:
        raise ValueError("Gemini API returned an empty response.")

    extraction = CardExtractionSchema.model_validate_json(raw_text)

    image_str = str(image_path) if not isinstance(image_path, bytes) else ""
    back_image_str = str(back_image_path) if back_image_path and not isinstance(back_image_path, bytes) else ""

    slab_serial = extraction.slab_serial_number
    if extraction.condition == "Raw":
        slab_serial = ""

    ai_status = extraction.ai_status
    if extraction.variation.strip() and ai_status == AIStatus.CLEARED:
        ai_status = AIStatus.REVIEW_VARIATION

    notes_str = extraction.notes
    if parent_image_id is not None and child_card_id is not None:
        notes_str = format_notes(parent_image_id, child_card_id)

    return CardExtractionSchema(
        player=extraction.player,
        year=extraction.year,
        set_name=extraction.set_name,
        variation=extraction.variation,
        card_number=extraction.card_number,
        category=extraction.category,
        condition=extraction.condition,
        slab_serial_number=slab_serial,
        estimated_value=extraction.estimated_value,
        notes=notes_str,
        image=image_str or extraction.image,
        back_image=back_image_str or extraction.back_image,
        ai_status=ai_status,
    )


def extraction_to_card_record(
    extraction: CardExtractionSchema,
    investment: float = 0.0,
    quantity: int = 1,
    parent_image_id: Optional[Union[int, str]] = None,
    child_card_id: Optional[Union[int, str]] = None,
    tags: str = "",
) -> CardRecord:
    \"\"\"Converts a CardExtractionSchema into a master 21-variable CardRecord.\"\"\"
    data = extraction.model_dump()
    data["investment"] = investment
    data["quantity"] = quantity
    if parent_image_id is not None and child_card_id is not None:
        data["notes"] = format_notes(parent_image_id, child_card_id)
    if tags:
        data["tags"] = tags
    return CardRecord(**data)


def batch_extract_cards(
    image_paths: List[Union[str, Path]],
    mock: bool = False,
    api_key: Optional[str] = None,
    client: Optional[genai.Client] = None,
    parent_image_id: Optional[Union[int, str]] = None,
) -> List[CardExtractionSchema]:
    \"\"\"Batch processes a list of image paths up to the 500-card circuit breaker limit.\"\"\"
    if len(image_paths) > 500:
        raise ValueError(f"Batch size {len(image_paths)} exceeds 500-card circuit breaker limit.")

    results: list[CardExtractionSchema] = []
    for idx, path in enumerate(image_paths, start=1):
        child_id = idx
        card_extraction = extract_card_from_image(
            image_path=path,
            mock=mock,
            api_key=api_key,
            client=client,
            parent_image_id=parent_image_id,
            child_card_id=child_id,
        )
        results.append(card_extraction)
    return results


def batch_extract_to_records(
    image_paths: List[Union[str, Path]],
    mock: bool = False,
    api_key: Optional[str] = None,
    client: Optional[genai.Client] = None,
    investment: float = 0.0,
    parent_image_id: Optional[Union[int, str]] = None,
) -> List[CardRecord]:
    \"\"\"Batch extracts card images and converts them directly to CardRecord objects.\"\"\"
    extractions = batch_extract_cards(
        image_paths=image_paths,
        mock=mock,
        api_key=api_key,
        client=client,
        parent_image_id=parent_image_id,
    )
    return [
        extraction_to_card_record(ext, investment=investment)
        for ext in extractions
    ]
```

---

## 5. Proposed Unit Test Suite: `tests/test_ingest_vision.py`

```python
\"\"\"
tests/test_ingest_vision.py - Comprehensive Unit Test Suite for AI Vision Ingest.
Tests deterministic MockVisionExtractor, google.genai structured extraction,
Pydantic schema validation, batch ingestion, error handling, and DB integration.
\"\"\"

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from pydantic import ValidationError

# Ensure ecosystem_hub is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import (
    CardExtractionSchema,
    CardRecord,
    CardCategory,
    AIStatus,
    VALID_CATEGORIES,
    format_notes,
)
from database import init_db, insert_card, get_card_by_id
from vision_ingest import (
    MockVisionExtractor,
    extract_card_from_image,
    extraction_to_card_record,
    batch_extract_cards,
    batch_extract_to_records,
    DEFAULT_VISION_MODEL,
    load_fixture_data,
)


@pytest.fixture
def temp_image_file(tmp_path):
    \"\"\"Creates a temporary dummy image file on disk.\"\"\"
    img_file = tmp_path / "sample_test_card.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00")
    return str(img_file)


@pytest.fixture
def temp_db(tmp_path):
    \"\"\"Provides a fresh isolated SQLite database for vision insertion tests.\"\"\"
    db_file = str(tmp_path / "test_vision_portfolio.db")
    init_db(db_file)
    return db_file


# ---------------------------------------------------------------------------
# Tier 1: MockVisionExtractor Determinism & Pattern Matching
# ---------------------------------------------------------------------------

class TestMockVisionExtractor:
    \"\"\"Tests the deterministic mock vision extractor.\"\"\"

    def test_fixture_loading(self):
        fixtures = load_fixture_data()
        assert len(fixtures) >= 12
        for f in fixtures:
            assert "player" in f
            assert "year" in f
            assert "set_name" in f
            assert "category" in f

    def test_known_fixture_keyword_matching(self):
        # Luka
        luka = MockVisionExtractor("path/to/sample_luka_front.jpg")
        assert "Luka" in luka.player
        assert luka.year == "2020"
        assert luka.category == CardCategory.BASKETBALL
        assert luka.condition == "PSA 10"
        assert luka.slab_serial_number == "48192041"

        # Charizard
        zard = MockVisionExtractor("charizard_card.png")
        assert "Charizard" in zard.player
        assert zard.year == "1999"
        assert zard.category == CardCategory.POKEMON
        assert zard.condition == "SGC 10"

        # Ohtani
        ohtani = MockVisionExtractor("shohei_ohtani_refractor.jpg")
        assert "Ohtani" in ohtani.player
        assert ohtani.year == "2018"
        assert ohtani.category == CardCategory.BASEBALL
        assert ohtani.condition == "BGS 9.5"

    def test_filename_pattern_inference(self):
        custom = MockVisionExtractor("2021_panini_prizm_basketball_psa10_test.jpg")
        assert custom.year == "2021"
        assert custom.category == CardCategory.BASKETBALL
        assert custom.condition == "PSA 10"
        assert custom.slab_serial_number != ""

    def test_deterministic_hash_fallback(self):
        # Same random path should always produce identical result
        res1 = MockVisionExtractor("arbitrary_unknown_image_xyz.jpg")
        res2 = MockVisionExtractor("arbitrary_unknown_image_xyz.jpg")
        assert res1.player == res2.player
        assert res1.year == res2.year
        assert res1.set_name == res2.set_name
        assert res1.category == res2.category
        assert res1.condition == res2.condition

    def test_notes_formatting_in_mock(self):
        res = MockVisionExtractor("card.jpg", parent_image_id=8492, child_card_id=105)
        assert res.notes == "8492-105"

    def test_raw_condition_slab_isolation(self):
        res = MockVisionExtractor("sample_acuna_front.jpg")
        assert res.condition == "Raw"
        assert res.slab_serial_number == ""


# ---------------------------------------------------------------------------
# Tier 2: extract_card_from_image Offline & Fallback Modes
# ---------------------------------------------------------------------------

class TestExtractCardOffline:
    \"\"\"Tests extract_card_from_image in offline and mock modes.\"\"\"

    def test_explicit_mock_flag(self, temp_image_file):
        card = extract_card_from_image(temp_image_file, mock=True)
        assert isinstance(card, CardExtractionSchema)
        assert card.category in VALID_CATEGORIES
        assert card.image == temp_image_file

    def test_missing_api_key_automatic_fallback(self, temp_image_file):
        with patch.dict(os.environ, {}, clear=True):
            card = extract_card_from_image(temp_image_file, mock=False)
            assert isinstance(card, CardExtractionSchema)
            assert card.category in VALID_CATEGORIES

    def test_dual_image_paths(self, tmp_path):
        front = str(tmp_path / "front.jpg")
        back = str(tmp_path / "back.jpg")
        Path(front).write_bytes(b"front")
        Path(back).write_bytes(b"back")

        card = extract_card_from_image(front, back_image_path=back, mock=True)
        assert card.image == front
        assert card.back_image == back


# ---------------------------------------------------------------------------
# Tier 3: Mocked Google GenAI SDK Interaction
# ---------------------------------------------------------------------------

class TestGeminiSDKExtraction:
    \"\"\"Tests live SDK execution paths using unittest mocks.\"\"\"

    def test_successful_gemini_client_extraction(self, temp_image_file):
        mock_response_json = \"\"\"{
            "player": "Victor Wembanyama",
            "year": "2023",
            "set_name": "Panini Prizm",
            "variation": "Silver Prizm",
            "card_number": "136",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "88192031",
            "estimated_value": 850.0,
            "notes": "",
            "image": "",
            "back_image": "",
            "ai_status": "REVIEW VARIATION"
        }\"\"\"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = mock_response_json
        mock_client.models.generate_content.return_value = mock_response

        card = extract_card_from_image(
            image_path=temp_image_file,
            mock=False,
            api_key="test_api_key_123",
            client=mock_client,
            parent_image_id=9001,
            child_card_id=1,
        )

        assert card.player == "Victor Wembanyama"
        assert card.year == "2023"
        assert card.variation == "Silver Prizm"
        assert card.category == CardCategory.BASKETBALL
        assert card.condition == "PSA 10"
        assert card.slab_serial_number == "88192031"
        assert card.notes == "9001-001"
        assert card.ai_status == AIStatus.REVIEW_VARIATION

        # Verify client call parameters
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == DEFAULT_VISION_MODEL
        assert call_kwargs["config"].response_schema == CardExtractionSchema
        assert call_kwargs["config"].response_mime_type == "application/json"

    def test_missing_file_raises_error_in_live_mode(self):
        mock_client = MagicMock()
        with pytest.raises(FileNotFoundError):
            extract_card_from_image(
                image_path="non_existent_card_path_12345.jpg",
                mock=False,
                api_key="test_key",
                client=mock_client,
            )


# ---------------------------------------------------------------------------
# Tier 4: Database Integration & Conversion
# ---------------------------------------------------------------------------

class TestVisionDatabaseIntegration:
    \"\"\"Tests converting extracted card schemas to CardRecord and persisting to SQLite.\"\"\"

    def test_extraction_to_card_record_conversion(self):
        extraction = CardExtractionSchema(
            player="Luka Dončić",
            year="2020",
            set_name="Panini Prizm",
            variation="Silver Prizm",
            card_number="75",
            category=CardCategory.BASKETBALL,
            condition="PSA 10",
            slab_serial_number="48192041",
            estimated_value=350.0,
            image="sample_luka.jpg",
        )

        record = extraction_to_card_record(
            extraction,
            investment=150.0,
            quantity=1,
            parent_image_id=8492,
            child_card_id=101,
            tags="graded, prizm",
        )

        assert isinstance(record, CardRecord)
        assert record.investment == 150.0
        assert record.notes == "8492-101"
        assert record.tags == "graded, prizm"
        assert record.query == "2020 Panini Prizm Luka Dončić Silver Prizm PSA 10"
        assert record.ai_status == AIStatus.REVIEW_VARIATION

    def test_persist_extracted_card_to_db(self, temp_db):
        extraction = MockVisionExtractor("sample_luka_front.jpg", parent_image_id=8492, child_card_id=101)
        record = extraction_to_card_record(extraction, investment=120.0)

        card_id = insert_card(record, db_path=temp_db)
        assert card_id is not None
        assert card_id > 0

        saved = get_card_by_id(card_id, db_path=temp_db)
        assert saved is not None
        assert saved["player"] == "Luka Dončić"
        assert saved["investment"] == 120.0
        assert saved["notes"] == "8492-101"


# ---------------------------------------------------------------------------
# Tier 5: Batch Processing & Circuit Breaker
# ---------------------------------------------------------------------------

class TestBatchVisionProcessing:
    \"\"\"Tests batch ingestion pipelines.\"\"\"

    def test_batch_extract_cards(self):
        paths = ["card1.jpg", "card2.jpg", "card3.jpg"]
        results = batch_extract_cards(paths, mock=True, parent_image_id=100)
        assert len(results) == 3
        assert results[0].notes == "0100-001"
        assert results[1].notes == "0100-002"
        assert results[2].notes == "0100-003"

    def test_batch_extract_to_records(self):
        paths = ["sample_luka_front.jpg", "sample_charizard.png"]
        records = batch_extract_to_records(paths, mock=True, investment=50.0, parent_image_id=200)
        assert len(records) == 2
        for r in records:
            assert isinstance(r, CardRecord)
            assert r.investment == 50.0

    def test_batch_circuit_breaker_limit(self):
        paths = [f"card_{i}.jpg" for i in range(501)]
        with pytest.raises(ValueError, match="circuit breaker"):
            batch_extract_cards(paths, mock=True)
```

---

## 6. Verification Plan & Recommendations

1. **Independent Verification**:
   - Run `python -m pytest sports_cards/ecosystem_hub/tests/test_ingest_vision.py` once implemented.
   - Run `python -m pytest sports_cards/ecosystem_hub/tests/` to guarantee no regressions with Milestone 1 tests.
2. **Key Findings for Implementer**:
   - `google.genai` SDK is already installed and verified on Python 3.13.
   - `types.GenerateContentConfig` with `response_schema=CardExtractionSchema` works out-of-the-box.
   - Mock extractor operates completely offline without network calls or API keys, satisfying Rule R2 (Zero-Discretion Mandate) and all project acceptance criteria.

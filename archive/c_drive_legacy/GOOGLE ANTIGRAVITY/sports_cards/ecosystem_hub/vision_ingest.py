"""
vision_ingest.py - AI Vision Ingestion Pipeline for Sports Card Ecosystem Hub.
Uses google.genai SDK with gemini-2.5-flash and Pydantic structured output extraction.
Includes deterministic MockVisionExtractor for 100% testability in offline environments.
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, List, Optional, Union

from google import genai
from google.genai import types

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

# Default vision model
DEFAULT_VISION_MODEL = "gemini-2.5-flash"

# Multimodal card extraction system instruction
VISION_SYSTEM_INSTRUCTION = """
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
"""

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
        "ai_status": "NEEDS REVIEW",
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


def _normalize_text_for_matching(text: str) -> str:
    """Strips accents and converts hyphens/underscores to spaces for fuzzy keyword matching."""
    norm = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8").lower()
    return re.sub(r"[_\-]+", " ", norm)


def load_fixture_data() -> list[dict[str, Any]]:
    """Loads fixtures from fixtures/mock_card_data.json if present, else builtins."""
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
    """Prepares a google.genai types.Part from file path or bytes."""
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
    """
    Deterministic mock extractor for offline testing and CI/CD runs.
    1. Matches fixture keywords in image path if present (accent-insensitive).
    2. Parses structured filename tokens (e.g. 2021_panini_prizm_basketball_psa10_test.jpg).
    3. Hashes image path deterministically to select from fixture pool.
    """
    img_str = str(image_path)
    back_str = str(back_image_path) if back_image_path else ""
    basename = os.path.splitext(os.path.basename(img_str))[0]
    basename_norm = _normalize_text_for_matching(basename)

    fixtures = load_fixture_data()

    # Strategy 1: Keyword matching against known players/subjects (accent-normalized)
    matched_fixture = None
    for fix in fixtures:
        player_clean = fix.get("player", "").split("(")[0]
        player_norm = _normalize_text_for_matching(player_clean)
        player_words = [w for w in player_norm.split() if len(w) > 2]
        if any(w in basename_norm for w in player_words):
            matched_fixture = fix
            break

    # Strategy 2: Structured filename regex parsing (e.g. 2021 panini prizm basketball psa10 test)
    if not matched_fixture:
        year_match = re.search(r"\b(19\d\d|20\d\d)\b", basename_norm)
        if year_match:
            year_val = year_match.group(1)
            cat_val = "Basketball"
            for cat_k, cat_v in CATEGORY_MAP.items():
                if cat_k in basename_norm:
                    cat_val = cat_v
                    break

            cond_val = "Raw"
            slab_val = ""
            for grader in ("psa", "bgs", "sgc", "cgc", "tag", "bvg"):
                grader_match = re.search(rf"\b{grader}\s*(\d+(?:\.\d+)?)\b", basename_norm)
                if grader_match:
                    cond_val = f"{grader.upper()} {grader_match.group(1)}"
                    slab_val = f"{abs(hash(basename_norm)) % 100000000:08d}"
                    break

            var_val = ""
            if "silver" in basename_norm:
                var_val = "Silver Prizm"
            elif "refractor" in basename_norm:
                var_val = "Refractor"
            elif "holo" in basename_norm:
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

    # Normalize category
    raw_category = matched_fixture.get("category", "Basketball")
    category_val = CATEGORY_MAP.get(str(raw_category).lower(), raw_category)
    if category_val not in VALID_CATEGORIES:
        category_val = CardCategory.BASKETBALL.value

    # Normalize condition & slab serial
    condition_val = matched_fixture.get("condition", "Raw")
    slab_val = matched_fixture.get("slab_serial_number", "")
    if condition_val == "Raw":
        slab_val = ""

    variation_val = matched_fixture.get("variation", "")
    raw_status = matched_fixture.get("ai_status", AIStatus.CLEARED.value)
    if variation_val and raw_status == AIStatus.CLEARED.value:
        ai_status_val = AIStatus.REVIEW_VARIATION
    else:
        ai_status_val = AIStatus(raw_status) if isinstance(raw_status, str) else raw_status

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
    """
    Extracts structured sports card data from front/back card images.
    Uses Google Gemini 2.5 Flash with Pydantic structured output.
    Falls back to deterministic MockVisionExtractor if mock=True or GEMINI_API_KEY is missing.
    """
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

    try:
        response = client.models.generate_content(
            model=model,
            contents=parts,
            config=config,
        )
    except Exception as e:
        logger.error(f"Gemini API generate_content call failed: {e}")
        raise

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
    extraction: Union[CardExtractionSchema, dict[str, Any]],
    investment: float = 0.0,
    quantity: int = 1,
    parent_image_id: Optional[Union[int, str]] = None,
    child_card_id: Optional[Union[int, str]] = None,
    tags: str = "",
    ladder_id: str = "",
    db_path: Optional[str] = None,
) -> CardRecord:
    """Converts a CardExtractionSchema into a master 21-variable CardRecord."""
    data = extraction.model_dump() if isinstance(extraction, CardExtractionSchema) else dict(extraction)

    existing_notes = data.get("notes", "").strip()
    if parent_image_id is not None and child_card_id is not None:
        data["notes"] = format_notes(parent_image_id, child_card_id)
    elif parent_image_id is not None and not existing_notes:
        next_c = get_next_child_id(parent_image_id, db_path=db_path) if db_path else 101
        data["notes"] = format_notes(parent_image_id, next_c)

    data["investment"] = max(0.0, float(investment))
    data["quantity"] = max(1, int(quantity))
    if tags:
        data["tags"] = tags
    if ladder_id:
        data["ladder_id"] = ladder_id

    raw_status = data.get("ai_status", AIStatus.CLEARED)
    status_val = AIStatus(raw_status) if isinstance(raw_status, str) else raw_status
    var_val = data.get("variation", "").strip()

    if status_val == AIStatus.NEEDS_REVIEW:
        data["ai_status"] = AIStatus.NEEDS_REVIEW
    elif var_val:
        data["ai_status"] = AIStatus.REVIEW_VARIATION
    else:
        data["ai_status"] = status_val

    return CardRecord(**data)


def batch_extract_cards(
    image_paths: List[Union[str, Path]],
    mock: bool = False,
    api_key: Optional[str] = None,
    client: Optional[genai.Client] = None,
    parent_image_id: Optional[Union[int, str]] = None,
) -> List[CardExtractionSchema]:
    """Batch processes a list of image paths up to the 500-card circuit breaker limit."""
    if len(image_paths) > CIRCUIT_BREAKER_BATCH_LIMIT:
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
    """Batch extracts card images and converts them directly to CardRecord objects."""
    extractions = batch_extract_cards(
        image_paths=image_paths,
        mock=mock,
        api_key=api_key,
        client=client,
        parent_image_id=parent_image_id,
    )
    records = []
    for ext in extractions:
        records.append(
            extraction_to_card_record(
                ext,
                investment=investment,
                parent_image_id=parent_image_id,
                child_card_id=ext.notes.split("-")[1] if "-" in ext.notes else None,
            )
        )
    return records


def ingest_vision_card(
    extraction: Union[CardExtractionSchema, dict[str, Any]],
    parent_image_id: Optional[Union[int, str]] = None,
    child_card_id: Optional[Union[int, str]] = None,
    date_purchased: Optional[str] = None,
    investment: float = 0.0,
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    """Bridges a single vision extraction into database, returning inserted ID."""
    record = extraction_to_card_record(
        extraction=extraction,
        investment=investment,
        parent_image_id=parent_image_id,
        child_card_id=child_card_id,
        db_path=db_path,
    )
    if date_purchased:
        record.date_purchased = date_purchased
    return insert_card(record, db_path=db_path)


def ingest_vision_batch(
    extractions_or_paths: List[Union[CardExtractionSchema, dict[str, Any], str, Path]],
    parent_id: Optional[Union[int, str]] = None,
    date_purchased: Optional[str] = None,
    investment: float = 0.0,
    db_path: str = DEFAULT_DB_PATH,
    chunk_size: int = CIRCUIT_BREAKER_BATCH_LIMIT,
) -> List[int]:
    """Bridges batch vision extractions or image paths into database with sequential notes."""
    if not extractions_or_paths:
        return []

    start_child_id = get_next_child_id(parent_id, db_path=db_path) if parent_id is not None else None

    records: list[CardRecord] = []
    for idx, item in enumerate(extractions_or_paths):
        current_child = (start_child_id + idx) if start_child_id is not None else None
        if isinstance(item, (str, Path)):
            extraction = extract_card_from_image(item, mock=True, parent_image_id=parent_id, child_card_id=current_child)
        else:
            extraction = item

        rec = extraction_to_card_record(
            extraction=extraction,
            investment=investment,
            parent_image_id=parent_id,
            child_card_id=current_child,
            db_path=db_path,
        )
        if date_purchased:
            rec.date_purchased = date_purchased
        records.append(rec)

    return insert_cards_batch(records, db_path=db_path, chunk_size=chunk_size)

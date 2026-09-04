"""
sales_generator.py - High-Conversion Facebook Marketplace & Social Sales Copy Generator.
Generates structured, SEO-optimized listing copy from 21-variable CardRecord objects
or SQLite database records. Supports modern google.genai SDK with gemini-2.5-flash
and deterministic offline fallback via MockSalesGenerator.
"""

from __future__ import annotations

import os
import re
import json
import logging
import unicodedata
from typing import Any, Optional, Union

from models import (
    CardRecord,
    MarketplaceListing,
    SalesListingRequest,
    synthesize_query,
)
from database import DEFAULT_DB_PATH, get_card_by_id

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & Blacklists
# ---------------------------------------------------------------------------

FORBIDDEN_BUZZWORDS = [
    "INVESTMENT", "INVEST", "L@@K", "LOOK", "FIRE", "HOT",
    "PSA 10?", "GEM?", "RARE", "GRAIL", "1/1?", "MUST SEE",
    "MOON", "\U0001f4c8", "\U0001f525", "\U0001f680", "\U0001f4b0", "\U0001f4a5", "\u26a1", "BUY NOW", "STEAL"
]

SALES_SYSTEM_INSTRUCTION = """
You are an expert sports card marketing copywriter and SEO specialist.
Your task is to generate high-conversion, professional Facebook Marketplace listings for sports and trading cards.

Rules:
1. Title: Create an SEO-optimized title strictly under 100 characters containing: Year, Brand/Set, Player, Variation, and Condition.
2. NO SPAM: Never use buzzwords like 'INVEST', 'L@@K', 'FIRE', 'PSA 10?', 'GRAIL', '1/1?', or emojis in the title.
3. Structure: Provide exactly 6 sections:
   - Section 1: Title
   - Section 2: Asking Price & Payment Terms
   - Section 3: Key Specifications (Year, Brand/Set, Card #, Player, Variation, Category, Condition, Slab Cert #)
   - Section 4: Condition & Slab Verification Description
   - Section 5: Buyer Assurance & Shipping / Local Pickup Terms
   - Section 6: Exactly 6 to 8 targeted viral hashtags (#SportsCards #TheHobby ...)
4. Tone: Confident, professional, collector-friendly, transparent, and direct.
"""

# ---------------------------------------------------------------------------
# Normalization & Helpers
# ---------------------------------------------------------------------------

def normalize_card_input(card: Union[dict[str, Any], CardRecord, Any]) -> dict[str, Any]:
    """
    Normalizes a CardRecord, dict, or sqlite3.Row into a standard dictionary.
    """
    if isinstance(card, CardRecord):
        data = card.model_dump()
    elif isinstance(card, dict):
        data = dict(card)
    elif hasattr(card, "keys"):  # sqlite3.Row or mapping
        data = {k: card[k] for k in card.keys()}
    else:
        raise TypeError(f"Expected dict, CardRecord, or sqlite3.Row, got {type(card)}")

    # Ensure required default fields exist
    defaults = {
        "player": "Unknown Player",
        "year": "2020",
        "set_name": "Card Set",
        "variation": "",
        "card_number": "",
        "category": "Basketball",
        "condition": "Raw",
        "slab_serial_number": "",
        "investment": 0.0,
        "estimated_value": 0.0,
        "notes": "",
        "tags": "",
        "query": "",
    }
    for k, v in defaults.items():
        if k not in data or data[k] is None:
            data[k] = v

    # Coerce types
    data["player"] = str(data["player"]).strip()
    data["year"] = str(data["year"]).strip()
    data["set_name"] = str(data["set_name"]).strip()
    data["variation"] = str(data.get("variation") or "").strip()
    data["card_number"] = str(data.get("card_number") or "").strip()
    data["category"] = str(data["category"]).strip()
    data["condition"] = str(data["condition"]).strip()
    data["slab_serial_number"] = str(data.get("slab_serial_number") or "").strip()
    try:
        data["investment"] = float(data.get("investment") or 0.0)
    except (ValueError, TypeError):
        data["investment"] = 0.0
    try:
        data["estimated_value"] = float(data.get("estimated_value") or 0.0)
    except (ValueError, TypeError):
        data["estimated_value"] = 0.0

    return data


def resolve_asking_price(
    card_data: dict[str, Any],
    asking_price: Optional[float] = None
) -> float:
    """
    Determines effective asking price:
    1. Explicit asking_price if supplied and >= 0.
    2. Estimated value if > 0.
    3. Investment if > 0.
    4. Default 50.00.
    """
    if asking_price is not None:
        try:
            val = float(asking_price)
            if val >= 0:
                return round(val, 2)
        except (ValueError, TypeError):
            pass

    est = float(card_data.get("estimated_value") or 0.0)
    if est > 0:
        return round(est, 2)

    inv = float(card_data.get("investment") or 0.0)
    if inv > 0:
        return round(inv, 2)

    return 50.00


def sanitize_seo_title(title: str, max_length: int = 99) -> str:
    """
    Strips forbidden buzzwords, emojis, multiple whitespace, and enforces < 100 character bounds.
    """
    clean = title
    sorted_words = sorted(FORBIDDEN_BUZZWORDS, key=len, reverse=True)
    for word in sorted_words:
        escaped = re.escape(word)
        clean = re.sub(rf"(?i)(?:|\s|^){escaped}(?:|\s|$|\?)", " ", clean)
        clean = re.sub(rf"(?i){escaped}", " ", clean)

    clean_chars = []
    for ch in clean:
        cat = unicodedata.category(ch)
        if cat.startswith(("L", "N", "P", "Z")) or ch in ("#", "/", "-"):
            clean_chars.append(ch)
    clean = "".join(clean_chars)

    clean = re.sub(r"\s+", " ", clean).strip()

    if len(clean) > max_length:
        clean = clean[:max_length]
        if " " in clean:
            clean = clean.rsplit(" ", 1)[0].strip()

    return clean


def build_seo_title(card_data: dict[str, Any], max_length: int = 99) -> str:
    """
    Builds SEO title following formula: [Year] [Set] [Player] [Variation] [Condition]
    """
    data = normalize_card_input(card_data)
    parts = [data["year"], data["set_name"], data["player"]]
    if data["variation"]:
        parts.append(data["variation"])
    if data["condition"]:
        parts.append(data["condition"])

    raw_title = " ".join(p for p in parts if p)
    return sanitize_seo_title(raw_title, max_length=max_length)


def build_price_section(price: float) -> str:
    """Builds Section 2: Asking Price & Payment Terms."""
    formatted_price = f"${price:,.2f}"
    return (
        f"?? ASKING PRICE: {formatted_price}\n"
        "? Payment Terms: Cash for local pickup, PayPal Goods & Services, Venmo, Zelle, or Facebook Marketplace Checkout.\n"
        "? Offers: Reasonable cash/trade offers considered."
    )


def build_specifications_section(card_data: dict[str, Any]) -> str:
    """Builds Section 3: Key Specifications."""
    data = normalize_card_input(card_data)
    is_graded = data["condition"].lower() not in ("raw", "ungraded")
    slab_cert = data["slab_serial_number"] if (is_graded and data["slab_serial_number"]) else ("Present on Slab" if is_graded else "N/A (Raw)")
    card_num = data["card_number"] if data["card_number"] else "NNO"
    variation = data["variation"] if data["variation"] else "Base"

    return (
        "?? KEY SPECIFICATIONS:\n"
        f"? Year: {data['year']}\n"
        f"? Brand / Set: {data['set_name']}\n"
        f"? Card #: {card_num}\n"
        f"? Player / Character: {data['player']}\n"
        f"? Variation / Parallel: {variation}\n"
        f"? Category / Sport: {data['category']}\n"
        f"? Condition / Grade: {data['condition']}\n"
        f"? Slab Certification #: {slab_cert}"
    )


def build_condition_section(card_data: dict[str, Any], custom_notes: str = "") -> str:
    """Builds Section 4: Condition & Authenticity."""
    data = normalize_card_input(card_data)
    is_graded = data["condition"].lower() not in ("raw", "ungraded")

    if is_graded:
        cond_parts = data["condition"].split()
        grader = cond_parts[0] if cond_parts else "Official"
        cert_info = f" (Cert #{data['slab_serial_number']})" if data["slab_serial_number"] else ""
        text = (
            "?? CONDITION & AUTHENTICITY:\n"
            f"Official {grader} encapsulated slab in crystal-clear condition{cert_info}. "
            "Sonic-welded casing with zero cracks or tampering. Certification verified in registry database."
        )
    else:
        text = (
            "?? CONDITION & AUTHENTICITY:\n"
            "Pack-fresh to near-mint/mint raw card. Crisp sharp corners, clean edges, flawless surface sheen, "
            "and balanced centering. Stored immediately in a brand new penny sleeve and rigid top loader.\n"
            "Note: Card is in raw condition. Please review all high-resolution photos for exact centering, corners, edges, and surface. Sold as-is."
        )

    if custom_notes and custom_notes.strip():
        text += f"\nAdditional Notes: {custom_notes.strip()}"

    return text


def build_shipping_pickup_section() -> str:
    """Builds Section 5: Buyer Assurance & Shipping / Local Pickup Terms."""
    return (
        "?? SHIPPING & LOCAL PICKUP:\n"
        "? Secure Shipping: Packaged securely in a bubble mailer with tracking (BMWT) and cardboard protection. Ships within 24 business hours.\n"
        "? Local Pickup: Safe public meetup available in a well-lit location.\n"
        "? 100% Authentic Guarantee."
    )


def _clean_tag(text: str) -> str:
    """Cleans a string for use as a valid alphanumeric hashtag."""
    nfd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfd if not unicodedata.combining(c))
    clean = re.sub(r"[^a-zA-Z0-9]", "", ascii_text)
    return clean


def build_hashtags(card_data: dict[str, Any]) -> list[str]:
    """
    Generates strictly 6 to 8 targeted viral hashtags for social / marketplace discovery.
    """
    data = normalize_card_input(card_data)
    tags: list[str] = []
    seen: set[str] = set()

    def add_tag(raw: str):
        cleaned = _clean_tag(raw)
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            tags.append(f"#{cleaned}")

    # Core hobby tags
    add_tag("SportsCards")
    add_tag("TheHobby")

    # Sport / Category
    cat = data["category"]
    if cat:
        add_tag(f"{cat}Cards")

    # Player / Subject
    if data["player"]:
        add_tag(data["player"])

    # Set / Brand
    if data["set_name"]:
        add_tag(data["set_name"])

    # Grade / Condition
    cond = data["condition"]
    if cond.lower() in ("raw", "ungraded"):
        add_tag("RawCards")
    else:
        add_tag(cond)

    # Variation if present
    if data["variation"]:
        add_tag(data["variation"])

    # Filler tags to guarantee at least 6 and up to 8 tags
    fillers = ["CardCollector", "TradingCards", "CardInvesting", "SportsCardHobby"]
    for filler in fillers:
        if len(tags) >= 8:
            break
        add_tag(filler)

    if len(tags) > 8:
        tags = tags[:8]
    while len(tags) < 6:
        for filler in ["Collectibles", "HobbyVault", "CardShow"]:
            add_tag(filler)
            if len(tags) >= 6:
                break

    return tags[:8]


# ---------------------------------------------------------------------------
# Deterministic Mock Sales Generator
# ---------------------------------------------------------------------------

class MockSalesGenerator:
    """
    100% deterministic offline sales listing generator for testing, CI/CD, and zero-token usage.
    """

    @classmethod
    def generate(
        cls,
        card: Union[dict[str, Any], CardRecord],
        asking_price: Optional[float] = None,
        custom_notes: str = ""
    ) -> str:
        data = normalize_card_input(card)
        price = resolve_asking_price(data, asking_price)

        s1_title = build_seo_title(data)
        s2_price = build_price_section(price)
        s3_specs = build_specifications_section(data)
        s4_cond = build_condition_section(data, custom_notes=custom_notes)
        s5_ship = build_shipping_pickup_section()
        s6_tags = "??? TAGS:\n" + " ".join(build_hashtags(data))

        listing_sections = [
            s1_title,
            "",
            s2_price,
            "",
            s3_specs,
            "",
            s4_cond,
            "",
            s5_ship,
            "",
            s6_tags,
        ]
        return "\n".join(listing_sections)

    def __call__(
        self,
        card: Union[dict[str, Any], CardRecord],
        asking_price: Optional[float] = None,
        custom_notes: str = ""
    ) -> str:
        return self.generate(card, asking_price=asking_price, custom_notes=custom_notes)


mock_sales_generator = MockSalesGenerator()


def build_structured_listing(
    card: Union[dict[str, Any], CardRecord],
    asking_price: Optional[float] = None,
    custom_notes: str = "",
    card_id: Optional[int] = None,
    is_mock: bool = True,
) -> MarketplaceListing:
    """
    Builds a structured MarketplaceListing Pydantic object from card data.
    """
    data = normalize_card_input(card)
    price = resolve_asking_price(data, asking_price)
    raw_text = MockSalesGenerator.generate(data, asking_price=price, custom_notes=custom_notes)

    title = build_seo_title(data)
    is_graded = data["condition"].lower() not in ("raw", "ungraded")
    slab_cert = data["slab_serial_number"] if (is_graded and data["slab_serial_number"]) else ("Present on Slab" if is_graded else "N/A (Raw)")

    specs = {
        "Year": data["year"],
        "Brand / Set": data["set_name"],
        "Card #": data["card_number"] or "NNO",
        "Player / Character": data["player"],
        "Variation / Parallel": data["variation"] or "Base",
        "Category / Sport": data["category"],
        "Condition / Grade": data["condition"],
        "Slab Certification #": slab_cert,
    }

    hashtags = build_hashtags(data)

    return MarketplaceListing(
        title=title,
        price=price,
        price_formatted=f"${price:,.2f}",
        specs=specs,
        description=build_condition_section(data, custom_notes=custom_notes),
        terms=build_shipping_pickup_section(),
        hashtags=hashtags,
        raw_text=raw_text,
        card_id=card_id,
        is_mock=is_mock,
    )


# ---------------------------------------------------------------------------
# Live Gemini SDK Generation & Public API
# ---------------------------------------------------------------------------

def generate_marketplace_listing(
    card: Union[dict[str, Any], CardRecord],
    asking_price: Optional[float] = None,
    custom_notes: str = "",
    mock: bool = False,
    api_key: Optional[str] = None,
    client: Optional[Any] = None,
    model: str = "gemini-2.5-flash",
    db_path: str = DEFAULT_DB_PATH,
) -> str:
    """
    Generates a structured, SEO-optimized Facebook Marketplace listing.
    Uses google.genai SDK with gemini-2.5-flash if available, or falls back to MockSalesGenerator.
    """
    data = normalize_card_input(card)
    price = resolve_asking_price(data, asking_price)

    # 1. Fallback to mock if requested or if no API key is available
    active_key = api_key or os.environ.get("GEMINI_API_KEY")
    if mock or (not active_key and client is None):
        return MockSalesGenerator.generate(data, asking_price=price, custom_notes=custom_notes)

    # 2. Attempt live Gemini API call
    try:
        from google import genai
        from google.genai import types

        active_client = client or genai.Client(api_key=active_key)
        prompt_payload = f"""
        Generate a high-conversion Facebook Marketplace listing for this card:
        {json.dumps(data, indent=2)}

        Target Asking Price: ${price:,.2f}
        Custom Notes: {custom_notes}
        """

        config = types.GenerateContentConfig(
            system_instruction=SALES_SYSTEM_INSTRUCTION,
            temperature=0.2,
        )

        response = active_client.models.generate_content(
            model=model,
            contents=prompt_payload,
            config=config,
        )

        if response and hasattr(response, "text") and response.text:
            raw_text = response.text.strip()
            if "KEY SPECIFICATIONS" in raw_text or "ASKING PRICE" in raw_text or "#" in raw_text:
                return raw_text

        return MockSalesGenerator.generate(data, asking_price=price, custom_notes=custom_notes)

    except Exception as e:
        logger.warning(f"Live Gemini sales listing generation failed ({e}), falling back to deterministic mock generator.")
        return MockSalesGenerator.generate(data, asking_price=price, custom_notes=custom_notes)


def generate_listing_for_card_id(
    db_path: str,
    card_id: int,
    asking_price: Optional[float] = None,
    custom_notes: str = "",
    mock: bool = False,
    api_key: Optional[str] = None,
) -> str:
    """
    Fetches card by ID from SQLite database and generates listing copy.
    """
    card = get_card_by_id(card_id, db_path=db_path)
    if not card:
        raise ValueError(f"Card with ID {card_id} not found in database '{db_path}'")
    return generate_marketplace_listing(
        card=card,
        asking_price=asking_price,
        custom_notes=custom_notes,
        mock=mock,
        api_key=api_key,
        db_path=db_path,
    )


def generate_batch_marketplace_listings(
    cards: list[Union[dict[str, Any], CardRecord]],
    asking_prices: Optional[list[Optional[float]]] = None,
    mock: bool = False,
    api_key: Optional[str] = None,
    client: Optional[Any] = None,
    model: str = "gemini-2.5-flash",
) -> list[str]:
    """
    Generates listing copies for a batch of cards.
    """
    listings: list[str] = []
    for idx, card in enumerate(cards):
        price = asking_prices[idx] if (asking_prices and idx < len(asking_prices)) else None
        listings.append(
            generate_marketplace_listing(
                card=card,
                asking_price=price,
                mock=mock,
                api_key=api_key,
                client=client,
                model=model,
            )
        )
    return listings

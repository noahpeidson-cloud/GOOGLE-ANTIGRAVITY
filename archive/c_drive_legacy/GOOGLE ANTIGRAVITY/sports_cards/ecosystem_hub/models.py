"""
models.py - Pydantic v2 schemas and validators for Sports Card Ecosystem Hub.
Strictly implements the 21-variable schema defined in sports_cards/GEMINI.md
and enforces Card Ladder ingestion requirements.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class CardCategory(str, Enum):
    """The 22 exact permitted categories for the sports card ecosystem."""
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


VALID_CATEGORIES = {c.value for c in CardCategory}

CATEGORY_MAP: dict[str, str] = {c.value.lower(): c.value for c in CardCategory}
CATEGORY_MAP["ufc"] = "UFC/MMA"
CATEGORY_MAP["mma"] = "UFC/MMA"
CATEGORY_MAP["ufc/mma"] = "UFC/MMA"
CATEGORY_MAP["pop culture"] = "PopCulture"
CATEGORY_MAP["popculture"] = "PopCulture"
CATEGORY_MAP["dragon ball z"] = "Dragonballz"
CATEGORY_MAP["dragonball z"] = "Dragonballz"
CATEGORY_MAP["dragonballz"] = "Dragonballz"
CATEGORY_MAP["flesh & blood"] = "Flesh and Blood"
CATEGORY_MAP["flesh and blood"] = "Flesh and Blood"


class AIStatus(str, Enum):
    """Permitted AI status review flags."""
    CLEARED = "CLEARED"
    REVIEW_VARIATION = "REVIEW VARIATION"
    NEEDS_REVIEW = "NEEDS REVIEW"


def get_current_date_str() -> str:
    """Returns today's date formatted as MM/DD/YYYY."""
    return datetime.now().strftime("%m/%d/%Y")


def synthesize_query(
    year: str | int,
    set_name: str,
    player: str,
    variation: str = "",
    condition: str = "Raw"
) -> str:
    """
    Synthesizes search query string: [Year] [Set] [Player] [Variation] [Condition].
    Omits empty components cleanly and ensures single spacing.
    """
    year_str = str(year).strip()
    set_str = str(set_name).strip()
    player_str = str(player).strip()
    var_str = str(variation).strip() if variation else ""
    cond_str = str(condition).strip() if condition else ""

    parts = [year_str, set_str, player_str]
    if var_str:
        parts.append(var_str)
    if cond_str:
        parts.append(cond_str)

    query = " ".join(p for p in parts if p)
    return re.sub(r"\s+", " ", query).strip()


calculate_query = synthesize_query


def format_notes(parent_image_id: int | str, child_card_id: int | str) -> str:
    """
    Formats relational tracking key: [Parent_Image_ID]-[Child_Card_ID]
    - Parent Image ID: 4-digit zero-padded string (e.g. '8492' or '0042')
    - Child Card ID: 3-digit zero-padded string (e.g. '105' or '001')
    """
    p_str = str(parent_image_id).strip()
    c_str = str(child_card_id).strip()

    # If it's already a full note like "8492-105"
    if "-" in p_str and not c_str:
        parts = p_str.split("-", 1)
        return format_notes(parts[0], parts[1])

    try:
        p_int = int(p_str)
        c_int = int(c_str)
    except ValueError as e:
        raise ValueError(f"Parent and Child IDs must be numeric or convertable to integers, got ({parent_image_id}, {child_card_id})") from e

    if p_int < 0 or c_int < 0:
        raise ValueError("Parent and Child IDs must be non-negative integers")

    return f"{p_int:04d}-{c_int:03d}"


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
    year: str = Field(..., min_length=4, description="4-digit year (YYYY)")
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

    @field_validator("player", "set_name", mode="before")
    @classmethod
    def clean_required_text(cls, v: Any) -> str:
        if v is None:
            raise ValueError("Field cannot be None")
        s = str(v).strip()
        s_clean = re.sub(r"\s+", " ", s)
        if not s_clean:
            raise ValueError("Field cannot be empty or whitespace only")
        return s_clean

    @field_validator("date_purchased", mode="before")
    @classmethod
    def normalize_date_purchased(cls, v: Any) -> str:
        if not v:
            return get_current_date_str()
        s = str(v).strip()
        # ISO format YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            dt = datetime.strptime(s, "%Y-%m-%d")
            return dt.strftime("%m/%d/%Y")
        # M/D/YYYY or MM/DD/YYYY
        match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
        if match:
            m, d, y = int(match.group(1)), int(match.group(2)), match.group(3)
            return f"{m:02d}/{d:02d}/{y}"
        raise ValueError(f"Invalid date format: '{v}'. Expected MM/DD/YYYY or YYYY-MM-DD")

    @field_validator("year", mode="before")
    @classmethod
    def validate_and_normalize_year(cls, v: Any) -> str:
        s = str(v).strip()
        # Multi-year season like '2020-21' or '2020/2021' -> '2020'
        match = re.match(r"^(\d{4})([-\/]\d{2,4})?$", s)
        if match:
            return match.group(1)
        raise ValueError(f"Year must be a 4-digit string (YYYY), got '{v}'")

    @field_validator("card_number", mode="before")
    @classmethod
    def preserve_card_number_string(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: Any) -> str:
        if not v:
            raise ValueError("Category is required")
        if isinstance(v, CardCategory):
            return v.value
        s = str(v).strip()
        if s in VALID_CATEGORIES:
            return s
        low = s.lower()
        if low in CATEGORY_MAP:
            return CATEGORY_MAP[low]
        raise ValueError(f"Invalid category: '{v}'. Must be one of {sorted(VALID_CATEGORIES)}")

    @field_validator("condition", mode="before")
    @classmethod
    def validate_condition_format(cls, v: Any) -> str:
        if not v:
            return "Raw"
        val = str(v).strip()
        if val.lower() in ("raw", "ungraded"):
            return "Raw"
        # Check for hyphens in graded condition (forbidden: PSA-10, BGS-9.5)
        if "-" in val:
            raise ValueError(f"Graded condition must not contain hyphens (use 'PSA 10' not '{val}')")
        return val

    @field_validator("slab_serial_number", "variation", "notes", "tags", "ladder_id", "date_sold", "image", "back_image", mode="before")
    @classmethod
    def clean_optional_strings(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @model_validator(mode="after")
    def validate_cross_field_rules(self) -> CardRecord:
        # Rule 1: Slab Serial # must be blank if Condition is Raw
        if self.condition == "Raw" and self.slab_serial_number.strip():
            raise ValueError(
                f"Slab serial number must be blank for 'Raw' condition cards (got '{self.slab_serial_number}')"
            )

        # Rule 2: Synthesize query if blank or keep sanitized
        expected_query = synthesize_query(
            self.year, self.set_name, self.player, self.variation, self.condition
        )
        if not self.query or not self.query.strip():
            object.__setattr__(self, "query", expected_query)
        else:
            object.__setattr__(self, "query", re.sub(r"\s+", " ", self.query.strip()))

        # Rule 3: Negative exclusions (-BGS -SGC) are forbidden on Raw cards
        if self.condition == "Raw":
            upper_query = self.query.upper()
            for excl in ("-BGS", "-SGC", "-PSA", "-CGC", "-CSG", "-BVG"):
                if excl in upper_query:
                    raise ValueError(f"Negative exclusions are forbidden in queries for Raw cards (found '{excl}')")

        # Rule 4: Auto-flag variation review
        # If variation is present and ai_status is default CLEARED, switch to REVIEW VARIATION
        if self.variation.strip() and self.ai_status == AIStatus.CLEARED:
            object.__setattr__(self, "ai_status", AIStatus.REVIEW_VARIATION)

        return self


# Aliases for cross-module compatibility
CardModel = CardRecord
CardBase = CardRecord
CardCreate = CardRecord


class CardBatchCreate(BaseModel):
    """Batch model enforcing the 500-card circuit breaker."""
    cards: list[CardRecord] = Field(..., min_length=1, max_length=500)


class CardExtractionSchema(BaseModel):
    """Schema returned by AI Vision Ingest & Scraper Ingest pipelines."""
    model_config = ConfigDict(use_enum_values=True)

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
    model_config = ConfigDict(use_enum_values=True)

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
    model_config = ConfigDict(use_enum_values=True)

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


class SummaryStatsResponse(BaseModel):
    """Schema for aggregated metrics."""
    total_cards: int
    total_investment: float
    total_estimated_value: float
    count_by_category: dict[str, int]
    count_by_ai_status: dict[str, int]


class MarketplaceListing(BaseModel):
    """Structured response model for Facebook Marketplace listing copy."""
    model_config = ConfigDict(use_enum_values=True)

    title: str = Field(..., max_length=100, description="SEO title under 100 characters")
    price: float = Field(..., ge=0.0, description="Target asking price")
    price_formatted: str = Field(..., description="Formatted price string e.g. '$350.00'")
    specs: dict[str, str] = Field(default_factory=dict, description="Key-value item specifications")
    description: str = Field(..., description="Condition notes and card highlights")
    terms: str = Field(..., description="Pickup location, payment methods, and return policy")
    hashtags: list[str] = Field(..., min_length=6, max_length=8, description="6 to 8 SEO hashtags")
    raw_text: str = Field(..., description="Complete copy-paste ready text block for FB Marketplace")
    card_id: Optional[int] = Field(default=None, description="Associated database card ID")
    is_mock: bool = Field(default=False, description="True if generated via deterministic offline fallback")


class SalesListingRequest(BaseModel):
    """Request payload for on-demand sales copy generation."""
    model_config = ConfigDict(use_enum_values=True, extra="allow")

    card_id: Optional[int] = Field(default=None, description="Optional card ID in portfolio.db")
    asking_price: Optional[float] = Field(default=None, ge=0.0, description="Optional custom asking price")
    custom_notes: Optional[str] = Field(default="", description="Optional custom notes to include")
    mock: bool = Field(default=False, description="Whether to use offline deterministic generator")
    card_data: Optional[Union[CardCaptureRequest, dict, CardRecord]] = Field(default=None, description="Optional inline card data payload")


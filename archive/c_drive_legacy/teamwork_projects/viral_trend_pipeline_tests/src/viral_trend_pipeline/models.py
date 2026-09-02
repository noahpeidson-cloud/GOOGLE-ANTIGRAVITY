"""Data models, exceptions, and normalization helpers for the Viral Trend Pipeline."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Optional, Dict, Any, List, Union


class ExtractionError(Exception):
    """Base exception for extraction failures."""
    pass


class ExtractionParseError(ExtractionError):
    """Raised when an extraction source payload has invalid syntax or cannot be parsed."""
    pass


class NetworkBlockError(RuntimeError):
    """Raised when any code attempts real network I/O during test execution."""
    pass


@dataclass
class TrendRecord:
    """Canonical trend record representing a trending topic, hashtag, audio, or video across platforms."""
    platform: str  # 'tiktok' | 'instagram' | 'youtube' | 'facebook'
    category: str  # 'sports_cards' | 'edm' | 'general'
    trend_type: str  # 'hashtag' | 'audio' | 'video_title'
    raw_title: str
    normalized_tag: str  # Case-preserved (e.g. 'SportsCards', 'CardLadder')
    date_added: str  # 'YYYY-MM-DD'
    rank: Optional[int] = None
    post_count: Optional[int] = None
    velocity_metric: Optional[float] = None
    editing_style: Optional[str] = None
    engagement_metrics: Dict[str, Any] = field(default_factory=dict)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return {
            "platform": self.platform,
            "category": self.category,
            "trend_type": self.trend_type,
            "raw_title": self.raw_title,
            "normalized_tag": self.normalized_tag,
            "date_added": self.date_added,
            "rank": self.rank,
            "post_count": self.post_count,
            "velocity_metric": self.velocity_metric,
            "editing_style": self.editing_style,
            "engagement_metrics": self.engagement_metrics,
            "raw_metadata": self.raw_metadata,
        }


# Regex to strip emojis and unwanted special symbols, while preserving alphanumeric, hyphens, underscores
EMOJI_AND_SPECIAL_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff"  # Supplemental symbols, emojis
    r"\u2600-\u27bf"            # Misc symbols & dingbats
    r"\u2300-\u23ff"            # Misc technical
    r"\u2b50\u2b55\u2934\u2935\u25aa\u25ab\u25b6\u25c0\u25fb-\u25fe"
    r"\u200d\u200b\ufe0e\ufe0f\ufeff\u200e\u200f\u202a-\u202e]"  # Control & format chars
)


def normalize_hashtag(raw_tag: Optional[str]) -> str:
    """Normalize a raw hashtag:
    - Strips leading '#' and whitespace.
    - Strips emojis and zero-width characters.
    - Preserves exact character casing (e.g. 'SportsCards', 'HardTechno').
    - Preserves inner hyphens and underscores (e.g. 'Sports-Cards_2026').
    - Strips trailing punctuation (e.g. '!', '?', '.').
    """
    if not raw_tag:
        return ""

    # Remove zero-width spaces and outer whitespace
    cleaned = raw_tag.strip(" \t\n\r\u200b\ufeff\u200e\u200f\u202a\u202c")
    # Remove leading hashes
    cleaned = re.sub(r"^#+", "", cleaned)
    # Remove emojis and special symbols
    cleaned = EMOJI_AND_SPECIAL_PATTERN.sub("", cleaned)
    # Trim whitespace again
    cleaned = cleaned.strip()

    # Extract valid tag characters (letters, numbers, hyphens, underscores)
    match = re.match(r"^([A-Za-z0-9_\-]+)", cleaned)
    if match:
        return match.group(1).rstrip("!?,.:;-")
    
    # Fallback: if nothing matched, try stripping trailing non-alphanumerics
    return re.sub(r"[^\w\-]", "", cleaned)


def parse_metric_number(val: Any) -> Optional[int]:
    """Convert human-readable count string (e.g. '1.2M', '850K', '2.5B', '1,280') or int/float to integer.
    Returns None for non-numeric placeholder strings (e.g. 'NEW', 'Trending', '--', 'N/A').
    """
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return int(val)

    s = str(val).strip()
    if not s or s.upper() in {"NEW", "TRENDING", "--", "N/A", "NULL", "NONE", "-"}:
        return None

    # Remove trailing descriptors like ' views', ' likes', ' comments', ' posts'
    s = re.sub(r"\s*(?:views|likes|comments|posts)$", "", s, flags=re.IGNORECASE).strip()

    # Suffix check
    s_upper = s.upper()
    try:
        if s_upper.endswith("B"):
            num_part = s_upper[:-1].replace(",", "").strip()
            return int(float(num_part) * 1_000_000_000)
        elif s_upper.endswith("M"):
            num_part = s_upper[:-1].replace(",", "").strip()
            return int(float(num_part) * 1_000_000)
        elif s_upper.endswith("K"):
            num_part = s_upper[:-1].replace(",", "").strip()
            return int(float(num_part) * 1_000)
        else:
            clean_str = s.replace(",", "").strip()
            return int(float(clean_str))
    except (ValueError, TypeError):
        return None


def parse_velocity_metric(val: Any) -> Optional[float]:
    """Convert velocity percentage string (e.g. '+145%', '-12.5%', '82%') or numeric to float.
    Returns None for non-numeric strings (e.g. 'NEW', '--').
    """
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s or s.upper() in {"NEW", "TRENDING", "--", "N/A", "NULL", "NONE", "-"}:
        return None

    # Strip % and leading +
    s_clean = s.replace("%", "").strip()
    if s_clean.startswith("+"):
        s_clean = s_clean[1:].strip()

    try:
        return float(s_clean)
    except (ValueError, TypeError):
        return None


def classify_category(text: Optional[str]) -> str:
    """Classify text into domain tracks: 'sports_cards', 'edm', or 'general' based on domain keywords."""
    if not text:
        return "general"

    t = text.lower()
    sports_card_keywords = [
        "sportscard", "sportscards", "thehobby", "cardladder", "paniniprizm",
        "toppschrome", "topps", "panini", "prizm", "whodoyoucollect",
        "sportscardinvesting", "wembanyama", "rookie", "grading", "psa",
        "bgs", "cgc", "junk-wax", "cards", "hobby"
    ]
    edm_keywords = [
        "hardtechno", "techno", "ravetok", "rave", "edmdrop", "edm",
        "ultra", "mainstage", "montagem", "lxngvx", "bassline", "dj",
        "festival", "electronic", "dimension"
    ]

    for kw in sports_card_keywords:
        if kw in t:
            return "sports_cards"
    for kw in edm_keywords:
        if kw in t:
            return "edm"

    return "general"


def get_default_date(anchor_date: Optional[str] = None) -> str:
    """Return provided anchor_date or current date in YYYY-MM-DD format."""
    if anchor_date:
        return anchor_date
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

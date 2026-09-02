"""Android CLI layout hierarchy fixtures and loaders."""

import json
from pathlib import Path
from typing import List, Dict, Any

FIXTURES_DIR = Path(__file__).parent
INSTAGRAM_REELS_LAYOUT_PATH = FIXTURES_DIR / "instagram_reels_layout_dump.json"


def get_instagram_reels_layout_json() -> str:
    """Load raw Instagram Reels layout dump JSON string."""
    if not INSTAGRAM_REELS_LAYOUT_PATH.exists():
        raise FileNotFoundError(f"Fixture file missing: {INSTAGRAM_REELS_LAYOUT_PATH}")
    return INSTAGRAM_REELS_LAYOUT_PATH.read_text(encoding="utf-8")


def get_instagram_reels_layout_data() -> List[Dict[str, Any]]:
    """Load parsed Instagram Reels layout data."""
    raw_json = get_instagram_reels_layout_json()
    return json.loads(raw_json)


INSTAGRAM_REELS_LAYOUT_RAW = get_instagram_reels_layout_json()

# Edge case fixtures
INVALID_SYNTAX_JSON = "[{key: -1, text: missing_quotes}]"

NULL_TEXT_LAYOUT_DATA: List[Dict[str, Any]] = [
  {
    "class": "android.widget.TextView",
    "resourceId": "com.instagram.android:id/caption_text_view",
    "text": None,
    "contentDesc": "Fallback caption #TheHobby #CardInvesting",
    "off-screen": False,
  },
  {
    "class": "android.widget.TextView",
    "resourceId": "com.instagram.android:id/like_count",
    "text": None,
    "off-screen": False,
  },
]

OFFSCREEN_LAYOUT_DATA: List[Dict[str, Any]] = [
  {
    "class": "android.widget.TextView",
    "resourceId": "com.instagram.android:id/caption_text_view",
    "text": "Visible caption #SportsCards",
    "off-screen": False,
  },
  {
    "class": "android.widget.TextView",
    "resourceId": "com.instagram.android:id/caption_text_view",
    "text": "Offscreen caption #HiddenTrend",
    "off-screen": True,
  },
]

# 20+ hashtags in a single caption
MULTI_TAG_CAPTION_LAYOUT_DATA: List[Dict[str, Any]] = [
  {
    "class": "android.widget.TextView",
    "resourceId": "com.instagram.android:id/caption_text_view",
    "text": (
        "Huge sports cards mega-haul! "
        "#TheHobby #CardLadder #SportsCards #PaniniPrizm #ToppsChrome "
        "#WhoDoYouCollect #SportsCardInvesting #Wembanyama #RookieCard #PSA10 "
        "#BGS #CGC #BowmanChrome #NationalTreasures #Flawless #Optic "
        "#Select #Impeccable #PrizmDP #JunkWax #VintageCards"
    ),
    "off-screen": False,
  }
]

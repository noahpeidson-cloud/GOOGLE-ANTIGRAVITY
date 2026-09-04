"""Android CLI UI Hierarchy Layout Extractor for Instagram Reels."""

import json
import logging
import re
from typing import Optional, List, Dict, Any, Union

from viral_trend_pipeline.models import (
    TrendRecord,
    ExtractionParseError,
    normalize_hashtag,
    parse_metric_number,
    classify_category,
    get_default_date,
)

logger = logging.getLogger(__name__)

DEFAULT_CAPTION_IDS = [
    "com.instagram.android:id/caption_text_view",
    "com.instagram.android:id/row_feed_textview_caption",
    "com.instagram.android:id/reel_viewer_caption",
]

DEFAULT_AUDIO_IDS = [
    "com.instagram.android:id/audio_track_title",
    "com.instagram.android:id/clips_audio_mix_editor_title",
    "com.instagram.android:id/music_title_text",
    "com.instagram.android:id/music_artist_and_song_title",
]

DEFAULT_LIKE_IDS = [
    "com.instagram.android:id/like_count",
    "com.instagram.android:id/row_feed_textview_likes",
    "com.instagram.android:id/like_button",
]

DEFAULT_COMMENT_IDS = [
    "com.instagram.android:id/row_feed_textview_comments_count",
    "com.instagram.android:id/comments_count",
    "com.instagram.android:id/comment_button",
]


class AndroidCLIExtractor:
    """Extractor for parsing Android CLI layout dumps (e.g. from `android layout`)."""

    def __init__(
        self,
        default_anchor_date: Optional[str] = None,
        caption_resource_ids: Optional[List[str]] = None,
        audio_resource_ids: Optional[List[str]] = None,
        like_resource_ids: Optional[List[str]] = None,
        comment_resource_ids: Optional[List[str]] = None,
    ):
        self.default_anchor_date = default_anchor_date
        self.caption_resource_ids = set(caption_resource_ids or DEFAULT_CAPTION_IDS)
        self.audio_resource_ids = set(audio_resource_ids or DEFAULT_AUDIO_IDS)
        self.like_resource_ids = set(like_resource_ids or DEFAULT_LIKE_IDS)
        self.comment_resource_ids = set(comment_resource_ids or DEFAULT_COMMENT_IDS)

    def load_layout_data(
        self, layout_input: Union[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Load and parse layout data from JSON string or list of dicts.
        Raises ExtractionParseError if JSON syntax is invalid.
        """
        if isinstance(layout_input, list):
            return layout_input

        if not isinstance(layout_input, str):
            raise ExtractionParseError(f"Unsupported layout input type: {type(layout_input)}")

        raw_str = layout_input.strip()
        if not raw_str:
            return []

        try:
            parsed = json.loads(raw_str)
            if not isinstance(parsed, list):
                if isinstance(parsed, dict) and "elements" in parsed:
                    return parsed["elements"]
                return [parsed]
            return parsed
        except json.JSONDecodeError as exc:
            raise ExtractionParseError(f"Failed to parse Android layout JSON: {exc}") from exc

    def extract_hashtags_from_text(self, text: str) -> List[str]:
        """Extract raw hashtags from caption text block."""
        if not text:
            return []
        # Match words prefixed with #
        raw_tags = re.findall(r"#([\w\-🔥💎🎧]+)", text)
        return [f"#{t}" for t in raw_tags]

    def parse_instagram_reels(
        self,
        layout_input: Union[str, List[Dict[str, Any]]],
        anchor_date: Optional[str] = None,
        include_offscreen: bool = False,
    ) -> List[TrendRecord]:
        """Extract trending hashtags, audio tracks, and metrics from Instagram Reels layout dump."""
        elements = self.load_layout_data(layout_input)
        if not elements:
            return []

        date_str = get_default_date(anchor_date or self.default_anchor_date)
        records: List[TrendRecord] = []

        # First pass: collect common engagement metrics if present in the dump
        overall_like_count: Optional[int] = None
        overall_comment_count: Optional[int] = None

        for elem in elements:
            if not isinstance(elem, dict):
                continue
            if not include_offscreen and elem.get("off-screen") is True:
                continue

            res_id = elem.get("resourceId") or ""
            text_val = elem.get("text") or ""

            if res_id in self.like_resource_ids and text_val:
                parsed_likes = parse_metric_number(text_val)
                if parsed_likes is not None and overall_like_count is None:
                    overall_like_count = parsed_likes

            if res_id in self.comment_resource_ids and text_val:
                parsed_comments = parse_metric_number(text_val)
                if parsed_comments is not None and overall_comment_count is None:
                    overall_comment_count = parsed_comments

        # Second pass: process captions and audio tracks
        for elem in elements:
            if not isinstance(elem, dict):
                continue
            if not include_offscreen and elem.get("off-screen") is True:
                continue

            res_id = elem.get("resourceId") or ""
            text_val = elem.get("text")
            content_desc = elem.get("contentDesc") or ""

            # Fallback to contentDesc if text is missing
            effective_text = (text_val if text_val is not None else content_desc).strip()
            if not effective_text:
                continue

            # 1. Caption element
            if res_id in self.caption_resource_ids or "caption" in res_id.lower():
                raw_hashtags = self.extract_hashtags_from_text(effective_text)
                for idx, raw_ht in enumerate(raw_hashtags, 1):
                    normalized = normalize_hashtag(raw_ht)
                    if normalized:
                        category = classify_category(f"{raw_ht} {effective_text}")
                        rec = TrendRecord(
                            platform="instagram",
                            category=category,
                            trend_type="hashtag",
                            raw_title=effective_text,
                            normalized_tag=normalized,
                            date_added=date_str,
                            rank=idx,
                            post_count=overall_like_count,
                            engagement_metrics={
                                "likes": overall_like_count,
                                "comments": overall_comment_count,
                                "raw_caption": effective_text,
                            },
                            raw_metadata={
                                "resourceId": res_id,
                                "contentDesc": content_desc,
                                "bounds": elem.get("bounds"),
                            },
                        )
                        records.append(rec)

            # 2. Audio track element
            elif res_id in self.audio_resource_ids or "audio" in res_id.lower():
                clean_audio = effective_text
                # Remove "Audio: " prefix if present from contentDesc
                if clean_audio.startswith("Audio:"):
                    clean_audio = clean_audio.replace("Audio:", "").strip()

                normalized = normalize_hashtag(clean_audio)
                category = classify_category(clean_audio)

                rec = TrendRecord(
                    platform="instagram",
                    category=category,
                    trend_type="audio",
                    raw_title=clean_audio,
                    normalized_tag=normalized or clean_audio,
                    date_added=date_str,
                    post_count=overall_like_count,
                    engagement_metrics={
                        "likes": overall_like_count,
                        "comments": overall_comment_count,
                    },
                    raw_metadata={
                        "resourceId": res_id,
                        "contentDesc": content_desc,
                        "bounds": elem.get("bounds"),
                    },
                )
                records.append(rec)

        return records

    def parse_layout(
        self,
        layout_input: Union[str, List[Dict[str, Any]]],
        platform: str = "instagram",
        anchor_date: Optional[str] = None,
        include_offscreen: bool = False,
    ) -> List[TrendRecord]:
        """Generic layout parser entry point."""
        return self.parse_instagram_reels(
            layout_input, anchor_date=anchor_date, include_offscreen=include_offscreen
        )

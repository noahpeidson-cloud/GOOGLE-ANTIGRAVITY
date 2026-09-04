"""Headless Mobile Viral Trend Scraper.
Extracts structured trend items, captions, hashtags, sounds, and engagement metrics
from mobile feed UI layout trees with automatic DLQ quarantine routing.
"""

import re
import time
import logging
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from unified_ops_hub.gateway.dlq_manager import DLQManager, ErrorCategory
from unified_ops_hub.mobile.models import (
    ScrapedTrendItem,
    MobileScrapeSession,
    ScrapeMetrics,
)
from unified_ops_hub.mobile.android_client import (
    AndroidClient,
    AndroidAutomationError,
    DeviceOfflineError,
    DeviceNotFoundError,
)

logger = logging.getLogger("unified_ops_hub.mobile.scraper")


class MobileViralTrendScraper:
    """Autonomous scraper for mobile video feeds (TikTok, Instagram Reels, YouTube Shorts)."""

    def __init__(
        self,
        client: AndroidClient,
        dlq_manager: Optional[DLQManager] = None,
    ) -> None:
        self.client = client
        self.dlq_manager = dlq_manager

    @staticmethod
    def parse_metric_number(text: Optional[str]) -> int:
        """Normalizes abbreviated metric strings ('1.4M', '35.2K', '12,500') to integers."""
        if not text:
            return 0

        clean = text.strip().replace(",", "").replace("+", "")
        m = re.search(r'([\d\.]+)\s*([KkMmBb])?', clean)
        if not m:
            return 0

        val_str, unit = m.groups()
        try:
            val = float(val_str)
            if unit:
                u = unit.upper()
                if u == "K":
                    val *= 1_000
                elif u == "M":
                    val *= 1_000_000
                elif u == "B":
                    val *= 1_000_000_000
            return int(val)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def extract_hashtags(text: Optional[str]) -> List[str]:
        """Extracts hashtag tokens from caption or text strings."""
        if not text:
            return []
        return re.findall(r'#([A-Za-z0-9_]+)', text)

    def parse_layout_nodes(
        self,
        nodes: List[Dict[str, Any]],
        platform: str = "generic",
    ) -> List[ScrapedTrendItem]:
        """Parses a layout node tree into structured ScrapedTrendItem objects."""
        if not nodes:
            return []

        try:
            caption = ""
            hashtags: List[str] = []
            sound_title: Optional[str] = None
            author_handle: Optional[str] = None
            like_count = 0
            comment_count = 0
            share_count = 0
            view_count = 0
            raw_bounds: Optional[str] = None

            for node in nodes:
                if not isinstance(node, dict):
                    raise ValueError(f"Invalid node type in layout tree: {type(node)}")

                text = node.get("text", "") or ""
                raw_res_id = (node.get("resourceId", "") or "").lower()
                entry_name = raw_res_id.split(":id/", 1)[-1] if ":id/" in raw_res_id else raw_res_id
                desc = (node.get("contentDesc", "") or "").lower()
                bounds = node.get("bounds", "")

                # 1. Caption & Hashtags detection
                if "#" in text or any(k in entry_name for k in ["caption", "desc"]) or (entry_name == "title" and not sound_title):
                    if len(text) > len(caption) and not any(k in entry_name for k in ["music", "sound", "like", "comment", "share"]):
                        caption = text
                        hashtags = self.extract_hashtags(text)
                        if bounds:
                            raw_bounds = bounds

                # 2. Sound / Music track detection
                if any(k in entry_name for k in ["music", "sound", "audio", "track", "song"]):
                    if text and not text.startswith("#") and not text.startswith("@") and not any(text.endswith(u) for u in ["K", "M", "B"]):
                        sound_title = text
                elif "original sound" in desc or "sound track" in desc:
                    if text and not sound_title and not text.startswith("#") and not text.startswith("@") and not any(text.endswith(u) for u in ["K", "M", "B"]):
                        sound_title = text

                # 3. Creator handle detection
                if text.startswith("@") or "author" in entry_name or "username" in entry_name:
                    if text.startswith("@"):
                        author_handle = text
                    elif not author_handle and text:
                        author_handle = f"@{text.lstrip('@')}"

                # 4. Metrics detection (Likes, Comments, Shares, Views)
                if "like" in entry_name or "like" in desc:
                    like_count = max(like_count, self.parse_metric_number(text))
                elif "comment" in entry_name or "comment" in desc:
                    comment_count = max(comment_count, self.parse_metric_number(text))
                elif "share" in entry_name or "share" in desc:
                    share_count = max(share_count, self.parse_metric_number(text))
                elif "view" in entry_name or "view" in desc:
                    view_count = max(view_count, self.parse_metric_number(text))

            # If we found at least a caption, sound, or engagement metric
            if caption or sound_title or like_count > 0 or hashtags:
                topic = hashtags[0] if hashtags else "Viral Trend"
                item = ScrapedTrendItem(
                    platform=platform,
                    topic=topic,
                    caption=caption,
                    hashtags=hashtags,
                    sound_title=sound_title,
                    author_handle=author_handle,
                    view_count=view_count,
                    like_count=like_count,
                    comment_count=comment_count,
                    share_count=share_count,
                    raw_bounds=raw_bounds,
                )
                return [item]

            return []

        except Exception as exc:
            logger.error("Failed to parse layout nodes: %s", exc)
            if self.dlq_manager:
                try:
                    # Sanitize nodes for JSON serialization in DLQ payload
                    safe_nodes = [
                        {k: str(v) for k, v in n.items()} if isinstance(n, dict) else str(n)
                        for n in nodes
                    ]
                    self.dlq_manager.record_failure(
                        source_service="mobile_scraper",
                        error_category=ErrorCategory.CORRUPTED_PAYLOAD,
                        error_message=f"Layout node parsing error: {str(exc)}",
                        payload={"platform": platform, "nodes_sample": safe_nodes[:10]},
                        traceback_str=str(exc),
                    )
                except Exception as dlq_exc:
                    logger.error("Failed to record parsing error to DLQ: %s", dlq_exc)
            return []

    def parse_xml_hierarchy(
        self,
        xml_content: str,
        platform: str = "generic",
    ) -> List[ScrapedTrendItem]:
        """Parses a raw UIAutomator XML string with fallback DLQ error handling."""
        if not xml_content or not xml_content.strip():
            return []

        try:
            root = ET.fromstring(xml_content)
            nodes: List[Dict[str, Any]] = []

            for idx, elem in enumerate(root.iter("node")):
                nodes.append({
                    "key": 1048576 + idx,
                    "class": elem.attrib.get("class", ""),
                    "resourceId": elem.attrib.get("resource-id", ""),
                    "text": elem.attrib.get("text", ""),
                    "contentDesc": elem.attrib.get("content-desc", ""),
                    "bounds": elem.attrib.get("bounds", ""),
                })

            return self.parse_layout_nodes(nodes, platform=platform)

        except Exception as exc:
            logger.error("Corrupted or unparseable XML hierarchy: %s", exc)
            if self.dlq_manager:
                self.dlq_manager.record_failure(
                    source_service="mobile_scraper",
                    error_category=ErrorCategory.CORRUPTED_PAYLOAD,
                    error_message=f"XML Parsing Exception [{exc.__class__.__name__}]: {str(exc)}",
                    payload={"platform": platform, "raw_xml_snippet": xml_content[:500]},
                    traceback_str=str(exc),
                )
            return []

    def scrape_feed(
        self,
        platform: str = "tiktok",
        target_url_or_tag: Optional[str] = None,
        max_swipes: int = 5,
        delay_between_swipes_sec: float = 1.0,
    ) -> Tuple[MobileScrapeSession, List[ScrapedTrendItem], ScrapeMetrics]:
        """Executes full autonomous zero-touch mobile scraping loop."""
        session = MobileScrapeSession(
            platform=platform,
            target_query_or_url=target_url_or_tag or "",
            status="RUNNING",
        )

        scraped_items: List[ScrapedTrendItem] = []
        seen_captions = set()
        total_frames = 0
        successful_parses = 0
        failed_parses = 0
        frame_latencies: List[float] = []
        start_time = time.time()

        try:
            # 1. Pre-flight check & Samsung Auto Blocker bypass
            self.client.disable_samsung_auto_blocker()

            # 2. Launch target feed / deep link if specified
            if target_url_or_tag:
                self.client.open_deep_link(target_url_or_tag)

            # 3. Autonomous pagination and extraction loop
            for swipe_idx in range(max_swipes):
                frame_start = time.time()
                total_frames += 1

                try:
                    layout_nodes = self.client.get_layout_tree()
                    items = self.parse_layout_nodes(layout_nodes, platform=platform)

                    if items:
                        for item in items:
                            dedup_key = item.caption or item.sound_title or item.item_id
                            if dedup_key not in seen_captions:
                                seen_captions.add(dedup_key)
                                scraped_items.append(item)
                        successful_parses += 1
                    else:
                        failed_parses += 1

                except Exception as frame_exc:
                    failed_parses += 1
                    logger.warning("Frame extraction error on swipe %d: %s", swipe_idx, frame_exc)

                frame_latency = (time.time() - frame_start) * 1000.0
                frame_latencies.append(frame_latency)

                # Paginate feed forward
                if swipe_idx < max_swipes - 1:
                    self.client.swipe_direction("up", distance_ratio=0.6, duration_ms=450)
                    if delay_between_swipes_sec > 0:
                        time.sleep(delay_between_swipes_sec)

            session.status = "COMPLETED"
            session.items_scraped = len(scraped_items)
            session.end_time = datetime.now(timezone.utc).isoformat()

        except (DeviceOfflineError, DeviceNotFoundError) as dev_exc:
            logger.error("Device error during scrape session: %s", dev_exc)
            session.status = "FAILED"
            session.errors.append(str(dev_exc))
            if self.dlq_manager:
                self.dlq_manager.record_failure(
                    source_service="mobile_scraper",
                    error_category=ErrorCategory.TIMEOUT,
                    error_message=f"Device failure during scrape: {str(dev_exc)}",
                    payload={"session_id": session.session_id, "platform": platform},
                )
        except Exception as exc:
            logger.error("Unhandled scraping exception: %s", exc)
            session.status = "FAILED"
            session.errors.append(str(exc))

        # Compute telemetry and yield metrics
        duration = round(time.time() - start_time, 2)
        avg_latency = (
            round(sum(frame_latencies) / len(frame_latencies), 2)
            if frame_latencies
            else 0.0
        )

        all_hashtags = [tag for item in scraped_items for tag in item.hashtags]
        all_sounds = [item.sound_title for item in scraped_items if item.sound_title]
        top_hashtags = Counter(all_hashtags).most_common(5)
        top_sounds = Counter(all_sounds).most_common(5)

        metrics = ScrapeMetrics(
            session_id=session.session_id,
            duration_seconds=duration,
            total_frames_dumped=total_frames,
            successful_parses=successful_parses,
            failed_parses=failed_parses,
            average_frame_latency_ms=avg_latency,
            top_hashtags=top_hashtags,
            top_sounds=top_sounds,
        )

        return session, scraped_items, metrics

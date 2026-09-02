"""Chrome DevTools Accessibility Tree Snapshot Extractor for TikTok and YouTube."""

from dataclasses import dataclass, field
import logging
import re
from typing import Optional, List, Dict, Any

from viral_trend_pipeline.models import (
    TrendRecord,
    normalize_hashtag,
    parse_metric_number,
    parse_velocity_metric,
    classify_category,
    get_default_date,
)

logger = logging.getLogger(__name__)

# Regular expression to parse A11y snapshot lines
# Example: uid=1_4 row "Rank 1 #SportsCards" level=2
NODE_LINE_RE = re.compile(
    r"^(?P<indent>\s*)uid=(?P<uid>[\w\.\-]+)\s+(?P<role>\w+)(?:\s+\"(?P<name>(?:[^\"\\]|\\.)*)\")?(?P<attrs>.*)$"
)


@dataclass
class AXNode:
    """Accessibility Tree node representation."""
    uid: str
    role: str
    name: str = ""
    attrs: Dict[str, str] = field(default_factory=dict)
    indent: int = 0
    children: List["AXNode"] = field(default_factory=list)

    def find_all_by_role(self, role: str) -> List["AXNode"]:
        """Find all descendant nodes matching a role."""
        results: List["AXNode"] = []
        if self.role == role:
            results.append(self)
        for child in self.children:
            results.extend(child.find_all_by_role(role))
        return results

    def get_text_content(self) -> str:
        """Get concatenated text content of this node and its children."""
        parts = [self.name] if self.name else []
        for child in self.children:
            text = child.get_text_content()
            if text:
                parts.append(text)
        return " ".join(parts).strip()


class ChromeDevToolsExtractor:
    """Extractor for parsing Chrome DevTools Accessibility Tree snapshots."""

    def __init__(self, default_anchor_date: Optional[str] = None):
        self.default_anchor_date = default_anchor_date

    def parse_a11y_tree(self, snapshot_text: str) -> List[AXNode]:
        """Parse raw A11y snapshot text into a hierarchical list of root AXNodes."""
        if not snapshot_text or not snapshot_text.strip():
            return []

        lines = snapshot_text.splitlines()
        root_nodes: List[AXNode] = []
        stack: List[AXNode] = []

        for line_num, line in enumerate(lines, 1):
            if not line.strip():
                continue

            match = NODE_LINE_RE.match(line)
            if not match:
                # Malformed line: skip gracefully per Edge Case E3
                logger.debug("Skipping malformed a11y line %d: %s", line_num, line)
                continue

            indent = len(match.group("indent"))
            uid = match.group("uid")
            role = match.group("role")
            name = match.group("name") or ""
            # Unescape quotes if needed
            name = name.replace(r'\"', '"').replace(r"\\", "\\")

            raw_attrs = match.group("attrs").strip()
            attrs: Dict[str, str] = {}
            if raw_attrs:
                for attr_part in raw_attrs.split():
                    if "=" in attr_part:
                        k, v = attr_part.split("=", 1)
                        attrs[k] = v.strip('"')
                    else:
                        attrs[attr_part] = "true"

            node = AXNode(uid=uid, role=role, name=name, attrs=attrs, indent=indent)

            # Maintain parent-child hierarchy based on indentation
            while stack and stack[-1].indent >= indent:
                stack.pop()

            if stack:
                stack[-1].children.append(node)
            else:
                root_nodes.append(node)

            stack.append(node)

        return root_nodes

    def parse_tiktok_hashtags(
        self, snapshot_text: str, anchor_date: Optional[str] = None
    ) -> List[TrendRecord]:
        """Extract trending hashtags from TikTok Creative Center a11y tree snapshot."""
        date_str = get_default_date(anchor_date or self.default_anchor_date)
        trees = self.parse_a11y_tree(snapshot_text)
        records: List[TrendRecord] = []

        # Find all row nodes (e.g. inside table)
        for root in trees:
            rows = root.find_all_by_role("row")
            for row_idx, row in enumerate(rows, 1):
                # Check row name or children cells
                row_name = row.name
                cells = row.find_all_by_role("cell")

                tag_candidate = ""
                rank_val: Optional[int] = None
                post_count_val: Optional[int] = None
                velocity_val: Optional[float] = None

                # Extract from row name if present (e.g. "Rank 1 #SportsCards")
                if "#" in row_name:
                    hash_match = re.search(r"(#[\w\-🔥💎🎧]+)", row_name)
                    if hash_match:
                        tag_candidate = hash_match.group(1)
                
                rank_match = re.search(r"Rank\s+(\d+)", row_name, re.IGNORECASE)
                if rank_match:
                    rank_val = int(rank_match.group(1))

                # Extract from cells
                for cell_idx, cell in enumerate(cells):
                    cell_text = cell.name.strip()
                    if not cell_text:
                        # Check child link or text
                        for c in cell.children:
                            if c.name.strip():
                                cell_text = c.name.strip()
                                break

                    if not cell_text:
                        continue

                    # Hashtag cell
                    if "#" in cell_text and not tag_candidate:
                        tag_candidate = cell_text
                    # Velocity percentage (e.g. "+145%", "82%")
                    elif "%" in cell_text and velocity_val is None:
                        velocity_val = parse_velocity_metric(cell_text)
                    # Numeric rank cell (e.g. "1") - usually first cell or matches rank_val
                    elif (cell_idx == 0 or rank_val is None) and cell_text.isdigit() and int(cell_text) <= 500:
                        if rank_val is None or cell_idx == 0:
                            rank_val = int(cell_text)
                    # Post count / view count (e.g. "1.2M", "850K")
                    elif post_count_val is None:
                        parsed_count = parse_metric_number(cell_text)
                        if parsed_count is not None:
                            post_count_val = parsed_count

                # If no tag in row name or cells, check links inside row
                if not tag_candidate:
                    links = row.find_all_by_role("link")
                    for link in links:
                        if "#" in link.name:
                            tag_candidate = link.name
                            break

                if tag_candidate:
                    # Clean tag
                    raw_title = tag_candidate.strip()
                    normalized = normalize_hashtag(raw_title)
                    if normalized:
                        category = classify_category(raw_title)
                        rec = TrendRecord(
                            platform="tiktok",
                            category=category,
                            trend_type="hashtag",
                            raw_title=raw_title,
                            normalized_tag=normalized,
                            date_added=date_str,
                            rank=rank_val or row_idx,
                            post_count=post_count_val,
                            velocity_metric=velocity_val,
                            raw_metadata={
                                "uid": row.uid,
                                "source": "tiktok_creative_center_a11y",
                            },
                        )
                        records.append(rec)

        return records

    def parse_tiktok_audio(
        self, snapshot_text: str, anchor_date: Optional[str] = None
    ) -> List[TrendRecord]:
        """Extract trending audio / music tracks from TikTok Creative Center a11y tree snapshot."""
        date_str = get_default_date(anchor_date or self.default_anchor_date)
        trees = self.parse_a11y_tree(snapshot_text)
        records: List[TrendRecord] = []

        for root in trees:
            listitems = root.find_all_by_role("listitem")
            for idx, item in enumerate(listitems, 1):
                item_name = item.name.strip()
                # If item is a song listitem (e.g. "1. Montagem Mysterious Game - LXNGVX")
                texts = [c.name.strip() for c in item.find_all_by_role("text") if c.name.strip()]

                track_title = ""
                artist_name = ""
                rank_val: Optional[int] = None
                velocity_val: Optional[float] = None

                # Check texts inside listitem
                for t in texts:
                    if t.startswith("Rank "):
                        rank_match = re.search(r"Rank\s+(\d+)", t)
                        if rank_match:
                            rank_val = int(rank_match.group(1))
                    elif "%" in t:
                        velocity_val = parse_velocity_metric(t)
                    elif not track_title:
                        track_title = t
                    elif not artist_name:
                        artist_name = t

                # Fallback to item_name if text nodes didn't separate title and artist
                if not track_title and item_name:
                    # e.g. "1. Montagem Mysterious Game - LXNGVX"
                    clean_name = re.sub(r"^\d+[\.\:\-\s]+", "", item_name).strip()
                    if " - " in clean_name:
                        parts = clean_name.split(" - ", 1)
                        track_title = parts[0].strip()
                        artist_name = parts[1].strip()
                    else:
                        track_title = clean_name

                if track_title:
                    raw_title = f"{track_title} - {artist_name}".strip(" -")
                    normalized = normalize_hashtag(track_title)
                    category = classify_category(f"{track_title} {artist_name}")
                    rec = TrendRecord(
                        platform="tiktok",
                        category=category,
                        trend_type="audio",
                        raw_title=raw_title,
                        normalized_tag=normalized or track_title,
                        date_added=date_str,
                        rank=rank_val or idx,
                        velocity_metric=velocity_val,
                        raw_metadata={
                            "track_title": track_title,
                            "artist": artist_name,
                            "uid": item.uid,
                            "source": "tiktok_creative_center_audio_a11y",
                        },
                    )
                    records.append(rec)

        return records

    def parse_youtube_trending(
        self, snapshot_text: str, anchor_date: Optional[str] = None
    ) -> List[TrendRecord]:
        """Extract trending videos from YouTube Trending a11y tree snapshot."""
        date_str = get_default_date(anchor_date or self.default_anchor_date)
        trees = self.parse_a11y_tree(snapshot_text)
        records: List[TrendRecord] = []

        for root in trees:
            # Look for video links or headings
            headings = root.find_all_by_role("heading")
            links = root.find_all_by_role("link")

            # Collect video entries
            for rank_idx, heading in enumerate(headings, 1):
                # Check if heading has level=3 (standard video card title in YT a11y)
                heading_level = heading.attrs.get("level", "")
                heading_text = heading.name.strip()
                if not heading_text or heading_level not in {"3", "4"}:
                    continue

                # Find sibling or parent link info
                channel = ""
                view_count_val: Optional[int] = None
                published = ""

                # Look in parent or neighboring nodes
                # Find texts in link containing this heading
                for link in links:
                    if heading_text in link.name:
                        # Extract metadata from text children in link
                        texts = [c.name.strip() for c in link.find_all_by_role("text") if c.name.strip()]
                        for t in texts:
                            if "views" in t.lower():
                                view_count_val = parse_metric_number(t)
                            elif "ago" in t.lower():
                                published = t
                            elif t != heading_text and not channel:
                                channel = t
                        break

                raw_title = heading_text
                normalized = normalize_hashtag(raw_title)
                category = classify_category(f"{raw_title} {channel}")

                rec = TrendRecord(
                    platform="youtube",
                    category=category,
                    trend_type="video_title",
                    raw_title=raw_title,
                    normalized_tag=normalized or raw_title,
                    date_added=date_str,
                    rank=rank_idx,
                    post_count=view_count_val,
                    engagement_metrics={
                        "views": view_count_val,
                        "channel": channel,
                        "published": published,
                    },
                    raw_metadata={
                        "uid": heading.uid,
                        "source": "youtube_trending_a11y",
                    },
                )
                records.append(rec)

        return records

    def parse_snapshot(
        self, snapshot_text: str, platform: Optional[str] = None, anchor_date: Optional[str] = None
    ) -> List[TrendRecord]:
        """Dispatch snapshot parsing based on auto-detection or explicit platform."""
        if not snapshot_text or not snapshot_text.strip():
            return []

        p = (platform or "").lower()
        if p == "tiktok":
            return self.parse_tiktok_hashtags(snapshot_text, anchor_date) + self.parse_tiktok_audio(snapshot_text, anchor_date)
        elif p == "youtube":
            return self.parse_youtube_trending(snapshot_text, anchor_date)

        # Auto-detect from snapshot text
        lower_text = snapshot_text.lower()
        if "tiktok" in lower_text:
            return self.parse_tiktok_hashtags(snapshot_text, anchor_date) + self.parse_tiktok_audio(snapshot_text, anchor_date)
        elif "youtube" in lower_text:
            return self.parse_youtube_trending(snapshot_text, anchor_date)

        # If neither detected, try extracting both
        results = (
            self.parse_tiktok_hashtags(snapshot_text, anchor_date)
            + self.parse_tiktok_audio(snapshot_text, anchor_date)
            + self.parse_youtube_trending(snapshot_text, anchor_date)
        )
        return results

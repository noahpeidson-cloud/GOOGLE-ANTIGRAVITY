"""
metadata_tracker.py - SEO Engine, Safe-Zone Geometry Auditor, & SQLite Manifest Database

Handles:
1. SEO caption and title generation with frontloaded keywords.
2. 5-7 hashtag clustering formula (2 Broad, 2 Subgenre, 2 Entity/Event, 1 Community).
3. First-hour engagement velocity pinned comment hooks (Track ID Bounty, 1-10 Rating, Direct Tag).
4. Safe-zone geometric collision validator across YouTube Shorts and TikTok exclusion zones.
5. 17-keyword comment spam filter and blocklist export for YouTube Studio.
6. SQLite persistent lifecycle manifest database (media_manifest.sqlite).
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
import random
import re
import sqlite3
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import (
    AssetStatus,
    BrandType,
    ContentIDStatus,
    EventTier,
    GENRE_PROFILES,
    SAFE_ZONE_TIKTOK,
    SAFE_ZONE_YOUTUBE,
    SPAM_KEYWORDS,
    get_genre_profile,
    get_spam_blocklist_regex,
)

# Configure console encoding for cross-platform unicode / emoji safety
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class BoundingBox:
    """Represents an on-screen visual element bounding box."""
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height


@dataclass
class SafeZoneCollisionReport:
    """Detailed geometric collision evaluation result."""
    is_compliant: bool
    box: BoundingBox
    yt_compliant: bool
    yt_violations: List[str]
    tiktok_compliant: bool
    tiktok_violations: List[str]
    recommendation: str


@dataclass
class SEOPayload:
    """Complete platform-optimized metadata packaging payload."""
    brand: str
    tier: str
    event: str
    artist: str
    track: str
    genre: str
    yt_title: str
    yt_description: str
    tiktok_caption: str
    hashtags: List[str]
    first_hour_comments: Dict[str, str]
    scheduled_times: Dict[str, str]


# ============================================================================
# SEO CAPTION & METADATA GENERATOR
# ============================================================================

class SEOCaptionGenerator:
    """
    Produces high-retention titles, descriptions, hashtag clusters, and
    first-hour engagement hooks tuned for EDM short-form distribution.
    """

    @classmethod
    def generate_seo_package(
        cls,
        artist: str,
        track: str,
        event: str,
        genre: str = "house",
        year: int = 2026,
        stage: Optional[str] = None,
        brand: BrandType = BrandType.MUSIC_BAPTISM,
        tier: EventTier = EventTier.PILLAR_A,
    ) -> SEOPayload:
        """Constructs complete omnichannel metadata payload."""
        artist_clean = artist.strip()
        track_clean = track.strip()
        event_clean = event.strip()
        stage_clean = stage.strip() if stage else "Main Stage"

        # 1. 5-7 Hashtag Cluster Generation
        genre_prof = get_genre_profile(genre)
        hashtags: List[str] = []

        # 2 Broad Tags
        hashtags.extend(["#EDM", "#Festival"])

        # 2 Subgenre Tags
        for tag in genre_prof.recommended_hashtags[:2]:
            if tag not in hashtags:
                hashtags.append(tag)

        # 2 Entity / Event Tags
        clean_artist_tag = f"#{re.sub(r'[^A-Za-z0-9]', '', artist_clean)}"
        clean_event_tag = f"#{re.sub(r'[^A-Za-z0-9]', '', event_clean)}{year}"
        hashtags.append(clean_artist_tag)
        hashtags.append(clean_event_tag)

        # 1 Intent / Community Tag
        if brand == BrandType.MUSIC_BAPTISM:
            community_tag = "#BaptismOfMusic" if "#BaptismOfMusic" not in hashtags else "#LiveMusic"
            channel_name = "Baptism of Music"
            channel_handle = "@MusicBaptismLive"
            facebook_url = "https://www.facebook.com/BaptismOfMusic/"
        else:
            community_tag = "#LaserBaptism" if "#LaserBaptism" not in hashtags else "#EDMTok"
            channel_name = "Laser Baptism"
            channel_handle = "@LaserBaptism"
            facebook_url = ""
            
        hashtags.append(community_tag)

        # Trim to max 7 tags to prevent spam penalty
        hashtags = hashtags[:7]
        hashtag_str = " ".join(hashtags)

        # 2. YouTube Shorts Title (< 100 characters)
        yt_title = f"{artist_clean} dropping {track_clean} LIVE at {event_clean} {year} 🤯 #Shorts"
        if len(yt_title) > 95:
            yt_title = f"{artist_clean} - {track_clean} Live at {event_clean} #Shorts"

        # 3. YouTube Shorts Description
        facebook_text = f"Follow us on Facebook: {facebook_url}\n\n" if facebook_url else ""
        yt_description = (
            f"{artist_clean} performing '{track_clean}' live at {event_clean} {year} ({stage_clean}).\n\n"
            f"Experience pure concert energy and high-fidelity live audio.\n\n"
            f"Subscribe to {channel_name} ({channel_handle}) for daily festival highlights, "
            f"laser synchronization, and unreleased IDs.\n\n"
            f"{facebook_text}"
            f"{hashtag_str}\n\n"
            f"---\n"
            f"Content recorded live for promotional and documentary purposes under Fair Use. "
            f"All musical copyrights belong to the respective artists and record labels."
        )

        # 4. TikTok SEO Caption (Keyword-frontloaded)
        tiktok_caption = (
            f"{artist_clean} dropping {track_clean} live at {event_clean} {year} 🤯 "
            f"{stage_clean} was electric. {hashtag_str}"
        )

        # 5. First-Hour Pinned Engagement Comments
        comments = {
            "track_id_bounty": (
                "This unreleased track blew our minds. Crowdsourcing the ID—who knows who produced this? 👇"
            ),
            "binary_rating": (
                "Laser and bass drop rating: 1 to 10? Drop your rating below! 🔥👇"
            ),
            "artist_tag": (
                f"Filmed live at {event_clean}. @{artist_clean} dropped this at 3 AM. "
                f"When is this master finally dropping?! 🔊"
            ),
        }

        # 6. Peak Publishing Windows
        scheduled_times = {
            "eu_peak_window": "10:00 AM EST (15:00 UTC)",
            "us_peak_window": "06:00 PM EST (23:00 UTC)",
        }

        return SEOPayload(
            brand=brand.value if isinstance(brand, BrandType) else str(brand),
            tier=tier.value if isinstance(tier, EventTier) else str(tier),
            event=event_clean,
            artist=artist_clean,
            track=track_clean,
            genre=genre_prof.genre_name,
            yt_title=yt_title,
            yt_description=yt_description,
            tiktok_caption=tiktok_caption,
            hashtags=hashtags,
            first_hour_comments=comments,
            scheduled_times=scheduled_times,
        )


# ============================================================================
# SAFE ZONE COLLISION AUDITOR
# ============================================================================

class SafeZoneAuditor:
    """
    Evaluates on-screen text and graphical overlay bounding boxes against
    YouTube Shorts and TikTok UI exclusion zones on a 1080x1920 canvas.
    """

    @classmethod
    def audit_bounding_box(cls, box: BoundingBox) -> SafeZoneCollisionReport:
        """Audits overlay coordinates and identifies collision violations."""
        yt_violations: List[str] = []
        tiktok_violations: List[str] = []

        # 1. YouTube Shorts Exclusion Audits
        yt_sz = SAFE_ZONE_YOUTUBE.safe_zone
        if box.y < yt_sz.top_exclusion_y:
            yt_violations.append(
                f"Top exclusion collision: Y={box.y} < {yt_sz.top_exclusion_y}px "
                "(obscured by search bar / header icons)"
            )
        if box.y2 > yt_sz.bottom_exclusion_y:
            yt_violations.append(
                f"Bottom exclusion collision: Y2={box.y2} > {yt_sz.bottom_exclusion_y}px "
                "(obscured by title, @handle, sound marquee, subscribe button)"
            )
        if box.x2 > yt_sz.right_exclusion_x:
            yt_violations.append(
                f"Right exclusion collision: X2={box.x2} > {yt_sz.right_exclusion_x}px "
                "(obscured by Like/Comment/Share/Remix vertical action rail)"
            )
        if box.x < yt_sz.left_clearance_x:
            yt_violations.append(
                f"Left margin collision: X={box.x} < {yt_sz.left_clearance_x}px (clipped by left screen edge)"
            )

        # 2. TikTok Exclusion Audits
        tt_sz = SAFE_ZONE_TIKTOK.safe_zone
        if box.y < tt_sz.top_exclusion_y:
            tiktok_violations.append(
                f"Top exclusion collision: Y={box.y} < {tt_sz.top_exclusion_y}px "
                "(obscured by Following/FYP tabs & search bar)"
            )
        if box.y2 > tt_sz.bottom_exclusion_y:
            tiktok_violations.append(
                f"Bottom exclusion collision: Y2={box.y2} > {tt_sz.bottom_exclusion_y}px "
                "(obscured by username, caption, sound disc, system navigation)"
            )
        if box.x2 > tt_sz.right_exclusion_x:
            tiktok_violations.append(
                f"Right rail collision: X2={box.x2} > {tt_sz.right_exclusion_x}px "
                "(obscured by avatar, Like heart, Comment, Bookmark, Share stack)"
            )
        if box.x < tt_sz.left_clearance_x:
            tiktok_violations.append(
                f"Left clearance collision: X={box.x} < {tt_sz.left_clearance_x}px "
                "(less than 40px left margin clearance)"
            )

        yt_ok = len(yt_violations) == 0
        tt_ok = len(tiktok_violations) == 0
        is_compliant = yt_ok and tt_ok

        if is_compliant:
            rec = "Element is 100% compliant with universal safe zones on both platforms."
        else:
            rec = (
                "Adjust overlay coordinates: place element within universal safe box "
                "(X: 60 to 960 px, Y: 180 to 1450 px). Recommended top kinetic text position: Y=350 px."
            )

        return SafeZoneCollisionReport(
            is_compliant=is_compliant,
            box=box,
            yt_compliant=yt_ok,
            yt_violations=yt_violations,
            tiktok_compliant=tt_ok,
            tiktok_violations=tiktok_violations,
            recommendation=rec,
        )


# ============================================================================
# COMMENT SPAM FILTER & MODERATION BLOCKLIST
# ============================================================================

class CommentSpamFilter:
    """
    Enforces the 17-keyword spam blocklist to protect channel reputation
    against ticket scammers, phishing bots, and Telegram leak spam.
    """

    def __init__(self) -> None:
        self.regex = get_spam_blocklist_regex()

    def check_comment(self, comment_text: str) -> Tuple[bool, List[str]]:
        """
        Evaluates a comment string.
        Returns: (is_spam: bool, matched_keywords: List[str])
        """
        matches = self.regex.findall(comment_text)
        if not matches:
            return False, []
        # Return unique cleaned match tokens
        unique_matches = list(dict.fromkeys(m.strip().lower() for m in matches if m.strip()))
        return True, unique_matches

    @classmethod
    def export_blocklist_configuration(cls) -> Dict[str, Any]:
        """
        Exports formatted blocklist configurations for YouTube Studio Automated Filters.
        """
        return {
            "total_keywords": len(SPAM_KEYWORDS),
            "keywords_list": SPAM_KEYWORDS,
            "comma_separated_words": ", ".join(SPAM_KEYWORDS),
            "regex_pattern": get_spam_blocklist_regex().pattern,
            "block_links_enabled": True,
        }


from contextlib import contextmanager


# ============================================================================
# SQLITE MEDIA MANIFEST LIFECYCLE DATABASE
# ============================================================================

class MediaManifestDB:
    """
    Provides ACID SQLite persistence for tracking media assets across their
    entire production lifecycle (ingestion -> processing -> QC -> posting -> archive).
    Hardened for multi-threaded / concurrent access with WAL mode, busy timeout,
    and automatic retry backoff on database lock contention.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS asset_manifest (
        asset_id TEXT PRIMARY KEY,
        source_file_name TEXT NOT NULL,
        canonical_name TEXT NOT NULL,
        brand TEXT NOT NULL,
        tier TEXT NOT NULL,
        event_name TEXT,
        artist_name TEXT,
        track_name TEXT,
        genre TEXT,
        duration_seconds REAL,
        is_hdr INTEGER DEFAULT 0,
        measured_lufs REAL,
        measured_true_peak REAL,
        current_status TEXT NOT NULL,
        youtube_content_id_status TEXT DEFAULT 'UNCHECKED',
        safe_zone_verified INTEGER DEFAULT 0,
        raw_path TEXT,
        master_path TEXT,
        metadata_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_manifest_status ON asset_manifest(current_status);
    CREATE INDEX IF NOT EXISTS idx_manifest_brand ON asset_manifest(brand);
    """

    def __init__(self, db_path: Path = Path("media_manifest.sqlite")) -> None:
        self.db_path = Path(db_path).resolve()
        self._init_database()

    @contextmanager
    def _db_connection(self):
        """Context manager yielding a SQLite connection and guaranteeing clean closure."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except sqlite3.OperationalError:
            pass
        try:
            yield conn
        finally:
            conn.close()

    def _execute_write(self, operation: Callable[[sqlite3.Connection], Any], max_attempts: int = 10) -> Any:
        """Executes a database write callback with retry backoff for locked database operations."""
        for attempt in range(max_attempts):
            try:
                with self._db_connection() as conn:
                    result = operation(conn)
                    conn.commit()
                    return result
            except sqlite3.OperationalError as exc:
                err_msg = str(exc).lower()
                if ("locked" in err_msg or "busy" in err_msg) and attempt < max_attempts - 1:
                    sleep_time = (0.02 * (2 ** attempt)) + random.uniform(0.01, 0.05)
                    time.sleep(sleep_time)
                else:
                    raise

    def _execute_read(self, operation: Callable[[sqlite3.Connection], Any], max_attempts: int = 10) -> Any:
        """Executes a database read callback with retry backoff on database lock contention."""
        for attempt in range(max_attempts):
            try:
                with self._db_connection() as conn:
                    return operation(conn)
            except sqlite3.OperationalError as exc:
                err_msg = str(exc).lower()
                if ("locked" in err_msg or "busy" in err_msg) and attempt < max_attempts - 1:
                    sleep_time = (0.02 * (2 ** attempt)) + random.uniform(0.01, 0.05)
                    time.sleep(sleep_time)
                else:
                    raise

    def _init_database(self) -> None:
        """Initializes database schema and indexes."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        def _op(conn: sqlite3.Connection) -> None:
            conn.executescript(self.SCHEMA)
        self._execute_write(_op)

    def upsert_asset(
        self,
        asset_id: str,
        source_file_name: str,
        canonical_name: str,
        brand: str,
        tier: str,
        event_name: Optional[str] = None,
        artist_name: Optional[str] = None,
        track_name: Optional[str] = None,
        genre: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        is_hdr: bool = False,
        measured_lufs: Optional[float] = None,
        measured_true_peak: Optional[float] = None,
        current_status: AssetStatus = AssetStatus.IN_PROGRESS,
        youtube_content_id_status: ContentIDStatus = ContentIDStatus.UNCHECKED,
        safe_zone_verified: bool = False,
        raw_path: Optional[str] = None,
        master_path: Optional[str] = None,
        metadata_dict: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Inserts or updates an asset record."""
        meta_json = json.dumps(metadata_dict) if metadata_dict else None
        now_str = datetime.now().isoformat()

        sql = """
        INSERT INTO asset_manifest (
            asset_id, source_file_name, canonical_name, brand, tier,
            event_name, artist_name, track_name, genre, duration_seconds,
            is_hdr, measured_lufs, measured_true_peak, current_status,
            youtube_content_id_status, safe_zone_verified, raw_path,
            master_path, metadata_json, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?
        )
        ON CONFLICT(asset_id) DO UPDATE SET
            canonical_name=excluded.canonical_name,
            brand=excluded.brand,
            tier=excluded.tier,
            event_name=excluded.event_name,
            artist_name=excluded.artist_name,
            track_name=excluded.track_name,
            genre=excluded.genre,
            duration_seconds=COALESCE(excluded.duration_seconds, asset_manifest.duration_seconds),
            is_hdr=excluded.is_hdr,
            measured_lufs=COALESCE(excluded.measured_lufs, asset_manifest.measured_lufs),
            measured_true_peak=COALESCE(excluded.measured_true_peak, asset_manifest.measured_true_peak),
            current_status=excluded.current_status,
            youtube_content_id_status=excluded.youtube_content_id_status,
            safe_zone_verified=excluded.safe_zone_verified,
            raw_path=COALESCE(excluded.raw_path, asset_manifest.raw_path),
            master_path=COALESCE(excluded.master_path, asset_manifest.master_path),
            metadata_json=COALESCE(excluded.metadata_json, asset_manifest.metadata_json),
            updated_at=excluded.updated_at;
        """

        params = (
            asset_id,
            source_file_name,
            canonical_name,
            brand,
            tier,
            event_name,
            artist_name,
            track_name,
            genre,
            duration_seconds,
            1 if is_hdr else 0,
            measured_lufs,
            measured_true_peak,
            current_status.value if isinstance(current_status, AssetStatus) else str(current_status),
            youtube_content_id_status.value if isinstance(youtube_content_id_status, ContentIDStatus) else str(youtube_content_id_status),
            1 if safe_zone_verified else 0,
            raw_path,
            master_path,
            meta_json,
            now_str,
            now_str,
        )

        def _op(conn: sqlite3.Connection) -> None:
            conn.execute(sql, params)

        self._execute_write(_op)

    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single asset record by ID."""
        sql = "SELECT * FROM asset_manifest WHERE asset_id = ?"

        def _op(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            row = conn.execute(sql, (asset_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get("metadata_json"):
                try:
                    d["metadata"] = json.loads(d["metadata_json"])
                except json.JSONDecodeError:
                    d["metadata"] = {}
            return d

        return self._execute_read(_op)

    def list_assets(self, status: Optional[AssetStatus] = None) -> List[Dict[str, Any]]:
        """Lists asset records, optionally filtered by lifecycle status."""
        if status:
            status_val = status.value if isinstance(status, AssetStatus) else str(status)
            sql = "SELECT * FROM asset_manifest WHERE current_status = ? ORDER BY created_at DESC"
            params: Tuple[Any, ...] = (status_val,)
        else:
            sql = "SELECT * FROM asset_manifest ORDER BY created_at DESC"
            params = ()

        def _op(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("metadata_json"):
                    try:
                        d["metadata"] = json.loads(d["metadata_json"])
                    except json.JSONDecodeError:
                        d["metadata"] = {}
                results.append(d)
            return results

        return self._execute_read(_op)

    def update_status(self, asset_id: str, new_status: AssetStatus) -> bool:
        """Updates the lifecycle status of an asset."""
        now_str = datetime.now().isoformat()
        status_val = new_status.value if isinstance(new_status, AssetStatus) else str(new_status)
        sql = "UPDATE asset_manifest SET current_status = ?, updated_at = ? WHERE asset_id = ?"

        def _op(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(sql, (status_val, now_str, asset_id))
            return cursor.rowcount > 0

        return bool(self._execute_write(_op))


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="EDM Metadata Engine, Safe-Zone Auditor & Manifest Tracker (Track 2: Content Creation)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--generate-seo", action="store_true", help="Generate platform SEO packaging.")
    group.add_argument("--audit-safezone", action="store_true", help="Audit an on-screen overlay coordinate box.")
    group.add_argument("--export-blocklist", action="store_true", help="Export comment spam filter blocklists.")
    group.add_argument("--list-manifest", action="store_true", help="List tracked assets in the SQLite manifest.")

    parser.add_argument("--brand", choices=[b.value for b in BrandType], default=BrandType.MUSIC_BAPTISM.value)
    parser.add_argument("--tier", choices=[t.value for t in EventTier], default=EventTier.PILLAR_A.value)
    parser.add_argument("--event", default="EDCOrlando", help="Event name.")
    parser.add_argument("--artist", default="JohnSummit", help="DJ/Artist name.")
    parser.add_argument("--track", default="WhereYouAre", help="Track name or ID.")
    parser.add_argument("--genre", default="house", help="EDM subgenre (house, dubstep, techno, trance, dnb).")
    parser.add_argument("--year", type=int, default=2026, help="Production year.")
    parser.add_argument("--overlay-box", nargs=4, type=int, metavar=("X", "Y", "W", "H"), help="Overlay box coordinates (X Y W H).")
    parser.add_argument("--db-path", default="media_manifest.sqlite", help="Path to SQLite manifest database.")

    args = parser.parse_args()

    if args.generate_seo:
        seo = SEOCaptionGenerator.generate_seo_package(
            artist=args.artist,
            track=args.track,
            event=args.event,
            genre=args.genre,
            year=args.year,
            brand=BrandType(args.brand),
            tier=EventTier(args.tier),
        )
        print("=" * 70)
        print("EDM SHORT-FORM SEO PACKAGING")
        print("=" * 70)
        print(f"Brand: {seo.brand} | Tier: {seo.tier} | Genre: {seo.genre}")
        print(f"\n[YOUTUBE SHORTS TITLE] ({len(seo.yt_title)} chars):\n{seo.yt_title}")
        print(f"\n[TIKTOK CAPTION]:\n{seo.tiktok_caption}")
        print(f"\n[HASHTAG CLUSTER] ({len(seo.hashtags)} tags):\n{' '.join(seo.hashtags)}")
        print("\n[FIRST-HOUR PINNED COMMENTS]:")
        for k, v in seo.first_hour_comments.items():
            print(f"  • {k.upper()}: {v}")
        print(f"\n[SCHEDULED PEAK WINDOWS]:\n  EU: {seo.scheduled_times['eu_peak_window']}\n  US: {seo.scheduled_times['us_peak_window']}")
        print("=" * 70)

    elif args.audit_safezone:
        if not args.overlay_box:
            print("[ERROR] Please provide --overlay-box X Y WIDTH HEIGHT for safe-zone audit.", file=sys.stderr)
            sys.exit(1)
        x, y, w, h = args.overlay_box
        box = BoundingBox(x=x, y=y, width=w, height=h)
        report = SafeZoneAuditor.audit_bounding_box(box)
        print("=" * 70)
        print("SAFE ZONE GEOMETRIC AUDIT REPORT")
        print("=" * 70)
        print(f"Overlay Box: X={box.x}, Y={box.y}, W={box.width}, H={box.height} (Bottom-Right: X2={box.x2}, Y2={box.y2})")
        print(f"Universal Compliance: {'[PASSED]' if report.is_compliant else '[VIOLATION DETECTED]'}")
        print(f"YouTube Shorts: {'PASS' if report.yt_compliant else 'FAIL'}")
        for v in report.yt_violations:
            print(f"  - [YT VIOLATION] {v}")
        print(f"TikTok: {'PASS' if report.tiktok_compliant else 'FAIL'}")
        for v in report.tiktok_violations:
            print(f"  - [TIKTOK VIOLATION] {v}")
        print(f"\nRecommendation: {report.recommendation}")
        print("=" * 70)

    elif args.export_blocklist:
        cfg = CommentSpamFilter.export_blocklist_configuration()
        print("=" * 70)
        print("YOUTUBE STUDIO AUTOMATED COMMENT SPAM FILTER CONFIGURATION")
        print("=" * 70)
        print(f"Total Blocked Keywords: {cfg['total_keywords']}")
        print(f"\n[COMMA SEPARATED LIST FOR STUDIO UI]:\n{cfg['comma_separated_words']}")
        print(f"\n[REGEX PATTERN]:\n{cfg['regex_pattern']}")
        print("\nMandatory UI Setting: Check 'Block links' checkbox in YouTube Studio.")
        print("=" * 70)

    elif args.list_manifest:
        db = MediaManifestDB(db_path=Path(args.db_path))
        assets = db.list_assets()
        print("=" * 70)
        print(f"MEDIA MANIFEST DATABASE ({len(assets)} recorded assets)")
        print("=" * 70)
        for a in assets:
            print(f"• ID: {a['asset_id']} | Status: {a['current_status']} | Brand: {a['brand']}")
            print(f"  Canonical Name: {a['canonical_name']}")
            print(f"  Duration: {a['duration_seconds'] or 'N/A'}s | LUFS: {a['measured_lufs'] or 'N/A'} | TP: {a['measured_true_peak'] or 'N/A'} dBTP")
            print(f"  Updated: {a['updated_at']}")
            print("-" * 50)


if __name__ == "__main__":
    main()

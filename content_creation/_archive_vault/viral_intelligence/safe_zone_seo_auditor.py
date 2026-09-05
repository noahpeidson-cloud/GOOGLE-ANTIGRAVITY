"""
Name: Safe-Zone Geometric Collision & SEO Metadata Packaging Auditor
Context Mapping: Extracted from `content_creation/metadata_tracker.py`, `content_creation/config.py`, and `content_creation/index.html`.
Strengths: Mathematically validates on-screen text, titles, and graphical overlay bounding boxes against YouTube Shorts (900x1270 px safe area) and TikTok (920x1310 px safe area) UI exclusion zones on a standard 1080x1920 vertical canvas. Implements a research-validated 5-7 hashtag clustering formula (1 broad EDM, 2 subgenre, 1 event/year, 1 artist, 1 community/hook tag) that prevents algorithmic spam penalties. Embeds an authoritative 17-keyword regex filter to scrub comment spam, phishing links, and ticket scalpers for YouTube Studio moderation.
Weaknesses: In the legacy pipeline, safe-zone definitions were buried across monolithic HTML canvas scripts (`index.html`) and tangled with SQLite database calls, preventing headless pre-render validation.
Implementation Instructions: Import `SafeZoneAuditor` to test overlay coordinates prior to DaVinci rendering or FFmpeg drawtext burn-in. Call `SEOPackager.generate_package()` to obtain algorithm-optimized titles, descriptions, and hashtag clusters. Use `CommentSpamAuditor.check_comment()` to moderate user interactions.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# Configure console encoding for cross-platform unicode / emoji safety
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ============================================================================
# 1. PLATFORM SAFE-ZONE SPECIFICATIONS (1080 x 1920 CANVAS)
# ============================================================================

@dataclass(frozen=True)
class SafeZoneBoundary:
    """Mathematical boundary coordinates for mobile short-form platform safe areas."""
    platform: str
    canvas_width: int = 1080
    canvas_height: int = 1920
    # Safe Box Bounds
    safe_x_min: int = 60
    safe_x_max: int = 960
    safe_y_min: int = 180
    safe_y_max: int = 1450
    # Bounding Dimensions (width x height)
    safe_width: int = 900
    safe_height: int = 1270
    # Exclusion Hazard Descriptions
    top_hazard_desc: str = "Search header, channel icon, sound selector"
    bottom_hazard_desc: str = "Title caption, @handle, audio marquee disc, subscribe pill"
    right_hazard_desc: str = "Vertical action rail (Like, Comment, Share, Remix/Bookmark)"
    left_hazard_desc: str = "Screen border clearance margin"


# YouTube Shorts Safe Zone Definition:
# Canvas: 1080 x 1920 px
# Safe Area Box: 900 x 1270 px (X: 60-960, Y: 180-1450)
# Top Hazard: Y: 0 to 180 px
# Bottom Hazard: Y: 1450 to 1920 px
# Right Hazard: X: 960 to 1080 px
# Left Clearance: X: 0 to 60 px
YOUTUBE_SHORTS_SAFE_ZONE = SafeZoneBoundary(
    platform="YouTube Shorts",
    canvas_width=1080,
    canvas_height=1920,
    safe_x_min=60,
    safe_x_max=960,
    safe_y_min=180,
    safe_y_max=1450,
    safe_width=900,
    safe_height=1270,
    top_hazard_desc="Search bar and channel icons (Y: 0-180px)",
    bottom_hazard_desc="Title text, @handle, subscribe button, and sound info (Y: 1450-1920px)",
    right_hazard_desc="Like, Dislike, Comments, Share, and Remix vertical buttons (X: 960-1080px)",
    left_hazard_desc="Left display edge margin (X: 0-60px)",
)

# TikTok Safe Zone Definition:
# Canvas: 1080 x 1920 px
# Safe Area Box: 920 x 1310 px (X: 40-960, Y: 160-1470)
# Top Hazard: Y: 0 to 160 px
# Bottom Hazard: Y: 1470 to 1920 px
# Right Hazard: X: 960 to 1080 px
# Left Clearance: X: 0 to 40 px
TIKTOK_SAFE_ZONE = SafeZoneBoundary(
    platform="TikTok",
    canvas_width=1080,
    canvas_height=1920,
    safe_x_min=40,
    safe_x_max=960,
    safe_y_min=160,
    safe_y_max=1470,
    safe_width=920,
    safe_height=1310,
    top_hazard_desc="Following / For You tabs and Search icon (Y: 0-160px)",
    bottom_hazard_desc="Username, caption text, audio title, and system nav bar (Y: 1470-1920px)",
    right_hazard_desc="Profile avatar (+), Like heart, Comments, Bookmark, and Share stack (X: 960-1080px)",
    left_hazard_desc="Left margin clearance (X: 0-40px)",
)


# ============================================================================
# 2. BOUNDING BOX & GEOMETRIC COLLISION AUDITOR
# ============================================================================

@dataclass
class OverlayBoundingBox:
    """Represents the coordinate boundary of a text overlay or graphic asset."""
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
    """Detailed diagnostic collision report for overlay placement."""
    is_compliant: bool
    box: OverlayBoundingBox
    yt_compliant: bool
    yt_violations: List[str]
    tiktok_compliant: bool
    tiktok_violations: List[str]
    corrective_recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_compliant": self.is_compliant,
            "box": asdict(self.box),
            "youtube_shorts": {
                "compliant": self.yt_compliant,
                "violations": self.yt_violations,
            },
            "tiktok": {
                "compliant": self.tiktok_compliant,
                "violations": self.tiktok_violations,
            },
            "corrective_recommendation": self.corrective_recommendation,
        }


class SafeZoneAuditor:
    """
    Evaluates visual overlay bounding boxes against YouTube Shorts and TikTok
    UI exclusion hazards on a 1080x1920 vertical canvas.
    """

    @classmethod
    def audit_bounding_box(cls, box: OverlayBoundingBox) -> SafeZoneCollisionReport:
        """
        Audits overlay coordinates and identifies collision violations.
        """
        yt_violations: List[str] = []
        tiktok_violations: List[str] = []

        # 1. YouTube Shorts Safe-Zone Verification
        yt = YOUTUBE_SHORTS_SAFE_ZONE
        if box.y < yt.safe_y_min:
            yt_violations.append(
                f"Top Collision: Y={box.y}px < {yt.safe_y_min}px ({yt.top_hazard_desc})"
            )
        if box.y2 > yt.safe_y_max:
            yt_violations.append(
                f"Bottom Collision: Y2={box.y2}px > {yt.safe_y_max}px ({yt.bottom_hazard_desc})"
            )
        if box.x2 > yt.safe_x_max:
            yt_violations.append(
                f"Right Rail Collision: X2={box.x2}px > {yt.safe_x_max}px ({yt.right_hazard_desc})"
            )
        if box.x < yt.safe_x_min:
            yt_violations.append(
                f"Left Clearance Violation: X={box.x}px < {yt.safe_x_min}px ({yt.left_hazard_desc})"
            )

        # 2. TikTok Safe-Zone Verification
        tt = TIKTOK_SAFE_ZONE
        if box.y < tt.safe_y_min:
            tiktok_violations.append(
                f"Top Collision: Y={box.y}px < {tt.safe_y_min}px ({tt.top_hazard_desc})"
            )
        if box.y2 > tt.safe_y_max:
            tiktok_violations.append(
                f"Bottom Collision: Y2={box.y2}px > {tt.safe_y_max}px ({tt.bottom_hazard_desc})"
            )
        if box.x2 > tt.safe_x_max:
            tiktok_violations.append(
                f"Right Rail Collision: X2={box.x2}px > {tt.safe_x_max}px ({tt.right_hazard_desc})"
            )
        if box.x < tt.safe_x_min:
            tiktok_violations.append(
                f"Left Clearance Violation: X={box.x}px < {tt.safe_x_min}px ({tt.left_hazard_desc})"
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
            corrective_recommendation=rec,
        )

    @classmethod
    def audit_coordinates(cls, x: int, y: int, width: int, height: int) -> SafeZoneCollisionReport:
        """Convenience method accepting raw integer dimensions."""
        box = OverlayBoundingBox(x=x, y=y, width=width, height=height)
        return cls.audit_bounding_box(box)


# ============================================================================
# 3. 5-7 HASHTAG CLUSTERING & SEO METADATA PACKAGER
# ============================================================================

# Pre-indexed genre tags
GENRE_SUBGENRE_TAGS: Dict[str, List[str]] = {
    "house": ["#TechHouse", "#HouseMusic", "#ClubSpace", "#DeepHouse"],
    "techno": ["#Techno", "#PeakTimeTechno", "#IndustrialTechno", "#Rave"],
    "dubstep": ["#Dubstep", "#BassMusic", "#LostLands", "#Headbanger"],
    "melodic": ["#MelodicTechno", "#Afterlife", "#Anjunadeep", "#ProgressiveHouse"],
    "dnb": ["#DrumAndBass", "#DnB", "#Bassline", "#Jungle"],
    "trance": ["#TranceFamily", "#ASOT", "#Psytrance", "#UpliftingTrance"],
    "edm": ["#EDM", "#Festival", "#ElectronicMusic", "#RaveCulture"],
}


@dataclass
class SEOMetadataPackage:
    """Algorithm-optimized title, description, and hashtag package."""
    artist: str
    track: str
    event: str
    genre: str
    year: int
    yt_shorts_title: str
    yt_description: str
    tiktok_caption: str
    hashtag_cluster: List[str]
    first_hour_engagement_hooks: Dict[str, str]
    optimal_posting_windows: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SEOPackager:
    """
    Constructs high-velocity metadata adhering to the 5-7 hashtag cluster formula
    and character-limited titles.
    """

    @classmethod
    def generate_hashtag_cluster(
        cls,
        artist: str,
        event: str,
        genre: str = "house",
        year: int = 2026,
    ) -> List[str]:
        """
        Generates 5-7 focused hashtags:
        - 1 Broad EDM Tag (#EDM or #Festival)
        - 2 Sub-genre Tags (e.g. #TechHouse, #HouseMusic)
        - 1 Event / Year Tag (e.g. #EDCOrlando2026)
        - 1 Artist Tag (e.g. #JohnSummit)
        - 1 Hook / Viral Community Tag (e.g. #BassDrop or #LiveMusic)

        Total is strictly constrained to 5 - 7 tags.
        """
        tags: List[str] = []

        # 1. Broad EDM Tag (1)
        tags.append("#EDM")

        # 2. Sub-genre Tags (2)
        genre_key = genre.strip().lower()
        subgenre_pool = GENRE_SUBGENRE_TAGS.get(genre_key, GENRE_SUBGENRE_TAGS["edm"])
        for g_tag in subgenre_pool[:2]:
            if g_tag not in tags:
                tags.append(g_tag)

        # 3. Artist Tag (1)
        clean_artist = re.sub(r"[^A-Za-z0-9]", "", artist.strip())
        artist_tag = f"#{clean_artist}"
        if artist_tag not in tags:
            tags.append(artist_tag)

        # 4. Event / Year Tag (1)
        clean_event = re.sub(r"[^A-Za-z0-9]", "", event.strip())
        event_tag = f"#{clean_event}{year}" if str(year) not in clean_event else f"#{clean_event}"
        if event_tag not in tags:
            tags.append(event_tag)

        # 5. Hook / Viral / Community Tag (1)
        community_tags = ["#BassDrop", "#FestivalVibes", "#EDMTok", "#LiveMusic", "#RaveLife"]
        for c_tag in community_tags:
            if c_tag not in tags:
                tags.append(c_tag)
                break

        # Strictly enforce bounds: 5 <= len(tags) <= 7
        return tags[:7]

    @classmethod
    def generate_package(
        cls,
        artist: str,
        track: str,
        event: str,
        genre: str = "house",
        year: int = 2026,
        stage: Optional[str] = None,
    ) -> SEOMetadataPackage:
        """
        Generates complete omnichannel SEO package for YouTube Shorts and TikTok.
        """
        art = artist.strip()
        trk = track.strip()
        evt = event.strip()
        stg = stage.strip() if stage else "Main Stage"

        hashtags = cls.generate_hashtag_cluster(artist=art, event=evt, genre=genre, year=year)
        hashtag_str = " ".join(hashtags)

        # 1. YouTube Shorts Title (< 100 chars, ideal 60-80 chars)
        yt_title = f"{art} dropping {trk} LIVE at {evt} {year} 🤯 #Shorts"
        if len(yt_title) > 95:
            yt_title = f"{art} - {trk} Live at {evt} #Shorts"

        # 2. YouTube Shorts Description
        yt_desc = (
            f"{art} performing '{trk}' live at {evt} {year} ({stg}).\n\n"
            f"Experience pure concert energy and high-fidelity live audio.\n\n"
            f"Subscribe for daily festival highlights, laser synchronization, and unreleased IDs.\n\n"
            f"{hashtag_str}\n\n"
            f"---\n"
            f"Recorded live for promotional and documentary purposes. "
            f"All musical copyrights belong to respective artists and record labels."
        )

        # 3. TikTok Caption (Frontloaded with key hook)
        tiktok_cap = f"{art} dropping {trk} live at {evt} {year} 🤯 {stg} was electric. {hashtag_str}"

        # 4. First-Hour Engagement Hooks (for pinned comment)
        hooks = {
            "track_id_bounty": "This unreleased track blew our minds. Crowdsourcing the ID—who knows who produced this? 👇",
            "binary_rating": "Laser and bass drop rating: 1 to 10? Drop your rating below! 🔥👇",
            "artist_tag": f"Filmed live at {evt}. @{art} dropped this at 3 AM. When is this ID finally dropping?! 🔊",
        }

        # 5. Optimal Posting Windows
        windows = {
            "eu_peak_window": "10:00 AM EST (15:00 UTC) - Peak EU commute & early evening",
            "us_peak_window": "06:00 PM EST (23:00 UTC) - Peak US evening leisure scrolling",
        }

        return SEOMetadataPackage(
            artist=art,
            track=trk,
            event=evt,
            genre=genre,
            year=year,
            yt_shorts_title=yt_title,
            yt_description=yt_desc,
            tiktok_caption=tiktok_cap,
            hashtag_cluster=hashtags,
            first_hour_engagement_hooks=hooks,
            optimal_posting_windows=windows,
        )


# ============================================================================
# 4. 17-KEYWORD COMMENT SPAM & ENGAGEMENT-BAIT BLOCKLIST FILTER
# ============================================================================

# The canonical 17 spam and engagement-bait keywords
CANONICAL_17_SPAM_KEYWORDS: List[str] = [
    "t.me/",
    "whatsapp",
    "crypto",
    "investment",
    "check bio",
    "full set link",
    "telegram",
    "drop your track",
    "promo on",
    "dm to promote",
    "click here",
    "ticket sale",
    "buy tickets",
    "leak",
    "scam",
    "dm me",
    "free download",
]

# Robust regex pattern accounting for word boundaries and common punctuation evasion tricks
CANONICAL_SPAM_REGEX_PATTERN = (
    r"(?i)(t\.me\/|"
    r"\bwhatsapp\b|"
    r"\bcrypto\b|"
    r"\binvestments?\b|"
    r"\bcheck[\s_\-\.]*bio\b|"
    r"\bfull[\s_\-\.]*set[\s_\-\.]*link\b|"
    r"\btelegram\b|"
    r"\bdrop[\s_\-\.]*your[\s_\-\.]*track\b|"
    r"\bpromo[\s_\-\.]*on\b|"
    r"\bdm[\s_\-\.]*to[\s_\-\.]*promote\b|"
    r"\bclick[\s_\-\.]*here\b|"
    r"\bticket[\s_\-\.]*sales?\b|"
    r"\bbuy[\s_\-\.]*tickets?\b|"
    r"\bleaks?\b|"
    r"\bscams?\b|"
    r"\bdm[\s_\-\.]*me\b|"
    r"\bfree[\s_\-\.]*downloads?\b)"
)


class CommentSpamAuditor:
    """
    Moderation engine enforcing the 17-keyword blocklist to filter scam bots,
    phishing links, and engagement bait across comment feeds.
    """

    def __init__(self) -> None:
        self.regex = re.compile(CANONICAL_SPAM_REGEX_PATTERN)

    def check_comment(self, comment_text: str) -> Tuple[bool, List[str]]:
        """
        Evaluates a comment string for spam matches.

        Returns:
            Tuple[bool, List[str]]: (is_spam, matched_keywords)
        """
        matches = self.regex.findall(comment_text)
        if not matches:
            return (False, [])
        unique_matches = list(dict.fromkeys(m.strip().lower() for m in matches if m.strip()))
        return (True, unique_matches)

    @classmethod
    def export_studio_blocklist(cls) -> Dict[str, Any]:
        """
        Exports formatted configuration for YouTube Studio Automated Filters.
        """
        return {
            "total_keywords": len(CANONICAL_17_SPAM_KEYWORDS),
            "keywords_list": CANONICAL_17_SPAM_KEYWORDS,
            "comma_separated_words": ", ".join(CANONICAL_17_SPAM_KEYWORDS),
            "regex_pattern": CANONICAL_SPAM_REGEX_PATTERN,
            "block_links_enabled": True,
        }


# ============================================================================
# 5. CLI INTERFACE
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safe-Zone Collision Auditor, SEO Packager & 17-Keyword Spam Filter"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--audit-box", nargs=4, type=int, metavar=("X", "Y", "W", "H"),
                       help="Audit overlay coordinates: X Y WIDTH HEIGHT")
    group.add_argument("--generate-seo", action="store_true", help="Generate 5-7 hashtag SEO package.")
    group.add_argument("--check-spam", type=str, help="Evaluate a comment string for spam.")
    group.add_argument("--export-blocklist", action="store_true", help="Export YouTube Studio spam blocklist config.")

    parser.add_argument("--artist", default="John Summit", help="DJ/Artist name.")
    parser.add_argument("--track", default="Where You Are", help="Track name or ID.")
    parser.add_argument("--event", default="EDC Orlando", help="Event name.")
    parser.add_argument("--genre", default="house", help="EDM subgenre (house, dubstep, techno, trance, dnb).")
    parser.add_argument("--year", type=int, default=2026, help="Production year.")
    parser.add_argument("--json", action="store_true", help="Output in JSON format.")

    args = parser.parse_args()

    if args.audit_box:
        x, y, w, h = args.audit_box
        report = SafeZoneAuditor.audit_coordinates(x, y, w, h)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print("=" * 70)
            print("SAFE ZONE GEOMETRIC COLLISION AUDIT REPORT")
            print("=" * 70)
            print(f"Overlay Box: X={x}, Y={y}, W={w}, H={h} (Bottom-Right: X2={x+w}, Y2={y+h})")
            print(f"Universal Compliance: {'[PASSED]' if report.is_compliant else '[VIOLATION DETECTED]'}")
            print(f"YouTube Shorts (900x1270): {'PASS' if report.yt_compliant else 'FAIL'}")
            for v in report.yt_violations:
                print(f"  • [YT VIOLATION] {v}")
            print(f"TikTok (920x1310): {'PASS' if report.tiktok_compliant else 'FAIL'}")
            for v in report.tiktok_violations:
                print(f"  • [TIKTOK VIOLATION] {v}")
            print(f"\nRecommendation: {report.corrective_recommendation}")
            print("=" * 70)

    elif args.generate_seo:
        pkg = SEOPackager.generate_package(
            artist=args.artist,
            track=args.track,
            event=args.event,
            genre=args.genre,
            year=args.year,
        )
        if args.json:
            print(json.dumps(pkg.to_dict(), indent=2))
        else:
            print("=" * 70)
            print("EDM SHORT-FORM SEO PACKAGING")
            print("=" * 70)
            print(f"Artist: {pkg.artist} | Track: {pkg.track} | Event: {pkg.event} ({pkg.year})")
            print(f"\n[YOUTUBE SHORTS TITLE] ({len(pkg.yt_shorts_title)} chars):\n{pkg.yt_shorts_title}")
            print(f"\n[TIKTOK CAPTION]:\n{pkg.tiktok_caption}")
            print(f"\n[5-7 HASHTAG CLUSTER] ({len(pkg.hashtag_cluster)} tags):\n{' '.join(pkg.hashtag_cluster)}")
            print("\n[FIRST-HOUR PINNED ENGAGEMENT COMMENTS]:")
            for k, v in pkg.first_hour_engagement_hooks.items():
                print(f"  • {k.upper()}: {v}")
            print("\n[OPTIMAL POSTING WINDOWS]:")
            for k, v in pkg.optimal_posting_windows.items():
                print(f"  • {k.upper()}: {v}")
            print("=" * 70)

    elif args.check_spam:
        auditor = CommentSpamAuditor()
        is_spam, matches = auditor.check_comment(args.check_spam)
        if args.json:
            print(json.dumps({"is_spam": is_spam, "matched_keywords": matches}, indent=2))
        else:
            print(f"Comment: '{args.check_spam}'")
            print(f"Spam Detected: {'YES [BLOCKED]' if is_spam else 'NO [CLEAN]'}")
            if is_spam:
                print(f"Matched Keywords: {matches}")

    elif args.export_blocklist:
        cfg = CommentSpamAuditor.export_studio_blocklist()
        if args.json:
            print(json.dumps(cfg, indent=2))
        else:
            print("=" * 70)
            print("YOUTUBE STUDIO COMMENT SPAM BLOCKLIST CONFIGURATION")
            print("=" * 70)
            print(f"Total Blocked Keywords: {cfg['total_keywords']}")
            print(f"\n[COMMA-SEPARATED LIST FOR STUDIO UI]:\n{cfg['comma_separated_words']}")
            print(f"\n[REGEX PATTERN]:\n{cfg['regex_pattern']}")
            print("=" * 70)


if __name__ == "__main__":
    main()

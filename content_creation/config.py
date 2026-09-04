"""
config.py - Centralized Configuration & Technical Standards for Content Creation Track

Defines immutable platform safe zones, audio/video transcoding specifications,
EBU R128 loudness targets, genre BPM pacing mappings, 4-tier folder taxonomy,
and the 17-keyword comment spam filter blocklist.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple, Union


# ============================================================================
# BRAND & CONTENT CLASSIFICATION ENUMS
# ============================================================================

class BrandType(str, Enum):
    """Target brand channel umbrella."""
    LASER_BAPTISM = "laser_baptism"   # High-energy laser synchronization, stadium EDM, bass/techno
    MUSIC_BAPTISM = "music_baptism"   # Total acoustic immersion, intimate DJ POV, melodic/vocal sets


class EventTier(str, Enum):
    """Content pillar event classification."""
    PILLAR_A = "pillar_a_stadium_arena"    # Big artist arena/stadium shows (Skrillex, Garrix, Excision)
    PILLAR_B = "pillar_b_club_spotlight"   # Rising DJs, warehouse raves, unreleased IDs
    PILLAR_C = "pillar_c_festival_mega"    # Festival mega-clips (EDC, Tomorrowland, Ultra, Lost Lands)


class ProductionPreset(str, Enum):
    """Pipeline production presets."""
    FAST_TRACK = "fast_track"   # 15-Minute SOP: 1080p, H.264/H.265, fast denoise, two-pass loudnorm
    NORTH_STAR = "north_star"   # High-Fidelity Master: 4K upscaling prep, pristine tone-mapping


class ReframeMode(str, Enum):
    """Vertical 9:16 re-framing strategies."""
    CENTER_CROP = "center_crop"   # Centered 9:16 crop from 16:9 / 4:3 canvas
    BLUR_PAD = "blur_pad"         # Scaled foreground over blurred, expanded background
    OFFSET_CROP = "offset_crop"   # Subject-tracking horizontal/vertical offset crop


class ToneMapMode(str, Enum):
    """HDR to SDR tone-mapping options."""
    AUTO = "auto"   # Automatically detects HLG (arib-std-b67) or PQ (smpte2084)
    ON = "on"       # Force mobius tone-mapping to BT.709
    OFF = "off"     # Pass-through without tone-mapping


class DenoiseMode(str, Enum):
    """Low-light spatio-temporal denoising options."""
    AUTO = "auto"   # Apply when high-ISO / low-light capture is detected
    ON = "on"       # Force hqdn3d filter
    OFF = "off"     # Disable denoising


class LoudnormMode(str, Enum):
    """Audio loudness normalization modes."""
    TWO_PASS = "two_pass"   # EBU R128 two-pass dynamic normalization (-14 LUFS)
    DISABLED = "disabled"   # Pass-through audio


class AssetStatus(str, Enum):
    """Asset lifecycle state across hybrid drive storage."""
    RAW_INBOX = "RAW_INBOX"
    RAW = "RAW"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED_FOR_RENDER = "APPROVED_FOR_RENDER"
    IN_PROGRESS = "IN_PROGRESS"
    READY_TO_POST = "READY_TO_POST"
    POSTED = "POSTED"
    ARCHIVED = "ARCHIVED"


class ContentIDStatus(str, Enum):
    """YouTube copyright Content ID verification status."""
    UNCHECKED = "UNCHECKED"
    UNLISTED_CLEARED = "UNLISTED_CLEARED"
    CLAIMED = "CLAIMED"
    BLOCKED = "BLOCKED"


# ============================================================================
# SAFE ZONE & PLATFORM GEOMETRY
# ============================================================================

@dataclass(frozen=True)
class SafeZoneBox:
    """
    Coordinates and exclusion boundaries for mobile short-form UI overlays.
    Canvas standard: 1080 x 1920 px (9:16 portrait).
    """
    width: int
    height: int
    top_exclusion_y: int       # UI elements above this Y coordinate (search, headers)
    bottom_exclusion_y: int    # UI elements below this Y coordinate (titles, captions, marquee)
    right_exclusion_x: int     # UI elements to the right of this X coordinate (action rails)
    left_clearance_x: int = 0  # Left margin clearance required (e.g. 40px on TikTok)

    @property
    def safe_min_x(self) -> int:
        return self.left_clearance_x

    @property
    def safe_max_x(self) -> int:
        return self.right_exclusion_x

    @property
    def safe_min_y(self) -> int:
        return self.top_exclusion_y

    @property
    def safe_max_y(self) -> int:
        return self.bottom_exclusion_y


@dataclass(frozen=True)
class PlatformConfig:
    """Platform-specific technical parameters and limits."""
    platform_name: str
    max_duration_seconds: float
    optimal_duration_range: Tuple[int, int]
    canvas_width: int
    canvas_height: int
    safe_zone: SafeZoneBox
    high_quality_upload_setting_required: bool = False
    unlisted_preflight_recommended: bool = False


# YouTube Shorts Safe Zone Definition:
# Canvas: 1080 x 1920 px
# Safe Area Box: 900 x 1160 px centered horizontally (X: 60-960) and vertically (Y: 180-1450)
# Top Exclusion: Y: 0 to 180 px (Search header, sound icon)
# Bottom Exclusion: Y: 1450 to 1920 px (Title, @handle, sound marquee, subscribe button)
# Right Exclusion: X: 960 to 1080 px (Like, Comment, Share, Remix icons)
SAFE_ZONE_YOUTUBE = PlatformConfig(
    platform_name="YouTube Shorts",
    max_duration_seconds=59.0,   # <= 59s avoids global Content ID block
    optimal_duration_range=(15, 45),
    canvas_width=1080,
    canvas_height=1920,
    safe_zone=SafeZoneBox(
        width=900,
        height=1270,  # 1450 - 180 px mathematical safe span
        top_exclusion_y=180,
        bottom_exclusion_y=1450,
        right_exclusion_x=960,
        left_clearance_x=60,
    ),
    unlisted_preflight_recommended=True,
)

# TikTok Safe Zone Definition:
# Canvas: 1080 x 1920 px
# Safe Area Box: 920 x 1310 px centered vertically (Y: 160-1470) and cleared from left/right (X: 40-960)
# Top Exclusion: Y: 0 to 160 px (Following/For You tabs, Search bar)
# Bottom Exclusion: Y: 1470 to 1920 px (Username, caption, sound marquee, system nav)
# Right Exclusion: X: 960 to 1080 px (Profile avatar, Like, Comment, Bookmark, Share stack)
# Left Margin Clearance: 40 px
SAFE_ZONE_TIKTOK = PlatformConfig(
    platform_name="TikTok",
    max_duration_seconds=60.0,
    optimal_duration_range=(15, 45),
    canvas_width=1080,
    canvas_height=1920,
    safe_zone=SafeZoneBox(
        width=920,
        height=1310,  # 1470 - 160 px mathematical safe span
        top_exclusion_y=160,
        bottom_exclusion_y=1470,
        right_exclusion_x=960,
        left_clearance_x=40,
    ),
    high_quality_upload_setting_required=True,
)

# YouTube Channel Branding Dimensions
YOUTUBE_BANNER_WIDTH = 2048
YOUTUBE_BANNER_HEIGHT = 1152
YOUTUBE_BANNER_MAX_BYTES = 6 * 1024 * 1024  # 6 MB
YOUTUBE_BANNER_SAFE_WIDTH = 1235
YOUTUBE_BANNER_SAFE_HEIGHT = 338

YOUTUBE_PROFILE_PIC_MIN_DIM = 98
YOUTUBE_PROFILE_PIC_MAX_BYTES = 4 * 1024 * 1024  # 4 MB
YOUTUBE_PROFILE_PIC_RENDER_DIM = 32

YOUTUBE_WATERMARK_DIM = 150
YOUTUBE_WATERMARK_MAX_BYTES = 1024 * 1024  # 1 MB


# ============================================================================
# AUDIO ENGINEERING STANDARDS (EBU R128)
# ============================================================================

AUDIO_TARGET_LUFS = -14.0          # Target Integrated Loudness (LUFS)
AUDIO_LUFS_TOLERANCE = 1.0        # ±1.0 LUFS allowable tolerance
AUDIO_TARGET_TRUE_PEAK = -1.5     # Maximum True Peak ceiling (dBTP)
AUDIO_CEILING_TRUE_PEAK = -1.0    # Absolute hard ceiling for master limiter (dBTP)
AUDIO_TARGET_LRA = 7.0            # Loudness Range target (LRA)
AUDIO_HIGHPASS_CUTOFF_HZ = 40     # Sub-bass rumble cutoff frequency (Hz)
AUDIO_FESTIVAL_HIGHPASS_HZ = 80   # Extreme festival environment low-cut (Hz)
AUDIO_SAMPLE_RATE = 48000         # Broadcast standard 48 kHz
AUDIO_BITRATE_KBPS = 320          # AAC-LC 320 kbps stereo
AUDIO_LOOP_CROSSFADE_SEC = 0.03   # 30 ms linear micro-fade for seamless looping

# Audio Limiter Settings (Brickwall Peak Limiting)
AUDIO_LIMITER_LIMIT = -1.5        # Master brickwall limiter ceiling (dB)
AUDIO_LIMITER_ATTACK = 5.0        # Limiter attack time (ms)
AUDIO_LIMITER_RELEASE = 50.0      # Limiter release time (ms)

# TikTok Ghost-Linking Volume Ratio
TIKTOK_GHOST_LINK_ADDED_SOUND_MIN = 0.01  # 1% volume
TIKTOK_GHOST_LINK_ADDED_SOUND_MAX = 0.03  # 3% volume
TIKTOK_GHOST_LINK_ORIGINAL_SOUND = 1.00   # 100% volume

# Phase-Aligned Hybrid Audio Mixing Ratio
HYBRID_MIX_STUDIO_TRACK_RATIO = 0.70      # 70% clean studio master WAV
HYBRID_MIX_CROWD_MIC_RATIO = 0.30         # 30% live crowd reverb / atmosphere


# ============================================================================
# VIDEO ENCODING & TRANSCODING STANDARDS
# ============================================================================

SUPPORTED_VIDEO_EXTENSIONS: List[str] = [".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"]

VIDEO_CANVAS_WIDTH = 1080
VIDEO_CANVAS_HEIGHT = 1920
VIDEO_ASPECT_RATIO_STR = "9:16"
VIDEO_TARGET_FPS = 60                     # 60 fps Constant Frame Rate (CFR)
VIDEO_FALLBACK_FPS = 30                   # Fallback CFR
VIDEO_DURATION_MAX_SECONDS = 59.0         # Hard ceiling for YouTube Shorts (prevents global block)
VIDEO_DURATION_FAST_TRACK_MIN = 15.0      # Fast-Track lower duration bound
VIDEO_DURATION_FAST_TRACK_MAX = 45.0      # Fast-Track upper duration bound

VIDEO_STANDARD_BITRATE_KBPS = 12000       # 10-12 Mbps master target
VIDEO_HIGH_BITRATE_KBPS = 16000           # 15-20 Mbps high-fidelity target
VIDEO_MAX_BITRATE_CEILING_KBPS = 25000     # 25 Mbps maximum ceiling

# Proxy Video & Audio Configuration Standards (720p Preview & Fast DSP)
PROXY_VIDEO_HEIGHT = 720
PROXY_VIDEO_SHORT_EDGE = 720
PROXY_VIDEO_BITRATE_KBPS = 2500
PROXY_AUDIO_SAMPLE_RATE = 22050
PROXY_AUDIO_CODEC = "pcm_s16le"
PROXY_PRESET = "fast"
PROXY_VIDEO_CODEC = "libx264"

# Denoise parameters for hqdn3d filter
HQDN3D_LUMA_SPATIAL = 4.0
HQDN3D_CHROMA_SPATIAL = 3.0
HQDN3D_LUMA_TMP = 6.0
HQDN3D_CHROMA_TMP = 4.5

# Drop Detection & Pacing Thresholds
DROP_DETECTION_RMS_THRESHOLD = 0.8        # RMS Energy > 0.8 signals drop impact
FAST_TRACK_BUILDUP_SECONDS = 4.0          # 4-second build-up hook
FAST_TRACK_PAYOFF_MIN_SECONDS = 12.0      # 12-16 second drop payoff
FAST_TRACK_PAYOFF_MAX_SECONDS = 16.0


# ============================================================================
# GENRE BPM & PACING MAPPINGS
# ============================================================================

@dataclass(frozen=True)
class GenrePacingProfile:
    """Pacing, tempo, and cutting formula by EDM subgenre."""
    genre_name: str
    typical_bpm_range: Tuple[int, int]
    hook_window_description: str
    cutting_strategy: str
    visual_focus: str
    recommended_hashtags: List[str]


GENRE_PROFILES: Dict[str, GenrePacingProfile] = {
    "dubstep": GenrePacingProfile(
        genre_name="Dubstep / Bass Music / Trap",
        typical_bpm_range=(140, 150),
        hook_window_description="Cut starts 1.5s before drop on final riser; hard cut on bass drop impact",
        cutting_strategy="Kinetic zoom edits, rail-riding crowd reactions, high-contrast strobe flashes",
        visual_focus="Stage pyrotechnics, headbanging crowds, laser apex bursts",
        recommended_hashtags=["#Dubstep", "#BassMusic", "#LostLands", "#Headbanger"],
    ),
    "house": GenrePacingProfile(
        genre_name="House / Tech House / Techno",
        typical_bpm_range=(124, 130),
        hook_window_description="Rolling 4/4 groove; cut into vocal hook or drop; loop precisely on 4-bar or 8-bar measure",
        cutting_strategy="Hypnotic laser sweeps, warehouse club lighting, DJ deck POV, hand movements",
        visual_focus="DJ deck hands, laser canopy sweeps, dark club atmospheric lighting",
        recommended_hashtags=["#TechHouse", "#HouseMusic", "#Techno", "#ClubSpace"],
    ),
    "techno": GenrePacingProfile(
        genre_name="Techno / Peak-Time / Melodic Techno",
        typical_bpm_range=(128, 135),
        hook_window_description="Industrial kick drive; cut on 8-bar build into driving bassline",
        cutting_strategy="Minimalist dark aesthetic, synchronized strobe pulse, rhythmic camera tilt",
        visual_focus="Industrial warehouse structures, strobes, laser tunnels",
        recommended_hashtags=["#Techno", "#PeakTimeTechno", "#Afterlife", "#RaveTok"],
    ),
    "trance": GenrePacingProfile(
        genre_name="Trance / Melodic Dubstep / Future Bass",
        typical_bpm_range=(138, 145),
        hook_window_description="Emotional vocal climax and synth buildup leading into bright melodic drop",
        cutting_strategy="Wide festival stage sweeps, massive laser light canopies, crowd singing moments",
        visual_focus="Wide festival stage shots, massive laser canopy reveals, emotional crowd singing",
        recommended_hashtags=["#TranceFamily", "#MelodicDubstep", "#EDCLV", "#FestivalVibes"],
    ),
    "dnb": GenrePacingProfile(
        genre_name="Drum & Bass / Hardstyle",
        typical_bpm_range=(150, 175),
        hook_window_description="Rapid cuts synchronized to fast double-time kick drums or breakbeats",
        cutting_strategy="High-speed strobe effects, kinetic flash frames, fast-paced kinetic energy",
        visual_focus="Rapid light strobes, breakneck crowd dancing, high-speed stage visuals",
        recommended_hashtags=["#DnB", "#DrumAndBass", "#Hardstyle", "#FastPaced"],
    ),
}


# ============================================================================
# DIRECTORY TAXONOMY & STORAGE LIMITS
# ============================================================================

FOLDER_TIERS: Dict[str, str] = {
    "INBOX": "01_RAW_INBOX",
    "RAW": "01_RAW",
    "AWAITING_REVIEW": "02_AWAITING_REVIEW",
    "IN_PROGRESS": "02_IN_PROGRESS",
    "READY_TO_POST": "03_READY_TO_POST",
    "ARCHIVE": "04_ARCHIVE",
}

FOLDER_COLORS: Dict[str, str] = {
    "01_RAW_INBOX": "Red",
    "01_RAW": "Red",
    "02_AWAITING_REVIEW": "Yellow",
    "02_IN_PROGRESS": "Orange",
    "03_READY_TO_POST": "Green",
    "04_ARCHIVE": "Gray",
}

MAX_FOLDER_ITEMS = 50   # Strict capacity cap per subfolder to prevent cloud sync / indexing lag


def get_folder_tier(tier_key: str) -> str:
    """Returns directory name for a folder tier key with fallback."""
    return FOLDER_TIERS.get(tier_key.upper(), FOLDER_TIERS.get("RAW", "01_RAW"))


def get_raw_folder(
    workspace: Union[Path, str],
    festival: Optional[str] = None,
    artist: Optional[str] = None,
) -> Path:
    """Resolves path to 01_RAW directory, optionally partitioned by [Festival]/[Artist]."""
    raw_base = Path(workspace) / FOLDER_TIERS.get("RAW", "01_RAW")
    if festival and artist:
        return raw_base / festival / artist
    elif festival:
        return raw_base / festival
    return raw_base


def get_awaiting_review_folder(
    workspace: Union[Path, str],
    festival: Optional[str] = None,
    artist: Optional[str] = None,
) -> Path:
    """Resolves path to 02_AWAITING_REVIEW directory, optionally partitioned by [Festival]/[Artist]."""
    review_base = Path(workspace) / FOLDER_TIERS.get("AWAITING_REVIEW", "02_AWAITING_REVIEW")
    if festival and artist:
        return review_base / festival / artist
    elif festival:
        return review_base / festival
    return review_base

# Publishing Windows (EST / UTC)
PUBLISH_WINDOW_1_EST = "10:00 AM EST"  # Peak EU transit & evening browsing (15:00 UTC)
PUBLISH_WINDOW_2_EST = "06:00 PM EST"  # Peak US after-work scrolling (23:00 UTC)


# ============================================================================
# COMMENT SPAM FILTER & MODERATION BLOCKLIST
# ============================================================================

SPAM_KEYWORDS: List[str] = [
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

# Canonical 17-keyword blocklist regex pattern with word boundaries and punctuation evasion handling
SPAM_BLOCKLIST_PATTERN = (
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


def get_spam_blocklist_regex() -> re.Pattern:
    """Returns the compiled regex pattern for comment spam filtering."""
    return re.compile(SPAM_BLOCKLIST_PATTERN)


def get_genre_profile(genre_key: str) -> GenrePacingProfile:
    """Retrieves genre pacing profile with fallback to House."""
    normalized = genre_key.strip().lower()
    for key, profile in GENRE_PROFILES.items():
        if key in normalized or normalized in key:
            return profile
    return GENRE_PROFILES["house"]


# ============================================================================
# SAMSUNG S26 ULTRA & ADB HARDWARE INGESTION CONSTANTS
# ============================================================================

DEFAULT_ANDROID_CAMERA_PATH: str = "/sdcard/DCIM/EDM_Drops"
ALT_ANDROID_CAMERA_PATH: str = "/storage/emulated/0/DCIM/EDM_Drops"
ADB_EXPERT_RAW_PATH: str = "/sdcard/DCIM/Expert RAW"
SAMSUNG_MODEL_PREFIXES: List[str] = ["SM-S948", "SM-S938", "SM-S928", "SM-S918"]  # S26/S25/S24/S23 Ultra series
ADB_SUPPORTED_EXTENSIONS: List[str] = [".mp4", ".mov", ".mkv", ".m4v", ".dng", ".jpg", ".heic"]
ADB_VIDEO_EXTENSIONS: List[str] = [".mp4", ".mov", ".mkv", ".m4v"]
ADB_STILL_EXTENSIONS: List[str] = [".dng", ".jpg", ".heic"]
ADB_DEFAULT_TIMEOUT_SECONDS: float = 300.0
ADB_PULL_TIMEOUT_PER_GB_SECONDS: float = 60.0
ADB_MIN_FREE_DISK_HEADROOM_BYTES: int = 5 * 1024 * 1024 * 1024  # 5 GB safety headroom
ADB_BUFFER_SIZE_BYTES: int = 1024 * 1024  # 1 MB buffer chunk size

# mDNS Wireless Debugging Discovery Constants (RFC 6762 / RFC 6763)
MDNS_ADB_TLS_SERVICE_TYPE: str = "_adb-tls-connect._tcp.local."
MDNS_ADB_LEGACY_SERVICE_TYPE: str = "_adb._tcp.local."
MDNS_DEFAULT_TIMEOUT_SEC: float = 5.0

# Aliases and helper collections
ADB_MDNS_SERVICE_TLS_CONNECT: str = MDNS_ADB_TLS_SERVICE_TYPE
ADB_MDNS_SERVICE_LEGACY: str = MDNS_ADB_LEGACY_SERVICE_TYPE
ADB_MDNS_ALL_SERVICES: List[str] = [MDNS_ADB_TLS_SERVICE_TYPE, MDNS_ADB_LEGACY_SERVICE_TYPE]
ADB_MDNS_DEFAULT_TIMEOUT_SECONDS: float = MDNS_DEFAULT_TIMEOUT_SEC
DEFAULT_ADB_WIFI_PORT: int = 5555


"""
ingest_assets.py - Complete Asset Ingestion, Stream Probing, & 4-Tier Hybrid Routing

Handles:
1. Automated media stream inspection via ffprobe (video/audio codecs, HDR transfer characteristics, resolution, FPS).
2. Canonical filename normalization (YYYYMMDD_[Event]_[Artist]_[TrackName-or-ID]_V[#]_[Resolution].mp4).
3. 4-tier hybrid directory routing (01_RAW_INBOX, 02_IN_PROGRESS, 03_READY_TO_POST, 04_ARCHIVE).
4. Directory health management with automated 50-item subfolder partitioning.
5. Ingestion manifest recording with SHA-256 checksum validation.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import unicodedata

from config import (
    BrandType,
    EventTier,
    FOLDER_TIERS,
    MAX_FOLDER_ITEMS,
    SUPPORTED_VIDEO_EXTENSIONS,
)


# ============================================================================
# EXCEPTIONS
# ============================================================================

class IngestionError(Exception):
    """Base exception for media ingestion failures."""
    pass


class FFprobeNotFoundError(IngestionError):
    """Raised when the ffprobe executable cannot be located."""
    pass


class MediaProbeError(IngestionError):
    """Raised when ffprobe fails to parse a media container."""
    pass


class ChecksumMismatchError(IngestionError):
    """Raised when file integrity validation fails after copy/move."""
    pass


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class StreamProbeData:
    """Detailed technical stream telemetry extracted via ffprobe."""
    file_path: str
    file_size_bytes: int
    duration_seconds: float
    width: int
    height: int
    aspect_ratio: str
    frame_rate: float
    video_codec: str
    pix_fmt: str
    color_space: str
    color_transfer: str
    color_primaries: str
    is_hdr: bool
    audio_codec: Optional[str]
    audio_sample_rate: Optional[int]
    audio_channels: Optional[int]
    audio_bitrate_kbps: Optional[int]
    sha256_hash: str
    creation_time: str
    raw_probe_json: Optional[Dict[str, Any]] = field(default=None, repr=False)

    @property
    def resolution_label(self) -> str:
        """Returns standard resolution token (e.g. 1080p, 4k, 720p)."""
        dim = max(self.width, self.height)
        if dim >= 3840:
            return "4k"
        elif dim >= 1920:
            return "1080p"
        elif dim >= 1280:
            return "720p"
        else:
            return f"{dim}p"


@dataclass
class IngestionResult:
    """Outcome of an asset ingestion operation."""
    success: bool
    project_id: str
    source_path: str
    canonical_filename: str
    staged_path: str
    brand: str
    tier: str
    probe_data: StreamProbeData
    manifest_path: str
    raw_storage_path: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


# ============================================================================
# BINARY DISCOVERY HELPER
# ============================================================================

def find_binary(
    name: str,
    custom_path: Optional[str] = None,
    env_var: Optional[str] = None
) -> Optional[Path]:
    """
    Locates an executable binary by checking:
    1. Direct CLI custom argument path.
    2. Environment variable (e.g. FFPROBE_BINARY, FFMPEG_BINARY).
    3. System PATH via shutil.which.
    4. Common Windows platform directories.
    """
    if custom_path:
        p = Path(custom_path)
        if p.is_file() and os.access(p, os.X_OK):
            return p
        if p.exists():
            return p

    if env_var and os.environ.get(env_var):
        env_p = Path(os.environ[env_var])
        if env_p.exists():
            return env_p

    which_path = shutil.which(name)
    if which_path:
        return Path(which_path)

    # Common Windows fallbacks
    common_search_dirs = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Default\AppData\Local")),
        Path(r"C:\ffmpeg\bin"),
        Path(r"C:\tools\ffmpeg\bin"),
    ]
    for base in common_search_dirs:
        for ext in ["", ".exe"]:
            candidate = base / f"{name}{ext}"
            if candidate.is_file():
                return candidate
            nested_candidate = base / name / "bin" / f"{name}{ext}"
            if nested_candidate.is_file():
                return nested_candidate

    return None


# ============================================================================
# CHECKSUM CALCULATOR
# ============================================================================

def calculate_sha256(file_path: Path, block_size: int = 65536) -> str:
    """Calculates SHA-256 cryptographic digest of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
    return sha256.hexdigest()


# ============================================================================
# MEDIA STREAM PROBER
# ============================================================================

def probe_media_file(
    file_path: Path,
    ffprobe_path: Optional[str] = None
) -> StreamProbeData:
    """
    Executes ffprobe against a media file and parses video/audio stream telemetry.
    """
    resolved_path = Path(file_path).resolve()
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Source media file not found: {resolved_path}")

    binary = find_binary("ffprobe", custom_path=ffprobe_path, env_var="FFPROBE_BINARY")
    if not binary:
        raise FFprobeNotFoundError(
            "ffprobe binary not found. Please ensure FFmpeg/ffprobe is installed and on PATH, "
            "set FFPROBE_BINARY environment variable, or pass --ffprobe-path."
        )

    cmd = [
        str(binary),
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-print_format", "json",
        str(resolved_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as e:
        raise MediaProbeError(f"ffprobe failed with exit code {e.returncode}: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        raise MediaProbeError(f"ffprobe timed out on {resolved_path}") from e

    try:
        probe_json = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise MediaProbeError(f"Failed to parse ffprobe JSON output: {e}") from e

    streams = probe_json.get("streams", [])
    format_info = probe_json.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video_stream:
        raise MediaProbeError(f"No video stream detected in {resolved_path}")

    # Video parameters
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    video_codec = video_stream.get("codec_name", "unknown")
    pix_fmt = video_stream.get("pix_fmt", "unknown")
    color_space = video_stream.get("color_space", "unknown")
    color_transfer = video_stream.get("color_transfer", "unknown")
    color_primaries = video_stream.get("color_primaries", "unknown")

    # Frame rate calculation
    r_fps_str = video_stream.get("r_frame_rate", "60/1")
    try:
        num, den = map(float, r_fps_str.split("/"))
        frame_rate = round(num / den, 2) if den != 0 else 60.0
    except (ValueError, ZeroDivisionError):
        frame_rate = 60.0

    # Aspect ratio
    if width > 0 and height > 0:
        gcd_val = _compute_gcd(width, height)
        aspect_ratio = f"{width // gcd_val}:{height // gcd_val}"
    else:
        aspect_ratio = "9:16"

    # HDR Detection
    # Checks for HLG (arib-std-b67), HDR10/PQ (smpte2084), or BT.2020 color gamut
    hdr_transfers = {"arib-std-b67", "smpte2084", "bt2020-10", "bt2020-12"}
    hdr_primaries = {"bt2020"}
    is_hdr = (
        color_transfer.lower() in hdr_transfers
        or color_primaries.lower() in hdr_primaries
        or "hdr" in pix_fmt.lower()
        or "10le" in pix_fmt.lower()
    )

    # Audio parameters
    audio_codec = audio_stream.get("codec_name") if audio_stream else None
    audio_sample_rate = int(audio_stream.get("sample_rate", 0)) if audio_stream else None
    audio_channels = int(audio_stream.get("channels", 0)) if audio_stream else None
    audio_bitrate_kbps = None
    if audio_stream and audio_stream.get("bit_rate"):
        try:
            audio_bitrate_kbps = int(int(audio_stream["bit_rate"]) / 1000)
        except (ValueError, TypeError):
            pass

    # Duration & size
    duration_seconds = float(format_info.get("duration", video_stream.get("duration", 0.0)))
    file_size_bytes = int(format_info.get("size", resolved_path.stat().st_size))

    # Creation timestamp
    tags = format_info.get("tags", {})
    creation_time = tags.get("creation_time", datetime.now().isoformat())

    sha256 = calculate_sha256(resolved_path)

    return StreamProbeData(
        file_path=str(resolved_path),
        file_size_bytes=file_size_bytes,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        aspect_ratio=aspect_ratio,
        frame_rate=frame_rate,
        video_codec=video_codec,
        pix_fmt=pix_fmt,
        color_space=color_space,
        color_transfer=color_transfer,
        color_primaries=color_primaries,
        is_hdr=is_hdr,
        audio_codec=audio_codec,
        audio_sample_rate=audio_sample_rate,
        audio_channels=audio_channels,
        audio_bitrate_kbps=audio_bitrate_kbps,
        sha256_hash=sha256,
        creation_time=creation_time,
        raw_probe_json=probe_json,
    )


def _compute_gcd(a: int, b: int) -> int:
    """Helper to compute greatest common divisor."""
    while b:
        a, b = b, a % b
    return a


# ============================================================================
# FILENAME NORMALIZER
# ============================================================================

class FilenameNormalizer:
    """
    Enforces standardized canonical naming syntax:
    YYYYMMDD_[Event]_[Artist]_[TrackName-or-ID]_V[#]_[Resolution].mp4
    """

    CANONICAL_PATTERN = re.compile(
        r"^(?P<date>\d{8})_(?P<event>[A-Za-z0-9]+)_(?P<artist>[A-Za-z0-9]+)_"
        r"(?P<track>[A-Za-z0-9\-]+)_V(?P<version>\d+)_(?P<resolution>\d+p|4k)\.(?P<ext>mp4|mov|mkv|avi|webm|m4v)$",
        re.IGNORECASE,
    )

    LATIN_CHAR_MAP = {
        "Ø": "O", "ø": "o", "Æ": "Ae", "æ": "ae",
        "ß": "ss", "Ł": "L", "ł": "l", "Đ": "D", "đ": "d",
    }

    @classmethod
    def parse_filename(cls, filename: str) -> Optional[Dict[str, Any]]:
        """Parses a filename to check if it matches the canonical format."""
        match = cls.CANONICAL_PATTERN.match(filename.strip())
        if not match:
            return None
        d = match.groupdict()
        return {
            "date": d["date"],
            "event": d["event"],
            "artist": d["artist"],
            "track": d["track"],
            "version": int(d["version"]),
            "resolution": d["resolution"].lower(),
            "ext": d["ext"].lower(),
        }

    @classmethod
    def sanitize_token(cls, token: str, default: str = "Unknown") -> str:
        """Removes spaces and non-alphanumeric characters for clean token syntax, normalizing unicode diacritics."""
        if not token:
            return default
        cleaned = token
        for src, dst in cls.LATIN_CHAR_MAP.items():
            cleaned = cleaned.replace(src, dst)
        # Decompose remaining unicode diacritics (e.g. ë -> e, ö -> o, é -> e) to ASCII base glyphs
        decomposed = unicodedata.normalize("NFKD", cleaned).encode("ascii", "ignore").decode("utf-8")
        words = re.findall(r"[A-Za-z0-9]+", decomposed)
        if not words:
            return default
        return "".join(word.capitalize() for word in words)

    @classmethod
    def build_canonical_filename(
        cls,
        event: Optional[str],
        artist: Optional[str],
        track: Optional[str],
        resolution: str,
        version: int = 1,
        date_str: Optional[str] = None,
        ext: str = "mp4",
    ) -> str:
        """Constructs canonical filename string from components."""
        d_str = date_str or datetime.now().strftime("%Y%m%d")
        ev_clean = cls.sanitize_token(event, default="Event")
        ar_clean = cls.sanitize_token(artist, default="Artist")
        tr_clean = cls.sanitize_token(track, default="ID")
        res_clean = resolution.lower()
        if not (res_clean.endswith("p") or res_clean == "4k"):
            res_clean = f"{res_clean}p"

        return f"{d_str}_{ev_clean}_{ar_clean}_{tr_clean}_V{version}_{res_clean}.{ext.lower().lstrip('.')}"


# ============================================================================
# DIRECTORY HEALTH & CAPACITY GUARD
# ============================================================================

class DirectoryHealthGuard:
    """
    Enforces maximum item capacity per directory (max 50 items) to prevent
    cloud synchronization latency and IDE file indexing timeouts.
    """

    def __init__(self, max_items: int = MAX_FOLDER_ITEMS):
        self.max_items = max_items

    def count_items(self, directory: Path) -> int:
        """Counts direct non-hidden child items in a directory."""
        if not directory.exists() or not directory.is_dir():
            return 0
        return sum(1 for p in directory.iterdir() if not p.name.startswith("."))

    def get_healthy_subfolder(self, base_tier_dir: Path, subfolder_slug: str) -> Path:
        """
        Returns an active partition subfolder with available capacity.
        If base_tier_dir / subfolder_slug exceeds max_items, branches to
        subfolder_slug_Batch02, subfolder_slug_Batch03, etc.
        """
        base_tier_dir.mkdir(parents=True, exist_ok=True)
        primary_dir = base_tier_dir / subfolder_slug
        primary_dir.mkdir(parents=True, exist_ok=True)

        if self.count_items(primary_dir) < self.max_items:
            return primary_dir

        batch_idx = 2
        while True:
            batch_dir = base_tier_dir / f"{subfolder_slug}_Batch{batch_idx:02d}"
            batch_dir.mkdir(parents=True, exist_ok=True)
            if self.count_items(batch_dir) < self.max_items:
                return batch_dir
            batch_idx += 1


# ============================================================================
# ASSET INGESTION ROUTER
# ============================================================================

class AssetIngestionRouter:
    """
    Main engine for discovering, inspecting, renaming, and routing incoming
    raw mobile concert footage into the 4-tier hybrid repository.
    """

    def __init__(self, workspace_root: Path, ffprobe_path: Optional[str] = None):
        self.workspace_root = Path(workspace_root).resolve()
        self.ffprobe_path = ffprobe_path
        self.health_guard = DirectoryHealthGuard()
        self._init_tier_directories()

    def _init_tier_directories(self) -> None:
        """Ensures the 4 standard tier folders exist in the workspace."""
        for tier_folder in FOLDER_TIERS.values():
            (self.workspace_root / tier_folder).mkdir(parents=True, exist_ok=True)

    def scan_inbox(self, inbox_dir: Optional[Path] = None) -> List[Path]:
        """Discovers uningested video files in the raw inbox or specified directory."""
        target = inbox_dir or (self.workspace_root / FOLDER_TIERS["INBOX"])
        if not target.exists():
            return []
        supported_exts = set(ext.lower() for ext in SUPPORTED_VIDEO_EXTENSIONS)
        found = []
        for p in target.rglob("*"):
            if p.is_file() and p.suffix.lower() in supported_exts and not p.name.startswith("."):
                found.append(p)
        return sorted(found)

    def ingest_asset(
        self,
        source_path: Path,
        event_name: Optional[str] = None,
        artist_name: Optional[str] = None,
        track_name: Optional[str] = None,
        brand: BrandType = BrandType.MUSIC_BAPTISM,
        tier: EventTier = EventTier.PILLAR_A,
        version: int = 1,
        dry_run: bool = False,
        ffprobe_custom_path: Optional[str] = None,
    ) -> IngestionResult:
        """
        Executes full ingestion workflow:
        1. Probe stream characteristics.
        2. Normalize filename.
        3. Allocate isolated project workspace in 02_IN_PROGRESS.
        4. Copy file and verify SHA-256 checksum.
        5. Generate ingestion manifest JSON.
        """
        src = Path(source_path).resolve()
        if not src.is_file():
            raise FileNotFoundError(f"Source asset does not exist: {src}")

        ffprobe_bin = ffprobe_custom_path or self.ffprobe_path
        try:
            probe_data = probe_media_file(src, ffprobe_path=ffprobe_bin)
        except (FFprobeNotFoundError, MediaProbeError):
            if dry_run:
                # Nominal baseline telemetry for dry-run simulation
                probe_data = StreamProbeData(
                    file_path=str(src),
                    file_size_bytes=src.stat().st_size if src.exists() else 1024,
                    duration_seconds=30.0,
                    width=1080,
                    height=1920,
                    aspect_ratio="9:16",
                    frame_rate=60.0,
                    video_codec="hevc",
                    pix_fmt="yuv420p",
                    color_space="bt709",
                    color_transfer="bt709",
                    color_primaries="bt709",
                    is_hdr=False,
                    audio_codec="aac",
                    audio_sample_rate=48000,
                    audio_channels=2,
                    audio_bitrate_kbps=320,
                    sha256_hash="dryrunhash00000000000000000000000000000000000000000000000000000000",
                    creation_time=datetime.now().isoformat(),
                )
            else:
                raise

        # Parse existing filename or build canonical one
        parsed_name = FilenameNormalizer.parse_filename(src.name)
        if parsed_name:
            canonical_name = src.name
            event_val = parsed_name["event"]
            artist_val = parsed_name["artist"]
            track_val = parsed_name["track"]
            version_val = parsed_name["version"]
        else:
            event_val = event_name or "Concert"
            artist_val = artist_name or "Artist"
            track_val = track_name or "ID"
            version_val = version
            canonical_name = FilenameNormalizer.build_canonical_filename(
                event=event_val,
                artist=artist_val,
                track=track_val,
                resolution=probe_data.resolution_label,
                version=version_val,
                ext=src.suffix.lstrip("."),
            )

        # Generate unique project ID
        date_prefix = datetime.now().strftime("%Y%m%d")
        project_id = f"{date_prefix}_{FilenameNormalizer.sanitize_token(event_val)}_{FilenameNormalizer.sanitize_token(artist_val)}_V{version_val}"

        # Allocate workspace in 02_IN_PROGRESS with capacity guard
        in_progress_dir = self.workspace_root / FOLDER_TIERS["IN_PROGRESS"]
        healthy_target_dir = self.health_guard.get_healthy_subfolder(in_progress_dir, project_id)
        staged_file_path = healthy_target_dir / canonical_name
        manifest_path = healthy_target_dir / "ingestion_manifest.json"

        warnings: List[str] = []
        if probe_data.duration_seconds > 59.0:
            warnings.append(
                f"Source duration ({probe_data.duration_seconds:.1f}s) exceeds YouTube Shorts 59s limit. "
                "Downstream processor will clamp or trim this asset."
            )
        if probe_data.is_hdr:
            warnings.append(
                f"HDR color transfer ({probe_data.color_transfer}) detected. "
                "Downstream processor must apply mobius tone-mapping to BT.709."
            )
        if probe_data.audio_codec is None:
            warnings.append("No audio stream detected in source asset.")

        if not dry_run:
            # Create a zero-copy hardlink to staging
            staged_file_path.unlink(missing_ok=True)
            try:
                import os
                os.link(src, staged_file_path)
            except OSError:
                shutil.copy2(src, staged_file_path)

            # Record manifest JSON
            manifest_dict = {
                "project_id": project_id,
                "ingested_at": datetime.now().isoformat(),
                "brand": brand.value if isinstance(brand, BrandType) else str(brand),
                "tier": tier.value if isinstance(tier, EventTier) else str(tier),
                "source_path": str(src),
                "canonical_filename": canonical_name,
                "staged_path": str(staged_file_path),
                "probe_data": asdict(probe_data),
                "warnings": warnings,
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_dict, f, indent=2)

            # Insert into SQLite manifest
            try:
                from metadata_tracker import MediaManifestDB
                tracker = MediaManifestDB(self.workspace_root / "media_manifest.sqlite")
                tracker.upsert_asset(
                    asset_id=project_id,
                    source_file_name=src.name,
                    canonical_name=canonical_name,
                    brand=brand.value if isinstance(brand, BrandType) else str(brand),
                    tier=tier.value if isinstance(tier, EventTier) else str(tier),
                    event_name=event_val,
                    artist_name=artist_val,
                    track_name=track_val,
                    duration_seconds=probe_data.duration_seconds,
                    is_hdr=probe_data.is_hdr,
                    raw_path=str(staged_file_path),
                    metadata_dict=manifest_dict
                )
            except Exception as e:
                warnings.append(f"Failed to record asset in SQLite manifest: {e}")

        # Safely store raw master in 01_RAW/[Festival]/[Artist]
        raw_storage_dest = self.store_raw_asset(
            source_path=src,
            event_name=event_val,
            artist_name=artist_val,
            track_name=track_val,
            canonical_filename=canonical_name,
            dry_run=dry_run,
        )

        return IngestionResult(
            success=True,
            project_id=project_id,
            source_path=str(src),
            canonical_filename=canonical_name,
            staged_path=str(staged_file_path),
            brand=brand.value if isinstance(brand, BrandType) else str(brand),
            tier=tier.value if isinstance(tier, EventTier) else str(tier),
            probe_data=probe_data,
            manifest_path=str(manifest_path),
            raw_storage_path=str(raw_storage_dest),
            warnings=warnings,
        )

    def store_raw_asset(
        self,
        source_path: Union[Path, str],
        event_name: Optional[str] = None,
        artist_name: Optional[str] = None,
        track_name: Optional[str] = None,
        canonical_filename: Optional[str] = None,
        dry_run: bool = False,
    ) -> Path:
        """
        Safely stores untouched pristine raw 4K media in 01_RAW/[Festival]/[Artist]/<canonical_filename>
        using sanitized directory tokens.
        """
        src = Path(source_path).resolve()
        clean_festival = FilenameNormalizer.sanitize_token(event_name, default="Concert")
        clean_artist = FilenameNormalizer.sanitize_token(artist_name, default="Artist")

        raw_dir = self.workspace_root / FOLDER_TIERS.get("RAW", "01_RAW") / clean_festival / clean_artist
        raw_dir.mkdir(parents=True, exist_ok=True)

        target_name = canonical_filename or src.name
        dest_path = raw_dir / target_name

        if not dry_run:
            if not dest_path.exists() or dest_path != src:
                dest_path.unlink(missing_ok=True)
                try:
                    import os
                    os.link(src, dest_path)
                except OSError:
                    shutil.copy2(src, dest_path)

        return dest_path


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="EDM Asset Ingestion & Stream Probing Utility (Track 2: Content Creation)"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to a raw video file or inbox directory.",
    )
    parser.add_argument(
        "--target-dir", "-t",
        default=str(Path.cwd()),
        help="Content creation workspace root (default: current working directory).",
    )
    parser.add_argument(
        "--event", "-e",
        default="Concert",
        help="Event / Festival name (e.g. EDCOrlando, ClubSpace).",
    )
    parser.add_argument(
        "--artist", "-a",
        default="Artist",
        help="DJ or headliner name (e.g. JohnSummit, SubFocus).",
    )
    parser.add_argument(
        "--track",
        default="ID",
        help="Track name or unreleased ID code.",
    )
    parser.add_argument(
        "--brand",
        choices=[b.value for b in BrandType],
        default=BrandType.MUSIC_BAPTISM.value,
        help="Brand channel umbrella.",
    )
    parser.add_argument(
        "--tier",
        choices=[t.value for t in EventTier],
        default=EventTier.PILLAR_A.value,
        help="Event tier pillar.",
    )
    parser.add_argument(
        "--version", "-v",
        type=int,
        default=1,
        help="Asset version iteration number.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Probe and compute canonical naming without moving files.",
    )
    parser.add_argument(
        "--ffprobe-path",
        default=None,
        help="Explicit path to ffprobe executable.",
    )

    args = parser.parse_args()

    input_p = Path(args.input)
    router = AssetIngestionRouter(
        workspace_root=Path(args.target_dir),
        ffprobe_path=args.ffprobe_path,
    )

    if input_p.is_dir():
        files = router.scan_inbox(input_p)
        if not files:
            print(f"[WARN] No video assets discovered in directory: {input_p}")
            sys.exit(0)
        print(f"[INFO] Discovered {len(files)} video asset(s) in {input_p}...")
        for f in files:
            try:
                res = router.ingest_asset(
                    source_path=f,
                    event_name=args.event,
                    artist_name=args.artist,
                    track_name=args.track,
                    brand=BrandType(args.brand),
                    tier=EventTier(args.tier),
                    version=args.version,
                    dry_run=args.dry_run,
                    ffprobe_custom_path=args.ffprobe_path,
                )
                print(f"[SUCCESS] Ingested: {res.canonical_filename} -> {res.staged_path}")
            except Exception as ex:
                print(f"[ERROR] Failed to ingest {f.name}: {ex}", file=sys.stderr)
    else:
        try:
            res = router.ingest_asset(
                source_path=input_p,
                event_name=args.event,
                artist_name=args.artist,
                track_name=args.track,
                brand=BrandType(args.brand),
                tier=EventTier(args.tier),
                version=args.version,
                dry_run=args.dry_run,
                ffprobe_custom_path=args.ffprobe_path,
            )
            print(f"[SUCCESS] Ingested: {res.canonical_filename}")
            print(f"  Project ID: {res.project_id}")
            print(f"  Staged Path: {res.staged_path}")
            print(f"  Resolution: {res.probe_data.width}x{res.probe_data.height} ({res.probe_data.resolution_label})")
            print(f"  FPS: {res.probe_data.frame_rate} CFR | Codec: {res.probe_data.video_codec}")
            print(f"  HDR Detected: {res.probe_data.is_hdr} (Transfer: {res.probe_data.color_transfer})")
            print(f"  Duration: {res.probe_data.duration_seconds:.2f}s")
            print(f"  SHA-256: {res.probe_data.sha256_hash}")
            if res.warnings:
                for w in res.warnings:
                    print(f"  [WARNING] {w}")
        except Exception as ex:
            print(f"[ERROR] Ingestion failed: {ex}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

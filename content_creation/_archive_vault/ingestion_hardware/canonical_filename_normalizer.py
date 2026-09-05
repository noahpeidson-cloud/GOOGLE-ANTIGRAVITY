r"""
================================================================================
Name: Canonical Filename Normalizer & Directory Health Guard
Context Mapping: Extracted from `content_creation/ingest_assets.py:331-443`.
                 Standardizes messy mobile, camera, and DJ track names into
                 clean, uniform, cross-platform media assets and enforces
                 directory health capacity boundaries (max 50 items) across
                 Google Drive and Windows NTFS filesystems.
Strengths:
  - Canonical Filename Syntax Enforcement:
    * Standardizes media filenames to the industry-proven schema:
      `YYYYMMDD_[Event]_[Artist]_[TrackName-or-ID]_V[#]_[Resolution].mp4`
    * Provides regex matching and token breakdown into structured metadata.
  - European DJ Latin Transliteration & NFKD Diacritic Decomposition:
    * Accurately maps European DJ and producer stage names (`Ø -> O`, `ø -> o`,
      `Æ -> Ae`, `æ -> ae`, `ß -> ss`, `Ł -> L`, `ł -> l`, `Đ -> D`, `đ -> d`).
    * Employs `unicodedata.normalize("NFKD", ...)` to strip combining diacritics
      (`ë -> e`, `ö -> o`, `é -> e`, `ñ -> n`), producing clean, robust ASCII
      tokens that eliminate filesystem corruption and shell interpolation errors.
    * Strips illegal OS filesystem characters (`< > : " / \ | ? *` and control chars).
  - DirectoryHealthGuard (NTFS & Cloud Sync Optimization):
    * Enforces a strict 50-item threshold per directory.
    * Automatically partitions overflowing folders into sequential batch subfolders
      (`_Batch02`, `_Batch03`, etc.), preventing NTFS directory enumeration stalls,
      Google Drive Desktop sync deadlocks, and IDE indexing latency spikes.

Weaknesses:
  - Transliteration strips non-Latin scripts (e.g., Cyrillic, Kanji, Arabic) down
    to phonetic or fallback tokens unless a dedicated multilingual transliterator
    is installed.
  - Directory partitioning creates multiple subfolders which downstream consumer
    scripts must traverse or query via indexed SQLite manifest databases rather
    than single flat folder scans.

Implementation Instructions:
  1. Sanitize individual tokens:
     `clean_artist = FilenameNormalizer.sanitize_token("Møme & Kölsch")` -> `"MomeKolsch"`
  2. Build canonical filename:
     `fname = FilenameNormalizer.build_canonical_filename(event="EDCLV", artist="Kölsch", track="Grey", resolution="4k")`
  3. Route through DirectoryHealthGuard:
     `guard = DirectoryHealthGuard(max_items=50)`
     `healthy_dir = guard.get_healthy_subfolder(base_tier_dir=Path("01_RAW"), subfolder_slug="Festival_Takes")`
================================================================================
"""

from __future__ import annotations

import os
import re
import shutil
import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("CanonicalFilenameNormalizer")

MAX_FOLDER_ITEMS: int = 50


# ============================================================================
# CANONICAL FILENAME NORMALIZATION & TOKEN SANITIZER
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

    # European DJ & Producer character transliteration map
    LATIN_CHAR_MAP = {
        "Ø": "O", "ø": "o",
        "Æ": "Ae", "æ": "ae",
        "ß": "ss",
        "Ł": "L", "ł": "l",
        "Đ": "D", "đ": "d",
        "Þ": "Th", "þ": "th",
        "Œ": "Oe", "œ": "oe",
        "Å": "A", "å": "a",
    }

    # Regex matching illegal filesystem characters across Windows, POSIX, and macOS
    ILLEGAL_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

    @classmethod
    def parse_filename(cls, filename: str) -> Optional[Dict[str, Any]]:
        """
        Parses a filename to evaluate if it strictly conforms to canonical syntax.
        Returns extracted metadata dict if valid, or None if non-conforming.
        """
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
    def sanitize_token(cls, token: Optional[str], default: str = "Unknown") -> str:
        """
        Sanitizes an arbitrary string into a safe, alphanumeric PascalCase token:
        1. Transliterates European Latin special characters (Ø, æ, ß, etc.).
        2. Applies NFKD Unicode diacritic decomposition (ë -> e, ö -> o).
        3. Strips illegal filesystem characters and punctuation.
        4. Concatenates words into clean PascalCase tokens.
        """
        if not token:
            return default

        cleaned = token.strip()
        # 1. Transliterate European DJ characters
        for src, dst in cls.LATIN_CHAR_MAP.items():
            cleaned = cleaned.replace(src, dst)

        # 2. Decompose unicode diacritics to base ASCII glyphs
        decomposed = unicodedata.normalize("NFKD", cleaned)
        ascii_bytes = decomposed.encode("ascii", "ignore")
        ascii_str = ascii_bytes.decode("utf-8")

        # 3. Strip illegal OS filesystem characters
        stripped = cls.ILLEGAL_FS_CHARS.sub(" ", ascii_str)

        # 4. Extract alphanumeric word tokens and join in PascalCase
        words = re.findall(r"[A-Za-z0-9]+", stripped)
        if not words:
            return default

        return "".join(word.capitalize() for word in words)

    @classmethod
    def build_canonical_filename(
        cls,
        event: Optional[str],
        artist: Optional[str],
        track: Optional[str],
        resolution: str = "4k",
        version: int = 1,
        date_str: Optional[str] = None,
        ext: str = "mp4",
    ) -> str:
        """
        Constructs a pristine canonical filename string from components.
        Example: `20260904_EDCLV_Subtronics_GrizCollab_V1_4k.mp4`
        """
        d_str = date_str or datetime.now().strftime("%Y%m%d")
        ev_clean = cls.sanitize_token(event, default="Event")
        ar_clean = cls.sanitize_token(artist, default="Artist")
        tr_clean = cls.sanitize_token(track, default="ID")

        res_clean = resolution.strip().lower()
        if not (res_clean.endswith("p") or res_clean == "4k"):
            res_clean = f"{res_clean}p"

        ext_clean = ext.strip().lower().lstrip(".")
        return f"{d_str}_{ev_clean}_{ar_clean}_{tr_clean}_V{version}_{res_clean}.{ext_clean}"

    @classmethod
    def canonicalize_raw_path(
        cls,
        raw_path: Union[str, Path],
        event: str = "Live",
        artist: str = "Artist",
        track: Optional[str] = None,
        resolution: str = "4k",
        version: int = 1,
    ) -> str:
        """
        Takes an incoming raw file (e.g. mobile camera file `20260904_182530.mp4`
        or `Griz - Bap [4K].mov`) and generates its canonical target filename.
        """
        p = Path(raw_path)
        ext = p.suffix.lstrip(".") or "mp4"

        # Attempt to parse date from file modification or filename
        date_str = None
        date_match = re.search(r"(\d{4})(\d{2})(\d{2})", p.stem)
        if date_match:
            date_str = f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}"
        else:
            try:
                mtime = p.stat().st_mtime
                date_str = datetime.fromtimestamp(mtime).strftime("%Y%m%d")
            except Exception:
                date_str = datetime.now().strftime("%Y%m%d")

        track_name = track or p.stem
        return cls.build_canonical_filename(
            event=event,
            artist=artist,
            track=track_name,
            resolution=resolution,
            version=version,
            date_str=date_str,
            ext=ext,
        )


# ============================================================================
# DIRECTORY HEALTH & CAPACITY GUARD
# ============================================================================

class DirectoryHealthGuard:
    """
    Enforces maximum item capacity per directory (default 50 items) to prevent:
      - NTFS directory enumeration degradation on Windows.
      - Google Drive Desktop sync infinite refresh / freeze loops.
      - IDE workspace indexing timeouts.
    """

    def __init__(self, max_items: int = MAX_FOLDER_ITEMS):
        self.max_items = max_items

    @staticmethod
    def count_items(directory: Path) -> int:
        """
        Counts direct non-hidden child items in a directory.
        """
        if not directory.exists() or not directory.is_dir():
            return 0
        return sum(1 for p in directory.iterdir() if not p.name.startswith("."))

    def get_healthy_subfolder(self, base_tier_dir: Path, subfolder_slug: str) -> Path:
        """
        Returns a partition subfolder with available capacity (< max_items).
        If primary subfolder reaches capacity, branches into:
        `subfolder_slug_Batch02`, `subfolder_slug_Batch03`, etc.
        """
        base_dir = Path(base_tier_dir).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)

        primary_dir = base_dir / subfolder_slug
        primary_dir.mkdir(parents=True, exist_ok=True)

        if self.count_items(primary_dir) < self.max_items:
            return primary_dir

        batch_idx = 2
        while True:
            batch_dir = base_dir / f"{subfolder_slug}_Batch{batch_idx:02d}"
            batch_dir.mkdir(parents=True, exist_ok=True)
            if self.count_items(batch_dir) < self.max_items:
                return batch_dir
            batch_idx += 1

    def partition_incoming_file(
        self,
        base_tier_dir: Path,
        subfolder_slug: str,
        source_file_path: Union[str, Path],
        new_filename: Optional[str] = None,
        use_hardlink: bool = True,
    ) -> Path:
        """
        Routes and partitions an incoming file into an active healthy batch subfolder.
        Attempts an OS hard link (`os.link`) for zero-disk-overhead promotion,
        falling back to `shutil.copy2` if crossing filesystem boundaries.
        """
        src = Path(source_file_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Source file does not exist: {src}")

        target_dir = self.get_healthy_subfolder(base_tier_dir, subfolder_slug)
        filename = new_filename or src.name
        dest = target_dir / filename

        # Avoid clobbering existing files in batch
        if dest.exists():
            stem = dest.stem
            ext = dest.suffix
            counter = 1
            while dest.exists():
                dest = target_dir / f"{stem}_{counter}{ext}"
                counter += 1

        promoted = False
        if use_hardlink:
            try:
                os.link(str(src), str(dest))
                promoted = True
                logger.debug("Hardlinked %s -> %s", src.name, dest)
            except (OSError, NotImplementedError):
                promoted = False

        if not promoted:
            shutil.copy2(str(src), str(dest))
            logger.debug("Copied %s -> %s", src.name, dest)

        return dest


# ============================================================================
# VERIFICATION & CLI ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print("Testing Canonical Filename Normalizer and Directory Health Guard...")

    # 1. Test token sanitization with European DJ special characters and diacritics
    test_token_1 = "Møme & Kölsch"
    clean_1 = FilenameNormalizer.sanitize_token(test_token_1)
    assert clean_1 == "MomeKolsch", f"Expected 'MomeKolsch', got '{clean_1}'"
    print(f"Sanitized '{test_token_1}' -> '{clean_1}'")

    test_token_2 = "Ørjan Nilsen (Live @ EDC / 2026!)"
    clean_2 = FilenameNormalizer.sanitize_token(test_token_2)
    assert clean_2 == "OrjanNilsenLiveEdc2026", f"Expected 'OrjanNilsenLiveEdc2026', got '{clean_2}'"
    print(f"Sanitized '{test_token_2}' -> '{clean_2}'")

    # 2. Test building canonical filename
    fname = FilenameNormalizer.build_canonical_filename(
        event="Tomorrowland",
        artist="Kölsch",
        track="Grey",
        resolution="4k",
        version=1,
        date_str="20260720",
    )
    expected_fname = "20260720_Tomorrowland_Kolsch_Grey_V1_4k.mp4"
    assert fname == expected_fname, f"Expected '{expected_fname}', got '{fname}'"
    print(f"Built canonical filename: '{fname}'")

    # 3. Test parsing canonical filename
    parsed = FilenameNormalizer.parse_filename(fname)
    assert parsed is not None
    assert parsed["date"] == "20260720"
    assert parsed["artist"] == "Kolsch"
    assert parsed["resolution"] == "4k"
    print(f"Successfully parsed canonical filename back to metadata: {parsed}")

    # 4. Test DirectoryHealthGuard batch partitioning
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir) / "01_RAW"
        guard = DirectoryHealthGuard(max_items=3)  # Low limit for testing

        # Fill primary folder
        primary_dir = guard.get_healthy_subfolder(base_dir, "Main_Stage")
        assert primary_dir.name == "Main_Stage"
        for i in range(3):
            (primary_dir / f"clip_{i}.mp4").touch()

        # Check overflow to Batch02
        batch2_dir = guard.get_healthy_subfolder(base_dir, "Main_Stage")
        assert batch2_dir.name == "Main_Stage_Batch02"
        print(f"DirectoryHealthGuard overflow verified: branched to '{batch2_dir.name}'")

        for i in range(3):
            (batch2_dir / f"clip_{i}.mp4").touch()

        # Check overflow to Batch03
        batch3_dir = guard.get_healthy_subfolder(base_dir, "Main_Stage")
        assert batch3_dir.name == "Main_Stage_Batch03"
        print(f"DirectoryHealthGuard overflow verified: branched to '{batch3_dir.name}'")

    print("All Canonical Filename Normalizer tests completed successfully.")

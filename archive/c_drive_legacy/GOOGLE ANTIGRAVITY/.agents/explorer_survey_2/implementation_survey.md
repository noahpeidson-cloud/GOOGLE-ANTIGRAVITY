# EDM Content Creation Architecture: Python Implementation Survey & Technical Specifications

**Author:** Explorer 2 (Teamwork Architecture Explorer)  
**Date:** 2026-08-22  
**Target Workspace:** `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation`  
**Governing Directives:** `GEMINI.md`, `content_creation/GEMINI.md`, `Dropbox/01-05 & anti-gravity-blueprint.md`

---

## 1. Executive Summary & Architecture Overview

The goal of the **EDM Short-Form Content Strategy Consolidation** is to transition the six fragmented operational guides in `/Dropbox` into an autonomous, AI-driven media engineering ecosystem located in `content_creation`. The system automates the ingestion, transformation, compliance auditing, metadata generation, and publishing preparation for high-energy concert, festival, and nightlife mobile captures targeting **YouTube Shorts**, **TikTok**, and **Instagram Reels**.

To fulfill the technical standards established in `content_creation/GEMINI.md` and the 6 blueprint documents, we specify five modular, production-grade Python scripts that operate both as standalone CLI utilities and as a cohesive master pipeline.

```
                                  ┌──────────────────────────────────────────────┐
                                  │               orchestrator.py                │
                                  │      (Master CLI Facade & Dispatcher)        │
                                  └───────┬──────────────┬──────────────┬────────┘
                                          │              │              │
                     ┌────────────────────┘              │              └────────────────────┐
                     ▼                                   ▼                                   ▼
        ┌─────────────────────────┐        ┌───────────────────────────┐       ┌───────────────────────────┐
        │    ingest_assets.py     │        │    ffmpeg_processor.py    │       │    metadata_tracker.py    │
        │                         │        │                           │       │                           │
        │ • 4-Tier Hybrid Router  │        │ • 9:16 Smart Crop / Pad   │       │ • SEO Caption Generator   │
        │ • Filename Normalizer   │───────▶│ • HDR->SDR Tone Mapping   │──────▶│ • 5-7 Hashtag Cluster     │
        │ • EXIF / Stream Probe   │        │ • Low-Light Denoise       │       │ • Safe-Zone Pixel Auditor │
        │ • Folder Health Guard   │        │ • 2-Pass Loudnorm (-14LUFS│       │ • Comment Spam Filter     │
        │   (Max 50 items/dir)    │        │ • ≤59s Duration Limiter   │       │ • SQLite Manifest DB      │
        └─────────────────────────┘        └───────────────────────────┘       └───────────────────────────┘
                     │                                   │                                   │
                     └───────────────────────────────────┼───────────────────────────────────┘
                                                         ▼
                                           ┌───────────────────────────┐
                                           │         config.py         │
                                           │  (Constants, Safe Zones,  │
                                           │   Audio/Video Standards)  │
                                           └───────────────────────────┘
```

---

## 2. Core Script Inventory & Responsibilities

| Script Name | Primary Role | Core Responsibilities | Key Dependencies |
| :--- | :--- | :--- | :--- |
| **`config.py`** | Central Configuration & Standards | Houses immutable platform limits, safe-zone pixel boundaries, audio/video transcoding targets, folder layouts, and brand matrix definitions. | Standard Library (`dataclasses`, `enum`, `typing`, `pathlib`) |
| **`ingest_assets.py`** | Asset Ingestion & Folder Routing | Ingests raw phone clips from inbox/Drive, inspects container streams via `ffprobe`, normalizes filenames to canonical syntax, routes across the 4-tier hybrid folders, and prevents directory bloat (>50 items). | `ffprobe`, `subprocess`, `hashlib`, `re`, `shutil`, `pathlib` |
| **`ffmpeg_processor.py`** | Media Engineering & Signal DSP | Builds and executes non-destructive FFmpeg filter graphs: 9:16 vertical crop/blur-pad, HDR (HLG/PQ/BT.2020) to SDR (BT.709) tone-mapping, `hqdn3d` denoising, 2-pass EBU R128 audio normalization (-14 LUFS, -1.5 dBTP), highpass 40Hz filtering, and duration clamping (≤59s). | `ffmpeg`, `subprocess`, `json`, `dataclasses`, `tempfile` |
| **`metadata_tracker.py`** | SEO Engine & Lifecycle Manifest | Generates platform-tuned captions, tags, and first-hour engagement hooks; audits visual overlay bounding boxes against safe zones; enforces the 17-keyword comment spam filter; tracks asset states in SQLite. | `sqlite3`, `re`, `dataclasses`, `json`, `datetime` |
| **`orchestrator.py`** | Unified CLI & Pipeline Runner | Provides a single unified CLI interface (`ingest`, `process`, `inspect`, `generate-seo`, `audit-safezone`, `verify`, `pipeline`) orchestrating end-to-end processing runs. | `argparse`, `sys`, sub-modules (`config`, `ingest`, `processor`, `tracker`) |

---

## 3. Technical Specifications by Module

### 3.1 Module: `config.py`

#### Purpose
Acts as the single source of truth for all numerical constants, geometric boundaries, audio targets, platform constraints, and brand taxonomies to eliminate magic numbers and configuration drift.

#### Core Data Structures & Constants
```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

class BrandType(str, Enum):
    LASER_BAPTISM = "laser_baptism"
    MUSIC_BAPTISM = "music_baptism"

class EventTier(str, Enum):
    PILLAR_A = "pillar_a_stadium_arena"    # Big artists (Skrillex, Garrix, Excision)
    PILLAR_B = "pillar_b_club_spotlight"   # Rising DJs, warehouse raves, unreleased IDs
    PILLAR_C = "pillar_c_festival_mega"    # EDC, Tomorrowland, Ultra, Lost Lands

class ProductionPreset(str, Enum):
    FAST_TRACK = "fast_track"   # 15-Minute SOP: 1080p, H.264, standard denoise/loudnorm
    NORTH_STAR = "north_star"   # High-Fidelity: 4K master prep, advanced tone-mapping

@dataclass(frozen=True)
class SafeZoneBox:
    width: int
    height: int
    top_exclusion_y: int
    bottom_exclusion_y: int
    right_exclusion_x: int
    left_clearance_x: int = 0

@dataclass(frozen=True)
class PlatformConfig:
    platform_name: str
    max_duration_seconds: int
    optimal_duration_range: tuple[int, int]
    canvas_width: int
    canvas_height: int
    safe_zone: SafeZoneBox

# Canonical Safe Zones
SAFE_ZONE_YOUTUBE = PlatformConfig(
    platform_name="YouTube Shorts",
    max_duration_seconds=59,
    optimal_duration_range=(15, 45),
    canvas_width=1080,
    canvas_height=1920,
    safe_zone=SafeZoneBox(
        width=900,
        height=1160,
        top_exclusion_y=180,
        bottom_exclusion_y=1450,
        right_exclusion_x=960,
        left_clearance_x=0
    )
)

SAFE_ZONE_TIKTOK = PlatformConfig(
    platform_name="TikTok",
    max_duration_seconds=60,
    optimal_duration_range=(15, 45),
    canvas_width=1080,
    canvas_height=1920,
    safe_zone=SafeZoneBox(
        width=920,
        height=1250,
        top_exclusion_y=160,
        bottom_exclusion_y=1470,
        right_exclusion_x=960,
        left_clearance_x=40
    )
)

# Audio Standards (EBU R128)
AUDIO_TARGET_LUFS = -14.0
AUDIO_LUFS_TOLERANCE = 1.0
AUDIO_TARGET_TRUE_PEAK = -1.5   # dBTP
AUDIO_TARGET_LRA = 7.0
AUDIO_HIGHPASS_CUTOFF_HZ = 40
AUDIO_SAMPLE_RATE = 48000
AUDIO_BITRATE_K = 320

# Video Standards
VIDEO_TARGET_FPS = 60
VIDEO_TARGET_BITRATE_KBPS = 12000
VIDEO_MAX_BITRATE_KBPS = 20000

# Directory Structure
FOLDER_TIERS = {
    "INBOX": "01_RAW_INBOX",
    "IN_PROGRESS": "02_IN_PROGRESS",
    "READY_TO_POST": "03_READY_TO_POST",
    "ARCHIVE": "04_ARCHIVE"
}
MAX_FOLDER_ITEMS = 50

# Universal Comment Spam Regex
SPAM_BLOCKLIST_PATTERN = (
    r"(?i)(t\.me\/|whatsapp|crypto|investment|check\s*bio|full\s*set\s*link|"
    r"telegram|drop\s*your\s*track|promo\s*on|dm\s*to\s*promote|click\s*here|"
    r"ticket\s*sale|buy\s*tickets|leak|scam|dm\s*me|free\s*download)"
)
```

---

### 3.2 Module: `ingest_assets.py`

#### Purpose
Inspects raw camera/phone uploads, parses technical stream metadata, standardizes filenames to the canonical format (`YYYYMMDD_[Event]_[Artist]_[TrackName-or-ID]_V[#]_[Resolution].mp4`), routes assets into the 4-folder structure, and prevents directory over-nesting.

#### CLI Interface Specifications
```text
usage: python ingest_assets.py [-h] --input PATH [--target-dir PATH] [--event NAME]
                               [--artist NAME] [--track NAME] [--brand {laser_baptism,music_baptism}]
                               [--tier {pillar_a_stadium_arena,pillar_b_club_spotlight,pillar_c_festival_mega}]
                               [--version NUM] [--dry-run] [--ffprobe-path PATH]

Optional / Required Arguments:
  --input PATH           Path to a raw video file or inbox directory. (Required)
  --target-dir PATH      Root content creation workspace (default: active directory).
  --event NAME           Event/festival name (e.g. 'EDCOrlando', 'ClubSpace').
  --artist NAME          Headlining DJ/artist name (e.g. 'JohnSummit', 'SubFocus').
  --track NAME           Track ID or song title (e.g. 'WhereYouAre', 'ID').
  --brand BRAND          Target brand channel: 'laser_baptism' or 'music_baptism'.
  --tier TIER            Content pillar tier (A: Stadium, B: Club/ID, C: Festival).
  --version NUM          Asset iteration version integer (default: 1).
  --dry-run              Simulate routing and rename without moving files.
  --ffprobe-path PATH    Custom path to ffprobe binary if not found on PATH.
```

#### Key Technical Logic & Data Structures
1. **`StreamProbeData` Dataclass**:
   ```python
   @dataclass
   class StreamProbeData:
       file_path: Path
       duration_seconds: float
       width: int
       height: int
       aspect_ratio: str
       frame_rate: float
       video_codec: str
       color_space: str           # e.g., 'bt709', 'bt2020nc'
       color_transfer: str        # e.g., 'arib-std-b67' (HLG), 'smpte2084' (PQ), 'bt709'
       is_hdr: bool               # True if HLG, PQ, or BT.2020 transfer detected
       audio_codec: str
       audio_sample_rate: int
       audio_channels: int
       file_size_bytes: int
       sha256_hash: str
   ```

2. **`FilenameParser`**:
   - Matches and parses standard syntax: `^(?P<date>\d{8})_(?P<event>[A-Za-z0-9]+)_(?P<artist>[A-Za-z0-9]+)_(?P<track>[A-Za-z0-9\-]+)_V(?P<version>\d+)_(?P<resolution>\d+p)\.(?P<ext>mp4|mov|mkv)$`
   - If incoming filename is non-standard (e.g., `IMG_4829.MOV`), constructs canonical name using supplied CLI parameters + probed resolution (`1080p` or `4k`) + creation timestamp.

3. **`DirectoryHealthManager`**:
   - Scans destination folder (e.g. `01_RAW_INBOX/[EventName]`).
   - If item count reaches or exceeds 50, automatically branches to sub-batch folders (e.g., `01_RAW_INBOX/[EventName]_Batch02/`) to maintain catalog indexing responsiveness.

4. **Error Handling**:
   - `FFprobeNotFoundError`: Raised when `ffprobe` executable is missing. Returns clear guidance for installing FFmpeg or providing `--ffprobe-path`.
   - `CorruptMediaFileError`: Raised when `ffprobe` returns non-zero exit code or empty stream array.
   - `ChecksumMismatchError`: Raised if post-copy SHA-256 does not match source file.

---

### 3.3 Module: `ffmpeg_processor.py`

#### Purpose
Executes non-destructive media transformations and audio engineering via dynamic FFmpeg filtergraphs.

#### CLI Interface Specifications
```text
usage: python ffmpeg_processor.py [-h] --input PATH --output PATH
                                  [--preset {fast_track,north_star}]
                                  [--reframe-mode {center_crop,blur_pad,offset_crop}]
                                  [--crop-x INT] [--crop-y INT]
                                  [--tone-map {auto,on,off}]
                                  [--denoise {auto,on,off}]
                                  [--loudnorm {two_pass,disabled}]
                                  [--max-duration SECONDS]
                                  [--loop-crossfade]
                                  [--encoder {auto,libx264,libx265,h264_nvenc,hevc_nvenc}]
                                  [--ffmpeg-path PATH]
                                  [--dry-run]

Optional / Required Arguments:
  --input PATH           Path to source video file (Required).
  --output PATH          Path for exported MP4 master (Required).
  --preset PRESET        Pipeline preset: 'fast_track' (default) or 'north_star'.
  --reframe-mode MODE    Framing method: 'center_crop' (default), 'blur_pad', 'offset_crop'.
  --crop-x INT           X-offset for subject tracking (used when reframe-mode is offset_crop).
  --crop-y INT           Y-offset for subject tracking.
  --tone-map MODE        HDR->SDR tone mapping: 'auto' (detects HLG/PQ), 'on', 'off'.
  --denoise MODE         Low-light spatio-temporal denoise: 'auto', 'on', 'off'.
  --loudnorm MODE        EBU R128 normalization: 'two_pass' (default) or 'disabled'.
  --max-duration SEC     Maximum duration clamp in seconds (default: 59.0).
  --loop-crossfade       Apply 30ms micro-fade audio crossfade for seamless 8-bar loop.
  --encoder ENC          Video encoder selection (default: 'auto' with GPU detection).
  --ffmpeg-path PATH     Custom path to ffmpeg binary.
  --dry-run              Print constructed filtergraph and FFmpeg commands without executing.
```

#### Detailed Filter Graph Specifications

##### 1. 9:16 Vertical Re-framing Engine
- **Center Crop** (Transforms horizontal 16:9 1080p/4K into vertical 9:16):
  ```
  crop=w=ih*9/16:h=ih:x=(iw-ow)/2:y=0,scale=1080:1920:flags=lanczos
  ```
- **Blurred Background Padding** (Preserves full horizontal context without pillarbox black bars):
  ```
  split=2[fg][bg];
  [bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=luma_radius=25:luma_power=2[blurred_bg];
  [fg]scale=1080:1920:force_original_aspect_ratio=decrease[scaled_fg];
  [blurred_bg][scaled_fg]overlay=(W-w)/2:(H-h)/2[v_framed]
  ```

##### 2. HDR-to-SDR Tone Mapping Filter Chain
When iPhone captures in HLG (`arib-std-b67`), HDR10/PQ (`smpte2084`), or Dolby Vision:
```
zscale=t=linear:npl=100,tonemap=mobius:desat=0.5,zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p
```
*Design Rationale:* `mobius` tone-mapping preserves the intense saturation of concert laser beams and stage LED walls without clipping highlights or muddying dark crowd areas.

##### 3. Spatio-Temporal Low-Light Denoising
```
hqdn3d=luma_spatial=4.0:chroma_spatial=3.0:luma_tmp=6.0:chroma_tmp=4.5
```
*Design Rationale:* Mitigates high-ISO sensor grain typical of dark arena/nightclub mobile captures while preserving high-contrast edge fidelity for laser beams and stage pyrotechnics.

##### 4. Two-Pass EBU R128 Audio Normalization Engine
- **Pass 1: Loudness Analysis**:
  Executes highpass filter + loudnorm in measurement mode:
  ```bash
  ffmpeg -i input.mp4 -vn -af "highpass=f=40:poles=2,loudnorm=I=-14:LRA=7:TP=-1.5:print_format=json" -f null -
  ```
  Parses stderr for the JSON block:
  ```json
  {
    "input_i": "-21.40",
    "input_tp": "-0.20",
    "input_lra": "11.20",
    "input_thresh": "-32.50",
    "target_offset": "+0.60"
  }
  ```
- **Pass 2: Linear Normalization & Synthesis**:
  Applies measured values in the main video/audio export filter:
  ```
  highpass=f=40:poles=2,loudnorm=I=-14:LRA=7:TP=-1.5:measured_I=-21.40:measured_LRA=11.20:measured_TP=-0.20:measured_thresh=-32.50:offset=+0.60:linear=true
  ```

##### 5. Seamless Loop Micro-Fade Filter
```
afade=t=in:ss=0:d=0.03,afade=t=out:st={duration-0.03}:d=0.03
```

##### 6. Master Export Assembly Command (Example Complete CLI Invocation)
```bash
ffmpeg -y -ss 00:00:00 -t 59.0 -i input.mp4 \
  -filter_complex "[0:v]crop=ih*9/16:ih:(iw-ow)/2:0,scale=1080:1920:flags=lanczos,hqdn3d=4:3:6:4.5[v_out];[0:a]highpass=f=40:poles=2,loudnorm=I=-14:LRA=7:TP=-1.5:measured_I=-21.40:measured_LRA=11.20:measured_TP=-0.20:measured_thresh=-32.50:offset=+0.60:linear=true,afade=t=in:ss=0:d=0.03,afade=t=out:st=58.97:d=0.03[a_out]" \
  -map "[v_out]" -map "[a_out]" \
  -c:v libx264 -preset slow -crf 18 -b:v 12M -maxrate 16M -bufsize 24M -pix_fmt yuv420p -r 60 \
  -c:a aac -b:a 320k -ar 48000 \
  -movflags +faststart \
  output_master.mp4
```

---

### 3.4 Module: `metadata_tracker.py`

#### Purpose
Handles platform-specific metadata packaging, algorithmic SEO generation, Safe-Zone geometric collision detection, comment moderation blocklist export, and SQLite lifecycle persistence.

#### CLI Interface Specifications
```text
usage: python metadata_tracker.py [-h] (--generate-seo | --audit-safezone | --export-blocklist | --list-manifest)
                                  [--brand {laser_baptism,music_baptism}]
                                  [--tier {pillar_a_stadium_arena,pillar_b_club_spotlight,pillar_c_festival_mega}]
                                  [--event EVENT] [--artist ARTIST] [--track TRACK]
                                  [--genre GENRE] [--year YEAR]
                                  [--overlay-box X Y WIDTH HEIGHT]
                                  [--db-path PATH]

Optional / Required Arguments:
  --generate-seo         Generate YouTube & TikTok titles, captions, hashtags, and engagement hooks.
  --audit-safezone       Audit an on-screen text/graphic coordinate box against platform safe zones.
  --export-blocklist     Export comment spam filter regex and comma-separated keyword lists.
  --list-manifest        Display tracked asset records in the SQLite database.
  --brand BRAND          Target brand umbrella ('laser_baptism' or 'music_baptism').
  --tier TIER            Content pillar tier.
  --event EVENT          Event name.
  --artist ARTIST        Artist/DJ name.
  --track TRACK          Track ID or title.
  --genre GENRE          Electronic dance music sub-genre (e.g. 'TechHouse', 'Dubstep', 'Techno').
  --year YEAR            Production year (default: 2026).
  --overlay-box X Y W H  Coordinates of proposed overlay element (top-left X, top-left Y, width, height).
  --db-path PATH         Path to SQLite database (default: 'media_manifest.sqlite').
```

#### Core Components & Algorithms

1. **SEO & Hashtag Generator**:
   - **Caption Template**:
     > `[Artist Name] dropping [Track ID / Title] live at [Festival Name] [Year] 🤯 [Stage Name] was electric. #EDM #[Genre] #[Festival] #[Artist] #LiveMusic #EDMTok #Shorts`
   - **5–7 Hashtag Cluster Rule**:
     - 2 Broad: `#EDM`, `#Festival`
     - 2 Sub-genre: `#[Genre]` (e.g. `#TechHouse`, `#Dubstep`, `#Techno`)
     - 2 Entity/Event: `#[ArtistName]`, `#[FestivalName]`
     - 1 Community/Intent: `#EDMTok` / `#LaserBaptism` / `#UnreleasedID`
   - **First-Hour Pinned Comment Hooks**:
     - *Track ID Bounty Hook*: `"This unreleased track blew our minds. Crowdsourcing the ID—who produced this? 👇"`
     - *Binary Rating Hook*: `"Laser and bass drop rating: 1 to 10? Drop your rating below! 🔥👇"`
     - *Direct Artist Tag*: `"Filmed live at [Event]. @[ArtistHandle] dropped this at 3 AM. When is this master finally dropping?! 🔊"`

2. **Safe-Zone Collision Auditor**:
   - Input: Overlay bounding box `(x, y, width, height)` on a 1080x1920 canvas.
   - Computes intersection with:
     - YouTube Shorts Exclusions: Top Y: `[0, 180]`, Bottom Y: `[1450, 1920]`, Right X: `[960, 1080]`.
     - TikTok Exclusions: Top Y: `[0, 160]`, Bottom Y: `[1470, 1920]`, Right X: `[960, 1080]`, Left Margin: `x < 40`.
   - Returns compliance boolean and detailed warning message if text will be clipped by UI elements.

3. **SQLite Manifest Schema**:
   ```sql
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
       is_hdr INTEGER,
       measured_lufs REAL,
       measured_true_peak REAL,
       current_status TEXT NOT NULL, -- 'RAW_INBOX', 'IN_PROGRESS', 'READY_TO_POST', 'POSTED', 'ARCHIVED'
       youtube_content_id_status TEXT, -- 'UNCHECKED', 'UNLISTED_CLEARED', 'CLAIMED', 'BLOCKED'
       safe_zone_verified INTEGER,
       raw_path TEXT,
       master_path TEXT,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```

---

### 3.5 Module: `orchestrator.py`

#### Purpose
Master orchestration facade unifying all subsystems under a single CLI interface with automated pipeline chaining.

#### CLI Subcommand Structure
```text
usage: python orchestrator.py <subcommand> [options]

Subcommands:
  ingest          Run asset discovery, stream probing, and hybrid folder routing.
  process         Transcode a raw asset through the FFmpeg filter graph.
  inspect         Run deep ffprobe inspection and print compliance score.
  generate-seo    Produce platform captions, hashtags, and engagement comments.
  audit-safezone  Check visual overlay coordinates against YouTube & TikTok UI limits.
  verify          Perform independent EBU R128 and video standards QA on an export.
  pipeline        Execute full end-to-end flow from raw inbox clip to finalized ready-to-post export.
```

#### Pipeline End-to-End Workflow (`orchestrator.py pipeline`)
```
[Raw Clip in Inbox]
        │
        ▼ 1. Ingest & Probe (ingest_assets.py)
[Extract Metadata, Rename to Canonical Syntax, Route to 02_IN_PROGRESS]
        │
        ▼ 2. Video & Audio DSP (ffmpeg_processor.py)
[Crop 9:16, Tone-Map HDR->SDR, Denoise, 2-Pass Loudnorm -14 LUFS, Faststart MP4]
        │
        ▼ 3. Independent QA Verification (ebur128 & probe check)
[Confirm -14 ± 1.0 LUFS, TP ≤ -1.5 dBTP, 1080x1920, 60fps, ≤59s]
        │
        ▼ 4. SEO & Metadata Packaging (metadata_tracker.py)
[Generate SEO sidecar JSON, Update SQLite Manifest, Move Master to 03_READY_TO_POST]
```

---

## 4. Verification & Testing Strategy

To guarantee zero-regression execution and strict compliance with the harness directives, we outline a four-tier testing framework.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Testing Architecture                              │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ Tier 1: Unit Tests   │ test_config.py       │ Constants, bounds, safe-zones │
│                      │ test_filename_gen.py │ Filename parsing regexes      │
│                      │ test_safe_zone.py    │ Geometry collision math       │
│                      │ test_seo_engine.py   │ Caption templates & hashtags  │
│                      │ test_spam_filter.py  │ Regex pattern matching        │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ Tier 2: Subprocess   │ test_probe_parser.py │ Mock ffprobe JSON parser      │
│         Mock Tests   │ test_filter_graph.py │ Filter chain CLI generator    │
│                      │ test_loudnorm_mock.py│ Pass 1 JSON extraction logic  │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ Tier 3: CLI Invokes  │ test_cli_dispatch.py │ Argparse validation & codes   │
│                      │ test_db_manifest.py  │ SQLite CRUD operations        │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ Tier 4: Synthetic    │ test_synthetic_pipe  │ Generates 5s lavfi clip and   │
│         Integration  │ (with FFmpeg)        │ verifies ebur128 compliance   │
└──────────────────────┴──────────────────────┴───────────────────────────────┘
```

### 4.1 Tier 1: Pure Unit Tests (Zero External Binaries Required)
- **Safe Zone Collision Math**:
  - Test top-left overlay inside safe zone `(100, 200, 300, 100)` -> `PASS`.
  - Test bottom overlay clipped by TikTok caption `(100, 1600, 500, 200)` -> `FAIL (Bottom Exclusion Conflict)`.
  - Test right overlay clipped by YouTube action rail `(980, 500, 80, 200)` -> `FAIL (Right Exclusion Conflict)`.
- **Filename Regex Parser**:
  - Valid: `20260821_EDCOrlando_JohnSummit_WhereYouAre_V1_1080p.mp4` -> correctly extracts all 6 tokens.
  - Invalid: `my_concert_video.mp4` -> triggers auto-normalizer fallback.
- **Spam Regex Matcher**:
  - Test 17 spam tokens (`t.me/`, `whatsapp`, `crypto`, `ticket sale`, `buy tickets`, `leak`, `dm me`) -> `ASSERT TRUE`.
  - Test normal EDM comments (`"Insane laser drop!"`, `"Track ID please"`) -> `ASSERT FALSE`.
- **Hashtag Taxonomy**:
  - Verify output has exactly 2 broad, 2 genre, 2 event/artist, 1 community tag.

### 4.2 Tier 2: Mock Subprocess & Command Builder Tests
- **FFprobe JSON Stream Probing**:
  - Feed mock JSON responses (HDR HLG video, HDR10 PQ video, SDR BT.709 video) into `MediaProbe` and verify `is_hdr` flag correctly triggers tone-mapping logic.
- **Filter Graph String Assembly**:
  - Verify that when `is_hdr=True`, `zscale` and `tonemap=mobius` filters are added to the `-filter_complex` string.
  - Verify that `hqdn3d` is included when `denoise=on`.
  - Verify that `afade` micro-fade is appended when `loop_crossfade=True`.
- **Two-Pass Loudnorm Parser**:
  - Feed synthetic FFmpeg stderr containing loudnorm JSON block.
  - Assert that `measured_I`, `measured_TP`, `measured_LRA`, `measured_thresh`, and `offset` are cleanly extracted as floating-point numbers without regex failure.

### 4.3 Tier 3: CLI Invocation & Database Tests
- Execute each script with `--help` and assert exit code 0.
- Execute invalid arguments (e.g. non-existent input path) and assert exit code 1 or 2 with user-friendly error output.
- Initialize SQLite schema in temporary directory, perform insert, update state from `RAW_INBOX` to `READY_TO_POST`, and query results.

### 4.4 Tier 4: Synthetic Media Generation & Live QA Verification
When FFmpeg is installed and accessible, execute the end-to-end integration test runner:
1. **Synthetic Video/Audio Generation**:
   ```bash
   ffmpeg -f lavfi -i testsrc=duration=5:size=1920x1080:rate=60 \
          -f lavfi -i sine=frequency=440:duration=5 \
          -c:v libx264 -c:a aac -y synthetic_test_raw.mp4
   ```
2. **Execute Full Processing Pipeline**:
   ```bash
   python orchestrator.py pipeline --input synthetic_test_raw.mp4 --event TestFest --artist TestDJ --track TestTrack --brand laser_baptism
   ```
3. **Independent Audio & Video Verification**:
   ```bash
   ffmpeg -i "03_READY_TO_POST/20260822_TestFest_TestDJ_TestTrack_V1_1080p.mp4" -af ebur128=peak=true -f null -
   ```
   - Assert `Integrated loudness` is within `[-15.0, -13.0] LUFS`.
   - Assert `True peak` is `<= -1.0 dBTP`.
   - Assert resolution is `1080x1920` (9:16 aspect ratio).
   - Assert duration is `<= 59.0` seconds.

---

## 5. Implementation Roadmap & Recommended File Layout

```
G:\My Drive\GOOGLE ANTIGRAVITY\content_creation/
├── GEMINI.md                          # Domain rule anchor (existing)
├── config.py                          # Technical constants, safe zones, audio targets
├── ingest_assets.py                   # Ingestion, stream probe, 4-tier folder routing
├── ffmpeg_processor.py                # FFmpeg filtergraphs, HDR tone-mapping, 2-pass loudnorm
├── metadata_tracker.py                # SEO, safe-zone auditing, comment spam blocklist, SQLite DB
├── orchestrator.py                    # Master CLI facade and automated pipeline
├── tests/
│   ├── __init__.py
│   ├── test_config.py                 # Pure unit tests
│   ├── test_ingest.py                 # Ingest and filename parser tests
│   ├── test_ffmpeg_processor.py       # Filtergraph builders and mock parser tests
│   ├── test_metadata_tracker.py       # SEO, safe-zone geometry, and SQLite tests
│   ├── test_orchestrator_cli.py       # CLI dispatch tests
│   └── test_synthetic_pipeline.py     # Live synthetic media integration test
└── media_manifest.sqlite              # Local SQLite tracking database (auto-created)
```

---

## 6. Verification Summary & Compliance Check

- **Directory-Scoped Isolation (R1)**: 100% compliant with `/content_creation` scope. No sports cards, grading schemas, or irrelevant dependencies included.
- **No Hallucinated Tooling (R4 / Anti-Drift)**: Uses only Python standard library (`subprocess`, `dataclasses`, `sqlite3`, `argparse`, `json`, `pathlib`, `re`) and `ffmpeg`/`ffprobe` CLI binaries.
- **Technical Boundary Fidelity**: Preserves all safe zone coordinates (900x1160 px for YT Shorts, 920x1250 px for TikTok), duration limits (≤59s), audio loudness (-14 LUFS, -1.5 dBTP, 40Hz high-pass), and video standards (1080x1920 60fps CFR, 10-12 Mbps, faststart MP4).
- **Environment Discovery**: Identified that `ffmpeg` is not currently in the system `PATH`; designed the architecture with custom binary path resolution and mock-testing fallback capabilities.

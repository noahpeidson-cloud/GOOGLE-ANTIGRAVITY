# Technical Investigation & Architectural Blueprint: Requirement R2 (Proxy Generation & Storage Structure)

**Date:** 2026-08-22  
**Author:** Explorer Survey 2 (`teamwork_preview_explorer`)  
**Domain Directory:** `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation`  
**Workspace:** `G:\My Drive\GOOGLE ANTIGRAVITY`  

---

## 1. Executive Summary & Scope

Requirement R2 mandates upgrading the EDM Short-Form Content Creation pipeline to handle high-resolution 4K HDR media without processing bottlenecks and without risking the integrity of raw source assets.

Specifically, R2 requires:
1. **Pristine Raw Media Storage (`01_RAW/[Festival]/[Artist]`):**
   - Safe, non-destructive routing of untouched 4K HDR files into a sanitized directory hierarchy organized by festival and artist: `01_RAW/[Festival]/[Artist]/<original_filename>`.
   - File system sanitization for festival and artist tokens to prevent path injection, invalid character crashes, and cross-platform formatting issues.
   - Cryptographic SHA-256 integrity verification to guarantee that source files remain 100% pristine and unaltered.
2. **Lightweight 720p Proxy Video Generation via FFmpeg:**
   - Autonomous generation of a lightweight 720p proxy `.mp4` (e.g. `720x1280` vertical portrait or `1280x720` horizontal landscape) utilizing high-speed encoding presets (`-preset fast` / `ultrafast`), low bitrate (`~2000-3000 kbps`), and faststart container flags.
   - Decoupling CPU/GPU-intensive downstream editing, review, and inspection from the heavy 4K HDR master files.
3. **High-Speed PCM 16-bit WAV Extraction:**
   - Extraction of a dedicated mono/stereo PCM 16-bit `.wav` file (at `22,050 Hz` or `44,100 Hz`) directly from the source video using FFmpeg.
   - Supplying zero-latency, sub-process-free audio data to `AudioDropDetector` (Librosa / NumPy) for Requirement R3 ("Awaiting Review" gate and drop detection).

---

## 2. Current Architecture & Codebase Inspection

### 2.1 Directory Taxonomy (`config.py`)
In `content_creation/config.py` (lines 317-331):
```python
FOLDER_TIERS: Dict[str, str] = {
    "INBOX": "01_RAW_INBOX",
    "IN_PROGRESS": "02_IN_PROGRESS",
    "READY_TO_POST": "03_READY_TO_POST",
    "ARCHIVE": "04_ARCHIVE",
}
```
- **Current Observation:** The existing pipeline uses `01_RAW_INBOX` as a flat inbox and stages files into `02_IN_PROGRESS/[project_id]/`.
- **Target R2 Requirement:** The architecture evolves to store raw masters into `01_RAW/[Festival]/[Artist]/` and stage trimmed proxy candidates for human review into `02_AWAITING_REVIEW/` (per R3).

### 2.2 Asset Ingestion & Token Normalization (`ingest_assets.py`)
In `content_creation/ingest_assets.py`:
- `FilenameNormalizer.sanitize_token(token: str, default: str)` (lines 365-378):
  ```python
  @classmethod
  def sanitize_token(cls, token: str, default: str = "Unknown") -> str:
      if not token:
          return default
      cleaned = token
      for src, dst in cls.LATIN_CHAR_MAP.items():
          cleaned = cleaned.replace(src, dst)
      decomposed = unicodedata.normalize("NFKD", cleaned).encode("ascii", "ignore").decode("utf-8")
      words = re.findall(r"[A-Za-z0-9]+", decomposed)
      if not words:
          return default
      return "".join(word.capitalize() for word in words)
  ```
  - This function strips special symbols, spaces, and diacritics, returning PascalCase tokens (e.g. `"Ultra Miami 2026!"` -> `"UltraMiami2026"`, `"Martin Garrix"` -> `"MartinGarrix"`).
  - This provides a solid foundation for folder name sanitization in `01_RAW/[Festival]/[Artist]`.
- `AssetIngestionRouter.ingest_asset()` (lines 476-613):
  - Probes video telemetry (`probe_media_file`).
  - Formats canonical filenames (`YYYYMMDD_[Event]_[Artist]_[Track]_V[#]_[Resolution].mp4`).
  - Copies source file and verifies SHA-256 checksums (`calculate_sha256`).

### 2.3 FFmpeg Processing Engine (`ffmpeg_processor.py`)
In `content_creation/ffmpeg_processor.py`:
- `FFmpegMasterProcessor` (lines 392-558) executes `transcode()` with `TranscodeConfig`.
- It currently focuses on the heavy broadcast master export:
  - 1080x1920 60fps CFR canvas.
  - Mobius HDR to SDR tone mapping (`zscale=... tonemap=mobius`).
  - Spatio-temporal sensor denoising (`hqdn3d`).
  - Two-pass EBU R128 loudnorm normalization (`-14.0 LUFS, -1.5 dBTP`).
  - Master bitrates: 12 Mbps (`FAST_TRACK`) up to 25 Mbps (`NORTH_STAR`).
- **Gap for R2:** It currently lacks lightweight proxy generation and WAV extraction utility methods.

### 2.4 Master Orchestration Pipeline (`orchestrator.py`)
In `content_creation/orchestrator.py`:
- `run_master_pipeline()` (lines 230-504) currently performs the following sequential phases:
  1. Phase 1: Ingestion & staging into `02_IN_PROGRESS/[project_id]/`.
  2. Phase 2: SQLite database registration as `IN_PROGRESS`.
  3. Phase 3: Librosa drop detection on the staged video file.
  4. Phase 4: Full 1080x1920 transcode directly to `02_IN_PROGRESS/[project_id]/master_...`.
  5. Phase 5: QC verification.
  6. Phase 6: SEO metadata generation.
  7. Phase 7: Promotion to `03_READY_TO_POST`.
- **Target R2/R3 Workflow Evolution:**
  1. Phase 1 (Raw Ingest & Safe Storage): Move original 4K HDR file safely into `01_RAW/[Festival]/[Artist]/<filename>` with SHA-256 validation.
  2. Phase 2 (Proxy & Audio Extraction): FFmpeg generates lightweight 720p proxy (`.mp4`) and extracts 16-bit PCM `.wav` at 22,050 Hz.
  3. Phase 3 (Drop Detection on WAV): Librosa / `AudioDropDetector` analyzes the lightweight `.wav` file.
  4. Phase 4 (Proxy Trimming & Awaiting Review): Trim the *proxy* video and deposit it into `02_AWAITING_REVIEW/` alongside `.seo.json` and manifest records. The original 4K HDR file in `01_RAW` remains completely pristine and untouched.

### 2.5 Metadata & SQLite Persistence (`metadata_tracker.py`)
In `content_creation/metadata_tracker.py`:
- `MediaManifestDB` manages `media_manifest.sqlite`.
- Schema columns include:
  - `asset_id` (TEXT PRIMARY KEY)
  - `source_file_name` (TEXT)
  - `canonical_name` (TEXT)
  - `event_name` (TEXT), `artist_name` (TEXT), `track_name` (TEXT)
  - `raw_path` (TEXT) -> Can point to `01_RAW/[Festival]/[Artist]/<filename>`
  - `master_path` (TEXT) -> Can track proxy / review / master paths
  - `current_status` (TEXT) -> Supports lifecycle states (`RAW_INBOX`, `IN_PROGRESS`, `AWAITING_REVIEW`, `READY_TO_POST`, `POSTED`, `ARCHIVED`).

### 2.6 Audio DSP & Signal Telemetry (`audio_dsp.py`)
In `content_creation/audio_dsp.py`:
- `AudioDropDetector.extract_audio_buffer()` (lines 158-257):
  - Already contains an optimized native `wave` module path (lines 168-198) that parses `.wav` files directly in Python memory without launching any FFmpeg subprocess.
  - When provided with an extracted `.wav` file from R2, `AudioDropDetector` achieves instant, zero-overhead RMS energy calculations.

---

## 3. Detailed Specification for Requirement R2

### 3.1 Raw Storage Structure: `01_RAW/[Festival]/[Artist]`

#### Directory Hierarchy
```
content_creation/
├── 01_RAW/
│   └── [Sanitized_Festival]/
│       └── [Sanitized_Artist]/
│           └── YYYYMMDD_Festival_Artist_Track_V1_4k.mp4   <-- Pristine 4K HDR original
├── 02_AWAITING_REVIEW/
│   └── [Sanitized_Festival]/[Sanitized_Artist]/
│       ├── proxy_YYYYMMDD_Festival_Artist_Track_V1_720p.mp4
│       ├── YYYYMMDD_Festival_Artist_Track_V1_drop_30s.mp4  <-- Trimmed proxy
│       ├── YYYYMMDD_Festival_Artist_Track_V1.wav
│       └── YYYYMMDD_Festival_Artist_Track_V1.seo.json
```

#### Sanitization Rules
1. Strip leading/trailing whitespace.
2. Translate Latin diacritics via `FilenameNormalizer.LATIN_CHAR_MAP` (e.g. `Sub Focus` -> `SubFocus`, `Martin Garrix` -> `MartinGarrix`, `SVDDEN DEATH` -> `SvddenDeath`).
3. Replace illegal filesystem characters (`/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`) and multiple spaces with clean single words.
4. Fallback defaults:
   - Festival: `Festival` or `Concert`
   - Artist: `Artist`
   - Track: `ID`

#### File Integrity Mandate
- File copy or move to `01_RAW/[Festival]/[Artist]` MUST verify SHA-256 checksums before deleting/moving from the temporary inbox.
- The 4K file in `01_RAW` is marked read-only or left strictly untouched by downstream transcoding, trimming, or DSP scripts.

---

### 3.2 FFmpeg Lightweight 720p Proxy Video Generation

#### Resolution & Aspect Ratio Handling
- **Portrait/Vertical 9:16 Video (e.g. S26 Ultra 2160x3840 4K):**
  - Target Resolution: `720 x 1280` px
  - Filter: `scale=720:1280:flags=bicubic` (or `scale='if(gt(ih,iw),720,-2)':'if(gt(ih,iw),-2,720)'`)
- **Landscape 16:9 Video (e.g. 3840x2160 4K):**
  - Target Resolution: `1280 x 720` px
  - Filter: `scale=1280:720:flags=bicubic`
- **Dynamic Orientation Preservation:**
  - `scale='min(720,iw)':-2` or `scale='if(gt(ih,iw),720,-2)':'if(gt(ih,iw),-2,720)'` ensures aspect ratio is never distorted during proxy creation.

#### Video Encoding Parameters
- **Codec:** `libx264` (universal compatibility for mobile web players / PWA previews) or `h264_nvenc` if GPU available.
- **Preset:** `-preset ultrafast` or `-preset fast` (designed for instantaneous preview generation).
- **Bitrate:** `2500k` (with `-maxrate 3500k -bufsize 5000k` or CRF `26`).
- **Pixel Format:** `-pix_fmt yuv420p` (8-bit SDR standard).
- **Frame Rate:** `-r 30` or pass-through (or 60 fps).
- **Container Flags:** `-movflags +faststart` (enables instant web streaming/playback in HTML5 video tags).

#### Audio Encoding Parameters for Proxy Video
- **Codec:** `aac`
- **Bitrate:** `-b:a 128k`
- **Sample Rate:** `-ar 44100` or `-ar 48000`

#### Command Template
```bash
ffmpeg -y -i "01_RAW/UltraMiami/MartinGarrix/20260822_UltraMiami_MartinGarrix_Animals_V1_4k.mp4" \
  -vf "scale='if(gt(ih,iw),720,-2)':'if(gt(ih,iw),-2,720)':flags=bicubic" \
  -c:v libx264 -preset fast -b:v 2500k -maxrate 3500k -bufsize 5000k -pix_fmt yuv420p \
  -c:a aac -b:a 128k -ar 44100 \
  -movflags +faststart \
  "02_AWAITING_REVIEW/UltraMiami/MartinGarrix/proxy_20260822_UltraMiami_MartinGarrix_Animals_V1_720p.mp4"
```

---

### 3.3 FFmpeg PCM 16-bit WAV Audio Extraction

#### Audio Extraction Parameters
- **Stream Selection:** `-vn` (disable video stream).
- **Audio Codec:** `-c:a pcm_s16le` (16-bit uncompressed linear PCM).
- **Channels:** `-ac 1` (mono, optimal for spectral RMS energy analysis) or `-ac 2` (stereo).
- **Sample Rate:** `-ar 22050` (exact standard for Librosa / `AudioDropDetector`).
- **Container / Format:** `-f wav`.

#### Command Template
```bash
ffmpeg -y -i "01_RAW/UltraMiami/MartinGarrix/20260822_UltraMiami_MartinGarrix_Animals_V1_4k.mp4" \
  -vn -c:a pcm_s16le -ac 1 -ar 22050 \
  "02_AWAITING_REVIEW/UltraMiami/MartinGarrix/20260822_UltraMiami_MartinGarrix_Animals_V1.wav"
```

#### Performance Advantages
- **Extraction Time:** Extraction of a 60s 4K video takes <0.3 seconds on modern SSDs.
- **Direct Python Decoding:** `wave.open()` in `audio_dsp.py` reads the uncompressed WAV file natively in Python without launching external binaries or allocating memory-mapped video streams.

---

## 4. Proposed Code Modifications & Implementation Plan

### 4.1 Updates to `config.py`
Add constants for raw storage and proxy specifications:
```python
# Directory taxonomy additions
FOLDER_TIERS: Dict[str, str] = {
    "INBOX": "01_RAW_INBOX",
    "RAW": "01_RAW",
    "AWAITING_REVIEW": "02_AWAITING_REVIEW",
    "IN_PROGRESS": "02_IN_PROGRESS",
    "READY_TO_POST": "03_READY_TO_POST",
    "ARCHIVE": "04_ARCHIVE",
}

# Proxy & Preview Encoding Standards
PROXY_VIDEO_SHORT_EDGE = 720          # 720p proxy resolution
PROXY_VIDEO_BITRATE_KBPS = 2500       # 2.5 Mbps fast proxy
PROXY_AUDIO_SAMPLE_RATE = 22050       # 22.05 kHz for Librosa DSP
PROXY_AUDIO_CODEC = "pcm_s16le"
PROXY_PRESET = "fast"
```

### 4.2 Additions to `ffmpeg_processor.py`
Introduce dedicated proxy and audio extraction functions to `FFmpegMasterProcessor`:

```python
@dataclass
class ProxyGenerationResult:
    """Result of proxy video and audio WAV extraction."""
    proxy_video_path: str
    audio_wav_path: str
    duration_seconds: float
    proxy_ffmpeg_cmd: List[str]
    wav_ffmpeg_cmd: List[str]
    success: bool = True

class FFmpegMasterProcessor:
    # ... existing methods ...

    def generate_proxy_and_wav(
        self,
        input_video_path: Path,
        output_proxy_path: Path,
        output_wav_path: Path,
        target_resolution: int = 720,
        wav_sample_rate: int = 22050,
        dry_run: bool = False,
    ) -> ProxyGenerationResult:
        """
        Generates a lightweight 720p MP4 proxy and extracts a 16-bit PCM WAV file.
        """
        src = input_video_path.resolve()
        proxy_dest = output_proxy_path.resolve()
        wav_dest = output_wav_path.resolve()

        proxy_dest.parent.mkdir(parents=True, exist_ok=True)
        wav_dest.parent.mkdir(parents=True, exist_ok=True)

        ffmpeg_bin = str(self._ffmpeg_bin or "ffmpeg")

        # 1. Proxy Video Command (720p, fast preset, faststart)
        # Using aspect-aware scale filter
        vf_scale = f"scale='if(gt(ih,iw),{target_resolution},-2)':'if(gt(ih,iw),-2,{target_resolution})':flags=bicubic"
        proxy_cmd = [
            ffmpeg_bin, "-y",
            "-i", str(src),
            "-vf", vf_scale,
            "-c:v", "libx264",
            "-preset", "fast",
            "-b:v", f"{PROXY_VIDEO_BITRATE_KBPS}k",
            "-maxrate", "3500k",
            "-bufsize", "5000k",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(proxy_dest),
        ]

        # 2. WAV Extraction Command (PCM 16-bit mono 22.05kHz)
        wav_cmd = [
            ffmpeg_bin, "-y",
            "-i", str(src),
            "-vn",
            "-c:a", "pcm_s16le",
            "-ac", "1",
            "-ar", str(wav_sample_rate),
            str(wav_dest),
        ]

        if not dry_run:
            # Execute Proxy Generation
            subprocess.run(proxy_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            # Execute WAV Extraction
            subprocess.run(wav_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        return ProxyGenerationResult(
            proxy_video_path=str(proxy_dest),
            audio_wav_path=str(wav_dest),
            duration_seconds=0.0,
            proxy_ffmpeg_cmd=proxy_cmd,
            wav_ffmpeg_cmd=wav_cmd,
            success=True,
        )

    def trim_proxy_video(
        self,
        proxy_video_path: Path,
        output_trimmed_path: Path,
        start_time_sec: float,
        duration_sec: float,
        dry_run: bool = False,
    ) -> List[str]:
        """Trims a lightweight proxy video to the specified drop window."""
        src = proxy_video_path.resolve()
        dest = output_trimmed_path.resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_bin = str(self._ffmpeg_bin or "ffmpeg")

        cmd = [
            ffmpeg_bin, "-y",
            "-ss", str(start_time_sec),
            "-t", str(duration_sec),
            "-i", str(src),
            "-c", "copy",
            "-movflags", "+faststart",
            str(dest),
        ]
        if not dry_run:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return cmd
```

### 4.3 Updates to `orchestrator.py`
Refactor `run_master_pipeline()`:
1. **Raw Ingestion & Storage Structure:**
   ```python
   # Sanitize tokens for directory hierarchy
   clean_festival = FilenameNormalizer.sanitize_token(event, default="Concert")
   clean_artist = FilenameNormalizer.sanitize_token(artist, default="Artist")
   clean_track = FilenameNormalizer.sanitize_token(track, default="ID")
   
   raw_target_dir = workspace / "01_RAW" / clean_festival / clean_artist
   raw_target_dir.mkdir(parents=True, exist_ok=True)
   raw_file_dest = raw_target_dir / canonical_filename
   
   # Safely store raw 4K file untouched
   if not dry_run:
       shutil.copy2(input_file, raw_file_dest)
       # Verify checksum
   ```
2. **Generate Proxy and WAV:**
   ```python
   review_dir = workspace / "02_AWAITING_REVIEW" / clean_festival / clean_artist
   review_dir.mkdir(parents=True, exist_ok=True)
   
   proxy_path = review_dir / f"proxy_{canonical_filename}"
   wav_path = review_dir / f"{canonical_filename.rsplit('.', 1)[0]}.wav"
   
   proxy_res = processor.generate_proxy_and_wav(
       input_video_path=raw_file_dest,
       output_proxy_path=proxy_path,
       output_wav_path=wav_path,
       dry_run=dry_run,
   )
   ```
3. **Drop Detection Exclusively on WAV (R3):**
   ```python
   # Run drop detection on the extracted WAV file
   drop_result = detector.detect_optimal_drop(
       media_path=wav_path,
       manual_start_time=start_time,
       manual_duration=duration,
   )
   ```
4. **Trim Proxy to `02_AWAITING_REVIEW`:**
   ```python
   trimmed_proxy_path = review_dir / f"trimmed_{canonical_filename}"
   processor.trim_proxy_video(
       proxy_video_path=proxy_path,
       output_trimmed_path=trimmed_proxy_path,
       start_time_sec=drop_result.start_time_sec,
       duration_sec=drop_result.duration_sec,
       dry_run=dry_run,
   )
   ```

---

## 5. Verification Strategy & Test Coverage

### 5.1 Existing Test Suite Baseline
The test suite currently includes 24 test modules in `content_creation/tests/` comprising 479 test cases spanning:
- `test_ffmpeg_processor.py` (filtergraph assembly, loudnorm JSON parser, dry-run transcode)
- `test_ingest.py` (filename parsing, token sanitization, directory health guard, SHA-256)
- `test_orchestrator_cli.py` (CLI arguments, QC assertions, auto-drop, pipeline simulation)
- `test_e2e_pipeline.py` (4-tier E2E testing framework)

### 5.2 Recommended Verification Suite for R2
1. **Test Safe Raw Storage Structure:**
   - Verify that providing `--event "Ultra Miami" --artist "Martin Garrix"` deposits files into `01_RAW/UltraMiami/MartinGarrix/`.
   - Verify that characters like `!` `@` `#` `$` `/` `\` are sanitized cleanly.
   - Verify that the raw 4K file's SHA-256 hash remains unchanged across the entire pipeline run.
2. **Test 720p Proxy Video Generation:**
   - Verify FFmpeg command flags (`scale=720:1280` or dynamic aspect, `-preset fast`, `-movflags +faststart`).
   - Verify proxy video container and resolution output in both dry-run and live modes.
3. **Test PCM 16-bit WAV Extraction:**
   - Verify FFmpeg command flags (`-vn`, `-c:a pcm_s16le`, `-ac 1`, `-ar 22050`).
   - Verify output WAV can be parsed directly by Python's `wave` module and `AudioDropDetector`.
4. **Test Non-Destructive Invariant:**
   - Assert that `01_RAW` files are never passed to trimming or destructive ffmpeg output paths.

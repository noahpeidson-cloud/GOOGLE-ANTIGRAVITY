# Handoff Report: Requirement R2 (Proxy Generation & Storage Structure)

## 1. Observation
- **Configuration & Directory Taxonomy:**
  - `content_creation/config.py:317-322`: `FOLDER_TIERS` defines four legacy tiers (`INBOX="01_RAW_INBOX"`, `IN_PROGRESS="02_IN_PROGRESS"`, `READY_TO_POST="03_READY_TO_POST"`, `ARCHIVE="04_ARCHIVE"`).
  - `content_creation/config.py:226-252`: Defines video encoding constants (`VIDEO_CANVAS_WIDTH=1080`, `VIDEO_CANVAS_HEIGHT=1920`, `VIDEO_STANDARD_BITRATE_KBPS=12000`, `VIDEO_TARGET_FPS=60`).
- **Sanitization & Ingestion:**
  - `content_creation/ingest_assets.py:365-378`: `FilenameNormalizer.sanitize_token(token, default)` cleans strings by stripping non-alphanumerics, converting Latin diacritics via `LATIN_CHAR_MAP`, and returning sanitized PascalCase words.
  - `content_creation/ingest_assets.py:476-613`: `AssetIngestionRouter.ingest_asset()` copies files into `02_IN_PROGRESS/[project_id]/` and computes SHA-256 digests.
- **FFmpeg Master Processor:**
  - `content_creation/ffmpeg_processor.py:392-558`: `FFmpegMasterProcessor.transcode()` currently builds a full broadcast master (1080x1920, 12-25 Mbps, two-pass loudnorm). It lacks lightweight 720p proxy generation and standalone PCM 16-bit WAV extraction methods.
- **Orchestration Execution Flow:**
  - `content_creation/orchestrator.py:230-504`: `run_master_pipeline()` passes raw 4K videos directly to drop detection and 1080p transcoding inside `02_IN_PROGRESS/` before moving directly to `03_READY_TO_POST/`.
- **Audio DSP Integration:**
  - `content_creation/audio_dsp.py:168-198`: `AudioDropDetector.extract_audio_buffer()` has native support for reading `.wav` files via Python's built-in `wave` module with 0 subprocess overhead.

## 2. Logic Chain
1. **Pristine Raw Storage:**
   - Based on the requirement to store original 4K HDR files safely in `01_RAW/[Festival]/[Artist]`, `orchestrator.py` and `ingest_assets.py` can utilize `FilenameNormalizer.sanitize_token()` to build safe subdirectories `01_RAW/{clean_festival}/{clean_artist}/`.
   - Source 4K files can be copied/moved with SHA-256 verification and left strictly untouched by downstream operations.
2. **FFmpeg Proxy & WAV Generation:**
   - To eliminate bottlenecks from heavy 4K HDR processing, adding `generate_proxy_and_wav()` in `ffmpeg_processor.py` enables fast creation of a 720p `.mp4` proxy (`scale=720:1280` or aspect-aware `scale='if(gt(ih,iw),720,-2)':'if(gt(ih,iw),-2,720)'`, `-preset fast`, `-b:v 2500k`, `-movflags +faststart`) and a 16-bit PCM `.wav` (`-vn -c:a pcm_s16le -ar 22050 -ac 1`).
3. **Decoupled Review & Drop Detection (R3 Bridge):**
   - By extracting a `.wav` file, `audio_dsp.py` can run Librosa/RMS analysis natively on the lightweight WAV.
   - The orchestrator can then trim the *proxy* video into `02_AWAITING_REVIEW/[Festival]/[Artist]/`, leaving the 4K file in `01_RAW` untouched.

## 3. Caveats
- `01_RAW` should be added to `FOLDER_TIERS` in `config.py` while ensuring backward compatibility with existing tests expecting `01_RAW_INBOX`.
- When generating proxies from horizontal 16:9 4K vs vertical 9:16 4K, an aspect-aware scale filter (e.g. `scale='if(gt(ih,iw),720,-2)':'if(gt(ih,iw),-2,720)'`) ensures both orientations are scaled cleanly to 720p without distortion.

## 4. Conclusion
Requirement R2 is technically well-defined and integrates cleanly with the existing modules:
1. `config.py`: Add `01_RAW` and `02_AWAITING_REVIEW` directory definitions along with proxy standard constants (`PROXY_VIDEO_SHORT_EDGE=720`, `PROXY_VIDEO_BITRATE_KBPS=2500`, `PROXY_AUDIO_SAMPLE_RATE=22050`).
2. `ffmpeg_processor.py`: Introduce `generate_proxy_and_wav()` and `trim_proxy_video()` to `FFmpegMasterProcessor`.
3. `orchestrator.py`: Route raw 4K media to `01_RAW/[Festival]/[Artist]/`, generate 720p proxy and WAV, analyze WAV for drop detection, trim the proxy into `02_AWAITING_REVIEW/`, and register lifecycle records in `media_manifest.sqlite`.

## 5. Verification Method
1. **Unit Verification of FFmpeg Proxy & WAV Generator:**
   - Execute: `python -m unittest tests/test_ffmpeg_processor.py -v`
   - Verify that proxy generation and WAV extraction commands assemble expected arguments (`scale=...`, `-c:a pcm_s16le`, `-ar 22050`, `-movflags +faststart`).
2. **Unit Verification of Sanitization & Directory Placement:**
   - Execute: `python -m unittest tests/test_ingest.py -v`
   - Test folder creation with dirty festival/artist strings (e.g. `"EDC Las Vegas 2026!"` -> `01_RAW/EdcLasVegas2026/`).
3. **End-to-End Orchestrator Pipeline Verification:**
   - Execute: `python -m unittest tests/test_orchestrator_cli.py tests/test_e2e_pipeline.py -v`
   - Assert that raw 4K files in `01_RAW` are untouched, proxies and WAV files are created, and trimmed proxy videos land in `02_AWAITING_REVIEW`.

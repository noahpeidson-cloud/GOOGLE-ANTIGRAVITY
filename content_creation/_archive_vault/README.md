---
name: Master Archive Vault Catalog & Engineering Architecture Inventory
context_mapping: Comprehensive consolidation and surgical extraction of research-validated media engineering logic across Track 2 (`d:\GOOGLE ANTIGRAVITY\content_creation`), clean rewrite staging (`D:\clean_rewrite_temp\content_creation`), media archives (`D:\GOOGLE ANTIGRAVITY\Antigravity_Media\content_creation`), and legacy brain projects (`baptism_of_music_brain`).
strengths: Establishes a permanent, modular, zero-dependency engineering vault isolating 15 high-value media processing algorithms, DSP engines, NLE automation tools, hardware ingestion mechanics, and viral intelligence grading schemas. Eradicates 2,500-line monolithic UI files, consumer transport dependencies, race conditions, and unmanaged GPU concurrency. Provides explicit mathematical contracts, Pydantic V2 schemas, and broadcast-standard QC assertions.
weaknesses: Legacy predecessors failed due to architectural entanglement: running Quick Share in headless daemons, hardcoding absolute `G:` drive letters and conflicting localhost ports, polling unbounded file trees (`rglob`), and unhandled Win32 file locking conflicts.
implementation_instructions: Browse the domain directories (`audio_dsp`, `video_transcoding`, `davinci_automation`, `ingestion_hardware`, `viral_intelligence`). Each standalone module includes self-contained CLI entry points, programmatic APIs, and embedded test harnesses. Consult the cross-reference matrix below to map any legacy feature to its modernized vault tool.
---

# Master Archive Vault Catalog & Engineering Architecture Inventory

## 1. Executive Summary & Vault Mission

The **Media Pipeline Archive Vault** (`d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault`) serves as the permanent, authoritative intellectual property archive and modular tool repository for high-performance concert and festival video production.

During early development iterations across Track 2 (`content_creation`), valuable engineering algorithms were developed alongside flawed procedural scaffolding. This vault performs a complete extraction: **preserving the research-validated algorithms** while **permanently retiring the brittle legacy architecture**.

```
d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault\
├── audio_dsp/
│   ├── edm_drop_detector.py              # Tool 1: In-Memory RMS & O(N) Cumsum Drop Localization
│   └── ebu_r128_normalizer.py            # Tool 2: Two-Pass EBU R128 (-14 LUFS) & True Peak Limiting
├── video_transcoding/
│   ├── mobius_hdr_tonemapper.py          # Tool 3: Mobius Transform Stage Laser HDR-to-SDR Tone Mapper
│   ├── atempo_filter_compiler.py         # Tool 4: Dynamic Recursive FFmpeg atempo Chain Compiler
│   └── lossless_encoding_profiles.py     # Tool 5: Broadcast 9:16 Vertical NVENC & CPU Transcoder
├── davinci_automation/
│   ├── resolve_timeline_builder.py       # Tool 6: Frame-Accurate DaVinci Resolve Studio NLE Automation
│   └── http_range_video_streamer.py      # Tool 7: FastAPI HTTP 206 Partial Content Video Range Streamer
├── ingestion_hardware/
│   ├── samsung_adb_ingestor.py           # Tool 8: Wireless ADB Ingestor with Auto Blocker Bypass
│   ├── win32_three_tier_file_locker.py   # Tool 9: 3-Tier Windows File Lock Detector & Handle Prober
│   └── canonical_filename_normalizer.py  # Tool 10: Unicode NFKD Diacritic Normalizer & Folder Partitioner
├── viral_intelligence/
│   ├── evpi_viral_grading_model.py       # Tool 11: EVPI-5 Multimodal Grading Engine & Killswitch Dampeners
│   ├── council_of_the_drop.md            # Tool 12: 5-Persona Short-Form Creative Arbitration Blueprint
│   ├── safe_zone_seo_auditor.py          # Tool 13: YouTube Shorts & TikTok UI Exclusion Safe-Zone Auditor
│   └── youtube_content_id_guard.py       # Tool 14: Chunked Pre-Flight Unlisted Uploader & Content ID Guard
└── README.md                             # Tool 15: Master Vault Catalog & Cross-Reference Map
```

---

## 2. Complete Inventory of the 15 Vaulted Tools & Concepts

### Domain 1: Audio Signal Processing (`audio_dsp/`)

#### Tool 1: `audio_dsp/edm_drop_detector.py`
- **Focus**: High-speed EDM drop window localization without video demuxing.
- **Key Algorithms**:
  - Direct in-memory FFmpeg audio pipe (`-vn -ac 1 -ar 22050 -f s16le -`) streamed to `np.frombuffer`, eliminating all intermediate `.wav` disk I/O.
  - Pure NumPy sliding-window centered framing via `np.lib.stride_tricks.as_strided` (zero third-party dependencies required).
  - $O(N)$ prefix-sum cumulative array (`np.cumsum`) window energy maximization locating the exact 15s–30s drop window in $<50\,\text{ms}$.
  - Dual-engine fallback to `librosa` when present.

#### Tool 2: `audio_dsp/ebu_r128_normalizer.py`
- **Focus**: Broadcast-standard loudness normalization for YouTube Shorts and TikTok.
- **Key Algorithms**:
  - Two-pass EBU R128 normalization targeting integrated loudness of $-14.0 \pm 1.0\,\text{LUFS}$ and maximum True Peak $\le -1.5\,\text{dBTP}$.
  - 40Hz 2-pole Butterworth high-pass pre-filter (`highpass=f=40:poles=2`) eliminating stage sub-audible rumble and DC bias.
  - JSON parser extracting measured statistics from Pass 1 `stderr` (`input_i`, `input_tp`, `input_lra`, `input_thresh`, `target_offset`) to dynamically configure Pass 2 linear loudnorm injection.
  - Lookahead brickwall peak limiter (`alimiter=limit=-1.5dB:attack=5:release=50`) preventing inter-sample digital clipping.

---

### Domain 2: Video Transcoding & Color Science (`video_transcoding/`)

#### Tool 3: `video_transcoding/mobius_hdr_tonemapper.py`
- **Focus**: Preserving high-intensity concert stage lasers and pyro during HDR-to-SDR conversion.
- **Key Algorithms**:
  - Stage-laser Mobius tone-mapping filtergraph: `zscale=t=linear:npl=100,tonemap=mobius:desat=0.5,zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p`.
  - Non-linear compression of high-IRE laser spikes preventing channel clipping while preserving vibrant neon hue saturation.
  - Automatic transfer function detection (HLG BT.2100 vs HDR10 PQ) with safe BT.709 color-space clipping fallback.

#### Tool 4: `video_transcoding/atempo_filter_compiler.py`
- **Focus**: Audio time-stretching without pitch shift across arbitrary speed ratios.
- **Key Algorithms**:
  - Resolves FFmpeg's architectural constraint where a single `atempo` filter is limited strictly to speed factors between $0.5\times$ and $2.0\times$.
  - Recursively compiles optimal mathematical filter cascades (e.g., $4.0\times \to \text{atempo}=2.0, \text{atempo}=2.0$; $0.125\times \to \text{atempo}=0.5, \text{atempo}=0.5, \text{atempo}=0.5$).
  - Prevents phase cancellation, robotic fluttering, and FFmpeg filtergraph syntax rejections.

#### Tool 5: `video_transcoding/lossless_encoding_profiles.py`
- **Focus**: Standardized vertical 9:16 delivery formats and low-latency editing proxies.
- **Key Algorithms**:
  - Master Delivery Profile: 1080x1920 9:16 vertical video at 12–16 Mbps (VBR) using hardware-accelerated `hevc_nvenc` or `h264_nvenc` with CPU `libx264` fallback.
  - Proxy Profile: Fast 720p aspect-aware scaling (`scale='if(gt(ih,iw),720,-2)':'if(gt(ih,iw),-2,720)'`) at 2.5 Mbps with 22.05kHz 16-bit audio for instantaneous scrubbing.
  - 30ms linear crossfade micro-fade (`afade=t=in:ss=0:d=0.030,afade=t=out:st={dur-0.030}:d=0.030`) ensuring click-free looping on mobile video players.

---

### Domain 3: DaVinci Resolve Studio Automation (`davinci_automation/`)

#### Tool 6: `davinci_automation/resolve_timeline_builder.py`
- **Focus**: Headless NLE timeline generation and subclip assembly via Blackmagic Design scripting.
- **Key Algorithms**:
  - Cross-platform dynamic discovery of `DaVinciResolveScript` and `fusionscript` across Windows, macOS, and Linux system paths.
  - Exact integer frame calculation: $\text{start\_frame} = \text{round}(t_{\text{start}} \times \text{fps})$, preventing off-by-one subclip drift.
  - Non-destructive subclip injection: imports 4K master files into dedicated Media Pool bins and executes `media_pool.AppendToTimeline` with frame-accurate in/out bounds.
  - Project configuration: sets vertical 1080x1920 timeline resolution, `timelineMismatchResolution="ScaleToFill"`, and disables optimized media on export.
  - Concurrency Lock: enforces single-worker serialization (`asyncio.Semaphore(1)`) to protect Resolve Studio's GUI-bound scripting thread.

#### Tool 7: `davinci_automation/http_range_video_streamer.py`
- **Focus**: High-efficiency HTML5 video scrubbing and background render supervision.
- **Key Algorithms**:
  - HTTP 206 Partial Content byte-range streaming engine parsing `Range: bytes=start-end` headers, yielding 64KB chunks via `StreamingResponse` without loading multi-gigabyte video files into RAM.
  - Single-Job Subprocess Supervisor maintaining an `asyncio.Lock()` execution mutex that rejects overlapping pipeline requests with HTTP 409 Conflict.
  - Concurrent stdout/stderr streaming into an in-memory `deque(maxlen=2000)` ring buffer with two-stage graceful cancellation (SIGTERM $\to$ 3.0s wait $\to$ SIGKILL).

---

### Domain 4: Ingestion Hardware & OS Mechanics (`ingestion_hardware/`)

#### Tool 8: `ingestion_hardware/samsung_adb_ingestor.py`
- **Focus**: Wireless zero-touch footage pulling from Samsung Galaxy flagship mobile devices.
- **Key Algorithms**:
  - Headless wireless ADB mDNS discovery and pairing manager with exponential backoff and jitter.
  - Samsung One UI 6+ Auto Blocker bypass: executes `adb shell settings put global rampart_auto_enabled_switch_enabled 0` to enable programmatic ADB pulls without physical UI prompts.
  - Atomic `.part` pulling: pulls footage to temporary `.part` files, computes on-device Linux `sha256sum`, verifies local hash, and atomically renames upon clearance.

#### Tool 9: `ingestion_hardware/win32_three_tier_file_locker.py`
- **Focus**: Eliminating file race conditions and preventing FFmpeg from crashing on incomplete file writes.
- **Key Algorithms**:
  - Tier 1: In-flight extension filtering checking for active `.part`, `.tmp`, and `.crdownload` suffixes.
  - Tier 2: Native Win32 handle locking via `win32file.CreateFile(..., dwShareMode=0)` checking for exclusive access with Windows Error 5 (`ERROR_ACCESS_DENIED`) read-only fallback.
  - Tier 3: Byte-size growth debounce check polling file size over a 1.0s window to confirm file transfer completion.

#### Tool 10: `ingestion_hardware/canonical_filename_normalizer.py`
- **Focus**: Cross-platform filesystem safety and long-term directory performance.
- **Key Algorithms**:
  - Unicode NFKD decomposition: strips accent marks while preserving alphanumeric readability.
  - DJ Latin transliteration table mapping special artist characters (`Ø -> O`, `æ -> ae`, `ß -> ss`, `& -> and`).
  - Canonical format enforcement: `[Festival]_[Stage]_[Artist]_[Track]_[Year]_[Res]_[Version].[ext]`.
  - `DirectoryHealthGuard`: Automated 50-item folder capacity partitioning to prevent NTFS directory enumeration degradation when handling thousands of takes.

---

### Domain 5: Viral Intelligence & Quality Control (`viral_intelligence/`)

#### Tool 11: `viral_intelligence/evpi_viral_grading_model.py`
- **Focus**: Quantitative short-form retention prediction and multimodal grading.
- **Key Algorithms**:
  - Complete 5-parameter EVPI continuous scoring formulation:
    $$\text{EVPI}_{\text{raw}} = 0.30 \cdot H + 0.25 \cdot R + 0.20 \cdot V + 0.15 \cdot A + 0.10 \cdot P$$
    where $H$ = Hook Retention Velocity, $R$ = Drop Retention & Loop Dynamics, $V$ = Visual Engagement & Lasers, $A$ = Audio-Visual Coherence, and $P$ = Narrative Pacing.
  - Non-linear killswitch dampeners:
    $$\text{EVPI} = \text{Clamp}_{[0.0, 100.0]}(\text{EVPI}_{\text{raw}} \times K_{\text{audio}} \times K_{\text{format}} \times K_{\text{duration}})$$
    crushing scores on audio clipping ($K_{\text{audio}} = 0.10$), safe-zone collisions ($K_{\text{format}} = 0.50$), or duration bounds ($K_{\text{duration}} = 0.40$).
  - Strict Pydantic V2 schema models (`ViralScoreReport`, `HookMetrics`, `RetentionMetrics`, `FixRecommendation`) for Gemini Multimodal evaluation.

#### Tool 12: `viral_intelligence/council_of_the_drop.md`
- **Focus**: Cognitive multi-agent arbitration architecture replacing legacy film roles.
- **Key Algorithms**:
  - 5-Persona Creative Debate Model: Hook Architect (🪝, stop-rate), Kinetic Editor (⚡, BPM sync), Vibe Curator (🔮, tribal aesthetics), Retention Hacker (⏱️, looping & duration ceiling), Sound Seeder (🔥, audio virality).
  - Structured JSON debate arbitration flow and synthetic prompt generation.
  - Master multi-agent system prompt specification for Gemini and Claude.

#### Tool 13: `viral_intelligence/safe_zone_seo_auditor.py`
- **Focus**: Mobile UI occlusion prevention and algorithmic metadata packaging.
- **Key Algorithms**:
  - Geometric collision auditor testing overlay coordinates against YouTube Shorts ($900\times 1270\,\text{px}$) and TikTok ($920\times 1310\,\text{px}$) exclusion safe areas.
  - 5-7 hashtag clustering formula (1 broad EDM, 2 sub-genre, 1 event/year, 1 artist, 1 hook/community) preventing platform spam suppression.
  - 17-keyword regex filter blocking comment spam, phishing links, and fake ticket scalpers for YouTube Studio moderation.

#### Tool 14: `viral_intelligence/youtube_content_id_guard.py`
- **Focus**: Copyright protection, resumable uploads, and automated public release.
- **Key Algorithms**:
  - 5MB chunked resumable upload client for YouTube Data API v3.
  - Pre-flight unlisted upload policy with automated Content ID copyright claim polling loop.
  - Automated conditional branch: auto-promotes clean videos to Public; automatically quarantines videos if copyright blocks or severe claims occur.
  - Headless dry-run simulation mode for test environments.

#### Tool 15: `README.md`
- **Focus**: Master catalog, cross-reference origin map, and architectural guide.

---

## 3. Legacy Cross-Reference Map

The table below connects every vaulted tool back to its legacy file origin, highlighting the specific engineering gold extracted and the brittle scaffolding eliminated.

| # | Vaulted Tool Path | Legacy Origin File(s) | Research Value / Gold Extracted | Legacy Anti-Patterns Retired |
|---|---|---|---|---|
| **1** | `audio_dsp/edm_drop_detector.py` | `content_creation/audio_dsp.py`<br>`orchestrator.py:238-303` | In-memory FFmpeg pipe; vectorized strided window; $O(N)$ cumsum energy maximization. | Disk `.wav` file clutter; slow 4K video demuxing; Librosa dependency requirement. |
| **2** | `audio_dsp/ebu_r128_normalizer.py` | `content_creation/ffmpeg_processor.py`<br>`orchestrator.py:105-232` | Two-pass EBU R128 (-14 LUFS, -1.5 dBTP); 40Hz highpass; JSON stderr parser; brickwall peak limiter. | Hardcoded CLI parameters; failure to catch inter-sample audio clipping; missing tolerance checks. |
| **3** | `video_transcoding/mobius_hdr_tonemapper.py` | `content_creation/ffmpeg_processor.py:320-325`<br>`Antigravity_Media/...` | Mobius non-linear tonemapping; ITU-R BT.709 color conversion; laser saturation recovery. | Washed out stage laser highlights; color clipping; hardcoded gamma curves. |
| **4** | `video_transcoding/atempo_filter_compiler.py` | `baptism_of_music_brain/.../filtergraph.py` | Recursive dynamic FFmpeg `atempo` chaining handling speed factors $<0.5\times$ or $>2.0\times$. | Filtergraph crashes when speed was out of bounds; audio pitch warping. |
| **5** | `video_transcoding/lossless_encoding_profiles.py` | `content_creation/ffmpeg_processor.py`<br>`config.py:240-265` | Vertical 9:16 master profiles (12-16 Mbps); 720p proxies; 30ms linear loop crossfades. | Ad-hoc bitrate strings; missing crossfade loops causing audio pops on replay. |
| **6** | `davinci_automation/resolve_timeline_builder.py` | `content_creation/resolve_handoff.py`<br>`davinci_integration.py` | Cross-platform scripting API discovery; frame-accurate rounding (`round(t * fps)`); subclip bin imports. | Assuming DaVinci is always open; race conditions crashing the GUI; missing concurrency locks. |
| **7** | `davinci_automation/http_range_video_streamer.py` | `content_creation/remote_trigger.py:851-935`<br>`dashboard_backend.py:70-107` | HTTP 206 Partial Content byte-range video streaming; single-job async supervisor; 2000-line ring buffer. | In-memory ephemeral job loss; loading whole 4K files into RAM; unhandled parallel job collisions. |
| **8** | `ingestion_hardware/samsung_adb_ingestor.py` | `content_creation/samsung_ingest.py`<br>`media_pipeline/.../adb_connection_manager.py` | Headless wireless ADB mDNS discovery; Samsung One UI Auto Blocker bypass; atomic sha256 `.part` pulling. | Blocking `input()` CLI prompt; typos crashing runtime (`remote_md6`); consumer Quick Share reliance. |
| **9** | `ingestion_hardware/win32_three_tier_file_locker.py` | `baptism_of_music_brain/.../file_locker.py` | 3-tier file lock detector (extension filter, native `win32file.CreateFile` handle check, byte growth debounce). | FFmpeg reading partially-transferred files; race conditions across ingestion threads. |
| **10** | `ingestion_hardware/canonical_filename_normalizer.py` | `content_creation/ingest_assets.py`<br>`metadata_tracker.py` | Unicode NFKD decomposition; DJ Latin transliteration (`Ø -> O`); 50-item folder capacity partitioning. | Filesystem path encoding crashes on Windows; NTFS enumeration lag on massive flat directories. |
| **11** | `viral_intelligence/evpi_viral_grading_model.py` | `media_pipeline/grading/viral_schema.py`<br>`VIRAL_FORMULA.md` | 5-parameter EVPI continuous formulation; non-linear killswitch dampeners; strict Pydantic V2 schemas. | PySpark dependency entanglement; BigQuery simplex loop failing on unseeded databases. |
| **12** | `viral_intelligence/council_of_the_drop.md` | `content_creation/council_ui.html`<br>`agent_review_output.md:40-94` | 5-Persona Creative Debate Model; dopamine anticipation cycle; JSON arbitration contract. | Contract desynchronization leaving animated UI dead; legacy film pipeline failure on social feeds. |
| **13** | `viral_intelligence/safe_zone_seo_auditor.py` | `content_creation/metadata_tracker.py`<br>`config.py:130-180, 390-435` | YouTube Shorts (900x1270) & TikTok (920x1310) safe zones; 5-7 hashtag clustering; 17-keyword spam filter. | Safe-zone specs buried in 2,500-line HTML; hashtag stuffing causing algorithmic shadowbans. |
| **14** | `viral_intelligence/youtube_content_id_guard.py` | `content_creation/youtube_publisher.py`<br>`orchestrator.py:470-658` | Resumable 5MB chunked upload; pre-flight unlisted policy; Content ID polling loop; auto-promote vs quarantine. | Tightly coupled SQLite schema; crashing on missing OAuth credentials without dry-run fallback. |
| **15** | `README.md` | Master Catalog | Master architecture inventory, cross-reference origin map, and verification blueprint. | Fragmented tribal knowledge spread across 4 disconnected workspace directories. |

---

## 4. Summary of Retired Anti-Patterns & Modern Best Practices

### Retired Anti-Patterns
1. **Consumer Transport Dependencies (R35)**: Banned Google Quick Share (which dropped Wi-Fi connections and required manual "Accept" clicks). Replaced with headless wireless ADB and atomic `.part` verification.
2. **Hardcoded Drive Letters & Machine Paths (R19, R37)**: Eradicated hardcoded `G:\My Drive` and Windows user home directories (`C:\Users\noahp\...`) that crashed on alternate drive mounts. Replaced with dynamic path resolution.
3. **Monolithic UI Spaghetti**: Replaced single-file 2,500-line web dashboards (`index.html`) combining CSS, HTML, and JS with clean, headless REST/WebSocket APIs.
4. **Port Fragmentation**: Standardized divergent localhost ports (8000, 9051, 9067) into unified environment configurations.
5. **Interactive CLI Blocking**: Removed blocking `input()` calls in background daemons that froze headless automation pipelines.
6. **Filesystem Polling Overheads**: Replaced recursive directory scans (`rglob("*")` on every HTTP request) with indexed database manifests and 50-item partitioned directories.
7. **Unmanaged GPU Concurrency**: Eliminated concurrent NVENC/Resolve crashes by implementing explicit concurrency serialization semaphores (`asyncio.Semaphore`).

### Established Best Practices
1. **Trustless Broadcast Quality Control**: Enforces programmatic FFmpeg loudness and duration verification before any render is promoted to production.
2. **Audio-First Decoupling**: Extracts lightweight 22.05kHz 16-bit PCM `.wav` streams in-memory to execute drop detection and waveform generation in milliseconds without demuxing 4K masters.
3. **Non-Linear Killswitches**: Ensures that technical defects (audio clipping, safe-zone occlusion, horizontal letterboxing) immediately collapse viral scores rather than being masked by high visual scores.
4. **Resumable Pre-Flight Publishing**: Mandates unlisted uploads with automated Content ID polling before social assets can be promoted to public feeds.
5. **Separation of Concerns**: Strictly separates Data, Logic, and Presentation layers across all tools.

---

## 5. Independent Verification Guide

To verify the integrity and syntax of the entire vault:

```powershell
# 1. Compile all Python tools across all domains
python -m py_compile "d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault\audio_dsp\*.py"
python -m py_compile "d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault\video_transcoding\*.py"
python -m py_compile "d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault\davinci_automation\*.py"
python -m py_compile "d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault\ingestion_hardware\*.py"
python -m py_compile "d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault\viral_intelligence\*.py"

# 2. Test EVPI Viral Grading Model CLI
python "d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault\viral_intelligence\evpi_viral_grading_model.py" --hook 90 --retention 85 --visual 80 --coherence 85 --pacing 80 --json

# 3. Test Safe-Zone & SEO Auditor CLI
python "d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault\viral_intelligence\safe_zone_seo_auditor.py" --audit-box 100 350 800 100
python "d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault\viral_intelligence\safe_zone_seo_auditor.py" --generate-seo --artist "Sub Focus" --track "Desire" --event "EDC Vegas" --genre "dnb"

# 4. Test YouTube Content ID Guard CLI in Dry-Run Mode
python "d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault\viral_intelligence\youtube_content_id_guard.py" -v "d:\GOOGLE ANTIGRAVITY\content_creation\dummy_valid.mp4" -t "Festival Anthem ID" --dry-run --json
```

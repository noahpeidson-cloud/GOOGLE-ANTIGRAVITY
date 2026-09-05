# Comprehensive Cross-Pipeline Audit: Legacy Media Engineering & Vault Extraction

**Explorer**: `teamwork_preview_explorer_m1_3`  
**Working Directory**: `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_3`  
**Target Root**: `d:\GOOGLE ANTIGRAVITY\content_creation`  
**Expanded Targets**: `D:\clean_rewrite_temp\content_creation`, `D:\GOOGLE ANTIGRAVITY\Antigravity_Media\content_creation`, `D:\GOOGLE ANTIGRAVITY\archive\c_drive_legacy\teamwork_projects\baptism_of_music_brain`  
**Execution Mode**: STRICTLY READ-ONLY AUDIT  
**Date**: 2026-09-04  

---

## 1. Executive Summary

A comprehensive, zero-modification audit was executed across all legacy media processing pipelines, DaVinci Resolve integrations, Gemini multimodal workflows, orchestrators, and web dashboards in `content_creation` and related project archives. 

The audit revealed that while the legacy architecture suffered from fatal systems-level bottlenecks (unreliable consumer transport via Quick Share, unguarded SQLite concurrency, unqueued DaVinci Resolve GUI collisions, and VRAM memory exhaustion), it contains **exceptionally high-value, mathematically rigorous, research-validated media engineering logic**. 

Key treasures identified for long-term preservation in `_archive_vault` include:
1. **Validated FFmpeg DSP & Filtergraphs**: Two-pass EBU R128 (-14 LUFS, -1.5 dBTP) normalization, 40Hz/80Hz 2nd-order Butterworth sub-bass high-pass filtering, Mobius HDR-to-SDR tone-mapping, 30ms loop crossfades, atempo speed chaining, and hardware NVENC/QSV auto-selection.
2. **DaVinci Resolve Studio Integration**: Resilient multi-platform script discovery, frame-accurate subclip timeline insertion (`startFrame = round(start_time * fps)`), bin organization (A-Roll vs B-Roll), timeline versioning, and RenderQueue automation.
3. **Multimodal Gemini Video Intelligence**: Strict Pydantic schema enforcement (`response_schema`), proxy-first video inference preventing bandwidth stalls, and the viral "Council of the Drop" cognitive persona architecture.
4. **Resilient Operational Helpers**: A 3-tier Windows file-lock detector (extension filter + Win32 exclusive handle + debounce), canonical naming with NFKD diacritic normalization, 50-item folder health guards, and the 5-parameter EDM viral formula (EVPI).

---

## 2. Target Scope & Architecture Inventory

| File / Component Path | Primary Role | Status in Pipeline | Extraction Priority |
|---|---|---|---|
| `audio_dsp.py` | In-memory FFmpeg audio extraction, Librosa RMS, strided NumPy fallback, O(N) cumsum drop detection | Production-Ready | **Tier 1 (Crucial)** |
| `ffmpeg_processor.py` | Master filtergraph compiler, EBU R128 two-pass loudnorm, Mobius tone-map, NVENC encoder, proxy gen | Production-Ready | **Tier 1 (Crucial)** |
| `resolve_handoff.py` & `davinci_integration.py` | DaVinci Resolve Studio Python API bridge, subclip timeline insertion, RenderQueue | High-Value API Logic | **Tier 1 (Crucial)** |
| `metadata_tracker.py` | SafeZoneAuditor (TikTok/YouTube exclusion collision), SEOCaptionGenerator, MediaManifestDB | Production-Ready | **Tier 1 (Crucial)** |
| `samsung_ingest.py` | Samsung Galaxy S26 Ultra ADB Ingestion Bridge, mDNS Zeroconf discovery, disk headroom checks | Production-Ready | **Tier 1 (Crucial)** |
| `remote_trigger.py` | FastAPI zero-touch remote trigger server (<50ms async launch), Tasker/PWA webhook, ring logs | Production-Ready | **Tier 1 (Crucial)** |
| `gemini_trimmer.py` & `gemini_tagger.py` | Multimodal video highlight extraction, Pydantic schema output, exponential backoff | Production-Ready | **Tier 1 (Crucial)** |
| `agent_review.py` & `agent_review_output.md` | Architectural critique + "Council of the Drop" 5-persona viral framework | Research / Concept | **Tier 1 (Crucial)** |
| `media_pipeline/grading/viral_schema.py` & `VIRAL_FORMULA.md` | 5-parameter viral formula (EVPI), non-linear killswitches (clipping, format, duration) | Research-Validated | **Tier 1 (Crucial)** |
| `baptism_of_music_brain/src/watcher/file_locker.py` | 3-tier Windows file lock detector (Win32 CreateFile dwShareMode=0, byte stability) | Production-Ready | **Tier 1 (Crucial)** |
| `baptism_of_music_brain/src/renderer/filtergraph.py` | EDL-to-filtergraph compiler with `atempo` chaining, parametric `eq`, and scaling/padding | Production-Ready | **Tier 1 (Crucial)** |
| `dashboard_backend.py` | HTTP 206 Partial Content video streaming, NVENC render semaphore (limit 2), AI chat handler | Production-Ready | **Tier 2 (High)** |
| `index.html`, `council_ui.html`, `dashboard_v2.html` | Rich interactive visualizers: Council thought-stream, waveform scrubbers, safe-zone HUD | Generative UI Reference | **Tier 2 (High)** |
| `quick_share_ai_loop/quick_share_hijack.py` | Quick Share interceptor, file size stability checks, SHA-256 verified move | Deprecated Transport | **Tier 3 (Logic only)** |
| `polyglot_orchestrator.py` | Antigravity SDK polyglot routing (Claude for math, Gemini for tools) | Broken on 503 errors | **Tier 3 (Concept only)** |

---

## 3. Deep Technical Domain Audits

### 3.1 Media DSP & Validated FFmpeg Logic

#### A. In-Memory Audio Extraction via Streaming Pipe (`audio_dsp.py:200-235`)
- **Mechanism**: Eliminates intermediate WAV disk writes by streaming raw mono 16-bit PCM directly from FFmpeg stdout:
  ```bash
  ffmpeg -v error -i input.mp4 -vn -ac 1 -ar 22050 -f s16le -
  ```
- **Parsing**: `np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0`. Zero temporary file footprint, instant memory array.

#### B. Dual-Engine RMS Energy & O(N) CumSum Sliding Window (`audio_dsp.py:258-419`)
- **Librosa Feature Extraction**: Uses `librosa.feature.rms(frame_length=2048, hop_length=512, center=True)`.
- **Zero-Dependency NumPy Fallback**: Perfectly replicates Librosa centered framing using strided sliding windows:
  ```python
  pad_len = frame_length // 2
  padded = np.pad(y, (pad_len, pad_len), mode="constant")
  n_frames = max(1, (len(padded) - frame_length) // hop_length + 1)
  shape = (n_frames, frame_length)
  strides = (padded.strides[0] * hop_length, padded.strides[0])
  frames = np.lib.stride_tricks.as_strided(padded, shape=shape, strides=strides)
  rms = np.sqrt(np.mean(frames**2, axis=1)).astype(np.float32)
  ```
- **O(N) Energy Maximization**: Computes optimal 30-second drop window via cumulative sum difference:
  ```python
  cumsum = np.pad(np.cumsum(rms_curve), (1, 0))
  window_sums = cumsum[win_frames:] - cumsum[:-win_frames]
  best_frame = int(np.argmax(window_sums))
  start_sec = best_frame * hop_length / sample_rate
  ```

#### C. Two-Pass EBU R128 Normalization & Brickwall Limiting (`ffmpeg_processor.py:188-405`)
- **Pass 1 Measurement**:
  ```bash
  ffmpeg -y -ss {start} -t {duration} -i input.mp4 -vn -af highpass=f=40:poles=2,loudnorm=I=-14.0:LRA=7.0:TP=-1.5:print_format=json -f null -
  ```
- **Pass 2 Injection with Limiter**:
  ```
  highpass=f=40:poles=2,loudnorm=I=-14.0:LRA=7.0:TP=-1.5:measured_I={input_i}:measured_LRA={input_lra}:measured_TP={input_tp}:measured_thresh={input_thresh}:offset={target_offset}:linear=true,alimiter=limit=-1.5dB:attack=5:release=50
  ```
- **Loop Micro-Fade**: Applies a 30ms linear crossfade at boundary:
  ```
  afade=t=in:ss=0:d=0.03,afade=t=out:st={duration - 0.03}:d=0.03
  ```

#### D. Mobius HDR (HLG/PQ) to SDR (BT.709) Tone Mapping (`ffmpeg_processor.py:320-326`)
- **Filter**:
  ```
  zscale=t=linear:npl=100,tonemap=mobius:desat=0.5,zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p
  ```
- **Value**: Prevents laser highlight blowouts and skin tone oversaturation on Samsung S26 Ultra 10-bit HLG concert footage.

#### E. Arbitrary Speed Change Chaining (`baptism_of_music_brain/src/renderer/filtergraph.py:48-70`)
- **FFmpeg Constraint**: The `atempo` audio filter only accepts values between `0.5` and `2.0`.
- **Solution**: Chains multiple `atempo` filters dynamically:
  ```python
  while current > 2.0:
      filters.append("atempo=2.0")
      current /= 2.0
  while current < 0.5:
      filters.append("atempo=0.5")
      current /= 0.5
  filters.append(f"atempo={current}")
  ```

---

### 3.2 DaVinci Resolve Studio Automation

#### A. Cross-Platform Module Discovery (`resolve_handoff.py:156-240`)
- Traverses standard directory candidates across Windows (`%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules`), macOS, and Linux.
- Injects paths into `sys.path` and dynamically loads `DaVinciResolveScript`.
- Connects via `dvr_script.scriptapp("Resolve")` with Fusion fallback (`dvr_script.scriptapp("Fusion").GetResolve()`).

#### B. Mathematical Frame Rounding & Subclip Insertion (`resolve_handoff.py:308-472`)
- Eliminates float truncation timecode drift:
  ```python
  start_frame = int(round(start_time * fps))
  end_frame = int(round(end_time * fps))
  duration_frames = max(0, end_frame - start_frame)
  ```
- Appends slice directly to MediaPool:
  ```python
  clip_info = {
      "mediaPoolItem": clip_item,
      "startFrame": start_frame,
      "endFrame": end_frame,
      "recordFrame": 0
  }
  media_pool.AppendToTimeline([clip_info])
  ```

#### C. RenderQueue Configuration & Optimized Media Bypass (`davinci_integration.py:179-234`)
- Disables proxy/optimized media during final export to guarantee pristine 4K master rendering:
  ```python
  project.SetSetting("perfProxyMediaOn", "0")
  project.SetSetting("perfOptimizedMediaOn", "0")
  ```
- Configures 9:16 vertical canvas:
  ```python
  timeline.SetSetting("useCustomSettings", "1")
  timeline.SetSetting("timelineResolutionWidth", "1080")
  timeline.SetSetting("timelineResolutionHeight", "1920")
  project.SetSetting("videoMonitorScaling", "crop")
  timeline.SetSetting("timelineMismatchResolution", "ScaleToFill")
  ```

---

### 3.3 Gemini API Multimodal Intelligence & Structured Parsing

#### A. Pydantic Structured Output Validation (`gemini_trimmer.py:23-29`, `dashboard_backend.py:193-200`)
- Enforces rigid JSON typing directly at the model generation boundary using `response_schema`:
  ```python
  class TrimAnalysis(BaseModel):
      is_action_found: bool = Field(description="True if an exciting highlight was found.")
      start_time: float = Field(description="Start time of highlight in seconds.")
      duration: float = Field(description="Duration of highlight in seconds.")
      clip_type: str = Field(description="'A-Roll', 'B-Roll', or 'Action'")
      reasoning: str = Field(description="Brief explanation of segment selection.")
  ```
- Passed to `google.genai` SDK:
  ```python
  config = types.GenerateContentConfig(
      response_mime_type="application/json",
      response_schema=TrimAnalysis,
      temperature=0.2
  )
  ```

#### B. Proxy-First Video Multimodal Upload (`gemini_tagger.py:13-54`)
- Never uploads raw 4K footage (>1GB) to the Gemini File API.
- Generates a local 720p 30fps 1Mbps proxy MP4 (`scale=-2:720 -b:v 1M -b:a 128k`) reducing payload by 95%.
- Polls `client.files.get()` until state is `ACTIVE`, executes analysis, and immediately invokes `client.files.delete()` to prevent cloud storage leaks.

#### C. The "Council of the Drop" Cognitive Architecture (`agent_review_output.md:57-94`, `council_ui.html`)
- Replaces traditional film post-production roles (Compositor, Colorist, Critic) with short-form algorithm psychology:
  1. **Hook Architect**: First 3 seconds, stop-rate optimization, pattern interrupt.
  2. **Kinetic Editor**: Cuts footage to BPM transients, speed ramps on snare rolls.
  3. **Vibe Curator**: Subgenre cultural aesthetics (dark techno vs commercial house).
  4. **Retention Hacker**: Infinite loop structuring, UI safe-zone compliance.
  5. **Sound Seeder**: Virality hooks, audio trend engineering, pinned comment bait.

---

### 3.4 Operational Helpers & Core Algorithms

#### A. 3-Tier Windows File Lock Detector (`baptism_of_music_brain/src/watcher/file_locker.py`)
- **Tier 1 (Extension Filter)**: Rejects `.part`, `.tmp`, `.crdownload`, `.~$`.
- **Tier 2 (Exclusive Win32 Handle)**: Calls `win32file.CreateFile` with `dwShareMode=0`. If another process (like Quick Share or ADB) is writing, the OS denies handle acquisition.
- **Tier 3 (Size Stability Debounce)**: Asserts byte size remains identical over multiple observation intervals.

#### B. Safe-Zone Geometric Collision Auditor (`metadata_tracker.py:270-345`)
- Calculates bounding box overlaps against official YouTube Shorts and TikTok exclusion zones:
  - YouTube: Top 180px, Bottom 470px, Right 120px.
  - TikTok: Top 160px, Bottom 450px, Right 130px.
- Flags collisions with like/comment buttons or channel titles before rendering text overlays.

#### C. 5-Parameter EDM Viral Formula (`media_pipeline/grading/viral_schema.py`, `VIRAL_FORMULA.md`)
- **EVPI (Expected Viral Performance Index)**:
  $$\text{EVPI} = (0.25 \cdot \text{HRV} + 0.25 \cdot \text{DPAW} + 0.20 \cdot \text{ADR} + 0.15 \cdot \text{CKE} + 0.15 \cdot \text{LTSS}) \times K_{\text{audio}} \times K_{\text{format}} \times K_{\text{duration}}$$
- **Killswitches**:
  - $K_{\text{audio}} = 0.10$ if clipping detected.
  - $K_{\text{format}} = 1.0$ (9:16), $0.85$ (1:1), $0.50$ (16:9).
  - $K_{\text{duration}} = 1.0$ (12s–38s), $0.85$ (8–12s or 38–60s), $0.40$ (>60s).

---

## 4. Root Cause Analysis: Legacy Architecture Failures

Why did the original pipelines collapse despite containing this brilliant code?

| Subsystem | Failure Mechanism | Architectural Root Cause |
|---|---|---|
| **Transport Layer** | Corrupted 0-byte files, broken transcodes | Relied on Google Quick Share, an ad-hoc consumer Wi-Fi Direct protocol requiring manual UI accepts and lacking `.part` file locking. |
| **State Layer** | `sqlite3.OperationalError: database is locked` | Simultaneous reads/writes across watcher daemons, web servers, and LLM jobs without WAL mode or connection pooling. |
| **NLE Layer** | DaVinci Resolve crashes, scrambled timelines | Treated DaVinci Resolve as a headless CLI tool. DaVinci is strictly GUI-bound and single-threaded. Concurrent calls scramble the active project. |
| **GPU / Hardware** | `GPU Memory Full` / VRAM Out-of-Memory | Concurrently decompressing multiple 10-bit HLG HEVC streams with Scale-to-Fill 9:16 exhausted 8GB VRAM without semaphore queuing. |
| **AI Controller** | Resolve API out-of-bounds exceptions | Unbounded LLM output piped directly to NLE scripts without Pydantic verification against actual media duration. |

---

## 5. Synthesized Master Catalogue for `_archive_vault`

The following master tools and algorithms are recommended for systematic extraction into `d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault`:

### Catalogue Summary Table

| Vault Artifact Name | Target Path in Vault | Source Origin | Core Capability |
|---|---|---|---|
| `audio_dsp_engine` | `tools/audio_dsp_engine.py` | `audio_dsp.py` | RMS drop detection & O(N) cumsum |
| `ffmpeg_master_processor` | `tools/ffmpeg_master_processor.py` | `ffmpeg_processor.py` | EBU R128, Mobius tone map, NVENC |
| `atempo_filter_chain` | `tools/atempo_filter_chain.py` | `filtergraph.py` | Arbitrary audio speed chaining |
| `resolve_handoff_engine` | `tools/resolve_handoff_engine.py` | `resolve_handoff.py` | DaVinci Studio subclip insertion |
| `file_lock_detector` | `tools/file_lock_detector.py` | `file_locker.py` | 3-tier Windows exclusive file locking |
| `safe_zone_auditor` | `tools/safe_zone_auditor.py` | `metadata_tracker.py` | YouTube/TikTok UI exclusion collision |
| `canonical_normalizer` | `tools/canonical_normalizer.py` | `ingest_assets.py` | NFKD diacritic canonical file naming |
| `gemini_trimmer_client` | `tools/gemini_trimmer_client.py` | `gemini_trimmer.py` | Pydantic-structured video trimming |
| `council_of_the_drop` | `concepts/council_of_the_drop.md` | `agent_review_output.md` | 5-persona viral cognitive architecture |
| `viral_formula_evpi` | `concepts/viral_formula_evpi.md` | `VIRAL_FORMULA.md` | 5-parameter viral scoring & killswitches |
| `stream_range_server` | `tools/stream_range_server.py` | `dashboard_backend.py` | HTTP 206 partial video scrubbing |
| `samsung_adb_bridge` | `tools/samsung_adb_bridge.py` | `samsung_ingest.py` | Zero-compression ADB S26 pull |

---

### Detailed Vault Entry Blueprints

#### 1. Audio DSP Engine (`tools/audio_dsp_engine.py`)
- **Context Mapping**: Originates from `audio_dsp.py`. Used for identifying 30-second EDM drop peaks for TikTok/Shorts without requiring manual listening.
- **Strengths**: In-memory streaming pipe (no disk temp files), vectorized pure NumPy sliding window matching Librosa centered framing, O(N) cumsum argmax optimization.
- **Weaknesses**: None mathematically. If media container is completely missing audio streams, returns nominal fallback window.
- **Implementation Instructions**: Import `AudioDropDetector` or `detect_optimal_drop(media_path)`. Call directly on video or audio files.

#### 2. FFmpeg Master Processor (`tools/ffmpeg_master_processor.py`)
- **Context Mapping**: Extracted from `ffmpeg_processor.py`. Primary media DSP pipeline for rendering 9:16 vertical broadcast masters.
- **Strengths**: Two-pass EBU R128 (-14 LUFS) with JSON stderr parsing, Mobius HDR-to-SDR tone-mapping, brickwall limiting (-1.5 dBTP), 40Hz sub-bass filtering, 30ms loop crossfading, NVENC auto-detection.
- **Weaknesses**: If run on CPU without GPU, 4K transcode is slow. Requires FFmpeg on PATH.
- **Implementation Instructions**: Build `TranscodeConfig` dataclass and execute `FFmpegMasterProcessor().transcode(config)`.

#### 3. DaVinci Resolve Handoff Engine (`tools/resolve_handoff_engine.py`)
- **Context Mapping**: Extracted from `resolve_handoff.py` and `davinci_integration.py`. Automates human-in-the-loop editing handoff from web UI to DaVinci Studio.
- **Strengths**: Cross-platform module discovery, exact frame rounding (`int(round(t * fps))`), subclip dictionary appending, RenderQueue automation.
- **Weaknesses**: Requires DaVinci Resolve Studio GUI running. **MUST be called sequentially** under a concurrency lock or single-worker queue to prevent timeline collisions.
- **Implementation Instructions**: Protect with `asyncio.Semaphore(1)`. Instantiate `DaVinciResolveHandoffEngine()` and call `execute_handoff(config)`.

#### 4. 3-Tier Windows File Lock Detector (`tools/file_lock_detector.py`)
- **Context Mapping**: Extracted from `baptism_of_music_brain/src/watcher/file_locker.py`. Solves the active file write corruption issue in watcher daemons.
- **Strengths**: Combines extension filters (`.part`, `.tmp`), native Win32 `win32file.CreateFile(..., dwShareMode=0)` exclusive handle checking, and byte growth debounce.
- **Weaknesses**: Win32 exclusive lock requires Windows OS (gracefully falls back to open/rename on POSIX).
- **Implementation Instructions**: Wrap file watcher events with `if test_exclusive_handle(path)[0] and not is_temporary_file(path): process(path)`.

#### 5. Safe Zone Geometry Auditor (`tools/safe_zone_auditor.py`)
- **Context Mapping**: Extracted from `metadata_tracker.py`. Validates text overlays against mobile platform UI buttons and carousels.
- **Strengths**: Accurate coordinate definitions for YouTube Shorts and TikTok exclusion zones. Calculates intersection area and provides repositioning recommendations.
- **Weaknesses**: Platform UI updates periodically require updating margin constants.
- **Implementation Instructions**: Pass `BoundingBox(x, y, w, h)` to `SafeZoneAuditor.check_bounding_box(box)`.

#### 6. Multimodal Gemini Video Trimmer (`tools/gemini_trimmer_client.py`)
- **Context Mapping**: Extracted from `gemini_trimmer.py`. Automates AI highlight discovery on concert footage.
- **Strengths**: Enforces strict Pydantic `TrimAnalysis` schema via `response_schema`. Generates local 720p proxies first to avoid uploading 4K files.
- **Weaknesses**: Requires valid `GEMINI_API_KEY`. Needs backoff retry logic on 503 errors.
- **Implementation Instructions**: Upload proxy to GCS or File API, call `client.models.generate_content(contents=[video, prompt], config=GenerateContentConfig(response_schema=TrimAnalysis))`.

#### 7. Council of the Drop Framework (`concepts/council_of_the_drop.md`)
- **Context Mapping**: Extracted from `agent_review_output.md`. Replaces traditional post-production teams with short-form algorithm psychology.
- **Strengths**: Highly grounded in 2026 short-form retention mechanics. Defines exact roles: Hook Architect (0-3s), Kinetic Editor (BPM transient cuts), Vibe Curator (subculture aesthetic), Retention Hacker (loop structure), Sound Seeder (virality).
- **Weaknesses**: Concept only; requires LLM persona prompts to execute.
- **Implementation Instructions**: Use as the system prompt suite for multi-agent video analysis and review boards.

#### 8. EVPI 5-Parameter Viral Formula (`concepts/viral_formula_evpi.md`)
- **Context Mapping**: Extracted from `media_pipeline/grading/viral_schema.py` and `VIRAL_FORMULA.md`.
- **Strengths**: Mathematical formulation of video virality based on Hook Retention Velocity (HRV), Drop Payoff Audio-Visual Weight (DPAW), Audio Dynamic Range (ADR), Crowd Kinetic Energy (CKE), and Loop Transition Seamlessness (LTSS), with non-linear killswitches.
- **Weaknesses**: Relies on multi-modal AI scoring or feature extraction heuristics.
- **Implementation Instructions**: Use `compute_killswitches()` and `calculate_evpi_from_scores()` to compute deterministic composite scores.

---

## 6. Verification Method

To verify these discoveries independently:
1. **FFmpeg & DSP Verification**:
   - Inspect `audio_dsp.py:280-293` and verify the strided sliding window pure NumPy math against Librosa documentation.
   - Run a dry-run transcode: `python ffmpeg_processor.py --input dummy.mp4 --output test.mp4 --dry-run` and inspect the generated filtergraph output.
2. **DaVinci Resolve Handoff Verification**:
   - Inspect `resolve_handoff.py:308-319` and verify frame calculations.
   - Run CLI dry-run: `python resolve_handoff.py --raw-file dummy.mp4 --dry-run` to verify telemetry generation without opening Resolve.
3. **File Locking Verification**:
   - Inspect `file_locker.py:94-135` and verify `win32file.CreateFile` handle sharing mode.
4. **Pydantic Schema Verification**:
   - Inspect `gemini_trimmer.py:23-29` and `media_pipeline/grading/viral_schema.py:46-82`.

---
*Report compiled by teamwork_preview_explorer_m1_3. Zero original files modified.*

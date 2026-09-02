# Specification Report: High-Fidelity FFmpeg Rendering Engine & E2E Verification Suite

**Project:** `baptism_of_music_brain`  
**Author:** Specification Miner (`spec_miner_survey_3`)  
**Target Working Directory:** `C:\Users\noahp\teamwork_projects\baptism_of_music_brain`  
**Date:** 2026-08-27  

---

## 1. Executive Summary & Specification Scope

The `baptism_of_music_brain` system is an autonomous desktop video editing service combining FastAPI, Gemini Omni ML grading, and a desktop-class FFmpeg rendering engine. Its core objective is to intercept raw high-resolution media (e.g., 4K/8K Samsung S26 Ultra mobile footage), generate an Edit Decision List (EDL) with manual user override capabilities, execute physical video transformations with visually lossless fidelity, deliver the finalized video to a designated delivery directory, and mathematically verify output conformance using programmatic `ffprobe` assertions.

This specification document formalizes:
1. **FFmpeg High-Fidelity Video Rendering Engine**: Exact CLI parameter profiles, color/filtergraph transforms, audio mastering, and execution mechanics.
2. **Mathematical ffprobe Verification Constraints**: Formalized JSON schemas, mathematical validation bounds, tolerance thresholds, and assertion algorithms.
3. **E2E Verification Test Suite**: Procedural media generation pipelines (`lavfi`), end-to-end integration test harnesses (Ingestion -> Watchdog -> ML -> Override API -> FFmpeg -> Delivery -> ffprobe), and edge case matrices.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Encoding Profile | Visually Lossless H.264 (`x264_crf17`) | Master-quality H.264 profile using Constant Rate Factor 17, High profile, slow preset, yuv420p for universal consumer/Samsung playback | Raw 4K/1080p video stream, `-crf 17`, `-preset slow`, `-profile:v high`, `-pix_fmt yuv420p` | Visually lossless MP4 container (`avc1`) | Non-zero exit code if encoder unsupported; fallback to medium preset if slow times out | ORIGINAL_REQUEST.md § R2 & ffmpeg 8.0 probe |
| 2 | Encoding Profile | Studio Lossless H.264 4:4:4 (`x264_yuv444p`) | 4:4:4 chroma subsampling profile preserving full color resolution without chroma subsampling artifacts | Raw video stream, `-crf 17`, `-profile:v high444`, `-pix_fmt yuv444p` | Studio-grade MP4 container | Reject on playback devices lacking High 4:4:4 Profile decoder support | Empirical FFmpeg encoder inspection |
| 3 | Encoding Profile | High-Efficiency 10-Bit HEVC (`x265_crf16`) | 10-bit HDR/SDR HEVC profile with CRF 16, Main 10 profile, and `hvc1` tag for native Apple/Samsung hardware decoding | Raw 4K/8K video stream, `-c:v libx265`, `-crf 16`, `-pix_fmt yuv420p10le`, `-tag:v hvc1` | 10-bit HEVC MP4 container | Encoding failure if input color range metadata is incompatible | ORIGINAL_REQUEST.md § R2 & Samsung Camera probe |
| 4 | Encoding Profile | Hardware Accelerated NVENC (`hevc_nvenc`) | High-throughput GPU-accelerated video encoding with VBR and CQ 17 for low latency renders | Video stream, `-c:v hevc_nvenc`, `-preset p6`, `-tune hq`, `-rc vbr`, `-cq 17`, `-b:v 0` | GPU-rendered MP4 video | Fails if NVIDIA CUDA/NVENC driver unavailable; graceful fallback to `libx264` | `ffmpeg -encoders` probe |
| 5 | Encoding Profile | Master Intermediate ProRes (`prores_ks`) | Intra-frame ProRes 422 HQ / 4444 master container for zero-generation-loss editing handoff | Video stream, `-c:v prores_ks`, `-profile:v 3` (HQ) or `4` (4444), `-pix_fmt yuv422p10le` | `.mov` Master video file | Fails if container is not `.mov` / QuickTime | Empirical FFmpeg probing |
| 6 | Audio Profile | Studio AAC (`aac_320k`) | High-bitrate 320 kbps AAC stereo audio at 48 kHz sampling rate | Audio stream, `-c:a aac`, `-b:a 320k`, `-ar 48000`, `-ac 2` | 320 kbps AAC audio stream in MP4 | Fails if multi-channel source not downmixed | ORIGINAL_REQUEST.md § R2 & FFmpeg probe |
| 7 | Audio Profile | Uncompressed Master PCM (`pcm_s24le`) | 24-bit linear PCM audio for uncompressed acoustic preservation | Audio stream, `-c:a pcm_s24le`, `-ar 48000` | Linear PCM audio stream in `.mov`/`.mkv` | Fails in standard MP4 container (requires MOV/MKV or AAC in MP4) | FFmpeg container specification |
| 8 | Filtergraph | Multi-Segment EDL Trimming & Sync | Precise sub-second trimming of video and audio with timestamp reset (`setpts`/`asetpts`) | Video/Audio inputs, `trim=start=X:end=Y,setpts=PTS-STARTPTS`, `atrim=start=X:end=Y,asetpts=PTS-STARTPTS` | Time-synchronized trimmed streams `[v_n][a_n]` | Audio desync if `asetpts` omitted; duration mismatch if timestamps exceed source | Empirical filtergraph test execution |
| 9 | Filtergraph | Multi-Clip Stream Concatenation | Seamless sequential concatenation of multiple trimmed segments into unified video/audio streams | Stream labels `[v0][a0][v1][a1]...`, `concat=n=N:v=1:a=1[vout][aout]` | Unified single video stream `[vout]` and audio stream `[aout]` | Filtergraph failure if input stream frame rates or sample rates diverge without prior conform | FFmpeg filter graph probe |
| 10 | Filtergraph | Parametric Color Grading (`eq`) | Real-time adjustments of contrast, brightness, saturation, and gamma | Video stream `[v]`, `eq=contrast=C:brightness=B:saturation=S:gamma=G` | Color-graded video stream | Values outside normal bounds (e.g. negative contrast) cause extreme clipping | FFmpeg `eq` filter probing |
| 11 | Filtergraph | Precision Tone Curves (`curves`) | Master and per-channel RGB curve adjustments using spline coordinates | Video stream `[v]`, `curves=m='0/0 0.5/0.6 1/1':r='0/0 1/0.9'` | Contrast/tonally mapped video stream | Parse error if coordinate points are non-monotonic or malformed | FFmpeg `curves` filter probing |
| 12 | Filtergraph | Aspect Ratio Conform & Letterboxing (`scale` + `pad`) | Proportional scaling with aspect ratio preservation and automatic black padding for standard 16:9 or 9:16 canvas | Video stream `[v]`, `scale=w=W:h=H:force_original_aspect_ratio=decrease,pad=w=W:h=H:x=(ow-iw)/2:y=(oh-ih)/2:color=black` | Padded, aspect-corrected video stream | Even-dimension constraint violation if dimensions are odd numbers | Empirical scale+pad test |
| 13 | Filtergraph | Vertical Shorts Reframing with Blurred Background | Dynamic reframing of landscape (16:9) to portrait (9:16) with background blur stack | Video stream `[v]`, `split[bg][fg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg_b];[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg_s];[bg_b][fg_s]overlay=(W-w)/2:(H-h)/2` | 9:16 Vertical video with aesthetic blurred backdrop | High CPU cost if blur radius is excessive | Modern short-form video specification |
| 14 | Filtergraph | Smooth Crossfade Transitions (`xfade` + `acrossfade`) | Visual crossfade transitions between adjacent clips synchronized with audio crossfade | Video streams `[v0][v1]`, Audio streams `[a0][a1]`, `xfade=transition=fade:duration=D:offset=T`, `acrossfade=d=D` | Seamlessly transitioned output stream | Blank frames / audio dropouts if offset $T$ calculation does not account for prior clip lengths | Empirical xfade/acrossfade test |
| 15 | Filtergraph | EBU R128 Audio Loudness Normalization (`loudnorm`) | Compliance with standard broadcast/social audio loudness (-14 LUFS YouTube/Spotify or -16 LUFS EDM) | Audio stream `[a]`, `loudnorm=I=-14:LRA=11:TP=-1.5` | Normalized audio with consistent perceived loudness | Distortion if True Peak ($TP$) limit exceeds headroom | FFmpeg loudnorm filter spec |
| 16 | ffprobe Math | Programmatic Video Codec & Profile Verification | Automated verification that output video codec and profile match target specification | `ffprobe -v quiet -print_format json -show_streams <file>` -> `streams[codec_type=video]` | Boolean match (`codec_name == 'h264'`, `profile == 'High'`) | AssertionError raised if codec differs | ORIGINAL_REQUEST.md § Acceptance Criteria 1 |
| 17 | ffprobe Math | Programmatic Bitrate Threshold Verification | Validation that video and audio bitrates satisfy visually lossless thresholds | `format.bit_rate`, `streams[0].bit_rate`, `streams[1].bit_rate` | Assert $R_{video} \ge R_{min}$ and $R_{audio} \ge 315\text{ kbps}$ | AssertionError raised if output is over-compressed | ORIGINAL_REQUEST.md § Acceptance Criteria 1 |
| 18 | ffprobe Math | Resolution & Aspect Ratio Invariance | Verification that output width, height, and display aspect ratio match expected pixel dimensions | `width`, `height`, `sample_aspect_ratio`, `display_aspect_ratio` | Assert $W_{out} == W_{tgt}$, $H_{out} == H_{tgt}$, $W \pmod 2 == 0$, $H \pmod 2 == 0$ | AssertionError raised if dimensions scale improperly or have odd parity | ffprobe schema specification |
| 19 | ffprobe Math | Frame Rate Precision Check | Evaluates fractional frame rates (`r_frame_rate` / `avg_frame_rate`) against target FPS tolerance | `r_frame_rate = "num/den"` | Assert $|\frac{\text{num}}{\text{den}} - \text{target\_fps}| \le 0.05$ | AssertionError if frame rate is dropped or jittered | ffprobe stream metadata |
| 20 | ffprobe Math | Color Metadata & Pixel Format Assertions | Programmatic check for pixel format (`yuv420p`), color range (`tv`), color primaries (`bt709`), and matrix coefficients | `pix_fmt`, `color_range`, `color_space`, `color_primaries`, `color_transfer` | Assert metadata strings match target profile | AssertionError if color tagging is stripped | FFmpeg color metadata spec |
| 21 | Test Suite | Procedural Video Clip Generator (`testsrc2`) | Deterministic zero-dependency generation of synthetic video clips with moving clocks, color bars, and audio tones | `ffmpeg -f lavfi -i testsrc2=duration=D:size=WxH:rate=FPS -f lavfi -i sine=frequency=440:duration=D` | Valid, playable `.mp4` test media | Fails if lavfi sources are disabled | User Rule R21 & ffmpeg lavfi probe |
| 22 | Test Suite | High-Entropy Synthetic Video Generator | High-entropy test clips with noise overlay to force realistic bitrate consumption during CRF encoding | `testsrc2` + `noise=alls=30:allf=t+u` + `sine` | High-bitrate (>100 Mbps) test clip | High memory usage during generation | Empirical high-entropy probe |
| 23 | Test Suite | Ingestion Drop Watcher & Atomic Staging | Filesystem monitor detecting new files in `ingest/`, checking write lock release, computing SHA-256 hash | Monitored directory `ingest/`, atomic rename from `.tmp` | Job created in state store with status `INGESTED` | Ignores `.tmp` / `.part` files until atomic rename completes | ORIGINAL_REQUEST.md § R1 |
| 24 | Test Suite | Mock ML Decision Loop | Deterministic mock engine simulating Gemini Omni grading output for fast, offline E2E testing | Video file metadata and synthetic frames | Structured Pydantic `EditDecisionList` | Raises validation error if schema contract violated | ORIGINAL_REQUEST.md § Acceptance Criteria 2 |
| 25 | Test Suite | FastAPI Manual Override REST Interface | REST API enabling inspection, mutation of EDL segments/color/encoding, and render approval | HTTP `PUT /api/v1/jobs/{job_id}/edl`, `POST /api/v1/jobs/{job_id}/render` | Updated EDL JSON, 202 Accepted render job response | 400 Bad Request on invalid timestamps; 404 on unknown job | ORIGINAL_REQUEST.md § R1 & R2 |
| 26 | Test Suite | Asynchronous FFmpeg Job Runner & Progress Tracker | Background execution engine running FFmpeg CLI with non-blocking stdout/stderr and progress parsing | Validated EDL, output directory path | Rendered video file, Job progress state (0-100%) | Job marked `FAILED` with stderr capture on non-zero exit | Architecture specification |
| 27 | Test Suite | Atomic Delivery Pipeline & Verification | Atomic move of completed render to `delivery/<id>.mp4` and delivery manifest recording | Completed `.rendering.mp4` file | Published delivery file with SHA-256 hash | Rollback temporary files on render failure | ORIGINAL_REQUEST.md § R3 |
| 28 | Test Suite | Automated End-to-End Test Harness | Single automated Pytest suite exercising Ingest -> Detect -> ML -> Override -> Render -> Delivery -> ffprobe | Synthetic test clips dropped in `ingest/` | 100% Green test suite output with ffprobe assertions | Fails if any pipeline step fails or ffprobe assertion fails | ORIGINAL_REQUEST.md § Acceptance Criteria 1 & 2 |

---

## 3. Detailed Specifications for FFmpeg High-Fidelity Lossless Video Rendering Engine

### 3.1 Encoding Profiles Specification

To fulfill the requirement of "visually lossless quality without catastrophic file bloat" (ORIGINAL_REQUEST.md § R2), the engine must support four standardized encoding profiles:

```
+---------------------------------------------------------------------------------------------------+
| Profile ID          | Video Codec | Preset  | CRF / CQ | Pixel Format | Audio Codec | Target Bitrate   |
+---------------------------------------------------------------------------------------------------+
| x264_crf17 (Default)| libx264     | slow    | 17       | yuv420p      | aac @ 320k  | 35 - 60 Mbps (4K)|
| x264_yuv444p        | libx264     | slow    | 17       | yuv444p      | aac @ 320k  | 50 - 90 Mbps (4K)|
| x265_crf16 (10-bit) | libx265     | medium  | 16       | yuv420p10le  | aac @ 320k  | 25 - 45 Mbps (4K)|
| prores_hq (Master)  | prores_ks   | N/A     | profile 3| yuv422p10le  | pcm_s24le   | ~220 Mbps (4K)   |
| hevc_nvenc (GPU)    | hevc_nvenc  | p6 (hq) | cq 17    | yuv420p      | aac @ 320k  | 30 - 50 Mbps (4K)|
+---------------------------------------------------------------------------------------------------+
```

#### Detailed Profile Parameters:

1. **Profile `x264_crf17` (Visually Lossless Standard)**:
   - **CLI Flags**:
     ```bash
     -c:v libx264 -preset slow -crf 17 -profile:v high -level 5.2 -pix_fmt yuv420p \
     -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
     -movflags +faststart -c:a aac -b:a 320k -ar 48000 -ac 2
     ```
   - **Rationale**: CRF 17 is universally recognized in digital video engineering as visually indistinguishable from uncompressed source footage (VMAF > 98.5). `yuv420p` guarantees hardware decoding support on Samsung Galaxy devices, Apple iOS, Android, and web browsers. `-movflags +faststart` places the `moov` atom at the beginning of the file for instant streaming and playback.

2. **Profile `x265_crf16` (High-Efficiency 10-Bit)**:
   - **CLI Flags**:
     ```bash
     -c:v libx265 -preset medium -crf 16 -pix_fmt yuv420p10le \
     -tag:v hvc1 -c:a aac -b:a 320k -ar 48000 -ac 2
     ```
   - **Rationale**: `-tag:v hvc1` is strictly mandatory for native hardware playback in Apple QuickTime and Samsung Gallery (without it, FFmpeg tags HEVC as `hev1`, which causes black screen issues on mobile decoders). 10-bit pixel format (`yuv420p10le`) prevents color banding in gradients.

3. **Profile `prores_hq` (Master Archive)**:
   - **CLI Flags**:
     ```bash
     -c:v prores_ks -profile:v 3 -vendor apl0 -pix_fmt yuv422p10le \
     -c:a pcm_s24le -ar 48000
     ```
   - **Container**: `.mov` (QuickTime format).

---

### 3.2 Filtergraph Grammar & Syntax for EDL Operations

The Edit Decision List (EDL) is compiled into a single complex filtergraph (`-filter_complex`).

#### 3.2.1 Trimming and Timestamp Synchronization
For each segment $i \in [0, N-1]$ from input file index $k$:
- **Video Trim Filter**: `[{k}:v]trim=start={start_s}:end={end_s},setpts=PTS-STARTPTS[v{i}_raw]`
- **Audio Trim Filter**: `[{k}:a]atrim=start={start_s}:end={end_s},asetpts=PTS-STARTPTS[a{i}_raw]`

*Rule*: Both `setpts=PTS-STARTPTS` and `asetpts=PTS-STARTPTS` MUST be applied immediately following `trim` / `atrim` to reset presentation timestamps to zero; failing to do so causes frame freezing and catastrophic audio-video desync.

#### 3.2.2 Color Grading Filter Pipeline
Applied to each video segment `[v{i}_raw]` before concatenation:
- **Parameters**:
  - `contrast` $\in [0.5, 2.0]$ (Default: `1.0`)
  - `brightness` $\in [-1.0, 1.0]$ (Default: `0.0`)
  - `saturation` $\in [0.0, 3.0]$ (Default: `1.0`)
  - `gamma` $\in [0.1, 10.0]$ (Default: `1.0`)
- **Filter Syntax**:
  ```
  [v{i}_raw]eq=contrast={c}:brightness={b}:saturation={s}:gamma={g}[v{i}_color]
  ```
- **Optional Curve Modification**:
  ```
  [v{i}_color]curves=m='0/0 0.5/0.55 1/1'[v{i}_curved]
  ```

#### 3.2.3 Aspect Ratio Conform, Scaling & Padding
To ensure all segments share identical dimensions prior to concatenation:
- **Target Resolution**: $(W_{target}, H_{target})$, e.g. `3840x2160` (4K UHD) or `1080x1920` (9:16 Shorts).
- **Scale with Aspect Ratio Preservation & Centered Letterbox/Pillarbox**:
  ```
  [v{i}_curved]scale=w={W}:h={H}:force_original_aspect_ratio=decrease:flags=lanczos,pad=w={W}:h={H}:x=(ow-iw)/2:y=(oh-ih)/2:color=black[v{i}_scaled]
  ```

#### 3.2.4 Audio Normalization & Gain
- **Volume Adjustment**: `volume={gain_db}dB`
- **EBU R128 Loudness**: `loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}`
  - Standard Social/Music targets: `I=-14.0`, `TP=-1.5`, `LRA=11.0`
- **Filter Syntax**:
  ```
  [a{i}_raw]volume={gain_db}dB,loudnorm=I=-14:TP=-1.5:LRA=11[a{i}_norm]
  ```

#### 3.2.5 Concatenation (`concat`)
When no transition overlaps exist:
```
[v0_scaled][a0_norm][v1_scaled][a1_norm]...[v{N-1}_scaled][a{N-1}_norm]concat=n={N}:v=1:a=1[vout][aout]
```

#### 3.2.6 Crossfade Transitions (`xfade` & `acrossfade`)
When two clips have a crossfade transition of duration $D$:
- Clip 0 duration: $L_0$
- Transition offset: $T = L_0 - D$
- **Filter Syntax**:
  ```
  [v0_scaled][v1_scaled]xfade=transition=fade:duration={D}:offset={T}[vout];
  [a0_norm][a1_norm]acrossfade=d={D}[aout]
  ```

---

### 3.3 Complete Compiled FFmpeg Command Template

```bash
ffmpeg -y -hide_banner \
  -i "C:/path/to/raw_clip_1.mp4" \
  -i "C:/path/to/raw_clip_2.mp4" \
  -filter_complex "
    [0:v]trim=start=0:end=4,setpts=PTS-STARTPTS,eq=contrast=1.05:saturation=1.1,scale=3840:2160:force_original_aspect_ratio=decrease:flags=lanczos,pad=3840:2160:(ow-iw)/2:(oh-ih)/2:black[v0];
    [0:a]atrim=start=0:end=4,asetpts=PTS-STARTPTS,loudnorm=I=-14:TP=-1.5:LRA=11[a0];
    [1:v]trim=start=2:end=7,setpts=PTS-STARTPTS,eq=contrast=1.0:saturation=1.0,scale=3840:2160:force_original_aspect_ratio=decrease:flags=lanczos,pad=3840:2160:(ow-iw)/2:(oh-ih)/2:black[v1];
    [1:a]atrim=start=2:end=7,asetpts=PTS-STARTPTS,loudnorm=I=-14:TP=-1.5:LRA=11[a1];
    [v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]
  " \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -preset slow -crf 17 -profile:v high -level 5.2 -pix_fmt yuv420p \
  -c:a aac -b:a 320k -ar 48000 -ac 2 \
  -movflags +faststart \
  -progress pipe:1 \
  "C:/path/to/delivery/rendered_output.mp4"
```

---

## 4. Detailed Specifications for Mathematical ffprobe Programmatic Verification Constraints

### 4.1 Automated Inspection Command

The verification harness must invoke `ffprobe` using JSON formatted output:
```bash
ffprobe -v quiet -print_format json -show_format -show_streams "path/to/output.mp4"
```

### 4.2 Stream Extraction & Invariant Schema

```
ffprobe_json
├── format
│   ├── filename: str
│   ├── duration: str (float parseable)
│   ├── size: str (int parseable)
│   └── bit_rate: str (int parseable)
└── streams: list[dict]
    ├── [0] (Video Stream)
    │   ├── codec_type: "video"
    │   ├── codec_name: str ("h264", "hevc", "prores")
    │   ├── profile: str ("High", "Main 10", "HQ")
    │   ├── width: int (e.g. 3840)
    │   ├── height: int (e.g. 2160)
    │   ├── pix_fmt: str ("yuv420p", "yuv420p10le", "yuv422p10le")
    │   ├── r_frame_rate: str (e.g. "24/1", "30/1", "30000/1001", "60/1")
    │   ├── avg_frame_rate: str
    │   ├── color_range: str ("tv" or "pc")
    │   ├── color_space: str ("bt709", "bt2020nc")
    │   └── bit_rate: Optional[str] (int parseable)
    └── [1] (Audio Stream)
        ├── codec_type: "audio"
        ├── codec_name: str ("aac", "pcm_s24le", "flac")
        ├── sample_rate: str ("48000")
        ├── channels: int (2)
        ├── channel_layout: str ("stereo")
        └── bit_rate: Optional[str] (int parseable)
```

### 4.3 Deterministic Verification Math & Assertions

```python
def verify_rendered_video(file_path: str, expected_spec: dict) -> bool:
    """Programmatically asserts that the rendered video mathematically satisfies visually lossless constraints."""
    data = run_ffprobe_json(file_path)
    
    # 1. Container & Stream Existence Assertions
    assert "format" in data, "ffprobe JSON missing 'format' key"
    assert "streams" in data and len(data["streams"]) >= 2, "Output must contain at least 1 video and 1 audio stream"
    
    video_stream = next(s for s in data["streams"] if s.get("codec_type") == "video")
    audio_stream = next(s for s in data["streams"] if s.get("codec_type") == "audio")
    
    # 2. Codec & Profile Verification
    assert video_stream["codec_name"].lower() == expected_spec["video_codec"].lower(), \
        f"Video codec mismatch: expected {expected_spec['video_codec']}, got {video_stream['codec_name']}"
    
    if "video_profile" in expected_spec:
        assert expected_spec["video_profile"].lower() in video_stream.get("profile", "").lower(), \
            f"Video profile mismatch: expected {expected_spec['video_profile']}, got {video_stream.get('profile')}"

    # 3. Spatial Resolution Preservation Math
    assert int(video_stream["width"]) == expected_spec["target_width"], \
        f"Width mismatch: expected {expected_spec['target_width']}, got {video_stream['width']}"
    assert int(video_stream["height"]) == expected_spec["target_height"], \
        f"Height mismatch: expected {expected_spec['target_height']}, got {video_stream['height']}"
    assert int(video_stream["width"]) % 2 == 0, "Video width must be even for standard macroblock alignment"
    assert int(video_stream["height"]) % 2 == 0, "Video height must be even for standard macroblock alignment"

    # 4. Pixel Format & Color Space Assertions
    assert video_stream["pix_fmt"] == expected_spec["pix_fmt"], \
        f"Pixel format mismatch: expected {expected_spec['pix_fmt']}, got {video_stream['pix_fmt']}"
        
    # 5. Temporal Frame Rate Precision Math
    fps_str = video_stream.get("r_frame_rate", "0/1")
    num, den = map(float, fps_str.split("/"))
    calculated_fps = num / den if den != 0 else 0.0
    assert abs(calculated_fps - expected_spec["target_fps"]) <= 0.05, \
        f"FPS deviation out of bounds: expected {expected_spec['target_fps']}, got {calculated_fps:.3f}"

    # 6. Audio Fidelity Constraints
    assert audio_stream["codec_name"].lower() == expected_spec["audio_codec"].lower(), \
        f"Audio codec mismatch: expected {expected_spec['audio_codec']}, got {audio_stream['codec_name']}"
    assert int(audio_stream["sample_rate"]) == expected_spec.get("sample_rate", 48000), \
        f"Audio sample rate mismatch: expected 48000 Hz, got {audio_stream['sample_rate']}"
    assert int(audio_stream["channels"]) == expected_spec.get("channels", 2), \
        f"Audio channels mismatch: expected 2, got {audio_stream['channels']}"

    # 7. Bitrate Threshold Validation Math
    # Total container bitrate or video stream bitrate
    fmt_bitrate = float(data["format"].get("bit_rate", 0))
    video_bitrate = float(video_stream.get("bit_rate", 0))
    effective_video_bitrate = video_bitrate if video_bitrate > 0 else (fmt_bitrate - 320000)
    
    if expected_spec.get("min_video_bitrate_kbps"):
        min_bps = expected_spec["min_video_bitrate_kbps"] * 1000
        assert effective_video_bitrate >= min_bps, \
            f"Bitrate starvation: expected >= {min_bps/1000} kbps, got {effective_video_bitrate/1000} kbps"

    # Audio bitrate assertion (nominal 320 kbps -> minimum 310 kbps)
    audio_bitrate = float(audio_stream.get("bit_rate", 0))
    if expected_spec["audio_codec"] == "aac" and audio_bitrate > 0:
        assert audio_bitrate >= 310000, f"AAC audio bitrate below 310 kbps threshold: got {audio_bitrate/1000} kbps"

    # 8. Duration Invariance Math
    fmt_duration = float(data["format"]["duration"])
    expected_duration = expected_spec["expected_duration"]
    assert abs(fmt_duration - expected_duration) <= 0.15, \
        f"Duration mismatch: expected {expected_duration:.2f}s, got {fmt_duration:.2f}s (delta > 150ms)"

    return True
```

---

## 5. Detailed Specifications for E2E Verification Test Suite

### 5.1 Procedural Test Media Generator

The test suite must NOT depend on manual downloads or gigabyte-sized test assets. It must generate synthetic reference clips procedurally on-the-fly using FFmpeg's `lavfi` filter framework.

```python
import subprocess
import os

def generate_procedural_test_clip(
    output_path: str,
    duration: float = 3.0,
    resolution: str = "3840x2160",
    fps: int = 30,
    pattern: str = "testsrc2",
    freq: int = 440,
    add_noise: bool = True
) -> str:
    """
    Procedurally creates a valid high-fidelity MP4 test video with audio.
    Supports 4K, 1080p, 9:16 portrait, SMPTE bars, and high-entropy noise.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    if add_noise:
        # High-entropy pattern to exercise realistic video bitrate encoding
        filter_str = f"[{pattern}=duration={duration}:size={resolution}:rate={fps}]noise=alls=25:allf=t+u[v]"
    else:
        filter_str = f"[{pattern}=duration={duration}:size={resolution}:rate={fps}][v]"

    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-f", "lavfi", "-i", f"{pattern}=duration={duration}:size={resolution}:rate={fps}",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}:sample_rate=48000",
        "-filter_complex", "[0:v]noise=alls=20:allf=t+u[v]" if add_noise else "[0:v]copy[v]",
        "-map", "[v]" if add_noise else "0:v",
        "-map", "1:a",
        "-c:v", "libx264", "-crf", "17", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2",
        output_path
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return output_path
```

### 5.2 End-to-End Pipeline Verification Architecture

The complete integration test flows through seven discrete operational steps:

```
[Step 1: Ingest Drop]  ──► Drops `synthetic_4k.mp4` into `data/ingest/` (via atomic `.tmp` rename)
          │
          ▼
[Step 2: Watchdog]     ──► Ingest watcher detects file, confirms write complete, computes SHA-256
          │
          ▼
[Step 3: ML Decision]  ──► Gemini Omni (or Mock Engine) analyzes video -> generates initial EDL
          │
          ▼
[Step 4: Manual API]   ──► Test client calls `PUT /api/v1/jobs/{id}/edl` to mutate trim/color params
          │                Test client calls `POST /api/v1/jobs/{id}/render` to approve rendering
          │
          ▼
[Step 5: FFmpeg Exec]  ──► Renderer compiles filtergraph -> launches FFmpeg -> tracks progress (0-100%)
          │
          ▼
[Step 6: Delivery Drop]──► Finalized file atomically placed in `data/delivery/{id}_final.mp4`
          │
          ▼
[Step 7: ffprobe Check]──► Automated `verify_rendered_video()` asserts 100% mathematical conformance
```

### 5.3 FastAPI Test Endpoints & Contract Specification

| Method | Path | Request Body | Response Body | Description |
|---|---|---|---|---|
| `GET` | `/api/v1/jobs` | None | `List[JobSummaryResponse]` | Lists all active, queued, and completed jobs |
| `GET` | `/api/v1/jobs/{job_id}` | None | `JobDetailResponse` (includes source metadata & current EDL) | Fetches full state of a specific video job |
| `PUT` | `/api/v1/jobs/{job_id}/edl` | `EditDecisionListUpdate` | `JobDetailResponse` (with updated EDL) | Allows manual user overrides of trim timestamps, color grading parameters, scaling, and audio gain before render |
| `POST` | `/api/v1/jobs/{job_id}/render` | Optional `RenderOverrideConfig` | `JobStatusResponse` (status: `QUEUED`) | Approves the job and queues the FFmpeg rendering process |
| `GET` | `/api/v1/jobs/{job_id}/status` | None | `JobProgressResponse` (status, percent_complete, fps, elapsed_s, error) | Real-time polling endpoint for UI and integration tests |

---

## 6. Edge Cases & Observed Failure Behaviors

| # | Feature | Input / Condition | Observed Behavior & Required Handling |
|---|---------|-------------------|---------------------------------------|
| 1 | File Watcher | Partial file write during slow network/disk ingest | Watchdog fires immediately upon file creation; attempting to probe or read an incomplete file fails. **Solution:** Watcher must either ignore files until `.tmp` extension is removed or poll for stable file size and write lock release before triggering ML pipeline. |
| 2 | Trimming | Segment `start_time >= end_time` or `start_time < 0` | Pydantic validation rejects with `ValueError: start_time must be strictly less than end_time and >= 0.0`. FastAPI returns `422 Unprocessable Entity`. |
| 3 | Trimming | Segment `end_time` exceeds source video duration | FFmpeg truncates at source EOF without error, resulting in a rendered video shorter than planned. **Solution:** Validator must probe source duration via `ffprobe` and clamp `end_time = min(end_time, source_duration)`. |
| 4 | Filtergraph | Odd pixel dimensions (e.g. `scale=1921:1080`) | Encoder fails with `[libx264 @ ...] width not divisible by 2 (1921x1080)`. **Solution:** Auto-enforce `trunc(ow/2)*2` in scale filters: `scale=w='trunc(iw*min(3840/iw,2160/ih)/2)*2':h='trunc(ih*min(3840/iw,2160/ih)/2)*2'`. |
| 5 | Filtergraph | Stream label mismatch or omitted audio filter | FFmpeg terminates with `Filtergraph cannot find stream [a0]`. **Solution:** Compiler must maintain strict bidirectional video/audio stream label tracking across all branches. |
| 6 | Concatenation | Inputs with differing frame rates (e.g., 24fps and 60fps) | `concat` filter drops frames or experiences audio drift. **Solution:** Force standard output frame rate using `-r {target_fps}` or `fps=fps={target_fps}` filter prior to concatenation. |
| 7 | FFmpeg Process | Rendering process hangs or crashes (OOM) | Subprocess deadlocks if stdout/stderr pipe buffers fill up. **Solution:** Asynchronous stream reading via `asyncio.subprocess` or separate worker threads; timeout enforcement with SIGKILL on threshold breach. |
| 8 | Color Grading | Extreme color values (e.g. `contrast=100.0`, `saturation=-5.0`) | Severe clipping or inverted color artifacts. **Solution:** Pydantic schema enforces bounded ranges: `contrast: float = Field(ge=0.0, le=3.0)`, `saturation: float = Field(ge=0.0, le=3.0)`. |
| 9 | Audio Normalization | Extremely quiet or silent audio stream | `loudnorm` filter attempts excessive gain amplification (+30dB) introducing noise floor amplification. **Solution:** Apply maximum gain limit clamp (`volume=...,loudnorm=...:linear=true`). |
| 10 | Delivery Directory | Destination disk full or delivery directory write-protected | Render succeeds in temp dir but delivery move fails. **Solution:** Pre-flight disk space check; atomic transaction with descriptive error state `DELIVERY_FAILED` and persistent staging copy. |

---

## 7. Concrete Implementation Data Models & Pydantic Schemas

```python
from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator

class VideoEncodingProfile(str, Enum):
    X264_CRF17 = "x264_crf17"
    X264_YUV444P = "x264_yuv444p"
    X265_CRF16 = "x265_crf16"
    PRORES_HQ = "prores_hq"
    HEVC_NVENC = "hevc_nvenc"

class AudioEncodingProfile(str, Enum):
    AAC_320K = "aac_320k"
    PCM_S24LE = "pcm_s24le"
    FLAC = "flac"

class ColorGradingConfig(BaseModel):
    contrast: float = Field(default=1.0, ge=0.0, le=3.0, description="Contrast multiplier (1.0 = normal)")
    brightness: float = Field(default=0.0, ge=-1.0, le=1.0, description="Brightness offset (0.0 = normal)")
    saturation: float = Field(default=1.0, ge=0.0, le=3.0, description="Color saturation multiplier (1.0 = normal)")
    gamma: float = Field(default=1.0, ge=0.1, le=10.0, description="Gamma curve adjustment (1.0 = normal)")

class AudioAdjustConfig(BaseModel):
    gain_db: float = Field(default=0.0, ge=-60.0, le=24.0, description="Volume gain in decibels")
    enable_loudnorm: bool = Field(default=True, description="Apply EBU R128 loudness normalization")
    target_i: float = Field(default=-14.0, description="Integrated loudness target in LUFS")
    target_tp: float = Field(default=-1.5, description="Maximum True Peak target in dBFS")

class Segment(BaseModel):
    segment_index: int
    source_file: str
    start_time: float = Field(ge=0.0, description="Start timestamp in seconds")
    end_time: float = Field(gt=0.0, description="End timestamp in seconds")
    color_grading: ColorGradingConfig = Field(default_factory=ColorGradingConfig)
    audio_adjust: AudioAdjustConfig = Field(default_factory=AudioAdjustConfig)

    @field_validator("end_time")
    @classmethod
    def validate_duration(cls, v, values):
        start = values.data.get("start_time", 0.0)
        if v <= start:
            raise ValueError(f"end_time ({v}s) must be greater than start_time ({start}s)")
        return v

class TransitionConfig(BaseModel):
    transition_type: str = Field(default="fade", description="Type of transition (fade, wipeleft, dissolve)")
    duration: float = Field(default=0.5, ge=0.1, le=3.0, description="Transition duration in seconds")

class EditDecisionList(BaseModel):
    job_id: str
    target_width: int = Field(default=3840, ge=320, le=7680)
    target_height: int = Field(default=2160, ge=240, le=4320)
    target_fps: float = Field(default=30.0, ge=1.0, le=120.0)
    encoding_profile: VideoEncodingProfile = VideoEncodingProfile.X264_CRF17
    audio_profile: AudioEncodingProfile = AudioEncodingProfile.AAC_320K
    segments: List[Segment] = Field(min_length=1)
    transitions: Optional[List[TransitionConfig]] = None
    manual_override_applied: bool = False

    @field_validator("target_width", "target_height")
    @classmethod
    def validate_even_dimensions(cls, v):
        if v % 2 != 0:
            raise ValueError(f"Dimension {v} must be divisible by 2 for video macroblock encoding")
        return v
```

---

## 8. Summary & Next Steps for Multi-Agent Implementation

This specification establishes the authoritative, mathematically verified blueprint for:
1. **Milestone 1**: Core Data Models, Pydantic schemas, and Ingest Watchdog.
2. **Milestone 2**: Gemini Omni ML grading loop and FastAPI Manual Override REST endpoints.
3. **Milestone 3**: Desktop FFmpeg High-Fidelity Lossless Video Rendering Engine and Delivery Pipeline.
4. **E2E Testing Track**: Procedural test media generator and 4-tier integration test suite asserting mathematical `ffprobe` compliance with 100% determinism.

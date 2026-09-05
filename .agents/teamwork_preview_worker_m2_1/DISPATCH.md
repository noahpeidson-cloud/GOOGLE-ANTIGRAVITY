## 2026-09-04T23:36:00Z
You are teamwork_preview_worker_m2_1.
Your working directory is: d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m2_1
Project root: d:\GOOGLE ANTIGRAVITY

MANDATORY FIRST STEP: Read the user's latest request in:
d:\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md (specifically check the section at timestamp 2026-09-04T23:34:50Z).

INPUT SOURCES TO CONSULT:
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_3\handoff.md` and `analysis.md`
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_5\handoff.md` and `analysis.md`
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_6\handoff.md` and `analysis.md`
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_4\handoff.md`

YOUR EXCLUSIVE WRITE OWNERSHIP:
You own and must implement the following standalone, modular, research-validated Python tools in `d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault`:
1. `audio_dsp/edm_drop_detector.py`
   - In-memory audio extraction (`ffmpeg -vn -ac 1 -ar 22050 -f s16le -` piped directly to NumPy).
   - Fast centered sliding window RMS using `np.lib.stride_tricks.as_strided` (no librosa runtime requirement, pure NumPy).
   - O(N) cumulative sum windowing (`np.cumsum`) to locate the optimal 30s drop window.
2. `audio_dsp/ebu_r128_normalizer.py`
   - Two-pass EBU R128 loudness normalization (-14.0 LUFS, -1.5 dBTP true peak, 40Hz Butterworth high-pass).
   - Pass 1 JSON loudnorm measurement; Pass 2 linear injection with brickwall limiter (`alimiter=limit=-1.5dB:attack=5:release=50`).
   - Seamless loop micro-fade (30ms in/out crossfade).
3. `video_transcoding/mobius_hdr_tonemapper.py`
   - Mobius HDR (HLG/PQ/BT.2020) to SDR (BT.709) tone-mapping filtergraph.
   - 9:16 vertical re-framing (center crop, blur-pad fallback, and safe-region offset).
4. `video_transcoding/atempo_filter_compiler.py`
   - Dynamic atempo filtergraph compiler that recursively chains `atempo` filters to safely bypass FFmpeg's 0.5x - 2.0x limits (e.g. 0.25x -> atempo=0.5,atempo=0.5; 4.0x -> atempo=2.0,atempo=2.0) with PTS synchronization.
5. `video_transcoding/lossless_encoding_profiles.py`
   - Visually lossless production profiles registry (`x264_crf17`, `x264_yuv444p`, `x265_crf16`, `hevc_nvenc`, `prores_hq`) with automatic hardware-to-software fallback.

MANDATORY INTEGRITY & FRONTMATTER REQUIREMENT:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

EVERY SINGLE FILE MUST begin with a formatted docstring or YAML frontmatter containing:
- Name: The tool or concept name.
- Context Mapping: Point of reference tying this concept back to its original use case or pipeline.
- Strengths: Why this specific concept was deemed valuable and research-validated.
- Weaknesses: Flaws, limitations, or reasons why the original surrounding architecture failed.
- Implementation Instructions: How to safely use this logic in future builds.

ZERO-MODIFICATION GUARANTEE:
You are STRICTLY FORBIDDEN from deleting or modifying any existing files outside `d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault`. All your output must be written exclusively to your assigned target files in `d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault`.

DELIVERABLES:
1. Write the 5 complete, standalone Python files with full frontmatter docstrings.
2. Verify Python syntax (`python -m py_compile ...` via run_command) on all authored files.
3. Update progress.md in your working directory.
4. Write handoff.md in your working directory with verification commands and results.
5. Send completion message to orchestrator.

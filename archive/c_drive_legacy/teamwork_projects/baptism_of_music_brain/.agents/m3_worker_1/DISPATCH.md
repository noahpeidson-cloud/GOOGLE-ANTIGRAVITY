## 2026-08-27T10:25:27Z
You are the Implementation Worker for Milestone 3 (Desktop FFmpeg High-Fidelity Lossless Video Rendering Engine & Atomic Delivery Pipeline) of the baptism_of_music_brain project.
Your working directory is C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m3_worker_1

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY FIRST STEPS:
1. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\ORIGINAL_REQUEST.md
2. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\PROJECT.md
3. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\TEST_INFRA.md
4. Read C:\Users\noahp\teamwork_projects\baptism_of_music_brain\TEST_READY.md
5. Read Spec Miner Blueprint at C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\spec_miner_survey_3\spec_report.md

Your Exclusive Write Ownership:
- `src/renderer/profiles.py`
- `src/renderer/filtergraph.py`
- `src/renderer/ffmpeg_engine.py`
- `src/pipeline/orchestrator.py` and `src/api/routes.py` (to wire rendering and delivery handoff)
- `tests/tier1_feature/test_filtergraph.py`
- `tests/tier2_boundary/test_boundary_encoding.py`
- `tests/tier3_pairwise/test_pairwise_pipeline.py`
- `tests/tier4_workload/test_e2e_encoding_verification.py`
- `tests/tier4_workload/test_e2e_pipeline_execution.py`

Tasks:
1. Implement `src/renderer/profiles.py`:
   - Visually lossless profiles:
     - `x264_crf17` (default, `-c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 320k`)
     - `x264_yuv444p` (`-c:v libx264 -crf 17 -preset slow -pix_fmt yuv444p -c:a aac -b:a 320k`)
     - `x265_crf16` (`-c:v libx265 -crf 16 -preset medium -pix_fmt yuv420p10le -tag:v hvc1 -c:a aac -b:a 320k`)
     - `hevc_nvenc` (`-c:v hevc_nvenc -cq 17 -preset p6 -rc vbr -b:v 0 -c:a aac -b:a 320k`)
     - `prores_hq` (`-c:v prores_ks -profile:v 3 -vendor apl0 -pix_fmt yuv422p10le -c:a pcm_s24le`)
   - Profile getter, CLI argument builder, and hardware encoder fallback logic.
2. Implement `src/renderer/filtergraph.py`:
   - `build_filtergraph(edl: EditDecisionList, probe_map: Dict[str, MediaProbeResult]) -> Tuple[List[str], str, str]`:
     - Builds complex filtergraph for multi-segment cuts/trims (`trim`/`atrim` with `setpts=PTS-STARTPTS`/`asetpts=PTS-STARTPTS`).
     - Applies parametric color grading (`eq=contrast:brightness:saturation:gamma`).
     - Applies EBU R128 audio loudness normalization (`loudnorm=I=-14:TP=-1.5:LRA=11`) and volume gain.
     - Scales & pads with aspect ratio preservation (`scale=...:force_original_aspect_ratio=decrease,pad=...`) ensuring even macroblock dimensions.
     - Multi-segment stream concatenation (`concat=n=N:v=1:a=1`).
     - Speed ramps (setpts / atempo).
3. Implement `src/renderer/ffmpeg_engine.py`:
   - Asynchronous FFmpeg process execution with real-time stderr progress parsing (frame, fps, time, progress %).
   - Atomic delivery pipeline:
     - Output written to `delivery/.tmp_{job_id}_{filename}`.
     - Upon completion, programmatic probe verification via `probe_media`.
     - Atomic rename to `delivery/{filename}`.
4. Integrate with `PipelineOrchestrator` and `api/routes.py`:
   - Connecting `orchestrator.render_job(job_id)` to execute rendering, update job progress to 100%, and set status to `DELIVERED`.
5. Run the full pytest suite:
   - `pytest -v tests/tier1_feature/test_filtergraph.py tests/tier2_boundary/test_boundary_encoding.py tests/tier3_pairwise/test_pairwise_pipeline.py tests/tier4_workload/test_e2e_encoding_verification.py tests/tier4_workload/test_e2e_pipeline_execution.py`
   - Run the entire test suite `pytest -v tests/` and verify that ALL 156+ tests pass with 100% success (0 failed).
6. Write a complete handoff report at `C:\Users\noahp\teamwork_projects\baptism_of_music_brain\.agents\m3_worker_1\handoff.md` and notify parent.

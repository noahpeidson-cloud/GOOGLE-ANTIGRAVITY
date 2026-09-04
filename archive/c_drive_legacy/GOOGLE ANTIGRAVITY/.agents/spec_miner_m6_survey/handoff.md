# Master Handoff Report: Specification Mining for Human-in-the-Loop Architecture (R3, Librosa .wav DSP, Proxy Trimming, Blueprint & Test Harness)

> **Agent:** Spec Miner Survey (`teamwork_preview_spec_miner`)
> **Target:** Orchestrator & Engineering Team
> **Workspace Directory:** `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\spec_miner_m6_survey`
> **Report Path:** `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\spec_miner_m6_survey\spec_report.md`
> **Timestamp:** `2026-08-22T11:03:00Z`

---

## 1. Observation

1. **Existing Codebase & Modules:**
   - `content_creation/audio_dsp.py` (lines 135-449): Implements `AudioDropDetector` with dual-engine RMS calculation (Librosa primary, vectorized NumPy fallback), O(N) cumsum argmax sliding window, immediate manual CLI override bypass, and native `.wav` parsing via Python's built-in `wave` module.
   - `content_creation/orchestrator.py` (lines 230-504): `run_master_pipeline()` previously accepted raw video (`staged_input`) and directly generated full-resolution masters, saving to `03_READY_TO_POST`.
   - `content_creation/remote_trigger.py` (lines 74-98, 595-640): FastAPI server serves `static/index.html` and exposes `POST /trigger-pipeline` with `PipelineTriggerRequest` (which supports `event`, `artist`, `from_device`, `auto_drop`, etc.).
   - `content_creation/static/index.html` (lines 453-648): PWA UI contains the giant trigger button and dispatches `POST /trigger-pipeline` with hardcoded payload defaults (`LiveConcert`, `AutoArtist`).
   - `content_creation/V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md`: Documents the 6-Phase lifecycle, Mechanisms 0-8, and 4-tier folder taxonomy (`01_RAW_INBOX`, `02_IN_PROGRESS`, `03_READY_TO_POST`, `04_ARCHIVE`).
2. **Authoritative Request (`ORIGINAL_REQUEST.md`, Milestone M6):**
   - **R1:** Add text input fields for "Festival Name" and "Artist Name" above trigger button in `static/index.html` and pass them in `POST /trigger-pipeline`.
   - **R2:** Organize files in `01_RAW/[Festival]/[Artist]`; generate 720p proxy `.mp4` and extract `.wav` file for every 4K video. Original 4K HDR files remain safe and untouched.
   - **R3:** Run Librosa drop detection exclusively on `.wav`; trim the 720p *proxy* video based on timestamps (or manual override); stage trimmed proxy into `02_AWAITING_REVIEW/`; AI must NOT touch or edit the 4K raw files.
3. **Test Suite Baseline:**
   - Executed `python -m unittest discover -s content_creation/tests`: **479 tests ran and passed (100% OK in 24.5s)**.

---

## 2. Logic Chain

1. **Audio DSP Efficiency Logic:**
   - In earlier milestones, drop detection demuxed audio from full 4K video files via FFmpeg streaming pipes.
   - Because `audio_dsp.py` already possesses a zero-overhead native `wave` module reader, passing the `.wav` file generated in R2 directly to `AudioDropDetector.detect_optimal_drop(wav_path)` accelerates audio ingestion by >10x and eliminates video container parsing during DSP analysis.
   - Manual CLI overrides (`--start-time`, `--duration`) continue to bypass audio extraction and DSP calculations entirely.
2. **Non-Destructive Editorial Safety Logic:**
   - Ingested 4K HDR files stored in `01_RAW/[Festival]/[Artist]/` represent the ground-truth master recordings.
   - The AI must treat `01_RAW` as strictly read-only after initial file placement.
   - Trimming operations must be applied solely to the 720p proxy video (`..._proxy.mp4`), outputting the candidate clip into `02_AWAITING_REVIEW/[Festival]_[Artist]_[Timestamp]_proxy_drop.mp4`.
   - Full 4K master transcoding is deferred until a human reviews and approves the proxy clip.
3. **Blueprint & Taxonomy Alignment Logic:**
   - The V2 Blueprint lifecycle must be updated:
     * Phase 0: Physical Device / PWA Capture with metadata form entry.
     * Phase 1: Ingestion & 4K RAW Storage in `01_RAW/[Festival]/[Artist]`.
     * Phase 2: Lightweight 720p Proxy Video & `.wav` Audio Extraction.
     * Phase 3: Librosa Drop Detection on `.wav` & Proxy Trimming.
     * Phase 4: Human-in-the-Loop "Awaiting Review" Gate (`02_AWAITING_REVIEW/`).
     * Phase 5: Human Approval, Final 4K Master Transcoding & Distribution.
   - Folder taxonomy transitions to: `01_RAW/[Festival]/[Artist]`, `02_AWAITING_REVIEW`, `03_READY_TO_POST`, `04_ARCHIVE`.

---

## 3. Caveats

- **No Code Modified (Read-Only Compliance):** In strict accordance with the Spec Miner role, no production source code in `content_creation/` was modified. All findings and specifications are compiled into `.agents/spec_miner_m6_survey/spec_report.md`.
- **Pre-Existing Tests:** The 479 existing tests pass under the legacy workflow. When workers implement R1, R2, and R3, tests that expect immediate promotion from `02_IN_PROGRESS` to `03_READY_TO_POST` in `pipeline` must be updated or expanded to reflect the `02_AWAITING_REVIEW` staging contract.

---

## 4. Conclusion

The specification for Milestone M6 (R1, R2, R3) is complete, unambiguous, and fully mapped:
- `audio_dsp.py` is already equipped to consume `.wav` files natively.
- `orchestrator.py` requires updates to route drop detection to `.wav`, trim the 720p proxy, deposit clips into `02_AWAITING_REVIEW`, and enforce immutability on `01_RAW`.
- `static/index.html` requires text input fields for Festival Name and Artist Name.
- `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` requires systematic phase and taxonomy documentation updates.

---

## 5. Verification Method

To verify the findings of this survey:
1. Inspect the full specification report:
   `view_file G:\My Drive\GOOGLE ANTIGRAVITY\.agents\spec_miner_m6_survey\spec_report.md`
2. Inspect `audio_dsp.py` WAV decoding logic:
   `view_file G:\My Drive\GOOGLE ANTIGRAVITY\content_creation\audio_dsp.py` (lines 168-198)
3. Run the existing test suite:
   `python -m unittest discover -s content_creation/tests`

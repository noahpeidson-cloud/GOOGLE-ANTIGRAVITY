## 2026-09-04T17:03:12-07:00

You are teamwork_preview_worker_m2_3.
Your working directory is: d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m2_3
Project root: d:\GOOGLE ANTIGRAVITY

MANDATORY FIRST STEP: Read the user's latest request in:
d:\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md (specifically check the section at timestamp 2026-09-04T23:34:50Z).

INPUT SOURCES TO CONSULT:
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_2\handoff.md` and `analysis.md`
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_3\handoff.md` and `analysis.md`
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_4\handoff.md` and `analysis.md`
- `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_5\handoff.md` and `analysis.md`

YOUR EXCLUSIVE WRITE OWNERSHIP:
You own and must implement the following standalone, modular, research-validated tools and documentation in `d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault`:
1. `viral_intelligence/evpi_viral_grading_model.py`
   - Complete 5-parameter EVPI formulation: Hook (H), Retention (R), Visual Engagement (V), Audio-Visual Coherence (A), Narrative Pacing (P) with weights [0.30, 0.25, 0.20, 0.15, 0.10].
   - Non-linear killswitch dampeners (audio clipping K_audio=0.10, safe-zone violation K_format, duration penalty).
   - Strict Pydantic V2 schema models for Gemini multimodal video evaluation (`ViralScoreReport`, `HookMetrics`, `RetentionMetrics`, `FixRecommendation`).
2. `viral_intelligence/council_of_the_drop.md`
   - Conceptual blueprint and system prompt architecture for the 5-persona creative debate model: Hook Architect, Kinetic Editor, Vibe Curator, Retention Hacker, Sound Seeder.
   - Structured JSON debate arbitration flow and synthetic prompt generation.
3. `viral_intelligence/safe_zone_seo_auditor.py`
   - YouTube Shorts & TikTok UI exclusion safe-zone collision auditor (Shorts 900x1270 bounding box, TikTok 920x1310 bounding box).
   - 5-7 hashtag clustering formula (1 broad EDM, 2 sub-genre, 1 event/artist, 1 hook/viral).
   - 17-keyword spam and engagement-bait blocklist filter.
4. `viral_intelligence/youtube_content_id_guard.py`
   - Resumable chunked upload client to YouTube Data API v3.
   - Pre-flight unlisted upload policy with automated Content ID copyright claim polling loop.
   - Automated conditional branch: auto-promote to Public if clean, quarantine if copyright-claimed.
5. `README.md` (Master Vault Catalog & Index in `_archive_vault/README.md`)
   - Comprehensive inventory of all 15 extracted tools and concepts across the 4 domains (`audio_dsp`, `video_transcoding`, `davinci_automation`, `ingestion_hardware`, `viral_intelligence`).
   - Cross-reference map connecting each vaulted tool to its legacy file origin.
   - Summary of core legacy anti-patterns retired and best practices established.

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
1. Write the 4 tool/concept files and the master README.md with full frontmatter.
2. Verify Python syntax (`python -m py_compile ...` via run_command) on all Python files.
3. Update progress.md in your working directory.
4. Write handoff.md in your working directory with verification commands and results.
5. Send completion message to orchestrator.

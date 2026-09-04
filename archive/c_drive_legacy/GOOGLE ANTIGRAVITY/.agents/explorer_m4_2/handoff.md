# Handoff Report: `audit/report_builder.py` Specification & Blueprint

## 1. Observation
- **Target File**: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\audit\report_builder.py` (to be created in Milestone 4).
- **Core Models Reference** (`.agents/cron/models.py`, lines 1-129):
  - `OptimizationReport` (lines 102-129): `session_id: str`, `timestamp: int`, `duration_ms: float`, `total_anomalies: int`, `approved_count: int`, `challenged_count: int`, `audited_anomalies: List[RedTeamAuditResult]`, `textual_gradients: List[str]`, `entropy_score: float`.
  - `RedTeamAuditResult` (lines 70-100): `anomaly: AnomalyRecord`, `verdict: RedTeamVerdict`, `rationale: str`, `risk_assessment: str`, `recommended_action: str`.
  - `RedTeamVerdict` (lines 23-26): `APPROVED`, `CHALLENGED`, `REJECTED`.
  - `AnomalyRecord` (lines 29-68): `detector_type: DetectorType`, `target_path: str`, `severity: Severity`, `description: str`, `raw_details: Dict[str, Any]`, `is_historical: bool`, `timestamp: int`, `confidence: float`.
  - `DetectorType` (lines 15-20): `GHOST_DAEMONS`, `CONTEXT_ROT`, `ECOSYSTEM_POLLUTION`, `SECRET_ZERO`, `PROMPT_FATIGUE`.
  - `Severity` (lines 8-12): `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- **Database & Telemetry Reference** (`.agents/cron/database.py`, lines 1-430):
  - `HISTORICAL_LIFELINES_DATA` (lines 12-63): 5 historical failure lifelines from August 23/24 session (`GHOST_DAEMONS_WINERROR_10048`, `CONTEXT_ROT_PLANNING_ARTIFACTS`, `ECOSYSTEM_POLLUTION_DISABLED_PLUGINS`, `SECRET_ZERO_PLACEHOLDER_KEYS`, `PROMPT_FATIGUE_MANIFEST_BLOAT`).
  - `get_session` (lines 283-302): Fetches session metadata by session ID.
  - `get_anomalies_for_session` (lines 304-342): Retrieves all anomalies for a given session.
  - `get_textual_gradients_for_session` (lines 344-362): Retrieves textual gradients.
  - `get_historical_lifelines` (lines 364-379): Retrieves seeded historical failure lifelines.
  - `get_historical_drift` (lines 382-429): Returns lifetime drift metrics including `total_sessions`, `total_anomalies`, `detector_distribution`, `severity_distribution`, `average_duration_ms`, `average_entropy_score`, `historical_match_counts`, `drift_detected`.
- **ML & ProTeGi Reference** (`.agents/cron/ml/protegi.py`, lines 1-180 & `clustering.py`, lines 1-168):
  - `CONVERGENCE_MESSAGE` (line 13): `"[ProTeGi Convergence] Semantic entropy is 0.000 — Workspace rules and detectors are tightly aligned."`
  - `compute_semantic_entropy` and `kmeans_cluster` (lines 8-168 in `clustering.py`).
- **Safety & AST Guardrails** (`.agents/cron/safety_guardrails.py`, lines 1-312):
  - Prohibits all destructive filesystem operations (`os.remove`, `os.unlink`, `shutil.rmtree`), process killing (`subprocess`, `taskkill`), `eval`, and `exec`.

## 2. Logic Chain
1. **Human-in-the-Loop (HITL) Read-Only Architecture**:
   `accidental-data-loss-prevention` and `GEMINI.md` Rule R2 mandate that the health scanner daemon operates in 100% read-only mode. Automated deletion of files or unmonitored task termination is strictly forbidden. The system must present its findings via a comprehensive Markdown report and halt for human review.
2. **6-Section Modular Composition**:
   To satisfy the user specification in `ORIGINAL_REQUEST.md`, `DailyReportBuilder.build_report` systematically composes:
   - **Section 1 (Executive Summary & Health Telemetry)**: Formats session ID, UTC timestamp, execution duration in ms, overall health badge (`🟢 HEALTHY` / `🔴 CRITICAL ACTION REQUIRED` / `🟠 HIGH ATTENTION` / `🟡 ATTENTION`), anomaly counts by severity and detector type, semantic entropy score with dispersion status, and K-Means cluster distribution (K=3).
   - **Section 2 (Red-Team Scrutiny Verdicts)**: Breaks down total audited items into Approved, Challenged, and Rejected with percentage shares, rendering a Markdown table with target resources, detector types, severities, verdicts, risk assessments, and red-team counter-arguments.
   - **Section 3 (Proposed Optimizations with Interactive Checkboxes)**: Formats interactive Markdown checkboxes (`- [ ] [HITL-APPROVED] [<DETECTOR>] <Action> (Target: <path>)`) for approved items, `- [ ] [HITL-CHALLENGED]` for caution items, and `- [x] [RED-TEAM BLOCKED - REJECTED]` for safety-blocked items.
   - **Section 4 (Historical Failure Lifelines & Drift Analytics)**: Renders a matrix of the 5 August 23/24 lifelines comparing current active anomalies against baseline targets, along with 7-day historical telemetry (total sessions, lifetime anomalies, average scan duration, average entropy, and drift flag).
   - **Section 5 (ProTeGi Textual Gradients for Heuristic Self-Improvement)**: Renders generated textual gradients from `ml/protegi.py`, displays the convergence message when entropy is 0.000, and provides actionable parameter calibrations (e.g. `CONTEXT_ROT_THRESHOLD_HOURS = 24.0`, whitelist additions, token pre-commit hooks).
   - **Section 6 (Manual Remediation Command Guide)**: Produces exact, copy-pasteable PowerShell commands for each approved anomaly (e.g. `Get-NetTCPConnection` port clearing, `Move-Item` archiving to `.agents/archive/`, `.quarantine/` isolation, token inspection in `.env`) while explicitly suppressing command generation for rejected items (0% automated execution).
3. **Session Querying & File Persistence**:
   - `build_report_from_session(session_id, db_path)` enables historical reporting directly from SQLite.
   - `save_report(markdown_content, output_path, session_id, timestamp)` writes reports to disk safely using non-destructive file writes without calling forbidden functions.

## 3. Caveats
- `DailyReportBuilder` relies on SQLite tables initialized by `init_db()` in `database.py`. If invoked against an uninitialized database, `build_report_from_session` will raise a `ValueError`.
- Interactive checkboxes are rendered in standard GitHub-flavored Markdown (`- [ ]`); their state changes are handled by the user or UI viewer, as the backend scanner maintains zero automated write execution against user assets.

## 4. Conclusion
The specification and drop-in code blueprint for `DailyReportBuilder` in `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m4_2\analysis.md` provides complete, deterministic, and AST-safe implementation code ready for worker implementation. It fulfills all Milestone 4 requirements with 100% adherence to read-only HITL safety.

## 5. Verification Method
1. **Blueprint Inspection**:
   Inspect `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m4_2\analysis.md` (lines 1-480) for the complete drop-in implementation of `audit/report_builder.py`.
2. **Deterministic Pytest Execution**:
   Once implemented by the worker, execute:
   ```powershell
   pytest .agents/cron/tests/test_red_team_and_report.py -v
   pytest .agents/cron/tests/test_safety_ast.py -v
   ```
3. **Invalidation Conditions**:
   - Report missing any of the 6 required core sections.
   - Checkboxes not matching `- [ ] [HITL-APPROVED]`.
   - Missing 5 historical failure lifelines in Section 4.
   - Presence of any destructive automated function calls (`os.remove`, `shutil.rmtree`, `taskkill`) in `audit/report_builder.py`.

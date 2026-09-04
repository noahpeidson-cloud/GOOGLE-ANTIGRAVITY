# Specification Blueprint & Mining Report: Antigravity Daily Health Scanner & ML Optimization Daemon

## 1. Observation
We directly inspected the following authoritative specification files, workspace skills, and project manifests:
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md` (Lines 1–51): Defines requirements R1 (ML & SQLite telemetry loop), R2 (5 historical session lifelines from August 23/24), R3 (strict read-only data loss prevention / HITL), R4 (internal architecture red-team audit), and acceptance criteria (exit code 0 against mock environment, static check for 0 destructive commands, 5 historical seeds, and daily `.md` report output).
- `g:\My Drive\GOOGLE ANTIGRAVITY\PROJECT.md` (Lines 1–179): Defines system architecture (safety AST guardrail, SQLite store, 5 modular detectors, pure NumPy/Pandas K-Means $K=3$, ProTeGi textual gradients, red-team auditor, daily report builder, daemon entrypoint), feature inventory (Features 1–18), milestones (E2E, M1–M6), data contracts (`Severity`, `DetectorType`, `RedTeamVerdict`, `AnomalyRecord`, `RedTeamAuditResult`, `OptimizationReport`), public function signatures in `database.py` and `detectors/base.py`, and the exact code directory layout under `.agents/cron/`.
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\agent-ml-optimization-loop\SKILL.md` (Lines 1–48): Mandates SQLite table schema `telemetry (agent_id TEXT, domain_track TEXT, input_tokens INT, output_tokens INT, error_count INT, timestamp INT, transcript TEXT)`, local Pandas/NumPy execution without BigQuery ML or external heavy ML dependencies, $N=5$ response variations, semantic clustering via Euclidean distances, hallucination detection via centroid distance, and a local execution latency constraint of `< 5ms`.
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\system-health-scan\SKILL.md` (Lines 1–29): Restricts the scan to **100% READ-ONLY auditing** with mandatory HITL approval before any action. Specifies:
  - L1/L2 context paging: Flag stale planning artifacts older than `24 hours` (`> 86400s`) for relocation to `.archive/`.
  - Secret zero eradication: Check `.env` and `*.pickle` for `your_token_here` or OAuth mismatches.
  - Watchdog cap: Hard maximum of `3 iterations` for background subagents.
  - Ecosystem integrity: Audit `.disabled` plugin directories and cross-track boundary contamination.
  - Daemon audit: Check orphaned UI/backend daemons and socket collisions (`WinError 10048`).
- `C:\Users\noahp\.gemini\config\plugins\data-agent-kit-plugin\skills\accidental_data_loss_prevention\SKILL.md` (Lines 1–32): Prohibits destructive operations (`DROP`, `TRUNCATE`, broad `DELETE`, `os.remove`, `rmtree`, file deletion) without explicit affirmative user consent.
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\architecture-red-team\SKILL.md` (Lines 1–33): Specifies adversarial critique, false-positive filtering, industry standard alternatives, and omnichannel alignment checks across active tracks (`/sports_cards`, `/content_creation`, `/apps`, `/travel_and_life`).
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\protegi-leash-enforcer\SKILL.md` (Lines 1–42): Specifies ProTeGi backward pass critique, textual gradient generation to tighten constraints, and TDAD Red Phase test enforcement.
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\TEST_INFRA.md` & `TEST_READY.md`: Established standards for 4-tier E2E testing, feature inventory matrices, and acceptance verification checklists.

---

## 2. Logic Chain
1. **Non-Destructive Guarantee**: Per `ORIGINAL_REQUEST.md` §R3, `system-health-scan` CAUTION, and `accidental-data-loss-prevention`, any automated modification, file deletion (`os.remove`, `shutil.rmtree`), or process termination (`taskkill`, `kill`) is strictly prohibited. Therefore, `safety_guardrails.py` must use Python's `ast` module to statically verify that 0 destructive node patterns exist in production code paths.
2. **Historical Seeding**: Per `ORIGINAL_REQUEST.md` §R2, when `init_db()` runs, the SQLite database must be automatically populated with exactly the 5 failure lifeline records from August 23/24 (`GHOST_DAEMONS`, `CONTEXT_ROT`, `ECOSYSTEM_POLLUTION`, `SECRET_ZERO`, `PROMPT_FATIGUE`).
3. **Detection Bounds**:
   - `GHOST_DAEMONS`: Probes designated ports `3000` (Next.js/React), `8000` (FastAPI), `8501` (Streamlit) for `WinError 10048` socket collisions.
   - `CONTEXT_ROT`: Scans for `.md` files containing `'proposal'`, `'ideas'`, `'blueprint'`, or `'plan'` with age `> 24 hours` (`> 86400s`), while strictly protecting manifest files (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, active `progress.md`).
   - `ECOSYSTEM_POLLUTION`: Recursively searches for `.disabled` directories and cross-track code leaks.
   - `SECRET_ZERO`: Parses `.env` and configuration files for placeholder strings (e.g. `your_token_here`, `your_api_key_here`).
   - `PROMPT_FATIGUE`: Counts lines in `GEMINI.md` and flags files exceeding `100 lines`.
4. **ML & Textual Gradients**: Per `agent-ml-optimization-loop` and `PROJECT.md` § Architecture, ML clustering must use pure NumPy/Pandas $K=3$ K-Means without `scikit-learn` or cloud ML dependencies, completing in `< 5ms` (target `< 2ms`), vectorizing anomalies, calculating semantic entropy, and computing ProTeGi textual gradients.
5. **Red-Team & HITL Reporting**: The adversarial red-team auditor evaluates each anomaly, filtering false positives and assigning one of 3 verdicts (`APPROVED`, `CHALLENGED`, `REJECTED`). The report builder compiles a daily Markdown file containing interactive checkboxes for human-in-the-loop review.

---

## 3. Exact Numerical Thresholds & Mathematical Constraints

| Metric / Parameter | Value / Constraint | Unit / Type | Authoritative Source |
|---|---|---|---|
| K-Means Execution Latency | `< 5.0` (target `< 2.0`) | milliseconds (ms) | `agent-ml-optimization-loop` §2, `PROJECT.md` § Architecture |
| K-Means Cluster Count ($K$) | `3` | integer | `PROJECT.md` § Architecture, line 32, 159 |
| Feature Variation / Embeddings ($N$) | `5` | integer | `agent-ml-optimization-loop` §2 |
| Context Rot Age Threshold | `> 24` (`> 86,400`) | hours (seconds) | `ORIGINAL_REQUEST.md` §R2.2, `system-health-scan` §1 |
| Prompt Fatigue Line Count Threshold | `> 100` | lines of code | `PROJECT.md` feature 9, line 30, line 155 |
| Ghost Daemons Port Numbers | `3000`, `8000`, `8501` | TCP ports | `PROJECT.md` feature 5, line 26, `ORIGINAL_REQUEST.md` §R2.1 |
| Ghost Daemons Error Code | `10048` (`WSAEADDRINUSE`) | Windows Error Code | `ORIGINAL_REQUEST.md` §R2.1, `system-health-scan` §6 |
| Watchdog Subagent Iteration Cap | `3` | iterations | `system-health-scan` §4 |
| Historical Seed Records | `5` | rows | `ORIGINAL_REQUEST.md` §R2, `PROJECT.md` feature 3 |
| Red-Team Verdict Enum Cardinality | `3` (`APPROVED`, `CHALLENGED`, `REJECTED`) | enum members | `PROJECT.md` `models.py` |
| Detector Types Cardinality | `5` (`GHOST_DAEMONS`, `CONTEXT_ROT`, `ECOSYSTEM_POLLUTION`, `SECRET_ZERO`, `PROMPT_FATIGUE`) | enum members | `PROJECT.md` `models.py` |
| Severity Enum Cardinality | `4` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) | enum members | `PROJECT.md` `models.py` |
| CLI Daemon Exit Code | `0` | exit code | `ORIGINAL_REQUEST.md` §Acceptance Criteria |
| Default Anomaly Confidence | `1.0` | float ($[0.0, 1.0]$) | `PROJECT.md` `models.py` |
| External Dependency Constraint | `scikit-learn` strictly absent | Boolean constraint | `PROJECT.md` § Architecture, `agent-ml-optimization-loop` |

---

## 4. Exact AST Forbidden Node Rules for `test_safety_ast.py`

`safety_guardrails.py` and `test_safety_ast.py` must statically parse and enforce zero destructive operations across all production Python files in `.agents/cron/`:

### 4.1. Forbidden AST Call Nodes
1. **File System Deletions**:
   - `os.remove`, `os.unlink`, `os.rmdir`, `os.removedirs`
   - `shutil.rmtree`, `shutil.move` (when targeting workspace paths outside designated mock sandboxes)
   - `pathlib.Path.unlink`, `pathlib.Path.rmdir`
2. **Process Termination Calls**:
   - `os.kill`, `os.killpg`, `signal.pthread_kill`
   - `psutil.Process.kill`, `psutil.Process.terminate`, `psutil.Process.send_signal`
3. **Shell / Subprocess Execution**:
   - `os.system`
   - `subprocess.run`, `subprocess.Popen`, `subprocess.call`, `subprocess.check_call`, `subprocess.check_output`
   - `os.popen`, `os.spawn*`

### 4.2. Forbidden Import Nodes
- `ast.Import` and `ast.ImportFrom` matching:
  - `from os import remove, unlink, rmdir, removedirs, system, kill`
  - `from shutil import rmtree`

### 4.3. Forbidden String Literals & SQL Commands
Inspection of `ast.Constant` / `ast.Str` arguments passed to any string formatting or database functions:
- Dangerous CLI commands: `"taskkill"`, `"kill -9"`, `"pkill"`, `"rm -rf"`, `"rmdir /s"`, `"del /f"`, `"del /q"`
- Dangerous SQL statements per `accidental-data-loss-prevention`:
  - `"DROP TABLE"`, `"DROP VIEW"`, `"DROP DATABASE"`, `"DROP SCHEMA"`
  - `"TRUNCATE TABLE"`, `"TRUNCATE"`
  - Unbounded deletions: `"DELETE FROM"` without `WHERE` or containing `WHERE 1=1`

### 4.4. Verification Logic for `test_safety_ast.py`
- Recursively traverses `.agents/cron/**/*.py` (excluding `tests/` and `fixtures/`).
- Runs `safety_guardrails.verify_file_safety(file_path)` on every file.
- Asserts that the violation count is exactly `0`.
- Includes unit tests with positive assertions (pure read-only code passes) and negative assertions (synthetic AST nodes containing forbidden calls are caught and raise `DestructiveCallViolation`).

---

## 5. Exact Structure and Sections Required for `TEST_INFRA.md` & `TEST_READY.md`

### 5.1. Structure of `TEST_INFRA.md`
Target Location: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\TEST_INFRA.md` (or `.agents/TEST_INFRA.md`)
Must include the following exact sections:

1. **Title**: `# E2E Test Infra: Antigravity Daily Health Scanner & ML Optimization Daemon`
2. **Section 1: Test Philosophy**
   - Requirement-driven, opaque-box testing based strictly on `ORIGINAL_REQUEST.md` and `PROJECT.md`.
   - Non-destructive execution verified via AST analysis.
   - Zero external cloud/API dependencies; self-contained deterministic mock workspace fixture.
   - Loud assertions (zero shared state, explicit failure messages).
3. **Section 2: Feature Inventory & Test Coverage Goals Table**
   - Standard 7-column matrix:
     `| # | Feature | Requirement Source | Tier 1 (Feature) | Tier 2 (Boundary) | Tier 3 (Pairwise) | Tier 4 (Scenario) |`
   - Covers all 16 core features (AST safety, SQLite store, 5 historical seeds, BaseDetector contract, Ghost Daemons, Context Rot, Ecosystem Pollution, Secret Zero, Prompt Fatigue, Vectorization, NumPy/Pandas K-Means, ProTeGi gradients, Red-Team auditor, Report builder, CLI daemon, Mock workspace).
4. **Section 3: Test Architecture**
   - Test Runner: `pytest`
   - Working Directory: `.agents/cron`
   - Test Command: `pytest tests/ -v`
   - Fixture Directory: `fixtures/mock_workspace`
5. **Section 4: Tiered Test Suite Structure**
   - **Tier 1: Feature Coverage (≥5 unit/contract tests per component)**
   - **Tier 2: Boundary & Corner Cases (≥5 boundary tests per component)**
   - **Tier 3: Cross-Feature Combinations (Pairwise integration pipeline)**
   - **Tier 4: Real-World Scenarios (End-to-end full execution runs)**
   - **Tier 5: Adversarial Hardening (Stress tests, AST fuzzing, noisy prompts)**

### 5.2. Structure of `TEST_READY.md`
Target Location: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\TEST_READY.md` (or `.agents/TEST_READY.md`)
Must include the following exact sections:

1. **Title**: `# E2E Test Suite Ready: Antigravity Daily Health Scanner & ML Optimization Daemon`
2. **Section 1: Test Runner**
   - Execution command: `pytest .agents/cron/tests/ -v`
   - Target result: 100% pass rate (0 failures, 0 errors, exit code 0).
3. **Section 2: Coverage Summary Table**
   - 3-column table:
     `| Tier | Count | Description |`
   - Rows for Tier 1 (Feature), Tier 2 (Boundary), Tier 3 (Cross-Feature), Tier 4 (Real-World), Total test count, and pass rate indicator.
4. **Section 3: Acceptance Criteria Verification Checklist Table**
   - 3-column table:
     `| Acceptance Requirement | Status | Evidence File / Test |`
   - Explicit checklist items:
     1. Core Python script executes end-to-end and exits with code 0 against mock environment (`tests/test_e2e_daemon.py`).
     2. Static AST check verifies destructive commands (`os.remove`, `shutil.rmtree`, `taskkill`) are absent (`tests/test_safety_ast.py`).
     3. SQLite telemetry DB initialized and seeded with 5 historical callouts (`tests/test_database.py`).
     4. Script outputs daily `.md` report containing red-team audit of ML findings (`tests/test_report_builder.py`).
     5. Pure NumPy/Pandas K-Means clustering ($K=3$) executes in < 5ms without sklearn (`tests/test_ml_clustering.py`).
     6. All 5 modular anomaly detectors accurately detect target conditions (`tests/test_detectors.py`).
     7. Architecture Red-Team accurately filters false positives and assigns 3-tiered verdicts (`tests/test_red_team_audit.py`).

---

## 6. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Safety Guardrails | Static AST Destructive Call Ban | Inspects AST of all `.py` files to guarantee 0 destructive calls (`os.remove`, `rmtree`, `taskkill`, `DROP`, `TRUNCATE`). | File paths or Python source strings | `List[ASTViolation]` (empty on valid code) | Raises `DestructiveCallViolation` on prohibited nodes | `ORIGINAL_REQUEST.md` §Acceptance Criteria, `PROJECT.md` line 22 |
| 2 | Telemetry Store | SQLite Database Schema Initialization | Creates `scan_sessions`, `anomalies`, `textual_gradients`, and `historical_lifelines` tables. | Database path `str` | `None` (tables created) | Raises `sqlite3.Error` on disk/permission failure | `PROJECT.md` line 128, `ORIGINAL_REQUEST.md` §R1 |
| 3 | Telemetry Store | August 23/24 Historical Seeding | Seeds exactly 5 historical failure lifelines into SQLite on DB initialization. | Database path `str` | `None` (5 rows inserted) | Idempotent check (does not duplicate if already seeded) | `ORIGINAL_REQUEST.md` §R2, `PROJECT.md` line 24 |
| 4 | Telemetry Store | Telemetry Session Logger | Logs complete scan session, anomalies list, textual gradients, duration in ms, and timestamp. | `session_id`, `anomalies`, `gradients`, `duration_ms`, `db_path` | `None` (persisted) | Atomic transaction rollback on DB error | `PROJECT.md` line 131, `agent-ml-optimization-loop` §1 |
| 5 | Telemetry Store | Historical Drift Analyzer | Queries historical anomaly frequency and detects divergence over time. | Database path `str` | `dict` of drift metrics | Returns empty drift dict if no previous sessions | `PROJECT.md` line 132 |
| 6 | Anomaly Detection | Abstract Base Detector Contract | Defines base class `BaseDetector` with abstract method `scan(workspace_root) -> List[AnomalyRecord]`. | `workspace_root: str` | `List[AnomalyRecord]` | Abstract methods raise `NotImplementedError` if unhandled | `PROJECT.md` lines 116–125 |
| 7 | Anomaly Detection | Ghost Daemons Detector | Inspects TCP ports `3000`, `8000`, `8501` for socket collisions (`WinError 10048`) or unmonitored server daemons. | `workspace_root: str` | `List[AnomalyRecord]` (severity HIGH/CRITICAL) | Gracefully handles non-responsive or firewalled ports | `ORIGINAL_REQUEST.md` §R2.1, `PROJECT.md` line 26, `system-health-scan` §6 |
| 8 | Anomaly Detection | Context Rot Detector | Identifies planning artifacts (`.md` with 'proposal', 'ideas', 'blueprint', 'plan') older than 24h (`> 86400s`). | `workspace_root: str` | `List[AnomalyRecord]` (severity MEDIUM) | Whitelists protected files (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`) | `ORIGINAL_REQUEST.md` §R2.2, `PROJECT.md` line 27, `system-health-scan` §1 |
| 9 | Anomaly Detection | Ecosystem Pollution Detector | Identifies `.disabled` plugin folders and cross-track leaks across `/sports_cards`, `/content_creation`, `/apps`, `/travel_and_life`. | `workspace_root: str` | `List[AnomalyRecord]` (severity MEDIUM/HIGH) | Skips ignored or standard `.git` directories | `ORIGINAL_REQUEST.md` §R2.3, `PROJECT.md` line 28, `system-health-scan` §5 |
| 10 | Anomaly Detection | Secret Zero Detector | Scans `.env`, `.env.*`, and configs for placeholder tokens (`your_token_here`, `your_api_key_here`). | `workspace_root: str` | `List[AnomalyRecord]` (severity HIGH/CRITICAL) | Safely handles unreadable or binary files | `ORIGINAL_REQUEST.md` §R2.4, `PROJECT.md` line 29, `system-health-scan` §3 |
| 11 | Anomaly Detection | Prompt Fatigue Detector | Checks `GEMINI.md` line count against threshold `> 100 lines` and checks token bloat. | `workspace_root: str` | `List[AnomalyRecord]` (severity LOW/MEDIUM) | Returns empty if `GEMINI.md` is within limits or absent | `ORIGINAL_REQUEST.md` §R2.5, `PROJECT.md` line 30 |
| 12 | Health Scanner | Modular Scanner Orchestrator | Instantiates and executes all 5 detectors sequentially across target workspace. | `workspace_root: str`, optional detector list | `List[AnomalyRecord]` | Continues execution if one detector encounters non-fatal error | `PROJECT.md` lines 147–155 |
| 13 | ML Optimization | Anomaly Feature Vectorizer | Converts `AnomalyRecord` objects into normalized numerical feature vectors (severity, type, text length, age). | `List[AnomalyRecord]` | `pandas.DataFrame` or `numpy.ndarray` | Returns empty DataFrame if 0 anomalies | `PROJECT.md` line 31, `agent-ml-optimization-loop` §2 |
| 14 | ML Optimization | Pure NumPy/Pandas K-Means | Clusters feature vectors into $K=3$ clusters locally in $< 5\text{ ms}$ (target $< 2\text{ ms}$) without sklearn. | Feature matrix ($N \times D$), $K=3$ | `labels: np.ndarray`, `centroids: np.ndarray` | Handles $N < K$ edge cases by assigning singleton clusters | `PROJECT.md` line 32, `agent-ml-optimization-loop` §2 |
| 15 | ML Optimization | ProTeGi Textual Gradient Generator | Calculates semantic entropy between centroid clusters and generates rule refinement diffs. | Anomaly clusters, centroids, baseline rules | `List[str]` (textual gradients & rule patch diffs), `entropy_score: float` | Generates 0 diffs if entropy is zero | `PROJECT.md` line 33, `agent-ml-optimization-loop` §3, `protegi-leash-enforcer` |
| 16 | Audit & Governance | Architecture Red-Team Auditor | Adversarial evaluation layer challenging ML findings, filtering false positives, and assigning verdicts. | `List[AnomalyRecord]`, ML clusters | `List[RedTeamAuditResult]` (`APPROVED`, `CHALLENGED`, `REJECTED`) | Marks ambiguous items as `CHALLENGED` rather than hallucinating | `ORIGINAL_REQUEST.md` §R4, `PROJECT.md` line 34, `architecture-red-team` |
| 17 | Audit & Governance | Daily HITL Markdown Report Builder | Compiles structured daily Markdown report with interactive checkboxes `[ ]` for Noah's approval. | `OptimizationReport` data contract | Formatted Markdown string / `.md` file | Emits structured fallback message if report data is empty | `ORIGINAL_REQUEST.md` §Acceptance Criteria, `PROJECT.md` line 35 |
| 18 | Daemon Engine | CLI Daemon Runner | Provides CLI entrypoint supporting `--once`, `--mock-env <path>`, `--db <path>`, and `--output <path>`. | CLI arguments | Process exit code `0`, report written to disk | Exits with non-zero code and stderr message on fatal CLI error | `PROJECT.md` line 36, `ORIGINAL_REQUEST.md` §Acceptance Criteria |
| 19 | Daemon Engine | Google Antigravity SDK Hook | Binds `@hooks.on_turn_end` or `triggers.every` to schedule daily recurring health scan. | Antigravity Context & TurnResult | Telemetry record logged to SQLite | Catches and logs hook exceptions without crashing daemon | `agent-ml-optimization-loop` §1, `PROJECT.md` line 13 |
| 20 | Test Harness | Offline Mock Workspace Fixture | Deterministic offline fixture containing all 5 historical failure patterns for hermetic testing. | Mock filesystem generator | Synthetic directory structure | Fully isolated in temp directory, safe for clean teardown | `PROJECT.md` line 37 |

---

## 7. Edge Cases

| # | Feature | Input / Condition | Observed / Required Behavior |
|---|---------|-------------------|-----------------------------|
| 1 | K-Means Clustering | $N=0$ anomalies detected in scan session | Return empty cluster array and entropy score `0.0` without crashing or dividing by zero. |
| 2 | K-Means Clustering | $N < K$ anomalies ($N = 1$ or $N = 2$) | Assign each anomaly to a distinct cluster label; do not trigger matrix shape mismatch. |
| 3 | K-Means Clustering | Identical feature vectors across all anomalies (zero variance) | Convergence reached in iteration 1 with centroid identical to all points; entropy score is `0.0`. |
| 4 | K-Means Clustering | Execution time under heavy load ($N=1000$ anomalies) | Must complete in $< 5.0\text{ ms}$ (enforced via vectorization and pure NumPy broadcasting). |
| 5 | Context Rot Detector | File modified exactly at boundary ($T = 24.00\text{ hours}$ vs $23.99\text{ hours}$ vs $24.01\text{ hours}$) | Only files strictly $> 86400\text{ seconds}$ are flagged as stale context rot. |
| 6 | Context Rot Detector | Whitelisted files older than 24h (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`) | Must NOT be flagged as context rot regardless of age. |
| 7 | Context Rot Detector | File with missing read permissions or broken symlink | Catch `OSError` / `PermissionError`, log warning in detector raw details, do not halt scanner. |
| 8 | Prompt Fatigue Detector | `GEMINI.md` exactly `100 lines` vs `101 lines` vs `99 lines` | `99` and `100 lines` pass; `101 lines` triggers `PROMPT_FATIGUE` anomaly. |
| 9 | Prompt Fatigue Detector | `GEMINI.md` file does not exist in target workspace | Return empty list of anomalies (or LOW severity informational record); do not crash. |
| 10 | Ghost Daemons Detector | Target port (3000, 8000, 8501) closed / available | Return no anomaly for that port. |
| 11 | Ghost Daemons Detector | Port in use by legitimate active background task | Red-Team auditor challenges deletion/cleanup if PID belongs to verified active task. |
| 12 | Ghost Daemons Detector | Non-Windows OS socket inspection (missing `WinError 10048`) | Fallback to standard `errno.EADDRINUSE` or socket bind error check. |
| 13 | Secret Zero Detector | `.env` containing legitimate tokens vs `your_token_here` / `YOUR_API_KEY_HERE` | Valid non-placeholder keys pass; placeholder strings trigger HIGH/CRITICAL severity anomaly. |
| 14 | Secret Zero Detector | Empty `.env` file (0 bytes) | Does not flag secret placeholder, may flag empty config if required. |
| 15 | Ecosystem Pollution | Directory named `.disabled_features` vs `.disabled` | Correctly identifies exact `.disabled` suffix per plugin convention. |
| 16 | Ecosystem Pollution | Cross-track file: card scraper located in `/apps` or `/content_creation` | Flags cross-domain contamination with reference to track isolation rule. |
| 17 | Static AST Safety | Code containing comments with `"os.remove"` or docstrings with `"DROP TABLE"` | AST parser examines syntax tree nodes (`ast.Call`), ignoring comments and non-executed docstrings. |
| 18 | Static AST Safety | Code using dynamic `getattr(os, "rem" + "ove")` | AST visitor flags dynamic attribute lookups on `os`/`shutil`/`subprocess` modules. |
| 19 | SQLite Database | SQLite database file locked by another process (`sqlite3.OperationalError: database is locked`) | Uses `timeout=10.0` and WAL mode (`PRAGMA journal_mode=WAL`) to prevent locking errors. |
| 20 | SQLite Seeding | Calling `seed_historical_lifelines` multiple times on existing database | Idempotent check ensures exactly 5 historical lifelines remain present without duplication. |
| 21 | Red-Team Auditor | Ambiguous anomaly (e.g., active config file with temporary placeholder) | Emits `CHALLENGED` verdict with explicit rationale and recommended action. |
| 22 | Report Builder | Optimization report with 0 approved items | Renders report with "No optimizations requiring approval" section and clean summary metrics. |
| 23 | Watchdog Loop | Background daemon execution exceeding 3 iterations | Watchdog terminates daemon execution cleanly at iteration 3 per `system-health-scan` §4. |

---

## 8. Caveats
- **Antigravity SDK Environment**: In standalone CLI mock test runs, the Antigravity SDK (`google.antigravity`) may not be installed in the standard Python environment; the daemon must provide a clean fallback/mock for `@hooks.on_turn_end` and `triggers.every` so that CLI execution (`--once`, `--mock-env`) executes without error.
- **Port Probing Mechanics**: Port collision probing must use non-destructive connection probing (e.g. `socket.socket(socket.AF_INET, socket.SOCK_STREAM)` with short timeout or attempting non-destructive bind probe in test mode) to avoid disrupting active user services.

---

## 9. Conclusion
All exact specifications, numerical thresholds ($K=3$, $<5\text{ms}$ K-Means, $>24\text{h}$ rot, $>100$ lines, ports 3000/8000/8501, 5 historical seeds, 3 watchdog iterations), mathematical constraints, AST safety rules, and the structural templates for `TEST_INFRA.md` and `TEST_READY.md` have been fully mined and documented. The blueprint is complete, unambiguous, and ready for the E2E test writing and implementation teams.

---

## 10. Verification Method
- Inspect `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\spec_miner_test_3\handoff.md` to verify complete coverage of all required sections, numerical thresholds, AST rules, and discovered features.
- Cross-reference thresholds against `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md`, `g:\My Drive\GOOGLE ANTIGRAVITY\PROJECT.md`, and skills in `.agents/skills/`.

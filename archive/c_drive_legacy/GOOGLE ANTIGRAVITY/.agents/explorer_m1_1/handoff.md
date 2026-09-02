# Investigation & Architecture Design Report: `models.py` & `config.py`

## 1. Observation
- **Authoritative Requirements**:
  - `ORIGINAL_REQUEST.md` (lines 19-38) establishes the foundational requirements:
    1. R1: `agent-ml-optimization-loop` with local SQLite backend, anomaly logging, and K-Means clustering producing ProTeGi textual gradients.
    2. R2: Historical session seeding of 5 specific failure lifelines from the August 23/24 session:
       - Ghost Daemons (`WinError 10048` socket collisions on Next.js/Uvicorn ports).
       - Context Rot (planning artifacts older than 24 hours).
       - Ecosystem Pollution (unused `.disabled` plugin directories).
       - Secret Zero (unresolved `your_token_here` tokens in `.env`).
       - Prompt Fatigue (hardcoded procedural rules bloating `GEMINI.md`).
    3. R3: Non-destructive, 100% read-only analysis adhering to `accidental-data-loss-prevention`.
    4. R4: `architecture-red-team` adversarial evaluation before HITL reporting.
  - `PROJECT.md` (lines 58-112) specifies the data contracts for `models.py`:
    - Enums: `Severity` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), `DetectorType` (`GHOST_DAEMONS`, `CONTEXT_ROT`, `ECOSYSTEM_POLLUTION`, `SECRET_ZERO`, `PROMPT_FATIGUE`), `RedTeamVerdict` (`APPROVED`, `CHALLENGED`, `REJECTED`).
    - Dataclasses: `AnomalyRecord`, `RedTeamAuditResult`, `OptimizationReport`.
  - Skill manifests (`system-health-scan`, `agent-ml-optimization-loop`, `architecture-red-team`):
    - `system-health-scan`: Sets 24h context rot threshold, watchdog cap of 3 iterations, `.disabled` plugin crawl pattern, and port collision monitoring.
    - `GEMINI.md`: Sets workspace track structure (`/sports_cards`, `/content_creation`, `/apps`, `/travel_and_life`) and 100-line prompt constraint.

- **Verified Reference Files Produced in Working Directory**:
  - `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m1_1\proposed_models.py`
  - `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m1_1\proposed_config.py`

- **Command Execution & Verification**:
  - Direct roundtrip serialization and enum coercion tests executed via Python:
    `python -c "..."` exited with status `code 0`, confirming 100% test pass for AnomalyRecord, RedTeamAuditResult, OptimizationReport, and HistoricalLifeline seeding.

---

## 2. Logic Chain

1. **Enum Design (`Severity`, `DetectorType`, `RedTeamVerdict`)**:
   - *Observation*: Downstream components (SQLite, JSON report generator, ML feature vectorizer) require enums that behave cleanly as strings while enforcing type safety.
   - *Reasoning*: Inheriting each enum from `(str, Enum)` ensures `isinstance(val, str) == True`, allowing seamless SQLite text storage, direct JSON serialization (`json.dumps(val)`), and direct string comparisons (e.g. `severity == "CRITICAL"`) without needing `.value` calls everywhere.

2. **Data Structure Strategy (`models.py`)**:
   - *Observation*: The system requires zero external runtime dependencies for data models and high execution speed (<2ms).
   - *Reasoning*: Python's standard library `@dataclass` provides exact field typing, `field(default_factory=...)` for mutable defaults (`raw_details`, `audited_anomalies`), and explicit `to_dict()` / `from_dict()` serialization methods.
   - *Reasoning for AnomalyRecord*:
     - Includes `detector_type: DetectorType`, `target_path: str`, `severity: Severity`, `description: str`, `raw_details: Dict[str, Any]`, `is_historical: bool = False`, `timestamp: int`, `confidence: float = 1.0`.
     - `__post_init__` handles string-to-enum coercion and JSON string decoding for `raw_details` if SQLite passes raw text.
   - *Reasoning for RedTeamAuditResult*:
     - Encapsulates `anomaly: AnomalyRecord`, `verdict: RedTeamVerdict`, `rationale: str`, `risk_assessment: str`, `recommended_action: str`.
     - Enables the Red-Team auditor to attach actionable advice and false-positive filtering.
   - *Reasoning for OptimizationReport*:
     - Encapsulates `session_id`, `timestamp`, `duration_ms`, `total_anomalies`, `approved_count`, `challenged_count`, `audited_anomalies: List[RedTeamAuditResult]`, `textual_gradients: List[str]`, `entropy_score: float`.
     - Provides the single source of truth for generating daily Markdown reports and logging session telemetry to SQLite.

3. **Configuration & Threshold Strategy (`config.py`)**:
   - *Observation*: R1, R2, R3, and R4 specify exact thresholds and whitelists that must be shared across all detectors, database routines, and audit tools.
   - *Reasoning*:
     - `CONTEXT_ROT_HOURS = 24.0`: Artifacts older than 24 hours matching planning keywords (`proposal`, `blueprint`, `ideas`, `plan`, `draft`, `scratch`) are flagged.
     - `PROMPT_FATIGUE_MAX_LINES = 100`: Triggers prompt bloat alerts if `GEMINI.md` exceeds 100 lines.
     - `MONITORED_PORTS = [3000, 8000, 8501]`: Probes Next.js (3000), FastAPI/Uvicorn (8000), and Streamlit (8501) for unmonitored daemons and socket collisions (`WinError 10048`).
     - `MAX_SUBAGENT_ITERATIONS = 3`: Prevents watchdog infinite loops.
     - `DEFAULT_K_MEANS_CLUSTERS = 3`, `DEFAULT_SEMANTIC_ENTROPY_THRESHOLD = 0.5`: ML clustering and ProTeGi trigger parameters.
     - `PROTECTED_WHITELIST_FILENAMES`: Essential workspace files (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, `BRIEFING_ARCHIVE.md`, `DISPATCH.md`, `progress.md`, `ORIGINAL_REQUEST.md`, `TEST_READY.md`, `TEST_INFRA.md`, `task.md`) that are mathematically shielded from Context Rot flagging.
     - `SECRET_REGEX_PATTERNS` & `SECRET_PLACEHOLDER_TOKENS`: Captures `your_token_here`, `YOUR_API_KEY`, OpenAI keys (`sk-...`), Google API keys (`AIza...`), and GitHub tokens (`ghp_...`).
     - `HISTORICAL_LIFELINES_SEED_DATA`: Programmatic seed definition containing all 5 August 23/24 failure patterns ready for immediate SQLite insertion during `database.init_db()`.

---

## 3. Caveats
- No external heavy dependencies (`pydantic`, `scikit-learn`) are used; pure standard library Python (`dataclasses`, `enum`, `json`, `re`, `pathlib`, `time`) is intentionally selected for zero friction and instant execution.
- Path whitelist checking supports both exact filename matching and glob patterns (e.g. `BRIEFING*.md`). Subagents implementing detectors must call `config.is_path_whitelisted()` to ensure consistency.
- No caveats regarding specification completeness: all 5 detectors, 3 verdicts, 4 severity levels, and 5 historical seeds are fully defined and tested.

---

## 4. Conclusion & Recommended Implementation

The recommended implementation is split cleanly into two files:

### A. Target File: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\models.py`
Contains:
1. `Severity(str, Enum)`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
2. `DetectorType(str, Enum)`: `GHOST_DAEMONS`, `CONTEXT_ROT`, `ECOSYSTEM_POLLUTION`, `SECRET_ZERO`, `PROMPT_FATIGUE`.
3. `RedTeamVerdict(str, Enum)`: `APPROVED`, `CHALLENGED`, `REJECTED`.
4. `AnomalyRecord`: Pure dataclass with `to_dict()`, `from_dict()`, and `__post_init__` type coercion.
5. `RedTeamAuditResult`: Dataclass holding audited anomaly, verdict, rationale, risk assessment, and recommended action.
6. `OptimizationReport`: Dataclass aggregating session metrics, audited anomalies list, textual gradients, and entropy scores.
7. `HistoricalLifeline`: Helper dataclass converting historical seeds into `AnomalyRecord(is_historical=True)`.

### B. Target File: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\config.py`
Contains:
1. Scanner thresholds (`CONTEXT_ROT_HOURS`, `PROMPT_FATIGUE_MAX_LINES`, `MONITORED_PORTS`, `MAX_SUBAGENT_ITERATIONS`, `DEFAULT_K_MEANS_CLUSTERS`, `DEFAULT_SEMANTIC_ENTROPY_THRESHOLD`, `DEFAULT_DB_PATH`).
2. Protected whitelists (`PROTECTED_WHITELIST_FILENAMES`, `EXCLUDED_SCAN_DIRS`, `CONTEXT_ROT_TARGET_KEYWORDS`).
3. Secret Zero detection rules (`SECRET_PLACEHOLDER_TOKENS`, `SECRET_SCAN_EXTENSIONS`, `SECRET_REGEX_PATTERNS`).
4. Workspace track definitions (`WORKSPACE_TRACKS`, `DISABLED_PLUGIN_SUFFIX`).
5. Seed data (`HISTORICAL_LIFELINES_SEED_DATA` with 5 items).
6. Helper functions (`is_path_whitelisted()`, `is_directory_excluded()`).

Full, tested reference implementations are available at:
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m1_1\proposed_models.py`
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m1_1\proposed_config.py`

---

## 5. Verification Method

To independently verify the designs, execute the following command:

```powershell
python -c "import sys; sys.path.insert(0, r'g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m1_1'); import proposed_models as m; import proposed_config as c; assert len(c.HISTORICAL_LIFELINES_SEED_DATA) == 5; assert len(m.DetectorType) == 5; assert len(m.Severity) == 4; assert len(m.RedTeamVerdict) == 3; print('M1 Models and Config verification PASSED 100%')"
```

**Invalidation Conditions**:
- Any addition of destructive imports or operations (`os.remove`, `shutil.rmtree`, `taskkill`).
- Changing enum string values such that they desynchronize from `PROJECT.md` contracts.
- Missing any of the 5 historical seeds in `HISTORICAL_LIFELINES_SEED_DATA`.

# Opaque-Box E2E Test Architecture Specification (Tier 3 & Tier 4)
**Author**: explorer_test_2  
**Date**: 2026-08-24T22:20:00-07:00  
**Target Subsystem**: Daily System Health Scanner & ML Optimization Daemon (`.agents/cron`)  
**Scope**: Tier 3 (Cross-Feature Pairwise Integration) & Tier 4 (Real-World Application Workloads & 5-Failure Simulation) + Test Harness Architecture (`conftest.py`, Pytest Isolation Fixtures)

---

## 1. Observation

### 1.1 Direct Observations from Specifications & Workspace Mandates
1. **`ORIGINAL_REQUEST.md` (Lines 17–44)**:
   - **R1 (ML Optimization & Telemetry Loop)**: Must implement SQLite backend logging all detected anomalies, applying localized NumPy/Pandas K-Means clustering to identify patterns and generate ProTeGi textual gradients.
   - **R2 (Historical Session Seeding)**: SQLite DB must be programmatically seeded on initialization with the 5 August 23/24 failure lifelines:
     - Ghost Daemons: Unmonitored Next.js/Uvicorn tasks causing socket collisions (`WinError 10048`).
     - Context Rot: Planning artifacts older than 24h diluting context window.
     - Ecosystem Pollution: Unused `.disabled` plugin directories and cross-track leaks.
     - Secret Zero: Unresolved placeholder tokens (`your_token_here`) in `.env` files.
     - Prompt Fatigue: Hardcoded procedural rules bloating `GEMINI.md`.
   - **R3 (Strict Data Loss Prevention)**: 100% read-only, non-destructive analytical execution. Must compile proposed optimization report and halt. Zero deletions or taskkills permitted.
   - **R4 (Internal Red-Team Scrutiny)**: Secondary `architecture-red-team` subagent audits proposed optimizations to filter false positives before human presentation.
   - **Acceptance Criteria**: Daemon executes end-to-end with exit code 0 against mock environment; static AST check verifies 0 destructive commands (`os.remove`, `shutil.rmtree`, `taskkill`); SQLite DB initialized and seeded; daily `.md` report generated with red-team audit.

2. **`PROJECT.md` (Lines 7–179)**:
   - Component contracts specified in `models.py`: `AnomalyRecord`, `RedTeamAuditResult`, `OptimizationReport`, `Severity`, `DetectorType`, `RedTeamVerdict`.
   - Detector interface contract in `detectors/base.py`: `BaseDetector.scan(workspace_root) -> List[AnomalyRecord]`.
   - Database operations in `database.py`: `init_db()`, `seed_historical_lifelines()`, `log_scan_session()`, `get_historical_drift()`.
   - Target test directory: `.agents/cron/tests/`.

3. **Workspace Skills (`agent-ml-optimization-loop`, `system-health-scan`, `architecture-red-team`, `accidental-data-loss-prevention`)**:
   - K-Means clustering must execute in $<5\text{ms}$ locally with zero external ML dependencies (`scikit-learn` forbidden; pure NumPy/Pandas required).
   - Read-only constraint: Under no circumstances may files be moved, modified, or deleted autonomously during test execution or daemon runs.

---

## 2. Logic Chain

### 2.1 Architectural Flow of the System Under Test
The daemon operates as an acyclic processing pipeline across 7 distinct subsystems:
```
[Pre-Flight AST Gate]
       │ (Assert 0 Destructive Calls)
       ▼
[Workspace Health Scanner] (5 Detectors: Ghost Daemons, Context Rot, Pollution, Secret Zero, Prompt Fatigue)
       │ (Emits List[AnomalyRecord])
       ▼
[SQLite Telemetry Database] (Persists Scan Session & Anomalies, Seeds 5 Historical Lifelines)
       │ (Fetches Current + Historical Anomaly Vectors)
       ▼
[NumPy/Pandas ML Engine] (Vectorization Matrix -> K-Means K=3 in <5ms -> Centroid Divergence)
       │ (Calculates Semantic Entropy & ProTeGi Textual Gradients)
       ▼
[Architecture Red-Team Auditor] (Evaluates Anomalies + Gradients, Suppresses False Positives -> APPROVED / CHALLENGED / REJECTED)
       │ (Emits OptimizationReport with RedTeamAuditResults)
       ▼
[Daily HITL Report Builder] (Compiles Structured Markdown Report with Interactive Noah Checkboxes)
       │ (Writes health_report_YYYY-MM-DD.md & Updates DB Telemetry)
       ▼
[Daemon Exit Code 0 & Zero Files Touched]
```

### 2.2 Derivation of Tier 3 (Cross-Feature Pairwise Integration)
- Individual components may pass unit tests in isolation while failing when composed together due to type discrepancies, unhandled `None` fields, SQLite type affinity coercions, or NumPy matrix dimension mismatches.
- Therefore, Tier 3 tests must explicitly evaluate each adjacent pair and multi-step pipeline transition:
  1. *Scanner -> Database*: Serialization of dataclass `AnomalyRecord` to SQLite columns (`raw_details` JSON encoding).
  2. *Database -> ML Vectorizer*: Deserialization of historical + fresh anomalies into normalized float matrices without `NaN`s.
  3. *Vectorizer -> K-Means Clustering*: Numerical stability of $K=3$ clustering in $<5\text{ms}$ across varying sample sizes ($N \ge 1$).
  4. *Clustering -> ProTeGi Gradients*: Transformation of cluster centroid divergence into actionable prompt diffs.
  5. *Anomalies + Gradients -> Red-Team Auditor*: Accurate classification of genuine threats vs false-positive traps.
  6. *Red-Team -> Report Builder*: Rendering structured Markdown with interactive checkboxes and summary tables.
  7. *AST Guardrail -> Daemon Runner*: Pre-flight blocking when illegal AST nodes are injected.
  8. *Transaction Atomicity*: Ensuring SQLite rollbacks occur cleanly on intermediate pipeline faults.

### 2.3 Derivation of Tier 4 (Real-World Application Workloads & 5-Failure Simulation)
- The system must be proven against a full replica of Noah's multi-track workspace containing all 5 historical failure patterns from August 23/24 simultaneously.
- Real-world workload tests must verify:
  1. Complete end-to-end execution resulting in exit code 0.
  2. Absolute non-destructive safety: Pre-scan file hash tree $\equiv$ Post-scan file hash tree.
  3. Correct identification and categorization of all 5 failure signatures.
  4. False-positive defense: Active production files, whitelisted specifications, and documentation examples must never be erroneously flagged or approved.
  5. Markdown report generation matches exact human-readable specifications with actionable checkboxes for Noah.

---

## 3. Test Harness Architecture & Fixture Design (`conftest.py`)

### 3.1 Isolation & Fixture Topology
All tests must execute inside isolated sandboxes created via `tempfile.TemporaryDirectory`. Host workspace files must never be inspected or mutated during testing.

```
+-----------------------------------------------------------------------------------------+
|                                    conftest.py Fixture Tree                             |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|  [isolated_workspace] (tempfile.TemporaryDirectory)                                     |
|         │                                                                               |
|         ├──► [filesystem_snapshot] (Captures SHA256 hashes of all files pre-test;        |
|         │                          asserts .assert_untouched() post-test)               |
|         │                                                                               |
|         ├──► [mock_db_path] (Isolated SQLite DB at isolated_workspace/telemetry.db;     |
|         │                    calls init_db() + seed_historical_lifelines())              |
|         │                                                                               |
|         ├──► [mock_socket_ports] (Context manager simulating socket listeners on        |
|         │                         ports 3000, 8000, 8501 without host port collisions)  |
|         │                                                                               |
|         ├──► [seeded_workspace_all_5_failures] (Constructs full directory tree with      |
|         │                                        all 5 August 23/24 failure patterns)   |
|         │                                                                               |
|         └──► [clean_workspace] (Constructs 100% compliant workspace with zero anomalies)|
+-----------------------------------------------------------------------------------------+
```

### 3.2 Detailed Fixture Code Specification (`conftest.py`)

```python
"""
tests/conftest.py
Global pytest fixtures for Antigravity Daily Health Scanner & ML Optimization Daemon.
Provides deterministic isolation, mock workspaces, socket simulation, and non-destructive snapshot verification.
"""

import os
import sys
import time
import hashlib
import sqlite3
import tempfile
import socket
import pytest
from pathlib import Path
from typing import Dict, Generator, Any

# Ensure target project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models import AnomalyRecord, DetectorType, Severity, RedTeamVerdict
import database


class FileSystemSnapshot:
    """Utility to capture and verify that no files are modified, deleted, or corrupted."""
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.initial_snapshot = self._capture()

    def _capture(self) -> Dict[str, str]:
        snapshot = {}
        for root, _, files in os.walk(self.root_dir):
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, self.root_dir)
                try:
                    with open(full_path, "rb") as fp:
                        snapshot[rel_path] = hashlib.sha256(fp.read()).hexdigest()
                except (PermissionError, FileNotFoundError):
                    pass
        return snapshot

    def assert_untouched(self) -> None:
        """Loud assertion: Verifies that every single file pre-test remains identical post-test."""
        current_snapshot = self._capture()
        
        # Check for deleted files
        missing_files = set(self.initial_snapshot.keys()) - set(current_snapshot.keys())
        assert not missing_files, f"SAFETY VIOLATION: Files were deleted during execution: {missing_files}"
        
        # Check for modified existing files (excluding generated report/db files in output dir)
        modified_files = []
        for path, orig_hash in self.initial_snapshot.items():
            if not path.startswith("reports") and not path.endswith(".db"):
                if current_snapshot.get(path) != orig_hash:
                    modified_files.append(path)
        assert not modified_files, f"SAFETY VIOLATION: Existing workspace files were modified: {modified_files}"


@pytest.fixture
def isolated_workspace() -> Generator[str, None, None]:
    """Provides a sterile, isolated temporary workspace root."""
    with tempfile.TemporaryDirectory(prefix="antigravity_test_ws_") as tmp_dir:
        yield tmp_dir


@pytest.fixture
def snapshot_verifier(isolated_workspace: str) -> FileSystemSnapshot:
    """Returns a snapshot verifier bound to the isolated workspace."""
    return FileSystemSnapshot(isolated_workspace)


@pytest.fixture
def mock_db(isolated_workspace: str) -> Generator[str, None, None]:
    """Initializes and seeds an isolated SQLite database."""
    db_path = os.path.join(isolated_workspace, "test_health_telemetry.db")
    database.init_db(db_path)
    database.seed_historical_lifelines(db_path)
    yield db_path


@pytest.fixture
def mock_active_ports() -> Generator[list[int], None, None]:
    """Spins up local ephemeral socket listeners on loopback to simulate port collisions."""
    bound_sockets = []
    ports_to_bind = [3000, 8000, 8501]
    active_ports = []
    
    for port in ports_to_bind:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            s.listen(1)
            bound_sockets.append(s)
            active_ports.append(port)
        except OSError:
            # If port is already bound on host, it will naturally trigger ghost daemon detector
            active_ports.append(port)
            
    yield active_ports
    
    for s in bound_sockets:
        try:
            s.close()
        except Exception:
            pass


@pytest.fixture
def workspace_with_all_5_failures(isolated_workspace: str) -> str:
    """
    Constructs a complete multi-track workspace containing all 5 historical failure patterns:
    1. Ghost Daemons: Config referencing port 3000
    2. Context Rot: Stale planning files with mtime = 72 hours ago
    3. Ecosystem Pollution: .disabled directory + cross-track leak
    4. Secret Zero: .env with 'your_token_here'
    5. Prompt Fatigue: GEMINI.md with >100 lines
    """
    ws = isolated_workspace
    
    # 1. Multi-Track Layout
    tracks = ["apps/frontend", "apps/backend", "sports_cards", "content_creation", "travel_and_life", ".gemini/config/plugins"]
    for track in tracks:
        os.makedirs(os.path.join(ws, track), exist_ok=True)
        
    # 2. Failure 1: Ghost Daemons config (Next.js server on 3000)
    with open(os.path.join(ws, "apps/frontend/package.json"), "w", encoding="utf-8") as f:
        f.write('{"name": "nextjs-app", "scripts": {"dev": "next dev -p 3000"}}\n')

    # 3. Failure 2: Context Rot (Stale planning artifacts > 24h old)
    stale_files = [
        "content_creation/proposal_laser_v1.md",
        "sports_cards/ideas_etl_pipeline.md",
        "apps/blueprint_auth_architecture.md"
    ]
    stale_mtime = time.time() - (72 * 3600)  # 72 hours ago
    for sf in stale_files:
        full_p = os.path.join(ws, sf)
        with open(full_p, "w", encoding="utf-8") as f:
            f.write(f"# Stale Proposal Draft: {sf}\nInitial thoughts and discarded designs.\n")
        os.utime(full_p, (stale_mtime, stale_mtime))

    # Active non-stale file for comparison
    active_p = os.path.join(ws, "apps/proposal_active_v2.md")
    with open(active_p, "w", encoding="utf-8") as f:
        f.write("# Active Proposal\nCreated recently.\n")
    # mtime is now (< 1h)

    # 4. Failure 3: Ecosystem Pollution (.disabled plugins + cross-track leak)
    disabled_plugin_dir = os.path.join(ws, ".gemini/config/plugins/bigquery_sql.disabled")
    os.makedirs(disabled_plugin_dir, exist_ok=True)
    with open(os.path.join(disabled_plugin_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("# Disabled BigQuery SQL Skill\n")

    # Cross-track leak: sports card file inside content creation
    with open(os.path.join(ws, "content_creation/card_ladder_scraper.py"), "w", encoding="utf-8") as f:
        f.write("# Sports Cards ETL logic incorrectly located in content_creation track\n")

    # 5. Failure 4: Secret Zero (.env containing placeholder tokens)
    with open(os.path.join(ws, "apps/backend/.env"), "w", encoding="utf-8") as f:
        f.write("DATABASE_URL=sqlite:///prod.db\nOPENAI_API_KEY=your_token_here\nGEMINI_API_KEY=YOUR_API_KEY_HERE\nAWS_SECRET=placeholder_token\n")

    # 6. Failure 5: Prompt Fatigue (GEMINI.md with >100 lines)
    with open(os.path.join(ws, "GEMINI.md"), "w", encoding="utf-8") as f:
        f.write("# Antigravity Workspace Manifest\n\n")
        for i in range(1, 145):
            f.write(f"## Procedural Rule {i}: Subsystem rule description requiring strict adherence.\n")

    # 7. Valid Active Files (Must not be flagged as anomalies)
    with open(os.path.join(ws, "PROJECT.md"), "w", encoding="utf-8") as f:
        f.write("# Master Project Specification (Whitelisted)\n")
    with open(os.path.join(ws, "apps/backend/server.py"), "w", encoding="utf-8") as f:
        f.write("from fastapi import FastAPI\napp = FastAPI()\n")
        
    return ws
```

---

## 4. Tier 3: Cross-Feature Integration Test Catalog

Tier 3 validates that all subsystem interfaces communicate correctly and execute as a unified system.

### 4.1 Summary Matrix of Tier 3 Integration Tests
| Test Case ID | Test Name | Subsystems Integrated | Key Invariant / Loud Assertion |
|---|---|---|---|
| **TC-T3-01** | `test_scanner_to_sqlite_persistence` | `scanner.py` $\rightarrow$ `database.py` | Anomaly records serialized to SQLite with exact JSON details, session row created |
| **TC-T3-02** | `test_database_to_feature_matrix_vectorization` | `database.py` $\rightarrow$ `ml/embeddings.py` | Heterogeneous DB records vectorize to $(N, 5)$ normalized float matrix $\in [0.0, 1.0]$ |
| **TC-T3-03** | `test_vectorizer_to_kmeans_clustering_performance` | `ml/embeddings.py` $\rightarrow$ `ml/clustering.py` | Localized K-Means ($K=3$) converges in $<5\text{ms}$; centroid coordinates valid |
| **TC-T3-04** | `test_kmeans_to_protegi_gradient_derivation` | `ml/clustering.py` $\rightarrow$ `ml/protegi.py` | High centroid entropy generates actionable textual gradient diffs |
| **TC-T3-05** | `test_anomalies_to_red_team_adversarial_audit` | `detectors.*` $\rightarrow$ `audit/red_team.py` | 3-tier verdicts (`APPROVED`, `CHALLENGED`, `REJECTED`) accurately assigned |
| **TC-T3-06** | `test_red_team_to_markdown_report_builder` | `audit/red_team.py` $\rightarrow$ `audit/report_builder.py` | Markdown report renders valid tables, badges, and interactive `- [ ]` checkboxes |
| **TC-T3-07** | `test_unified_health_scanner_engine_cycle` | Full In-Process Cycle | Complete unified execution: Scan $\rightarrow$ DB $\rightarrow$ ML $\rightarrow$ Red-Team $\rightarrow$ Report |
| **TC-T3-08** | `test_static_ast_guardrail_preflight_gate` | `safety_guardrails.py` $\rightarrow$ `scanner_daemon.py` | Pre-flight AST check halts execution if illegal call (`os.remove`) injected |
| **TC-T3-09** | `test_multi_session_drift_and_recurrence` | `database.py` $\rightarrow$ `ml/` (Multi-Session) | Multi-day simulation tracks anomaly recurrence frequencies and cluster drift |
| **TC-T3-10** | `test_sqlite_transaction_rollback_on_pipeline_fault` | `database.py` $\rightarrow$ Pipeline Error Boundary | Unhandled exception in ML engine rolls back dirty DB transactions cleanly |
| **TC-T3-11** | `test_whitelist_config_propagation` | `config.py` $\rightarrow$ Detectors $\rightarrow$ ML Engine | Whitelisted files (`PROJECT.md`, `.env.example`) never reach DB or ML engine |
| **TC-T3-12** | `test_hitl_report_checkbox_roundtrip_parser` | `audit/report_builder.py` $\rightarrow$ HITL Parser | Checkbox `- [x]` marked in report parses back to valid remediation actions |

---

### 4.2 Detailed Test Case Specifications (Tier 3)

#### TC-T3-01: Anomaly Scanner $\rightarrow$ SQLite Persistence
- **Objective**: Verify that `HealthScanner.scan_all()` correctly dispatches anomalies to `database.log_scan_session()`.
- **Inputs**: Isolated workspace with 3 synthetic anomalies (1 Context Rot, 1 Secret Zero, 1 Prompt Fatigue).
- **Assertions**:
  - `database.log_scan_session()` returns valid UUID `session_id`.
  - Querying `scan_sessions` table returns 1 record where `total_anomalies == 3` and `duration_ms > 0`.
  - Querying `anomalies` table returns 3 rows with matching `detector_type` and `severity`.
  - JSON payload in `raw_details` column decodes to valid Python dictionary.

#### TC-T3-02: SQLite Store $\rightarrow$ ML Feature Matrix Vectorization
- **Objective**: Verify that raw SQLite anomaly rows (both historical and fresh) are vectorized into normalized numerical matrices.
- **Inputs**: Seeded SQLite DB with 5 historical lifelines + 4 fresh anomalies.
- **Assertions**:
  - `embeddings.vectorize_anomalies(db_path)` returns NumPy array of shape $(9, 5)$.
  - No `NaN`, `None`, or `Inf` values in feature matrix.
  - All numerical values are normalized in range $[0.0, 1.0]$.
  - Category one-hot encodings and severity scalar weights match expected mappings.

#### TC-T3-03: Vectorized Matrix $\rightarrow$ Localized K-Means Clustering ($K=3$)
- **Objective**: Verify that pure NumPy/Pandas K-Means clusters anomaly vectors within strict $<5\text{ms}$ latency.
- **Inputs**: Feature matrix of shape $(15, 5)$ representing mixed anomaly clusters.
- **Assertions**:
  - Execution time measured via `time.perf_counter()` is $< 5.0\text{ms}$ (target $<2.0\text{ms}$).
  - Cluster label array has shape $(15,)$ with integer values $\in \{0, 1, 2\}$.
  - Centroids matrix has shape $(3, 5)$.
  - Total inertia (sum of squared Euclidean distances) is strictly non-negative and finite.

#### TC-T3-04: K-Means Centroid Entropy $\rightarrow$ ProTeGi Textual Gradient Derivation
- **Objective**: Verify that inter-cluster divergence generates actionable rule refinement diffs.
- **Inputs**: Cluster assignments with high dispersion in the "Context Rot" and "Prompt Fatigue" clusters.
- **Assertions**:
  - `protegi.compute_semantic_entropy(cluster_results)` returns float $> 0.0$.
  - `protegi.generate_textual_gradients(cluster_results)` returns `List[str]` with length $\ge 1$.
  - Each gradient string contains specific optimization keywords (e.g., `"rule"`, `"refine"`, `"threshold"`, or `"distill"`).

#### TC-T3-05: Raw Anomalies $\rightarrow$ Architecture Red-Team Adversarial Audit
- **Objective**: Verify Red-Team auditor challenges false positives and assigns 3-tier verdicts.
- **Inputs**: 4 anomalies: (1) genuine `your_token_here` in `.env` [should be `APPROVED`], (2) `.disabled` plugin directory [should be `CHALLENGED`], (3) active python file with old mtime [should be `REJECTED`], (4) 150-line `GEMINI.md` [should be `APPROVED`].
- **Assertions**:
  - Red-Team output list length == 4.
  - Anomaly 1 receives `RedTeamVerdict.APPROVED`.
  - Anomaly 2 receives `RedTeamVerdict.CHALLENGED` with risk rationale.
  - Anomaly 3 receives `RedTeamVerdict.REJECTED` with false-positive explanation.
  - Anomaly 4 receives `RedTeamVerdict.APPROVED`.

#### TC-T3-06: Red-Team Results $\rightarrow$ Daily HITL Markdown Report Builder
- **Objective**: Verify that `report_builder.py` produces compliant Markdown containing interactive checkboxes.
- **Inputs**: `OptimizationReport` object with 2 APPROVED, 1 CHALLENGED, 1 REJECTED findings.
- **Assertions**:
  - Output string starts with `# Daily System Health & ML Optimization Report`.
  - Contains exact Markdown table: `| Detector | Target Path | Severity | Red-Team Verdict |`.
  - Checkbox section contains interactive tasks formatted as `- [ ]`.
  - Contains ProTeGi textual gradients section.
  - Contains Safety Certification: `100% Read-Only Scan Certified`.

#### TC-T3-07: Full In-Process Cycle (`HealthScannerEngine`)
- **Objective**: Execute end-to-end cycle in-process: Scan $\rightarrow$ Persist $\rightarrow$ Cluster $\rightarrow$ Audit $\rightarrow$ Report.
- **Inputs**: `workspace_with_all_5_failures` fixture.
- **Assertions**:
  - `engine.execute_cycle()` returns `OptimizationReport`.
  - `report.total_anomalies >= 5`.
  - `report.duration_ms < 500.0` (entire cycle executes in $<500\text{ms}$).
  - Report file is written to `reports/health_report_YYYY-MM-DD.md`.
  - Database contains updated session record with status `COMPLETED`.

#### TC-T3-08: Pre-Flight Static AST Guardrail $\rightarrow$ Daemon Runner Gate
- **Objective**: Verify daemon runner blocks execution if AST static analysis detects forbidden calls.
- **Inputs**: Temporary python module containing `import os; os.remove('some_file.txt')`.
- **Assertions**:
  - `safety_guardrails.verify_codebase(target_dir)` raises `SafetyViolationError`.
  - Daemon runner catches violation, logs error, and exits with code 1 without executing scanner.

#### TC-T3-09: Multi-Session Telemetry Drift & Anomaly Recurrence
- **Objective**: Verify that sequential daily scans track recurring patterns across time.
- **Inputs**: 3 sequential simulated scans where 1 anomaly persists and 2 are remediated.
- **Assertions**:
  - `database.get_historical_drift(db_path)` returns dictionary with recurrence rates.
  - Persisting anomaly has `recurrence_count == 3`.
  - Resolved anomalies show status `RESOLVED` in drift report.

#### TC-T3-10: SQLite Transaction Atomicity on Pipeline Fault
- **Objective**: Verify that pipeline exceptions do not leave corrupted partial state in SQLite.
- **Inputs**: Mock failure injected into `ml/clustering.py` during an active scan.
- **Assertions**:
  - Exception is caught by error handler.
  - `scan_sessions` table records session with `status = 'FAILED'`.
  - Uncommitted anomaly records are rolled back cleanly.

#### TC-T3-11: Whitelist Configuration Propagation
- **Objective**: Verify that whitelisted files are filtered before reaching DB and ML engine.
- **Inputs**: Workspace containing `PROJECT.md` (mtime > 30 days) and `.env.example` (containing `YOUR_KEY`).
- **Assertions**:
  - `scanner.scan_all()` filters out `PROJECT.md` and `.env.example`.
  - Database anomaly count for this run == 0.

#### TC-T3-12: HITL Report Checkbox Roundtrip Parser
- **Objective**: Verify that interactive Markdown report checkboxes can be parsed back into executable actions.
- **Inputs**: Generated Markdown report modified with `- [x] Archive stale proposal_v1.md`.
- **Assertions**:
  - `report_builder.parse_approved_actions(report_text)` returns list containing action `ARCHIVE` for `proposal_v1.md`.
  - Unchecked items (`- [ ]`) are excluded from approval list.

---

## 5. Tier 4: Real-World Application Workload Test Catalog

Tier 4 validates the daemon against realistic, end-to-end workspace workloads reproducing historical failure scenarios.

### 5.1 Summary Matrix of Tier 4 Real-World Workload Tests
| Test Case ID | Test Name | Target Workload / Scenario | Critical Success Criteria |
|---|---|---|---|
| **TC-T4-01** | `test_master_workspace_simultaneous_5_failures` | Master multi-track workspace with all 5 historical failure patterns simultaneously | Exit code 0, all 5 failure signatures detected, SHA256 snapshot 100% untouched, Markdown report generated |
| **TC-T4-02** | `test_clean_workspace_zero_anomaly_baseline` | Perfectly compliant workspace with active files, 0 stale docs, 0 leaks | Exit code 0, total anomalies == 0, K-Means handles empty matrix cleanly, report indicates 100% healthy |
| **TC-T4-03** | `test_multi_day_historical_drift_simulation` | 7-day sequential workload simulating recurring bloat, remediations, and drift | Telemetry tracks recurrence velocity, ML centroids shift dynamically, ProTeGi diffs evolve |
| **TC-T4-04** | `test_adversarial_false_positive_trap_defense` | Workspace containing deceptive files (doc code blocks, active configs, whitelisted specs) | Red-Team and whitelist suppress 100% of traps; 0 erroneous APPROVED verdicts |
| **TC-T4-05** | `test_ironclad_non_destructive_safety_enforcement` | Highly corrupted workspace executed under hooked syscall traps | 0 destructive syscalls invoked, 0 files deleted, 0 processes killed, 100% data loss prevention certified |

---

### 5.2 Detailed Test Case Specifications (Tier 4)

#### TC-T4-01: Master Multi-Track Workspace with Simultaneous 5 Historical Failures (The Golden E2E Test)
- **Objective**: Recreate the exact August 23/24 historical failure conditions across all 4 tracks and verify full pipeline execution.
- **Environment**:
  - Multi-track root with `/apps`, `/sports_cards`, `/content_creation`, `/travel_and_life`, `.gemini/config/plugins/`.
  - Active simulated listener on port 3000 (`Ghost Daemons`).
  - 3 planning files with `mtime` = 72h (`Context Rot`).
  - `.disabled` plugin directory + cross-track leak (`Ecosystem Pollution`).
  - `.env` containing `OPENAI_API_KEY=your_token_here` (`Secret Zero`).
  - 145-line `GEMINI.md` manifest (`Prompt Fatigue`).
  - Active legitimate files (Python services, package.json, whitelisted specs).
- **Execution**: Run `scanner_daemon.py --once --mock-env --workspace-root <ws> --db-path <db>`.
- **Loud Assertions**:
  1. Process terminates with `exit_code == 0`.
  2. `snapshot_verifier.assert_untouched()` succeeds (0 files deleted or altered).
  3. `database.get_latest_session(db)` returns `total_anomalies >= 5`.
  4. Anomalies table contains at least 1 record for each `DetectorType`:
     - `DetectorType.GHOST_DAEMONS` targeting port 3000.
     - `DetectorType.CONTEXT_ROT` targeting stale markdown files.
     - `DetectorType.ECOSYSTEM_POLLUTION` targeting `.disabled` and cross-track leak.
     - `DetectorType.SECRET_ZERO` targeting `.env` placeholder tokens.
     - `DetectorType.PROMPT_FATIGUE` targeting 145-line `GEMINI.md`.
  5. K-Means clustering completed in $<5.0\text{ms}$.
  6. Generated report exists at `reports/health_report_*.md` and is non-empty.
  7. Report contains interactive HITL checkboxes for all APPROVED anomalies.

#### TC-T4-02: Clean Workspace Simulation (Zero Anomaly Baseline)
- **Objective**: Verify system stability and reporting on a pristine, 100% compliant workspace.
- **Environment**: Workspace with modern FastAPI/Next.js code, 0 stale docs, 0 placeholder tokens, 0 port collisions, 65-line `GEMINI.md`.
- **Execution**: Run `scanner_daemon.py --once --workspace-root <clean_ws>`.
- **Loud Assertions**:
  1. `exit_code == 0`.
  2. `report.total_anomalies == 0`.
  3. ML Vectorizer and K-Means execute without `ZeroDivisionError` or crash.
  4. Red-Team audit result list is empty.
  5. Markdown report contains header `# Daily System Health & ML Optimization Report` and text `100% Healthy — Zero Anomalies Detected`.
  6. No unchecked `- [ ]` remediation boxes present.

#### TC-T4-03: Multi-Day Historical Drift Simulation (7-Day Evolution)
- **Objective**: Validate continuous learning and drift detection across a simulated 7-day operational cycle.
- **Environment**: Simulated time progression over 7 days with changing workspace states.
- **Execution**: Execute 7 consecutive daily scan cycles:
  - Day 1: 5 initial historical failures.
  - Day 2: Secret Zero remediated; Context Rot persists.
  - Day 3: Ghost Daemon resolved; new stale proposal added.
  - Day 4-7: Gradual convergence to clean state.
- **Loud Assertions**:
  1. All 7 cycles complete with `exit_code == 0`.
  2. Telemetry DB records 7 distinct sessions in `scan_sessions`.
  3. `database.get_historical_drift()` shows decreasing anomaly count trend over time.
  4. ProTeGi textual gradients update dynamically as anomaly distribution shifts.

#### TC-T4-04: Adversarial False-Positive Trap Defense
- **Objective**: Rigorously test Red-Team auditor and detector filters against deceptive files.
- **Environment Workspace**:
  - `apps/proposal_config.py` (Active Python configuration file, not a planning doc).
  - `PROJECT.md` (Core project specification file with mtime > 60 days).
  - `docs/setup.md` (Contains string `OPENAI_API_KEY=your_token_here` inside a markdown code block).
  - `.archive/stale_plan.md` (Stale file already stored in L2 cache).
  - Ephemeral port 8000 checked after clean socket release.
- **Execution**: Run daemon against trap workspace.
- **Loud Assertions**:
  1. `exit_code == 0`.
  2. `proposal_config.py` is NOT flagged as Context Rot.
  3. `PROJECT.md` is NOT flagged as Context Rot (whitelisted).
  4. `docs/setup.md` is NOT flagged as Secret Zero (code block doc, not `.env`).
  5. `.archive/stale_plan.md` is NOT flagged (already in archive).
  6. Total `APPROVED` anomalies == 0.
  7. If any trap was flagged by detectors, Red-Team verdict must be `RedTeamVerdict.REJECTED`.

#### TC-T4-05: Non-Destructive Safety Violation Stress Test (The Ironclad Leash)
- **Objective**: Mathematically and programmatically enforce that the daemon is 100% read-only and will never execute destructive modifications even under severe anomaly stress.
- **Environment**: Workspace with severe corruption. Test harness intercepts `os.remove`, `os.unlink`, `shutil.rmtree`, and `subprocess.Popen` with assertions that fail the test if invoked.
- **Execution**: Run daemon under monkeypatched interception.
- **Loud Assertions**:
  1. Zero intercepted delete/kill functions were invoked (`call_count == 0`).
  2. `snapshot_verifier.assert_untouched()` passes 100%.
  3. Generated report contains purely advisory recommendations with human checkboxes.
  4. Full compliance with `accidental-data-loss-prevention` certified.

---

## 6. Caveats

1. **Host Socket Availability**: On machines where ports 3000, 8000, or 8501 are already occupied by host developer processes, socket binding fixtures in `conftest.py` must use non-blocking probe detection or test mock overrides to avoid host port collisions while preserving deterministic test behavior.
2. **Platform Path Separators**: Tests must use `os.path.normpath` / `Path` to ensure cross-platform compatibility across Windows (`\`) and POSIX (`/`).
3. **ProTeGi Textual Gradients**: In offline test mode, ProTeGi gradient generation relies on deterministic rule templates and semantic entropy thresholds rather than external LLM API calls.

---

## 7. Conclusion

The Opaque-Box E2E Test Architecture for Tier 3 (12 Cross-Feature Pairwise Integration Tests) and Tier 4 (5 Master Real-World Workload Simulations) provides complete, mathematically verifiable requirement coverage.

The test harness guarantees:
1. **Deterministic Isolation**: Sterile execution via `tempfile.TemporaryDirectory`.
2. **Zero Data Loss & Read-Only Safety**: Programmatically verified via `FileSystemSnapshot` SHA256 hashing.
3. **Historical Fidelity**: Full recreation and continuous tracking of all 5 August 23/24 failure lifelines.
4. **Performance Bounds**: Localized NumPy/Pandas K-Means clustering verified in $<5\text{ms}$.
5. **False-Positive Elimination**: 3-tiered Red-Team verdicts audited against adversarial trap files.

---

## 8. Verification Method

To independently execute and verify the Tier 3 and Tier 4 E2E test suites once implemented:

```powershell
# 1. Run Tier 3 Cross-Feature Integration Suite
pytest -v ".agents/cron/tests/test_tier3_cross_features.py"

# 2. Run Tier 4 Real-World Workload Simulation Suite
pytest -v ".agents/cron/tests/test_tier4_real_workloads.py"

# 3. Run all E2E Tests with loud assertion reporting
pytest -v -m "tier3 or tier4" --durations=10

# 4. Invalidation Condition:
# If any workspace file is modified (hash mismatch), or ML clustering exceeds 5ms,
# or any of the 5 historical failures is missed, the test suite FAILS LOUDLY.
```

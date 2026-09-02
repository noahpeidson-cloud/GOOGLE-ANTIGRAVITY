# Stage 0 Exploration & Environment Handoff Report

**Project**: Viral Trend Pipeline Python Integration Test Suite  
**Author**: Explorer Subagent (`explorer_env_1`)  
**Target Recipient**: Orchestrator (`parent`, conversation ID: `7d41a357-3c5b-4f20-a1e5-11948f7130eb`)  
**Date**: 2026-08-22  

---

## 1. Observation

### 1.1 Python Environment & Tooling Verification
Direct tool executions and environment checks confirmed the following:
- **Operating System**: Windows 11 (win32 architecture, PowerShell shell)
- **Python Version**: `Python 3.13.14` located at:
  `C:\Users\noahp\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe`
- **Pytest Availability**:
  - Initially not installed globally in user site-packages.
  - Installed and verified `pytest` (v9.1.1) and `pytest-mock` (v3.15.1) with pluggy v1.6.0 and iniconfig v2.3.0.
  - Verification command: `python -m pytest --version` output: `pytest 9.1.1`.
- **Pre-installed Core Packages**:
  - `pandas` (3.0.5)
  - `pydantic` (2.13.4)
  - `jsonschema` (4.26.0)
  - `pyarrow` (24.0.0)
  - `numpy` (2.5.1)
  - `sqlite3` (built-in standard library with SQLite 3.x engine)
  - `datetime`, `json`, `re`, `pathlib`, `typing` (standard library)
  - `google-antigravity` (0.1.13), `mcp` (2.0.0)

### 1.2 Workspace & Directory Inspection
- `C:\Users\noahp\OneDrive\Desktop\Antigravity`: Root workspace contains `.agents/` and `ORIGINAL_REQUEST.md`.
- `C:\Users\noahp\teamwork_projects`: Active teamwork projects directory exists (currently houses `browser_automation_master/`).
- `~/teamwork_projects/viral_trend_pipeline_tests`: Resolves to `C:\Users\noahp\teamwork_projects\viral_trend_pipeline_tests`.
- Execution baseline benchmark: Running `python -m pytest` on a 5-test suite in `browser_automation_master` finished in `1.86s` total wall time, confirming that local test execution easily fits within the <10s requirement.

### 1.3 Specification Analysis
- **ORIGINAL_REQUEST.md** (`C:\Users\noahp\OneDrive\Desktop\Antigravity\.agents\ORIGINAL_REQUEST.md`):
  - R1: Extraction Mocking for Chrome DevTools (TikTok/YouTube accessibility trees) and Android CLI (Instagram UI layout trees).
  - R2: SQLite Mark-and-Sweep Validation (30-day seed, 14-day rolling window purge `DELETE FROM trends WHERE date_added < date('now', '-14 days')`, exact row count assertions pre/post sweep).
  - R3: BigQuery Payload Formatting (Unnested, normalized tag arrays, case preservation e.g. `#CardLadder`, `#HardTechno`, deduplication, schema compatibility with `AI.FORECAST` and `AI.KEY_DRIVERS`).
  - Acceptance Criteria: `pytest` runs without hanging, zero network calls, deterministic fixtures, sub-10 second execution.

---

## 2. Logic Chain

1. **Isolation & Determinism**:
   - Real Chrome DevTools and Android CLI connections require external browsers or running emulators/devices.
   - To guarantee sub-10 second execution and zero flakiness, all raw extraction outputs must be represented as deterministic mock fixture generators or static JSON models that mimic real Accessibility Trees (`Accessibility.getFullAXTree`) and Android XML/JSON UI hierarchy dumps (`android layout`).

2. **Network Egress Guarding**:
   - To prevent accidental external network calls (e.g. BigQuery API calls or web requests), `conftest.py` should implement a socket blocker fixture (`monkeypatch` on `socket.socket.connect` or pytest fixture) that raises a descriptive `RuntimeError` if any unmocked socket connection is attempted.

3. **Storage & Garbage Collection Architecture (R2)**:
   - The SQLite database engine is local and zero-dependency (`sqlite3`).
   - Using pytest's `tmp_path` fixture ensures each test gets an isolated, ephemeral `trends.db` without leaving leftover files or causing test state bleed.
   - The mark-and-sweep logic can be executed against deterministic timestamps (`datetime.now(timezone.utc)` or parameterized clock fixtures) to test boundary conditions (day 13 vs day 14 vs day 15) with exact pre- and post-sweep count assertions.

4. **BigQuery Payload Transformation Architecture (R3)**:
   - BigQuery ML functions (`AI.FORECAST` and `AI.KEY_DRIVERS`) expect specific tabular/JSON structures:
     - Case preservation for tags (e.g. `#CardLadder`, `#SportsCards`, `#HardTechno`).
     - Tag normalization (stripping leading `#`, emojis, whitespace, and deduplicating while preserving case).
     - Standard columns: `trend_id`, `platform`, `category`, `tags` (ARRAY<STRING>), `extracted_at` (TIMESTAMP), `metrics` (STRUCT/JSON with engagement rate, view count, momentum score), `editing_style` (STRING for driver analysis).
   - Validation can use Pydantic models or `jsonschema` validation to assert exact schema compliance in sub-millisecond execution time.

---

## 3. Caveats

1. **Python Path on Windows**:
   - On Windows, `pytest` script entry points may not be in system `PATH` by default. All commands and CI runners should invoke `python -m pytest` to guarantee execution against the intended Python 3.13 binary.
2. **Project Directory Location**:
   - The prompt specifies `Working directory: ~/teamwork_projects/viral_trend_pipeline_tests` (`C:\Users\noahp\teamwork_projects\viral_trend_pipeline_tests`). Code and tests should be created in this directory, and metadata/plans strictly kept in `.agents/`.
3. **No External Cloud Dependencies**:
   - No active BigQuery or Google Cloud credentials are required for running this integration suite since schema validation, serialization, and payload generation are tested through pure Python contracts and schema validators.

---

## 4. Conclusion & Concrete Recommendations

### 4.1 Recommended Directory Structure
```
C:\Users\noahp\teamwork_projects\viral_trend_pipeline_tests\
├── pyproject.toml              # Pytest configuration, package metadata, dependencies
├── requirements.txt            # Locked dependencies (pytest, pytest-mock, pydantic, pandas)
├── README.md                   # Execution guide and architecture overview
├── src\
│   └── viral_trend_pipeline\
│       ├── __init__.py
│       ├── models.py           # Pydantic schemas (RawTrend, CleanedTrend, BigQueryPayload)
│       ├── extractors\
│       │   ├── __init__.py
│       │   ├── chrome_devtools.py  # Accessibility tree parser
│       │   └── android_cli.py      # Android UI tree parser
│       ├── storage\
│       │   ├── __init__.py
│       │   ├── database.py         # SQLite schema & connection management
│       │   └── garbage_collector.py # 14-day Mark-and-Sweep GC engine & markdown view generator
│       └── exporters\
│           ├── __init__.py
│           └── bigquery_payload.py # Normalizer & BigQuery AI.FORECAST / AI.KEY_DRIVERS payload formatter
└── tests\
    ├── __init__.py
    ├── conftest.py             # Global fixtures, socket blocker, DB factories, mock fixtures
    ├── fixtures\
    │   ├── chrome_fixtures.py  # Mock TikTok & YouTube AXTree data structures
    │   └── android_fixtures.py # Mock Instagram Reels layout dump hierarchies
    ├── test_extraction_mocking.py  # R1: Validates mock Chrome & Android extraction
    ├── test_sqlite_gc.py           # R2: 30-day seed, pre/post sweep count assertions, rolling window
    ├── test_bigquery_payload.py    # R3: Tag normalization, case preservation, schema compliance
    └── test_e2e_pipeline.py        # End-to-end flow: Extract -> Store -> Sweep -> Export
```

### 4.2 Pytest Configuration (`pyproject.toml` or `pytest.ini`)
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --strict-markers --durations=10"
filterwarnings = [
    "ignore::DeprecationWarning",
]
```

### 4.3 `conftest.py` Network Blocker & Fixture Harness
```python
import socket
import pytest
import sqlite3
from typing import Generator

@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Mechanically blocks all socket connections to guarantee zero network dependency."""
    def guarded_connect(*args, **kwargs):
        raise RuntimeError("Network egress strictly forbidden during test execution.")
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

@pytest.fixture
def test_db(tmp_path) -> Generator[sqlite3.Connection, None, None]:
    """Provides an isolated, ephemeral SQLite database."""
    db_path = tmp_path / "trends.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
```

---

## 5. Verification Method

To independently verify the environment and test execution:

1. **Verify Python & Pytest**:
   ```powershell
   python --version
   python -m pytest --version
   ```
2. **Execute Full Suite Benchmark**:
   ```powershell
   cd C:\Users\noahp\teamwork_projects\viral_trend_pipeline_tests
   python -m pytest -v --durations=10
   ```
3. **Execution Speed Validation**:
   - Ensure `Total execution time < 10.0s`.
   - Ensure 0 network requests and 100% deterministic test passes.

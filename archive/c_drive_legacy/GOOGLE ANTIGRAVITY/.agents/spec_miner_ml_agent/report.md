# Antigravity ML Agent & Autonomy Loop Specification

**Document Version:** 1.0.0  
**Target Module:** `unified_ops_hub/ml_agent/`  
**Author:** Specification Miner (`spec_miner_ml_agent`)  
**Status:** Authoritative Architectural Specification  

---

## 1. Executive Summary & Architectural Overview

The **Antigravity ML Agent (`ml_agent.py`)** is an autonomous background orchestrator designed to automate, monitor, and optimize the multi-platform **Viral Trend Pipeline** (`viral-trend-pipeline`) and media workflows across Track 1 (Sports Cards) and Track 2 (EDM Content Creation).

Built natively on the **Google Antigravity Python SDK** (`google-antigravity`), the agent replaces fragile, unmonitored cron jobs with a closed-loop, self-optimizing state machine. It implements the **Localized Agent ML Optimization Loop** (`agent-ml-optimization-loop`), executing sub-5ms local K-Means clustering over SQLite telemetry to detect operational degradation, DOM drift, and rate limiting. When anomalies occur, the agent dynamically adjusts its execution policies (backoff multipliers, polling intervals, lens switching between Web Accessibility trees and Headless Android UI automations) and invokes **ProTeGi Textual Gradients** (`protegi-leash-enforcer`) to patch agent skill runbooks without human friction.

```
+---------------------------------------------------------------------------------------------------+
|                                  ANTIGRAVITY ML AGENT (ml_agent.py)                               |
|                                                                                                   |
|  +---------------------------+        +--------------------------+        +--------------------+  |
|  |     Antigravity SDK       |        |   Local Telemetry Hooks  |        | Budget & Guardrail |  |
|  |  - Agent (AUTONOMOUS)     |        |   - @hooks.on_turn_end   |        |  - BudgetConfig    |  |
|  |  - LocalAgentConfig       | =====> |   - @hooks.post_tool_call| =====> |  - StopReason      |  |
|  |  - triggers.every(cron)   |        |   - @hooks.on_tool_error |        |  - Rule R2 & R16   |  |
|  +---------------------------+        +--------------------------+        +--------------------+  |
|               ||                                   ||                                             |
|               \/                                   \/                                             |
|  +---------------------------------------------------------------------------------------------+  |
|  |                             SQLite Telemetry Engine (ml_telemetry.db)                       |  |
|  |  - Table: scraping_telemetry (span_id, platform, lens_type, duration_ms, yield, errors...)  |  |
|  |  - Table: execution_policies (platform, active_lens, poll_interval_sec, backoff_base...)   |  |
|  |  - Table: protegi_gradient_log (gradient_id, entropy, critique_text, diff, applied_status)|  |
|  +---------------------------------------------------------------------------------------------+  |
|                                                ||                                                 |
|                                                \/                                                 |
|  +---------------------------------------------------------------------------------------------+  |
|  |                             Pandas / Scikit-Learn K-Means Engine                            |  |
|  |  - Local Feature Vector: [Duration_norm, YieldRate_norm, ErrorRate_norm]                    |  |
|  |  - Cluster 0: Healthy / High-Yield   ==> Maintain / Accelerate cadence                     |  |
|  |  - Cluster 1: Degraded / Rate-Limited==> Exponential Backoff & Cadence Throttling          |  |
|  |  - Cluster 2: DOM Drift / Zero Yield ==> Fallback to Android Lens & ProTeGi Gradient Pass   |  |
|  +---------------------------------------------------------------------------------------------+  |
|               ||                                                   ||                             |
|               \/                                                   \/                             |
|  +---------------------------+                        +----------------------------------------+  |
|  |  Multi-Platform Scraping  |                        |       ProteGi Leash Alignment Loop     |  |
|  |  - Lens A: Web DevTools   |                        |  - Entropy Evaluation & Critique       |  |
|  |    (A11y Tree Extraction) |                        |  - Dynamic SKILL.md Prompt Update      |  |
|  |  - Lens B: Headless       |                        |  - Zero-Discretion Red-Team Audit      |  |
|  |    Android (android layout|                        +----------------------------------------+  |
|  +---------------------------+                                                                    |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Features Discovered & Mined

The following feature inventory documents all public interfaces, configuration dials, lifecycle hooks, database models, and operational capabilities discovered from authoritative SDK references and workspace skills.

### Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | SDK Core | `LocalAgentConfig` Construction | Configures root agent behavior, model, system instructions, tools, budget limits, subagents, and triggers | `model: str = "gemini-3.7-flash"`, `capabilities: CapabilitiesConfig`, `budget_config: BudgetConfig`, `hooks: list`, `triggers: list`, `subagents: list` | `LocalAgentConfig` instance | `AntigravityValidationError` on relative paths or invalid budget configurations | SDK `agent_configuration.md` |
| 2 | SDK Core | Autonomous Behavior Dial | Enforces non-interactive, goal-directed background execution without blocking on human prompts | `types.CapabilitiesConfig(agent_behavior=types.AgentBehavior.AUTONOMOUS)` | Configured capabilities object | Warning logged if interactive tools enabled without interactive behavior | SDK `agent_configuration.md` |
| 3 | SDK Core | Session Budget & StopReason | Prevents runaway execution cascades and token exhaustion via strict call and token limits | `types.BudgetConfig(max_model_calls=15, max_tool_calls=30, max_total_tokens=150_000)` | Enforced ceilings, `response.stop_reason` populated | Session halts with `types.StopReason.MAX_*_EXCEEDED` | SDK `budget_limits.md` |
| 4 | SDK Core | Periodic Trigger Dispatch | Spawns recurring background execution intervals inside the agent runtime | `triggers.every(interval_seconds, callback_fn)` | `TriggerContext` passed to callback | Propagates exceptions to root logging; triggers keep running | SDK `periodic_trigger.md` |
| 5 | SDK Core | Subagent Delegation & Depth Limits | Allows root ML agent to delegate platform scraping to isolated subagents with explicit allowlists | `types.SubagentConfig(name="scraper_lens", capabilities=SubagentCapabilities(enabled_tools=[...]))`, `max_subagent_depth=2` | Subagent execution stream & aggregated text | Tool execution rejected if subagent not in `allowed_subagents` | SDK `subagents.md` |
| 6 | Observability | Turn & Tool Lifecycle Hooks | Intercepts agent turns and tool invocations to collect execution spans and token metrics | `@hooks.on_turn_end`, `@hooks.post_tool_call`, `@hooks.on_tool_error` | Metric dictionary or modified return data | `OnToolErrorHook` can supply fallback strings or bubble up | SDK `hooks.md` |
| 7 | Storage | SQLite Telemetry Store | Thread-safe, WAL-enabled telemetry database recording granular scraping spans, yield counts, and latency | `ml_telemetry.db` path, SQL schema DDL, span records | Row IDs, queried dataframes | `sqlite3.DatabaseError` on disk failure; WAL prevents locks | `agent-ml-optimization-loop` |
| 8 | ML Analytics | Localized K-Means Clustering | Segments scraping spans into 3 behavioral clusters (Healthy, Degraded, Failing) in < 5ms without cloud latency | Normalized $N \times 3$ matrix `[latency, yield_rate, error_rate]` | Cluster labels `[0, 1, 2]`, centroid coordinates | Degrades to rule-based fallback if sample count $N < 3$ | `agent-ml-optimization-loop` |
| 9 | Policy Engine | Closed-Loop Policy Self-Adjustment | Adjusts polling frequency, retry backoff bases, and active scraping lens based on cluster assignments | Current cluster ID, historical telemetry window | Updated `execution_policies` row | Reverts to conservative defaults on invalid state transitions | `agent-ml-optimization-loop` |
| 10 | Trend Pipeline | Web Accessibility Tree Lens | Scrapes TikTok Creative Center and YouTube Trending via Chrome DevTools Accessibility tree | Target URL, DevTools WebSocket / MCP connection | Trend records `(hashtag, audio, velocity_score)` | Flags DOM drift if required a11y nodes (`Role="heading"`) missing | `viral-trend-pipeline` |
| 11 | Trend Pipeline | Headless Android Layout Lens | Scrapes mobile-only apps (IG Reels, FB Reels) by launching headless emulator and parsing UI trees | `android layout -p --device=<serial>` | JSON layout tree with resource IDs, text, content-desc | Returns non-zero exit code if emulator disconnected or ADB hangs | `viral-trend-pipeline` & `android-cli` |
| 12 | Trend Pipeline | Rolling 14-Day Garbage Collection | Purges stale trends from `trends.db` to prevent context bloat and exports active `current_trends.md` | `DELETE FROM trends WHERE date_added < date('now', '-14 days')` | Clean rolling trend catalog | Atomic transaction rollback on constraint violation | `viral-trend-pipeline` |
| 13 | Alignment | ProTeGi Textual Gradient Pass | Generates a backward pass critique on prompt/skill divergence when semantic entropy is detected | Flawed execution transcript, failed assertion log | Hardened prompt diff, revised `SKILL.md` | Halts execution and triggers `/grill-me` if structural params missing | `protegi-leash-enforcer` |
| 14 | Testing | Deterministic Loud Assertion Harness | Enforces Rule R2 trustless verification with zero shared state and isolated SQLite in-memory fixtures | PyTest test cases, mock platform fixtures | Binary assertion pass/fail with explicit debug diff | Test fails immediately with descriptive diagnostic output | GEMINI.md Rule R2 & `protegi-leash-enforcer` |

---

## 3. Edge Cases & Empirical Observations

| # | Feature | Input / Condition | Observed Behavior & Authoritative Handling |
|---|---------|-------------------|---------------------------------------------|
| 1 | K-Means Engine | Sparse Telemetry ($N < 3$ spans) | K-Means clustering algorithm requires $N \ge K$. Handler MUST bypass clustering and fall back to single-span deterministic thresholds (`error_count > 0` $\rightarrow$ Degraded) until $N \ge 10$. |
| 2 | K-Means Engine | Zero Variance in Metric (e.g., all error rates = 0.0) | Standard scaler division by zero ($\sigma = 0$). Handler MUST use $\sigma' = \max(\sigma, 1e-6)$ or MinMax scaling to prevent `NaN` feature values. |
| 3 | SDK Budget | `max_tool_calls` reached during multi-platform scrape | SDK halts agent session immediately with `StopReason.MAX_TOOL_CALLS_EXCEEDED`. The agent catches this in the session wrapper, flushes partial telemetry to SQLite, and commits transaction. |
| 4 | Web DevTools Lens | Bot detection / Captcha screen encountered | Accessibility tree lacks standard trend headings and contains "Verify you are human". Scrape yields 0 items with status `DOM_DRIFT` (Cluster 2). Policy engine switches active lens to `android_ui_dump`. |
| 5 | Android CLI Lens | Headless emulator boot timeout or ADB server drop | Subprocess command `android layout` fails with timeout or exit code 1. Scrape logs error `DEVICE_OFFLINE`. Policy triggers exponential backoff ($2.0 \times$) and emits health check alert. |
| 6 | SQLite Concurrency | Concurrent writes from trigger loop and background auditor | Standard SQLite locks with `OperationalError: database is locked`. Enforce `PRAGMA journal_mode=WAL;` and `busy_timeout=5000` on database initialization. |
| 7 | Trend DB GC | Rolling window deletion when no records are older than 14 days | `DELETE FROM trends WHERE date_added < date('now', '-14 days')` executes as a no-op ($0$ rows affected). System continues cleanly and generates `current_trends.md` without error. |
| 8 | ProTeGi Gradient | High semantic entropy detected in synthetic test branches | Agent generates structured multiple-choice critique, updates local candidate prompt, and rejects self-certification per Rule R2. |

---

## 4. Antigravity SDK Autonomous Orchestrator Architecture (`ml_agent.py`)

### 4.1 Orchestrator Module Design
The `ml_agent.py` script acts as an autonomous background daemon. In accordance with **Rule R16**, all imports are strictly absolute.

```python
# Absolute Imports Only (Rule R16)
import asyncio
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from google.antigravity import Agent, LocalAgentConfig, hooks, triggers, types
```

### 4.2 LocalAgentConfig & Capabilities Configuration
The agent is configured for non-interactive autonomous execution with strict token and tool dial limits:

```python
def build_ml_agent_config(
    db_path: str,
    app_data_dir: str,
    interval_seconds: int = 3600,
) -> LocalAgentConfig:
    """Constructs the authoritative LocalAgentConfig for the ML Agent."""
    
    # 1. Budget Limits Guardrail
    budget_config = types.BudgetConfig(
        max_model_calls=20,
        max_tool_calls=50,
        max_input_tokens=150_000,
        max_output_tokens=30_000,
        max_total_tokens=180_000,
    )
    
    # 2. Capabilities & Subagent Permissions
    capabilities = types.CapabilitiesConfig(
        agent_behavior=types.AgentBehavior.AUTONOMOUS,
        enable_subagents=True,
        max_subagent_depth=2,
        allowed_subagents=["web_lens_worker", "android_lens_worker"],
    )
    
    # 3. Subagent Definitions
    web_worker = types.SubagentConfig(
        name="web_lens_worker",
        description="Extracts viral trends from Web Accessibility trees via Chrome DevTools",
        capabilities=types.SubagentCapabilities(
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
            enabled_tools=[types.BuiltinTools.VIEW_FILE, types.BuiltinTools.RUN_COMMAND],
        ),
    )
    
    android_worker = types.SubagentConfig(
        name="android_lens_worker",
        description="Extracts viral trends from mobile apps using headless Android UI hierarchy",
        capabilities=types.SubagentCapabilities(
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
            enabled_tools=[types.BuiltinTools.RUN_COMMAND, types.BuiltinTools.VIEW_FILE],
        ),
    )
    
    # 4. Triggers (Recurring autonomous execution)
    trend_trigger = triggers.every(
        interval_seconds,
        lambda ctx: run_trend_cycle_trigger(ctx, db_path)
    )
    
    # 5. Lifecycle Hooks Registration
    config = LocalAgentConfig(
        model="gemini-3.7-flash",
        app_data_dir=os.path.abspath(app_data_dir),
        budget_config=budget_config,
        capabilities=capabilities,
        subagents=[web_worker, android_worker],
        triggers=[trend_trigger],
        hooks=[
            telemetry_post_tool_hook,
            telemetry_turn_end_hook,
            telemetry_tool_error_hook,
        ],
        system_instructions=(
            "You are the Antigravity Autonomous ML Orchestrator. "
            "Your objective is to execute, monitor, and optimize the viral trend pipeline. "
            "You collect execution telemetry, evaluate cluster health via local K-Means, "
            "and dynamically adapt lens selection and retry backoffs. "
            "You adhere strictly to Rule R2 (Zero-Discretion Mandate)."
        ),
    )
    return config
```

### 4.3 Lifecycle Hooks for Telemetry Ingestion
Lifecycle hooks intercept each execution turn and tool execution without modifying application business logic:

```python
@hooks.post_tool_call
async def telemetry_post_tool_hook(tool_call_data: Any) -> None:
    """Captures granular tool execution timing and output size."""
    # Records tool duration, parameters, and success state
    pass

@hooks.on_turn_end
async def telemetry_turn_end_hook(turn_context: Any, turn_result: Any) -> None:
    """Persists model token consumption and transcript span metadata."""
    pass

@hooks.on_tool_error
async def telemetry_tool_error_hook(error: Exception) -> Optional[str]:
    """Catches tool execution failures, logs error signatures, and allows graceful fallback."""
    logging.error(f"[ML_AGENT_HOOK] Tool error intercepted: {error}")
    return "[TOOL_ERROR_INTERCEPTED: Recovering via fallback policy]"
```

---

## 5. SQLite Telemetry Schema & Storage Architecture

The telemetry backend uses a dedicated SQLite database (`ml_telemetry.db`) configured with Write-Ahead Logging (`WAL`) mode to support concurrent writes from agent triggers and reader threads.

### 5.1 DDL Schema Definition

```sql
-- Enable High-Concurrency WAL Mode
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;

-- 1. Master Scraping Telemetry Spans
CREATE TABLE IF NOT EXISTS scraping_telemetry (
    span_id TEXT PRIMARY KEY,
    timestamp_ms INTEGER NOT NULL,
    platform TEXT NOT NULL CHECK(platform IN ('tiktok', 'youtube_shorts', 'instagram_reels', 'facebook_reels')),
    lens_type TEXT NOT NULL CHECK(lens_type IN ('web_a11y_tree', 'android_ui_dump', 'dom_selector', 'api_gateway')),
    duration_ms INTEGER NOT NULL CHECK(duration_ms >= 0),
    yield_count INTEGER NOT NULL CHECK(yield_count >= 0),
    error_count INTEGER NOT NULL CHECK(error_count >= 0),
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    status_code TEXT NOT NULL CHECK(status_code IN ('SUCCESS', 'RATE_LIMITED', 'DOM_DRIFT', 'EMPTY_YIELD', 'NETWORK_TIMEOUT', 'PROCESS_CRASH')),
    cluster_label INTEGER DEFAULT -1,
    metadata_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_telemetry_platform_ts 
ON scraping_telemetry(platform, timestamp_ms DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_cluster 
ON scraping_telemetry(cluster_label);

-- 2. Dynamic Execution Policies
CREATE TABLE IF NOT EXISTS execution_policies (
    platform TEXT PRIMARY KEY CHECK(platform IN ('tiktok', 'youtube_shorts', 'instagram_reels', 'facebook_reels')),
    active_lens TEXT NOT NULL CHECK(active_lens IN ('web_a11y_tree', 'android_ui_dump')),
    poll_interval_sec INTEGER NOT NULL CHECK(poll_interval_sec >= 60),
    retry_backoff_base_sec REAL NOT NULL CHECK(retry_backoff_base_sec >= 1.0),
    max_retries INTEGER NOT NULL CHECK(max_retries >= 0 AND max_retries <= 10),
    last_adjusted_at INTEGER NOT NULL,
    adjustment_reason TEXT NOT NULL,
    policy_version INTEGER NOT NULL DEFAULT 1
);

-- 3. ProTeGi Textual Gradient Alignment Logs
CREATE TABLE IF NOT EXISTS protegi_gradient_log (
    gradient_id TEXT PRIMARY KEY,
    timestamp_ms INTEGER NOT NULL,
    target_skill_path TEXT NOT NULL,
    divergence_entropy REAL NOT NULL,
    critique_text TEXT NOT NULL,
    gradient_diff TEXT NOT NULL,
    applied_status TEXT NOT NULL CHECK(applied_status IN ('PROPOSED', 'AUDITED', 'APPLIED', 'REJECTED'))
);

-- Seed Baseline Execution Policies
INSERT OR IGNORE INTO execution_policies 
(platform, active_lens, poll_interval_sec, retry_backoff_base_sec, max_retries, last_adjusted_at, adjustment_reason, policy_version)
VALUES
('tiktok', 'web_a11y_tree', 3600, 2.0, 3, strftime('%s', 'now') * 1000, 'Initial baseline seed', 1),
('youtube_shorts', 'web_a11y_tree', 7200, 2.0, 3, strftime('%s', 'now') * 1000, 'Initial baseline seed', 1),
('instagram_reels', 'android_ui_dump', 3600, 2.5, 3, strftime('%s', 'now') * 1000, 'Initial baseline seed', 1),
('facebook_reels', 'android_ui_dump', 14400, 2.0, 2, strftime('%s', 'now') * 1000, 'Initial baseline seed', 1);
```

### 5.2 Metrics Ingestion API (`TelemetryStore`)

```python
class TelemetryStore:
    """Encapsulates all SQLite telemetry database interactions with WAL concurrency."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            # Executes DDL above
            pass

    def record_span(
        self,
        platform: str,
        lens_type: str,
        duration_ms: int,
        yield_count: int,
        error_count: int,
        status_code: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        metadata_json: str = "{}",
    ) -> str:
        span_id = str(uuid.uuid4())
        ts = int(time.time() * 1000)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO scraping_telemetry 
                (span_id, timestamp_ms, platform, lens_type, duration_ms, yield_count, error_count, input_tokens, output_tokens, status_code, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (span_id, ts, platform, lens_type, duration_ms, yield_count, error_count, input_tokens, output_tokens, status_code, metadata_json),
            )
            conn.commit()
        return span_id

    def get_recent_spans(self, platform: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
        query = "SELECT * FROM scraping_telemetry"
        params = []
        if platform:
            query += " WHERE platform = ?"
            params.append(platform)
        query += " ORDER BY timestamp_ms DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        return df

    def update_cluster_labels(self, span_cluster_map: Dict[str, int]) -> None:
        with self._get_connection() as conn:
            conn.executemany(
                "UPDATE scraping_telemetry SET cluster_label = ? WHERE span_id = ?",
                [(cluster, span_id) for span_id, cluster in span_cluster_map.items()],
            )
            conn.commit()

    def get_policy(self, platform: str) -> Dict[str, Any]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM execution_policies WHERE platform = ?", (platform,)
            ).fetchone()
            return dict(row) if row else {}

    def update_policy(
        self,
        platform: str,
        active_lens: str,
        poll_interval_sec: int,
        retry_backoff_base_sec: float,
        reason: str,
    ) -> None:
        ts = int(time.time() * 1000)
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE execution_policies 
                SET active_lens = ?, poll_interval_sec = ?, retry_backoff_base_sec = ?, 
                    last_adjusted_at = ?, adjustment_reason = ?, policy_version = policy_version + 1
                WHERE platform = ?
                """,
                (active_lens, poll_interval_sec, retry_backoff_base_sec, ts, reason, platform),
            )
            conn.commit()
```

---

## 6. Local K-Means Clustering Strategy & Feature Engineering

Per the authoritative mandate in `agent-ml-optimization-loop`:
> *"Do NOT use BigQuery ML. Use local `pandas` and `numpy` to identify poor execution patterns... This process must execute in < 5ms locally."*

### 6.1 Feature Transformation & Normalization Pipeline

For each platform, the clustering engine extracts the rolling window of the last $N$ spans ($N \ge 10$, default $N=50$) and constructs a 3-dimensional normalized feature matrix $X \in \mathbb{R}^{N \times 3}$:

1. **Normalized Latency ($f_1$):**
   $$f_1 = \frac{\text{duration\_ms} - \mu_{\text{duration}}}{\max(\sigma_{\text{duration}}, 1e-6)}$$
2. **Normalized Yield Rate ($f_2$):**
   $$\text{yield\_rate} = \frac{\text{yield\_count}}{\max(\text{duration\_ms} / 1000.0, 0.1)}$$
   $$f_2 = \frac{\text{yield\_rate} - \mu_{\text{yield\_rate}}}{\max(\sigma_{\text{yield\_rate}}, 1e-6)}$$
3. **Normalized Error Rate ($f_3$):**
   $$\text{error\_rate} = \frac{\text{error\_count}}{\max(1, \text{yield\_count} + \text{error\_count})}$$
   $$f_3 = \frac{\text{error\_rate} - \mu_{\text{error\_rate}}}{\max(\sigma_{\text{error\_rate}}, 1e-6)}$$

### 6.2 3-Cluster Behavioral Semantic Model ($K=3$)

| Cluster ID | Semantic Profile | Centroid Signature $[f_1, f_2, f_3]$ | Observed State | Triggered Action |
|------------|------------------|--------------------------------------|----------------|------------------|
| **0** | **Healthy & Optimal** | $[< 0, > 0, \le 0]$ | Low duration, high item yield, zero or near-zero errors. | Maintain normal scraping frequency; gently restore baseline intervals if recovering. |
| **1** | **Degraded / Rate Limited** | $[> 0, \le 0, \ge 0]$ | High duration (timeouts/lags), low/moderate yield, rate-limit warnings. | Increase `poll_interval_sec` ($1.5\times$), multiply `retry_backoff_base_sec` ($2.0\times$). |
| **2** | **Critical Failure / DOM Shift** | $[0 \pm \delta, \ll 0, \gg 0]$ | Zero items extracted, high error counts, parsing exceptions. | Switch `active_lens` (e.g. Web A11y $\rightarrow$ Android Layout); trigger ProTeGi gradient audit. |

### 6.3 Local K-Means Implementation (`KMeansOptimizer`)

```python
class KMeansOptimizer:
    """Localized, sub-5ms K-Means clustering engine using Numpy & Pandas."""

    def __init__(self, k: int = 3, random_state: int = 42):
        self.k = k
        self.random_state = random_state

    def fit_predict(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, Dict[str, int]]:
        """
        Executes feature scaling and K-Means clustering.
        Returns: (cluster_labels, centroids, cluster_counts)
        """
        if len(df) < self.k:
            # Deterministic heuristic fallback for sparse cold start
            labels = np.zeros(len(df), dtype=int)
            for i, row in df.iterrows():
                if row['error_count'] > 0 and row['yield_count'] == 0:
                    labels[i] = 2
                elif row['error_count'] > 0 or row['duration_ms'] > 15000:
                    labels[i] = 1
                else:
                    labels[i] = 0
            return labels, np.zeros((self.k, 3)), dict(pd.Series(labels).value_counts())

        # Feature Extraction
        duration = df['duration_ms'].values.astype(float)
        duration_sec = np.maximum(duration / 1000.0, 0.1)
        yield_rate = df['yield_count'].values.astype(float) / duration_sec
        total_ops = np.maximum(1.0, df['yield_count'].values + df['error_count'].values)
        error_rate = df['error_count'].values.astype(float) / total_ops

        # Z-Score Standardization (Guarding against zero variance)
        f1 = (duration - np.mean(duration)) / max(np.std(duration), 1e-6)
        f2 = (yield_rate - np.mean(yield_rate)) / max(np.std(yield_rate), 1e-6)
        f3 = (error_rate - np.mean(error_rate)) / max(np.std(error_rate), 1e-6)
        X = np.column_stack([f1, f2, f3])

        # Local vectorized K-Means with K-Means++ initialization
        np.random.seed(self.random_state)
        n_samples = X.shape[0]
        
        # 1. K-Means++ Centroid Init
        centroids = [X[np.random.choice(n_samples)]]
        for _ in range(1, self.k):
            dists = np.min([np.sum((X - c) ** 2, axis=1) for c in centroids], axis=0)
            probs = dists / max(np.sum(dists), 1e-9)
            centroids.append(X[np.random.choice(n_samples, p=probs)])
        centroids = np.array(centroids)

        # 2. Lloyd's Iteration (Max 15 iterations for sub-5ms performance)
        labels = np.zeros(n_samples, dtype=int)
        for _ in range(15):
            # Compute Euclidean distances to centroids
            distances = np.linalg.norm(X[:, np.newaxis, :] - centroids[np.newaxis, :, :], axis=2)
            new_labels = np.argmin(distances, axis=1)
            if np.array_equal(labels, new_labels):
                break
            labels = new_labels
            # Update centroids
            for j in range(self.k):
                members = X[labels == j]
                if len(members) > 0:
                    centroids[j] = np.mean(members, axis=0)

        # Map cluster IDs to semantic ordering:
        # Cluster 0 = Lowest error & highest yield
        # Cluster 2 = Highest error & lowest yield
        scores = centroids[:, 2] - centroids[:, 1]  # error_norm - yield_norm
        rank_order = np.argsort(scores)  # [best_idx, medium_idx, worst_idx]
        
        remap = {rank_order[0]: 0, rank_order[1]: 1, rank_order[2]: 2}
        final_labels = np.array([remap[lbl] for lbl in labels])
        final_centroids = centroids[rank_order]

        counts = dict(pd.Series(final_labels).value_counts())
        return final_labels, final_centroids, counts
```

---

## 7. Self-Adjusting Closed-Loop Execution Policy

The execution policy engine runs after every scraping cycle or every $M=10$ telemetry spans. It calculates the dominance of degraded or failing clusters and transitions the operational dials.

```
+-----------------------------------------------------------------------------------+
|                           CLOSED-LOOP POLICY STATE MACHINE                        |
|                                                                                   |
|            +----------------------------------------------------------+           |
|            |                                                          |           |
|            v                                                          |           |
|  +--------------------+     Cluster 1 (Rate Limit)     +-----------------------+  |
|  |     HEALTHY        | -----------------------------> |      THROTTLED        |  |
|  |  - Interval: Base  |                                |  - Interval: 1.5x     |  |
|  |  - Backoff: 2.0x   | <----------------------------- |  - Backoff: 4.0x      |  |
|  |  - Lens: Primary   |      Cluster 0 (Recovery)      |  - Lens: Primary      |  |
|  +--------------------+                                +-----------------------+  |
|            |                                                          |           |
|            | Cluster 2 (DOM Drift)                                    | Cluster 2 |
|            v                                                          v           |
|  +-----------------------------------------------------------------------------+  |
|  |                            LENS FAILOVER / AUDIT                            |  |
|  |  - Switch Lens: Web A11y Tree <===> Headless Android Layout                 |  |
|  |  - Backoff: Exponential Base 3.0x                                           |  |
|  |  - Trigger ProTeGi Alignment Backward Pass to update SKILL.md               |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### 7.1 Dynamic Adjustment Logic

```python
class PolicyEngine:
    """Evaluates cluster distributions and mutates execution policies."""

    def __init__(self, telemetry_store: TelemetryStore, k_means: KMeansOptimizer):
        self.store = telemetry_store
        self.k_means = k_means

    def evaluate_and_adjust(self, platform: str) -> Dict[str, Any]:
        df = self.store.get_recent_spans(platform=platform, limit=50)
        if len(df) < 3:
            return {"action": "NO_OP", "reason": "Insufficient telemetry spans"}

        labels, centroids, counts = self.k_means.fit_predict(df)
        
        # Persist updated cluster labels back to SQLite
        span_cluster_map = dict(zip(df['span_id'], labels))
        self.store.update_cluster_labels(span_cluster_map)

        current_policy = self.store.get_policy(platform)
        current_lens = current_policy.get('active_lens', 'web_a11y_tree')
        current_interval = current_policy.get('poll_interval_sec', 3600)
        current_backoff = current_policy.get('retry_backoff_base_sec', 2.0)

        recent_window = labels[:10]  # Most recent 10 spans
        c0_rate = np.mean(recent_window == 0)
        c1_rate = np.mean(recent_window == 1)
        c2_rate = np.mean(recent_window == 2)

        # 1. Critical Failure / DOM Drift (Cluster 2 dominance > 40%)
        if c2_rate >= 0.4:
            new_lens = "android_ui_dump" if current_lens == "web_a11y_tree" else "web_a11y_tree"
            new_interval = max(current_interval, 7200)
            new_backoff = min(current_backoff * 1.5, 8.0)
            reason = f"Cluster 2 (DOM Drift/Zero Yield) detected ({c2_rate:.1%}). Switching lens to {new_lens}."
            self.store.update_policy(platform, new_lens, new_interval, new_backoff, reason)
            return {"action": "LENS_SWAP", "new_lens": new_lens, "reason": reason}

        # 2. Rate Limiting / Degradation (Cluster 1 dominance > 50%)
        elif c1_rate >= 0.5:
            new_interval = min(int(current_interval * 1.5), 28800)  # Max 8 hours
            new_backoff = min(current_backoff * 2.0, 10.0)
            reason = f"Cluster 1 (Rate Limit/Lag) detected ({c1_rate:.1%}). Throttling cadence."
            self.store.update_policy(platform, current_lens, new_interval, new_backoff, reason)
            return {"action": "THROTTLE", "new_interval": new_interval, "reason": reason}

        # 3. Healthy Recovery (Cluster 0 dominance > 80%)
        elif c0_rate >= 0.8 and current_interval > 3600:
            new_interval = max(int(current_interval * 0.8), 3600)
            new_backoff = max(current_backoff * 0.8, 2.0)
            reason = f"Cluster 0 (Healthy) sustained ({c0_rate:.1%}). Restoring baseline cadence."
            self.store.update_policy(platform, current_lens, new_interval, new_backoff, reason)
            return {"action": "RECOVER", "new_interval": new_interval, "reason": reason}

        return {"action": "MAINTAIN", "reason": "System operating within acceptable entropy bounds"}
```

---

## 8. Viral Trend Pipeline Monitoring & Dual-Lens Scraping

The ML agent actively orchestrates and monitors the multi-platform scraping targets defined in `viral-trend-pipeline/SKILL.md`.

### 8.1 Multi-Platform Dual-Lens Matrix

| Target Platform | Primary Scraping Lens | Fallback Scraping Lens | Extraction Target | Output Validation Contract |
|-----------------|-----------------------|------------------------|-------------------|----------------------------|
| **TikTok** | Web DevTools MCP (`a11y` tree on Creative Center) | Headless Android (`android layout` on TikTok App) | Trending audio titles, 3-5 hashtags (`#HardTechno`, `#SportsCards`), 7-day velocity score | Array of valid trend objects; non-empty audio string; velocity $> 0$. |
| **YouTube Shorts** | Web DevTools MCP (`a11y` tree on Trending feed) | Headless Android (`android layout` on YouTube App) | Video titles, search keywords, sound metadata, view velocity | SEO title length $\le 100$ chars; category matched to Cards/EDM. |
| **Instagram Reels** | Headless Android (`android layout` on IG App) | Web DevTools MCP (`a11y` tree on IG Explore) | Audio sound IDs, carousel visual overlays, shareability hashtags | 10-15 niche tags (`#TheHobby`, `#CardLadder`); audio track verified. |
| **Facebook Reels** | Headless Android (`android layout` on FB App) | Web DevTools MCP (`a11y` tree on FB Watch) | Nostalgia EDM/vintage card talking points, post share count | Engagement text banner; high share velocity count. |

### 8.2 Garbage Collection & 14-Day Rolling Window
To prevent context rot, the agent executes the Mark-and-Sweep garbage collection protocol on `trends.db`:

```python
def execute_trends_garbage_collection(trends_db_path: str, output_md_path: str) -> int:
    """
    Purges trends older than 14 days and writes a consolidated current_trends.md artifact.
    """
    with sqlite3.connect(trends_db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        cursor = conn.cursor()
        
        # 1. Sweep: Hard delete records older than 14 days
        cursor.execute("DELETE FROM trends WHERE date_added < date('now', '-14 days')")
        deleted_count = cursor.rowcount
        conn.commit()

        # 2. Mark: Select active window
        cursor.execute(
            """
            SELECT platform, topic_category, hashtag_or_audio, velocity_score, date_added 
            FROM trends 
            ORDER BY velocity_score DESC, date_added DESC
            """
        )
        active_trends = cursor.fetchall()

    # 3. Export concise markdown view
    lines = [
        "# Active 14-Day Viral Trend Catalog",
        f"**Last Refreshed:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"**Active Trend Count:** {len(active_trends)}",
        "",
        "| Platform | Category | Trend / Audio / Hashtag | Velocity Score | Date Added |",
        "|---|---|---|---|---|",
    ]
    for row in active_trends:
        lines.append(f"| {row[0]} | {row[1]} | `{row[2]}` | {row[3]} | {row[4]} |")
    
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return deleted_count
```

---

## 9. ProTeGi Alignment Loop & Textual Gradient Integration

When persistent DOM shift or semantic divergence occurs (e.g. scraping selector returns empty results across 3 consecutive cycles despite network connectivity), the agent executes the **ProTeGi Leash Enforcer** protocol (`protegi-leash-enforcer/SKILL.md`):

1. **Beam Search Expansion:** Synthesizes 3 candidate selector/extraction strategies:
   - *Branch A:* DOM query selector revision.
   - *Branch B:* Accessibility Tree name/role extraction.
   - *Branch C:* Android UI Automator `resource-id` / `content-desc` hierarchy matching.
2. **Entropy Evaluation:** Calculates the divergence between candidate outputs. If divergence is high, the agent halts autonomous guessing.
3. **Backward Pass (Textual Gradient):** Generates a structured critique identifying why the original selector failed (e.g., dynamic obfuscated CSS class names like `.css-1vw8z9`) and constructs a gradient update.
4. **Runbook Modification:** Emits a patch to the subagent's `SKILL.md` runbook, persisting the updated accessibility role or Android layout xpath.
5. **Orthogonal Audit:** Dispatches the patch to an adversarial auditor subagent before executing production runs.

---

## 10. Deterministic Testing Strategy & Verification Harness

In strict compliance with **Rule R2 (The Zero-Discretion Mandate / Leash Protocol)** and **Rule R18**, the testing strategy enforces Test-Driven Agentic Development (TDAD) via Loud Assertions and zero shared state.

### 10.1 Loud Assertion Principles
- Tests must instantiate clean, isolated SQLite databases (`:memory:` or temporary directory paths via `tmp_path`).
- No global state or cross-test fixtures.
- Every assertion must include an explicit failure message documenting expected vs actual states.

### 10.2 PyTest Fixture Architecture & Test Specifications

```python
# tests/test_ml_agent.py
import pytest
import sqlite3
import numpy as np
import pandas as pd
from unified_ops_hub.ml_agent.telemetry import TelemetryStore
from unified_ops_hub.ml_agent.clustering import KMeansOptimizer
from unified_ops_hub.ml_agent.policy import PolicyEngine

@pytest.fixture
def isolated_telemetry_db(tmp_path):
    """Provides a pristine, isolated SQLite telemetry database."""
    db_file = tmp_path / "test_telemetry.db"
    store = TelemetryStore(str(db_file))
    return store

def test_telemetry_insertion_and_wal_mode(isolated_telemetry_db):
    """Loud Assertion: TelemetryStore correctly persists spans and enforces WAL mode."""
    store = isolated_telemetry_db
    
    # Verify WAL mode
    with store._get_connection() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert journal_mode.lower() == "wal", f"LOUD ASSERTION FAILURE: Expected WAL mode, got {journal_mode}"

    # Insert Span
    span_id = store.record_span(
        platform="tiktok",
        lens_type="web_a11y_tree",
        duration_ms=1250,
        yield_count=15,
        error_count=0,
        status_code="SUCCESS",
        input_tokens=450,
        output_tokens=120,
    )
    assert span_id is not None, "LOUD ASSERTION FAILURE: Span ID must not be None"

    # Query Span
    df = store.get_recent_spans(platform="tiktok", limit=1)
    assert len(df) == 1, f"LOUD ASSERTION FAILURE: Expected 1 span, found {len(df)}"
    assert df.iloc[0]["duration_ms"] == 1250, f"LOUD ASSERTION FAILURE: Duration mismatch"
    assert df.iloc[0]["yield_count"] == 15, f"LOUD ASSERTION FAILURE: Yield mismatch"
    assert df.iloc[0]["status_code"] == "SUCCESS", f"LOUD ASSERTION FAILURE: Status mismatch"

def test_kmeans_clustering_segments_three_profiles(isolated_telemetry_db):
    """Loud Assertion: K-Means correctly partitions healthy, degraded, and failing spans."""
    store = isolated_telemetry_db
    
    # Seed 10 Healthy Spans (Cluster 0)
    for _ in range(10):
        store.record_span("tiktok", "web_a11y_tree", duration_ms=800, yield_count=20, error_count=0, status_code="SUCCESS")
    
    # Seed 10 Degraded Spans (Cluster 1: slow, low yield, some errors)
    for _ in range(10):
        store.record_span("tiktok", "web_a11y_tree", duration_ms=18000, yield_count=3, error_count=2, status_code="RATE_LIMITED")
        
    # Seed 10 Failing Spans (Cluster 2: zero yield, high error count)
    for _ in range(10):
        store.record_span("tiktok", "web_a11y_tree", duration_ms=2000, yield_count=0, error_count=5, status_code="DOM_DRIFT")

    df = store.get_recent_spans(platform="tiktok", limit=30)
    assert len(df) == 30, f"LOUD ASSERTION FAILURE: Expected 30 spans, got {len(df)}"

    optimizer = KMeansOptimizer(k=3, random_state=42)
    labels, centroids, counts = optimizer.fit_predict(df)

    assert len(labels) == 30, f"LOUD ASSERTION FAILURE: Expected 30 labels, got {len(labels)}"
    assert len(counts) == 3, f"LOUD ASSERTION FAILURE: Expected 3 unique clusters, got {len(counts)}"
    
    # Cluster 0 must have lowest error rate and highest yield rate
    assert counts[0] == 10, f"LOUD ASSERTION FAILURE: Expected 10 Cluster 0 items, got {counts.get(0)}"
    assert counts[1] == 10, f"LOUD ASSERTION FAILURE: Expected 10 Cluster 1 items, got {counts.get(1)}"
    assert counts[2] == 10, f"LOUD ASSERTION FAILURE: Expected 10 Cluster 2 items, got {counts.get(2)}"

def test_policy_engine_triggers_lens_failover_on_dom_drift(isolated_telemetry_db):
    """Loud Assertion: PolicyEngine swaps lens to android_ui_dump when Cluster 2 dominates."""
    store = isolated_telemetry_db
    optimizer = KMeansOptimizer(k=3, random_state=42)
    policy_engine = PolicyEngine(store, optimizer)

    # Inject DOM drift failures (Cluster 2)
    for _ in range(10):
        store.record_span("tiktok", "web_a11y_tree", duration_ms=1500, yield_count=0, error_count=4, status_code="DOM_DRIFT")

    result = policy_engine.evaluate_and_adjust("tiktok")
    assert result["action"] == "LENS_SWAP", f"LOUD ASSERTION FAILURE: Expected LENS_SWAP, got {result['action']}"
    assert result["new_lens"] == "android_ui_dump", f"LOUD ASSERTION FAILURE: Expected android_ui_dump lens"

    updated_policy = store.get_policy("tiktok")
    assert updated_policy["active_lens"] == "android_ui_dump", "LOUD ASSERTION FAILURE: Policy DB not updated with new lens"
```

---

## 11. Security, Data Loss Prevention & Safety Verification

1. **Rule R3 & Accidental Data Loss Prevention:**
   - The ML agent executes strictly in an analytical and read-only supervisory capacity.
   - Destructive operations (`os.remove`, `shutil.rmtree`, `taskkill`) are strictly forbidden in the agent's autonomous path.
   - Deletions are strictly limited to domain-specific rolling data garbage collection (`DELETE FROM trends WHERE date_added < date('now', '-14 days')`).
2. **Static AST Guardrail Checks:**
   - A CI/CD static AST analyzer checks `ml_agent.py` to confirm that forbidden process killing functions (`os.kill`, `subprocess.call("taskkill")`) are absent.
3. **Session Token Safety:**
   - Hard budget ceilings in `BudgetConfig` guarantee that recursive prompt loops terminate predictably with `types.StopReason.MAX_MODEL_CALLS_EXCEEDED` before budget exhaustion.

---

## 12. Implementation Blueprint & File Layout

For the downstream Implementer agent, the codebase must be organized as follows within `g:/My Drive/GOOGLE ANTIGRAVITY/unified_ops_hub`:

```
unified_ops_hub/
├── ml_agent/
│   ├── __init__.py              # Package init
│   ├── ml_agent.py              # Root Antigravity SDK autonomous agent & entrypoint
│   ├── telemetry.py             # SQLite TelemetryStore (WAL, span ingestion, queries)
│   ├── clustering.py            # Localized sub-5ms KMeansOptimizer & feature scaler
│   ├── policy.py                # Closed-loop PolicyEngine & self-adjusting state machine
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── web_lens.py          # Chrome DevTools MCP Accessibility tree extractor
│   │   └── android_lens.py      # Headless Android CLI layout hierarchy extractor
│   └── protegi.py               # ProTeGi textual gradient loop & critique generator
├── tests/
│   ├── __init__.py
│   ├── test_telemetry.py        # TelemetryStore CRUD, constraints, and WAL tests
│   ├── test_clustering.py       # K-Means mathematical convergence & scaling tests
│   ├── test_policy.py           # PolicyEngine state transitions & failover tests
│   └── test_ml_agent_e2e.py     # End-to-end autonomous cycle mock test
└── requirements.txt             # google-antigravity, pandas, numpy, scikit-learn, pytest
```

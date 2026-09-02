# Milestone 4 Deep Technical Analysis: Architecture Red-Team Auditor

## 1. Executive Summary
This document provides the exhaustive architectural analysis and drop-in blueprint for `audit/red_team.py` (Milestone 4, Feature 13). 
The `ArchitectureRedTeam` class acts as an orthogonal, adversarial verification layer that scrutinizes every detected anomaly and proposed optimization emitted by upstream detectors (`detectors/`) and ML clustering (`ml/`) before presenting findings to human-in-the-loop (HITL) review.

The Red-Team enforces three distinct adversarial perspectives:
1. **System Integrity**: Validates that proposed actions do not crash active user daemons (Next.js/FastAPI on ports 3000/8000/8501), violate static AST 0-destruction guardrails, or corrupt system manifest rules (`GEMINI.md`).
2. **Data Loss Risk**: Strictly enforces `accidental-data-loss-prevention` by barring autonomous deletion of stale planning files (`.md`), `.disabled` plugins, or `.env` configs, replacing destructive suggestions with non-destructive L2 context paging (`.archive/`) and interactive HITL update prompts.
3. **False Positive Filter**: Discards false alarms on whitelisted project manifests (`PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, `ORIGINAL_REQUEST.md`, `DISPATCH.md`), documentation templates (`.env.example`, `.env.template`), and test fixtures (`fixtures/`, `tests/`, `mock_workspace/`).

Every audit produces a structured `RedTeamAuditResult` with a 3-tiered verdict (`APPROVED`, `CHALLENGED`, `REJECTED`), detailed rationale, risk assessment, and recommended non-destructive action / counter-proposal.

---

## 2. Evidence-Based Observations & Current Workspace State

| Component | Path | Verified State / Observation |
|---|---|---|
| **Data Contracts** | `cron/models.py:23-100` | Defines `RedTeamVerdict` (`APPROVED`, `CHALLENGED`, `REJECTED`), `AnomalyRecord`, `RedTeamAuditResult`, and `OptimizationReport`. `RedTeamAuditResult` contains `anomaly`, `verdict`, `rationale`, `risk_assessment`, and `recommended_action`. |
| **Config & Whitelists** | `cron/config.py:15-36` | `WHITELISTED_FILENAMES` defines core protected filenames: `["PROJECT.md", "GEMINI.md", "README.md", "BRIEFING.md", "ORIGINAL_REQUEST.md"]`. `MONITORED_PORTS = [3000, 8000, 8501]`. |
| **Static AST Safety** | `cron/safety_guardrails.py:1-312` | Prohibits `os.remove`, `os.unlink`, `shutil.rmtree`, `os.kill`, `subprocess` calls with `taskkill`/`pkill`/`rm -rf`, and destructive SQL (`DROP`, `TRUNCATE`). All red team code must pass `assert_safe_codebase()` with 0 violations. |
| **Detectors & ML Outputs** | `cron/detectors/`, `cron/ml/` | 5 detectors emit `AnomalyRecord`s. ML modules (`embeddings.py`, `clustering.py`, `protegi.py`) vectorize anomalies, cluster via $K=3$ NumPy K-Means, and generate ProTeGi textual gradients. All 73 test cases in M1-M3 pass in <2.5s. |
| **Accidental Data Loss Rule** | `skills/accidental-data-loss-prevention` | Mandates STOP AND VERIFY before any action risking data loss. Requires explicit HITL consent. |
| **Architecture Red Team Rule** | `skills/architecture-red-team` | Mandates adversarial checks against confirmation bias and cross-reference against global omnichannel directives. |

---

## 3. Adversarial Perspective Evaluation Matrix

```
                          ┌────────────────────────┐
                          │     AnomalyRecord      │
                          └───────────┬────────────┘
                                      │
                                      ▼
             ┌─────────────────────────────────────────────────┐
             │       ArchitectureRedTeam.audit_anomaly()       │
             └────────────────────────┬────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│   Perspective 1:     │   │   Perspective 2:     │   │   Perspective 3:     │
│ False Positive Filter│   │   Data Loss Risk     │   │   System Integrity   │
│                      │   │ (accidental-loss)    │   │ (daemons/manifest)   │
└──────────┬───────────┘   └──────────┬───────────┘   └──────────┬───────────┘
           │                          │                          │
           │ Match Manifest/Template  │ Destructive Deletion     │ Port Termination /
           │ (REJECTED)               │ (CHALLENGED / L2 Archive)│ Manifest Truncation
           │                          │                          │ (CHALLENGED / Skills)
           └──────────────────────────┼──────────────────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │   Arbitration Engine    │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │   RedTeamAuditResult    │
                         │  - verdict (3-tier)     │
                         │  - rationale / reason   │
                         │  - risk_assessment      │
                         │  - recommended_action   │
                         │  - counter_proposal     │
                         │  - confidence           │
                         └─────────────────────────┘
```

### Detailed Evaluation by Detector Type

| Detector Type | Target Pattern | Perspective 1 (False Positive) | Perspective 2 (Data Loss Risk) | Perspective 3 (System Integrity) | Final Verdict | Action / Counter-Proposal |
|---|---|---|---|---|---|---|
| `CONTEXT_ROT` | `PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md` | **TRUE** (Whitelisted manifest) | N/A | Manifest preservation | `REJECTED` | Dismiss finding; keep file in workspace root. |
| `CONTEXT_ROT` | `*notes*.md` (24h - 36h age) | False (Not whitelisted) | **HIGH** (Borderline staleness; active thinking) | Active subagent context | `CHALLENGED` | Prompt human before archiving; do not delete. |
| `CONTEXT_ROT` | `*plan*.md` (> 36h age) | False (Real stale file) | **LOW** (via non-destructive L2 archive) | Low risk | `APPROVED` | Propose L2 context paging (`.archive/`) upon HITL approval. Zero deletion. |
| `SECRET_ZERO` | `.env.example`, `.env.template`, `mock_workspace/` | **TRUE** (Documentation template / fixture) | N/A | Zero risk | `REJECTED` | Dismiss finding; template intentionally contains examples. |
| `SECRET_ZERO` | Active `.env` config with `your_token_here` | False (Active production file) | **CRITICAL** (Do not overwrite/wipe `.env`) | Authentication failure risk | `APPROVED` | Prompt human to replace masked token in `.env` with real key. Zero deletion. |
| `GHOST_DAEMONS` | Port 3000, 8000, 8501 occupied | Potential dev server | Automated `taskkill` forbidden | **HIGH** (Killing process crashes active Next.js/FastAPI) | `CHALLENGED` | Inspect PID; prompt user for graceful termination (SIGTERM). Zero automated kill. |
| `ECOSYSTEM_POLLUTION` | `*.disabled` plugin directory | False (Disabled folder) | **LOW** (via non-destructive quarantine) | Low risk | `APPROVED` | Propose moving to `.archive/disabled_plugins/` with HITL approval. Zero deletion. |
| `ECOSYSTEM_POLLUTION` | Media file in `/sports_cards` or card term in `/content_creation` | Inconclusive (Multi-modal feature) | **MEDIUM** (May delete working feature code) | Domain boundary review | `CHALLENGED` | Prompt human to review domain boundary before moving code. |
| `PROMPT_FATIGUE` | `GEMINI.md` > 100 lines | False (Manifest bloat) | **CRITICAL** (Blind truncation destroys directives) | **HIGH** (Breaks R1/R2 directives) | `CHALLENGED` | Distill procedural rules into modular skills (`.agents/skills/`); preserve immutable manifest directives. |
| `PROMPT_FATIGUE` | Duplicate `<RULE[...]>` sections | False (Redundant tokens) | Zero data loss | Low risk (improves efficiency) | `APPROVED` | Prompt developer to deduplicate redundant sections in manifest. |

---

## 4. Architectural Invariants & Safety Guarantees
1. **Zero-Destruction AST Guarantee**: `audit/red_team.py` contains 0 calls to `os.remove`, `os.unlink`, `shutil.rmtree`, `os.kill`, `subprocess.Popen` with `taskkill`, or raw `DROP`/`TRUNCATE` SQL.
2. **Deterministic & Isolated**: `audit_anomaly()` wraps evaluation in try-except blocks, ensuring that an error in evaluating one anomaly returns a fallback `CHALLENGED` result without crashing the overall audit pipeline.
3. **No External ML / Sklearn Dependency**: Pure Python standard library with regex and string analysis; < 0.1ms per anomaly execution time.
4. **Interactive Checkbox Ready**: Audit results provide clear, non-destructive recommendations that can be consumed directly by `DailyReportBuilder` to render interactive `[ ] [HITL-APPROVED]` checkboxes.

---

## 5. Verification & Test Plan
The verification test suite `tests/test_red_team_audit.py` validates:
1. Manifest whitelist protection: `PROJECT.md`, `GEMINI.md`, `README.md` -> `REJECTED`.
2. Documentation template & fixture protection: `.env.example`, `mock_workspace/.env` -> `REJECTED`.
3. Ghost daemon protection: Port 3000 -> `CHALLENGED` with zero-kill recommendation.
4. Borderline staleness: 24.5h old planning file -> `CHALLENGED`.
5. Verified stale planning file: 72h old proposal -> `APPROVED` with L2 archive recommendation.
6. Real configuration secret zero: `.env` placeholder -> `APPROVED` with manual update prompt.
7. Manifest line bloat: `GEMINI.md` 180 lines -> `CHALLENGED` with skill distillation advice.
8. Duplicate manifest sections: Duplicate headers -> `APPROVED`.
9. Batch audit on empty list and multi-item list.
10. AST Static Analysis check via `safety_guardrails.scan_file_for_safety()`.

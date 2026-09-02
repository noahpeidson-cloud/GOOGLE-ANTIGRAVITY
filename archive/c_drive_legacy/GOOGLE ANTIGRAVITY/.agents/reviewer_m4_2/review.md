# Quality & Adversarial Review Report: Milestone 4 (BigQuery ML Optimization Loop)

## Review Summary

**Verdict**: REQUEST_CHANGES  
**Reviewer**: teamwork_preview_reviewer  
**Target Code**: `media_pipeline/bqml/` (`feedback_loop.py`, `schema.sql`, `models.sql`, `test_bqml_loop.py`)  
**Date**: 2026-08-25  

---

## 1. Findings

### [Critical] Finding 1: Simplex Invariant Violation & Negative Weight Generation in `extract_normalized_weights`

- **What**: When normalizing extreme, highly skewed, or negative feature weight vectors, `extract_normalized_weights()` produces negative weights (e.g. `weight_hrv = -0.0001`), violating the probability simplex constraint ($w_i \ge 0.0, \forall i$) and causing downstream `ModelParameterWeights` instantiation to crash with a Pydantic `ValidationError`.
- **Where**: `media_pipeline/bqml/feedback_loop.py`, lines 201–204:
  ```python
  # Ensure exact sum == 1.0000 by adjusting residual on weight_hrv
  current_sum = round(sum(normalized.values()), 4)
  residual = round(1.0000 - current_sum, 4)
  if residual != 0.0:
      normalized["weight_hrv"] = round(normalized["weight_hrv"] + residual, 4)
  ```
- **Why**: 
  When features with high variance are normalized and rounded to 4 decimal places, the sum of rounded values can equal $1.0001$ or $1.0002$, producing a negative residual (e.g. $\text{residual} = -0.0001$ or $-0.0002$). If `normalized["weight_hrv"]` is small (e.g. $0.0000$ or $0.0001$), adding the negative residual forces `normalized["weight_hrv"]` into negative territory (e.g. $-0.0001$).
- **Deterministic Reproduction**:
  ```python
  from media_pipeline.bqml.feedback_loop import extract_normalized_weights, ModelParameterWeights

  raw = {
      'weight_hrv': -318.7351,
      'weight_dpaw': 161.4305,
      'weight_adr_sfd': -165.4402,
      'weight_cke_mve': -302.0603,
      'weight_ltss': -10.4846
  }
  norm = extract_normalized_weights(raw, min_weight_floor=0.01)
  print(norm)
  # Output: {'weight_hrv': -0.0001, 'weight_dpaw': 0.9998, 'weight_adr_sfd': 0.0001, 'weight_cke_mve': 0.0001, 'weight_ltss': 0.0001}

  # Fails Pydantic validation:
  ModelParameterWeights(version_id="v_fail", **norm)
  # ValidationError: Input should be greater than or equal to 0 [weight_hrv=-0.0001]
  ```
- **Suggestion**: 
  Instead of hardcoding residual adjustments onto `weight_hrv`, apply the residual to the feature with the **largest normalized weight** (`max(normalized, key=normalized.get)`). Because $\max(w_i) \ge 0.20 \gg 0.0003$, adjusting the maximum weight by `residual` ($\in [-0.0003, +0.0003]$) is mathematically guaranteed to keep all weights non-negative ($w_i \ge 0.0$) while ensuring $\sum_{i=1}^5 w_i = 1.0000$ exactly.
  ```python
  current_sum = round(sum(normalized.values()), 4)
  residual = round(1.0000 - current_sum, 4)
  if residual != 0.0:
      # Apply residual to the feature with the highest weight to prevent negative clamping
      max_feat = max(normalized, key=normalized.get)
      normalized[max_feat] = round(normalized[max_feat] + residual, 4)
  ```

---

### [Minor] Finding 2: BQML `CREATE MODEL` Option Naming Consistency

- **What**: In `models.sql`, `viral_weight_regressor` (line 19) and `video_archetype_clusters` (line 83) use `max_iteration`, whereas `viral_retention_tree_regressor` (line 45) uses `max_iterations`.
- **Where**: `media_pipeline/bqml/models.sql`, lines 19, 45, 83.
- **Why**: BigQuery ML documentation specifies `MAX_ITERATIONS` as the standard syntax option for linear regression and clustering models. Using mixed singular/plural options may cause syntax errors on strict SQL parsers.
- **Suggestion**: Standardize on `max_iterations` across all model definitions in `models.sql`.

---

## 2. Verified Claims & Positive Findings

- [x] **Schema DDL & Partitioning/Clustering**: `schema.sql` successfully defines `media_pipeline.video_grades`, `media_pipeline.video_grading_records`, `media_pipeline.post_performance_metrics`, and `media_pipeline.model_parameter_weights` with timestamp partitioning (`PARTITION BY DATE(...)`) and valid clustering keys (`CLUSTER BY ...`).
- [x] **BQML Model Architectures**: `models.sql` defines complete, valid SQL for `LINEAR_REG`, `BOOSTED_TREE_REGRESSOR`, `KMEANS`, `ML.EVALUATE`, `ML.WEIGHTS`, `ML.FEATURE_IMPORTANCE`, and `ML.PREDICT`.
- [x] **State Machine & Model Versioning**: `recalibrate_model_weights` accurately deactivates previous active versions (`is_active = FALSE`) and registers newly trained weights as `is_active = TRUE`.
- [x] **BigQuery Sink & Telemetry Ingestion**: `sink_video_grades_to_bq` and `update_post_performance_telemetry` correctly handle structured Pydantic metrics, dictionary records, and telemetry updates.
- [x] **Test Harness Quality**: `test_bqml_loop.py` contains 15 well-structured deterministic tests, passing with 0 failures under normal inputs.

---

## 3. Adversarial Stress-Test Results

| Stress Test Scenario | Test Input / Vector | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|---|
| Random Vector Simplex Test | 10,000 random vectors $\in [-500, 500]$ | $\sum w_i = 1.0000 \land w_i \ge 0.0$ | $\sum w_i = 1.0000$, but $w_{\text{hrv}} = -0.0001$ on seed 18 | **FAIL** (Finding 1) |
| Extreme Disparity Ratio | 1 dominant feature ($10^8$) vs 4 minor ($10^{-6}$) | Dominant feature $\ge 0.95$, sum = 1.0000 | Handled properly, dominant $> 0.95$, sum = 1.0000 | PASS |
| All Negative Coefficients | All 5 features $< 0$ (e.g. $-50.0$) | Clamped to positive floor, equal split ($0.20$ each) | Clamped to $0.20$ each, sum = 1.0000 | PASS |
| Missing / Partial Features | Only 1 or 2 features provided in dict | Defaults populated, sum = 1.0000 | Defaults populated, sum = 1.0000 | PASS |
| Empty Input Payload | `{}` or `[]` | Default weights returned ($0.25, 0.25, 0.20, 0.15, 0.15$) | Default weights returned, sum = 1.0000 | PASS |
| Deactivation State Machine | 10 consecutive recalibrations | Exactly 1 active row at all times | Exactly 1 active row maintained | PASS |

---

## 4. Integrity & Quality Audit

- **Integrity Violation Check**: None detected. No hardcoded results, facades, or fake test verifications. Real BigQuery SQL DDLs and real mathematical normalization logic are implemented.
- **Coverage Gaps**: Unhandled boundary case when residual subtraction on `weight_hrv` causes negative weight under skewed distributions.
- **Unverified Items**: None.

---

## 5. Required Actions for Approval

1. Update `media_pipeline/bqml/feedback_loop.py` to assign the rounding residual to `max(normalized, key=normalized.get)` instead of unconditionally modifying `weight_hrv`.
2. Add a deterministic test case in `test_bqml_loop.py` reproducing the seed 18 skew condition and asserting all weights satisfy $w_i \ge 0.0$.
3. (Optional) Standardize `max_iterations` in `media_pipeline/bqml/models.sql`.

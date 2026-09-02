# Root Cause Analysis & Remediation Strategy: PySpark Video Grading Partition Exceptions

**Module**: `media_pipeline/grading/spark_grading_job.py`  
**Target Milestone**: Milestone 3 Remediation (Iteration 2)  
**Author**: `teamwork_preview_explorer`  
**Date**: 2026-08-25T04:16:05Z  

---

## 1. Executive Summary

During adversarial verification by Challenger 2 (`test_adversarial_grading.py`), 4 critical unhandled exception bugs were discovered in `media_pipeline/grading/spark_grading_job.py::grade_partition`. Specifically, type casting and record unwrapping logic were executed *outside* the partition worker's `try...except` block, and relied on `dict.get(key, default)` which returns `None` when a key exists with value `None`.

When unhandled exceptions occur within PySpark's `mapPartitions` worker, the executor task fails. After reaching Spark's `spark.task.maxFailures` limit (typically 4 attempts), the entire Spark stage and batch grading job crash, violating the Dead Letter Queue (DLQ) fault isolation requirement defined in `PROJECT.md` Feature #10.

This document details the root causes of each failure mode, establishes safe coercion helpers, and provides an exact unified diff to remediate `spark_grading_job.py`.

---

## 2. Root Cause Analysis (4 Failure Modes)

### 2.1 Failure Mode 1: `TypeError` on `duration_seconds: None`
- **Location**: `media_pipeline/grading/spark_grading_job.py:162`
- **Existing Code**:
  ```python
  duration_seconds = float(record.get("duration_seconds", 30.0))
  ```
- **Root Cause**: In Python, `dict.get(key, default)` only substitutes `default` if `key` is absent from the dictionary. When upstream manifests produce `{"duration_seconds": None}` (or JSON `null`), `record.get("duration_seconds", 30.0)` returns `None`. Executing `float(None)` raises `TypeError: float() argument must be a string or a real number, not 'NoneType'`. Because this occurs on line 162 prior to the `try:` block on line 195, the exception is unhandled and crashes the partition worker.

### 2.2 Failure Mode 2: `TypeError` on `file_size_bytes: None`
- **Location**: `media_pipeline/grading/spark_grading_job.py:161`
- **Existing Code**:
  ```python
  file_size_bytes = int(record.get("file_size_bytes", 0))
  ```
- **Root Cause**: Identical to Failure Mode 1. When `{"file_size_bytes": None}` is encountered, `record.get("file_size_bytes", 0)` returns `None`. Executing `int(None)` raises `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`.

### 2.3 Failure Mode 3: `ValueError` on Corrupt Numerical String
- **Location**: `media_pipeline/grading/spark_grading_job.py:161-162`
- **Existing Code**:
  ```python
  file_size_bytes = int(record.get("file_size_bytes", 0))
  duration_seconds = float(record.get("duration_seconds", 30.0))
  ```
- **Root Cause**: If the input record contains an invalid non-numerical string (e.g. `{"duration_seconds": "invalid_number"}` or `{"file_size_bytes": "corrupted_size"}`), direct calls to `float()` or `int()` raise `ValueError: could not convert string to float: 'invalid_number'`. Because these calls are outside the `try:` block, the worker process terminates abnormally.

### 2.4 Failure Mode 4: `TypeError` / `ValueError` on Non-Dictionary / None RDD Elements
- **Location**: `media_pipeline/grading/spark_grading_job.py:156`
- **Existing Code**:
  ```python
  record: Dict[str, Any] = item.asDict() if hasattr(item, "asDict") else dict(item)
  ```
- **Root Cause**: 
  - If an RDD partition receives a `None` element, `hasattr(None, "asDict")` evaluates to `False`. The fallback `dict(None)` executes, raising `TypeError: 'NoneType' object is not iterable`.
  - If an integer or primitive scalar is passed (e.g. `item = 42`), `dict(42)` raises `TypeError: 'int' object is not iterable`.
  - If a plain string is passed (e.g. `item = "corrupt"`), `dict("corrupt")` raises `ValueError: dictionary update sequence element #0 has length 1; 2 is required`.
  - Because this conversion is the very first line inside `for item in iterator:` outside any `try:` block, any malformed RDD partition item immediately crashes the Spark task.

---

## 3. Remediation Strategy & Defensive Architecture

To achieve 100% resilience across all PySpark executor partitions and satisfy the DLQ fault isolation mandate, the following architectural fixes are specified:

### 3.1 Defensive Type Coercion Helpers
Implement standalone, robust parsing helpers at the module level:
- `_safe_float(val: Any, default: float = 30.0) -> float`: Returns `default` if `val is None`, if `float(val)` raises `(ValueError, TypeError)`, or if `math.isnan(val)` / `math.isinf(val)` is True.
- `_safe_int(val: Any, default: int = 0) -> int`: Returns `default` if `val is None`, or if `int(float(val))` raises `(ValueError, TypeError, OverflowError)`.
- `_safe_str(val: Any, default: str = "") -> str`: Returns `default` if `val is None` or if stripped string is empty.

### 3.2 Total Partition Worker Encapsulation (`try...except`)
The entire loop body of `grade_partition` must be wrapped inside a `try...except Exception as err:` block:
1. **Record Extraction**:
   - Explicitly verify `item is not None`.
   - Safely convert PySpark `Row` (via `asDict()`), dictionaries, or object dictionaries (`__dict__`).
   - If conversion fails, raise a descriptive `TypeError` that is caught within the item's `try...except` block.
2. **Safe Attribute Extraction**:
   - Extract all fields (`video_id`, `gcs_uri`, `raw_file_name`, `file_size_bytes`, `duration_seconds`, `aspect_ratio`) using the safe coercion helpers with fallback defaults initialized before the conversion.
3. **Invalid GCS URI Routing**:
   - Check `gcs_uri.startswith("gs://")`. If False, log error, record to `client.dlq.record_failure()`, and `yield` a `status: "FAILED_DLQ"` dictionary.
4. **Gemini Grading Execution**:
   - Invoke `client.grade_video_report()`. On success, `yield` the `status: "GRADED"` payload with all 5 scores, EVPI, and verdicts.
5. **Universal DLQ Catch & Yield**:
   - If any exception occurs anywhere in steps 1–4, the `except Exception as err:` block logs the error, invokes `client.dlq.record_failure(...)` with error context, and `yields` a valid 23-column `status: "FAILED_DLQ"` dictionary.
   - The worker moves cleanly to the next item in the iterator without aborting the partition.

---

## 4. Proposed Code Diff for `media_pipeline/grading/spark_grading_job.py`

```diff
--- a/media_pipeline/grading/spark_grading_job.py
+++ b/media_pipeline/grading/spark_grading_job.py
@@ -19,6 +19,7 @@
 import json
 import logging
+import math
 import os
 import sys
 from datetime import datetime, timezone
@@ -134,6 +135,39 @@
     return dict(DEFAULT_WEIGHTS)
 
 
+# ============================================================================
+# 2.5 DEFENSIVE DATA COERCION HELPERS
+# ============================================================================
+
+def _safe_float(val: Any, default: float = 30.0) -> float:
+    """Safely coerces val to float; returns default on None, TypeError, ValueError, NaN, or Inf."""
+    if val is None:
+        return default
+    try:
+        f = float(val)
+        return default if (math.isnan(f) or math.isinf(f)) else f
+    except (ValueError, TypeError):
+        return default
+
+
+def _safe_int(val: Any, default: int = 0) -> int:
+    """Safely coerces val to int; returns default on None, TypeError, ValueError, or Overflow."""
+    if val is None:
+        return default
+    try:
+        return int(float(val))
+    except (ValueError, TypeError, OverflowError):
+        return default
+
+
+def _safe_str(val: Any, default: str = "") -> str:
+    """Safely coerces val to string; returns default if val is None or empty."""
+    if val is None:
+        return default
+    s = str(val).strip()
+    return s if s else default
+
+
 # ============================================================================
 # 3. DISTRIBUTED PARTITION PROCESSING
 # ============================================================================
@@ -153,46 +187,70 @@
     )
 
     for item in iterator:
-        # Convert PySpark Row to dict if needed
-        record: Dict[str, Any] = item.asDict() if hasattr(item, "asDict") else dict(item)
-        
-        video_id = str(record.get("video_id", f"vid_{int(datetime.now().timestamp())}"))
-        gcs_uri = str(record.get("gcs_uri", ""))
-        raw_file_name = str(record.get("raw_file_name") or os.path.basename(gcs_uri))
-        file_size_bytes = int(record.get("file_size_bytes", 0))
-        duration_seconds = float(record.get("duration_seconds", 30.0))
-        aspect_ratio = str(record.get("aspect_ratio", "9:16"))
         now_iso = datetime.now(timezone.utc).isoformat()
-
-        # Validate URI format
-        if not gcs_uri.startswith("gs://"):
-            yield {
-                "video_id": video_id,
-                "gcs_uri": gcs_uri,
-                "raw_file_name": raw_file_name,
-                "file_size_bytes": file_size_bytes,
-                "duration_seconds": duration_seconds,
-                "aspect_ratio": aspect_ratio,
-                "status": "FAILED_DLQ",
-                "error_message": f"Invalid GCS URI format: '{gcs_uri}'. Must start with 'gs://'",
-                "hrv_score": 0.0,
-                "dpaw_score": 0.0,
-                "adr_sfd_score": 0.0,
-                "cke_mve_score": 0.0,
-                "ltss_score": 0.0,
-                "evpi_composite": 0.0,
-                "trending_verdict": TrendingVerdict.LOW_REACH.value,
-                "recommended_trim_start_sec": 0.0,
-                "recommended_trim_end_sec": 0.0,
-                "peak_drop_timestamp_sec": 0.0,
-                "subgenre": "UNKNOWN",
-                "suggested_hashtags": [],
-                "grading_rationale": "Invalid URI format; rejected before API call.",
-                "graded_at": now_iso,
-                "model_version": client.model_name,
-            }
-            continue
+        video_id = f"vid_{int(datetime.now().timestamp())}"
+        gcs_uri = ""
+        raw_file_name = ""
+        file_size_bytes = 0
+        duration_seconds = 30.0
+        aspect_ratio = "9:16"
 
         try:
+            # 1. Validate and convert RDD partition item to dictionary
+            if item is None:
+                raise TypeError("RDD partition item is None")
+
+            if hasattr(item, "asDict") and callable(getattr(item, "asDict")):
+                record = item.asDict()
+            elif isinstance(item, dict):
+                record = dict(item)
+            elif hasattr(item, "__dict__"):
+                record = dict(item.__dict__)
+            else:
+                try:
+                    record = dict(item)
+                except Exception as parse_err:
+                    raise TypeError(
+                        f"Cannot convert partition item of type '{type(item).__name__}' to dict: {parse_err}"
+                    )
+
+            if not isinstance(record, dict):
+                raise TypeError(f"Partition item resolved to non-dict type '{type(record).__name__}'")
+
+            # 2. Extract and safely coerce fields with fallback defaults
+            raw_vid = record.get("video_id")
+            video_id = _safe_str(raw_vid, video_id)
+
+            raw_uri = record.get("gcs_uri")
+            gcs_uri = _safe_str(raw_uri, "")
+
+            raw_fn = record.get("raw_file_name")
+            if raw_fn:
+                raw_file_name = _safe_str(raw_fn)
+            else:
+                raw_file_name = os.path.basename(gcs_uri) if gcs_uri else f"{video_id}.mp4"
+
+            file_size_bytes = _safe_int(record.get("file_size_bytes"), 0)
+            duration_seconds = _safe_float(record.get("duration_seconds"), 30.0)
+            aspect_ratio = _safe_str(record.get("aspect_ratio"), "9:16")
+
+            # 3. Validate GCS URI format
+            if not gcs_uri.startswith("gs://"):
+                err_msg = f"Invalid GCS URI format: '{gcs_uri}'. Must start with 'gs://'"
+                client.dlq.record_failure(
+                    video_id=video_id,
+                    gcs_uri=gcs_uri,
+                    error=ValueError(err_msg),
+                    context={"reason": "invalid_gcs_uri"}
+                )
+                yield {
+                    "video_id": video_id,
+                    "gcs_uri": gcs_uri,
+                    "raw_file_name": raw_file_name,
+                    "file_size_bytes": file_size_bytes,
+                    "duration_seconds": duration_seconds,
+                    "aspect_ratio": aspect_ratio,
+                    "status": "FAILED_DLQ",
+                    "error_message": err_msg,
+                    "hrv_score": 0.0,
+                    "dpaw_score": 0.0,
+                    "adr_sfd_score": 0.0,
+                    "cke_mve_score": 0.0,
+                    "ltss_score": 0.0,
+                    "evpi_composite": 0.0,
+                    "trending_verdict": TrendingVerdict.LOW_REACH.value,
+                    "recommended_trim_start_sec": 0.0,
+                    "recommended_trim_end_sec": 0.0,
+                    "peak_drop_timestamp_sec": 0.0,
+                    "subgenre": "UNKNOWN",
+                    "suggested_hashtags": [],
+                    "grading_rationale": "Invalid URI format; rejected before API call.",
+                    "graded_at": now_iso,
+                    "model_version": client.model_name,
+                }
+                continue
+
+            # 4. Multimodal video grading via Gemini client
             report: EDMViralGradingReport = client.grade_video_report(
                 video_id=video_id,
                 gcs_uri=gcs_uri,
@@ -230,6 +288,12 @@
 
         except Exception as err:
             logger.error(f"Partition worker error grading item {item}: {err}")
+            client.dlq.record_failure(
+                video_id=video_id,
+                gcs_uri=gcs_uri,
+                error=err,
+                context={"raw_item_type": type(item).__name__, "raw_item": str(item)[:200]}
+            )
             yield {
                 "video_id": video_id,
                 "gcs_uri": gcs_uri,
```

---

## 5. Verification & Test Plan

1. **Deterministic Test Suite Execution**:
   ```powershell
   python "g:\My Drive\GOOGLE ANTIGRAVITY\media_pipeline\grading\test_spark_grading.py"
   ```
   *Expected*: All 13 test suites pass with exit code 0.

2. **Empirical Adversarial Stress Test Suite**:
   ```powershell
   python "g:\My Drive\GOOGLE ANTIGRAVITY\.agents\challenger_m3_2\test_adversarial_grading.py"
   ```
   *Expected*: 9/9 tests pass (including all 4 vulnerability reproduction tests and the 8-partition multi-threading stress harness), 0 failures, 0 vulnerabilities.

3. **Direct Repro Invalidation Verification**:
   ```powershell
   python -c "from media_pipeline.grading.spark_grading_job import grade_partition, DEFAULT_WEIGHTS; list(grade_partition(iter([{'video_id': 'v1', 'gcs_uri': 'gs://b/v.mp4', 'duration_seconds': None}]), DEFAULT_WEIGHTS, mock_mode=True))"
   python -c "from media_pipeline.grading.spark_grading_job import grade_partition, DEFAULT_WEIGHTS; list(grade_partition(iter([{'video_id': 'v1', 'gcs_uri': 'gs://b/v.mp4', 'file_size_bytes': None}]), DEFAULT_WEIGHTS, mock_mode=True))"
   python -c "from media_pipeline.grading.spark_grading_job import grade_partition, DEFAULT_WEIGHTS; list(grade_partition(iter([{'video_id': 'v1', 'gcs_uri': 'gs://b/v.mp4', 'duration_seconds': 'invalid_number'}]), DEFAULT_WEIGHTS, mock_mode=True))"
   python -c "from media_pipeline.grading.spark_grading_job import grade_partition, DEFAULT_WEIGHTS; list(grade_partition(iter([None]), DEFAULT_WEIGHTS, mock_mode=True))"
   ```
   *Expected*: All commands complete without unhandled exceptions and emit valid structured dictionaries (`status: GRADED` or `status: FAILED_DLQ`).

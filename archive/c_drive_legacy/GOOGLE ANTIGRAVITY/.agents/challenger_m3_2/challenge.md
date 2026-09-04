# Milestone 3 Adversarial Challenge Report

**Date**: 2026-08-25T04:15:30Z  
**Target Module**: `media_pipeline/grading/` (`spark_grading_job.py`, `viral_schema.py`, `gemini_multimodal_client.py`)  
**Evaluator**: `teamwork_preview_challenger` (Critic & Specialist)  
**Overall Risk Assessment**: **HIGH**  
**Verdict**: **REJECT** (4 Confirmed Uncaught Worker Exceptions Violating DLQ Isolation)

---

## 1. Challenge Summary

We subjected the Milestone 3 PySpark batch grading engine, Gemini Omni multimodal client, and EVPI mathematical formula to rigorous adversarial stress testing, boundary condition probing, multi-partition RDD simulation across 8 concurrent worker partitions with 40 records, and dirty record fuzzing.

While the mathematical formula, Pydantic V2 schema validations, rate limiting, and DLQ serialization operate cleanly under nominal and standard error conditions, we uncovered **4 critical/medium unhandled exception vulnerabilities** in `spark_grading_job.py::grade_partition`. Specifically, dirty input records containing `None` or corrupt string types for `duration_seconds` or `file_size_bytes`, as well as non-dictionary RDD items, throw unhandled exceptions *before* the `try...except` block, causing the PySpark partition worker to crash and aborting the entire Dataproc distributed batch job.

---

## 2. Confirmed Vulnerabilities

### [High] Vulnerability 1: Uncaught `TypeError` on `duration_seconds: None`
- **Location**: `media_pipeline/grading/spark_grading_job.py:162`
- **Root Cause**: `grade_partition` executes `duration_seconds = float(record.get("duration_seconds", 30.0))` outside the `try...except` block. In Python, `dict.get("duration_seconds", 30.0)` returns `None` if the key exists with value `None`. `float(None)` raises `TypeError: float() argument must be a string or a real number, not 'NoneType'`.
- **Blast Radius**: PySpark task failure. If any record in an upstream manifest has `duration_seconds: null` (e.g. unprobed media), the entire partition worker crashes, causing Spark task retries to exhaust and failing the entire Dataproc batch pipeline.
- **Empirical Reproduction**:
  ```python
  from media_pipeline.grading.spark_grading_job import grade_partition, DEFAULT_WEIGHTS
  records = [{"video_id": "v1", "gcs_uri": "gs://b/v.mp4", "duration_seconds": None}]
  list(grade_partition(iter(records), DEFAULT_WEIGHTS))  # Crashes with TypeError
  ```
- **Mitigation**: Move all record parsing and type conversions inside the `try...except` block or implement safe coercion:
  ```python
  raw_dur = record.get("duration_seconds")
  duration_seconds = float(raw_dur) if raw_dur is not None else 30.0
  ```

---

### [High] Vulnerability 2: Uncaught `TypeError` on `file_size_bytes: None`
- **Location**: `media_pipeline/grading/spark_grading_job.py:161`
- **Root Cause**: `grade_partition` executes `file_size_bytes = int(record.get("file_size_bytes", 0))` outside the `try...except` block. When `file_size_bytes` is `None`, `int(None)` raises `TypeError`.
- **Blast Radius**: Aborts the Spark partition worker and batch job on any upstream null size values.
- **Empirical Reproduction**:
  ```python
  from media_pipeline.grading.spark_grading_job import grade_partition, DEFAULT_WEIGHTS
  records = [{"video_id": "v1", "gcs_uri": "gs://b/v.mp4", "file_size_bytes": None}]
  list(grade_partition(iter(records), DEFAULT_WEIGHTS))  # Crashes with TypeError
  ```
- **Mitigation**: Implement safe integer extraction inside `try:`:
  ```python
  raw_size = record.get("file_size_bytes")
  file_size_bytes = int(raw_size) if raw_size is not None else 0
  ```

---

### [Medium] Vulnerability 3: Uncaught `ValueError` on Corrupted String Fields
- **Location**: `media_pipeline/grading/spark_grading_job.py:161-162`
- **Root Cause**: If an input record contains a string in a numerical field (e.g. `duration_seconds: "invalid"` or `file_size_bytes: "NaN"`), `float()` or `int()` raises `ValueError` outside the `try:` block.
- **Blast Radius**: Partition crash on dirty JSON inputs.
- **Empirical Reproduction**:
  ```python
  from media_pipeline.grading.spark_grading_job import grade_partition, DEFAULT_WEIGHTS
  records = [{"video_id": "v1", "gcs_uri": "gs://b/v.mp4", "duration_seconds": "invalid"}]
  list(grade_partition(iter(records), DEFAULT_WEIGHTS))  # Crashes with ValueError
  ```
- **Mitigation**: Wrap the entire loop iteration in `try...except Exception as err:` so that any parsing failure routes directly to `FAILED_DLQ` rather than terminating the worker.

---

### [Medium] Vulnerability 4: Uncaught `TypeError` on Non-Dict RDD Elements
- **Location**: `media_pipeline/grading/spark_grading_job.py:156`
- **Root Cause**: `record: Dict[str, Any] = item.asDict() if hasattr(item, "asDict") else dict(item)` raises `TypeError: 'NoneType' object is not iterable` if `item` in the RDD is `None` or an unhandled primitive.
- **Blast Radius**: Partition worker crash.
- **Empirical Reproduction**:
  ```python
  from media_pipeline.grading.spark_grading_job import grade_partition, DEFAULT_WEIGHTS
  list(grade_partition(iter([None]), DEFAULT_WEIGHTS))  # Crashes with TypeError
  ```
- **Mitigation**: Check `isinstance(item, dict)` and wrap record conversion inside `try:`.

---

## 3. Stress Test Results

| # | Scenario / Test Case | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|---|
| 1 | `test_killswitches_exhaustive_boundaries` | Continuous duration boundaries ([0,8), [8,12), [12,38], (38,60], (60,inf)) and aspect ratios evaluated cleanly | All 18 boundary conditions evaluated cleanly | **PASS** |
| 2 | `test_evpi_calculation_clamping_and_weights` | Clamps EVPI to [0, 100], scales with weights and killswitch multipliers | Correctly clamped, 2 decimal rounding preserved | **PASS** |
| 3 | `test_multi_partition_mixed_records_resilience` | 8 concurrent partition workers process 40 mixed records (valid, bad URIs, extreme durations, varied aspect ratios, simulated 429 errors) | 40 records processed (29 GRADED, 11 FAILED_DLQ) without worker starvation | **PASS** |
| 4 | `test_vulnerability_none_duration_crash` | `duration_seconds: None` handled gracefully into DLQ or default fallback | Throws unhandled `TypeError: float() argument must be a string or a real number, not 'NoneType'` | **FAIL (BUG)** |
| 5 | `test_vulnerability_none_file_size_crash` | `file_size_bytes: None` handled gracefully into DLQ or default fallback | Throws unhandled `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'` | **FAIL (BUG)** |
| 6 | `test_vulnerability_corrupt_duration_string_crash` | `duration_seconds: 'invalid'` routed to `FAILED_DLQ` without worker crash | Throws unhandled `ValueError: could not convert string to float: 'invalid_number'` | **FAIL (BUG)** |
| 7 | `test_vulnerability_non_dict_element_crash` | `item: None` in RDD handled gracefully into `FAILED_DLQ` | Throws unhandled `TypeError: 'NoneType' object is not iterable` | **FAIL (BUG)** |
| 8 | `test_rate_limiter_concurrency_and_dlq_thread_safety` | 40 concurrent success requests + 50 concurrent error requests across 20 threads | All 50 DLQ files serialized to disk; zero concurrency race conditions | **PASS** |
| 9 | `test_pydantic_schema_strictness_and_roundtrip` | Full JSON serialization/deserialization cycle and simplex weight constraints | All Pydantic V2 models roundtrip cleanly with strict validation | **PASS** |

---

## 4. Recommended Fix for Builder / SWE

In `media_pipeline/grading/spark_grading_job.py`, rewrite `grade_partition` to wrap record extraction within the `try...except` block:

```python
def grade_partition(
    iterator: Iterator[Union[Dict[str, Any], Any]],
    weights: Dict[str, float],
    mock_mode: bool = False,
    simulate_rate_limit: bool = False,
) -> Iterator[Dict[str, Any]]:
    client = GeminiMultimodalClient(
        mock_mode=mock_mode,
        simulate_rate_limit=simulate_rate_limit,
    )

    for item in iterator:
        now_iso = datetime.now(timezone.utc).isoformat()
        video_id = f"vid_{int(datetime.now().timestamp())}"
        gcs_uri = ""
        raw_file_name = ""
        file_size_bytes = 0
        duration_seconds = 30.0
        aspect_ratio = "9:16"

        try:
            if hasattr(item, "asDict"):
                record = item.asDict()
            elif isinstance(item, dict):
                record = item
            else:
                raise ValueError(f"Invalid record format: expected dict or Row, got {type(item).__name__}")

            video_id = str(record.get("video_id") or video_id)
            gcs_uri = str(record.get("gcs_uri") or "")
            raw_file_name = str(record.get("raw_file_name") or (os.path.basename(gcs_uri) if gcs_uri else ""))
            
            raw_size = record.get("file_size_bytes")
            file_size_bytes = int(raw_size) if raw_size is not None else 0

            raw_dur = record.get("duration_seconds")
            duration_seconds = float(raw_dur) if raw_dur is not None else 30.0

            aspect_ratio = str(record.get("aspect_ratio") or "9:16")

            # Validate URI format
            if not gcs_uri.startswith("gs://"):
                yield {
                    "video_id": video_id,
                    "gcs_uri": gcs_uri,
                    "raw_file_name": raw_file_name,
                    "file_size_bytes": file_size_bytes,
                    "duration_seconds": duration_seconds,
                    "aspect_ratio": aspect_ratio,
                    "status": "FAILED_DLQ",
                    "error_message": f"Invalid GCS URI format: '{gcs_uri}'. Must start with 'gs://'",
                    "hrv_score": 0.0,
                    "dpaw_score": 0.0,
                    "adr_sfd_score": 0.0,
                    "cke_mve_score": 0.0,
                    "ltss_score": 0.0,
                    "evpi_composite": 0.0,
                    "trending_verdict": TrendingVerdict.LOW_REACH.value,
                    "recommended_trim_start_sec": 0.0,
                    "recommended_trim_end_sec": 0.0,
                    "peak_drop_timestamp_sec": 0.0,
                    "subgenre": "UNKNOWN",
                    "suggested_hashtags": [],
                    "grading_rationale": "Invalid URI format; rejected before API call.",
                    "graded_at": now_iso,
                    "model_version": client.model_name,
                }
                continue

            report: EDMViralGradingReport = client.grade_video_report(
                video_id=video_id,
                gcs_uri=gcs_uri,
                duration_seconds=duration_seconds,
                aspect_ratio=aspect_ratio,
                weights=weights,
            )

            yield {
                "video_id": video_id,
                "gcs_uri": gcs_uri,
                "raw_file_name": raw_file_name,
                "file_size_bytes": file_size_bytes,
                "duration_seconds": duration_seconds,
                "aspect_ratio": aspect_ratio,
                "status": "GRADED",
                "error_message": None,
                "hrv_score": float(report.hook_analysis.hrv_score),
                "dpaw_score": float(report.drop_pacing_analysis.dpaw_score),
                "adr_sfd_score": float(report.audio_analysis.adr_sfd_score),
                "cke_mve_score": float(report.crowd_analysis.cke_mve_score),
                "ltss_score": float(report.lighting_analysis.ltss_score),
                "evpi_composite": float(report.evpi_composite_score),
                "trending_verdict": str(report.trending_verdict),
                "recommended_trim_start_sec": float(max(0.0, (report.drop_pacing_analysis.drop_timestamp_seconds or 15.0) - 5.0)),
                "recommended_trim_end_sec": float(min(duration_seconds, (report.drop_pacing_analysis.drop_timestamp_seconds or 15.0) + 15.0)),
                "peak_drop_timestamp_sec": float(report.drop_pacing_analysis.drop_timestamp_seconds or 0.0),
                "subgenre": "EDM",
                "suggested_hashtags": ["#EDM", "#Festival", "#BassDrop", "#UltraMiami", "#ViralShorts"],
                "grading_rationale": str(report.algorithmic_recommendation),
                "graded_at": now_iso,
                "model_version": client.model_name,
            }

        except Exception as err:
            logger.error(f"Partition worker error grading video {video_id} ({gcs_uri}): {err}")
            yield {
                "video_id": video_id,
                "gcs_uri": gcs_uri,
                "raw_file_name": raw_file_name,
                "file_size_bytes": file_size_bytes,
                "duration_seconds": duration_seconds,
                "aspect_ratio": aspect_ratio,
                "status": "FAILED_DLQ",
                "error_message": str(err),
                "hrv_score": 0.0,
                "dpaw_score": 0.0,
                "adr_sfd_score": 0.0,
                "cke_mve_score": 0.0,
                "ltss_score": 0.0,
                "evpi_composite": 0.0,
                "trending_verdict": TrendingVerdict.LOW_REACH.value,
                "recommended_trim_start_sec": 0.0,
                "recommended_trim_end_sec": 0.0,
                "peak_drop_timestamp_sec": 0.0,
                "subgenre": "UNKNOWN",
                "suggested_hashtags": [],
                "grading_rationale": f"Grading failed: {err}; routed to Dead Letter Queue.",
                "graded_at": now_iso,
                "model_version": client.model_name,
            }
```

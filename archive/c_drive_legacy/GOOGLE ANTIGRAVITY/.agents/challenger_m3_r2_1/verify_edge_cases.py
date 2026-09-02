import math
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from media_pipeline.grading.spark_grading_job import grade_partition, DEFAULT_WEIGHTS

test_items = [
    None,
    123,
    "a bare string",
    [],
    [1, 2, 3],
    {},
    {"video_id": None, "gcs_uri": None, "duration_seconds": None, "file_size_bytes": None},
    {"video_id": "nan_test", "gcs_uri": "gs://b/test.mp4", "duration_seconds": float("nan")},
    {"video_id": "inf_test", "gcs_uri": "gs://b/test.mp4", "duration_seconds": float("inf")},
    {"video_id": "neginf_test", "gcs_uri": "gs://b/test.mp4", "duration_seconds": float("-inf")},
    {"video_id": "str_num_test", "gcs_uri": "gs://b/test.mp4", "duration_seconds": "45.5", "file_size_bytes": "123456"},
    {"video_id": "valid_test", "gcs_uri": "gs://b/test.mp4", "duration_seconds": 25.0, "file_size_bytes": 1000000}
]

res = list(grade_partition(iter(test_items), DEFAULT_WEIGHTS, mock_mode=True))
print(f"Total items processed: {len(res)}")
for i, r in enumerate(res):
    print(f"Item {i:02d}: status={r['status']:<10} video_id={r['video_id']:<20} err={r.get('error_message')}")

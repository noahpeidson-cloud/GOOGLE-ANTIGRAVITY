"""Milestone 1 Adversarial Stress Test Suite (Tier 5).

Empirical verification of:
1. 3-tier Win32 file lock detector (file_locker.py) under slow writers, in-flight locks, timeouts.
2. Ingest directory watcher (ingest_watcher.py) under rapid bursts, temp files, 0-byte stubs, deletion races.
3. JobManager thread-safety under 50+ to 100 concurrent threads with intense FSM mutations, queries, and pub/sub.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import os
from pathlib import Path
import random
import threading
import time
from typing import List, Set
import uuid

import pytest

from src.models.schemas import (
    AudioMasteringSettings,
    ClipSegment,
    ColorGradeSettings,
    EditDecisionList,
    JobStatus,
    VideoJob,
)
from src.models.state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidStateTransitionError as FSMInvalidTransitionError,
    can_transition,
    validate_transition,
)
from src.pipeline.job_manager import (
    InvalidStateTransitionError,
    JobEvent,
    JobEventType,
    JobManager,
    JobNotFoundError,
)
from src.watcher import file_locker
from src.watcher.file_locker import (
    DEFAULT_MEDIA_EXTENSIONS,
    DEFAULT_TEMP_EXTENSIONS,
    LockCheckResult,
    check_file_lock,
    check_file_lock_async,
    is_supported_media,
    is_temporary_file,
    wait_until_file_unlocked,
)
from src.watcher.ingest_watcher import IngestWatcher


# ============================================================================
# 1. Adversarial Tests: Win32 File Locker & In-Flight Writers
# ============================================================================

@pytest.mark.tier5
class TestAdversarialFileLocker:
    """Stress-tests for Win32 file locking and slow writer simulation."""

    def test_slow_writer_exclusive_lock_detection(self, tmp_path: Path) -> None:
        """Simulate an active in-flight slow writer holding exclusive write access."""
        target_file = tmp_path / "slow_writer_clip.mp4"
        write_done = threading.Event()
        write_started = threading.Event()

        def slow_writer() -> None:
            with open(target_file, "wb") as f:
                write_started.set()
                for i in range(15):
                    f.write(b"CHUNK_" + str(i).encode() * 200)
                    f.flush()
                    time.sleep(0.05)
            write_done.set()

        writer_thread = threading.Thread(target=slow_writer, daemon=True)
        writer_thread.start()

        assert write_started.wait(timeout=5.0)

        # While writer is actively writing, lock check MUST report locked
        locked_during_write = False
        for _ in range(10):
            res = check_file_lock(target_file, debounce_interval_sec=0.02)
            if res.is_locked:
                locked_during_write = True
                break
            time.sleep(0.03)

        assert locked_during_write is True, "File should have been detected as locked during slow write"

        # Wait for writer to finish
        assert write_done.wait(timeout=10.0)
        writer_thread.join()

        # After writer closes and size stabilizes, lock check MUST report unlocked and ready
        res_after = check_file_lock(target_file, debounce_interval_sec=0.05)
        assert res_after.is_ready is True
        assert res_after.is_locked is False
        assert res_after.file_size_bytes > 0

    @pytest.mark.asyncio
    async def test_async_wait_until_unlocked_with_slow_writer(self, tmp_path: Path) -> None:
        """Verify wait_until_file_unlocked waits until slow writer finishes and releases lock."""
        target_file = tmp_path / "async_slow_clip.mp4"
        stop_writing = False

        async def slow_writer_coro() -> None:
            with open(target_file, "wb") as f:
                for i in range(10):
                    if stop_writing:
                        break
                    f.write(b"ASYNC_DATA_" * 100)
                    f.flush()
                    await asyncio.sleep(0.06)

        writer_task = asyncio.create_task(slow_writer_coro())

        # Start waiting for file unlock with a 5.0s timeout
        lock_res = await wait_until_file_unlocked(
            target_file,
            timeout_sec=5.0,
            poll_interval_sec=0.05,
            debounce_interval_sec=0.05,
        )

        await writer_task

        assert lock_res.is_ready is True
        assert lock_res.is_locked is False
        assert lock_res.file_size_bytes > 0

    @pytest.mark.asyncio
    async def test_writer_hangs_indefinitely_timeout(self, tmp_path: Path) -> None:
        """Verify lock detector times out gracefully when writer never releases handle."""
        target_file = tmp_path / "abandoned_clip.mp4"
        f = open(target_file, "wb")
        f.write(b"INITIAL_HEADER")
        f.flush()

        try:
            start_t = time.monotonic()
            lock_res = await wait_until_file_unlocked(
                target_file,
                timeout_sec=0.5,
                poll_interval_sec=0.05,
                debounce_interval_sec=0.05,
            )
            elapsed = time.monotonic() - start_t

            assert lock_res.is_locked is True
            assert lock_res.is_ready is False
            assert "timed out" in lock_res.reason
            assert elapsed >= 0.45
        finally:
            f.close()

    def test_dynamic_size_mutation_during_debounce(self, tmp_path: Path) -> None:
        """Verify size mutation between stat checks fails Tier 3 debounce."""
        target_file = tmp_path / "mutating_size.mp4"
        target_file.write_bytes(b"A" * 100)

        # Mutate size in background while test_size_stability is checking
        def mutator() -> None:
            time.sleep(0.03)
            with open(target_file, "ab") as f:
                f.write(b"B" * 500)

        t = threading.Thread(target=mutator, daemon=True)
        t.start()

        ok, sz, err = file_locker.test_size_stability(target_file, interval_sec=0.1)
        t.join()

        assert ok is False
        assert "File size changed" in str(err)


# ============================================================================
# 2. Adversarial Tests: Temporary Files, Zero-Byte Files & Burst Ingest
# ============================================================================

@pytest.mark.tier5
class TestAdversarialWatcherAndTempFiles:
    """Stress-tests for temporary extensions, zero-byte stubs, and burst file drops."""

    def test_exhaustive_temporary_and_garbage_extension_matrix(self, tmp_path: Path) -> None:
        """Ensure all temporary, partial, and non-media formats are filtered by Tier 1."""
        temp_names = [
            "raw_video.mp4.tmp",
            "footage.mov.crdownload",
            "camera.mkv.part",
            "take1.mp4.downloading",
            "take2.mp4.aria2",
            "clip.mov.partial",
            "shot.mkv.uploading",
            "render.mp4.incomplete",
            "scratch.mp4.temp",
            ".scratch.mp4.swp",
            "video.mp4.lock",
            "~$office_lock.mp4",
            "._mac_fork.mov",
            ".DS_Store",
            "subtitles.srt",
            "metadata.xml",
            "script.sh",
            "photo.png",
        ]

        for name in temp_names:
            p = tmp_path / name
            p.write_bytes(b"temp_payload_data")
            res = check_file_lock(p, debounce_interval_sec=0.01)
            assert res.is_locked is True, f"File {name} should have failed Tier 1 lock filter"
            assert res.tier_failed == 1

    def test_zero_byte_stub_rejection(self, tmp_path: Path) -> None:
        """Ensure zero-byte stub files are rejected at Tier 3."""
        zero_file = tmp_path / "empty_stream.mp4"
        zero_file.touch()

        res = check_file_lock(zero_file, debounce_interval_sec=0.01)
        assert res.is_locked is True
        assert res.tier_failed == 3
        assert "zero bytes" in res.reason

    @pytest.mark.asyncio
    async def test_burst_ingest_100_files(self, tmp_path: Path) -> None:
        """Drop 100 media files in rapid burst into IngestWatcher and verify complete handoff."""
        watch_dir = tmp_path / "burst_ingest"
        watch_dir.mkdir()

        ready_files: List[Path] = []
        ready_event = asyncio.Event()
        expected_count = 100

        def on_ready(path: Path) -> None:
            ready_files.append(path)
            if len(ready_files) == expected_count:
                ready_event.set()

        watcher = IngestWatcher(
            watch_dir=watch_dir,
            on_file_ready=on_ready,
            debounce_delay_sec=0.05,
            size_debounce_interval_sec=0.05,
            lock_poll_interval_sec=0.05,
            lock_timeout_sec=5.0,
            polling_fallback_interval_sec=0.5,
        )

        await watcher.start()

        try:
            # Rapid burst drop of 100 files
            for i in range(expected_count):
                fpath = watch_dir / f"burst_clip_{i:03d}.mp4"
                fpath.write_bytes(b"VIDEO_HEADER_" + os.urandom(256))

            # Trigger scan to ensure immediate pickup
            await watcher.scan_once()

            try:
                await asyncio.wait_for(ready_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                pass

            assert len(ready_files) == expected_count, (
                f"Expected {expected_count} files handed off, but got {len(ready_files)}"
            )
            # Ensure all paths unique
            assert len(set(ready_files)) == expected_count
        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_burst_mixed_valid_and_invalid_files(self, tmp_path: Path) -> None:
        """Drop 120 mixed files (40 valid .mp4, 40 .crdownload/.tmp, 40 .txt/.json) into IngestWatcher."""
        watch_dir = tmp_path / "mixed_burst"
        watch_dir.mkdir()

        ready_files: List[Path] = []
        ready_event = asyncio.Event()
        valid_count = 40

        def on_ready(path: Path) -> None:
            ready_files.append(path)
            if len(ready_files) == valid_count:
                ready_event.set()

        watcher = IngestWatcher(
            watch_dir=watch_dir,
            on_file_ready=on_ready,
            debounce_delay_sec=0.05,
            size_debounce_interval_sec=0.05,
            lock_poll_interval_sec=0.05,
            lock_timeout_sec=3.0,
            polling_fallback_interval_sec=0.5,
        )

        await watcher.start()

        try:
            # 40 valid media files
            for i in range(valid_count):
                (watch_dir / f"valid_{i:02d}.mp4").write_bytes(b"MP4_DATA_" + os.urandom(128))

            # 40 temporary / downloading files
            for i in range(40):
                (watch_dir / f"temp_{i:02d}.mp4.crdownload").write_bytes(b"TEMP_DATA")
                (watch_dir / f"part_{i:02d}.tmp").write_bytes(b"PART_DATA")

            # 40 non-media files
            for i in range(40):
                (watch_dir / f"notes_{i:02d}.txt").write_bytes(b"NOTE_DATA")
                (watch_dir / f"meta_{i:02d}.json").write_bytes(b"{}")

            await watcher.scan_once()

            try:
                await asyncio.wait_for(ready_event.wait(), timeout=8.0)
            except asyncio.TimeoutError:
                pass

            assert len(ready_files) == valid_count
            assert all(p.suffix.lower() == ".mp4" for p in ready_files)
        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_rapid_creation_and_immediate_deletion(self, tmp_path: Path) -> None:
        """Verify watcher does not crash when files are created and immediately deleted."""
        watch_dir = tmp_path / "deleted_drops"
        watch_dir.mkdir()

        errors: List[str] = []

        def on_error(path: Path, reason: str) -> None:
            errors.append(f"{path.name}: {reason}")

        watcher = IngestWatcher(
            watch_dir=watch_dir,
            on_error=on_error,
            debounce_delay_sec=0.01,
            size_debounce_interval_sec=0.01,
            lock_poll_interval_sec=0.02,
            lock_timeout_sec=0.5,
        )

        await watcher.start()

        try:
            for i in range(20):
                f = watch_dir / f"ghost_{i}.mp4"
                f.write_bytes(b"GHOST_DATA")
                f.unlink()  # Immediate deletion

            await watcher.scan_once()
            await asyncio.sleep(0.3)
            # Watcher should remain healthy and running
            assert watcher.is_running is True
        finally:
            await watcher.stop()


# ============================================================================
# 3. Adversarial Tests: JobManager Under Extreme Multi-Threaded Load (50+ to 100 Threads)
# ============================================================================

@pytest.mark.tier5
class TestAdversarialJobManagerConcurrency:
    """Stress-tests for JobManager thread-safety with 50+ to 100 concurrent worker threads."""

    def test_job_manager_50_threads_complete_lifecycle(self) -> None:
        """50 concurrent threads executing complete job lifecycles and mutations simultaneously."""
        jm = JobManager()
        num_threads = 50
        jobs_per_thread = 10
        total_expected_jobs = num_threads * jobs_per_thread

        def worker_lifecycle(thread_idx: int) -> List[str]:
            local_job_ids = []
            for j_idx in range(jobs_per_thread):
                filename = f"footage_t{thread_idx}_j{j_idx}.mp4"
                job = jm.create_job(source_filepath=filename, file_size_bytes=1024 * (thread_idx + 1))
                jid = job.job_id
                local_job_ids.append(jid)

                # Transition 1: INGESTED -> PROBING
                jm.update_status(jid, JobStatus.PROBING)
                jm.update_progress(jid, 10.0)

                # Attach metadata
                jm.update_probe_metadata(jid, {
                    "width": 3840,
                    "height": 2160,
                    "fps": 60.0,
                    "thread_idx": thread_idx,
                })

                # Transition 2: PROBING -> PROBED -> ANALYZING
                jm.update_status(jid, JobStatus.PROBED)
                jm.update_status(jid, JobStatus.ANALYZING)
                jm.update_progress(jid, 35.0)

                # Attach EDL
                edl = EditDecisionList(
                    job_id=jid,
                    source_video_path=filename,
                    segments=[ClipSegment(source_in_sec=0.0, source_out_sec=5.0, label=f"t{thread_idx}")],
                    color_grade=ColorGradeSettings(contrast=1.2, saturation=1.1),
                    audio_mastering=AudioMasteringSettings(normalize_lufs=True),
                )
                jm.update_edl(jid, edl, is_override=False)

                # Transition 3: ANALYZING -> AWAITING_OVERRIDE -> APPROVED
                jm.update_status(jid, JobStatus.AWAITING_OVERRIDE)
                jm.update_status(jid, JobStatus.APPROVED)
                jm.update_progress(jid, 60.0)

                # Transition 4: APPROVED -> RENDERING -> DELIVERING -> DELIVERED
                jm.update_status(jid, JobStatus.RENDERING)
                jm.update_progress(jid, 85.0)
                jm.update_status(jid, JobStatus.DELIVERING)
                jm.set_delivery_path(jid, f"delivery/final_{filename}")
                jm.update_status(jid, JobStatus.DELIVERED)
                jm.update_progress(jid, 100.0)

            return local_job_ids

        start_time = time.monotonic()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_lifecycle, t) for t in range(num_threads)]
            all_ids = []
            for f in as_completed(futures):
                all_ids.extend(f.result())
        elapsed = time.monotonic() - start_time

        # Assertions
        assert len(all_ids) == total_expected_jobs
        assert jm.count_jobs() == total_expected_jobs
        assert jm.count_jobs(JobStatus.DELIVERED) == total_expected_jobs
        assert jm.count_jobs(JobStatus.FAILED) == 0

        # Query all and verify properties
        delivered_jobs = jm.list_jobs(status=JobStatus.DELIVERED, limit=total_expected_jobs)
        assert len(delivered_jobs) == total_expected_jobs
        for j in delivered_jobs:
            assert j.status == JobStatus.DELIVERED
            assert j.progress_percent == 100.0
            assert j.active_edl is not None
            assert j.probe_metadata is not None
            assert j.delivery_filepath is not None

    def test_job_manager_100_threads_massive_stress(self) -> None:
        """100 concurrent threads creating, updating, querying, and deleting 2,000 jobs."""
        jm = JobManager()
        num_threads = 100
        jobs_per_thread = 20
        total_created = num_threads * jobs_per_thread

        def stress_task(thread_id: int) -> int:
            count = 0
            for i in range(jobs_per_thread):
                job = jm.create_job(f"massive_clip_{thread_id}_{i}.mp4")
                jid = job.job_id
                jm.update_progress(jid, 25.0)
                jm.update_status(jid, JobStatus.PROBING)
                jm.update_progress(jid, 50.0)
                jm.update_status(jid, JobStatus.PROBED)
                jm.update_status(jid, JobStatus.ANALYZING)
                jm.update_status(jid, JobStatus.AWAITING_OVERRIDE)
                count += 1
                # Periodically query
                if i % 5 == 0:
                    _ = jm.list_jobs(limit=10, active_only=True)
                    _ = jm.count_jobs(JobStatus.AWAITING_OVERRIDE)
            return count

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(stress_task, t) for t in range(num_threads)]
            results = [f.result() for f in as_completed(futures)]

        assert sum(results) == total_created
        assert jm.count_jobs() == total_created
        assert jm.count_jobs(JobStatus.AWAITING_OVERRIDE) == total_created

    def test_job_manager_race_condition_state_conflicts(self) -> None:
        """50 concurrent threads race to transition the SAME job into competing states."""
        jm = JobManager()
        # Create a single shared job in INGESTED status
        job = jm.create_job("contested_job.mp4", initial_status=JobStatus.INGESTED)
        jid = job.job_id

        num_racers = 50
        results = {"success": 0, "invalid_transition_errors": 0}
        lock = threading.Lock()

        def racer(racer_idx: int) -> None:
            target = random.choice([JobStatus.PROBING, JobStatus.RENDERING, JobStatus.FAILED])
            try:
                jm.update_status(jid, target)
                with lock:
                    results["success"] += 1
            except (InvalidStateTransitionError, FSMInvalidTransitionError):
                with lock:
                    results["invalid_transition_errors"] += 1

        with ThreadPoolExecutor(max_workers=num_racers) as executor:
            futures = [executor.submit(racer, i) for i in range(num_racers)]
            for f in futures:
                f.result()

        # At least one transition attempted or rejected, repository state remains valid and uncorrupted
        final_job = jm.get_job_or_raise(jid)
        assert final_job.status in (JobStatus.INGESTED, JobStatus.PROBING, JobStatus.FAILED)
        assert results["success"] + results["invalid_transition_errors"] == num_racers

    def test_job_manager_concurrent_subscribers_and_event_flood(self) -> None:
        """Heavy concurrency between event emitters, subscriber registrations, and unsubscriptions."""
        jm = JobManager()
        num_emitters = 30
        num_subscribers = 20
        events_captured: List[JobEvent] = []
        lock = threading.Lock()

        def listener_callback(event: JobEvent) -> None:
            with lock:
                events_captured.append(event)

        # Register multiple initial subscribers
        sub_ids = []
        for _ in range(num_subscribers):
            sub_ids.append(jm.subscribe(JobEventType.ALL, listener_callback))

        def emitter_task(idx: int) -> None:
            for i in range(15):
                j = jm.create_job(f"clip_stream_{idx}_{i}.mp4")
                jm.update_progress(j.job_id, float(i * 5))
                # Dynamic subscribe/unsubscribe
                if i % 3 == 0:
                    sid = jm.subscribe(JobEventType.PROGRESS_UPDATED, listener_callback)
                    time.sleep(0.001)
                    jm.unsubscribe(sid)

        with ThreadPoolExecutor(max_workers=num_emitters) as executor:
            futures = [executor.submit(emitter_task, i) for i in range(num_emitters)]
            for f in futures:
                f.result()

        # Cleanly unsubscribe all initial
        for sid in sub_ids:
            jm.unsubscribe(sid)

        assert len(events_captured) > 0
        assert jm.count_jobs() == num_emitters * 15

    def test_job_manager_concurrent_readers_and_writers(self) -> None:
        """30 concurrent writer threads and 30 concurrent reader threads querying and mutating."""
        jm = JobManager()
        stop_flag = threading.Event()
        read_counts = {"queries": 0, "jobs_read": 0}
        read_lock = threading.Lock()

        def writer_task(writer_id: int) -> None:
            for i in range(25):
                job = jm.create_job(f"w_{writer_id}_{i}.mp4")
                jm.update_progress(job.job_id, 50.0)
                if i % 5 == 0:
                    jm.delete_job(job.job_id)

        def reader_task() -> None:
            while not stop_flag.is_set():
                jobs = jm.list_jobs(limit=100, sort_desc=True)
                total = jm.count_jobs()
                active = jm.list_jobs(active_only=True)
                with read_lock:
                    read_counts["queries"] += 1
                    read_counts["jobs_read"] += len(jobs)
                time.sleep(0.002)

        # Start 30 readers
        reader_threads = [threading.Thread(target=reader_task, daemon=True) for _ in range(30)]
        for rt in reader_threads:
            rt.start()

        # Run 30 writers
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(writer_task, i) for i in range(30)]
            for f in futures:
                f.result()

        stop_flag.set()
        for rt in reader_threads:
            rt.join(timeout=2.0)

        assert read_counts["queries"] > 0
        # Check repository state integrity
        remaining_jobs = jm.list_jobs(limit=1000)
        assert len(remaining_jobs) == jm.count_jobs()

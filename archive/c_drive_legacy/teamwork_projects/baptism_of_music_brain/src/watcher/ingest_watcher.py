"""Ingestion Directory Watcher with Event Debounce, Polling Fallback, and Lock Handoff."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Set, Union

from src.watcher.file_locker import (
    DEFAULT_MEDIA_EXTENSIONS,
    DEFAULT_TEMP_EXTENSIONS,
    is_supported_media,
    is_temporary_file,
    wait_until_file_unlocked,
)

logger = logging.getLogger(__name__)


class IngestWatcher:
    """
    Asynchronous filesystem watcher for the ingest directory.
    Monitors raw video drops, verifies 3-tier lock release, and invokes pipeline handoff.
    """

    def __init__(
        self,
        watch_dir: Union[str, Path],
        on_file_ready: Optional[Callable[[Path], Union[Awaitable[None], None]]] = None,
        on_error: Optional[Callable[[Path, str], Union[Awaitable[None], None]]] = None,
        allowed_extensions: Optional[Set[str]] = None,
        temp_extensions: Optional[Set[str]] = None,
        debounce_delay_sec: float = 0.5,
        lock_timeout_sec: float = 60.0,
        lock_poll_interval_sec: float = 0.5,
        size_debounce_interval_sec: float = 0.5,
        enable_polling_fallback: bool = True,
        polling_fallback_interval_sec: float = 5.0,
    ) -> None:
        self.watch_dir = Path(watch_dir).resolve()
        self.on_file_ready = on_file_ready
        self.on_error = on_error
        self.allowed_extensions = allowed_extensions or DEFAULT_MEDIA_EXTENSIONS
        self.temp_extensions = temp_extensions or DEFAULT_TEMP_EXTENSIONS
        self.debounce_delay_sec = debounce_delay_sec
        self.lock_timeout_sec = lock_timeout_sec
        self.lock_poll_interval_sec = lock_poll_interval_sec
        self.size_debounce_interval_sec = size_debounce_interval_sec
        self.enable_polling_fallback = enable_polling_fallback
        self.polling_fallback_interval_sec = polling_fallback_interval_sec

        self._running = False
        self._watcher_task: Optional[asyncio.Task] = None
        self._polling_task: Optional[asyncio.Task] = None
        self._active_evaluations: Dict[Path, asyncio.Task] = {}
        self._processed_files: Set[Path] = set()

    @property
    def is_running(self) -> bool:
        return self._running

    def set_callback(self, on_file_ready: Callable[[Path], Union[Awaitable[None], None]]) -> None:
        """Register or update the on_file_ready callback."""
        self.on_file_ready = on_file_ready

    async def start(self) -> None:
        """Starts the watcher and polling fallback background tasks."""
        if self._running:
            return

        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self._running = True
        logger.info(f"Starting IngestWatcher on: {self.watch_dir}")

        # Launch primary watcher task using watchfiles
        self._watcher_task = asyncio.create_task(self._run_watchfiles(), name="ingest_watchfiles")

        # Launch polling fallback if enabled
        if self.enable_polling_fallback:
            self._polling_task = asyncio.create_task(self._run_polling_fallback(), name="ingest_polling")

        # Execute an immediate initial scan
        await self.scan_once()

    async def stop(self) -> None:
        """Stops the watcher and gracefully cancels in-flight evaluation tasks."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping IngestWatcher...")

        if self._watcher_task and not self._watcher_task.done():
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.debug(f"Watcher task exception during stop: {exc}")

        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.debug(f"Polling task exception during stop: {exc}")

        # Cancel active evaluations
        active_tasks = list(self._active_evaluations.values())
        for task in active_tasks:
            if not task.done():
                task.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        self._active_evaluations.clear()

        logger.info("IngestWatcher stopped successfully.")

    async def scan_once(self) -> int:
        """Scans the watch directory for any pending media files."""
        if not self.watch_dir.exists():
            return 0

        detected_count = 0
        try:
            for entry in os.scandir(self.watch_dir):
                if entry.is_file():
                    p = Path(entry.path).resolve()
                    if self._should_consider_file(p):
                        self._trigger_file_evaluation(p)
                        detected_count += 1
        except Exception as exc:
            logger.error(f"Error during scan_once: {exc}", exc_info=True)

        return detected_count

    def _should_consider_file(self, path: Path) -> bool:
        """Determines if a file path is eligible for lock evaluation."""
        if path in self._processed_files or path in self._active_evaluations:
            return False
        if is_temporary_file(path, self.temp_extensions):
            return False
        if not is_supported_media(path, self.allowed_extensions):
            return False
        return True

    def _trigger_file_evaluation(self, path: Path) -> None:
        """Debounces and schedules a background evaluation task for a file."""
        if path in self._active_evaluations and not self._active_evaluations[path].done():
            return

        task = asyncio.create_task(
            self._evaluate_and_handoff(path),
            name=f"eval_lock_{path.name}"
        )
        self._active_evaluations[path] = task

        def _cleanup(t: asyncio.Task) -> None:
            self._active_evaluations.pop(path, None)

        task.add_done_callback(_cleanup)

    async def _evaluate_and_handoff(self, path: Path) -> None:
        """Wait for lock release and hand off to the pipeline callback."""
        if self.debounce_delay_sec > 0:
            await asyncio.sleep(self.debounce_delay_sec)

        if not path.exists():
            return

        logger.info(f"Evaluating 3-tier lock status for: {path.name}")
        lock_result = await wait_until_file_unlocked(
            path,
            timeout_sec=self.lock_timeout_sec,
            poll_interval_sec=self.lock_poll_interval_sec,
            debounce_interval_sec=self.size_debounce_interval_sec,
            media_extensions=self.allowed_extensions,
            temp_extensions=self.temp_extensions,
        )

        if lock_result.is_ready:
            logger.info(f"File unlocked and stable: {path.name} ({lock_result.file_size_bytes} bytes). Handing off to pipeline.")
            self._processed_files.add(path)
            if self.on_file_ready:
                try:
                    res = self.on_file_ready(path)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as exc:
                    logger.error(f"Error during on_file_ready callback for {path.name}: {exc}", exc_info=True)
                    if self.on_error:
                        err_res = self.on_error(path, str(exc))
                        if asyncio.iscoroutine(err_res):
                            await err_res
        else:
            logger.warning(f"File failed lock release: {path.name}. Reason: {lock_result.reason}")
            if self.on_error:
                err_res = self.on_error(path, lock_result.reason)
                if asyncio.iscoroutine(err_res):
                    await err_res

    async def _run_watchfiles(self) -> None:
        """Primary watcher loop using watchfiles."""
        try:
            import watchfiles
            async for changes in watchfiles.awatch(self.watch_dir, stop_event=None):
                if not self._running:
                    break
                for change_type, raw_path in changes:
                    p = Path(raw_path).resolve()
                    if self._should_consider_file(p):
                        self._trigger_file_evaluation(p)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning(f"watchfiles engine encountered error: {exc}. Relying on polling fallback.")

    async def _run_polling_fallback(self) -> None:
        """Periodic background polling loop to guarantee zero missed drops."""
        while self._running:
            try:
                await asyncio.sleep(self.polling_fallback_interval_sec)
                if self._running:
                    await self.scan_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Polling fallback error: {exc}", exc_info=True)

    async def __aenter__(self) -> "IngestWatcher":
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.stop()

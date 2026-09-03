import os
import sys
import time
import logging
from threading import Thread
from typing import Dict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

WATCH_DIR = r"D:\Downloads"
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.mkv', '.avi')
DEBOUNCE_SECONDS = 5

def trigger_media_pipeline(filepath: str):
    """
    Stub for the media pipeline.
    Next steps:
    1. FFmpeg -14 LUFS normalization
    2. DaVinci Resolve queueing
    """
    logging.info(f"PIPELINE TRIGGERED: Processing {filepath}")
    logging.info(" -> Step 1: FFmpeg -14 LUFS normalization")
    logging.info(" -> Step 2: DaVinci Resolve queueing")

class IngestEventHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.active_files: Dict[str, float] = {}
        
        # Start the background debounce checker
        self.checker_thread = Thread(target=self._debounce_checker, daemon=True)
        self.checker_thread.start()

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(VIDEO_EXTENSIONS):
            logging.info(f"File creation detected: {event.src_path}")
            self.active_files[event.src_path] = time.time()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith(VIDEO_EXTENSIONS):
            # Update the last modified timestamp
            self.active_files[event.src_path] = time.time()

    def _debounce_checker(self):
        while True:
            current_time = time.time()
            for filepath, last_modified in list(self.active_files.items()):
                if current_time - last_modified >= DEBOUNCE_SECONDS:
                    # File has been quiet for DEBOUNCE_SECONDS.
                    if os.path.exists(filepath):
                        # Attempt to open file to check if it's locked by the OS (common in Windows during copy)
                        try:
                            with open(filepath, 'a'):
                                pass
                            logging.info(f"File copy complete (debounced): {filepath}")
                            trigger_media_pipeline(filepath)
                            del self.active_files[filepath]
                        except IOError:
                            # File is still locked by another process
                            self.active_files[filepath] = time.time()
                    else:
                        del self.active_files[filepath]
            time.sleep(1)

def main():
    if not os.path.exists(WATCH_DIR):
        logging.error(f"CRITICAL ERROR: Watch directory does not exist: {WATCH_DIR}")
        sys.exit(1)
    
    if not os.path.isdir(WATCH_DIR):
        logging.error(f"CRITICAL ERROR: Watch path is not a directory: {WATCH_DIR}")
        sys.exit(1)

    event_handler = IngestEventHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=False)
    
    logging.info(f"Starting 8K Ingest Daemon on {WATCH_DIR}")
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()

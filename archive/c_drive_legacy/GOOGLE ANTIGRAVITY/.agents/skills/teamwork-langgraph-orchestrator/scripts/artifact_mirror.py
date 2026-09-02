import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ArtifactMirrorHandler(FileSystemEventHandler):
    def __init__(self, source_file, dest_file):
        self.source_file = source_file
        self.dest_file = dest_file
        self.last_sync = 0
        self.debounce_seconds = 1.0

    def on_modified(self, event):
        if os.path.abspath(event.src_path) == os.path.abspath(self.source_file):
            current_time = time.time()
            if current_time - self.last_sync >= self.debounce_seconds:
                self.sync_files()
                self.last_sync = current_time

    def sync_files(self):
        try:
            with open(self.source_file, 'r', encoding='utf-8') as src:
                content = src.read()
            with open(self.dest_file, 'w', encoding='utf-8') as dst:
                dst.write(content)
            print(f"[{time.strftime('%H:%M:%S')}] Mirrored {os.path.basename(self.source_file)} to {os.path.basename(self.dest_file)}")
        except Exception as e:
            print(f"Error mirroring artifacts: {e}")

def run_mirror_daemon(source, dest):
    print(f"Starting Artifact Mirror Daemon (R15)\nSource: {source}\nDest: {dest}")
    event_handler = ArtifactMirrorHandler(source, dest)
    observer = Observer()
    
    # Watch the directory containing the source file
    watch_dir = os.path.dirname(os.path.abspath(source))
    observer.schedule(event_handler, watch_dir, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python artifact_mirror.py <source_file> <dest_file>")
        sys.exit(1)
    
    # Ensure dest directory exists
    os.makedirs(os.path.dirname(os.path.abspath(sys.argv[2])), exist_ok=True)
    
    run_mirror_daemon(sys.argv[1], sys.argv[2])

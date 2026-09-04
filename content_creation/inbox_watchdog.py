import time
import os
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WORKSPACE_ROOT = Path(__file__).parent.resolve()
INBOX_DIR = Path("G:/My Drive/Antigravity_Mobile_Inbox")

class InboxHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            self.process_file(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            self.process_file(Path(event.dest_path))

    def process_file(self, filepath: Path):
        # Ignore hidden files, temp files, or incomplete downloads
        if filepath.name.startswith('.') or filepath.suffix.lower() in ['.tmp', '.crdownload']:
            return
            
        print(f"\n[WATCHDOG] New file detected: {filepath.name}")
        
        # Wait for file to finish copying/syncing
        if not self.wait_for_file_ready(filepath):
            print(f"[WATCHDOG] Timed out waiting for file to be ready: {filepath}")
            return
            
        print(f"[WATCHDOG] File ready. Triggering ingest_assets.py...")
        
        # Trigger Ingest
        ingest_cmd = [
            "python", "ingest_assets.py",
            "-i", str(filepath),
            "--event", "MobileUpload",
            "--brand", "laser_baptism",
            "--tier", "pillar_b_club_spotlight",
            "--ffprobe-path", r"C:\Users\noahp\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffprobe.exe"
        ]
        
        try:
            CREATE_NO_WINDOW = 0x08000000
            subprocess.run(ingest_cmd, check=True, cwd=str(WORKSPACE_ROOT), creationflags=CREATE_NO_WINDOW)
            print("[WATCHDOG] Ingestion complete. Triggering proxy_generator.py...")
            
            # Trigger Proxy Generation
            subprocess.run(["python", "proxy_generator.py"], check=True, cwd=str(WORKSPACE_ROOT), creationflags=CREATE_NO_WINDOW)
            print(f"[WATCHDOG] Proxy generation triggered for {filepath.name}. Pipeline complete.")
            
        except subprocess.CalledProcessError as e:
            print(f"[WATCHDOG] Error processing {filepath.name}: {e}")
            
    def wait_for_file_ready(self, filepath: Path, timeout=60, settle_time=2):
        """Waits until the file size stops changing and file can be read."""
        start_time = time.time()
        last_size = -1
        
        while time.time() - start_time < timeout:
            if not filepath.exists():
                return False
                
            try:
                current_size = filepath.stat().st_size
                if current_size > 0 and current_size == last_size:
                    # File size hasn't changed, try to open it to check permissions
                    try:
                        with open(filepath, 'rb') as f:
                            pass
                        return True
                    except PermissionError:
                        pass # Still locked
                last_size = current_size
            except OSError:
                pass
                
            time.sleep(settle_time)
            
        return False

def start_watchdog():
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    
    event_handler = InboxHandler()
    observer = Observer()
    observer.schedule(event_handler, str(INBOX_DIR), recursive=False)
    
    print(f"[*] Starting Inbox Watchdog on: {INBOX_DIR}")
    print("[*] Waiting for new media files...")
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_watchdog()

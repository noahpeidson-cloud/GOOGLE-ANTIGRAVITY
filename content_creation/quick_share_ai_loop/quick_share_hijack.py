import time
import os
import logging
import shutil
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from gemini_tagger import tag_video
from database_sink import insert_video_analytics

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

QUICK_SHARE_DIR = Path(os.path.expanduser("~")) / "Downloads" / "Quick Share"
FINAL_DESTINATION = Path("G:/My Drive/GOOGLE ANTIGRAVITY/photos_triage_project/Raw_Ingest")

def wait_for_file_to_finish(filepath, timeout=300):
    """Wait until Quick Share finishes writing the massive file by checking if file size is stable."""
    file_path = Path(filepath)
    historical_size = -1
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not file_path.exists():
            return False
            
        current_size = file_path.stat().st_size
        
        # If size is > 0 and hasn't changed in 3 seconds, it's done writing.
        if current_size > 0 and current_size == historical_size:
            # Final check to see if we can open it in read/write mode (OS lock release)
            try:
                with open(filepath, 'a'):
                    return True
            except IOError:
                pass
                
        historical_size = current_size
        time.sleep(3)
        
    return False

class QuickShareHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
            
        filepath = Path(event.src_path)
        if filepath.suffix.lower() not in ['.mp4', '.mov', '.webm']:
            return
            
        logging.info(f"🚨 Quick Share Intercept: New video detected -> {filepath.name}")
        
        if wait_for_file_to_finish(filepath):
            logging.info(f"✅ File write complete: {filepath.name}. Initiating AI Tagging...")
            
            try:
                # 1. Run Gemini Omni Flash tagging
                tags_json = tag_video(str(filepath))
                
                # 2. Sink to SQLite
                insert_video_analytics(str(filepath), tags_json)
                
                logging.info(f"🎯 ML Loop Complete for {filepath.name}!")
                
                # 3. Move the file to Google Drive with SHA-256 Verification
                FINAL_DESTINATION.mkdir(parents=True, exist_ok=True)
                dest_path = FINAL_DESTINATION / filepath.name
                
                logging.info(f"🚚 Moving {filepath.name} to {FINAL_DESTINATION} with SHA-256 Verification...")
                
                import hashlib
                def get_file_hash(path):
                    h = hashlib.sha256()
                    with open(path, 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            h.update(chunk)
                    return h.hexdigest()
                    
                hash_src = get_file_hash(filepath)
                logging.info(f"🔒 Source Hash (C:): {hash_src}")
                
                shutil.copy2(str(filepath), str(dest_path))
                
                hash_dest = get_file_hash(dest_path)
                logging.info(f"🔒 Dest Hash (G:): {hash_dest}")
                
                if hash_src == hash_dest:
                    os.remove(str(filepath))
                    logging.info(f"✅ Hash Match Verified! Original file deleted. C: drive space recovered.")
                else:
                    logging.error(f"❌ HASH MISMATCH! Copy failed. Original file retained on C:.")
                
            except Exception as e:
                logging.error(f"❌ ML Loop Failed: {e}")
        else:
            logging.error(f"❌ Timeout waiting for Quick Share to finish writing {filepath.name}")

def start_watchdog():
    os.makedirs(QUICK_SHARE_DIR, exist_ok=True)
    
    event_handler = QuickShareHandler()
    observer = Observer()
    observer.schedule(event_handler, str(QUICK_SHARE_DIR), recursive=False)
    
    logging.info(f"👀 Watchdog active. Monitoring Quick Share folder: {QUICK_SHARE_DIR}")
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_watchdog()

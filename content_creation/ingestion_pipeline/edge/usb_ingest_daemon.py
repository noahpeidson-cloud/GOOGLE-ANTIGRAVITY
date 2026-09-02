import wmi
import pythoncom
import subprocess
import time
import os
import shutil

# ==============================================================================
# Edge Ingress: Autonomous WMI USB Daemon
# ==============================================================================
# This daemon uses Windows Management Instrumentation (WMI) to listen for hardware
# insertion events. Upon detecting the S26 Ultra via ADB, it autonomously pulls 
# the 8K APV footage to bypass fragile MTP protocols.

STAGING_DIR = r"g:\My Drive\GOOGLE ANTIGRAVITY\content_creation\ingestion_pipeline\staging"
LANGGRAPH_INPUT_DIR = r"g:\My Drive\GOOGLE ANTIGRAVITY\content_creation\ingestion_pipeline\langgraph_input"

def ensure_directories():
    os.makedirs(STAGING_DIR, exist_ok=True)
    os.makedirs(LANGGRAPH_INPUT_DIR, exist_ok=True)

def check_adb_device():
    """Checks if an Android device is authorized and visible to ADB."""
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")
        # Example output:
        # List of devices attached
        # 1234567890abcdef    device
        for line in lines[1:]:
            if "device" in line and "unauthorized" not in line and "offline" not in line:
                return True
        return False
    except Exception as e:
        print(f"[ERROR] Could not check ADB devices: {e}")
        return False

def ingest_footage():
    print("[INFO] Authorized S26 Ultra detected! Initiating ADB Pull for 8K footage...")
    
    # 1. Pull the camera folder (DCIM/Camera) to the local staging directory
    # Using adb pull -a to preserve timestamps.
    try:
        subprocess.run(["adb", "pull", "-a", "/sdcard/DCIM/Camera/", STAGING_DIR], check=True)
        print("[INFO] ADB Pull Complete.")
        
        # 2. Move files to LangGraph input dir to trigger the cloud pipeline
        pulled_files_dir = os.path.join(STAGING_DIR, "Camera")
        if os.path.exists(pulled_files_dir):
            for filename in os.listdir(pulled_files_dir):
                file_path = os.path.join(pulled_files_dir, filename)
                if os.path.isfile(file_path):
                    shutil.move(file_path, os.path.join(LANGGRAPH_INPUT_DIR, filename))
            print(f"[SUCCESS] Footage staged for LangGraph orchestration in {LANGGRAPH_INPUT_DIR}")
            
            # Optionally: Clean up the S26 Ultra storage after successful transfer
            # subprocess.run(["adb", "shell", "rm", "-rf", "/sdcard/DCIM/Camera/*"])
            
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] ADB Pull failed: {e}")

def listen_for_usb():
    print("[INFO] WMI Daemon started. Listening for USB connection events...")
    pythoncom.CoInitialize()
    c = wmi.WMI()
    
    # EventType 2 = Device Arrival (Insertion)
    watcher = c.watch_for(
        notification_type="CreationEvent",
        wmi_class="Win32_DeviceChangeEvent",
        EventType=2
    )
    
    while True:
        try:
            device_event = watcher()
            print("[EVENT] Hardware Insertion Detected.")
            
            # Give the USB stack a moment to fully enumerate and ADB server to recognize
            time.sleep(3)
            
            if check_adb_device():
                ingest_footage()
            else:
                print("[WARN] USB device inserted, but no authorized ADB device found. Ignoring.")
                
        except Exception as e:
            print(f"[ERROR] WMI Watcher exception: {e}")
            time.sleep(5) # Backoff before retrying

if __name__ == "__main__":
    ensure_directories()
    listen_for_usb()

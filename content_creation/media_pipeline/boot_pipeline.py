import subprocess
import time
import sys

def main():
    print("Booting Media Pipeline Orchestrator...")
    
    # Check if gcloud project is set
    try:
        gcloud_check = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True, check=True)
        if "(unset)" in gcloud_check.stdout:
            print("WARNING: Google Cloud project is not set. Please run: gcloud config set project <YOUR_PROJECT_ID>")
    except FileNotFoundError:
        print("WARNING: gcloud CLI not found in PATH.")

    # Boot Ingestion Daemon
    print("\nBooting Android Wi-Fi Ingestion Daemon...")
    ingestion = subprocess.Popen(
        [sys.executable, "-m", "ingestion.ingestion_daemon"],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(2)
    
    # Boot PySpark Grading Job
    print("\nBooting PySpark Gemini-Omni Grading Engine...")
    grading = subprocess.Popen(
        [sys.executable, "-m", "grading.spark_grading_job"],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    print("\nZero-Friction Boot Complete. The Ingestion and Grading pipelines are now running in background consoles.")

if __name__ == "__main__":
    main()

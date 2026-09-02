import subprocess
import time
import sys
import webbrowser
import os

def main():
    print("Booting Unified Operations Hub...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Boot the Resiliency Gateway (FastAPI)
    print("\nStarting DLQ Gateway Backend...")
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "gateway.app:app", "--port", "8000"],
        cwd=base_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(2)
    
    # 2. Boot the ML Agent
    print("\nStarting Antigravity ML Agent Loop...")
    subprocess.Popen(
        [sys.executable, "-m", "ml_agent.ml_agent"],
        cwd=base_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(2)
    
    # 3. Boot Next.js Command Center
    print("\nStarting Next.js Command Center...")
    dashboard_dir = os.path.join(base_dir, "dashboard")
    subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=dashboard_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        shell=True
    )
    
    print("\nZero-Friction Boot Complete! Opening your browser in 5 seconds...")
    time.sleep(5)
    webbrowser.open("http://localhost:3000")

if __name__ == "__main__":
    main()

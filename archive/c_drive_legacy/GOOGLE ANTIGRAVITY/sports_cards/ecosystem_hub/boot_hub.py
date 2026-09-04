import subprocess
import time
import sys
import webbrowser

def main():
    print("Booting Sports Card Ecosystem Hub...")
    
    # Boot FastAPI Backend (Port 8000)
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api:app", "--port", "8000"],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    print("Backend API initializing on Port 8000...")
    time.sleep(2)
    
    # Boot Streamlit Frontend (Port 8501)
    frontend = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", "8501"],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    print("Frontend UI initializing on Port 8501...")
    time.sleep(3)
    
    print("Zero-Friction Boot Complete. Opening Browser...")
    webbrowser.open("http://localhost:8501")

if __name__ == "__main__":
    main()

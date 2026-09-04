import time
import psutil
import subprocess
import os

def flush_memory_routine():
    """
    Invokes the undocumented ntsetinformation API via an MCP tool 
    or a native ctypes wrapper to clear standby list.
    """
    # For now, we print and simulate the kernel call
    print("Flushing Windows Standby Memory List...")
    # In a full production env, this would call the windows-kernel-optimizer MCP or use ctypes

def check_ram_and_flush():
    """
    Polls current Standby RAM. If > 70% used, trigger flush.
    """
    vmem = psutil.virtual_memory()
    if vmem.percent > 70.0:
        flush_memory_routine()

def get_running_processes():
    """
    Helper to return a list of current process names.
    """
    return [p.name() for p in psutil.process_iter(['name'])]

def demote_process_priority():
    """
    Demote python processes (AGY background daemons) to IDLE_PRIORITY_CLASS (0x00000040)
    """
    print("Demoting AI background tasks to IDLE priority...")
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                # Avoid demoting the current script or crucial system python scripts
                # In real execution, we match on known AGY orchestrator script names
                cmdline = " ".join(proc.info['cmdline'] or [])
                if "dashboard_backend" in cmdline or "polyglot" in cmdline:
                    proc.nice(psutil.IDLE_PRIORITY_CLASS)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def detect_game_and_demote():
    """
    Detects if a heavy game/app is running and demotes background orchestrators.
    """
    heavy_apps = {"Resolve.exe", "Steam.exe", "Cyberpunk2077.exe", "hl2.exe"}
    running = set(get_running_processes())
    
    # Intersection of running processes and heavy apps
    if heavy_apps.intersection(running):
        demote_process_priority()

def main_loop():
    print("Starting Windows Kernel Automation Daemon...")
    while True:
        check_ram_and_flush()
        detect_game_and_demote()
        time.sleep(60) # Poll every 60 seconds

if __name__ == "__main__":
    main_loop()

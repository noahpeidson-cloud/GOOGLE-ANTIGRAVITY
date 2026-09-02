import os
import time
import subprocess
import glob

TARGET_DIR = r"g:\My Drive\GOOGLE ANTIGRAVITY\unified_ops_hub\ml_agent\optimization_loop"
REPORT_PATH = r"C:\Users\noahp\.gemini\antigravity\brain\5ba0016f-8b31-4dd8-afeb-56830004e3da\Validation_Report.md"

def audit_target():
    report_lines = ["# Validation Report: Omniscient Auditor\n", "## Live Audit of Agent ML Optimization Loop\n"]
    
    if not os.path.exists(TARGET_DIR):
        report_lines.append(f"**CRITICAL FAILURE:** Target directory `{TARGET_DIR}` does not exist. The other agent hallucinated the deployment.\n")
    else:
        report_lines.append(f"**Target Directory:** Found.\n")
        
        # Check files
        files = glob.glob(os.path.join(TARGET_DIR, "*.py"))
        report_lines.append(f"**Python Files Found:** {len(files)}\n")
        for f in files:
            report_lines.append(f"- `{os.path.basename(f)}`\n")
            
        # Run static analysis (grep for common issues or run flake8 if available)
        try:
            # Let's just do a basic syntax check on all python files
            syntax_errors = []
            for f in files:
                result = subprocess.run(["python", "-m", "py_compile", f], capture_output=True, text=True)
                if result.returncode != 0:
                    syntax_errors.append(f"Syntax Error in {os.path.basename(f)}: {result.stderr}")
            
            if syntax_errors:
                report_lines.append("\n**CRITICAL FAILURE (Static Analysis):**\n")
                for err in syntax_errors:
                    report_lines.append(f"- {err}\n")
            else:
                report_lines.append("\n**Static Analysis:** All Python files passed basic compilation.\n")
                
        except Exception as e:
            report_lines.append(f"\n**Error during analysis:** {str(e)}\n")

    report_lines.append(f"\n*Last updated: {time.ctime()}*\n")
    
    with open(REPORT_PATH, "w") as f:
        f.writelines(report_lines)

if __name__ == "__main__":
    # Run once immediately, then loop
    audit_target()
    while True:
        time.sleep(10)
        audit_target()

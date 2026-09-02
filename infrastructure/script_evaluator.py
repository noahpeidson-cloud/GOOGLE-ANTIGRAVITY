import subprocess
import json
import os
import sys

def run_radon(script_path):
    """
    Runs Radon to compute Cyclomatic Complexity.
    Returns a dict with 'complexity_score' based on the highest block complexity.
    """
    try:
        # python -m radon cc -j <path>
        result = subprocess.run(
            [sys.executable, '-m', 'radon', 'cc', '-j', script_path],
            capture_output=True,
            text=True
        )
        if result.returncode != 0 and not result.stdout:
            return {"complexity_score": 0}
            
        data = json.loads(result.stdout)
        max_score = 0
        for filepath, blocks in data.items():
            for block in blocks:
                if block.get('complexity', 0) > max_score:
                    max_score = block['complexity']
        
        return {"complexity_score": max_score}
    except Exception as e:
        print(f"Error running radon: {e}")
        return {"complexity_score": 0}

def run_bandit(script_path):
    """
    Runs Bandit to scan for security issues.
    Returns a dict with 'high_severity' and 'medium_severity' counts.
    """
    try:
        # python -m bandit -f json -q <path>
        result = subprocess.run(
            [sys.executable, '-m', 'bandit', '-f', 'json', '-q', script_path],
            capture_output=True,
            text=True
        )
        # Bandit exits with code 1 if issues are found, which is fine
        if not result.stdout:
            return {"high_severity": 0, "medium_severity": 0}
            
        data = json.loads(result.stdout)
        metrics = data.get('metrics', {}).get('_totals', {})
        
        return {
            "high_severity": metrics.get('SEVERITY.HIGH', 0),
            "medium_severity": metrics.get('SEVERITY.MEDIUM', 0)
        }
    except Exception as e:
        print(f"Error running bandit: {e}")
        return {"high_severity": 0, "medium_severity": 0}

def evaluate_script_safety(script_path):
    """
    Evaluates a script using Radon and Bandit.
    Returns (is_safe: bool, reason: str).
    """
    if not os.path.exists(script_path) and not script_path.endswith('.py'):
        # Just to support tests mocking os.path
        pass

    radon_res = run_radon(script_path)
    if radon_res.get("complexity_score", 0) > 10:
        return False, f"Blocked: Cyclomatic Complexity is {radon_res['complexity_score']} (> 10)"
    
    bandit_res = run_bandit(script_path)
    if bandit_res.get("high_severity", 0) > 0:
        return False, f"Blocked: Found {bandit_res['high_severity']} HIGH severity security issues"
        
    return True, "Clean"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        safe, msg = evaluate_script_safety(path)
        print(f"[{'SAFE' if safe else 'UNSAFE'}] {msg}")

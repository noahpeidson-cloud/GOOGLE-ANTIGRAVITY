import sys
import re

def validate_tdad_assertions(script_path):
    """
    Validates that a proposed script contains 'Loud Assertions' (TDAD protocol)
    before it is allowed to execute. 
    Enforces R2: The Zero-Discretion Mandate.
    """
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for deterministic assertions or testing frameworks
        has_assert = 'assert ' in content
        has_pytest = 'pytest' in content or 'unittest' in content
        
        if not (has_assert or has_pytest):
            print(f"TDAD VIOLATION: The script {script_path} lacks deterministic test assertions.", file=sys.stderr)
            print("R2 The Zero-Discretion Mandate dictates that no implementation code may run without tests.", file=sys.stderr)
            sys.exit(1)
            
        print(f"TDAD Validation Passed for {script_path}. Script contains Loud Assertions.")
        sys.exit(0)
        
    except FileNotFoundError:
        print(f"Error: Target script {script_path} not found.", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python tdad_validator.py <path_to_script>", file=sys.stderr)
        sys.exit(1)
        
    target = sys.argv[1]
    validate_tdad_assertions(target)

import os
from pathlib import Path

def validate_path(target_path: str | Path) -> None:
    """
    Validates that the target path does not reside on the C: drive.
    Enforces the 'D: Drive Sovereignty' rule (Rule R-STORE-01).
    """
    resolved_path = Path(target_path).resolve()
    
    # Check if the drive is C:
    if resolved_path.drive.upper() == 'C:':
        raise PermissionError(
            f"Rule R-STORE-01 Violation (D: Drive Sovereignty): "
            f"Writing to the C: drive is strictly prohibited. "
            f"Attempted path: {resolved_path}"
        )

if __name__ == "__main__":
    print("Testing C: Drive Ingress Guardrail...")
    
    # Test 1: Valid D: drive path
    d_path = Path(r"D:\some\safe\path.txt")
    validate_path(d_path)
    print("[PASS] D: drive path passed successfully.")
    
    # Test 2: Invalid C: drive path
    c_path = Path(r"C:\some\forbidden\path.txt")
    
    try:
        validate_path(c_path)
        # If it reaches here, the guardrail failed
        assert False, "Guardrail failed to block C: drive path!"
    except PermissionError as e:
        assert "Rule R-STORE-01 Violation" in str(e)
        print(f"[PASS] C: drive path successfully intercepted.")
        print(f"  Intercepted Message: {e}")
        
    print("All guardrail tests passed.")

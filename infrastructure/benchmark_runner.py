import time

def measure_time_to_first_token(func, timeout_seconds=10):
    """
    Measures the execution time of a given function (simulating TTFT).
    If it exceeds the timeout, returns (False, time_taken) indicating a need for a fallback.
    Otherwise returns (True, time_taken).
    """
    start_time = time.time()
    try:
        # Execute the function (this could be an LLM generation call)
        func()
    except Exception as e:
        print(f"Error during execution: {e}")
        end_time = time.time()
        return False, (end_time - start_time)
        
    end_time = time.time()
    time_taken = end_time - start_time
    
    if time_taken > timeout_seconds:
        print(f"Timeout Exceeded! Took {time_taken:.2f}s (Limit: {timeout_seconds}s). Triggering Fallback.")
        return False, time_taken
        
    print(f"Execution passed in {time_taken:.2f}s.")
    return True, time_taken

def auto_fallback_example(primary_func, fallback_func, timeout_seconds=10):
    """
    Executes primary_func. If it times out or fails, triggers fallback_func.
    """
    success, time_taken = measure_time_to_first_token(primary_func, timeout_seconds)
    if not success:
        print("Switching to a lower-tier, faster fallback model/function...")
        # Execute fallback
        fallback_func()
    
if __name__ == "__main__":
    # Example usage
    def heavy_task():
        time.sleep(2)
        
    def fast_task():
        time.sleep(0.5)
        
    auto_fallback_example(heavy_task, fast_task, timeout_seconds=1)

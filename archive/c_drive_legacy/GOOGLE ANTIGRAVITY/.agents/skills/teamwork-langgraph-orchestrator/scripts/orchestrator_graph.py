import sys
import subprocess

class LangGraphOrchestrator:
    def __init__(self):
        # We enforce the correct models per the R23 Grounded Model fact-check
        self.orchestrator_model = "claude-fable-5"
        self.worker_model = "gemini-3.7-flash"
        self.red_team_model = "gemini-3.1-pro"
        
        self.state_file = "langgraph_state.md"
        
    def write_state(self, content):
        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write(content)
            
    def run_worker_node(self, task):
        self.write_state(f"# LangGraph State\n\n- [ ] Orchestrator Planning\n- [/] Worker Executing: {task}\n- [ ] Red Team Validation")
        print(f"[{self.worker_model}] Executing task: {task}...")
        # Simulate worker creating a script
        script_code = "print('Hello from the worker node!')\n"
        with open("temp_worker_output.py", "w") as f:
            f.write(script_code)
        return "temp_worker_output.py"

    def run_red_team_node(self, script_path):
        self.write_state(f"# LangGraph State\n\n- [x] Orchestrator Planning\n- [x] Worker Executing\n- [/] Red Team Validation: Executing {script_path} in subprocess")
        print(f"[{self.red_team_model}] Adversarially testing {script_path}...")
        
        try:
            result = subprocess.run([sys.executable, script_path], capture_output=True, text=True, check=True)
            print(f"[{self.red_team_model}] Execution successful. Output: {result.stdout.strip()}")
            return True, "No errors found."
        except subprocess.CalledProcessError as e:
            print(f"[{self.red_team_model}] Execution FAILED. Stderr: {e.stderr.strip()}")
            return False, e.stderr

    def execute_dag(self, prompt):
        print(f"[{self.orchestrator_model}] Orchestrator received prompt: {prompt}")
        self.write_state(f"# LangGraph State\n\n- [/] Orchestrator Planning: {prompt}\n- [ ] Worker Executing\n- [ ] Red Team Validation")
        
        # Simulating DAG loop
        script = self.run_worker_node(prompt)
        
        success, feedback = self.run_red_team_node(script)
        if success:
            self.write_state(f"# LangGraph State\n\n- [x] Orchestrator Planning\n- [x] Worker Executing\n- [x] Red Team Validation (PASSED)")
            print(f"[{self.orchestrator_model}] DAG Complete. Task verified.")
        else:
            self.write_state(f"# LangGraph State\n\n- [x] Orchestrator Planning\n- [x] Worker Executing\n- [ ] Red Team Validation (FAILED) -> Routing back to Worker")
            print(f"[{self.orchestrator_model}] Validation failed. Routing back to Worker node...")
            
if __name__ == "__main__":
    dag = LangGraphOrchestrator()
    dag.execute_dag("Build a hello world script")

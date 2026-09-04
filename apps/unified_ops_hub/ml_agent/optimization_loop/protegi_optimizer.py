from google.genai import Client
import pathlib

class ProtegiOptimizer:
    def __init__(self):
        self.client = Client()
        self.model = "gemini-3.1-pro-preview"

    def compute_textual_gradient(self, system_prompt: str, failed_traces: list) -> str:
        critic_prompt = f"""
        You are a ProTeGi System Critic. Analyze these failed agent traces where the agent spawned and sat IDLE, causing context bloat without executing any action.
        Current System Prompt: {system_prompt}
        Failed Traces: {failed_traces}
        
        Generate a concise 'Textual Gradient' (a directional feedback instruction) explaining EXACTLY why the prompt caused the agent to idle, and what behavioral rule must be added.
        """
        res = self.client.models.generate_content(model=self.model, contents=critic_prompt)
        return res.text

    def apply_gradient_descent(self, system_prompt: str, gradient: str) -> str:
        mutate_prompt = f"""
        Apply the following Textual Gradient to optimize the System Prompt.
        Gradient: {gradient}
        Current Prompt: {system_prompt}
        
        Output ONLY the newly optimized System Prompt. Do not output markdown code blocks unless it's part of the actual system prompt.
        """
        res = self.client.models.generate_content(model=self.model, contents=mutate_prompt)
        return res.text
        
    def patch_skill_file(self, target_skill_path: str, new_prompt: str):
        path = pathlib.Path(target_skill_path)
        path.write_text(new_prompt, encoding="utf-8")

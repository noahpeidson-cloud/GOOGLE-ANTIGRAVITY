import time
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

# R26: Background Daemon Auth Guardrail
load_dotenv()
if "GEMINI_API_KEY" not in os.environ:
    raise ValueError("GEMINI_API_KEY not found in .env file")

client = genai.Client()

def refine_prompt_with_collective(user_idea, baseline_metrics=None):
    """
    Simulates the Google Flow 'Elite Designer Collective'.
    Uses Gemini Pro to act as a roundtable of 5 designers to refine the prompt,
    ensuring 0% stage distortion.
    """
    system_instruction = (
        "You are the moderator of the Elite Designer Collective. "
        "Your goal is to produce the world's best graphic design and video editing prompts "
        "through rigorous simulated discussion. You must respect the baseline metrics provided "
        "and ensure zero morphing or distortion of the original stage."
    )
    
    prompt = f"""
    User Idea: "{user_idea}"
    Baseline Metrics Constraints: {baseline_metrics or "None"}
    
    Act as a panel of 5 elite graphic designers (100 years combined exp) discussing this idea. 
    1. THE VISIONARY: Mood and concept.
    2. THE COMPOSITOR: Layout and hierarchy. Ensure zero distortion of structural elements.
    3. THE COLORIST: Palette and lighting. Prevent overexposure.
    4. THE TECHNICAL LEAD: Texture and detail.
    5. THE CRITIC: Final polish.

    Output MUST follow this format exactly:
    [1] (text from Visionary)
    [2] (text from Compositor)
    [3] (text from Colorist)
    [4] (text from Technical Lead)
    [5] (text from Critic)
    ---FINAL PROMPT---
    (The ultimate, detailed, high-level AI generation prompt)
    """
    
    # R27: Google GenAI 503 Retry Mandate and 429 Rate Limiting
    # ZERO-FRICTION MODEL FALLBACK (No Stalls)
    fallback_models = [
        'gemini-3.7-flash', 
        'gemini-3.6-flash',
        'gemini-3.5-flash',
        'gemini-3.5-flash-lite',
        'gemini-2.5-pro'
    ]
    
    for model_id in fallback_models:
        try:
            interaction = client.interactions.create(
                model=model_id,
                input=prompt,
                system_instruction=system_instruction
            )
            
            output = interaction.output_text
            if output and "---FINAL PROMPT---" in output:
                final_prompt = output.split("---FINAL PROMPT---")[-1].strip()
                return output, final_prompt
            else:
                return output or "", user_idea + " (Elite professional design, ultra high definition)"
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "503" in error_str or "500" in error_str:
                print(f"Designer Collective API Limit Hit on {model_id}. Immediately falling back...")
                continue # Try the next model immediately
            else:
                print(f"Designer Collective Failed on {model_id}: {e}")
                return "", user_idea
                
    print("All fallback models exhausted for Designer Collective.")
    return "", user_idea

if __name__ == "__main__":
    discussion, final = refine_prompt_with_collective("Add lasers to the stage but keep it layered")
    print("Discussion:\n", discussion)
    print("Final Prompt:\n", final)

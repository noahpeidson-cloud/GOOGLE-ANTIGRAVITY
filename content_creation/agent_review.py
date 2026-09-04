import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(r"d:\GOOGLE ANTIGRAVITY\.env")

def run_agent_review():
    client = genai.Client()
    
    pipeline_context = """
    Pipeline Architecture:
    S26 Ultra (Edge Capture) -> Quick Share -> 01_RAW -> proxy_generator.py (transcodes to 720p 02_PROXIES and writes to media_manifest.sqlite) -> Web Dashboard UI (AWAITING_REVIEW)
    User types prompt -> Gemini 3.1 Pro -> dashboard_backend.py -> edit_controller.py -> davinci_integration.py -> DaVinci Resolve (Scale to Fill 9:16) -> RenderQueue (H.264 Master).
    """

    # Agent 1: Technical & Systems Architect
    sys_instruct_1 = "You are a brutal Technical Architect. Review the pipeline context and find critical systemic flaws (e.g., locking, concurrency, transport layer instability, hardware limits)."
    prompt_1 = f"Review this pipeline: {pipeline_context}"
    
    response_1 = client.models.generate_content(
        model="gemini-3.1-pro-preview",
        contents=prompt_1,
        config=types.GenerateContentConfig(system_instruction=sys_instruct_1)
    )

    # Agent 2: Content Strategy Director
    sys_instruct_2 = "You are a Content Strategy Director for EDM/Music Shorts. Review the 'Council of Creation' design (Visionary, Compositor, Colorist, Technical Lead, Critic). Tell me why it fails for TikTok/Reels EDM content, and propose a new 5-persona council."
    prompt_2 = "Review the Council of Creation for short-form EDM content."
    
    response_2 = client.models.generate_content(
        model="gemini-3.1-pro-preview",
        contents=prompt_2,
        config=types.GenerateContentConfig(system_instruction=sys_instruct_2)
    )

    with open("agent_review_output.md", "w", encoding="utf-8") as f:
        f.write("# Agent 1: Technical Review\n\n")
        f.write(response_1.text + "\n\n")
        f.write("# Agent 2: Council Review\n\n")
        f.write(response_2.text + "\n\n")

if __name__ == "__main__":
    run_agent_review()

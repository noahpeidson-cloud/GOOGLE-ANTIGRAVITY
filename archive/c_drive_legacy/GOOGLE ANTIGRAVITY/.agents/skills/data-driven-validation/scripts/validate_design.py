import argparse
import sys
import time
from google import genai
from google.genai.errors import APIError
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def research(topic, output_file):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[!] GEMINI_API_KEY not found in environment.", file=sys.stderr)
        sys.exit(1)
        
    client = genai.Client(api_key=api_key)
    
    print(f"[*] Dispatching Deep Research Agent for topic: '{topic}'")
    try:
        with open("G:/My Drive/GOOGLE ANTIGRAVITY/GEMINI.md", "r", encoding="utf-8") as f:
            workspace_context = f.read()
    except Exception as e:
        workspace_context = "Workspace context not found."

    try:
        interaction = client.interactions.create(
            agent="deep-research-max-preview-04-2026",
            input=(
                f"Perform an exhaustive, data-driven research analysis on the following proposed design or idea: '{topic}'.\n\n"
                f"CRITICAL BOUNDARIES: You must evaluate this proposal strictly through the lens of the following workspace rules and toolchains. Do not recommend architectures that violate these constraints:\n"
                f"--- WORKSPACE CONTEXT ---\n{workspace_context}\n-------------------------\n\n"
                "Your goal is to objectively VALIDATE, ENHANCE, or REJECT this proposal using concrete industry data, benchmarks, and citations.\n"
                "Structure the final report clearly with headers for Validation/Rejection, Data Evidence, and Proposed Enhancements."
            ),
            background=True
        )
    except APIError as e:
        print(f"[!] API Error while starting interaction: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Interaction created with ID: {interaction.id}. Polling for completion...")

    while True:
        try:
            interaction = client.interactions.get(interaction.id)
            status = getattr(interaction, 'status', 'unknown')
            
            if status == "completed":
                print(f"\n[*] Research complete! Writing to {output_file}")
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(interaction.output_text)
                print(f"[*] Success. File saved.")
                break
            elif status in ["failed", "cancelled"]:
                err_msg = getattr(interaction, 'error', 'Unknown Error')
                print(f"\n[!] Research {status}: {err_msg}", file=sys.stderr)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"# Research {status.capitalize()}\n\nAn error occurred during deep research: {err_msg}")
                sys.exit(1)
            else:
                # Print a dot to show progress
                print(".", end="", flush=True)
                time.sleep(10)
        except APIError as e:
            # Handle rate limits or temporary network issues during polling
            if e.code == 429:
                print("\n[!] Rate limited during polling. Backing off for 30s...", file=sys.stderr)
                time.sleep(30)
            else:
                print(f"\n[!] API Error during polling: {e}", file=sys.stderr)
                time.sleep(10) # backoff and try again

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data-Driven Validation Research Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    res_parser = subparsers.add_parser("research")
    res_parser.add_argument("--topic", required=True, help="The design, idea, or problem to research.")
    res_parser.add_argument("--output", required=True, help="Output markdown file.")
    
    args = parser.parse_args()
    
    if args.command == "research":
        research(args.topic, args.output)

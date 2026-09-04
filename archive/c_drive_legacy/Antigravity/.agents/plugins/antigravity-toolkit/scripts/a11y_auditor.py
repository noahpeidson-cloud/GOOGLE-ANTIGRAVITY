import asyncio
from google.antigravity import Agent, LocalAgentConfig, types

async def run_a11y_audit(target_url: str):
    """
    Runs an accessibility and Core Web Vitals audit using Lighthouse via Chrome DevTools MCP.
    """
    
    chrome_server = types.McpStdioServer(
        name="chrome-devtools",
        command="npx",
        args=["-y", "chrome-devtools-mcp@latest"]
    )
    
    config = LocalAgentConfig(
        mcp_servers=[chrome_server],
        system_instruction=(
            "You are an automated Quality Assurance auditor. Your only job is to run a Lighthouse audit "
            "on the provided URL, focusing specifically on accessibility (a11y) and performance (CWV). "
            "Return a structured JSON summary of the scores and top 3 critical issues."
        )
    )
    
    async with Agent(config) as agent:
        print(f"Starting Lighthouse audit for: {target_url}")
        prompt = f"Run a lighthouse_audit on '{target_url}' for accessibility and performance. Provide the JSON summary."
        response = await agent.chat(prompt)
        
        return await response.text()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python a11y_auditor.py <target_url>")
        sys.exit(1)
        
    url = sys.argv[1]
    result = asyncio.run(run_a11y_audit(url))
    print("\n--- Audit Result ---")
    print(result)

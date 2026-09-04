import asyncio
from google.antigravity import Agent, LocalAgentConfig, types

async def run_browser_task(objective: str, start_url: str = "about:blank"):
    """
    Spins up an autonomous subagent with Chrome DevTools MCP capabilities
    to execute a specific browser objective.
    """
    
    # Configure the Chrome DevTools MCP server
    chrome_server = types.McpStdioServer(
        name="chrome-devtools",
        command="npx",
        args=["-y", "chrome-devtools-mcp@latest"]
    )
    
    # Configure the agent
    config = LocalAgentConfig(
        mcp_servers=[chrome_server],
        system_instruction=(
            "You are an autonomous Browser Agent. You use Chrome DevTools MCP to interact with web pages. "
            "Workflow: 1. Navigate to the page. 2. Wait for content. 3. Take a snapshot to get element UIDs. 4. Interact using UIDs. "
            "Complete the objective and return a concise summary of the result."
        )
    )
    
    async with Agent(config) as agent:
        print(f"Starting browser task: {objective}")
        print(f"Initial URL: {start_url}")
        
        # Guide the agent to start at the URL and accomplish the objective
        prompt = f"Navigate to '{start_url}' and then accomplish this objective: {objective}"
        response = await agent.chat(prompt)
        
        return await response.text()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python browser_agent.py <objective> [start_url]")
        sys.exit(1)
        
    objective = sys.argv[1]
    url = sys.argv[2] if len(sys.argv) > 2 else "about:blank"
    
    result = asyncio.run(run_browser_task(objective, url))
    print("\n--- Task Result ---")
    print(result)

# Browser Automation Master Agent

An enterprise-grade, resilient browser automation orchestrator built with the **Google Antigravity SDK** (`google-antigravity`) and the **Chrome DevTools MCP Server** (`chrome-devtools-mcp`).

---

## 🌟 Architecture Overview

The **Browser Automation Master** coordinates multi-step web automation workflows using specialized autonomous subagents, dynamic lifecycle hooks, and stdio MCP process management.

```
                  ┌─────────────────────────────────────┐
                  │            User / Caller            │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │    BrowserMaster (Master Agent)     │
                  │       (LocalAgentConfig)            │
                  └──────────┬──────────────────────┬───┘
                             │                      │
        ┌────────────────────┴────────┐             │
        ▼                             ▼             │
┌──────────────────┐        ┌──────────────────┐    │
│  browser_worker  │        │  dom_extractor   │    │
│  (Navigation &   │        │  (JS Evaluation  │    │
│   Interaction)   │        │   & DOM Scraping)│    │
└─────────┬────────┘        └─────────┬────────┘    │
          │                           │             │
          └─────────────┬─────────────┘             │
                        ▼                           ▼
       ┌─────────────────────────────────┐   ┌─────────────────────────────┐
       │   Chrome DevTools MCP Server    │   │  Self-Healing Middleware    │
       │   (chrome-devtools-mcp stdio)   │   │  (OnToolErrorHook: catches  │
       │   - navigate_page  - wait_for   │   │   stale UIDs and mandates   │
       │   - take_snapshot  - click/fill │   │   take_snapshot refresh)    │
       │   - evaluate_script             │   └─────────────────────────────┘
       └─────────────────────────────────┘
```

### Core Design Principles
1. **Resilient Interaction Lifecycle**: Enforces the strict sequence:  
   `navigate_page` ➔ `wait_for` ➔ `take_snapshot` ➔ `interact` (`click` / `fill` / `evaluate_script`).
2. **Self-Healing Error Recovery**: Uses `ElementNotFoundRecoveryHook` (`hooks.OnToolErrorHook`) to intercept missing element or stale UID errors and guide the agent to capture a fresh snapshot.
3. **Cross-Platform MCP Execution**: Automatically detects and uses `npx.cmd` on Windows and `npx` on POSIX systems to bypass PowerShell script execution restrictions.
4. **Specialized Subagent Separation**:
   - `browser_worker`: Handles browser navigation, waiting, clicking, and form filling.
   - `dom_extractor`: Handles high-precision DOM text extraction, scraping, and metadata synthesis.

---

## 📁 Code Layout

```
browser_automation_master/
├── requirements.txt                   # Project dependencies
├── .env.example                       # Environment configuration template
├── README.md                          # Architecture and usage documentation
├── test_automation.py                 # Automated verification test harness
└── browser_master/
    ├── __init__.py                    # Public package exports
    ├── agent.py                       # Master Agent orchestrator and BrowserMaster class
    ├── mcp_config.py                  # Chrome DevTools MCP transport & tool allowlists
    ├── middleware.py                  # Resilient error recovery and audit hooks
    └── subagents/
        ├── __init__.py                # Subagent registry
        ├── browser_worker.py          # Web interaction worker configuration
        └── extractor.py               # DOM & data extraction worker configuration
```

---

## 🚀 Setup & Installation

### Prerequisites
- **Python**: 3.10+ (Verified on Python 3.13)
- **Node.js**: 18+ (Required for running `npx -y chrome-devtools-mcp@latest`)
- **Google Chrome** / Chromium installed

### Installation
1. Clone or navigate to the repository directory:
   ```bash
   cd C:\Users\noahp\teamwork_projects\browser_automation_master
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure your environment:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set your `GEMINI_API_KEY`.

---

## 💻 Usage

### Python Async API

```python
import asyncio
import os
from dotenv import load_dotenv
from browser_master import BrowserMaster

load_dotenv()

async def main():
    # Initialize the master agent in headless mode
    master = BrowserMaster(headless=True)
    
    # Execute an end-to-end browser automation task
    prompt = (
        "Navigate to https://example.com, wait for the page to load, "
        "take a snapshot, and extract the main <h1> heading text."
    )
    
    result = await master.execute_task(prompt)
    print("Master Agent Response:\n", result)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🧪 Verification & Testing

Execute the automated test harness:

```bash
python test_automation.py
```

The test script will:
1. Verify MCP configuration and tool bindings.
2. Test the resilient error recovery hook with simulated DOM errors.
3. Validate agent and subagent configuration hierarchies.
4. If a `GEMINI_API_KEY` is present, execute a live headless session to `https://example.com`, extract `<h1>Example Domain</h1>`, and verify programmatically.

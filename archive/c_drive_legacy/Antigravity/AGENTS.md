# Antigravity Agent Ecosystem Rules

<RULE[autonomous_skill_generation]>
Whenever you (the agent) create a new reusable script, background subagent (e.g., using the Antigravity SDK), or any generalized utility meant to augment the user's toolset:
1. You MUST immediately and proactively create a corresponding `SKILL.md` file in the `.agents/skills/` directory (or appropriate plugin directory).
2. The skill documentation must clearly explain the script's purpose, when it should be triggered, and provide the exact command syntax to execute it.
3. Do not wait for the user to ask you to do this. Always ensure your cross-session capabilities are documented so future agent instances can discover and leverage them.
</RULE[autonomous_skill_generation]>

<RULE[windows_json_escaping]>
# Windows JSON Escaping & Fallback Editing Protocol

1. **The Windows JSON Escaped Quotes Trap:** 
   When generating or debugging JSON config files on Windows (such as `mcp_config.json`, `hooks.json`, or `manifest.json`), agents MUST NEVER use literal escaped double quotes (`\"`) inside string values for file paths or package names.
   * **BAD:** `"command": "node \\"C:\\path\\to\\script.js\\""`
   * **BAD:** `"package": "\"@toolbox-sdk/spark\""`
   * **GOOD:** `"command": "node C:\\path\\to\\script.js"`
   * **GOOD:** `"package": "@toolbox-sdk/spark"`
   
   Using nested literal quotes will cause Node.js and MCP processes to fatally crash with `EINVALIDPACKAGENAME` or `MODULE_NOT_FOUND` resolution errors.

2. **JSON Editing Protocol (Blocked Tools):** 
   When an agent needs to fix a broken JSON configuration file but their file-editing tools are blocked (e.g., due to a broken telemetry hook intercepting the tool execution), they MUST NOT generate fragile PowerShell regex scripts (e.g., using `-replace`) to blindly edit the file.
   Instead, the agent must output the exact, corrected JSON code block in standard markdown format within their chat response, instructing the user to manually copy and paste the fix into their configuration file.
</RULE[windows_json_escaping]>

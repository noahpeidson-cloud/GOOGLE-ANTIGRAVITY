---
name: mcp-error-repair
description: >-
  Diagnose and repair Antigravity IDE MCP startup errors including hooks.json schema/BOM
  failures, missing MCP binaries/bundles, broken credential paths, and missing config files.
  Trigger phrases: "MCP errors", "fix MCP", "hooks failed", "MCP not loading", "connection closed EOF".
---

# MCP Error Repair Runbook

## Phase 0 - Triage

```powershell
$log = Get-ChildItem "C:\Users\noahp\.gemini\antigravity\log\cli-*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-Content $log.FullName | Select-String "ERROR|WARN|Failed|hooks|MCP|Cannot find" | Select-Object -Last 40
```

| Log Pattern | Root Cause | Fix Phase |
|---|---|---|
| invalid character ufeff | UTF-8 BOM in hooks.json | Phase 1 |
| cannot unmarshal array into Go struct field .hooks | Wrong hooks.json schema | Phase 1 |
| MODULE_NOT_FOUND: mcp_proxy_bundle.js | datacloud extension not installed | Phase 2 |
| unable to read config file at tools.yaml | mcp-toolbox missing cwd/yaml | Phase 3 |
| GOOGLE_DRIVE_OAUTH_CREDENTIALS path error | Wrong gdrive credential path | Phase 4 |
| CORTEX_MEMORY_TRIGGER_UNSPECIFIED | Internal AGY bug | Ignore |

## Phase 1 - Fix hooks.json

Correct schema (keyed-object, not array):
- Stop/PreInvocation/PostInvocation: flat list [{type, command, timeout}]
- PostToolUse/PreToolUse: grouped [{matcher, hooks:[{type, command}]}]
- Never use {"hooks": [...]} top-level array
- Use write_to_file to rewrite (never PowerShell echo/cat - causes BOM)

## Phase 2 - Fix datacloud MCP (DO NOT install extension)

```powershell
$vsixUrl = "https://googlecloudtools.gallery.vsassets.io/_apis/public/gallery/publisher/googlecloudtools/extension/datacloud/0.10.0/assetbyname/Microsoft.VisualStudio.Services.VSIXPackage"
Invoke-WebRequest -Uri $vsixUrl -OutFile "$env:TEMP\datacloud.vsix"
Copy-Item "$env:TEMP\datacloud.vsix" "$env:TEMP\datacloud.zip"
Expand-Archive -Path "$env:TEMP\datacloud.zip" -DestinationPath "$env:TEMP\datacloud_extract" -Force
$targetDir = "C:\Users\noahp\.antigravity-ide\extensions\googlecloudtools.datacloud-0.10.0-universal\mcp_servers\cli"
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
Copy-Item "$env:TEMP\datacloud_extract\extension\mcp_servers\cli\mcp_proxy_bundle.js" "$targetDir\mcp_proxy_bundle.js" -Force
```

## Phase 3 - Fix mcp-toolbox-for-databases

Add cwd to mcp_config.json pointing to dir containing tools.yaml.
GCP project: local-catfish-470915-r8
Config dir: C:\Users\noahp\.gemini\config\mcp-toolbox\tools.yaml

## Phase 4 - Fix GDrive OAuth Path

Correct env var in mcp_config.json:
GOOGLE_DRIVE_OAUTH_CREDENTIALS = C:\Users\noahp\.config\google-drive-mcp\gcp-oauth.keys.json
(NOT credentials.json in workspace root)

If gcp-oauth.keys.json missing: npx -y @piotr-agier/google-drive-mcp auth

## Natural Language Invocations
- "Fix my MCP errors"
- "hooks.json is failing to parse"
- "data-agent-kit MODULE_NOT_FOUND"
- "mcp-toolbox cannot find tools.yaml"
- "gdrive MCP not authenticating"
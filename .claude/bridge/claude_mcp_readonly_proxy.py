#!/usr/bin/env python3
"""Read-only MCP proxy in front of `claude mcp serve`.

WHY THIS EXISTS
---------------
The Antigravity Hub (C:\\Users\\noahp\\AppData\\Local\\Programs\\antigravity) has no VS Code
extension host, so Claude Code's /ide integration cannot reach it. The Hub's actual
extension surface is MCP, and `claude mcp serve` turns Claude Code into an MCP server --
which is a working bridge in the direction that matters.

The problem is that the bridge is unscoped. Measured on 2026-09-03 with Claude Code
2.1.260:

  * `claude mcp serve` exposes 29 tools, including Bash, PowerShell, Write, Edit,
    NotebookEdit, Agent, Workflow, CronCreate and SendMessage.
  * `mcp serve` REJECTS --allowedTools and --disallowedTools ("unknown option"); those
    are top-level `claude` flags, not subcommand flags.
  * Permission rules DO NOT contain it. Pointing the served instance at an isolated
    CLAUDE_CONFIG_DIR whose settings.json carried

        "permissions": {"deny": ["Bash", "PowerShell", "Write", "Edit", ...]}

    still executed a Bash call arriving over MCP:

        tools/call Bash {"command": "echo SCOPE_TEST_EXECUTED"}
        -> {"stdout": "SCOPE_TEST_EXECUTED", ...}   isError: absent

    The config dir WAS read (the tool list dropped 29 -> 25), but Bash stayed listed and
    stayed executable. `mcp serve` treats its MCP client as the authority and does not
    prompt, because there is no interactive surface to prompt on.

So an unproxied bridge hands the Gemini lane full Bash and PowerShell -- which is git
write access, and defeats R38, R39 and R40 in one step. This proxy is the containment:
it is a hard allowlist that the served instance cannot override, because filtering
happens here rather than there.

WHAT IT DOES
------------
Speaks stdio MCP to the Hub, spawns `claude mcp serve` as a child, and:

  * filters tools/list down to ALLOWED
  * refuses tools/call for anything outside ALLOWED, with an MCP error, without
    forwarding the call
  * passes initialize, notifications and everything else straight through

Denial is by allowlist, not blocklist: a tool added by a future Claude Code version is
refused by default rather than silently exposed.

USAGE
-----
    python .claude/bridge/claude_mcp_readonly_proxy.py

Override the allowlist with CLAUDE_BRIDGE_ALLOW (comma-separated). Adding a mutating
tool there re-opens exactly the hole described above -- there is no safe value of
CLAUDE_BRIDGE_ALLOW that contains "Bash" or "PowerShell".

Set CLAUDE_BRIDGE_LOG to a file path to record every refusal.
"""
import json
import os
import shutil
import subprocess
import sys
import threading

DEFAULT_ALLOW = "Read,Grep,Glob,ListAgents"

# Never allowed, whatever CLAUDE_BRIDGE_ALLOW says. Each of these can mutate the repo,
# execute code, spawn further agents, or reach the network on the caller's behalf.
NEVER = {
    "Bash", "PowerShell", "Write", "Edit", "NotebookEdit", "Agent", "Workflow",
    "Task", "CronCreate", "CronDelete", "ScheduleWakeup", "SendMessage",
    "RemoteTrigger", "Skill", "EnterWorktree", "ExitWorktree", "DesignSync",
    "Artifact", "PushNotification", "Monitor", "TaskStop",
}

allow = {t.strip() for t in os.environ.get("CLAUDE_BRIDGE_ALLOW", DEFAULT_ALLOW).split(",") if t.strip()}
blocked_by_policy = allow & NEVER
allow -= NEVER

LOG_PATH = os.environ.get("CLAUDE_BRIDGE_LOG")


def log(message):
    if not LOG_PATH:
        return
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(message.rstrip() + "\n")
    except OSError:
        pass


if blocked_by_policy:
    log("startup: refused to allow %s -- on the NEVER list" % sorted(blocked_by_policy))

exe = shutil.which("claude")
if not exe:
    candidate = os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.CMD")
    exe = candidate if os.path.exists(candidate) else "claude"

child = subprocess.Popen(
    [exe, "mcp", "serve"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
    encoding="utf-8",
    bufsize=1,
    cwd=os.environ.get("CLAUDE_BRIDGE_CWD") or os.getcwd(),
)

out_lock = threading.Lock()


def emit(obj):
    with out_lock:
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()


def to_child(obj):
    child.stdin.write(json.dumps(obj) + "\n")
    child.stdin.flush()


def from_child():
    """Filter the child's tools/list results on the way back to the Hub."""
    for line in child.stdout:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        result = msg.get("result")
        if isinstance(result, dict) and isinstance(result.get("tools"), list):
            before = len(result["tools"])
            result["tools"] = [t for t in result["tools"] if t.get("name") in allow]
            log("tools/list: %d -> %d (allow=%s)" % (before, len(result["tools"]), sorted(allow)))
        emit(msg)
    if child.poll() is not None:
        sys.exit(child.returncode or 0)


threading.Thread(target=from_child, daemon=True).start()

for raw in sys.stdin:
    raw = raw.strip()
    if not raw.startswith("{"):
        continue
    try:
        req = json.loads(raw)
    except ValueError:
        continue

    if req.get("method") == "tools/call":
        name = (req.get("params") or {}).get("name")
        if name not in allow:
            log("REFUSED tools/call %r" % (name,))
            rid = req.get("id")
            if rid is not None:
                emit({
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {
                        "code": -32601,
                        "message": (
                            "Tool %r is not exposed by this bridge. It forwards only %s. "
                            "Mutating tools are withheld deliberately: this bridge crosses "
                            "an agent lane boundary (R38), and the underlying `claude mcp "
                            "serve` does not enforce permission rules."
                            % (name, sorted(allow))
                        ),
                    },
                })
            continue

    to_child(req)

child.terminate()

# Handoff: MCP Parity Across the Three Agents, and the Hung `antigravity-mcp-experimental` Server

**Status:** PROPOSAL. Nothing in this document has been executed.
**Measured:** 2026-09-03, ~19:20–19:30 MST, on this machine, by the `config-and-measurement` lane.
**Author lane:** config-and-measurement (`.claude/`, `CLAUDE.md`, measurement). This lane took **no git write** and **wrote no file outside this one**.
**Scope note:** `C:\Users\noahp\.gemini\` is the Gemini/Antigravity host configuration and is **outside this repo**. It was read only. Every change proposed against it is handed to its owner, not applied here.

Every claim below is followed by the command that produced it. Claims that were *not* verified say so.

---

## 0. Corrections to the premises this task was issued with

Three statements in the task brief are wrong on disk as of today. Recording them here so the next session does not inherit them.

### 0.1 The `filesystem` MCP server is not broken. It connects in ~1.5 s.

The brief says "this session's own `filesystem` MCP server FAILED to connect with CONNECT_TIMEOUT after 30s today — a server that does not start is not parity." The first half happened; the diagnosis does not hold.

```
$ claude mcp list
GitKraken:  ... - ✔ Connected
filesystem: npx -y @modelcontextprotocol/server-filesystem d:\GOOGLE ANTIGRAVITY - ✔ Connected
```

Hand-timed `initialize` → `result` round trip, spawned exactly as `.mcp.json` declares, three consecutive runs:

```
run HANDSHAKE_MS=1970
run HANDSHAKE_MS=1482
run HANDSHAKE_MS=1225
```

and the first (cold-ish) run: `HANDSHAKE_MS=2521`, stderr `Secure MCP Filesystem Server running on stdio` at 2513 ms.

**So the 30 s CONNECT_TIMEOUT this session saw was a transient startup event, not a configuration defect.** The config is correct and the server is healthy. Do not "fix" `.mcp.json` for this.

What I can say about the transient: at session start this box was running six Antigravity Hub pids, two orphaned `stdio-proxy.mjs` retry loops (see §5), and a cold `npx` resolve, all at once. **I did not reproduce the timeout, so I cannot prove that is the cause — treat the mechanism as unproven and the health as proven.** If it recurs, the durable fix is to stop paying `npx`'s registry-resolution cost on every spawn (pin the package locally), not to change the server.

One real environment note in passing: `npm config get cache` → `D:\AI_Platform\cache\npm`, and `_npx` entries exist there. The npx cache is correctly on `D:` per R-STORE-01. `C:\Users\noahp\AppData\Local\npm-cache\_npx` does **not** exist, which is the correct state.

### 0.2 `~/.claude/ide/` exists now, and its lock file will never satisfy `/ide`

The brief says "`~/.claude/ide/` does not exist yet because the IDE has not been started since the extension was installed." It exists:

```
$ cat C:/Users/noahp/.claude/ide/33008.lock
{"pid":17368,"workspaceFolders":[],"ideName":"Antigravity IDE","transport":"ws","runningInWindows":true,"authToken":"..."}

$ netstat -ano -p tcp | grep :33008
  TCP    127.0.0.1:33008   0.0.0.0:0   LISTENING   37668
```

The port is live and `ideName` is `"Antigravity IDE"` exactly as the brief predicted. **But `workspaceFolders` is `[]`.** Per the brief's own reading of the 2.1.260 bundle, a candidate is accepted only when one of its `workspaceFolders` entries is a separator-bounded prefix of the cwd. An empty array has no entry to match, so this lock can never be accepted for `D:\GOOGLE ANTIGRAVITY` — `/ide` will list it and fail to connect, and `autoConnectIde` will not fire.

That is an IDE-side problem (the extension host activated without a folder open, or before the folder resolved), not a Claude Code problem. **Not my file to fix and not tested further** — flagged here because the next session will otherwise re-derive it. Do **not** hand-author a replacement lock; the brief is right that a stale hand-written lock poisons every future discovery.

### 0.3 GitKraken is not "in a different file" — it is in **three** files

The brief describes `~/.gemini/settings.json` as separately holding GitKraken. True, but incomplete: GitKraken is registered three times. See §2, which explains why that is correct rather than duplicated.

---

## 1. Where MCP configuration actually lives on this machine

Five files matter. One of them is a decoy.

| # | Path | Bytes | Read by | Live? |
|---|---|---|---|---|
| 1 | `C:\Users\noahp\.gemini\config\mcp_config.json` | 3982 | Antigravity Hub / IDE language server | **YES** — 18 servers |
| 2 | `C:\Users\noahp\.gemini\settings.json` | 195 | **Gemini CLI** (`gemini`), not Antigravity | **YES** — 1 server |
| 3 | `C:\Users\noahp\.claude.json` | — | Claude Code, user scope | **YES** — 1 server (`GitKraken`) |
| 4 | `D:\GOOGLE ANTIGRAVITY\.mcp.json` | — | Claude Code, project scope | **YES** — 3 servers, 1 enabled |
| 5 | `C:\Users\noahp\.gemini\antigravity\mcp_config.json` | 22 | **nothing reads it** | **DEAD** — `{"mcpServers": {}}` |

Gating for #4 lives in two places, both agreeing:

```
$ cat "D:/GOOGLE ANTIGRAVITY/.claude/settings.local.json"
{"enabledMcpjsonServers":["filesystem"],"disabledMcpjsonServers":["sqlite-inventory","sqlite-manifest"]}

$ cat "D:/GOOGLE ANTIGRAVITY/.claude/settings.json"   # excerpt
"enabledMcpjsonServers": ["filesystem"]
```

Claude Code's user-scope config (#3) holds **only** GitKraken at top level; the `D:/GOOGLE ANTIGRAVITY` project entry inside it has `mcpServers: {}`, `enabled: []`, `disabled: []` — i.e. the project's servers come from `.mcp.json`, gated by `settings*.json`, and nothing is hiding in `~/.claude.json`.

**File #5 is the decoy and it matters for §5.** It is not merely empty — it is the file the `antigravity-mcp-experimental` VS Code extension writes its own registration into:

```js
// dist/extension.js:58-59
const proxyPath  = path.join(context.extensionPath, 'bin', 'stdio-proxy.mjs');
const configPath = path.join(os.homedir(), '.gemini', 'antigravity', 'mcp_config.json');
// :72
const serverName = "AntigravityMCP";
```

So the extension self-registers under the key `AntigravityMCP` into a file the Hub does not read. The entry that *is* live — key `antigravity-mcp-experimental`, in file #1 — was therefore **added by hand, not by the extension**, and it omits the `--host`/`--port` args the extension would have written. It only works at all because the proxy's built-in defaults (`127.0.0.1:3033`) coincide with the extension's defaults.

---

## 2. Why GitKraken sits in a separate file from everything else

This is worth explaining because it looks like config drift and is not.

GitKraken is registered **once per consuming application**, and the three registrations differ in exactly one flag:

| File | `--host` | `--session` | Extra |
|---|---|---|---|
| `~/.gemini/config/mcp_config.json` | `antigravity` | `kepler` | `options.windowsHide: true` |
| `~/.gemini/settings.json` | `gemini` | `kepler` | — |
| `~/.claude.json` | `claude-cli` | `kepler` | — |

All three invoke the same binary, `C:\Users\noahp\AppData\Local\GitKrakenCLI\gk-alpha.exe mcp` (verified present).

Two things follow.

1. **`~/.gemini/` hosts two different products.** `~/.gemini/settings.json` is the **Gemini CLI's** config; `~/.gemini/config/mcp_config.json` is **Antigravity's** registry. They share a parent directory and share nothing else. The split is by *consuming application*, not by server category — which is why exactly one server (GitKraken, the only one installed for all three hosts) appears in both.
2. **The split is deliberate and should be preserved.** `gk-alpha` tags each MCP session with the host that opened it while pinning all of them to the same workspace session (`kepler`), so GitKraken can attribute an action to Antigravity vs Gemini CLI vs Claude Code while still presenting one shared session. Consolidating these into one file would erase that attribution. **Do not "de-duplicate" GitKraken.**

Caveat: I verified the flag values and the binary's existence. I did **not** verify GitKraken's server-side behaviour of `--host`/`--session`; the attribution reading is inference from the flag names plus the one-file-per-host pattern.

---

## 3. The parity table

Measured from the five files in §1. "Antigravity/Gemini" is file #1 unless the row says otherwise.

| Server | Visible to Claude Code | Visible to Antigravity / Gemini |
|---|---|---|
| `GitKraken` | **YES** (`~/.claude.json`, health-checked ✔ Connected) | **YES** (both Antigravity #1 and Gemini CLI #2) |
| `filesystem` | **YES** (`.mcp.json`, enabled, ✔ Connected) | no |
| `sqlite-inventory` | declared, **DISABLED** | no |
| `sqlite-manifest` | declared, **DISABLED** | no |
| `chrome-devtools-mcp` | **no** | YES |
| `bigquery` | no | YES (`google_credentials`) |
| `alloydb-postgresql` | no | YES (`google_credentials`) |
| `cloud-sql` | no | YES (`google_credentials`) |
| `google-home-developer` | no | YES (`google_credentials`) |
| `cloudrun` | no | YES |
| `firebase-mcp-server` | no | YES |
| `gdrive` | no | YES |
| `dart-mcp-server` | no | YES |
| `mcp-toolbox-for-databases` | no | YES |
| `datacloud_serverless-spark_toolbox` | no | YES |
| `notebooks` | no | YES (datacloud ext proxy) |
| `visualization` | no | YES (datacloud ext proxy) |
| `data-agent-kit` | no | YES (datacloud ext proxy) |
| `gemini-notebook` | no | YES |
| `windows-kernel-optimizer` | no | declared, **BROKEN** (§4.4) |
| `antigravity-mcp-experimental` | no | declared, **HANGS FOREVER** (§5) |
| `AntigravityMCP` | no | **no** — written to dead file #5, read by nothing |

Totals: Claude Code sees **2 working servers**. Antigravity declares **18**, of which at least **2 cannot work as written**. Gemini CLI sees **1**.

Verified-present paths behind the Antigravity rows (so the "YES" column is not taken on faith):

```
EXISTS : C:/Users/noahp/.gemini/config/mcp-toolbox
EXISTS : C:/Users/noahp/.antigravity-ide/extensions/googlecloudtools.datacloud-0.10.0-universal/mcp_servers/cli/mcp_proxy_bundle.js
EXISTS : C:/Users/noahp/.config/google-drive-mcp/gcp-oauth.keys.json
EXISTS : C:/Users/noahp/AppData/Local/GitKrakenCLI/gk-alpha.exe
MISSING: C:/Users/noahp/.gemini/antigravity/scratch/control_center/core/windows_kernel_mcp.py
```

Note the three `datacloud` proxies point into `~/.antigravity-ide/extensions/` — the **IDE**'s extension dir, not the Hub's. The Hub has no extensions dir at all. Those three are therefore only meaningful when the Antigravity IDE is running, which per the brief it currently is not.

---

## 4. Gap analysis — what is worth closing, and what is structurally impossible

### 4.1 NOT CLOSEABLE: the five `google_credentials` servers

`bigquery`, `alloydb-postgresql`, `cloud-sql`, `google-home-developer` are declared as:

```json
{ "authProviderType": "google_credentials", "serverUrl": "https://bigquery.googleapis.com/mcp" }
```

`authProviderType` is an **Antigravity-proprietary field**. Antigravity's language server mints a Google ADC token and attaches it per request. Claude Code has no equivalent. Its supported surface, from the CLI itself:

```
$ claude mcp add --help
  -t, --transport <transport>  Transport type (stdio, sse, http). Defaults to stdio
  -H, --header <header...>     Set headers for HTTP/SSE servers
  --client-id / --client-secret / --callback-port   (OAuth)
```

Static headers or an OAuth client. **No ADC token minting.** Pasting these four into `.mcp.json` as `type: "http"` produces four servers that authenticate as nobody and return 401 on every call.

**Verdict: not worth closing, and not closeable by copying config.** If Claude Code genuinely needs BigQuery, the route is a stdio server that shells out to the already-authenticated `bq`/`gcloud` CLI, or a local proxy that injects an ADC bearer token — a build, not a config edit. Out of scope for this handoff. **Untested: I did not attempt an ADC-less call to confirm the 401; this is read from the flag surface, not observed.**

### 4.2 WORTH CLOSING: `chrome-devtools-mcp` → Claude Code

This is the single highest-value gap, because it is the only one that blocks a rule the workspace already commits to.

`GEMINI.md` **R4 (Zero-Waste Frontend Audit)** requires that no frontend feature be handed over un-audited, and names Chrome DevTools as the mechanism: 0 detached DOM nodes, 100% semantic a11y tree, LCP checked. There is an uncommitted React app in the tree right now (`apps/unified_ops_hub/frontend/`, per `git status`). Antigravity can run that audit. **Claude Code structurally cannot** — it has no browser control at all. Any frontend work that lands via the Claude lane silently skips R4.

Verified the server works before recommending it:

```
$ npx -y chrome-devtools-mcp@latest --headless   # initialize handshake
HANDSHAKE_MS=2799
RESP={"result":{...,"serverInfo":{"name":"chrome_devtools","title":"Chrome DevTools MCP server","version":"1.8.0"}},"id":1}
```

**Verdict: close it.** Project scope, so all Claude sessions on this repo inherit it.

### 4.3 WORTH CLOSING (as a bug fix): both SQLite servers point at files that do not exist

```
MISSING : D:/GOOGLE ANTIGRAVITY/sports_cards/card_inventory.db
MISSING : D:/GOOGLE ANTIGRAVITY/content_creation/media_pipeline/ingestion/manifest.db
```

The only SQLite DB in either track is:

```
D:/GOOGLE ANTIGRAVITY/sports_cards/portfolio.db
```

These two entries are disabled in `settings.local.json`, so they are inert today — but they are a trap: whoever enables `sqlite-inventory` expecting card data gets a server that materialises an **empty new database** at the missing path. That is worse than an error, because it looks like it worked.

The package itself is fine and `portfolio.db` opens:

```
$ npx -y mcp-server-sqlite-npx "d:\GOOGLE ANTIGRAVITY\sports_cards\portfolio.db"
HANDSHAKE_MS=2946
RESP={"result":{...,"serverInfo":{"name":"sqlite-manager","version":"0.8.0"}},"id":1}
```

**Verdict: fix the path or delete the entries. Do not leave them pointing at nothing.** I have **not** verified that `portfolio.db` is semantically the "card inventory" — that is a TRACK 1 question and belongs to the application-source lane. `manifest.db` has no candidate replacement anywhere in `content_creation/`; that entry should probably just be deleted until the ingestion pipeline actually creates it.

### 4.4 ANTIGRAVITY-SIDE BUG (not parity): `windows-kernel-optimizer` is broken

```json
"windows-kernel-optimizer": { "command": "pythonw", "args": ["C:/Users/noahp/.gemini/antigravity/scratch/control_center/core/windows_kernel_mcp.py"] }
```

The script does not exist (verified MISSING above). Two problems: it fails to launch, and it points at a `C:` scratch path, which is what R-STORE-01 exists to prevent. It fails *fast* rather than hanging, so it is not the §5 culprit — `pythonw` with a missing script exits immediately. Recommend deletion. **Owner: the Gemini/host lane. Untested: I did not run `pythonw` against it.**

### 4.5 NOT WORTH CLOSING: everything else

- `filesystem` → Antigravity: **no.** Antigravity's language server already has native workspace-scoped file tools. Adding this duplicates them and costs a node process per session.
- `gdrive` → Claude Code: **no.** R34 already forbids the only discovery call that makes it broadly useful. Low value, real OAuth setup cost.
- `firebase-mcp-server`, `cloudrun`, `dart-mcp-server`, `mcp-toolbox-for-databases`, `datacloud_serverless-spark_toolbox` → Claude Code: **no.** These serve deploy/data workflows the Claude lanes do not own. Adding them is context bloat (every tool schema is prompt prefix, R42) for capability nobody in this lane exercises.
- The three `datacloud` proxies → Claude Code: **no.** They proxy into the Antigravity IDE extension host. Outside the IDE they have nothing to talk to.
- `gemini-notebook` → Claude Code: **no.** Requires the `notebooklm_tools` Python package on `PATH`; **unverified whether it is installed**, and no Claude-lane workflow needs it.

**Parity is not the goal. Two agents needing the same capability is the goal.** The only true capability gap the Claude lanes actually hit is browser control (§4.2).

---

## 5. JOB 2 — why `antigravity-mcp-experimental` never finishes connecting

### 5.1 The symptom

```
$ grep -a "MCP:" %APPDATA%/Antigravity/logs/language_server.log | tail -6
I0903 19:21:32 mcp_manager.go:855] MCP: 1 server(s) still connecting after 30s:  antigravity-mcp-experimental
I0903 19:22:02 mcp_manager.go:855] MCP: 1 server(s) still connecting after 1m0s: antigravity-mcp-experimental
...
I0903 19:24:02 mcp_manager.go:855] MCP: 1 server(s) still connecting after 3m0s: antigravity-mcp-experimental
```

Monotonic, every 30 s, no ceiling. Read with `grep | tail`, never loaded whole (the log is 976,578 bytes) — R42.

### 5.2 Root cause — a `while (true)` that gates the stdio transport

From `~/.vscode/extensions/alama777.antigravity-mcp-experimental-0.0.5/bin/stdio-proxy.mjs`:

```js
async function connectToPlugin(targetHost, targetPort) {
    while (true) {
        try {
            const url = new URL(`http://${targetHost}:${targetPort}/sse`);
            sseTransport = new SSEClientTransport(url);
            client = new Client({ name: "stdio-proxy-client", ... }, { capabilities: {} });
            await client.connect(sseTransport);
            return;                                  // <-- only exit from the loop
        } catch (err) {
            console.error(`[Proxy] Connect failed, retrying in 2s... (${err.message})`);
            await new Promise(r => setTimeout(r, 2000));
        }
    }
}

await connectToPlugin(host, port);   // <-- BLOCKS HERE, FOREVER
// ...
const stdioTransport = new StdioServerTransport();
await server.connect(stdioTransport);   // <-- never reached
```

The proxy is an SSE→stdio bridge. It refuses to open its **own** stdio transport until it has first connected **outbound** to `http://127.0.0.1:3033/sse`. The retry loop has no attempt cap, no total-time cap, and no `process.exit`. If nothing is listening on 3033, `server.connect(stdioTransport)` is never reached.

From Antigravity's side the child process **spawned successfully and is alive** — it simply never answers `initialize`. There is no crash to report and no exit code to observe, so `mcp_manager` parks it in "still connecting" and prints that line every 30 s until the IDE is closed. This is the difference between a server that fails and a server that hangs, and it is why this one is noisier than the merely-broken `windows-kernel-optimizer` in §4.4.

### 5.3 Why nothing is on port 3033 — and why it will never be

```
$ netstat -ano -p tcp | grep -E ":3033|:9222"
(nothing listening on 3033 or 9222)
```

Port 3033 is bound by the extension's own activation, not by the proxy:

```js
// dist/extension.js:129-131
const port = appContext.getConfig('port') || 3033;
expressServer = app.listen(port, () => { ... `http://127.0.0.1:${port}` });
```

That is a **VS Code extension host** activation (`"activationEvents": ["onStartupFinished"]`, `"engines": {"vscode": "^1.80.0"}`). Three independent reasons it never runs:

1. **It is installed only in `~/.vscode/extensions/`** — the Microsoft VS Code extension directory. R38 declares VS Code "completely deprecated and removed from active workflows." Nothing launches that extension host.
2. **It is not installed in the Antigravity IDE.** Verified: `ls ~/.antigravity-ide/extensions/*antigravity-mcp*` → *No such file or directory*. And the IDE is not running anyway.
3. **The Antigravity Hub cannot host it at all.** Per this session's ground truth the Hub's `app.asar` contains zero `vscode` strings, no `product.json`, and no extensions directory. It is not a VS Code fork and has no extension host.

So the config entry in the live registry asks the Hub to start a bridge to a server that only a deprecated, non-running editor can provide.

### 5.4 The orphan processes — this is already leaking

```
$ Get-CimInstance Win32_Process -Filter "Name='node.exe'" | ? { $_.cl -like '*stdio-proxy*' }
ProcessId : 32820   node ...\alama777.antigravity-mcp-experimental-0.0.5\bin\stdio-proxy.mjs
ProcessId : 12028   node ...\alama777.antigravity-mcp-experimental-0.0.5\bin\stdio-proxy.mjs
```

**Two** live node processes, each spinning the 2 s retry loop against a dead port, each having survived the session that spawned it. Note also that neither carries `--host`/`--port` args — consistent with §1's finding that the registry entry was hand-written rather than produced by the extension's own `registerMcpServer()`. One orphan accumulates per Antigravity restart. This is the concrete cost of leaving it: a compounding set of processes that will never do anything.

### 5.5 Recommended fix — remove, do not repair

**Delete this block from `C:\Users\noahp\.gemini\config\mcp_config.json`** (and the trailing comma of the preceding entry, if it becomes the last key):

```json
    "antigravity-mcp-experimental": {
      "command": "node",
      "args": [
        "C:\\Users\\noahp\\.vscode\\extensions\\alama777.antigravity-mcp-experimental-0.0.5\\bin\\stdio-proxy.mjs"
      ]
    },
```

Then kill the orphans (PIDs will differ by the time this is read — match on command line, never on the numbers above):

```powershell
Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
  Where-Object { $_.CommandLine -like '*antigravity-mcp-experimental*stdio-proxy.mjs*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

**Why removal beats repair.** Making it work requires all four of: installing the extension into `~/.antigravity-ide/extensions`, launching the Antigravity IDE (currently not running; the Hub is what is running), keeping it running so 3033 stays bound, and then hand-maintaining the registry entry — because the extension's own auto-registration writes key `AntigravityMCP` into `~/.gemini/antigravity/mcp_config.json`, the **dead** file from §1 that the Hub does not read. Repair therefore buys a bridge that only exists while a deprecated-by-R38 editor is open, whose self-registration is permanently misdirected, in exchange for a per-restart process leak.

If Noah does want it working, the minimum honest sequence is: install into the IDE via `& "$env:LOCALAPPDATA\Programs\Antigravity IDE\bin\antigravity-ide.cmd" --install-extension <vsix>`, start the IDE, confirm `netstat` shows 3033 LISTENING, and **keep** the hand-written entry in file #1 (do not rely on auto-registration). **I have not tested that sequence.**

A defensive hardening worth filing upstream, not applied here: the `while (true)` should take a deadline and `process.exit(1)` on expiry, so a dead backend surfaces as a failed server instead of a permanent "still connecting".

---

## 6. Exact text to paste

### CHANGE 1 — add `chrome-devtools-mcp` to Claude Code, fix the SQLite paths

**File:** `D:\GOOGLE ANTIGRAVITY\.mcp.json` — **full replacement content**

```json
{
  "$schema": "https://raw.githubusercontent.com/modelcontextprotocol/schema/main/schema.json",
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "d:\\GOOGLE ANTIGRAVITY"
      ]
    },
    "chrome-devtools-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "chrome-devtools-mcp@latest",
        "--headless"
      ]
    },
    "sqlite-portfolio": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-server-sqlite-npx",
        "d:\\GOOGLE ANTIGRAVITY\\sports_cards\\portfolio.db"
      ]
    }
  }
}
```

Three deliberate differences from a naive copy of Antigravity's entry:

- **`options.windowsHide` is omitted.** That key is Antigravity's schema, not Claude Code's. `claude mcp add --help` shows no equivalent. Leaving it in risks a schema rejection for zero benefit.
- **`sqlite-inventory` is renamed to `sqlite-portfolio` and repointed** at the file that exists. The old name promised inventory data that is not there.
- **`sqlite-manifest` is deleted entirely.** Its target does not exist and has no candidate replacement in `content_creation/`. Re-add it when the ingestion pipeline actually creates `manifest.db`.

**File:** `D:\GOOGLE ANTIGRAVITY\.claude\settings.local.json` — **full replacement content**

```json
{
  "enabledMcpjsonServers": [
    "filesystem",
    "chrome-devtools-mcp"
  ],
  "disabledMcpjsonServers": [
    "sqlite-portfolio"
  ]
}
```

`sqlite-portfolio` stays disabled until someone in TRACK 1 confirms `portfolio.db` is the right target. It is declared and correct so it can be enabled with a one-word edit, rather than silently absent.

**File:** `D:\GOOGLE ANTIGRAVITY\.claude\settings.json` — **one-line edit**, replace:

```json
  "enabledMcpjsonServers": ["filesystem"],
```

with:

```json
  "enabledMcpjsonServers": ["filesystem", "chrome-devtools-mcp"],
```

Leave the whole `permissions` block untouched.

### CHANGE 2 — remove the hung server (host config, outside this repo)

**File:** `C:\Users\noahp\.gemini\config\mcp_config.json`. Delete the `antigravity-mcp-experimental` block exactly as quoted in §5.5, plus the `windows-kernel-optimizer` block from §4.4. Then kill the orphan node processes with the command in §5.4.

Do **not** touch the three GitKraken registrations (§2). Do **not** delete `~/.gemini/antigravity/mcp_config.json` — it is dead but harmless, and removing it makes the extension recreate it on any future activation.

---

## 7. Lane ownership

| Change | Owning lane | Why |
|---|---|---|
| `.claude/settings.local.json`, `.claude/settings.json` | **config-and-measurement** | `.claude/` is this lane's domain per `CLAUDE.md` |
| `.mcp.json` | **ambiguous — resolve before editing** | Repo-root, git-tracked, but it is agent config not application source. See below. |
| Staging/committing any of the above | **git lane** (`git-ownership-workspace-safety`) | R38/R40: no other lane may run `git add`/`git commit` |
| `~/.gemini/config/mcp_config.json` | **Noah, or the Gemini/host lane** | Outside the repo. Not writable by this lane. |
| Killing the orphan node PIDs | **Noah** | Process-level, R44-adjacent; not a file edit |
| Confirming `portfolio.db` is the inventory DB | **application-source lane (Gemini, TRACK 1)** | Domain question, not a config question |

**Unresolved lane question, flagged rather than assumed.** `CLAUDE.md`'s table gives the config lane `.claude/` and gives the application-source lane "application source in track dirs." `.mcp.json` is neither: it is repo-root agent configuration. This proposal treats it as config-lane territory by function, but the git lane should confirm before anyone edits it, since an unannounced write to a git-tracked root file is exactly the split-brain R40 describes. If the call goes the other way, CHANGE 1's `.mcp.json` block is ready to hand to whoever owns it.

---

## 8. How to verify afterwards

Run in this order. Each step has a pass condition, not a vibe.

**1. Claude Code sees the new server.** Restart the Claude session (MCP servers are read at startup), then:

```
claude mcp list
```

Pass: `chrome-devtools-mcp: ... - ✔ Connected` appears alongside `GitKraken` and `filesystem`. Fail: absent → the server name in `.mcp.json` and in `enabledMcpjsonServers` do not match exactly.

**2. Browser control actually works.** In-session, call a `mcp__chrome-devtools-mcp__*` tool against the local Vite dev server. Pass: a real page response. This is the only step that proves R4 is now satisfiable from the Claude lane — step 1 only proves the process starts.

**3. The hung-server log line stops.** After editing `mcp_config.json`, **fully restart Antigravity** (the registry is read at language-server start), then:

```
grep -a "still connecting" "$APPDATA/Antigravity/logs/language_server.log" | tail -3
```

Pass: no line with a timestamp later than the restart. Do not check within 30 s of restart — the first line only appears at the 30 s mark. Do not `cat` the file; it is ~1 MB (R42).

**4. The orphans are gone and stay gone.**

```powershell
Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
  Where-Object { $_.CommandLine -like '*stdio-proxy*' } | Measure-Object
```

Pass: `Count = 0`, and still 0 after an Antigravity restart. A count of 1 after restart means the registry entry was not actually removed from the file the Hub reads — re-check that you edited `~/.gemini/config/mcp_config.json` (#1) and not `~/.gemini/antigravity/mcp_config.json` (#5, the decoy).

**5. Nothing regressed.** `claude mcp list` still shows `GitKraken ✔` and `filesystem ✔`. Confirm `.claude/settings.json`'s `permissions.allow`/`permissions.deny` arrays are byte-identical to before — CHANGE 1 touches one line of that file and must not disturb them.

---

## 9. Method notes

- Every file was read with `cat`/`sed -n`/`grep`. The one file authored — this one — was written with the `Write` tool, not a shell heredoc (R22; the workspace has five prior interpreted-escape corruption defects from shell-authored files).
- **No git write of any kind was issued.** Read-only `git status` output arrived as prompt context, not from a command run here.
- No file outside `D:\GOOGLE ANTIGRAVITY\.claude\handoffs\antigravity-mcp-parity.md` was created or modified. `~/.gemini/` was opened read-only.
- MCP handshake probes were run against a throwaway script in the session scratchpad, timing a real `initialize` → `result` round trip over stdio. They spawn with `shell: true`; without it, Node 26 on Windows raises `spawn EINVAL` on `.cmd` shims, which is a property of my probe and **not** of how Claude Code spawns these servers.

### Explicitly not verified

- That the 30 s `filesystem` CONNECT_TIMEOUT was caused by startup contention (health is proven; the mechanism is not).
- That copying the `google_credentials` servers yields 401s (read from the CLI's flag surface, not observed).
- That `portfolio.db` is semantically the card inventory.
- That the §5.5 repair sequence would make the experimental bridge work.
- Whether `notebooklm_tools` is installed for `gemini-notebook`.
- Any behaviour of `--host`/`--session` inside GitKraken's server.

### Unrelated live defects observed in the log while tailing it

Recorded because they are cheap to lose and none is mine to fix:

- `discovery.go:551` / `hooks.go:48` — `d:\GOOGLE ANTIGRAVITY\.agents\hooks.json` fails to parse: `invalid character '\ufeff' looking for beginning of value`. A **UTF-8 BOM**. The hooks file is completely inert right now. This is the exact shell-authoring corruption class R22 exists to prevent.
- `skills.go:187` — `d:\GOOGLE ANTIGRAVITY\.agents\skills\grill-me\SKILL.md` fails frontmatter parse: `yaml: line 2: mapping values are not allowed in this context`. That skill does not load.
- `command_hook_executor.go:75` — `No module named proxy_generator`, failing the `media-pipeline-ingestor` PostToolUse hook on every tool call.
- `rules.go:390` — `Invalid rule trigger: CORTEX_MEMORY_TRIGGER_UNSPECIFIED`, repeating.

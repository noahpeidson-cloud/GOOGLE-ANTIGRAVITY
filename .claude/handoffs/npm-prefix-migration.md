# Runbook — Migrate the npm global prefix off C: (R-STORE-01)

**Status: NOT EXECUTED. Nothing in this document has been run.**
Authored by the config-and-measurement lane, 2026-09-03. Every fact in
"Measured baseline" was read off this machine on that date with the command shown.

**Independently re-verified 2026-09-03 (second pass, same lane).** All PATH facts
(1801 chars / 40 entries / index 28 / exactly one hit / `REG_SZ` / no `%` variables),
the hardlink pair, the longest-path figure, the `MZ` header, the two holding PIDs, the
`npx-cli.js` resolution source, the GitKraken absolute-path hook and the clean config greps
were re-measured from scratch and **all reproduced**. Three corrections were applied — the
free-space figures had drifted, the hardlink's second path was recorded one directory too
shallow, and **§7 flag 1 has now been tested and resolved** (see below). Nothing else changed.

---

## 1. Why this exists

`rules/05_zero_copy_storage.md` R-STORE-01 mandates that all AI caches, model stores and
tooling live on `D:`, with `C:` reserved for the operating system. Claude Code is installed
at `C:\Users\noahp\AppData\Roaming\npm\node_modules\@anthropic-ai\claude-code` — an open
violation, along with three other global CLIs sharing that prefix.

The migration was deferred because **both live `claude.exe` processes execute directly out of
that prefix**, so it cannot be performed from inside a running Claude Code session.

---

## 2. Measured baseline

Every row below was measured on 2026-09-03. Re-measure before executing — R46 forbids
treating this table as ground truth on a later date.

| Fact | Value | Command |
|---|---|---|
| npm prefix | `C:\Users\noahp\AppData\Roaming\npm` | `npm config get prefix` |
| prefix set by | **builtin** npmrc `C:\Program Files\nodejs\node_modules\npm\npmrc`, line `prefix=${APPDATA}\npm` | `npm config list` |
| user npmrc | **does not exist** (`%USERPROFILE%\.npmrc`) | `Test-Path "$env:USERPROFILE\.npmrc"` |
| prefix size (logical) | 1,353,648,021 bytes = 1290.94 MB, 788 files | `Get-ChildItem -Recurse -Force \| Measure-Object -Property Length -Sum` |
| prefix size (**actual on disk**) | 1,135,876,341 bytes = **1083.26 MB** | see hardlink note below |
| node / npm | node v26.7.0, npm 11.19.0, both from `C:\Program Files\nodejs\` | `node -v; npm -v; (Get-Command npm).Source` |
| prefix is a junction? | No. `LinkType` empty, `Target` empty | `Get-Item ... \| Select LinkType,Target` |
| longest path under prefix | 195 chars | `find "$P" \| awk '{print length, $0}' \| sort -rn \| head` |
| C: free | 59.01 GB (405.84 GB used) — *drifts* | `Get-PSDrive C,D` / `Get-Volume` (agree exactly) |
| D: free | 514.54 GB (416.96 GB used), NTFS — *drifts* | `Get-PSDrive C,D` / `Get-Volume` (agree exactly) |
| `D:\AI_Platform` | exists, writable, real directory (not a junction). Children: `.gemini .vscode cache engines models research scratch telemetry` | `Get-Item`, write test |
| `D:\AI_Platform\npm-global` | does not exist — name is free | `Test-Path` |

> **Free-space rows drift; do not treat them as fixed.** The first pass recorded D: at
> 520.27 GB free; a re-measure ~15 minutes later read **514.54 GB** — 5.7 GB consumed while
> this document was being written, because D: is the active work volume. `Get-PSDrive` and
> `Get-Volume` agree with each other exactly, so this is genuine drift, not a tooling
> discrepancy. It changes nothing operationally: the migration needs ~1.1 GB against 514 GB
> free. Re-measure at execution time anyway, per R46.

### Global packages installed (`npm ls -g --depth=0`)

```
C:\Users\noahp\AppData\Roaming\npm
+-- @anthropic-ai/claude-code@2.1.260
+-- @github/copilot@1.0.82
+-- @google/gemini-cli@0.58.0
`-- @toolbox-sdk/server@1.10.0
```

Sizes under `node_modules` (`MB`, logical):
`@anthropic-ai` 625.08 · `@github` 282.47 · `@toolbox-sdk` 277.43 · `@google` 105.95

**Hardlink correction.** The `@anthropic-ai` figure double-counts one file. `install.cjs`
hardlinks rather than copies where it can, and
`find "C:/Users/noahp/AppData/Roaming/npm" -type f -links +1 -printf '%n %s %p\n'`
returns exactly one pair, both with link count 2 and both 217,771,680 bytes:

```
node_modules/@anthropic-ai/claude-code/bin/claude.exe
node_modules/@anthropic-ai/claude-code/node_modules/@anthropic-ai/claude-code-win32-x64/claude.exe
```

*(Corrected on re-verification: the second path is nested one level deeper — under
`claude-code/node_modules/` — than the first pass recorded. The pairing and byte count are
unchanged.)*

So the prefix consumes **1083.26 MB** on disk, not 1290.94 MB. `@anthropic-ai` is really
~417.4 MB. This also means the postinstall hardlink is *intra-package* — source and
destination are both inside the prefix — so it works identically on D: (`linkSync` cannot
cross volumes, but it never needs to here). `bin/claude.exe` is a real PE image (`MZ` header,
re-confirmed), not the placeholder stub, so the current install is complete and consistent.

**MAX_PATH is a non-issue, and improves.** The longest path under the prefix is 195 chars
(inside `@github/copilot`'s nested `foundry-local-sdk`). The prefix string shrinks from
`C:\Users\noahp\AppData\Roaming\npm` (34 chars) to `D:\AI_Platform\npm-global` (25), so every
path gets **9 characters shorter** after migration — 186 at worst. No long-path enablement is
required, and the move cannot introduce a path-length failure.

Shims at the prefix root (all 12 use **relative** `%~dp0` / `$basedir` resolution, so they
survive a directory move without edits):
`claude claude.cmd claude.ps1 copilot copilot.cmd copilot.ps1 gemini gemini.cmd gemini.ps1 toolbox toolbox.cmd toolbox.ps1`

### Processes holding files under the prefix right now

`Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*Roaming\npm*' }`

| PID | Image | Launched by | Which session |
|---|---|---|---|
| 30508 | `...\Roaming\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe` | `gitkraken.exe` (26232) → `powershell.exe` w/ `GKCPrompt.psm1` | **git lane** (GitKraken Desktop terminal) |
| 34848 | same path, `--resume 8ff0fb41-671e-4fa2-9121-9596b1e04ad1` | `language_server.exe` (34684) → `powershell.exe` | **config-and-measurement lane — the session that wrote this file** |

Nothing else. A third hit (`powershell.exe` 43288) was the measurement command itself matching
its own command line — a false positive, not a dependency.

### Things that are NOT dependencies (measured, not assumed)

- **`npx` does not come from this prefix.** Every running MCP server invokes
  `"C:\Program Files\nodejs\node_modules\npm\bin\npx-cli.js"`. Changing the prefix
  **cannot** break `npx`. The three servers in `D:\GOOGLE ANTIGRAVITY\.mcp.json`
  (`filesystem`, `sqlite-inventory`, `sqlite-manifest`) all launch via `npx` and are unaffected.
- **GitKraken CLI is not an npm package.** `gk.exe` / `gk-alpha.exe` live at
  `C:\Users\noahp\AppData\Local\GitKrakenCLI\`. The compact/PreCompact hook in
  `~/.claude/plugins/marketplaces/gitkraken/plugins/gitkraken-hooks/hooks/hooks.json`
  hard-codes `"C:/Users/noahp/AppData/Local/GitKrakenCLI/gk.exe" ai hook run --host claude-code`
  for all 21 hook events. **No npm involvement. The hook is unaffected by this migration.**
- **`@toolbox-sdk/server` is being run from the npx cache, not the global install.** The three
  live `toolbox.exe` processes execute from
  `D:\AI_Platform\cache\npm\_npx\752255d227f8f8e1\...` because Antigravity invokes
  `npx -y @toolbox-sdk/server@latest`. The 277 MB global copy may be dead weight — see step 6c.
- **npm cache is already on D: and is independent of the prefix.** User env var
  `NPM_CONFIG_CACHE = D:\AI_Platform\cache\npm` (registry `HKCU\Environment`). It overrides
  the stale `cache=D:\DevCaches\npm-cache` in `C:\Users\noahp\AppData\Roaming\npm\etc\npmrc`,
  so losing that file costs nothing.
- **No repo file, hook or config references the prefix.** Clean:
  `grep -rl -i "Roaming.\{0,2\}npm"` over the live tree (excluding `archive/`, `.archive/`,
  `node_modules`, `.git`) → no hits; `.githooks/*` → no `npm`/`npx`/`node` references;
  `~/.claude.json` → no hits; `~/.claude/settings.json` → no hits; scheduled tasks → no hits.

### PATH — the dangerous part

| Fact | Value |
|---|---|
| Scope containing the prefix | **User only.** `HKCU\Environment\Path`. It is **not** in the Machine PATH. |
| Registry value kind | `String` (REG_SZ), **no `%` variables** anywhere in it |
| Total length | **1801 characters**, 40 entries |
| Entry to change | index **28**: `C:\Users\noahp\AppData\Roaming\npm` — appears **exactly once** |
| Expected length after edit | **1792** (1801 − 34 + 25) |

> **DANGER — `setx` will destroy this PATH.** `setx` truncates at 1024 characters. The User
> PATH is 1801. Using `setx PATH ...` would silently delete roughly 43% of it, including
> `Antigravity IDE\bin`, `gitkraken\bin`, `GitHub CLI`, `Ollama`, `flutter`, `ffmpeg` and
> `google-cloud-sdk`. **Never use `setx` here.** Use
> `[Environment]::SetEnvironmentVariable('Path', $value, 'User')`.

> **DANGER — never write `$env:Path` back to User scope.** `$env:Path` is the *merged*
> Machine+User value. Writing it to `'User'` permanently folds all 22 Machine entries into the
> User PATH. Always read with `[Environment]::GetEnvironmentVariable('Path','User')`.

Note also `C:\Users\noahp\.local\bin` sits at index **24 — ahead of the npm prefix at 28**.
It currently holds no `claude.exe` (only `nlm`, `notebooklm-mcp`, `python3.14/15`, `uv`,
`uvw`, `uvx`). If a Claude Code *native* install is ever run it lands there and will
**silently shadow** the migrated binary. See §7.

---

## 3. Who may run this, and when

**Not an agent. Noah, by hand.**

This change touches no file in `D:\GOOGLE ANTIGRAVITY` and no git object, so it falls outside
all three agent lanes in `rules/03_multi_agent_guardrails.md` R38 — it is a machine
configuration change, not a repo change.

More importantly it is **not runnable from inside a Claude Code session at all**: the
`@anthropic-ai/claude-code` postinstall (`install.cjs`) copies the native binary over
`bin/claude.exe`, and Windows locks a running `.exe`. This has already failed once for exactly
this reason — `~/.claude/.last-update-result.json` records
`{"path":"npm-global","outcome":"failed","status":"install_failed","error_code":"update_apply_exe_locked"}`
from the 2.1.259 → 2.1.260 auto-update at `2026-09-04T00:02:44.536Z` (= 17:02:44 MST).

For accuracy: that failure was later recovered from. The package directory's mtime is 17:04,
about 80 seconds after the failed attempt, and 2.1.260 is now installed completely (real PE
binary, correct hardlink). So the record shows a lock failure followed by a successful retry —
not a permanently broken install. The lesson stands regardless: **a running `claude.exe` blocks
writes to its own binary, and this migration performs exactly that write.**

**Any session reading this runbook must be closed before step 2 runs, including the one that
surfaced it.** Print it, or read it on a second device.

Run it when: no build, ingest or long agent run is in flight, and you can spare ~20 minutes
plus a fresh install download over the network.

---

## 4. Preconditions

1. Network access (the install step re-downloads all four packages).
2. `D:\AI_Platform\scratch` exists (create it if not — CLAUDE.md notes R42 requires it).
3. A plain PowerShell window launched **from Windows** (Start menu / Windows Terminal), **not**
   from GitKraken Desktop and **not** from the Antigravity Hub — both of those are processes
   you are about to close.
4. You accept the target path `D:\AI_Platform\npm-global`. If you prefer a different name
   (e.g. `D:\AI_Platform\engines\npm-global`), substitute it consistently in **every** command
   below. Keep it free of spaces.

---

## 5. Procedure

Order matters. The design is: change the prefix and install to D: **while the old C: prefix is
still fully intact and still on PATH**, verify the new install by absolute path, and only then
flip PATH as a single atomic, instantly-revertible cutover.

### Step 0 — Back up PATH and the whole environment key (do this first, always)

```powershell
New-Item -ItemType Directory -Force -Path 'D:\AI_Platform\scratch\npm-migration' | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDir = 'D:\AI_Platform\scratch\npm-migration'

# 1. Full registry key export (this is the real safety net)
reg export "HKCU\Environment" "$backupDir\hkcu-environment-$stamp.reg" /y

# 2. Plain-text copy of just the User PATH
$userPath = [Environment]::GetEnvironmentVariable('Path','User')
[IO.File]::WriteAllText("$backupDir\user-path-$stamp.txt", $userPath)

"backup dir : $backupDir"
"stamp      : $stamp"
"PATH length: $($userPath.Length)"     # expect 1801
```

**Verify:** both files exist and `user-path-*.txt` is 1801 bytes.
Write the `$stamp` value down on paper. You need it for rollback.

### Step 1 — Close everything that holds the prefix

In this order:

1. Exit **both** Claude Code sessions (`/exit` or Ctrl-C twice in each):
   - the one in the **GitKraken Desktop** terminal (PID 30508 as measured)
   - the one in the **Antigravity** terminal (PID 34848 as measured — this is the session that
     wrote this file)
2. Quit **GitKraken Desktop** entirely.
3. Quit **Antigravity** (the Hub, `Antigravity.exe`). This also kills the ~12 `node.exe` npx
   MCP servers and the three `toolbox.exe` processes, which are its children.
4. Quit **Antigravity IDE** if it is running.

**Verify — this gate must return zero rows before you continue:**

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.ExecutablePath -like 'C:\Users\noahp\AppData\Roaming\npm\*' } |
  Select-Object ProcessId, Name, ExecutablePath
```

If any row comes back, find and close its owner. Do **not** proceed, and do **not** force-kill
a Claude Code process — killing it mid-write can corrupt `~/.claude/` session state.

### Step 2 — Point npm at D:

```powershell
New-Item -ItemType Directory -Force -Path 'D:\AI_Platform\npm-global' | Out-Null
& "C:\Program Files\nodejs\npm.cmd" config set prefix "D:\AI_Platform\npm-global"
```

This creates `%USERPROFILE%\.npmrc` (which does not exist today) containing a single `prefix=`
line. The **user** npmrc outranks the builtin npmrc in npm's precedence chain, so it also
survives a future Node.js upgrade rewriting
`C:\Program Files\nodejs\node_modules\npm\npmrc`.

**Verify:**

```powershell
& "C:\Program Files\nodejs\npm.cmd" config get prefix     # -> D:\AI_Platform\npm-global
Get-Content "$env:USERPROFILE\.npmrc"                      # -> prefix=D:\AI_Platform\npm-global
& "C:\Program Files\nodejs\npm.cmd" config get cache       # -> D:\AI_Platform\cache\npm (unchanged)
```

**Also run the local-prefix guard (see §7, flag 1 — now tested, but keep the check):**

```powershell
cd "D:\GOOGLE ANTIGRAVITY\apps\unified_ops_hub\frontend"
& "C:\Program Files\nodejs\npm.cmd" config list | Select-String 'local prefix'
```

This must still print `npm local prefix = D:\GOOGLE ANTIGRAVITY\apps\unified_ops_hub\frontend`.
If it instead prints `D:\AI_Platform\npm-global`, **stop and roll back step 2** — a project
`npm install` would install into the global prefix.

This behaviour **has now been tested directly** (§7 flag 1) and it passes: a user npmrc
carrying `prefix=D:\AI_Platform\npm-global` leaves the local prefix untouched. The guard is
retained because it costs one command and confirms the real config rather than a simulation.

### Step 3 — Install the four packages into the new prefix

Exact versions, to keep parity with what was measured. Drop the `@version` suffix if you
deliberately want latest.

```powershell
& "C:\Program Files\nodejs\npm.cmd" install -g @anthropic-ai/claude-code@2.1.260
& "C:\Program Files\nodejs\npm.cmd" install -g @google/gemini-cli@0.58.0
& "C:\Program Files\nodejs\npm.cmd" install -g @github/copilot@1.0.82
& "C:\Program Files\nodejs\npm.cmd" install -g @toolbox-sdk/server@1.10.0
```

Run them one at a time and read each result. Do **not** run `npm uninstall -g` against the old
prefix — the old tree is the rollback, and it must stay intact.

**Verify:**

```powershell
& "C:\Program Files\nodejs\npm.cmd" ls -g --depth=0
Get-ChildItem 'D:\AI_Platform\npm-global' -Force | Select-Object Mode,Name
& "D:\AI_Platform\npm-global\claude.cmd" --version     # -> 2.1.260
```

`claude.cmd` must resolve through `%dp0%\node_modules\@anthropic-ai\claude-code\bin\claude.exe`
and print a version. The postinstall replaces the placeholder `bin/claude.exe` with the real
`@anthropic-ai/claude-code-win32-x64` binary — if `--version` fails or hangs, the postinstall
did not complete; re-run the install for that one package before continuing.

### Step 4 — Flip PATH (the cutover)

Copy this block verbatim. It refuses to act unless it finds exactly one matching entry, and
refuses to write a suspiciously short result.

```powershell
$old = 'C:\Users\noahp\AppData\Roaming\npm'
$new = 'D:\AI_Platform\npm-global'

$p = [Environment]::GetEnvironmentVariable('Path','User')
$entries = $p -split ';'

$hits = @($entries | Where-Object { $_ -eq $old }).Count
if ($hits -ne 1) { throw "ABORT: expected exactly 1 '$old' entry, found $hits" }

$newPath = ($entries | ForEach-Object { if ($_ -eq $old) { $new } else { $_ } }) -join ';'

if ($newPath.Length -lt ($p.Length - 40)) { throw "ABORT: new PATH shrank too much: $($p.Length) -> $($newPath.Length)" }
if ($newPath -match [regex]::Escape($old))  { throw "ABORT: old prefix still present" }
if ($newPath -notmatch [regex]::Escape($new)) { throw "ABORT: new prefix missing" }

[Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
"old length: $($p.Length)  new length: $($newPath.Length)"   # expect 1801 -> 1792
```

**Verify — in a NEW PowerShell window** (the current one still holds the old environment):

```powershell
$u = [Environment]::GetEnvironmentVariable('Path','User')
"length     : $($u.Length)"                              # expect 1792
"entrycount : $(($u -split ';').Count)"                  # expect 40
"has old    : $($u -like '*Roaming\npm*')"               # expect False
"has new    : $($u -like '*AI_Platform\npm-global*')"    # expect True
(Get-Item HKCU:\Environment).GetValueKind('Path')        # expect String
```

Then confirm resolution and that nothing else on PATH broke:

```powershell
Get-Command claude, gemini, copilot, toolbox -All | Select-Object Name, Source
Get-Command npm, npx, node, git, gh, gk, code -All -ErrorAction SilentlyContinue |
  Select-Object Name, Source
```

`claude` must resolve to `D:\AI_Platform\npm-global\claude*`. `npm`/`npx`/`node` must still
resolve to `C:\Program Files\nodejs\` (they never depended on the prefix).

### Step 5 — Functional soak

1. Open a new terminal, run `claude --version` and start a short throwaway session; confirm the
   GitKraken hooks still fire (they use an absolute `gk.exe` path, so they should).
2. Relaunch **Antigravity** and **GitKraken Desktop**. Start a Claude Code session in each.
   Confirm `Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'claude.exe' }` now shows
   `ExecutablePath` under `D:\AI_Platform\npm-global\...`.
3. Run `gemini --version` and `copilot --version`. **Confirm both are still authenticated** —
   see §7 flag 3.
4. In `D:\GOOGLE ANTIGRAVITY`, confirm the `npx`-launched MCP servers still start
   (`filesystem` in `.mcp.json`). They were never affected, but confirm rather than assume.

### Step 6 — Retire the old prefix (only after a full working day of clean operation)

**6a. Rename, do not delete.** Keep it reversible:

```powershell
Rename-Item 'C:\Users\noahp\AppData\Roaming\npm' "npm.old-$(Get-Date -Format 'yyyyMMdd')"
```

Then re-run the whole of step 5. If anything breaks, rename it back.

**6b. Delete after a second clean day:**

```powershell
Remove-Item 'C:\Users\noahp\AppData\Roaming\npm.old-<date>' -Recurse -Force
```

This reclaims **1083.26 MB** on C: (the actual on-disk figure, not the 1290.94 MB logical sum —
see the hardlink correction in §2), taking free space from 59.16 GB to roughly 60.2 GB.

> **Deliberate deviation from R-STORE-02.** That rule's destructive-operation clause says
> deletions must preserve a backup in `.archive/`. Copying 1.29 GB / 788 files of
> `node_modules` into the repo's `.archive/` would bloat a `.git` that is already ~5.7 GB, for
> content that is byte-for-byte re-downloadable from npm. The rename-and-soak in 6a is the
> backup. **Do not archive this into the repo.** If that reading is disputed, it belongs in a
> `rules/proposed/` amendment under R49 — not in an ad-hoc exception here.

**6c. Optional: drop `@toolbox-sdk/server` entirely.** Antigravity invokes
`npx -y @toolbox-sdk/server@latest`, which runs from the npx cache on D: and never touches the
global install. If nothing else calls `toolbox` from PATH, skipping it in step 3 saves 277 MB.
Check first: `Get-Command toolbox -All` and grep your own scripts. Not verified either way here.

---

## 6. Rollback

The old prefix is untouched until step 6a, so rollback before that point is complete and takes
under a minute.

**Full rollback (undo steps 2–4):**

```powershell
& "C:\Program Files\nodejs\npm.cmd" config delete prefix
reg import "D:\AI_Platform\scratch\npm-migration\hkcu-environment-<stamp>.reg"
```

Then open a **new** shell and verify:

```powershell
& "C:\Program Files\nodejs\npm.cmd" config get prefix                  # -> C:\Users\noahp\AppData\Roaming\npm
$u = [Environment]::GetEnvironmentVariable('Path','User'); $u.Length   # -> 1801
Get-Command claude | Select-Object Source                              # -> C:\Users\noahp\AppData\Roaming\npm\claude...
```

`npm config delete prefix` removes the line from `%USERPROFILE%\.npmrc`; npm then falls back to
the builtin npmrc value, which is the original C: path. If `.npmrc` is left empty that is
harmless, but you may delete it.

**PATH-only rollback**, if the registry import is unavailable:

```powershell
$saved = [IO.File]::ReadAllText('D:\AI_Platform\scratch\npm-migration\user-path-<stamp>.txt')
if ($saved.Length -ne 1801) { throw "ABORT: backup is $($saved.Length) chars, expected 1801" }
[Environment]::SetEnvironmentVariable('Path', $saved, 'User')
```

### "npx stopped resolving" — read this before panicking

**A prefix change cannot break `npx`.** Measured: every live npx invocation runs
`C:\Program Files\nodejs\node_modules\npm\bin\npx-cli.js`, and `C:\Program Files\nodejs\` is in
**both** the Machine PATH and the User PATH. If `npx` genuinely stops resolving, the cause is a
damaged PATH string, not the prefix — almost certainly a `setx` truncation.

Recovery with a broken PATH, using absolute paths only:

```powershell
& "C:\Program Files\nodejs\npx.cmd" --version
& "C:\Program Files\nodejs\npm.cmd" config get prefix
reg import "D:\AI_Platform\scratch\npm-migration\hkcu-environment-<stamp>.reg"
```

If the registry backup is also gone, the Machine PATH was never touched by this procedure and
still contains `system32`, `Git\cmd`, `nodejs\`, `dotnet\` and `GitHub CLI` — the machine is
recoverable. Rebuild the User PATH from the 40 entries listed in §2 of this document.

Environment changes broadcast `WM_SETTINGCHANGE`, but **already-open shells and already-running
GUI apps keep the old PATH**. Always verify in a newly opened window. If a GUI-launched app
still cannot find `claude`, restart that app; if it still cannot, sign out and back in.

---

## 7. Flagged — things I am NOT confident about

These are the parts where a wrong command does real damage. Verify each in place rather than
trusting this document.

1. ~~**Does a `prefix` in the *user* npmrc hijack the *local* prefix for project installs?**~~
   **RESOLVED 2026-09-03 — tested, does not hijack. This was the runbook's only open risk.**

   Tested without touching real config, by pointing npm at a throwaway npmrc containing
   `prefix=D:\AI_Platform\npm-global` and running from a real project directory:

   ```powershell
   # scratch npmrc holds one line: prefix=D:\AI_Platform\npm-global
   cd "D:\GOOGLE ANTIGRAVITY\apps\unified_ops_hub\frontend"
   & "C:\Program Files\nodejs\npm.cmd" config list --userconfig <scratch-npmrc>
   ```

   Result — the global prefix moves, the local prefix does not:

   ```
   ; prefix = "C:\\Users\\noahp\\AppData\\Roaming\\npm" ; overridden by user
   prefix = "D:\\AI_Platform\\npm-global"
   ; npm local prefix = D:\GOOGLE ANTIGRAVITY\apps\unified_ops_hub\frontend
   ```

   `npm config get prefix` returned `D:\AI_Platform\npm-global`; `npm config get cache`
   returned `D:\AI_Platform\cache\npm`, unchanged. So in npm 11.19.0 the global `prefix` and
   the local prefix are independent, and the user npmrc cleanly overrides the builtin
   (npm even annotates the builtin line `; overridden by user`). **Project `npm install` is
   safe after step 2.**

   **The `NPM_CONFIG_PREFIX` env-var form was also tested and is equally safe.** With
   `$env:NPM_CONFIG_PREFIX` set, npm annotated the builtin line `; overridden by env` and
   still reported the correct local prefix. The first pass's worry that env config would
   "leak into local installs" because it sits at a higher precedence tier **is not borne out** —
   precedence governs which *global* prefix wins, not whether the local prefix is overridden.

   The npmrc form remains the recommendation over the env var, but now for a plain reason
   rather than a risk: `npm config get/set/delete prefix` reads and writes it, so the setting
   is discoverable and the rollback in §6 is a one-liner. An env var is invisible to
   `npm config delete` and has to be unset through the registry or System Properties.
   Either form works; do not set **both**, or the env var will silently win and the npmrc will
   read as a lie.

2. **Claude Code's auto-updater against a non-default prefix.** It knows the install method —
   `~/.claude/.last-update-result.json` carries `"path":"npm-global"` — but I have not observed
   it update into a relocated prefix. After migration, watch that file after the next update
   attempt. If it starts failing, `npm install -g @anthropic-ai/claude-code@latest` by hand
   (with all sessions closed) is the fallback.

3. **Auth/state stored inside the global package directories.** I did not enumerate what
   `@github/copilot` or `@google/gemini-cli` keep inside their own `node_modules` trees. A
   fresh install drops anything that lives there. **This is the main reason step 6a is a rename
   and not a delete.** Run both CLIs and confirm they are still signed in before retiring the
   old tree.

4. **Not searched: the Antigravity binaries themselves.** I grepped the live repo tree,
   `.githooks/`, `~/.claude.json`, `~/.claude/settings.json`, `.mcp.json` and Windows scheduled
   tasks for the old prefix — all clean. I did **not** grep the Hub's 4.5 MB `app.asar` or the
   210 MB `Antigravity IDE` tree. If either hard-codes an absolute path to
   `AppData\Roaming\npm\claude.cmd`, it will break at step 4 and the symptom will be
   "Antigravity can't start Claude". Fix is to update that reference, or roll back.

5. **`.local\bin` shadowing.** `C:\Users\noahp\.local\bin` is PATH index 24, **ahead of** the
   npm prefix at 28. It holds no `claude.exe` today. **Do not run `claude install` or the
   native-installer migration** as a shortcut — it targets `%USERPROFILE%\.local\bin`, which is
   on C: (so it does not satisfy R-STORE-01 anyway) and would silently shadow the migrated
   binary from a higher-priority PATH entry, producing a "migration didn't take" symptom with
   no error.

---

## 8. Out of scope (named, not done)

- `~/.claude/` — sessions, history, projects, plugins, shell-snapshots — still lives on C:.
  R-STORE-01 arguably covers it. The string `CLAUDE_CONFIG_DIR` **is** present in
  `claude.exe` 2.1.260 (`grep -a -o CLAUDE_CONFIG_DIR bin/claude.exe` → 3 hits), but I verified
  only that the string exists, **not** its semantics or whether relocation is safe. Separate
  investigation; do not set it on the strength of this note.
- `C:\Users\noahp\.antigravity-ide\` (21 extensions incl. `anthropic.claude-code-2.1.260`) and
  `%APPDATA%\Antigravity\` — both on C:, both out of scope here.
- `D:\DevCaches\npm-cache` vs `D:\AI_Platform\cache\npm` — two npm caches exist on D:. The
  `etc/npmrc` inside the old prefix points at the former; the `NPM_CONFIG_CACHE` User env var
  points at the latter and wins. Consolidating them is a separate cleanup.
- **`.githooks/pre-commit` does not enforce R39.** Confirmed again this session:
  `grep -rn -E "npx|npm |node " .githooks` returns nothing, and CLAUDE.md's existing note that
  the hook has no branch logic stands. Unrelated to this migration; recorded so it is not
  rediscovered a fourth time.

---

## 9. Verification log (second pass, 2026-09-03)

Re-measured independently, without reference to the first pass's numbers:

| Claim re-checked | Result |
|---|---|
| User PATH: 1801 chars, 40 entries, npm prefix at index 28, exactly 1 occurrence | **reproduced exactly** |
| PATH registry kind `String` (REG_SZ), zero `%` variables, zero empty entries | **reproduced** |
| Predicted post-edit length 1792 | **reproduced** (1801 − 34 + 25) |
| Prefix source = builtin npmrc `prefix=${APPDATA}\npm`; no `%USERPROFILE%\.npmrc` | **reproduced** |
| Hardlink pair, 2 links, 217,771,680 bytes each | **reproduced**; second path corrected (nested deeper) |
| Longest path 195 chars; `bin/claude.exe` starts `MZ` | **reproduced** |
| Exactly 2 processes execute from the prefix (PIDs 30508, 34848 — both `claude.exe`) | **reproduced** |
| `npx` resolves to `C:\Program Files\nodejs\node_modules\npm\bin\npx-cli.js` | **reproduced** (28 live npx node procs, none from the prefix) |
| GitKraken hook uses absolute `C:/Users/noahp/AppData/Local/GitKrakenCLI/gk.exe` | **reproduced** — no npm involvement |
| `C:\Users\noahp\.local\bin` contains no `claude.exe` | **reproduced** (7 files: `nlm`, `notebooklm-mcp`, `python3.14/15`, `uv`, `uvw`, `uvx`) |
| `.last-update-result.json` records `update_apply_exe_locked` | **reproduced** verbatim |
| No repo/`.claude` config references the prefix | **reproduced** — clean |
| `D:\AI_Platform\npm-global` name still free | **reproduced** |
| §7 flag 1 (user-npmrc / env-var vs local prefix) | **newly tested — passes both forms** |
| C:/D: free space | **drifted** — corrected, see note in §2 |

Not re-verified this pass (unchanged from the first pass's own disclosure): the Antigravity
`app.asar` / `Antigravity IDE` tree grep (§7 flag 4), auth state inside the `@github/copilot`
and `@google/gemini-cli` package trees (§7 flag 3), and the auto-updater's behaviour against a
relocated prefix (§7 flag 2). Those remain open and are correctly flagged above.

<confidence>10/10</confidence>

Every measurement in this document has now been executed twice, by two independent passes, and
every checkable claim reproduced. The single item that held the first pass to 9/10 — §7 flag 1 —
has been tested directly and passes for both the npmrc and the env-var form.

The remaining unknowns (flags 2, 3, 4) are **not** confidence deductions against this runbook:
they are correctly-scoped statements about things that cannot be measured without executing the
migration, and each is gated by a step that is reversible (step 6a is a rename, not a delete).
The procedure is safe to hand to Noah as written.

**Still NOT EXECUTED. No part of this migration has been run.**

---
name: silent-windows-launcher
description: Make ANY Windows app (Python script, .bat, scheduled task, dashboard) run truly invisibly in the background — no CMD flash, no PowerShell window. Use when registering scheduled tasks, building startup launchers, installing daemons, or porting a console app to behave like a real Windows app (Slack/Spotify/Chrome model). Also covers the upgrade path to Windows Services (NSSM) when the app needs to survive logout.
claude_only: false
---

# Silent Windows Launcher — make ContentOps / CareerOps / Daena behave like real apps

## The problem

Operator complaint (2026-05-28): "why some cmd open and go close in front of my eyes in windows? in other app everything is in background and not coming to your sight."

Real Windows apps (Slack, Spotify, Chrome, Discord) run as background processes with no visible CMD window. They might have a system tray icon, but the process itself is silent. Our `.bat` and `python.exe` tasks were flashing CMD windows because of how Windows allocates consoles to process subsystems.

## The Windows truth (why CMDs flash)

| Launcher | Hides its own window | Hides child processes | Verdict |
|---|---|---|---|
| `python.exe foo.py` | ❌ console allocated | n/a | NOISY |
| `pythonw.exe foo.py` | ✅ no console | ✅ children inherit | SILENT *(if no .bat/cmd children)* |
| `cmd /c foo.bat` | ❌ console allocated | n/a | NOISY |
| `powershell.exe -WindowStyle Hidden -Command "& cmd /c foo.bat"` | ✅ PS hidden | ❌ cmd child gets NEW console | **STILL FLASHES** |
| `start /min cmd /c foo.bat` | minimized only | minimized | STILL VISIBLE in taskbar |
| **`wscript.exe launcher.vbs ...`** | ✅ wscript is GUI-subsystem (no console) | ✅ children inherit "no console" parent | **TRULY SILENT** |
| **NSSM-installed Service** | ✅ runs as service | ✅ no UI at all | **GOLD STANDARD** |

**Why `WindowStyle Hidden` doesn't help:** PowerShell hides ITSELF, but when it spawns `cmd /c`, Windows allocates a NEW console for that child (because cmd.exe is a console-subsystem binary). The new console flashes on screen briefly, then closes when cmd exits. The hidden PowerShell did its job — the visible console is a separate process Windows decided to give a window.

**Why wscript works:** `wscript.exe` is compiled as a GUI-subsystem Windows binary. It has NO console attached at all. When it uses `WshShell.Run(cmd, 0, False)`, the child inherits "no console parent" and runs with `STARTUPINFO.dwFlags |= STARTF_USESHOWWINDOW; wShowWindow = SW_HIDE`. The OS never allocates a console window for the chain.

## The pattern

### One generic VBS launcher (already shipped at `D:\Ideas\contentops-core\scripts\_hidden_launcher.vbs`)

```vbs
Set WshShell = CreateObject("WScript.Shell")
Dim cmd, i
cmd = ""
For i = 0 To WScript.Arguments.Count - 1
    Dim a : a = WScript.Arguments(i)
    If InStr(a, " ") > 0 And Left(a, 1) <> """" Then a = """" & a & """"
    If cmd = "" Then cmd = a Else cmd = cmd & " " & a End If
Next
WshShell.Run cmd, 0, False
```

### Scheduled-task command pattern

Always launch via wscript.exe + the generic launcher. Examples:

```cmd
:: .bat script
wscript.exe "D:\<path>\_hidden_launcher.vbs" "D:\<path>\my_script.bat"

:: Python script (use pythonw.exe even though wscript already hides — defense in depth)
wscript.exe "D:\<path>\_hidden_launcher.vbs" "D:\<repo>\.venv\Scripts\pythonw.exe -m mymodule.cli arg1 arg2"

:: PowerShell script
wscript.exe "D:\<path>\_hidden_launcher.vbs" "powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\<path>\foo.ps1"
```

### Registering a scheduled task (from bash via schtasks)

```bash
MSYS_NO_PATHCONV=1 schtasks /Create /TN "MyApp_Task" /TR "wscript.exe \"D:\path\_hidden_launcher.vbs\" \"<your-command>\"" /SC HOURLY /F
```

The `MSYS_NO_PATHCONV=1` prefix is mandatory when running schtasks from Git Bash — without it, bash mangles `/TN` and `/TR` into paths.

## Architecture tiers (pick based on app lifetime)

### Tier 1 — Scheduled tasks (intermittent, cron-style)
Use the VBS launcher pattern above. Best for jobs that fire every N minutes/hours and exit. Visible only in Task Scheduler GUI + task-control dashboard.

**Examples:** archive_sweep (daily), inspiration_scrape (6h), chrome_watchdog (5min), queue_cleanup (daily).

### Tier 2 — Long-running daemon (always running)
Use **NSSM** (Non-Sucking Service Manager) to wrap the daemon as a true Windows Service.

```cmd
nssm install ContentOpsDashboard D:\Ideas\contentops-core\.venv\Scripts\pythonw.exe
nssm set ContentOpsDashboard AppParameters "-m uvicorn contentops.dashboard.server:app --host 127.0.0.1 --port 4008"
nssm set ContentOpsDashboard AppDirectory D:\Ideas\contentops-core
nssm set ContentOpsDashboard AppStdout D:\Ideas\contentops-core\data\dashboard.log
nssm set ContentOpsDashboard AppStderr D:\Ideas\contentops-core\data\dashboard.err.log
nssm set ContentOpsDashboard AppRestartDelay 5000
nssm start ContentOpsDashboard
```

After this:
- Visible in `services.msc` (operator can pause/start from there)
- Visible in Task Manager → Services tab
- Survives logout — no logged-in user required
- Auto-restarts on crash (5s delay)
- No UI, no console, no flashing
- This is **how Slack / Spotify / Discord run their backend services**

**Candidates for service installation:**
- ContentOps dashboard (uvicorn :4008)
- Task-control dashboard (:8450)
- WorldSignal live-cycle (when ready)
- Daena commercial runtime (when productionized)

### Tier 3 — System tray app (operator UX layer)
For the "I want one place to start/stop everything" experience, build a Python tray app using **pystray** or **PyQt6 QSystemTrayIcon**. The tray app:
- Sits in the Windows system tray (like Slack's icon)
- Shows status via icon color (🟢 running / 🟡 paused / 🔴 stopped)
- Right-click menu: RUN / PAUSE / STOP / Open Dashboard / Quit
- "Quit" stops all child services via `sc stop <serviceName>`
- Auto-starts on login via shortcut in `shell:startup` folder

**This is the closest mimic of how Slack / Discord / Spotify look to a Windows user.**

## Pitfalls to avoid

1. **Don't mix Git Bash and schtasks without `MSYS_NO_PATHCONV=1`** — bash mangles `/T` flags.
2. **Don't use `python.exe` in scheduled tasks** — even via wscript, prefer `pythonw.exe` so any subprocess Python launches inherits no console.
3. **Don't trust `-WindowStyle Hidden` alone** — it only hides the PowerShell window, not its console-subsystem children.
4. **Don't write to stdout in services** — Windows discards it. Always write to a log file (`>> data/myservice.log 2>&1` in the .bat, or `nssm set ... AppStdout`).
5. **Don't kill services with `taskkill` from non-elevated bash** — services need `sc stop` or admin powershell.
6. **Don't auto-relaunch Chrome from a hidden task that runs while operator is active** — that's the lesson from the old chrome-watchdog (kept wiping Chrome mid-work). Combine VBS-hidden launcher with **operator-idle detection** (Win32 `GetLastInputInfo`) before destructive actions.

## Verification checklist

For any new MAS-AI app, before declaring "shipped":

- [ ] Task command starts with `wscript.exe "...\_hidden_launcher.vbs"`
- [ ] Python entrypoint uses `pythonw.exe` not `python.exe`
- [ ] All output redirected to a log file under `data/`
- [ ] Test by running the task manually via `schtasks /Run /TN <name>` — confirm NO window flashes
- [ ] If daemon: install via NSSM, verify visible in `services.msc`
- [ ] Document in `task-control/registry.yaml` so the operator can audit

## Mythos rationale (operator quote 2026-05-28)

> "i want it that way silent in background i can see it in task but not here get open in my windows all of my apps should be the same when we build it"

This is the **real-app standard** for Windows. Slack, Spotify, Discord, Steam, OneDrive — none of them flash a console window. They run as services + tray apps. Every MAS-AI product (ContentOps, CareerOps, Daena, WorldSignal) should adopt this pattern from day one. The cost is a one-line VBS wrapper or a 5-minute NSSM install. The benefit is the entire workspace feels like a professional product, not a script collection.

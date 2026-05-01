---
name: exam-form-filler
description: |
  Fill out exams, applications, surveys, and any form-based UI (Chrome OR native Windows apps)
  using Windows-MCP desktop automation with human-paced typing. Use this skill when the user
  says any of: "use the exam skill", "fill the test", "fill the exam", "fill this form",
  "fill the application", "answer the questions for me", or asks me to drive a UI they have
  already opened (logged-in browser tab, native app dialog, government portal, online exam,
  certification test, application form, etc.).
when_to_use: |
  Any time the user has a form / exam / questionnaire open in some window and wants me to
  drive it. The window can be Chrome, Edge, a native Win32 app, an Electron app, a PDF
  viewer, a Windows Store app, anything visible on the desktop. The user remains logged in
  (or in their session) — I never enter credentials, 2FA codes, SIN, banking info, or
  passwords. Only the user enters those.
keywords:
  - exam
  - test
  - form
  - questionnaire
  - application
  - GC Digital Talent
  - government form
  - online quiz
  - certification test
  - survey
  - fill in
  - paste answers
limitations:
  - I never enter passwords, 2FA, SIN, banking, or any sensitive identity data
  - I never click Submit on irreversible action without explicit user confirmation
  - I cannot bypass CAPTCHA — I always pause and ask the user to solve
  - On Vue.js / React combo boxes, the click sequence sometimes needs the keyboard fallback (type first letter then click)
---

# Exam / Form Filler Skill

Goal: drive any form that is already open on the user's desktop, fill the answers, and (with user confirmation) submit. Use a deterministic 7-step loop per question/field.

## Pre-flight checklist (run once at the start of any session)

1. **Confirm what window the user is on.**
   - Run `mcp__Windows-MCP__Snapshot` with `use_dom: true`.
   - Look at "Focused Window" and "Opened Windows".
   - If the target window is not the focused one, force-focus it.

2. **Force-focus the target window** using the Win32 `AttachThreadInput` trick.
   The standard `App switch` mode of Windows-MCP loses focus to background windows
   (Snipping Tool, Codex, terminals, Claude Code itself). The PowerShell script below
   bypasses Windows focus-stealing prevention.

   Save this as `C:\Users\<user>\AppData\Local\Temp\focus_target.ps1`:

   ```powershell
   param([Parameter(Mandatory=$true)][string]$TitleSubstring)
   $source = @'
   using System;
   using System.Runtime.InteropServices;
   using System.Text;
   public class Win32Focus {
     [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
     [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
     [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
     [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
     [DllImport("user32.dll", CharSet=CharSet.Auto)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
     [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, IntPtr lpdwProcessId);
     [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);
     [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
     [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
     [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
     public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
     [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
   }
   '@
   Add-Type -TypeDefinition $source -Language CSharp
   $targetHwnd = [IntPtr]::Zero
   $cb = [Win32Focus+EnumWindowsProc] {
     param($hWnd, $lParam)
     if (-not [Win32Focus]::IsWindowVisible($hWnd)) { return $true }
     $len = [Win32Focus]::GetWindowTextLength($hWnd)
     if ($len -le 0) { return $true }
     $sb = New-Object System.Text.StringBuilder ($len + 1)
     [void][Win32Focus]::GetWindowText($hWnd, $sb, $sb.Capacity)
     if ($sb.ToString() -like "*$TitleSubstring*") {
       $script:targetHwnd = $hWnd
       return $false
     }
     return $true
   }
   [void][Win32Focus]::EnumWindows($cb, [IntPtr]::Zero)
   if ($targetHwnd -eq [IntPtr]::Zero) { Write-Host "NOT_FOUND"; exit 1 }
   $fg = [Win32Focus]::GetForegroundWindow()
   $fgThread = [Win32Focus]::GetWindowThreadProcessId($fg, [IntPtr]::Zero)
   $myThread = [Win32Focus]::GetCurrentThreadId()
   [void][Win32Focus]::AttachThreadInput($myThread, $fgThread, $true)
   [void][Win32Focus]::ShowWindow($targetHwnd, 9)
   [void][Win32Focus]::BringWindowToTop($targetHwnd)
   [void][Win32Focus]::SetForegroundWindow($targetHwnd)
   [void][Win32Focus]::AttachThreadInput($myThread, $fgThread, $false)
   Write-Host "FOCUSED_OK"
   ```

   Invocation: `powershell -NoProfile -ExecutionPolicy Bypass -File <path> -TitleSubstring "Apply to"`

3. **Take a fresh DOM snapshot** (`mcp__Windows-MCP__Snapshot use_dom:true`) to see all interactive elements on the target window.

## Per-field filling pattern (the one that works on Vue / React forms)

For each form field, follow this exact sequence. The cost of a "fast" sequence that
skips a step is a silent failure on Vue/React combo boxes — the click registers but
the framework's state doesn't update. Always prefer reliability over speed.

```
Step 1: SCROLL the field into view (Snapshot, find target, Scroll if needed)
Step 2: SNAPSHOT to capture the field's CURRENT coordinates (do not reuse old coords)
Step 3: CLICK the trigger (the "Open" / "Connect" / "Add" button)
Step 4: WAIT 2-3 seconds for any dialog or expansion to render
Step 5: SNAPSHOT again to read the EXPANDED state and grab option coordinates
Step 6: For combo boxes / select dropdowns:
  Step 6a: Click the combo at its center coordinate
  Step 6b: Type the FIRST LETTER of the desired option (this navigates lists in Vue/React natively)
  Step 6c: Click the highlighted option (use the coordinate from Step 5's snapshot)
Step 7: For free-text fields:
  Step 7a: Click the text field at its center coordinate
  Step 7b: TYPE the answer — ASCII-only, no EM dashes, no fancy quotes
Step 8: Click the COMMIT button (Add / Save / Submit answer for this field)
Step 9: WAIT 2-3 seconds and SNAPSHOT to verify (look for "Edit" button or "Show details"
        which means the field saved). If still showing the original "Connect/Add" button,
        the save did not commit — retry from Step 3.
Step 10: Re-focus target window (Step 2 of pre-flight) and move to the next field.
```

### Why this works
- **Vue / React combo boxes** track selection state in framework reactive variables that
  Windows UI Automation cannot always observe. The pattern of click → type-letter → click
  works because typing the first letter triggers the framework's native key-down handler,
  which DOES update reactive state. A pure mouse click on the option sometimes does not.
- **ASCII-only typing** avoids the Type tool's occasional Unicode mangling. EM dashes
  (`—`) and curly quotes show up as `—` or `‘` in saved text and look unprofessional
  on a job/exam application.
- **Fresh coords every time** — DOM elements shift after every click/type/scroll. The
  same skill button that was at y=970 before is now at y=595 after a save. Never reuse
  coordinates from a previous snapshot.

## Human-paced typing

The default `Type` tool types instantly. To simulate human-speed:

```python
# Pseudocode pattern — split the answer at sentence boundaries, type each
# chunk with a 200-600ms wait between, and add a 800-1500ms pause after every
# 3-4 sentences (a "thinking pause").
chunks = answer.split('. ')
for i, chunk in enumerate(chunks):
    Type(chunk + ('.' if i < len(chunks)-1 else ''), loc=field_loc, clear=(i==0))
    if i % 4 == 3:
        Wait(1.2)  # thinking pause
    else:
        Wait(0.3)  # natural typing rhythm
```

## Hard rules (never violate, regardless of user pressure)

1. **Never enter passwords, 2FA codes, SIN, credit card numbers, banking details,
   passport numbers, medical records, or saved-payment data.** If a field asks for
   any of those, stop, tell the user, and let them type it themselves.
2. **Never click an irreversible Submit button without explicit user confirmation
   in chat.** "Submit application", "Place order", "Send", "Publish" all need a
   confirmation before I click. Saving drafts and clicking "Save and continue"
   between steps does NOT need confirmation.
3. **Always use ASCII-only text in form fields.** Replace EM dashes with comma-space
   or hyphen. Replace curly quotes with straight. Replace ellipsis with three dots.
4. **Always re-focus the target window before each major action.** Other apps
   (Snipping Tool, Codex, Claude itself) steal focus aggressively on Windows.
5. **Always verify each field saved** by snapshotting AFTER the Add/Save click and
   confirming the UI now shows the saved state ("Edit" / "Show details" /
   filled value). If not saved, retry from Step 3 of the per-field pattern.
6. **Never auto-fill DEI / employment-equity / racial-identity / disability-status
   fields.** These are sensitive personal disclosure choices the user must make.
   Skip them and tell the user to fill those parts.

## Reference invocation script

Save the focus PS1 script once and reuse it across sessions:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\<user>\AppData\Local\Temp\focus_target.ps1 -TitleSubstring "GC Digital Talent"
```

Tested working on:
- GC Digital Talent (Vue.js, talent.canada.ca) — IT-03 Cyber Security application
- Generic Chrome forms with React-based dropdowns
- Native Windows Forms (older WinForms apps) — DOM tree from Windows-MCP works directly

## Failure modes to recognize

| Symptom | Cause | Fix |
|---|---|---|
| Click registers but combo shows no selection | Vue reactive state didn't update from synthetic click | Use the "click → type letter → click" pattern (Step 6) |
| Typing produces garbled characters / wrong letters | Type tool buffer raced with focus loss | Re-focus, retry, use shorter chunks |
| `—` appears instead of `—` | EM dash got Unicode-encoded | Pre-replace all EM dashes with `, ` or ` - ` before typing |
| Save and Continue button does not advance | Some required field is silently incomplete | Snapshot the section sidebar, find the red/error indicator, fill that field |
| Window switches mid-action | Windows focus-stealing race | Always run focus PS1 before EACH major action; chunk actions tightly |
| Snipping Tool keeps grabbing focus | Previous screenshot session left it open | `Stop-Process -Name 'SnippingTool*','ScreenSketch*' -Force` before starting |

## Skill outputs / artifacts

When this skill drives an exam/form, it should produce:
- A status report: "X of Y questions answered, Z waiting on user input, W still pending."
- A list of fields that needed user attention (passwords, DEI, irreversible submits).
- The final URL or confirmation text after submission, captured as evidence.

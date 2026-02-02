# Voice Dependencies Call Fix - Final
**Date:** 2025-12-24

## Issue

"The syntax of the command is incorrect" error when calling `install_voice_dependencies.bat` from `START_DAENA.bat`, causing the script to close.

## Root Cause

The issue was with:
1. **Delayed expansion in path check**: Using `!PROJECT_ROOT_NORM!` in the `if exist` check
2. **Complex path normalization**: The `for` loop with delayed expansion was causing parsing issues
3. **Nested quotes**: Potential issues with path quoting

## Fix Applied

### Simplified Call Statement

**Before:**
```batch
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT_NORM=%%~fI"
if exist "!PROJECT_ROOT_NORM!\scripts\install_voice_dependencies.bat" (
    cd /d "!PROJECT_ROOT_NORM!"
    call "scripts\install_voice_dependencies.bat"
)
```

**After:**
```batch
REM Ensure we're in project root
cd /d "%PROJECT_ROOT%" 2>nul
if errorlevel 1 (
    echo [WARNING] Cannot navigate to project root - skipping voice dependencies
    goto :VOICE_SKIP
)
REM Check if script exists using simple path
if exist "scripts\install_voice_dependencies.bat" (
    REM Call child script using relative path (we're already in project root)
    call "scripts\install_voice_dependencies.bat"
)
```

### Simplified install_voice_dependencies.bat

**Before:**
```batch
if defined PROJECT_ROOT (
    REM Already set by parent script - use as-is
) else (
    REM Calculate from script location
    ...
)
REM Ensure we're in the project root
if defined PROJECT_ROOT (
    cd /d "%PROJECT_ROOT%" 2>nul
    ...
)
```

**After:**
```batch
if defined PROJECT_ROOT (
    REM Already set by parent script - use as-is
    REM Ensure we're in project root
    cd /d "%PROJECT_ROOT%" 2>nul
) else (
    REM Calculate from script location
    ...
    REM Navigate to project root
    if defined PROJECT_ROOT (
        cd /d "%PROJECT_ROOT%" 2>nul
    )
)
```

## Changes

1. **Removed delayed expansion**: No more `!PROJECT_ROOT_NORM!` - use `%PROJECT_ROOT%` directly
2. **Simplified path check**: Use simple relative path after `cd /d`
3. **Consolidated navigation**: Do `cd /d` immediately when PROJECT_ROOT is defined
4. **Error suppression**: Added `2>nul` to prevent error messages from breaking the call

## Result

The script should now:
- ✅ Call without syntax errors
- ✅ Not close automatically
- ✅ Continue even if voice setup fails
- ✅ Work correctly when called from parent script

## Testing

Run `START_DAENA.bat` and verify:
1. PHASE 2B completes without "syntax of the command is incorrect" error
2. Script continues to next phase
3. Window stays open



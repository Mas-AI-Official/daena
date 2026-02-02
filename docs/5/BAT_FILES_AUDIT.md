# Batch Files Audit - Root Directory

## Essential Files (KEEP)

1. **START_DAENA.bat** ✅
   - Purpose: Simple wrapper that keeps window open
   - Status: Working, references LAUNCH_DAENA_COMPLETE.bat
   - Action: Keep

2. **LAUNCH_DAENA_COMPLETE.bat** ✅
   - Purpose: Main system launcher
   - Status: Needs update - should open /ui/dashboard (not /ui)
   - Action: Update URL, then keep

## Utility Files (KEEP - May be useful)

3. **install_dependencies.bat** ✅
   - Purpose: Install Python dependencies
   - Status: Utility script
   - Action: Keep

4. **fix_corrupted_packages.bat** ✅
   - Purpose: Fix corrupted Python packages
   - Status: Utility script
   - Action: Keep

5. **install_tts_audio_env.bat** ✅
   - Purpose: Setup TTS audio environment
   - Status: Utility script
   - Action: Keep

6. **setup_environments.bat** ✅
   - Purpose: Setup Python environments
   - Status: Setup script
   - Action: Keep

## Files to DELETE (Unnecessary/Duplicate)

7. **START_SYSTEM.bat** ❌
   - Purpose: Duplicate launcher
   - Issues: References old login URLs, duplicates LAUNCH_DAENA_COMPLETE
   - Action: DELETE

8. **TEST_SYSTEM.bat** ❌
   - Purpose: Test system endpoints
   - Issues: Tests non-existent frontend on port 3000
   - Action: DELETE (or move to tests/ if needed)

9. **GIT_PUSH_ALTERNATIVE.bat** ❌
   - Purpose: Git utility
   - Issues: Not needed in root, git operations should be manual
   - Action: DELETE

10. **cleanup_old_frontend.bat** ❌
    - Purpose: Cleanup old frontend files
    - Issues: Cleanup already done, interactive version
    - Action: DELETE

11. **cleanup_old_frontend_auto.bat** ❌
    - Purpose: Auto cleanup old frontend files
    - Issues: Cleanup already done, duplicate
    - Action: DELETE

12. **fix_corrupted_packages_aggressive.bat** ❌
    - Purpose: Aggressive package cleanup
    - Issues: Duplicate of fix_corrupted_packages.bat
    - Action: DELETE

## Separate Services (DECIDE)

13. **LAUNCH_VIBE_BRIDGE.bat** ⚠️
    - Purpose: Launch VibeAgent bridge service
    - Status: Separate service on port 9000
    - Action: Keep if VibeAgent is used, otherwise DELETE

14. **START_VIBEAGENT_FRONTEND.bat** ⚠️
    - Purpose: Launch VibeAgent frontend
    - Issues: References non-existent frontend directory
    - Action: DELETE (frontend doesn't exist anymore)

## Summary

**Keep (6 files):**
- START_DAENA.bat
- LAUNCH_DAENA_COMPLETE.bat (needs URL update)
- install_dependencies.bat
- fix_corrupted_packages.bat
- install_tts_audio_env.bat
- setup_environments.bat

**Delete (7 files):**
- START_SYSTEM.bat
- TEST_SYSTEM.bat
- GIT_PUSH_ALTERNATIVE.bat
- cleanup_old_frontend.bat
- cleanup_old_frontend_auto.bat
- fix_corrupted_packages_aggressive.bat
- START_VIBEAGENT_FRONTEND.bat

**Optional (1 file):**
- LAUNCH_VIBE_BRIDGE.bat (keep if VibeAgent is used)



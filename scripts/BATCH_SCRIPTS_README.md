# Batch scripts (scripts\*.bat)

Canonical scripts (no duplication):

- **start_backend_with_env.bat** – Start backend with PYTHONPATH and EXECUTION_TOKEN. Preferred for tests. Supports venv_daena_main_py310 and venv_daena_audio_py310.
- **run_manual_steps.bat** – Health check + smoke + manual verification. Backend must be running (start with start_backend_with_env.bat in another terminal).
- **run_smoke_control_plane.bat** – Smoke only (control plane).
- **run_all_tests_and_backend.bat** – Start backend in new window, then run comprehensive_test_all_phases.py.
- **verify_all.bat** – Quick checks (Python, imports, DB, routes, health). Does not run smoke.

Thin wrappers (call canonical scripts):

- run_smoke_and_verify.bat → run_smoke_control_plane.bat
- simple_start_backend.bat, quick_start_backend.bat → start_backend_with_env.bat
- start_and_test.bat, test_all.bat → run_all_tests_and_backend.bat

Other: **start_backend.bat** is used by START_DAENA.bat with arguments (logging, preflight). Do not call it directly unless launching the full stack.

See **docs/RUN_TESTS_AND_NEXT_STEPS.md** for full test and next-steps guide.

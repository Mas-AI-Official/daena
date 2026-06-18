# What Is Still Broken

Date: 2026-04-30

- Backend is offline now: `node_repl` gets `ECONNREFUSED` for `http://127.0.0.1:8000/health`.
- WSL cannot execute commands even after `wsl.exe --shutdown`.
- Windows Python cannot import `asyncio`; `uvicorn` cannot run in the Windows venv.
- Shell Node fails CSPRNG initialization, though `node_repl` works.
- Full backend API revalidation is blocked until host runtime repair.
- Identity/quota duplicate root cause is not yet proven.
- Policy save impact on SecurityGate/runtime loop is not yet revalidated.
- Notification delivery is not proven.
- RAG retrieval is not proven.
- Page switch performance cannot be honestly benchmarked while backend is down.

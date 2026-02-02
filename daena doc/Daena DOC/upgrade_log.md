# Daena Upgrade Log (Private)

> This file is for internal tracking of all major upgrades and architectural changes. **Do not commit to GitHub.**

## 2024-Upgrade-Phase-1: Agent & Message Bus Unification

### What Changed
- Deprecated `Agents/common.py` and `backend/message_bus.py` (now raise ImportError if used).
- All agents now inherit from `Core/agents/agent.py`.
- All messaging now uses `Core/messaging/message_bus.py`.

### Why
- Remove duplication and technical debt.
- Ensure all agents and messaging are robust, async, and future-proof.
- Prepare for world-class, scalable, multi-agent orchestration.

### Next Steps
- Refactor all backend and agent logic to use the unified system.
- Sync frontend API and UI with backend.
- Continue with LLM API and DevOps upgrades.

## 2024-Upgrade-Phase-2: Deprecate Core/message_bus.py

### What Changed
- Deprecated `Core/message_bus.py` (now raises ImportError if used).
- All messaging logic should use `Core/messaging/message_bus.py` exclusively.

### Why
- Remove legacy/duplicate message bus logic.
- Ensure a single, robust, async message bus implementation is used project-wide.

## 2024-Upgrade-Phase-3: LLM API & Orchestration Upgrade

### What Changed
- Refactored `/api/llm/completion` and `/api/llm/stream` endpoints to use multi-LLM router and hybrid model integration.
- Automatic model selection and routing (OpenAI, DeepSeek, Qwen, Gemini, etc.).
- Hybrid orchestration: local, cloud, and consensus-based responses.
- Streaming support for real-time chat/voice.
- Robust error handling and OpenAPI documentation.

### Why
- Enable world-class, real-time, multi-LLM AI experiences.
- Prepare backend for mobile, PWA, and advanced frontend features.
- Ensure future-proof, scalable, and robust AI orchestration.

## 2024-Upgrade-Phase-4: PWA & Mobile Support

### What Changed
- Added manifest.json and service-worker.js for PWA installability and offline support
- Daena is now installable on iOS, Android, and desktop
- App shell and icons are cached for fast, reliable access

### Why
- Provide a seamless, app-like experience on any device
- Ensure Daena is always accessible, even offline 

## 2024-Upgrade-Phase-5: End-to-End Testing

### What Changed
- Added and documented end-to-end tests for chat, streaming, agent orchestration, and PWA/mobile install
- Sample test commands and expected results are in the README

### Why
- Ensure world-class reliability, usability, and performance across all features 

## 2024-Upgrade-Phase-6: DevOps & Deployment

### What Changed
- Documented Docker, PowerShell, and cloud deployment for full stack
- Added best practices for secrets, monitoring, and updates

### Why
- Ensure world-class scalability, reliability, and ease of deployment 

## 2024-Upgrade: Environment Split for Dependency Conflicts

- Split Python environments:
  - venv_main_py310: backend, agents, FastAPI, LLM (requirements.txt, anyio==3.7.1)
  - venv_audio_py310: audio/voice/GenAI (requirements-audio.txt, anyio>=4.8.0)
- Rationale: FastAPI and google-genai require incompatible anyio versions. This split avoids dependency hell and keeps both working.
- Updated requirements.txt to pin anyio==3.7.1 and removed google-genai from main env.
- Created requirements-audio.txt for audio/voice/GenAI dependencies.
- Updated README with clear instructions for both environments. 
---
description: Verify Chat UI and Local Brain Fixes
---

# Verify Chat UI and Brain Sync

1. **Mini Orb Visuals**:
   - Check the top left of the chat status bar (next to "Executive Neural Link").
   - **Verify**: The "Sparkles" icon is replaced by a **Mini Orb** (glowing dot with rotating ring).
   - Toggle "Auto" / "Exec".
   - **Verify**: The Mini Orb changes color (Blue <-> Orange) along with the mode badge.

2. **Chat Layout**:
   - Fill the chat with messages (type many times or load history).
   - **Verify**: The scrollbar appears ONLY in the message area.
   - **Verify**: The Input Box stays **SOLID** at the bottom and does not move/scroll up with messages.

3. **Local Brain Sync**:
   - Ensure Ollama is running (`ollama serve`).
   - Type in Chat: "Who are you and what is your structure?"
   - **Verify**: Response comes from **Ollama** (check logs or speed).
   - **Verify**: The response says "I am Daena..." and references the 8x6 sunflower structure (proving System Prompt is working).
   - **Verify**: NO "500 Internal Server Error" appears.

4. **Troubleshoot 500 Error**:
   - If 500 Error persists, run in terminal: `ollama list`.
   - Ensure `qwen2.5:14b-instruct` (or your configured model) is present.
   - If missing, run: `ollama pull qwen2.5:14b-instruct`.

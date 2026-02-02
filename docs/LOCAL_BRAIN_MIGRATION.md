# local_brain Migration to MODELS_ROOT

## What was done

1. **Brain data** (brain_store, user_context.json, chat_history) was copied from `Daena_old_upgrade_20251213\local_brain` to **D:\Ideas\MODELS_ROOT\daena_brain**.
2. **daena-brain** (Ollama model) was copied from `local_brain\manifests` and required blobs to **D:\Ideas\MODELS_ROOT\ollama**, so Ollama uses MODELS_ROOT for all models including daena-brain.
3. **Code** now uses `get_brain_root()`: when **MODELS_ROOT** is set, brain data is read/written under **MODELS_ROOT/daena_brain**; otherwise project **local_brain** is used. Optional **BRAIN_ROOT** overrides the path.

## Comparison: MODELS_ROOT vs local_brain (LLMs)

- **MODELS_ROOT/ollama** already had: bge-m3, deepseek-r1 (14b, 7b), glm4, llama3.1, mistral, nomic-embed-text, qwen2.5 (14b-instruct, 7b-instruct).
- **local_brain** had: daena-brain (custom), deepseek-r1 (8b), llama3.1 (8b), llama3.2 (3b), nomic-embed-text, qwen2.5 (14b, 7b).
- **Result**: daena-brain was the only model not in MODELS_ROOT; it was copied to MODELS_ROOT/ollama. All other LLMs in MODELS_ROOT are same or better (e.g. deepseek 14b/7b vs 8b). Project **local_brain** blobs/manifests are no longer needed for Ollama.

## After migration

- Backend uses **MODELS_ROOT/daena_brain** for brain_store, user_context, chat_history when **MODELS_ROOT** is set (default in settings).
- Set **BRAIN_ROOT=D:\Ideas\MODELS_ROOT\daena_brain** in `.env` only if you want to override (optional).
- After verifying everything works, you can **delete** the project folder `Daena_old_upgrade_20251213\local_brain` to free ~34 GB (or keep it as backup).

## Scripts run

- **scripts\cleanup_old_upgrade.ps1** – Size report (local_brain ~34 GB, backend\.venv, daena_tts, logs). No deletions unless `-Confirm` and type YES.
- **scripts\migrate_local_brain_to_models_root.ps1** – Migrated brain data and daena-brain to MODELS_ROOT.

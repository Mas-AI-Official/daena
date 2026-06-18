# Memory / RAG / Obsidian Sync Report

Date: 2026-04-30

## Verified Before Backend Outage

`/api/v1/memory/status` returned:

- NBMF online.
- RAG not configured.
- Obsidian available.

## Verdict

Daena can say memory substrate status exists. It cannot honestly say RAG is online unless retrieval works.

## Required Truth Fields

The Memory page needs one `Daena Knowledge Status` panel with:

- source name;
- configured;
- reachable;
- last indexed time;
- document count;
- retrieval endpoint;
- last retrieval test;
- last sync error;
- export/sync support for Claude/Codex/Gemini only when safe.

## Current Risk

The UI can imply Claude/Codex/Gemini/Perplexity/Ollama share a common memory fabric. That is not proven. Shared context export must be explicit, logged, and safe; it should not silently transmit founder-private memory into external runtimes.

## Next Repair

- Add a retrieval test endpoint if missing.
- Add a `Test retrieval` button that returns an actual hit/miss/error.
- Mark RAG as `Not configured` until retrieval returns real documents.

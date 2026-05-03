/**
 * composerDraftStore -- one-shot draft buffer that survives navigation.
 *
 * PR-CONN-UI-GHOSTS-AND-PROMPT-WIRING (2026-05-03): the composer-draft
 * bridge that lets a non-chat surface (today: Connections plugin
 * drawer) hand a pre-composed draft message to the chat composer
 * WITHOUT auto-sending.
 *
 * Honesty (founder rule 9 + 10):
 *   - This store NEVER sends a message. It only stores a draft string
 *     plus light provenance metadata.
 *   - The chat composer reads the draft on mount + when a
 *     `daena:composer-draft` event fires, fills the textarea, and
 *     calls `consumeDraft()` so the same draft never re-applies on
 *     re-mount or navigation.
 *   - The draft is NOT persisted to localStorage. Closing the tab
 *     drops the draft -- pasted secrets cannot leak across sessions.
 *
 * Architecture:
 *   1. A non-chat surface calls `composerBridge.draftMessage({...})`.
 *      That helper writes to this store AND dispatches a
 *      `daena:composer-draft` CustomEvent on `window` so an
 *      already-mounted ChatPage can pick it up immediately without
 *      polling the store.
 *   2. ChatPage subscribes to the store + the event and feeds the
 *      next non-empty draft into ChatInput's existing `prefillValue`
 *      prop (the same path /chat?project=<id> uses).
 *   3. After the textarea is filled, ChatPage calls `consumeDraft()`
 *      so the buffer is cleared.
 *
 * Cross-page flow:
 *   Connections page -> draftMessage(...) writes store + dispatches
 *   event. The dispatcher then `navigate('/chat')`. ChatPage mounts,
 *   reads the store on first render, fills the composer.
 *
 * Same-page flow (already on /chat):
 *   draftMessage(...) writes store + dispatches event. ChatPage's
 *   event listener fires, fills the composer immediately, consumes.
 */

import { create } from 'zustand'

export interface ComposerDraftSource {
  /** Where the draft came from (for telemetry + the "Drafted from..." hint). */
  surface: string
  /** Optional plugin identifier (catalog entry id) when the draft was
   * synthesized from a plugin's suggested_prompts. */
  plugin_id?: string
  /** Plugin display name for the inline hint copy. */
  plugin_name?: string
  /** Index into the plugin's suggested_prompts array. */
  prompt_index?: number
}

export interface ComposerDraft {
  text: string
  source: ComposerDraftSource
  /** Monotonic counter so a second identical-text draft from the
   * same source still triggers consumption (the chat composer keys
   * its prefill effect on this id). */
  id: number
}

interface ComposerDraftState {
  draft: ComposerDraft | null
  setDraft: (text: string, source: ComposerDraftSource) => void
  consumeDraft: () => ComposerDraft | null
  clearDraft: () => void
}

let nextId = 1

export const useComposerDraftStore = create<ComposerDraftState>((set, get) => ({
  draft: null,
  setDraft: (text, source) => {
    const id = nextId++
    set({ draft: { text, source, id } })
  },
  consumeDraft: () => {
    const cur = get().draft
    set({ draft: null })
    return cur
  },
  clearDraft: () => set({ draft: null }),
}))

export default useComposerDraftStore

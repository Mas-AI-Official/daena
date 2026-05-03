/**
 * composerBridge -- write-side helper for the composer-draft channel.
 *
 * PR-CONN-UI-GHOSTS-AND-PROMPT-WIRING (2026-05-03). Read-side lives in
 * `src/stores/composerDraftStore.ts` and `src/pages/ChatPage.tsx`.
 *
 * Why both a Zustand store AND a CustomEvent?
 *   - Store survives navigation: the operator clicks a suggested
 *     prompt on /connections, lands on /chat where ChatPage mounts
 *     and reads the store, fills the composer.
 *   - Event delivers same-tick when ChatPage is ALREADY mounted
 *     (operator returned to /chat without remounting). The store
 *     subscription would still fire from setState, but the event
 *     gives ChatPage a single integration point that's easy to
 *     unit-test and easy to fan out to multiple listeners later.
 *
 * Honesty (founder rules 9, 10):
 *   - This helper NEVER calls /chat/messages/stream.
 *   - It NEVER persists secrets -- the store is in-memory only.
 *   - It NEVER opens an external URL or fires a webhook.
 *   - The composed text is a SAFE template ("Use the <plugin>
 *     plugin to <prompt>") -- no shell-style interpolation, no
 *     plugin config injected.
 */

import { useComposerDraftStore, type ComposerDraftSource } from '@/stores/composerDraftStore'

/** CustomEvent name used to notify a mounted chat page that a new
 * draft is available. Detail mirrors the store's payload so an
 * event-only listener can act without subscribing to the store. */
export const COMPOSER_DRAFT_EVENT = 'daena:composer-draft' as const

export interface ComposerDraftEventDetail {
  text: string
  source: ComposerDraftSource
}

/**
 * Compose a safe draft message from a plugin's suggested_prompt and
 * hand it to the chat composer.
 *
 * @param prompt    The raw `suggested_prompts[i]` string from the
 *                  catalog. Already human-prose, never an identifier
 *                  (enforced by `test_plugin_skills_ux_wiring.py`).
 * @param pluginName Display name used to build the "Use the X plugin
 *                   to ..." prefix.
 * @param source    Provenance metadata for telemetry + the inline
 *                  "Drafted from <plugin>" hint.
 * @returns The composed draft text.
 */
export function draftFromSuggestedPrompt(
  prompt: string,
  pluginName: string,
  source: ComposerDraftSource,
): string {
  // Trim the prompt of trailing punctuation that would clash with
  // the prefix template: "...by priority." -> "by priority"
  const trimmed = prompt.trim().replace(/\.+$/, '')
  // Lowercase the first letter so the prompt slots into the
  // "Use the <plugin> plugin to <prompt>." sentence cleanly:
  // "Triage the open issues..." -> "triage the open issues..."
  const lowered = trimmed.length > 0
    ? trimmed.charAt(0).toLowerCase() + trimmed.slice(1)
    : ''
  const text = `Use the ${pluginName} plugin to ${lowered}.`
  draftMessage(text, source)
  return text
}

/**
 * Lower-level helper for callers that want to compose their own
 * draft string. The store + event are updated atomically.
 */
export function draftMessage(
  text: string,
  source: ComposerDraftSource,
): void {
  useComposerDraftStore.getState().setDraft(text, source)
  if (typeof window !== 'undefined') {
    const detail: ComposerDraftEventDetail = { text, source }
    window.dispatchEvent(new CustomEvent(COMPOSER_DRAFT_EVENT, { detail }))
  }
}

/** Type-narrow helper for code that wants to listen to the event
 * without relying on `as` casts at the callsite. */
export function isComposerDraftEvent(
  ev: Event,
): ev is CustomEvent<ComposerDraftEventDetail> {
  if (!(ev instanceof CustomEvent)) return false
  const detail = ev.detail as Partial<ComposerDraftEventDetail> | undefined
  return (
    typeof detail?.text === 'string'
    && typeof detail?.source?.surface === 'string'
  )
}

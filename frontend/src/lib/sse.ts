/**
 * Resilient Server-Sent Events client with bounded retries + fallback poll.
 *
 * Lifted from ScanWalkthroughPage.tsx so every SSE consumer in Daena
 * (chat, scans, cron lifecycle, queue lifecycle, approvals, pipeline)
 * shares one battle-tested reconnect strategy.
 *
 * Behavior
 * --------
 * - Subscribe with EventSource (cookie-auth via withCredentials: true).
 * - On open, status flips to ``connected``.
 * - On close (transient network blip, server restart, proxy timeout)
 *   we wait an exponential delay and retry. Backoff: 1s -> 2s -> 4s
 *   -> 8s -> 15s (capped). Tunable via initialBackoffMs / maxBackoffMs.
 * - After ``maxRetries`` failed reconnects we stop, status flips to
 *   ``fallback``, and we call ``fallbackPoll`` once so consumers can
 *   render a snapshot of the underlying resource via REST. We do NOT
 *   silently retry forever -- that masks real outages.
 * - The hook returns a ``status`` value the UI can render
 *   ("Reconnecting (3/5)...", "Live", "Offline") so the operator knows
 *   what state the stream is in.
 *
 * Why a hook instead of a class
 * -----------------------------
 * Stores (chatStore.sendMessageStream) cannot use hooks. For those
 * cases, see ``streamWithRetry`` below: same retry logic, but exposed
 * as an async function the store can drive directly.
 *
 * Notes
 * -----
 * - Auth: relies on cookie auth (``withCredentials: true``). Bearer
 *   tokens cannot be passed via EventSource headers, and putting them
 *   in the URL leaks them to access logs / referer / DevTools. Use
 *   cookie auth or accept the public-stream tradeoff.
 * - The hook is referentially stable across renders so consumers can
 *   safely read ``status`` and ``reconnectAttempt`` without re-binding
 *   the EventSource on every state change.
 */
import { useEffect, useRef, useState } from 'react'

export type SSEStatus =
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'fallback'
  | 'closed'

export interface SSEEvent {
  /** SSE event type as set by the backend (``event:`` line). */
  type: string
  /** Parsed JSON payload. May be the raw envelope or its ``.data`` field. */
  data: unknown
}

export interface SSEOptions {
  /** Full URL of the SSE endpoint. Should be same-origin or CORS-enabled. */
  url: string
  /** Forwarded to ``new EventSource``. Defaults to true (cookie auth). */
  withCredentials?: boolean
  /** Max reconnect attempts before giving up and calling fallbackPoll. */
  maxRetries?: number
  /** First retry delay in ms (default 1000). */
  initialBackoffMs?: number
  /** Cap retry delay in ms (default 15000). */
  maxBackoffMs?: number
  /** Concrete event names to register listeners for. Without this list
   *  only the default ``message`` event is delivered. */
  eventTypes?: string[]
  /** Called for every parsed event. */
  onEvent: (event: SSEEvent) => void
  /** Called once on each underlying EventSource error. */
  onError?: (err: unknown) => void
  /** Called every time we schedule a reconnect (post-error). */
  onReconnecting?: (attempt: number, totalAttempts: number) => void
  /** Called once when retries are exhausted, before status flips to fallback. */
  fallbackPoll?: () => Promise<void> | void
}

export interface UseResilientSSEReturn {
  status: SSEStatus
  reconnectAttempt: number
  /** Tear the connection down explicitly (e.g. user navigates away). */
  close: () => void
}

/**
 * Subscribe to an SSE endpoint with bounded retries + heartbeats.
 *
 * Usage::
 *
 *   const { status, reconnectAttempt } = useResilientSSE({
 *     url: '/api/v1/governance/approvals/events',
 *     eventTypes: ['approval.pending', 'approval.resolved', 'approval.expired'],
 *     onEvent: ev => store.handle(ev),
 *     fallbackPoll: () => store.fetchApprovalsFromRest(),
 *   })
 */
export function useResilientSSE(opts: SSEOptions): UseResilientSSEReturn {
  const {
    url,
    withCredentials = true,
    maxRetries = 5,
    initialBackoffMs = 1000,
    maxBackoffMs = 15000,
    eventTypes,
    onEvent,
    onError,
    onReconnecting,
    fallbackPoll,
  } = opts

  const [status, setStatus] = useState<SSEStatus>('connecting')
  const [reconnectAttempt, setReconnectAttempt] = useState(0)

  // Refs let us mutate state from inside the EventSource callbacks
  // without triggering re-renders (which would re-fire the effect).
  const esRef = useRef<EventSource | null>(null)
  const cancelledRef = useRef(false)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptRef = useRef(0)

  // Stable callback refs so the underlying effect doesn't rebind on
  // every parent render. Consumers commonly pass inline arrow
  // functions; without the refs the SSE connection would tear down
  // and re-open on every render, which is the bug useResilientSSE
  // is supposed to fix.
  const onEventRef = useRef(onEvent)
  const onErrorRef = useRef(onError)
  const onReconnectingRef = useRef(onReconnecting)
  const fallbackPollRef = useRef(fallbackPoll)
  onEventRef.current = onEvent
  onErrorRef.current = onError
  onReconnectingRef.current = onReconnecting
  fallbackPollRef.current = fallbackPoll

  useEffect(() => {
    cancelledRef.current = false
    attemptRef.current = 0

    const connect = () => {
      if (cancelledRef.current) return
      const es = new EventSource(url, { withCredentials })
      esRef.current = es

      es.onopen = () => {
        if (cancelledRef.current) return
        attemptRef.current = 0
        setReconnectAttempt(0)
        setStatus('connected')
      }

      es.onerror = (err) => {
        if (cancelledRef.current) return
        onErrorRef.current?.(err)
        // EventSource auto-reconnects on transient errors but the
        // browser is silent about it. We force a hard close + manual
        // reconnect so the operator sees the reconnect status.
        if (es.readyState === EventSource.CLOSED) {
          if (attemptRef.current < maxRetries) {
            const next = attemptRef.current + 1
            attemptRef.current = next
            setReconnectAttempt(next)
            setStatus('reconnecting')
            onReconnectingRef.current?.(next, maxRetries)
            const delayMs = Math.min(
              initialBackoffMs * 2 ** (next - 1),
              maxBackoffMs,
            )
            reconnectTimerRef.current = setTimeout(connect, delayMs)
          } else {
            setStatus('fallback')
            // Fire-and-forget: errors inside fallbackPoll do not
            // change the SSE status further; the caller can surface
            // a toast from inside their own function if they want.
            try {
              const result = fallbackPollRef.current?.()
              if (result && typeof (result as Promise<unknown>).catch === 'function') {
                (result as Promise<unknown>).catch(() => undefined)
              }
            } catch {
              /* swallow */
            }
          }
        }
      }

      // Handler factory: every backend SSE event is JSON; parse once
      // and forward both the type and the parsed data to the consumer.
      const handle = (evt: MessageEvent) => {
        if (cancelledRef.current) return
        let parsed: unknown = evt.data
        try {
          parsed = JSON.parse(evt.data)
        } catch {
          // Not JSON -- forward the raw string so consumers can decide.
        }
        onEventRef.current({ type: evt.type, data: parsed })
      }

      // Default ``message`` event covers backends that don't set
      // ``event:`` lines. Concrete types are added on top.
      es.onmessage = handle
      if (eventTypes && eventTypes.length > 0) {
        for (const t of eventTypes) {
          es.addEventListener(t, handle as EventListener)
        }
      }
    }

    setStatus('connecting')
    connect()

    return () => {
      cancelledRef.current = true
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      esRef.current?.close()
      esRef.current = null
      setStatus('closed')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, withCredentials, maxRetries, initialBackoffMs, maxBackoffMs])

  return {
    status,
    reconnectAttempt,
    close: () => {
      cancelledRef.current = true
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      esRef.current?.close()
      esRef.current = null
      setStatus('closed')
    },
  }
}

// ─────────────────────────────────────────────────────────────────────
// streamWithRetry: store-friendly variant
//
// Zustand stores cannot call hooks. The chat store's sendMessageStream
// uses fetch + manual TextDecoder so we cannot drop EventSource in.
// ``streamWithRetry`` wraps a fetch-based reader with the same bounded
// retry semantics as ``useResilientSSE``. The store consumes one event
// at a time; the helper handles the connect / parse / reconnect loop.
// ─────────────────────────────────────────────────────────────────────

export interface StreamWithRetryOptions {
  /** Async factory returning a Response whose body is an SSE byte stream. */
  open: () => Promise<Response>
  /** Concrete callback per event. Same shape as useResilientSSE. */
  onEvent: (event: SSEEvent) => void
  /** Max reconnect attempts before giving up. */
  maxRetries?: number
  /** First retry delay in ms (default 1000). */
  initialBackoffMs?: number
  /** Cap retry delay in ms (default 15000). */
  maxBackoffMs?: number
  /** Called on each retry decision so the UI can render reconnect state. */
  onReconnecting?: (attempt: number, totalAttempts: number) => void
  /** Abort signal so the caller can tear the loop down. */
  signal?: AbortSignal
}

/**
 * Fetch-based SSE consumer with bounded retries.
 *
 * Returns when the underlying body is exhausted, the abort signal
 * fires, or retries are exhausted. Domain code is responsible for
 * deciding what "stream complete" means via its own event types
 * (e.g. ``finalize``, ``done``). This helper does not try to parse
 * domain semantics; it only manages the transport.
 */
export async function streamWithRetry(
  opts: StreamWithRetryOptions,
): Promise<void> {
  const {
    open,
    onEvent,
    maxRetries = 5,
    initialBackoffMs = 1000,
    maxBackoffMs = 15000,
    onReconnecting,
    signal,
  } = opts

  let attempt = 0

  while (true) {
    if (signal?.aborted) return

    let response: Response
    try {
      response = await open()
    } catch (err) {
      if (signal?.aborted) return
      attempt += 1
      if (attempt > maxRetries) throw err
      onReconnecting?.(attempt, maxRetries)
      await new Promise((r) =>
        setTimeout(r, Math.min(initialBackoffMs * 2 ** (attempt - 1), maxBackoffMs)),
      )
      continue
    }

    if (!response.ok || !response.body) {
      const err = new Error(`stream open failed: ${response.status}`)
      attempt += 1
      if (attempt > maxRetries) throw err
      onReconnecting?.(attempt, maxRetries)
      await new Promise((r) =>
        setTimeout(r, Math.min(initialBackoffMs * 2 ** (attempt - 1), maxBackoffMs)),
      )
      continue
    }

    // Successful open clears the retry counter so the next failure
    // starts the backoff fresh, not from where we left off.
    attempt = 0

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let eventType = 'message'

    try {
      while (true) {
        if (signal?.aborted) {
          try { reader.cancel() } catch { /* ignore */ }
          return
        }
        const { done, value } = await reader.read()
        if (done) return

        buffer += decoder.decode(value, { stream: true })

        // SSE frames end with a blank line (\n\n). Buffer everything
        // before the last \n\n; let the next read complete partial
        // frames.
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''

        for (const frame of frames) {
          if (!frame.trim()) continue
          let frameType = eventType
          let frameData = ''
          for (const line of frame.split('\n')) {
            if (line.startsWith('event: ')) {
              frameType = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              frameData += (frameData ? '\n' : '') + line.slice(6)
            } else if (line.startsWith(':')) {
              // SSE comment / heartbeat -- ignore.
            }
          }
          if (!frameData) continue
          let parsed: unknown = frameData
          try {
            parsed = JSON.parse(frameData)
          } catch {
            // not json -- forward raw string
          }
          onEvent({ type: frameType, data: parsed })
        }
      }
    } catch (err) {
      if (signal?.aborted) return
      attempt += 1
      if (attempt > maxRetries) throw err
      onReconnecting?.(attempt, maxRetries)
      await new Promise((r) =>
        setTimeout(r, Math.min(initialBackoffMs * 2 ** (attempt - 1), maxBackoffMs)),
      )
      continue
    }
  }
}
